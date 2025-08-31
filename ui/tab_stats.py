# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QWidget, QGridLayout, QLabel, QHBoxLayout, QPushButton, QFileDialog, QMessageBox
from PyQt5.QtGui import QPixmap, QPainter, QFont
from PyQt5.QtCore import Qt

from models import pretty_money


class TabStats(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.build()

    def build(self):
        self.setStyleSheet("""
            QLabel { font-size: 12pt; color: #ddd; }
            QLabel.big { font-size: 20pt; font-weight: 700; }
            QPushButton { font-size: 11pt; }
        """)

        g = QGridLayout(self)
        g.setHorizontalSpacing(12)
        g.setVerticalSpacing(10)

        # Título + botão exportar
        title_row = QWidget()
        h = QHBoxLayout(title_row)
        h.setContentsMargins(0, 0, 0, 0)
        self.lbl_title = QLabel("Resumo Global (todas as carteiras)")
        self.lbl_title.setProperty("class", "big")
        self.lbl_title.setStyleSheet("font-size: 20pt; font-weight: 700; color: #eee;")
        self.btn_export = QPushButton("Exportar PNG")
        self.btn_export.clicked.connect(self.export_png)
        h.addStretch(); h.addWidget(self.lbl_title); h.addSpacing(12); h.addWidget(self.btn_export); h.addStretch()
        g.addWidget(title_row, 0, 0, 1, 2)

        # Linhas de KPIs
        def kpi_row(label_text):
            ln = QLabel(label_text); lv = QLabel("-")
            ln.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            lv.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            return ln, lv

        self.rows = {}
        r = 1
        for key, text in [
            ("total_trades", "Total de trades:"),
            ("closed_trades", "Fechados:"),
            ("open_trades", "Abertos:"),
            ("winners", "Vencedores:"),
            ("losers", "Perdedores:"),
            ("breakeven", "Break-even:"),
            ("winrate_pct", "Taxa de acerto:"),
            ("pnl_total", "PnL total:"),
            ("initial_balance", "Saldo inicial (soma):"),
            ("current_balance", "Saldo atual (soma):"),
            ("growth_pct", "Crescimento (global):"),
        ]:
            ln, lv = kpi_row(text)
            g.addWidget(ln, r, 0)
            g.addWidget(lv, r, 1)
            self.rows[key] = lv
            r += 1

        self.refresh()

    # ---------- cálculo local (GLOBAL) ----------
    @staticmethod
    def _compute_stats_global(all_trades, initial_sum: float):
        total = len(all_trades)
        closed = [t for t in all_trades if getattr(t, "status", "") == "Closed"]
        open_ts = total - len(closed)

        winners = sum(1 for t in closed if (t.pnl_abs or 0) > 0)
        losers = sum(1 for t in closed if (t.pnl_abs or 0) < 0)
        breakeven = sum(1 for t in closed if (t.pnl_abs or 0) == 0)

        pnl_total = sum((t.pnl_abs or 0.0) for t in closed)
        current_balance = initial_sum + pnl_total

        winrate_pct = (winners / len(closed) * 100.0) if closed else 0.0
        growth_pct = ((current_balance - initial_sum) / initial_sum * 100.0) if initial_sum > 0 else 0.0

        return {
            "total_trades": total,
            "closed_trades": len(closed),
            "open_trades": open_ts,
            "winners": winners,
            "losers": losers,
            "breakeven": breakeven,
            "winrate_pct": winrate_pct,
            "pnl_total": pnl_total,
            "current_balance": current_balance,
            "growth_pct": growth_pct,
        }

    # ---------- Lógica ----------
    def refresh(self):
        """Resumo global: considera TODAS as carteiras e TODOS os trades."""
        # soma dos saldos iniciais de todas as carteiras
        wallets = list(self.app.ds.wallets.values()) if hasattr(self.app.ds, "wallets") else []
        initial_sum = sum(getattr(w, "initial_balance", 0.0) for w in wallets)

        # todos os trades
        all_trades = list(self.app.ds.trades.values()) if hasattr(self.app.ds, "trades") else []

        stats = self._compute_stats_global(all_trades, initial_sum)

        self.rows["total_trades"].setText(str(stats["total_trades"]))
        self.rows["closed_trades"].setText(str(stats["closed_trades"]))
        self.rows["open_trades"].setText(str(stats["open_trades"]))
        self.rows["winners"].setText(str(stats["winners"]))
        self.rows["losers"].setText(str(stats["losers"]))
        self.rows["breakeven"].setText(str(stats["breakeven"]))
        self.rows["winrate_pct"].setText(f"{stats['winrate_pct']:.2f}%")
        self.rows["pnl_total"].setText(f"$ {pretty_money(stats['pnl_total'])}")
        self.rows["initial_balance"].setText(f"$ {pretty_money(initial_sum)}")
        self.rows["current_balance"].setText(f"$ {pretty_money(stats['current_balance'])}")
        self.rows["growth_pct"].setText(f"{stats['growth_pct']:.2f}%")

    def export_png(self):
        """Guarda uma imagem PNG da aba com nome da carteira atual e logo (se houver)."""
        pix: QPixmap = self.grab()

        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing)
        font = QFont(); font.setPointSize(12); font.setBold(True)
        painter.setFont(font); painter.setPen(Qt.white)

        # Nota: título já indica que é global; apenas decorativo
        painter.drawText(10, 22, "Resumo Global")

        try:
            if getattr(self.app, "logo_label", None) and self.app.logo_label.pixmap():
                painter.drawPixmap(
                    pix.width() - 70, 5,
                    self.app.logo_label.pixmap().scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
        except Exception:
            pass

        painter.end()

        path, _ = QFileDialog.getSaveFileName(self, "Guardar PNG", "tradeiros_stats_global.png", "PNG (*.png)")
        if not path:
            return
        ok = pix.save(path, "PNG")
        QMessageBox.information(self, "Exportar PNG", f"Estatísticas guardadas em:\n{path}" if ok else "Falha ao guardar PNG.")
