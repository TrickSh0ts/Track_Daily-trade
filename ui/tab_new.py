# -*- coding: utf-8 -*-
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QGridLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QDoubleSpinBox, QTextEdit, QMessageBox, QButtonGroup
)
from PyQt5.QtCore import Qt

from models import new_trade_id, pnl_value, pretty_money, wallet_current_balance, Trade


def _base_asset(sym: str) -> str:
    """Extrai ativo base do símbolo (BTCUSDT -> BTC). Fallback: símbolo todo."""
    if not sym:
        return ""
    s = sym.strip().upper()
    suffixes = ["USDT", "USDC", "BUSD", "USD", "EUR", "BRL", "GBP", "BTC", "ETH"]
    for suf in suffixes:
        if s.endswith(suf) and len(s) > len(suf):
            return s[: -len(suf)]
    return s


class TabNew(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self._syncing_pos = False
        self.build()

    def build(self):
        self.setStyleSheet("""
            QLabel { font-size: 12pt; }
            QComboBox, QDoubleSpinBox, QTextEdit, QPushButton { font-size: 11pt; }
        """)
        g = QGridLayout(self)

        # Paridades
        prio = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"]
        pool = [s.upper() for s in self.app.ds.symbols]
        head = [s for s in prio if s in pool]; tail = sorted([s for s in pool if s not in head])
        ordered_symbols = head + tail

        self.cmb_symbol = QComboBox(); self.cmb_symbol.setEditable(True)
        self.cmb_symbol.addItems(ordered_symbols)
        self.cmb_symbol.setInsertPolicy(QComboBox.NoInsert)
        self.cmb_symbol.setMinimumWidth(360)
        # BTCUSDT predefinida
        idx = self.cmb_symbol.findText("BTCUSDT")
        if idx >= 0: self.cmb_symbol.setCurrentIndex(idx)

        self.btn_add_symbol = QPushButton("Adicionar à lista")
        self.btn_manage_symbols = QPushButton("Gerir Paridades")

        # Direção
        self.btn_long = QPushButton("Long")
        self.btn_short = QPushButton("Short")
        for b in (self.btn_long, self.btn_short):
            b.setCheckable(True); b.setMinimumHeight(28); b.setMinimumWidth(120); b.setStyleSheet("font-weight:600;")
        self.btn_long.setChecked(True)
        self.dir_group = QButtonGroup(self); self.dir_group.setExclusive(True)
        self.dir_group.addButton(self.btn_long); self.dir_group.addButton(self.btn_short)
        self.btn_long.toggled.connect(self.update_dir_styles)
        self.btn_short.toggled.connect(self.update_dir_styles)
        self.btn_long.toggled.connect(self.update_risk_labels)
        self.btn_short.toggled.connect(self.update_risk_labels)
        self.update_dir_styles()
        wrap_dir = QWidget(); hdir = QHBoxLayout(wrap_dir); hdir.addWidget(self.btn_long); hdir.addWidget(self.btn_short)

        # Preços
        self.sp_entry = QDoubleSpinBox(); self.sp_entry.setDecimals(2); self.sp_entry.setMaximum(1e12); self.sp_entry.setValue(90000.00); self.sp_entry.setFixedWidth(180)
        self.sp_sl    = QDoubleSpinBox(); self.sp_sl.setDecimals(2);    self.sp_sl.setMaximum(1e12);    self.sp_sl.setValue(90000.00);    self.sp_sl.setFixedWidth(180)
        self.sp_tp    = QDoubleSpinBox(); self.sp_tp.setDecimals(2);    self.sp_tp.setMaximum(1e12);    self.sp_tp.setValue(90000.00);    self.sp_tp.setFixedWidth(180)

        # Quantidade / Valor
        self.lbl_qty_title = QLabel("")  # será "Quantidade (BTC):"
        self._update_qty_title()  # inicial

        self.sp_pos_units = QDoubleSpinBox(); self.sp_pos_units.setDecimals(4); self.sp_pos_units.setSingleStep(0.0001); self.sp_pos_units.setMaximum(1e12); self.sp_pos_units.setFixedWidth(200)
        self.sp_pos_value = QDoubleSpinBox(); self.sp_pos_value.setDecimals(2); self.sp_pos_value.setMaximum(1e12); self.sp_pos_value.setPrefix("$ "); self.sp_pos_value.setFixedWidth(220)

        def on_units_changed(_=None):
            if self._syncing_pos: return
            self._syncing_pos = True
            self.sp_pos_value.setValue(float(self.sp_entry.value()) * float(self.sp_pos_units.value()))
            self._syncing_pos = False
            self.update_risk_labels()

        def on_value_changed(_=None):
            if self._syncing_pos: return
            self._syncing_pos = True
            entry = float(self.sp_entry.value()) or 1.0
            self.sp_pos_units.setValue(float(self.sp_pos_value.value()) / entry)
            self._syncing_pos = False
            self.update_risk_labels()

        self.sp_entry.valueChanged.connect(on_units_changed)
        self.sp_pos_units.valueChanged.connect(on_units_changed)
        self.sp_pos_value.valueChanged.connect(on_value_changed)
        self.sp_sl.valueChanged.connect(self.update_risk_labels)
        self.sp_tp.valueChanged.connect(self.update_risk_labels)
        self.cmb_symbol.currentTextChanged.connect(lambda _: self._update_qty_title())

        # Razão
        self.ed_reason = QTextEdit(); self.ed_reason.setFixedHeight(70); self.ed_reason.setPlaceholderText("Razão da entrada...")

        # Guardar
        self.btn_save_trade = QPushButton("Guardar Trade")
        self.btn_add_symbol.clicked.connect(self.add_symbol_to_list)
        self.btn_manage_symbols.clicked.connect(self.app.manage_symbols_dialog)
        self.btn_save_trade.clicked.connect(self.on_add_trade)

        # Layout
        r = 0
        g.addWidget(QLabel("Paridade:"), r, 0)
        wrap_sym = QWidget(); hs = QHBoxLayout(wrap_sym); hs.addWidget(self.cmb_symbol, 1); hs.addWidget(self.btn_add_symbol); hs.addWidget(self.btn_manage_symbols)
        g.addWidget(wrap_sym, r, 1); r += 1
        g.addWidget(QLabel("Direção:"), r, 0); g.addWidget(wrap_dir, r, 1); r += 1
        g.addWidget(QLabel("Preço de Entrada:"), r, 0); g.addWidget(self.sp_entry, r, 1); r += 1
        g.addWidget(QLabel("Stop Loss:"), r, 0); g.addWidget(self.sp_sl, r, 1); r += 1
        g.addWidget(QLabel("Take Profit:"), r, 0); g.addWidget(self.sp_tp, r, 1); r += 1

        rowpos = QWidget(); hp = QHBoxLayout(rowpos)
        hp.addWidget(self.lbl_qty_title); hp.addWidget(self.sp_pos_units)
        hp.addSpacing(12); hp.addWidget(QLabel("ou Valor ($):")); hp.addWidget(self.sp_pos_value); hp.addStretch()
        g.addWidget(rowpos, r, 0, 1, 2); r += 1

        self.lbl_rr = QLabel("Risco Retorno — 0 : 1")
        self.lbl_risk_pct = QLabel("Risco da Operação: 0.00%")
        row_rr = QWidget(); hrr = QHBoxLayout(row_rr); hrr.addWidget(self.lbl_rr); hrr.addSpacing(24); hrr.addWidget(self.lbl_risk_pct); hrr.addStretch()
        g.addWidget(row_rr, r, 0, 1, 2); r += 1

        self.lbl_loss_dollar = QLabel("Perda potencial (SL): $ 0,00")
        self.lbl_gain_dollar = QLabel("Ganho potencial (TP): $ 0,00")
        row_val = QWidget(); hv = QHBoxLayout(row_val); hv.addWidget(self.lbl_loss_dollar); hv.addSpacing(24); hv.addWidget(self.lbl_gain_dollar); hv.addStretch()
        g.addWidget(row_val, r, 0, 1, 2); r += 1

        g.addWidget(QLabel("Razão da Entrada:"), r, 0); g.addWidget(self.ed_reason, r, 1); r += 1
        g.addWidget(self.btn_save_trade, r, 0, 1, 2)

        on_units_changed()

    # ---------- helpers ----------
    def _update_qty_title(self):
        asset = _base_asset(self.cmb_symbol.currentText())
        if not asset:
            asset = "UNIDADES"
        self.lbl_qty_title.setText(f"Quantidade ({asset}):")

    def update_dir_styles(self):
        if self.btn_long.isChecked():
            self.btn_long.setStyleSheet("font-weight:600; background-color:#2e7d32; color:white;")
            self.btn_short.setStyleSheet("font-weight:600; background-color:#555; color:#ddd;")
        elif self.btn_short.isChecked():
            self.btn_short.setStyleSheet("font-weight:600; background-color:#b71c1c; color:white;")
            self.btn_long.setStyleSheet("font-weight:600; background-color:#555; color:#ddd;")
        else:
            self.btn_long.setStyleSheet("font-weight:600; background-color:#555; color:#ddd;")
            self.btn_short.setStyleSheet("font-weight:600; background-color:#555; color:#ddd;")

    def _direction_text(self) -> str:
        return "Long" if self.btn_long.isChecked() else "Short"

    def update_risk_labels(self):
        w = self.app.current_wallet()
        entry = float(self.sp_entry.value()); sl = float(self.sp_sl.value()); tp = float(self.sp_tp.value())
        size = float(self.sp_pos_units.value()); direction = self._direction_text()

        # reset cores default
        self.lbl_risk_pct.setStyleSheet("")
        self.lbl_loss_dollar.setStyleSheet("")
        self.lbl_gain_dollar.setStyleSheet("")

        if entry <= 0 or sl <= 0 or tp <= 0 or size <= 0:
            self.lbl_rr.setText("Risco Retorno — 0 : 1")
            self.lbl_risk_pct.setText("Risco da Operação: 0.00%")
            self.lbl_loss_dollar.setText("Perda potencial (SL): $ 0,00")
            self.lbl_gain_dollar.setText("Ganho potencial (TP): $ 0,00")
            return

        loss_abs = pnl_value(direction, entry, sl, size)
        gain_abs = pnl_value(direction, entry, tp, size)

        if direction == "Long":
            risk_per_unit = max(entry - sl, 0.0)
            reward_per_unit = max(tp - entry, 0.0)
        else:
            risk_per_unit = max(sl - entry, 0.0)
            reward_per_unit = max(entry - tp, 0.0)

        rr = (reward_per_unit / risk_per_unit) if risk_per_unit > 0 else 0.0
        # 👉 inteiro: "N : 1"
        self.lbl_rr.setText(f"Risco Retorno — {int(round(rr))} : 1")

        bal = wallet_current_balance(self.app.ds.trades_for_wallet(w.id), w.initial_balance) if w else 0.0
        risk_amount = risk_per_unit * size
        risk_pct = (risk_amount / bal * 100.0) if bal > 0 else 0.0

        # cor por patamar (novo: >3% também vermelho)
        if risk_pct <= 1.0:
            color = "#2e7d32"   # verde
        elif risk_pct <= 2.0:
            color = "#ffcc00"   # amarelo
        else:
            color = "#b71c1c"   # vermelho para >2% (inclui >3%)
        self.lbl_risk_pct.setStyleSheet(f"color: {color};")
        self.lbl_risk_pct.setText(f"Risco da Operação: {risk_pct:.2f}%")

        # cores fixas para perda/ganho
        self.lbl_loss_dollar.setStyleSheet("color: #b71c1c;")
        self.lbl_gain_dollar.setStyleSheet("color: #2e7d32;")
        self.lbl_loss_dollar.setText(f"Perda potencial (SL): $ {pretty_money(loss_abs)}")
        self.lbl_gain_dollar.setText(f"Ganho potencial (TP): $ {pretty_money(gain_abs)}")

    def add_symbol_to_list(self):
        sym = self.cmb_symbol.currentText().strip().upper()
        if not sym:
            QMessageBox.warning(self, "Paridade", "Indica uma paridade."); return
        if sym not in self.app.ds.symbols:
            self.app.ds.symbols.append(sym)
            self.app.ds.symbols = sorted(list(set(self.app.ds.symbols)))
            self.app.ds.save_symbols()
            prio = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"]
            pool = [s.upper() for s in self.app.ds.symbols]
            head = [s for s in prio if s in pool]; tail = sorted([s for s in pool if s not in head])
            ordered = head + tail
            self.cmb_symbol.clear(); self.cmb_symbol.addItems(ordered); self.cmb_symbol.setEditText(sym)
        self._update_qty_title()

    def on_add_trade(self):
        w = self.app.current_wallet()
        if not w:
            QMessageBox.warning(self, "Carteira", "Cria/seleciona uma carteira."); return

        symbol = self.cmb_symbol.currentText().strip().upper()
        entry = float(self.sp_entry.value()); sl = float(self.sp_sl.value()); tp = float(self.sp_tp.value())
        size = float(self.sp_pos_units.value())
        reason = self.ed_reason.toPlainText().strip()

        if not symbol or entry<=0 or sl<=0 or size<=0:
            QMessageBox.warning(self, "Validação", "Paridade, entrada, SL e posição devem ser válidos."); return
        if not reason:
            QMessageBox.warning(self, "Validação", "É obrigatório indicar a razão da entrada."); return

        direction = "Long" if self.btn_long.isChecked() else "Short"
        pos_value = round(entry * size, 2)
        created_at = datetime.now().isoformat(timespec='seconds')

        balance_at_open = wallet_current_balance(self.app.ds.trades_for_wallet(w.id), w.initial_balance)
        risk_amount = abs(entry - sl) * size
        risk_pct_bal = (risk_amount / balance_at_open * 100.0) if balance_at_open > 0 else 0.0

        if risk_pct_bal > 3.0:
            if QMessageBox.warning(self, "Atenção — Risco Elevado",
                                   f"Risco: {risk_pct_bal:.2f}% do saldo.\nContinuar?",
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
                return

        trade_id = new_trade_id(self.app.ds.trades)
        t = Trade(
            id=trade_id, wallet_id=w.id, symbol=symbol, direction=direction,
            entry_price=round(entry, 2), stop_loss=round(sl, 2), take_profit=round(tp, 2),
            position_size=size, position_value=pos_value, reason=reason,
            created_at=created_at, risk_amount=risk_amount, risk_pct_of_balance=risk_pct_bal,
            status="Open", exit_price=None, closed_at=None, pnl_abs=None, pnl_pct=None, result=None, close_reason=None
        )
        self.app.ds.add_trade(t)

        # reset
        self.cmb_symbol.setCurrentIndex(self.cmb_symbol.findText("BTCUSDT"))
        self.btn_long.setChecked(True)
        self.sp_entry.setValue(90000.00); self.sp_sl.setValue(90000.00); self.sp_tp.setValue(90000.00)
        self.sp_pos_units.setValue(0.0); self.sp_pos_value.setValue(0.0); self.ed_reason.clear()
        self._update_qty_title()
        self.update_risk_labels()

        QMessageBox.information(self, "Sucesso", "Trade guardado.")
        self.app.refresh_all()
        try: self.app.tab_update.populate_update_trade_combo()
        except Exception: pass
