# -*- coding: utf-8 -*-
from dataclasses import dataclass
from typing import Optional, List, Dict
from datetime import datetime
import random


@dataclass
class Wallet:
    id: str
    name: str
    initial_balance: float
    risk_percent: float
    created_at: str


@dataclass
class Trade:
    id: str
    wallet_id: str
    symbol: str
    direction: str  # "Long" | "Short"
    entry_price: float
    stop_loss: float
    take_profit: float
    position_size: float
    position_value: float
    reason: str
    created_at: str
    risk_amount: float
    risk_pct_of_balance: float
    status: str  # "Open" | "Closed"
    exit_price: Optional[float]
    closed_at: Optional[str]
    pnl_abs: Optional[float]
    pnl_pct: Optional[float]
    result: Optional[str]         # "Gain" | "Loss" | "Break-even"
    close_reason: Optional[str]   # "TP" | "SL" | "Manual"


# ---------- Funções utilitárias ----------

def symbols_default() -> List[str]:
    return ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"]


def pretty_money(v: float) -> str:
    try:
        return f"{v:,.2f}".replace(",", " ").replace(".", ",")
    except Exception:
        return "0,00"


def new_trade_id(trades: Dict[str, Trade]) -> str:
    while True:
        code = "".join(random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") for _ in range(6))
        if code not in trades:
            return code


def pnl_value(direction: str, entry: float, exit_price: float, size: float) -> float:
    """Calcula o PnL de forma segura."""
    try:
        if size <= 0 or entry <= 0 or exit_price <= 0:
            return 0.0
        return (exit_price - entry) * size if direction == "Long" else (entry - exit_price) * size
    except Exception:
        return 0.0


def wallet_current_balance(trades: List[Trade], initial_balance: float) -> float:
    """Saldo atual da carteira = inicial + soma dos PnL fechados."""
    bal = initial_balance
    for t in trades:
        if t.status == "Closed" and t.pnl_abs is not None:
            bal += t.pnl_abs
    return bal


def migrate_trade_dict(raw: dict, wallets: Dict[str, Wallet]) -> dict:
    """Garante compatibilidade com versões antigas dos ficheiros JSON."""
    out = dict(raw)
    out.setdefault("exit_price", None)
    out.setdefault("closed_at", None)
    out.setdefault("pnl_abs", None)
    out.setdefault("pnl_pct", None)
    out.setdefault("result", None)
    out.setdefault("close_reason", None)
    # assegurar consistência de wallet_id
    if out.get("wallet_id") not in wallets:
        if wallets:
            out["wallet_id"] = list(wallets.keys())[0]
    return out


def equity_curve(trades: List[Trade], initial_balance: float):
    """Devolve lista de pontos (datetime, saldo) só com trades fechados."""
    bal = initial_balance
    points = []
    closed = [t for t in trades if t.status == "Closed" and t.pnl_abs is not None]
    closed.sort(key=lambda x: x.closed_at or x.created_at)
    for t in closed:
        bal += t.pnl_abs
        points.append((datetime.fromisoformat(t.closed_at or t.created_at), bal))
    return points
