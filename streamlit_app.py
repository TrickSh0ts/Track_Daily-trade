# -*- coding: utf-8 -*-
# Tradeiros — Streamlit v12 (fix stay-on-tab + per-tab alerts + charts lado a lado)

import os, sys, io
from datetime import datetime
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

# ===== imports locais =====
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from storage import DataStore, WALLETS_FILE, TRADES_FILE, SYMBOLS_FILE, SETTINGS_FILE, save_json
from models import (
    Trade, new_trade_id, pnl_value, wallet_current_balance,
    equity_curve, symbols_default
)

# ===== helpers =====
def pretty_money(v: float) -> str:
    try:
        return f"{v:,.2f}".replace(",", " ").replace(".", ",")
    except Exception:
        return "0,00"

def base_asset(sym: str) -> str:
    if not sym:
        return ""
    s = sym.strip().upper()
    for suf in ["USDT","USDC","BUSD","USD","EUR","BRL","GBP","BTC","ETH"]:
        if s.endswith(suf) and len(s) > len(suf):
            return s[:-len(suf)]
    return s

def parse_number(txt: str) -> float:
    if txt is None:
        return 0.0
    t = str(txt).strip().replace(" ", "").replace("$","").replace("€","").replace(",", ".")
    if not t:
        return 0.0
    try:
        return float(t)
    except Exception:
        return 0.0

def refresh_datastore():
    cur = st.session_state.get("selected_wallet_id")
    st.session_state.ds = DataStore()
    st.session_state.selected_wallet_id = cur if cur in st.session_state.ds.wallets else (
        next(iter(st.session_state.ds.wallets.keys()), None)
    )

def compute_stats(trades, initial_balance: float):
    closed = [t for t in trades if (t.status or "Open") == "Closed"]
    winners = [t for t in closed if (t.pnl_abs or 0) > 0]
    losers  = [t for t in closed if (t.pnl_abs or 0) < 0]
    be      = [t for t in closed if (t.pnl_abs or 0) == 0]
    pnl_total = sum((t.pnl_abs or 0.0) for t in closed)
    total = len(trades)
    winrate = (len(winners)/len(closed)*100.0) if closed else 0.0
    current_balance = (initial_balance or 0.0) + pnl_total
    growth_pct = ((current_balance/initial_balance - 1)*100.0) if initial_balance and initial_balance>0 else 0.0
    return dict(
        total_trades=total, closed_trades=len(closed), open_trades=total-len(closed),
        winners=len(winners), losers=len(losers), breakeven=len(be),
        winrate_pct=winrate, pnl_total=pnl_total,
        initial_balance=initial_balance or 0.0, current_balance=current_balance,
        growth_pct=growth_pct
    )

# ===== app config / CSS =====
st.set_page_config(page_title="Tradeiros", page_icon="💹", layout="wide")
st.markdown("""
<style>
.block-container{padding-top:.6rem;padding-bottom:.25rem; max-width: 1400px;}
h1, h2, h3 {margin-bottom:.25rem;}
.stTabs [data-baseweb="tab-list"]{gap:.5rem}
.stTextInput>div>div>input{font-variant-numeric:tabular-nums}
div.row-widget.stRadio > div{gap: 1.0rem}

/* pílulas direção */
.long-pill{background:#2e7d32;color:#fff;padding:.24rem .5rem;border-radius:6px;font-weight:600;margin-left:.5rem}
.short-pill{background:#b71c1c;color:#fff;padding:.24rem .5rem;border-radius:6px;font-weight:600;margin-left:.35rem}
.gray-pill{background:#555;color:#ddd;padding:.24rem .5rem;border-radius:6px;font-weight:600;margin-left:.5rem}


/* botões coloridos largura total */
.tp-scope .stButton>button{background:#2e7d32 !important; color:#fff !important; font-weight:700;border:0;border-radius:10px;width:100%; padding:.7rem 1rem;}
.sl-scope .stButton>button{background:#b71c1c !important; color:#fff !important; font-weight:700;border:0;border-radius:10px;width:100%; padding:.7rem 1rem;}
.man-scope .stButton>button{background:#ff8c00 !important; color:#000 !important; font-weight:700;border:0;border-radius:10px;width:100%; padding:.7rem 1rem;}

/* alertas topo */
.alert-box{padding:.55rem .8rem;border-radius:8px;margin:.05rem 0 .4rem 0;}
.alert-success{background:#16351a;border:1px solid #2e7d32;color:#c9e7cf;}
.alert-info{background:#15293b;border:1px solid #1976d2;color:#d5e7fb;}
.alert-warn{background:#3b2a15;border:1px solid #ffb300;color:#ffe9b3;}

/* divisores curtos */
hr, [data-testid="stDivider"]{margin:.14rem 0;}

/* segurança: esconder inputs sem label (se algum ficar perdido) */
div[data-testid="stTextInput"] label:empty + div { display:none !important; }
div[data-testid="stTextInput"] label:empty { display:none !important; }
</style>
""", unsafe_allow_html=True)

