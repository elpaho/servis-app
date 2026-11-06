"""Boje i stil. Crvena/žuta moraju odgovarati pravilima isticanja iz db.py."""
RED_BG, RED_FG = "#FCEBEB", "#791F1F"
AMBER_BG, AMBER_FG = "#FAEEDA", "#633806"
ACCENT = "#185FA5"

STYLESHEET = f"""
QWidget {{ font-size: 11pt; color: #2c2c2a; }}
QMainWindow, QDialog {{ background: #f7f6f2; }}
QLineEdit, QPlainTextEdit, QComboBox, QDateEdit, QSpinBox {{
    padding: 6px 8px; border: 1px solid #b4b2a9; border-radius: 6px; background: white;
}}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QDateEdit:focus, QSpinBox:focus {{ border: 1px solid {ACCENT}; }}
QPushButton {{ padding: 8px 18px; border: 1px solid #b4b2a9; border-radius: 6px; background: white; }}
QPushButton:hover {{ background: #efede6; }}
QPushButton#primary {{ background: {ACCENT}; color: white; border: 1px solid {ACCENT}; font-weight: 600; }}
QPushButton#primary:hover {{ background: #0C447C; }}
QTableWidget {{
    background: white; border: 1px solid #d3d1c7; gridline-color: #ece9e0;
    selection-background-color: #B5D4F4; selection-color: #042C53;
}}
QHeaderView::section {{
    background: #f1efe8; padding: 7px 6px; border: none; border-bottom: 1px solid #d3d1c7; font-weight: 600;
}}
QTabBar::tab {{ padding: 9px 22px; border: 1px solid #d3d1c7; border-bottom: none; background: #efede6;
    margin-right: 2px; border-top-left-radius: 6px; border-top-right-radius: 6px; }}
QTabBar::tab:selected {{ background: white; font-weight: 600; color: {ACCENT}; }}
QGroupBox {{ border: 1px solid #d3d1c7; border-radius: 8px; margin-top: 12px; padding: 14px 10px 8px 10px; background: white; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 6px; font-weight: 600; }}
QListWidget {{ border: 1px solid #d3d1c7; border-radius: 6px; background: white; }}
QLabel#hint {{ color: #5f5e5a; }}
QLabel#error {{ color: #A32D2D; font-weight: 600; }}
"""
