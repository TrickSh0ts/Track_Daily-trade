# -*- coding: utf-8 -*-
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QGridLayout, QLabel, QComboBox, QPushButton, QDoubleSpinBox,
    QHBoxLayout, QMessageBox, QLineEdit, QVBoxLayout, QFrame
)
from PyQt5.QtGui import QDoubleValidator
from PyQt5.QtCore import QSignalBlocker, Qt
from models import pnl_value, pretty_money, wallet_current_balance


def _to_float(le: QLineEdit) -> float:
    try:
        txt = le.text().strip().replace(",", ".")
        return float(txt) if txt else 0.0
    except Exception:
        return 0.0


def _set_lineedit(le: QLineEdit, val: float):
    with QSignalBlocker(le):
        le.setText(f"{float(val):.2f}")


def _base_asset(sym: str) -> str:
    """Extrai o ativo base do símbolo (BTCUSDT -> BTC)."""
    if not sym:
        return ""
    s = sym.strip().upper()
    suffixes = ["USDT", "USDC", "BUSD", "USD", "EUR", "BRL", "GBP", "BTC", "ETH"]
    for suf in suffixes:
        if s.endswith(suf) and len(s) > len(suf):
            return s[: -len(suf)]
    return s


class TabUpdate(QWidget):
    """
    Atualizar/Fechar trades abertos.
    - Coluna esquerda: snapshot (bloqueado).
    - Coluna direita: edição.
    - Bloco inferior: fecho (TP/SL/Manual).
    """
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.current_trade = None
        self._snapshot = None  # snapshot do “trade original”
        self.build()

    # ==================== UI ====================
    def build(self):
        self.setStyleSheet("""
            QLabel { font-size: 12pt; }
            QComboBox, QDoubleSpinBox, QLineEdit, QPushButton { font-size: 11pt; }
            QLabel.muted { color:#bbb; }
        """)
        root = QGridLayout(self)
        # 👉 reduzir margens/espacamentos para subir os blocos
        self.setContentsMargins(6, 4, 6, 6)
        root.setContentsMargins(8, 0, 8, 8)
        root.setVerticalSpacing(8)
        root.setHorizontalSpacing(10)
        root.setRowStretch(0, 0)  # linha do título/combo
        root.setRowStretch(1, 0)  # direção
        root.setRowStretch(2, 0)  # blocos de cima
        root.setRowStretch(3, 1)  # bloco inferior empurrado quando há espaço

        # Linha de seleção + direção
        self.cmb_trade = QComboBox()
        self.cmb_trade.currentIndexChanged.connect(self.load_selected_trade)
        self.lbl_direction = QLabel("")

        root.addWidget(QLabel("Trade Aberto:"), 0, 0)
        root.addWidget(self.cmb_trade, 0, 1, 1, 3)
        root.addWidget(self.lbl_direction, 1, 0, 1, 4)

        # ====== COLUNA ESQUERDA — Snapshot bloqueado ======
        left = QGridLayout()
        left.setContentsMargins(8, 8, 8, 8)
        left.setHorizontalSpacing(8)
        left.setVerticalSpacing(6)
        box_left = QFrame(); box_left.setLayout(left)
        box_left.setFrameShape(QFrame.StyledPanel)
        root.addWidget(box_left, 2, 0, 1, 2)

        self.ed_symbol_ro = QLineEdit(); self.ed_symbol_ro.setReadOnly(True)
        self.le_entry_ro = QLineEdit(); self.le_entry_ro.setReadOnly(True)
        self.le_sl_ro    = QLineEdit(); self.le_sl_ro.setReadOnly(True)
        self.le_tp_ro    = QLineEdit(); self.le_tp_ro.setReadOnly(True)
        self.sp_qty_ro   = QDoubleSpinBox(); self.sp_qty_ro.setDecimals(4); self.sp_qty_ro.setReadOnly(True); self.sp_qty_ro.setButtonSymbols(QDoubleSpinBox.NoButtons)
        self.lbl_pos_value_ro = QLabel("Valor posição: $ 0,00")
        self.lbl_qty_title_ro = QLabel("Quantidade:")

        r = 0
        left.addWidget(QLabel("<b>Trade original (bloqueado)</b>"), r, 0, 1, 2); r += 1
        left.addWidget(QLabel("Paridade:"), r, 0); left.addWidget(self.ed_symbol_ro, r, 1); r += 1
        left.addWidget(QLabel("Preço de Entrada:"), r, 0); left.addWidget(self.le_entry_ro, r, 1); r += 1
        left.addWidget(QLabel("Stop Loss:"), r, 0); left.addWidget(self.le_sl_ro, r, 1); r += 1
        left.addWidget(QLabel("Take Profit:"), r, 0); left.addWidget(self.le_tp_ro, r, 1); r += 1
        rowpos_left = QWidget(); hpL = QHBoxLayout(rowpos_left); hpL.setContentsMargins(0,0,0,0)
        hpL.addWidget(self.lbl_qty_title_ro); hpL.addWidget(self.sp_qty_ro); hpL.addSpacing(12); hpL.addWidget(self.lbl_pos_value_ro); hpL.addStretch()
        left.addWidget(rowpos_left, r, 0, 1, 2); r += 1

        # ====== COLUNA DIREITA — Edição ======
        right = QGridLayout()
        right.setContentsMargins(8, 8, 8, 8)
        right.setHorizontalSpacing(8)
        right.setVerticalSpacing(6)
        box_right = QFrame(); box_right.setLayout(right)
        box_right.setFrameShape(QFrame.StyledPanel)
        root.addWidget(box_right, 2, 2, 1, 2)

        v2 = QDoubleValidator(0.0, 1e12, 2)
        self.ed_symbol = QLineEdit(); self.ed_symbol.setReadOnly(True)
        self.le_entry = QLineEdit(); self.le_entry.setValidator(v2); self.le_entry.setFixedWidth(180)
        self.le_sl    = QLineEdit(); self.le_sl.setValidator(v2);     self.le_sl.setFixedWidth(180)
        self.le_tp    = QLineEdit(); self.le_tp.setValidator(v2);     self.le_tp.setFixedWidth(180)
        self.sp_pos   = QDoubleSpinBox(); self.sp_pos.setDecimals(4); self.sp_pos.setMaximum(1e12); self.sp_pos.setFixedWidth(200)
        self.sp_pos.setKeyboardTracking(False)
        self.lbl_pos_value = QLabel("Valor posição: $ 0,00")
        self.lbl_qty_title = QLabel("Quantidade:")

        r = 0
        right.addWidget(QLabel("<b>Editar trade</b>"), r, 0, 1, 2); r += 1
        right.addWidget(QLabel("Paridade:"), r, 0); right.addWidget(self.ed_symbol, r, 1); r += 1
        right.addWidget(QLabel("Preço de Entrada:"), r, 0); right.addWidget(self.le_entry, r, 1); r += 1
        right.addWidget(QLabel("Stop Loss:"), r, 0); right.addWidget(self.le_sl, r, 1); r += 1
        right.addWidget(QLabel("Take Profit:"), r, 0); right.addWidget(self.le_tp, r, 1); r += 1

        rowpos = QWidget(); hp = QHBoxLayout(rowpos); hp.setContentsMargins(0,0,0,0)
        hp.addWidget(self.lbl_qty_title); hp.addWidget(self.sp_pos); hp.addSpacing(12); hp.addWidget(self.lbl_pos_value); hp.addStretch()
        right.addWidget(rowpos, r, 0, 1, 2); r += 1

        # ====== BLOCO INFERIOR — Fechar trade ======
        bottom = QGridLayout()
        bottom.setContentsMargins(8, 8, 8, 8)
        bottom.setHorizontalSpacing(8)
        bottom.setVerticalSpacing(6)
        box_bottom = QFrame(); box_bottom.setLayout(bottom)
        box_bottom.setFrameShape(QFrame.StyledPanel)
        root.addWidget(box_bottom, 3, 0, 1, 4)

        # Botões fechar
        self.btn_close_tp = QPushButton("Fechar em TP")
        self.btn_close_tp.setStyleSheet("background-color:#2e7d32; color:white; font-weight:600;")
        self.btn_close_sl = QPushButton("Fechar em SL")
        self.btn_close_sl.setStyleSheet("background-color:#b71c1c; color:white; font-weight:600;")
        for b in (self.btn_close_tp, self.btn_close_sl): b.setMinimumHeight(34)

        self.lbl_tp_val = QLabel("Ganho em TP: $ 0,00"); self.lbl_tp_val.setStyleSheet("color:#2e7d32;")
        self.lbl_sl_val = QLabel("Perda em SL: $ 0,00"); self.lbl_sl_val.setStyleSheet("color:#b71c1c;")

        row_btns = QWidget(); hb = QHBoxLayout(row_btns); hb.setContentsMargins(0,0,0,0)
        hb.addWidget(self.btn_close_tp); hb.addWidget(self.btn_close_sl); hb.addStretch()
        row_vals = QWidget(); hv = QHBoxLayout(row_vals); hv.setContentsMargins(0,0,0,0)
        hv.addWidget(self.lbl_tp_val); hv.addSpacing(24); hv.addWidget(self.lbl_sl_val); hv.addStretch()

        bottom.addWidget(QLabel("<b>Fechar trade</b>"), 0, 0, 1, 2)
        bottom.addWidget(row_btns, 1, 0, 1, 2)
        bottom.addWidget(row_vals, 2, 0, 1, 2)

        # Fecho manual (com PnL ao lado)
        manual_row = QWidget(); mh = QHBoxLayout(manual_row); mh.setContentsMargins(0,0,0,0)
        self.btn_close_manual = QPushButton("Fechar Manual"); self.btn_close_manual.setMinimumHeight(34)
        self.btn_close_manual.setStyleSheet("background-color:#ff8c00; color:black; font-weight:600;")
        self.sp_exit_manual = QDoubleSpinBox(); self.sp_exit_manual.setDecimals(2); self.sp_exit_manual.setMaximum(1e12); self.sp_exit_manual.setFixedWidth(180)
        self.sp_exit_manual.setKeyboardTracking(False)
        self.lbl_manual_pnl = QLabel("—"); self.lbl_manual_pnl.setStyleSheet("color:#bbb;")
        mh.addWidget(self.btn_close_manual); mh.addWidget(QLabel("Preço do fechamento:")); mh.addWidget(self.sp_exit_manual)
        mh.addSpacing(12); mh.addWidget(self.lbl_manual_pnl); mh.addStretch()
        bottom.addWidget(manual_row, 3, 0, 1, 2)

        # ====== Sinais ======
        # Persistir em editingFinished:
        for w in (self.le_entry, self.le_sl, self.le_tp):
            w.editingFinished.connect(self.on_any_finished)
        self.sp_pos.editingFinished.connect(self.on_any_finished)

        # Pré-visualização instantânea (não persiste):
        self.le_entry.textChanged.connect(self._update_preview_only)
        self.le_sl.textChanged.connect(self._update_preview_only)
        self.le_tp.textChanged.connect(self._update_preview_only)
        self.sp_pos.valueChanged.connect(self._update_preview_only)

        self.btn_close_tp.clicked.connect(self.close_by_tp)
        self.btn_close_sl.clicked.connect(self.close_by_sl)
        self.btn_close_manual.clicked.connect(self.close_by_manual)
        self.sp_exit_manual.valueChanged.connect(self._update_manual_pnl_preview)

        # Povoar combo
        self.populate_update_trade_combo()

    # ==================== Dados ====================
    def populate_update_trade_combo(self):
        current = self.cmb_trade.currentData()
        self.cmb_trade.blockSignals(True)
        self.cmb_trade.clear()
        open_trades = [t for t in self.app.ds.trades.values() if t.status == "Open"]
        open_trades.sort(key=lambda x: x.created_at)  # mais antigo primeiro
        self._open_cache = open_trades[:]
        for t in open_trades:
            self.cmb_trade.addItem(f"{t.created_at.replace('T',' ')} • {t.symbol} • {t.id}", userData=t.id)
        self.cmb_trade.blockSignals(False)
        if current:
            i = self.cmb_trade.findData(current)
            if i >= 0: self.cmb_trade.setCurrentIndex(i)
        if self.cmb_trade.currentIndex() < 0 and self.cmb_trade.count() > 0:
            self.cmb_trade.setCurrentIndex(0)
        self.load_selected_trade()

    def load_selected_trade(self):
        tid = self.cmb_trade.currentData()
        self.current_trade = self.app.ds.trades.get(tid) if tid else None
        t = self.current_trade

        # limpar preview manual
        self.sp_exit_manual.setValue(0.0)
        self.lbl_manual_pnl.setText("—"); self.lbl_manual_pnl.setStyleSheet("color:#bbb;")

        if not t:
            self.lbl_direction.setText("")
            for w in (self.le_entry, self.le_sl, self.le_tp): _set_lineedit(w, 0.0)
            with QSignalBlocker(self.sp_pos): self.sp_pos.setValue(0.0)
            self.ed_symbol.setText("")
            # lado esquerdo
            self.ed_symbol_ro.setText(""); _set_lineedit(self.le_entry_ro, 0.0); _set_lineedit(self.le_sl_ro, 0.0); _set_lineedit(self.le_tp_ro, 0.0)
            with QSignalBlocker(self.sp_qty_ro): self.sp_qty_ro.setValue(0.0)
            self.lbl_pos_value_ro.setText("Valor posição: $ 0,00"); self.lbl_qty_title_ro.setText("Quantidade:")
            self.lbl_tp_val.setText("Ganho em TP: $ 0,00"); self.lbl_sl_val.setText("Perda em SL: $ 0,00"); self.lbl_pos_value.setText("Valor posição: $ 0,00")
            return

        # snapshot “original” (lado esquerdo)
        self._snapshot = {
            "symbol": t.symbol,
            "entry": t.entry_price,
            "sl": t.stop_loss,
            "tp": t.take_profit,
            "qty": t.position_size,
        }
        asset = _base_asset(t.symbol)
        self.ed_symbol_ro.setText(t.symbol)
        _set_lineedit(self.le_entry_ro, t.entry_price)
        _set_lineedit(self.le_sl_ro, t.stop_loss)
        _set_lineedit(self.le_tp_ro, t.take_profit)
        with QSignalBlocker(self.sp_qty_ro): self.sp_qty_ro.setValue(t.position_size)
        self.lbl_qty_title_ro.setText(f"Quantidade ({asset}):")
        self.lbl_pos_value_ro.setText(f"Valor posição: $ {pretty_money(t.entry_price * t.position_size)}")

        # lado direito (editável)
        self.ed_symbol.setText(t.symbol)
        _set_lineedit(self.le_entry, t.entry_price)
        _set_lineedit(self.le_sl, t.stop_loss)
        _set_lineedit(self.le_tp, t.take_profit)
        with QSignalBlocker(self.sp_pos): self.sp_pos.setValue(t.position_size)
        self.lbl_qty_title.setText(f"Quantidade ({asset}):")

        self.update_direction_label()
        self._update_preview_only()

    def update_direction_label(self):
        if not self.current_trade: self.lbl_direction.setText(""); return
        if self.current_trade.direction == "Long":
            self.lbl_direction.setText("<b>Direção:</b> <span style='color:#2e7d32;'>Long</span>")
        else:
            self.lbl_direction.setText("<b>Direção:</b> <span style='color:#b71c1c;'>Short</span>")

    # ==================== Preview / Cálculos visuais ====================
    def _update_preview_only(self):
        """Atualiza valor posição e PnL de TP/SL em tempo real (sem persistir)."""
        t = self.current_trade
        if not t:
            self.lbl_pos_value.setText("Valor posição: $ 0,00")
            self.lbl_tp_val.setText("Ganho em TP: $ 0,00")
            self.lbl_sl_val.setText("Perda em SL: $ 0,00")
            return
        entry = _to_float(self.le_entry); size = float(self.sp_pos.value())
        tp = _to_float(self.le_tp); sl = _to_float(self.le_sl); direction = t.direction

        self.lbl_pos_value.setText(f"Valor posição: $ {pretty_money(entry * size)}")
        pnl_tp = pnl_value(direction, entry, tp, size)
        pnl_sl = pnl_value(direction, entry, sl, size)
        self.lbl_tp_val.setText(f"Ganho em TP: $ {pretty_money(pnl_tp)}")
        self.lbl_sl_val.setText(f"Perda em SL: $ {pretty_money(pnl_sl)}")
        self.lbl_tp_val.setStyleSheet("color:#2e7d32;")
        self.lbl_sl_val.setStyleSheet("color:#b71c1c;")
        self._update_manual_pnl_preview()

    # ==================== Persistência (após edição) ====================
    def on_any_finished(self):
        """Persiste alterações e atualiza tudo."""
        t = self.current_trade
        if not t:
            self._update_preview_only(); return

        t.entry_price = round(_to_float(self.le_entry), 2)
        t.stop_loss   = round(_to_float(self.le_sl), 2)
        t.take_profit = round(_to_float(self.le_tp), 2)
        t.position_size = float(self.sp_pos.value())
        t.position_value = round(t.entry_price * t.position_size, 2)
        t.risk_amount = abs(t.entry_price - t.stop_loss) * t.position_size

        w = self.app.current_wallet()
        bal = wallet_current_balance(self.app.ds.trades_for_wallet(w.id), w.initial_balance) if w else 0.0
        t.risk_pct_of_balance = (t.risk_amount / bal * 100.0) if bal > 0 else 0.0

        self.app.ds.update_trade(t)
        self._update_preview_only()
        self.app.refresh_all()

    # ---------- preview PnL manual conforme preço digitado ----------
    def _update_manual_pnl_preview(self):
        t = self.current_trade
        if not t:
            self.lbl_manual_pnl.setText("—"); self.lbl_manual_pnl.setStyleSheet("color:#bbb;"); return
        exit_price = float(self.sp_exit_manual.value())
        if exit_price <= 0:
            self.lbl_manual_pnl.setText("—"); self.lbl_manual_pnl.setStyleSheet("color:#bbb;"); return
        entry = _to_float(self.le_entry); size = float(self.sp_pos.value())
        pnl = pnl_value(t.direction, entry, exit_price, size)
        txt = f"$ {pretty_money(pnl)}"
        if pnl > 0:
            self.lbl_manual_pnl.setStyleSheet("color:#2e7d32;")
        elif pnl < 0:
            self.lbl_manual_pnl.setStyleSheet("color:#b71c1c;")
        else:
            self.lbl_manual_pnl.setStyleSheet("color:#bbb;")
        self.lbl_manual_pnl.setText(txt)

    # ==================== Ações de fecho ====================
    def _close_with_price(self, price: float, reason: str):
        t = self.current_trade
        if not t: return
        t.exit_price = round(price, 2)
        t.closed_at = datetime.now().isoformat(timespec='seconds')
        t.status = "Closed"; t.close_reason = reason
        t.pnl_abs = pnl_value(t.direction, t.entry_price, t.exit_price, t.position_size)

        w = self.app.current_wallet()
        bal = wallet_current_balance(self.app.ds.trades_for_wallet(w.id), w.initial_balance) if w else 0.0
        t.pnl_pct = (t.pnl_abs / bal * 100.0) if bal > 0 else None
        t.result = "Gain" if (t.pnl_abs or 0) > 0 else ("Loss" if (t.pnl_abs or 0) < 0 else "Break-even")

        self.app.ds.update_trade(t)
        self.app.refresh_all()
        self.populate_update_trade_combo()

        msg = f"PnL: $ {pretty_money(t.pnl_abs)}"
        if t.pnl_pct is not None:
            msg += f" ({t.pnl_pct:.2f}% do saldo)"
        QMessageBox.information(self, "Trade fechado", msg)

    def close_by_tp(self):
        t = self.current_trade
        if not t or t.take_profit <= 0:
            QMessageBox.warning(self, "TP inválido", "Define um TP válido."); return
        self._close_with_price(t.take_profit, "TP")

    def close_by_sl(self):
        t = self.current_trade
        if not t or t.stop_loss <= 0:
            QMessageBox.warning(self, "SL inválido", "Define um SL válido."); return
        self._close_with_price(t.stop_loss, "SL")

    def close_by_manual(self):
        t = self.current_trade
        if not t: return
        price = float(self.sp_exit_manual.value())
        if price <= 0:
            QMessageBox.warning(self, "Preço inválido", "Indica um preço válido."); return
        self._close_with_price(price, "Manual")
