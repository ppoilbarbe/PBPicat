import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from pbpicat import i18n
from pbpicat.config import init_catalogs
from pbpicat.ui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("PBPicat")
    app.setOrganizationName("PBPicat")
    app.setApplicationVersion("1.0.0")

    icon_path = Path(__file__).parent / "resources" / "pbpicat.svg"
    app.setWindowIcon(QIcon(str(icon_path)))

    init_catalogs()
    i18n.setup(app)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
