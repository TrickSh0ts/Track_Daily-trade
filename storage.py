# -*- coding: utf-8 -*-
"""
Paths seguros para dados/recursos + DataStore com leitura/escrita robusta.

- DATA_DIR: %LOCALAPPDATA%/Tradeiros (ou equivalente), com fallback para pasta local.
- Recursos (logo, ico, qss...) resolvidos compatíveis com PyInstaller (sys._MEIPASS).
- save_json: escrita atómica para evitar ficheiros corrompidos.
- BASE_DIR: compatibilidade p/ código antigo (aponta para a base de recursos).
"""

import os
import sys
import json
import pathlib
from dataclasses import asdict
from typing import Dict, List
from datetime import datetime

from models import Wallet, Trade, symbols_default, migrate_trade_dict

APP_NAME = "Tradeiros"
APP_PUBLISHER = "TradeirosApp"  # usado pelo appdirs


# ---------- paths de recursos (logo/ico) ----------
def resources_base_dir() -> pathlib.Path:
    """
    Base de RECURSOS (ficheiros empacotados: imagens, qss, etc.)
    - PyInstaller (--onefile/--onedir): sys._MEIPASS
    - Execução normal: pasta deste ficheiro
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return pathlib.Path(sys._MEIPASS)
    return pathlib.Path(__file__).resolve().parent


def get_asset_path(name: str) -> str:
    """
    Caminho absoluto para um recurso empacotado.
    Ex.: get_asset_path('tradeiros_logo.png')
    """
    return str(resources_base_dir() / name)


# ---------- COMPAT: BASE_DIR (algum código ainda pode usar isto) ----------
# Mantemos para não partir imports antigos: from storage import BASE_DIR
BASE_DIR = str(resources_base_dir())


# ---------- paths de dados (JSON) ----------
def _user_data_dir() -> pathlib.Path:
    """
    Tenta usar AppData/Local (Windows) ou equivalente via appdirs.
    Fallback: pasta do executável (./data).
    """
    # 1) tentar appdirs (recomendado)
    try:
        from appdirs import user_data_dir  # type: ignore
        p = pathlib.Path(user_data_dir(APP_NAME, APP_PUBLISHER))
        p.mkdir(parents=True, exist_ok=True)
        return p
    except Exception:
        pass

    # 2) Windows LOCALAPPDATA
    local = os.getenv("LOCALAPPDATA")
    if local:
        p = pathlib.Path(local) / APP_NAME
        try:
            p.mkdir(parents=True, exist_ok=True)
            return p
        except Exception:
            pass

    # 3) Fallback: ao lado do executável/código
    if getattr(sys, "frozen", False):
        base_dir = pathlib.Path(os.path.dirname(sys.executable))
    else:
        base_dir = pathlib.Path(__file__).resolve().parent
    p = base_dir / "data"
    p.mkdir(parents=True, exist_ok=True)
    return p


DATA_DIR = _user_data_dir()
WALLETS_FILE  = str(DATA_DIR / "wallets.json")
TRADES_FILE   = str(DATA_DIR / "trades.json")
SYMBOLS_FILE  = str(DATA_DIR / "symbols.json")
SETTINGS_FILE = str(DATA_DIR / "settings.json")


# ---------- IO ----------
def load_json(path: str, default):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default


def save_json(path: str, obj) -> None:
    """
    Escrita atómica: escreve para <path>.tmp e renomeia.
    """
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.flush()
        try:
            os.fsync(f.fileno())
        except Exception:
            pass
    try:
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass
        os.rename(tmp, path)


# ---------- DataStore ----------
class DataStore:
    def __init__(self):
        self.wallets: Dict[str, Wallet] = {}
        self.trades: Dict[str, Trade] = {}
        self.symbols: List[str] = []
        self.settings: Dict[str, str] = {}
        self.load_all()

    def load_all(self):
        # carteiras
        wl = load_json(WALLETS_FILE, [])
        self.wallets = {}
        for w in wl:
            try:
                self.wallets[w["id"]] = Wallet(**w)
            except Exception:
                pass

        # trades (migração tolerante)
        tl = load_json(TRADES_FILE, [])
        self.trades = {}
        for raw in tl:
            try:
                fixed = migrate_trade_dict(raw, self.wallets)
                t = Trade(**fixed)
                self.trades[t.id] = t
            except Exception:
                pass

        # símbolos
        sl = load_json(SYMBOLS_FILE, None)
        if not sl or not isinstance(sl, list):
            sl = symbols_default()
            save_json(SYMBOLS_FILE, sl)
        self.symbols = sorted(list({str(s).upper().strip() for s in sl if str(s).strip()}))

        # settings
        st = load_json(SETTINGS_FILE, {"theme": "dark"})
        self.settings = st if isinstance(st, dict) else {"theme": "dark"}

    # saves
    def save_wallets(self):
        save_json(WALLETS_FILE, [asdict(w) for w in self.wallets.values()])

    def save_trades(self):
        save_json(TRADES_FILE, [asdict(t) for t in self.trades.values()])

    def save_symbols(self):
        save_json(SYMBOLS_FILE, sorted(list({s.upper() for s in self.symbols})))

    def save_settings(self):
        save_json(SETTINGS_FILE, self.settings)

    # carteiras
    def add_wallet(self, name: str, init_bal: float, risk_pct: float) -> Wallet:
        import uuid
        w = Wallet(
            id=str(uuid.uuid4()),
            name=name.strip(),
            initial_balance=float(init_bal),
            risk_percent=float(risk_pct),
            created_at=datetime.now().isoformat(timespec='seconds')
        )
        self.wallets[w.id] = w
        self.save_wallets()
        return w

    def update_wallet(self, wallet: Wallet):
        self.wallets[wallet.id] = wallet
        self.save_wallets()

    def get_wallets(self) -> List[Wallet]:
        return list(self.wallets.values())

    # trades
    def add_trade(self, t: Trade):
        self.trades[t.id] = t
        self.save_trades()

    def update_trade(self, t: Trade):
        self.trades[t.id] = t
        self.save_trades()

    def delete_trade(self, trade_id: str):
        if trade_id in self.trades:
            del self.trades[trade_id]
            self.save_trades()

    def trades_for_wallet(self, wallet_id: str) -> List[Trade]:
        return [t for t in self.trades.values() if t.wallet_id == wallet_id]
