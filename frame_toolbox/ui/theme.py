# 最小限のダークテーマを定義する。
# 状態の意味は色と独立した文字ラベルで表す。
STYLESHEET = """
QWidget { background: #141b23; color: #e4ebf1; font-size: 14px; }
QMainWindow { background: #10171f; }
QLabel#title { font-size: 29px; font-weight: 650; }
QLabel#subtitle { color: #a5b6c6; }
QLabel#mode { background: #284458; color: #bce6ff; border-radius: 6px; padding: 8px; }
QTabWidget::pane { border: 1px solid #344554; border-radius: 6px; }
QTabBar::tab { background: #1c2834; color: #b6c6d4; padding: 12px 18px; }
QTabBar::tab:selected { background: #2b4a61; color: white; }
QGroupBox { border: 1px solid #344554; border-radius: 8px; margin-top: 12px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 14px; padding: 0 6px; }
QPushButton { background: #28485f; border: 1px solid #527187; border-radius: 6px; padding: 10px 15px; }
QPushButton:hover { background: #345d7b; }
QPushButton:disabled { background: #202b35; color: #7e909f; border-color: #344554; }
QLineEdit, QSpinBox, QDoubleSpinBox, QPlainTextEdit { background: #0e1720; border: 1px solid #425567; border-radius: 4px; padding: 7px; selection-background-color: #345d7b; }
QScrollArea { border: 0; }
QStatusBar { color: #b5c9d8; }
QCheckBox { spacing: 9px; }
"""