from storage import get_asset_path

logo_path = get_asset_path("tradeiros_logo.png")
st.sidebar.image(logo_path, use_container_width=True)


# ===== estado =====
if "ds" not in st.session_state:
    st.session_state.ds = DataStore()
if "selected_wallet_id" not in st.session_state:
    ws = list(st.session_state.ds.wallets.values())
    st.session_state.selected_wallet_id = (ws[0].id if ws else None)

# paridade selecionada (key do selectbox)
if "sym_select" not in st.session_state:
    base_syms = st.session_state.ds.symbols or symbols_default()
    st.session_state.sym_select = (base_syms[0] if base_syms else "BTCUSDT")

# flags para gerir widgets do “Novo Trade”
st.session_state.setdefault("sym_to_focus", None)
st.session_state.setdefault("new_sym_text", "")
st.session_state.setdefault("clear_new_sym", False)

# === Alertas por aba ===
def set_alert(scope: str, a_type: str, msg: str):
    st.session_state[f"_alert_{scope}"] = {"type": a_type, "msg": msg}

def show_alert(scope: str):
    key = f"_alert_{scope}"
    alert = st.session_state.get(key)
    if not alert:
        return
    cls = "alert-success" if alert["type"]=="success" else ("alert-info" if alert["type"]=="info" else "alert-warn")
    st.markdown(f"<div class='alert-box {cls}'>{alert['msg']}</div>", unsafe_allow_html=True)
    st.session_state[key] = None  # limpa quando a aba renderiza

ds: DataStore = st.session_state.ds

# ===== sidebar carteiras =====
st.sidebar.subheader("Carteiras")
wallets = ds.get_wallets()
wallet_map = {w.name: w.id for w in wallets}

if wallets:
    names = list(wallet_map.keys())
    try:
        idx = names.index(next(n for n, wid in wallet_map.items() if wid == st.session_state.selected_wallet_id))
    except Exception:
        idx = 0
        st.session_state.selected_wallet_id = wallet_map[names[0]]
    chosen = st.sidebar.selectbox("Selecionar carteira", options=names, index=idx)
    st.session_state.selected_wallet_id = wallet_map[chosen]
else:
    st.sidebar.info("Ainda não tens carteiras.")

with st.sidebar.expander("➕ Nova Carteira", expanded=not wallets):
    with st.form("new_wallet", clear_on_submit=True):
        wname = st.text_input("Nome*", value="")
        winit = st.number_input("Saldo inicial*", min_value=0.0, value=10000.0, step=100.0, format="%.2f")
        wrisk = st.number_input("Risco referência (%)", min_value=0.0, max_value=100.0, value=1.0, step=0.25, format="%.2f")
        ok = st.form_submit_button("Guardar")
    if ok:
        if not wname.strip():
            st.warning("Indica um nome.")
        else:
            w = ds.add_wallet(wname.strip(), winit, wrisk)
            st.session_state.selected_wallet_id = w.id
            set_alert("new", "success", f"Carteira <b>{w.name}</b> criada com sucesso.")
            st.rerun()

if st.session_state.selected_wallet_id and st.session_state.selected_wallet_id in ds.wallets:
    curw = ds.wallets[st.session_state.selected_wallet_id]
    with st.sidebar.expander("✏️ Editar Carteira", expanded=False):
        with st.form("edit_wallet"):
            name_e = st.text_input("Nome", value=curw.name)
            init_e = st.number_input("Saldo inicial", min_value=0.0, step=100.0, value=float(curw.initial_balance), format="%.2f")
            risk_e = st.number_input("Risco (%)", min_value=0.0, max_value=100.0, step=0.25, value=float(curw.risk_percent), format="%.2f")
            ok_e = st.form_submit_button("Guardar")
        if ok_e:
            curw.name = name_e.strip() or curw.name
            curw.initial_balance = float(init_e)
            curw.risk_percent = float(risk_e)
            ds.update_wallet(curw)
            set_alert("new", "success", "Carteira atualizada.")
            refresh_datastore(); st.rerun()

