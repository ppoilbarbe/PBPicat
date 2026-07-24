import argparse
import sys
from importlib.metadata import version
from pathlib import Path

from PySide6.QtCore import QLoggingCategory
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from pbpicat import i18n
from pbpicat.argparse_qt import add_qt_arguments
from pbpicat.config import init_catalogs, list_catalogs, set_base_dir, set_current_catalog
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
    parser.add_argument(
        "catalog",
        nargs="?",
        default=None,
        help="Name of a catalog to load at startup (not a path). Ignored with an error if no such catalog exists.",
    )
    add_qt_arguments(parser)
    return parser.parse_args()


def _load_bundled_fonts(app: object) -> None:
    """Register bundled fonts and set a reliable default font (frozen builds only).

    The libfontconfig.so bundled by PyInstaller has its default config path
    hardcoded to the build machine's conda prefix.  On any other machine that
    path is missing and fontconfig fails silently, leaving Qt with no valid
    system font.  This function bypasses fontconfig for font selection:
      1. All bundled .ttf files are registered in Qt's font database.
      2. Ubuntu (shipped with fonts-conda-ecosystem) is set as the application
         font so the UI always looks correct regardless of the host configuration.
    The runtime hook (pyi_rth_fonts.py) still generates a portable fonts.conf so
    that fontconfig rendering settings (anti-aliasing, hinting…) are inherited
    from the system /etc/fonts/fonts.conf.
    """
    if not getattr(sys, "frozen", False):
        return
    from PySide6.QtGui import QFont, QFontDatabase

    fonts_dir = Path(sys._MEIPASS) / "fonts"  # type: ignore[attr-defined]
    if not fonts_dir.is_dir():
        return

    loaded: set[str] = set()
    for ttf in sorted(fonts_dir.glob("*.ttf")):
        fid = QFontDatabase.addApplicationFont(str(ttf))
        if fid >= 0:
            loaded.update(QFontDatabase.applicationFontFamilies(fid))

    # Set Ubuntu as the default application font so the bundle renders
    # consistently on any machine, regardless of whether fontconfig finds
    # the system config.  The bundled libfontconfig.so has its default config
    # path hardcoded to the build machine's conda prefix, which does not exist
    # on target machines, so font selection cannot rely on fontconfig.
    if "Ubuntu" in loaded:
        current = app.font()  # type: ignore[union-attr]
        app.setFont(  # type: ignore[union-attr]
            QFont("Ubuntu", current.pointSize() if current.pointSize() > 0 else 10)
        )


def main() -> None:
    args = _parse_args()
    if args.dev_config_dir:
        set_base_dir(args.dev_config_dir)

    # Some camera firmware produces JPEGs with trailing garbage bytes before the
    # EOI marker; Qt's libjpeg decodes them fine but logs a harmless warning for
    # every such file. Silence it — there is nothing actionable for the user.
    QLoggingCategory.setFilterRules("qt.gui.imageio.jpeg=false")

    app = QApplication([sys.argv[0]] + args.qt_args)
    _load_bundled_fonts(app)
    app.setApplicationName("PBPicat")
    app.setOrganizationName("PBPicat")
    app.setApplicationVersion(version("pbpicat"))

    icon_path = _resource("resources/pbpicat.svg")
    app.setWindowIcon(QIcon(str(icon_path)))

    init_catalogs()
    i18n.setup(app)

    if args.catalog is not None:
        if args.catalog in list_catalogs(include_hidden=True):
            set_current_catalog(args.catalog)
        else:
            QMessageBox.warning(
                None,
                _("Catalog not found"),
                _('No catalog named "{name}" was found; using the last opened catalog instead.').format(
                    name=args.catalog
                ),
            )

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":  # pragma: no cover
    main()
