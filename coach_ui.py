from __future__ import annotations

import sys

APP_USER_MODEL_ID = "DotaCoachAI.App"


def _enable_windows_taskbar_icon() -> None:
    """Give Windows a real app identity so the taskbar uses our icon, not pythonw.exe."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:
        # The app should still start even if Windows refuses the explicit ID.
        pass


from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app_paths import resource_path
from config import APP_NAME
from ui.main_window import MainWindow

APP_STYLE = """
QWidget {
    background: #08111d;
    color: #f3f7ff;
    font-family: Segoe UI, Inter, Arial;
    font-size: 14px;
}
QFrame#Header {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #12233b, stop:0.55 #111a2b, stop:1 #231622);
    border: 1px solid #28405f;
    border-radius: 18px;
}
QFrame#Sidebar {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #101f35, stop:1 #0a1423);
    border: 1px solid #243b5c;
    border-radius: 18px;
    min-width: 178px;
    max-width: 205px;
}
QFrame#StatCard, QGroupBox {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #111d31, stop:1 #0c1524);
    border: 1px solid #28405f;
    border-radius: 16px;
}
QFrame#StatCard:hover, QGroupBox:hover {
    border-color: #3f608d;
}
QLabel#AppTitle {
    font-size: 28px;
    font-weight: 900;
    color: #ffffff;
}
QLabel#SectionTitle {
    font-size: 22px;
    font-weight: 800;
    color: #ffffff;
}
QLabel#Muted, QLabel#CardHint {
    color: #a9b8cc;
}
QLabel#CardTitle {
    color: #86b8ff;
    font-size: 13px;
    font-weight: 700;
    text-transform: uppercase;
}
QLabel#CardValue {
    color: #ffffff;
    font-size: 23px;
    font-weight: 900;
}
QLabel#StatusPill {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #16375b, stop:1 #2a2445);
    color: #e9f4ff;
    border: 1px solid #4d6f9e;
    border-radius: 12px;
    padding: 8px 12px;
}
QLabel#Warning {
    color: #ffd27c;
}
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2f4770, stop:1 #1a2942);
    border: 1px solid #496b9d;
    border-radius: 12px;
    padding: 9px 14px;
    color: #ffffff;
    font-weight: 700;
}
QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #e45f34, stop:1 #344f7e);
    border-color: #ff9a5e;
}
QPushButton:pressed {
    background: #162237;
}
QLineEdit, QTextEdit, QTableWidget, QComboBox, QListWidget {
    background: #0d1726;
    border: 1px solid #2a3f5d;
    border-radius: 12px;
    padding: 8px;
    selection-background-color: #2d6fc1;
    selection-color: #ffffff;
}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
    border-color: #f07a3f;
}
QTextEdit {
    line-height: 1.35em;
}
QGroupBox {
    margin-top: 12px;
    padding: 14px;
    font-weight: 800;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 7px;
    color: #ffb35c;
}
QHeaderView::section {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #203553, stop:1 #16243a);
    color: #f2f7ff;
    border: 0;
    border-right: 1px solid #334b70;
    padding: 8px;
    font-weight: 800;
}
QTableWidget {
    background: #0d1726;
    alternate-background-color: #12233a;
    color: #f4f8ff;
    gridline-color: #2d4160;
}
QTableWidget::item {
    background-color: #0d1726;
    color: #f4f8ff;
    padding: 6px;
    border: 0;
}
QTableWidget::item:alternate {
    background-color: #12233a;
    color: #f4f8ff;
}
QTableWidget::item:selected {
    background: #2d6fc1;
    color: #ffffff;
}
QTableCornerButton::section {
    background: #1f2f49;
    border: 0;
}
QComboBox::drop-down {
    border: 0;
    width: 26px;
}
QComboBox QAbstractItemView {
    background: #0f1b2c;
    color: #f4f8ff;
    border: 1px solid #2f4667;
    selection-background-color: #2d6fc1;
}
QListWidget::item {
    background: #12233a;
    border: 1px solid #2b4263;
    border-radius: 8px;
    margin: 3px;
    padding: 6px;
}
QListWidget::item:selected {
    background: #2d6fc1;
    color: #ffffff;
}
QScrollArea#PageScroll {
    border: 0;
    background: transparent;
}
QScrollBar:vertical {
    background: #07101b;
    width: 15px;
    margin: 0;
    border-radius: 7px;
}
QScrollBar::handle:vertical {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #365b8e, stop:1 #f06b3a);
    min-height: 42px;
    border-radius: 7px;
}
QScrollBar::handle:vertical:hover {
    background: #ff8a4f;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background: #07101b;
    height: 15px;
    margin: 0;
    border-radius: 7px;
}
QScrollBar::handle:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #365b8e, stop:1 #f06b3a);
    min-width: 42px;
    border-radius: 7px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}
"""



def main() -> None:
    _enable_windows_taskbar_icon()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    try:
        app.setDesktopFileName(APP_USER_MODEL_ID)
    except Exception:
        pass
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLE)

    icon_path = resource_path("ui", "assets", "dota_coach.ico")
    if icon_path.exists():
        icon = QIcon(str(icon_path))
        app.setWindowIcon(icon)
    else:
        icon = None

    window = MainWindow()
    if icon is not None:
        window.setWindowIcon(icon)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
