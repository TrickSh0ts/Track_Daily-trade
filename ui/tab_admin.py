# -*- coding: utf-8 -*-
import os
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QMessageBox
from PyQt5.QtCore import Qt

from storage import WALLETS_FILE, TRADES_FILE, SYMBOLS_FILE, SETTINGS_FILE, save_json
from storage import load_json


class TabAdmin(QWidget):
    """Aba de manutenção: reset total."""
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.build()

    def build(self):
        self.setStyleSheet("QLabel { font-size: 12pt; } QPushButton { font-size: 12pt; }")
        v = QVBoxLayout(self)
        v.setAlignment(Qt.AlignTop)
        v.addWidget(QLabel("<b>Manutenção</b>"))
        v.addWidget(QLabel("⚠️ Reset Total apaga carteiras, trades, paridades e definições."))
        btn = QPushButton("RESET TOTAL (apagar todos os dados)")
        btn.setStyleSheet("background:#b71c1c; color:white; font-weight:600; padding:8px;")
        btn.clicked.connect(self.reset_all)
        v.addWidget(btn)

    def reset_all(self):
        if QMessageBox.question(self, "Confirmar Reset",
                                "Irá perder TODOS os dados. Tem a certeza?",
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        # Apagar ficheiros (ou limpar conteúdo)
        for path in [WALLETS_FILE, TRADES_FILE, SYMBOLS_FILE, SETTINGS_FILE]:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass
        # Recriar defaults mínimos
        save_json(SYMBOLS_FILE, ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"])
        save_json(SETTINGS_FILE, {"theme": "dark"})
        QMessageBox.information(self, "Reset", "Dados apagados. Reinicie a aplicação.")
