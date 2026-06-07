import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from pbpicat import i18n
from pbpicat.config import init_catalogs
from pbpicat.ui.main_window import MainWindow

try:
    import pillow_heif

    pillow_heif.register_heif_opener()
except ImportError:  # pragma: no cover
    pass


def _resource(relative: str) -> Path:
    # sys._MEIPASS is set by PyInstaller when running from a frozen bundle
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative
    return Path(__file__).parent / relative


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("PBPicat")
    app.setOrganizationName("PBPicat")
    app.setApplicationVersion("1.6.3")

    icon_path = _resource("resources/pbpicat.svg")
    app.setWindowIcon(QIcon(str(icon_path)))

    init_catalogs()
    i18n.setup(app)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":  # pragma: no cover
    main()
