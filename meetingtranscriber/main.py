import sys
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QFont
from PySide6.QtWidgets import QApplication

from meetingtranscriber.core.paths import assets_dir
from meetingtranscriber.ui.main_window import MainWindow


def load_qss(app: QApplication):
    qss_path = assets_dir() / "theme.qss"
    if qss_path.exists():
        app.setStyleSheet(qss_path.read_text(encoding="utf-8"))


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    app.setFont(QFont("WinSoft Pro", 14))

    ico_path = assets_dir() / "app.ico"
    if ico_path.exists():
        app.setWindowIcon(QIcon(str(ico_path)))

    load_qss(app)

    w = MainWindow()
    w.setLayoutDirection(Qt.RightToLeft)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()