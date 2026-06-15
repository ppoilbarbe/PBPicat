import argparse
import sys
from importlib.metadata import version
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from pbpicat import i18n
from pbpicat.argparse_qt import add_qt_arguments
from pbpicat.config import init_catalogs, set_base_dir
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


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pbpicat",
        description=(
            "PBPicat — rename image/video files and their sidecars "
            "according to a structured schema built from EXIF metadata."
        ),
    )
    parser.add_argument(
        "--dev-config-dir",
        metavar="DIR",
        type=Path,
        help="Use DIR as the configuration directory instead of the default XDG location.",
    )
    add_qt_arguments(parser)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.dev_config_dir:
        set_base_dir(args.dev_config_dir)

    app = QApplication([sys.argv[0]] + args.qt_args)
    app.setApplicationName("PBPicat")
    app.setOrganizationName("PBPicat")
    app.setApplicationVersion(version("pbpicat"))

    icon_path = _resource("resources/pbpicat.svg")
    app.setWindowIcon(QIcon(str(icon_path)))

    init_catalogs()
    i18n.setup(app)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":  # pragma: no cover
    main()