if st.sidebar.button("🗑️ Apagar carteira", disabled=not wallets):
    wid = st.session_state.selected_wallet_id
    if wid and wid in ds.wallets:
        for t in list(ds.trades.values()):
            if t.wallet_id == wid:
                del ds.trades[t.id]
        ds.save_trades()
        del ds.wallets[wid]; ds.save_wallets()
        set_alert("new", "success", "Carteira apagada.")
        refresh_datastore(); st.rerun()

if st.session_state.selected_wallet_id and st.session_state.selected_wallet_id in ds.wallets:
    wsel = ds.wallets[st.session_state.selected_wallet_id]
    saldo_atual = wallet_current_balance(ds.trades_for_wallet(wsel.id), wsel.initial_balance)
    st.sidebar.markdown(f"**Saldo atual:** $ {pretty_money(saldo_atual)}")

# ===== título =====
st.title("Tradeiros — Diário de Trades")

# ===== tabs =====
tabs = st.tabs(["Novo Trade", "Atualização de Trade", "Histórico", "Estatísticas", "Gráficos", "Manutenção"])

# =============== TAB 0: NOVO TRADE ===============
with tabs[0]:
    show_alert("new")
    if not wallets:
        st.info("Cria uma carteira na barra lateral para começar.")
    else:
        w = ds.wallets[st.session_state.selected_wallet_id]

        # defaults + reset antes dos widgets
        for k, v in {
            "entry_txt":"90000,00","sl_txt":"90000,00","tp_txt":"90000,00",
            "qty_txt":"0,0000","val_txt":"0,00","dir_new":"Long",
            "last_changed":None
        }.items(): st.session_state.setdefault(k, v)
        if st.session_state.get("_reset_new"):
            st.session_state.update({
                "dir_new":"Long",
                "entry_txt":"90000,00","sl_txt":"90000,00","tp_txt":"90000,00",
                "qty_txt":"0,0000","val_txt":"0,00", "last_changed":None
            })
            st.session_state["_reset_new"] = False

        # flags ANTES dos widgets de paridade
        if st.session_state.sym_to_focus:
            st.session_state.sym_select = st.session_state.sym_to_focus
            st.session_state.sym_to_focus = None
        if st.session_state.clear_new_sym:
            st.session_state.new_sym_text = ""
            st.session_state.clear_new_sym = False

        # linha: paridade + adicionar paridade
        cL, cR = st.columns([3,2])
        with cL:
            base_symbols = ds.symbols or symbols_default()
            init_index = base_symbols.index(st.session_state.sym_select) if st.session_state.sym_select in base_symbols else 0
            symbol = st.selectbox("Paridade", options=base_symbols, index=init_index, key="sym_select")
        with cR:
            st.caption("Adicionar nova paridade")
            i1, i2 = st.columns([4,1])
            i1.text_input("ex.: SOLUSDT", key="new_sym_text", label_visibility="collapsed", placeholder="ex.: SOLUSDT")
            if i2.button("Adicionar à lista", use_container_width=True, key="add_sym_btn"):
                ns = (st.session_state.new_sym_text or "").strip().upper()
                if ns:
                    if ns not in ds.symbols:
                        ds.symbols.append(ns); ds.symbols = sorted(list(set(ds.symbols))); ds.save_symbols()
                        set_alert("new", "success", f"Paridade <b>{ns}</b> adicionada.")
                    else:
                        set_alert("new", "info", "Paridade já existe.")
                    st.session_state.sym_to_focus = ns
                    st.session_state.clear_new_sym = True
                    st.rerun()
                else:
                    st.warning("Indica uma paridade válida.")

        # Direção (radio + pílulas inline)
        rL, rR = st.columns([1.2, 1])
        with rL:
            dir_choice = st.radio("Direção", ["Long","Short"], horizontal=True, key="dir_new")
        with rR:
            pills = (
                f"<span class='{'long-pill' if dir_choice=='Long' else 'gray-pill'}'>Long</span>"
                f"<span class='{'short-pill' if dir_choice=='Short' else 'gray-pill'}'>Short</span>"
            )
            st.markdown("&nbsp;<br/>" + pills, unsafe_allow_html=True)

        # preços (lado a lado)
        cE, cSL, cTP = st.columns([1,1,1])
        def on_entry_change():
            entry = parse_number(st.session_state.entry_txt)
            if st.session_state.get("last_changed") == "qty":
                q = parse_number(st.session_state.qty_txt); st.session_state.val_txt = f"{q*entry:.2f}".replace(".", ",")
            elif st.session_state.get("last_changed") == "val":
                v = parse_number(st.session_state.val_txt);
                if entry>0: st.session_state.qty_txt = f"{v/entry:.4f}".replace(".", ",")
        def on_qty_change():
            st.session_state.last_changed = "qty"
            entry = parse_number(st.session_state.entry_txt); q = parse_number(st.session_state.qty_txt)
            st.session_state.val_txt = f"{q*entry:.2f}".replace(".", ",")
        def on_val_change():
            st.session_state.last_changed = "val"
            entry = parse_number(st.session_state.entry_txt); v = parse_number(st.session_state.val_txt)
            if entry>0: st.session_state.qty_txt = f"{v/entry:.4f}".replace(".", ",")

        entry_txt = cE.text_input("Preço de Entrada", value=st.session_state.entry_txt, key="entry_txt", on_change=on_entry_change)
        sl_txt    = cSL.text_input("Stop Loss",       value=st.session_state.sl_txt,    key="sl_txt")
        tp_txt    = cTP.text_input("Take Profit",     value=st.session_state.tp_txt,    key="tp_txt")
        entry = parse_number(entry_txt); sl = parse_number(sl_txt); tp = parse_number(tp_txt)

        # quantidade / valor (sync automático)
        asset = base_asset(symbol) or "UNIDADES"
        cQ, cV = st.columns([1,1])
        qty_txt = cQ.text_input(f"Quantidade ({asset})", value=st.session_state.qty_txt, key="qty_txt", on_change=on_qty_change)
        val_txt = cV.text_input("ou Valor ($)",        value=st.session_state.val_txt, key="val_txt", on_change=on_val_change)
        qty = parse_number(qty_txt)

        # métricas
        c1, c2, c3, c4 = st.columns([1,1,1,1])
        risk_per_unit   = max(entry - sl, 0.0) if dir_choice == "Long" else max(sl - entry, 0.0)
        reward_per_unit = max(tp - entry, 0.0) if dir_choice == "Long" else max(entry - tp, 0.0)
        rr = (reward_per_unit / risk_per_unit) if risk_per_unit > 0 else 0.0
        risk_amount = risk_per_unit * qty
        loss_abs = pnl_value(dir_choice, entry, sl, qty)
        gain_abs = pnl_value(dir_choice, entry, tp, qty)
        bal = wallet_current_balance(ds.trades_for_wallet(w.id), w.initial_balance)
        risk_pct = (risk_amount / bal * 100.0) if bal > 0 else 0.0
        risk_color = "#2e7d32" if risk_pct <= 1.0 else ("#ffcc00" if risk_pct <= 2.0 else "#b71c1c")
        c1.markdown(f"**Risco Retorno**<br><span style='font-size:20px'>{int(round(rr))} : 1</span>", unsafe_allow_html=True)
        c2.markdown(f"**Risco da Operação**<br><span style='color:{risk_color};font-size:20px'>{risk_pct:.2f}%</span>", unsafe_allow_html=True)
        c3.markdown(f"**Perda potencial (SL)**<br><span style='color:#b71c1c;font-size:20px'>$ {pretty_money(loss_abs)}</span>", unsafe_allow_html=True)
        c4.markdown(f"**Ganho potencial (TP)**<br><span style='color:#2e7d32;font-size:20px'>$ {pretty_money(gain_abs)}</span>", unsafe_allow_html=True)

        reason = st.text_area("Razão da Entrada", height=60)
        if st.button("Guardar Trade", type="primary", use_container_width=True):
            if not symbol or entry<=0 or sl<=0 or qty<=0 or not reason.strip():
                st.error("Paridade, entrada, SL, quantidade e razão da entrada são obrigatórios.")
            else:
                trade_id = new_trade_id(ds.trades)
                created_at = datetime.now().isoformat(timespec='seconds')
                t = Trade(
                    id=trade_id, wallet_id=w.id, symbol=symbol.strip().upper(),
                    direction=dir_choice, entry_price=round(entry,2), stop_loss=round(sl,2),
                    take_profit=round(tp,2), position_size=float(qty),
                    position_value=round(entry*float(qty),2), reason=reason.strip(),
                    created_at=created_at, risk_amount=risk_amount,
                    risk_pct_of_balance=(risk_pct if bal>0 else 0.0), status="Open",
                    exit_price=None, closed_at=None, pnl_abs=None, pnl_pct=None,
                    result=None, close_reason=None
                )
                ds.add_trade(t)
                st.session_state["_reset_new"] = True
                set_alert("new", "success", "Trade guardado.")
                refresh_datastore(); st.rerun()

