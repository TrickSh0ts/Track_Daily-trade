# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton
from charts import EquityCanvas, PnLCanvas
from models import equity_curve

class TabCharts(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.build()

    def build(self):
        v = QVBoxLayout(self)
        self.canvas_equity = EquityCanvas(self); v.addWidget(self.canvas_equity, 1)
        self.canvas_pnl = PnLCanvas(self); v.addWidget(self.canvas_pnl, 1)
        hb = QHBoxLayout(); btn = QPushButton("Atualizar Gráficos"); btn.clicked.connect(self.refresh); hb.addStretch(); hb.addWidget(btn); v.addLayout(hb)

    def refresh(self):
        w = self.app.current_wallet()
        if not w:
            self.canvas_equity.draw_equity([], 0.0); self.canvas_pnl.draw_pnl([]); return
        eq = equity_curve(self.app.ds.trades_for_wallet(w.id), w.initial_balance)
        self.canvas_equity.draw_equity(eq, w.initial_balance)
        closed = [t for t in self.app.ds.trades_for_wallet(w.id) if t.status=="Closed" and t.pnl_abs is not None]
        closed.sort(key=lambda x: x.closed_at or x.created_at)
        pnls = [t.pnl_abs for t in closed]
        self.canvas_pnl.draw_pnl(pnls)
