"""Internationalisation bootstrap for PBPicat.

Call setup(app) once before creating any window.
"""

from __future__ import annotations

import gettext
import locale
import os
from pathlib import Path

from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator
from PySide6.QtWidgets import QApplication

_DOMAIN = "pbpicat"
_LOCALE_DIR = Path(__file__).parent / "locale"


class _GettextTranslator(QTranslator):
    def __init__(self, translation: gettext.NullTranslations, parent: QApplication) -> None:
        super().__init__(parent)
        self._t = translation

    def translate(self, context: str, source_text: str, disambiguation=None, n: int = -1) -> str:
        return self._t.gettext(source_text)


def _system_language() -> str:
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        val = os.environ.get(var, "")
        if val:
            first = val.split(":")[0]
            lang = first.split("_")[0].split(".")[0]
            if lang and lang not in ("", "C", "POSIX"):
                return lang
    loc, _ = locale.getlocale()
    if loc:
        return loc.split("_")[0]
    return "en"


def available_languages() -> list[tuple[str, str]]:
    """Return [(lang_code, lang_name_in_that_language), …] sorted by code."""
    result: list[tuple[str, str]] = []
    for mo_path in sorted(_LOCALE_DIR.glob("*/LC_MESSAGES/pbpicat.mo")):
        lang_code = mo_path.parts[-3]
        try:
            t = gettext.translation(_DOMAIN, localedir=str(_LOCALE_DIR), languages=[lang_code])
        except FileNotFoundError:
            continue
        lang_name = t.gettext("language_name")
        if lang_name == "language_name":
            lang_name = lang_code
        result.append((lang_code, lang_name))
    return result


def current_language() -> str:
    """Return the language code currently in effect (same resolution as setup())."""
    from pbpicat.config import load_global_config

    config = load_global_config()
    override = config.get("language", "")
    return override if override else _system_language()


def setup(app: QApplication) -> None:
    """Install translations for app. Safe to call multiple times."""
    lang = current_language()

    try:
        t: gettext.NullTranslations = gettext.translation(_DOMAIN, localedir=str(_LOCALE_DIR), languages=[lang])
    except FileNotFoundError:
        t = gettext.NullTranslations()

    t.install()
    translator = _GettextTranslator(t, app)
    app.installTranslator(translator)

    qt_translator = QTranslator(app)
    translations_path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if qt_translator.load(QLocale(lang), "qtbase", "_", translations_path):
        app.installTranslator(qt_translator)