# =============== TAB 1: ATUALIZAÇÃO DE TRADE ===============
with tabs[1]:
    show_alert("update")
    if not wallets:
        st.info("Cria uma carteira para continuar.")
    else:
        w = ds.wallets[st.session_state.selected_wallet_id]
        open_trades = [t for t in ds.trades.values() if t.wallet_id == w.id and t.status == "Open"]
        if not open_trades:
            st.info("Não há trades abertos nesta carteira.")
        else:
            open_trades.sort(key=lambda x: x.created_at)
            labels = [f"{t.created_at.replace('T',' ')} • {t.symbol} • {t.id}" for t in open_trades]
            idx = st.selectbox("Trade Aberto", options=range(len(open_trades)), format_func=lambda i: labels[i])
            t = open_trades[idx]

            st.markdown("<b>Direção:</b> " + ("<span style='color:#2e7d32'>Long</span>" if t.direction=="Long" else "<span style='color:#b71c1c'>Short</span>"), unsafe_allow_html=True)

            left, right = st.columns([1,1])

            # ====== BLOCO TRADE ORIGINAL ======
            with left:
                st.markdown("<div class='boxed'>", unsafe_allow_html=True)
                st.markdown("**Trade original (bloqueado)**")
                l1c1, l1c2, l1c3 = st.columns([1,1,1])
                l1c1.text_input("Preço de Entrada", value=f"{t.entry_price:.2f}".replace(".",","), key=f"orig_e_{t.id}", disabled=True)
                l1c2.text_input("Stop Loss",       value=f"{t.stop_loss:.2f}".replace(".",","),  key=f"orig_sl_{t.id}", disabled=True)
                l1c3.text_input("Take Profit",     value=f"{t.take_profit:.2f}".replace(".",","),key=f"orig_tp_{t.id}", disabled=True)
                l2c1, l2c2 = st.columns([1,1])
                l2c1.text_input("Quantidade", value=f"{t.position_size:.4f}".replace(".",","), key=f"orig_q_{t.id}", disabled=True)
                l2c2.text_input("Valor posição ($)", value=f"{t.entry_price*t.position_size:.2f}".replace(".",","), key=f"orig_v_{t.id}", disabled=True)
                st.markdown("</div>", unsafe_allow_html=True)

            # ====== Edição à direita ======
            with right:
                st.markdown("**Editar trade**")
                r1c1, r1c2, r1c3 = st.columns([1,1,1])
                new_entry = parse_number(r1c1.text_input("Preço de Entrada", value=f"{t.entry_price:.2f}".replace(".",","), key=f"e_{t.id}"))
                new_sl    = parse_number(r1c2.text_input("Stop Loss",       value=f"{t.stop_loss:.2f}".replace(".",","),  key=f"sl_{t.id}"))
                new_tp    = parse_number(r1c3.text_input("Take Profit",     value=f"{t.take_profit:.2f}".replace(".",","),key=f"tp_{t.id}"))

                r2c1, r2c2 = st.columns([1,1])
                new_qty   = parse_number(r2c1.text_input("Quantidade",      value=f"{t.position_size:.4f}".replace(".",","), key=f"q_{t.id}"))
                r2c2.caption(f"Valor posição: $ {pretty_money(new_entry * new_qty)}")

                r3c1, r3c2 = st.columns([1,1])
                r3c1.caption(f"<span style='color:#2e7d32'>Ganho em TP:</span> $ {pretty_money(pnl_value(t.direction, new_entry, new_tp, new_qty))}", unsafe_allow_html=True)
                r3c2.caption(f"<span style='color:#b71c1c'>Perda em SL:</span> $ {pretty_money(pnl_value(t.direction, new_entry, new_sl, new_qty))}", unsafe_allow_html=True)

                if st.button("Guardar alterações", key=f"upd_{t.id}", use_container_width=True):
                    t.entry_price = round(new_entry, 2)
                    t.stop_loss   = round(new_sl, 2)
                    t.take_profit = round(new_tp, 2)
                    t.position_size = float(new_qty)
                    t.position_value = round(t.entry_price * t.position_size, 2)
                    t.risk_amount = abs(t.entry_price - t.stop_loss) * t.position_size
                    bal_upd = wallet_current_balance(ds.trades_for_wallet(t.wallet_id), ds.wallets[t.wallet_id].initial_balance)
                    t.risk_pct_of_balance = (t.risk_amount / bal_upd * 100.0) if bal_upd > 0 else 0.0
                    ds.update_trade(t)
                    set_alert("update", "success", "Alterações guardadas.")

            # ====== Fechar trade ======
            st.subheader("Fechar trade", divider="gray")
            b1, b2, b3 = st.columns([1,1,2])

            with b1:
                st.markdown("<div class='tp-scope'>", unsafe_allow_html=True)
                if st.button("Fechar em TP", key=f"btn_tp_{t.id}", use_container_width=True):
                    t.exit_price = round(t.take_profit, 2)
                    t.closed_at = datetime.now().isoformat(timespec='seconds')
                    t.status = "Closed"; t.close_reason = "TP"
                    t.pnl_abs = pnl_value(t.direction, t.entry_price, t.exit_price, t.position_size)
                    balc = wallet_current_balance(ds.trades_for_wallet(t.wallet_id), ds.wallets[t.wallet_id].initial_balance)
                    t.pnl_pct = (t.pnl_abs / balc * 100.0) if balc > 0 else None
                    t.result = "Gain" if (t.pnl_abs or 0) > 0 else ("Loss" if (t.pnl_abs or 0) < 0 else "Break-even")
                    ds.update_trade(t)
                    set_alert("update", "success", f"Trade fechado em TP. PnL: $ {pretty_money(t.pnl_abs)}")
                st.markdown("</div>", unsafe_allow_html=True)
                st.caption(f"<span style='color:#2e7d32'>Ganho em TP:</span> $ {pretty_money(pnl_value(t.direction, t.entry_price, t.take_profit, t.position_size))}", unsafe_allow_html=True)

            with b2:
                st.markdown("<div class='sl-scope'>", unsafe_allow_html=True)
                if st.button("Fechar em SL", key=f"btn_sl_{t.id}", use_container_width=True):
                    t.exit_price = round(t.stop_loss, 2)
                    t.closed_at = datetime.now().isoformat(timespec='seconds')
                    t.status = "Closed"; t.close_reason = "SL"
                    t.pnl_abs = pnl_value(t.direction, t.entry_price, t.exit_price, t.position_size)
                    balc = wallet_current_balance(ds.trades_for_wallet(t.wallet_id), ds.wallets[t.wallet_id].initial_balance)
                    t.pnl_pct = (t.pnl_abs / balc * 100.0) if balc > 0 else None
                    t.result = "Gain" if (t.pnl_abs or 0) > 0 else ("Loss" if (t.pnl_abs or 0) < 0 else "Break-even")
                    ds.update_trade(t)
                    set_alert("update", "warn", f"Trade fechado em SL. PnL: $ {pretty_money(t.pnl_abs)}")
                st.markdown("</div>", unsafe_allow_html=True)
                st.caption(f"<span style='color:#b71c1c'>Perda em SL:</span> $ {pretty_money(pnl_value(t.direction, t.entry_price, t.stop_loss, t.position_size))}", unsafe_allow_html=True)

            with b3:
                st.markdown("<div class='man-scope'>", unsafe_allow_html=True)
                exit_txt = st.text_input("Preço do fechamento (manual)", value="0,00", key=f"m_{t.id}")
                if st.button("Fechar Manual", key=f"btn_man_{t.id}", use_container_width=True):
                    exit_price = parse_number(exit_txt)
                    if exit_price <= 0:
                        set_alert("update", "warn", "Indica um preço válido para fechar manualmente.")
                    else:
                        t.exit_price = round(exit_price, 2)
                        t.closed_at = datetime.now().isoformat(timespec='seconds')
                        t.status = "Closed"; t.close_reason = "Manual"
                        t.pnl_abs = pnl_value(t.direction, t.entry_price, t.exit_price, t.position_size)
                        balc = wallet_current_balance(ds.trades_for_wallet(t.wallet_id), ds.wallets[t.wallet_id].initial_balance)
                        t.pnl_pct = (t.pnl_abs / balc * 100.0) if balc > 0 else None
                        t.result = "Gain" if (t.pnl_abs or 0) > 0 else ("Loss" if (t.pnl_abs or 0) < 0 else "Break-even")
                        ds.update_trade(t)
                        set_alert("update", "info", f"Trade fechado manualmente. PnL: $ {pretty_money(t.pnl_abs)}")
                st.markdown("</div>", unsafe_allow_html=True)
                exit_price = parse_number(exit_txt)
                preview = pnl_value(t.direction, float(new_entry), exit_price, float(new_qty))
                st.caption(f"Pré-visualização PnL: $ {pretty_money(preview)}")

# =============== TAB 2: HISTÓRICO ===============
with tabs[2]:
    show_alert("history")
    wallets_all = list(ds.wallets.values())
    if not wallets_all:
        st.info("Sem carteiras.")
    else:
        opts = ["Todas"] + [w.name for w in wallets_all]
        opt = st.selectbox("Carteira", options=opts, index=0)
        if opt == "Todas":
            trades = list(ds.trades.values())
            wname_of = lambda tid: ds.wallets[ds.trades[tid].wallet_id].name if ds.trades[tid].wallet_id in ds.wallets else "—"
        else:
            wsel = next(w for w in wallets_all if w.name == opt)
            trades = [t for t in ds.trades.values() if t.wallet_id == wsel.id]
            wname_of = lambda tid: opt

        c1, c2, c3, c4 = st.columns(4)
        with c1: from_date = st.date_input("De", value=pd.to_datetime("2000-01-01")).strftime("%Y-%m-%d")
        with c2: to_date   = st.date_input("Até", value=pd.Timestamp.today()).strftime("%Y-%m-%d")
        with c3: symbol_f  = st.text_input("Paridade (filtro)", "")
        with c4: status_f  = st.selectbox("Estado", ["Todos","Open","Closed"])

        def in_range(iso):
            try:
                d = datetime.fromisoformat(iso)
                dmin = pd.to_datetime(from_date)
                dmax = pd.to_datetime(to_date) + pd.Timedelta(hours=23, minutes=59, seconds=59)
                return dmin <= d <= dmax
            except Exception:
                return True

        rows = []
        for t in trades:
            if symbol_f and symbol_f.upper() not in (t.symbol or "").upper(): continue
            if status_f != "Todos" and (t.status or "Open") != status_f: continue
            if not in_range(t.created_at or ""): continue
            rows.append(t)

        def as_dict(t: Trade):
            tofloat = lambda v: (float(v) if v is not None else None)
            return dict(ID=t.id, Data=(t.created_at or "").replace("T"," "),
                        Carteira=wname_of(t.id), Paridade=t.symbol, Direção=t.direction,
                        Entrada=tofloat(t.entry_price), SL=tofloat(t.stop_loss), TP=tofloat(t.take_profit),
                        Quantidade=tofloat(t.position_size), ValorPos=tofloat(t.position_value),
                        RiscoUSD=tofloat(t.risk_amount), RiscoPct=tofloat(t.risk_pct_of_balance),
                        Estado=t.status, Saída=tofloat(t.exit_price), PnL=tofloat(t.pnl_abs),
                        PnLPct=tofloat(t.pnl_pct), Resultado=t.result, FechadoComo=t.close_reason, Razão=t.reason)
        df = pd.DataFrame([as_dict(t) for t in rows])
        st.dataframe(df, use_container_width=True)

        to_delete = st.selectbox("Apagar trade (opcional)", options=["—"] + [t.id for t in rows])
        if to_delete != "—" and st.button("Apagar trade selecionado"):
            ds.delete_trade(to_delete)
            set_alert("history", "success", "Trade apagado.")
            refresh_datastore(); st.rerun()

        if st.button("Exportar Excel"):
            initial_total = sum((w.initial_balance or 0.0) for w in wallets_all)
            stats_global = compute_stats(list(ds.trades.values()), initial_total)
            stats_wallet = None
            if opt != "Todas":
                wsel = next(w for w in wallets_all if w.name == opt)
                stats_wallet = compute_stats([t for t in ds.trades.values() if t.wallet_id == wsel.id], wsel.initial_balance)

            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="Trades")
                if stats_wallet:
                    (pd.DataFrame([stats_wallet]).T.reset_index()
                     .rename(columns={"index":"Métrica", 0:"Valor"}).to_excel(writer, index=False, sheet_name=f"Estatísticas_{opt}"))
                (pd.DataFrame([stats_global]).T.reset_index()
                 .rename(columns={"index":"Métrica", 0:"Valor"}).to_excel(writer, index=False, sheet_name="Estatísticas_Global"))
            st.download_button("Descarregar Excel", data=buffer.getvalue(),
                               file_name="Tradeiros_Historico.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# =============== TAB 3: ESTATÍSTICAS ===============
with tabs[3]:
    show_alert("stats")
    wallets_all = list(ds.wallets.values())
    initial_total = sum((w.initial_balance or 0.0) for w in wallets_all) if wallets_all else 0.0
    s = compute_stats(list(ds.trades.values()), initial_total)
    cA, cB, cC = st.columns(3)
    cA.metric("Total de trades", s["total_trades"]); cA.metric("Fechados", s["closed_trades"]); cA.metric("Abertos", s["open_trades"])
    cB.metric("Vencedores", s["winners"]); cB.metric("Perdedores", s["losers"]); cB.metric("Break-even", s["breakeven"])
    cC.metric("Taxa de acerto", f"{s['winrate_pct']:.2f}%"); cC.metric("PnL total", f"$ {pretty_money(s['pnl_total'])}")
    st.write("---")
    c1, c2, c3 = st.columns(3)
    c1.metric("Saldo inicial (soma)", f"$ {pretty_money(s['initial_balance'])}")
    c2.metric("Saldo atual (soma)", f"$ {pretty_money(s['current_balance'])}")
    c3.metric("Crescimento (global)", f"{s['growth_pct']:.2f}%")

# =============== TAB 4: GRÁFICOS (lado a lado) ===============
with tabs[4]:
    show_alert("charts")
    if not wallets:
        st.info("Cria uma carteira para ver gráficos.")
    else:
        w = ds.wallets[st.session_state.selected_wallet_id]
        col1, col2 = st.columns(2)

        with col1:
            eq = equity_curve(ds.trades_for_wallet(w.id), w.initial_balance)
            fig1, ax1 = plt.subplots(figsize=(4.0, 2.0))
            if eq:
                xs = list(range(1, len(eq)+1)); ys = [p[1] for p in eq]; ax1.plot(xs, ys, marker="o")
            else:
                ax1.plot([0,1],[w.initial_balance, w.initial_balance])
            ax1.set_title("Evolução do Saldo"); ax1.set_xlabel("Trade fechado #"); ax1.set_ylabel("Saldo")
            st.pyplot(fig1, use_container_width=True)

        with col2:
            closed = [t for t in ds.trades_for_wallet(w.id) if t.status=="Closed" and t.pnl_abs is not None]
            closed.sort(key=lambda x: x.closed_at or x.created_at); pnls = [t.pnl_abs for t in closed]
            fig2, ax2 = plt.subplots(figsize=(4.0, 2.0))
            if pnls:
                xs = list(range(1, len(pnls)+1)); colors = ["#4caf50" if p>=0 else "#e53935" for p in pnls]
                ax2.bar(xs, pnls, align="center", color=colors)
            ax2.set_title("PnL por Trade (fechados)"); ax2.set_xlabel("Trade fechado #"); ax2.set_ylabel("PnL")
            st.pyplot(fig2, use_container_width=True)

# =============== TAB 5: MANUTENÇÃO ===============
with tabs[5]:
    show_alert("admin")
    st.warning("⚠️ Reset Total apaga carteiras, trades, paridades e definições.", icon="⚠️")
    if st.button("RESET TOTAL (apagar todos os dados)", type="secondary"):
        import os as _os
        for path in [WALLETS_FILE, TRADES_FILE, SYMBOLS_FILE, SETTINGS_FILE]:
            try:
                if _os.path.exists(path): _os.remove(path)
            except Exception:
                pass
        save_json(SYMBOLS_FILE, symbols_default()); save_json(SETTINGS_FILE, {"theme":"dark"})
        set_alert("admin", "success", "Dados apagados.")
        refresh_datastore(); st.rerun()
