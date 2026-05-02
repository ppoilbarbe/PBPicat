"""Tests for src/pbpicat/i18n.py — 100% statement coverage."""

import builtins
import gettext
from pathlib import Path
from unittest.mock import patch

import pbpicat.i18n as i18n_mod
from pbpicat.i18n import _GettextTranslator, _system_language, available_languages, setup

_LANG_VARS = ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG")


def _clear_lang_env(monkeypatch):
    for var in _LANG_VARS:
        monkeypatch.delenv(var, raising=False)


# ---------------------------------------------------------------------------
# _GettextTranslator
# ---------------------------------------------------------------------------


def test_translator_null_translations(qapp):
    t = gettext.NullTranslations()
    tr = _GettextTranslator(t, qapp)
    assert tr.translate("ctx", "hello") == "hello"


def test_translator_with_fr_catalogue(qapp):
    locale_dir = Path(i18n_mod.__file__).parent / "locale"
    t = gettext.translation("pbpicat", localedir=str(locale_dir), languages=["fr"])
    tr = _GettextTranslator(t, qapp)
    assert tr.translate("ctx", "Ready.") == "Prêt."


def test_translator_optional_args_accepted(qapp):
    t = gettext.NullTranslations()
    tr = _GettextTranslator(t, qapp)
    assert tr.translate("ctx", "hi", disambiguation="d", n=3) == "hi"


# ---------------------------------------------------------------------------
# _system_language
# ---------------------------------------------------------------------------


def test_system_language_uses_LANGUAGE(monkeypatch):  # noqa: N802
    _clear_lang_env(monkeypatch)
    monkeypatch.setenv("LANGUAGE", "de")
    assert _system_language() == "de"


def test_system_language_colon_list_uses_first(monkeypatch):
    _clear_lang_env(monkeypatch)
    monkeypatch.setenv("LANGUAGE", "fr:en:de")
    assert _system_language() == "fr"


def test_system_language_strips_locale_suffix(monkeypatch):
    _clear_lang_env(monkeypatch)
    monkeypatch.setenv("LANGUAGE", "fr_FR.UTF-8")
    assert _system_language() == "fr"


def test_system_language_strips_encoding_only(monkeypatch):
    _clear_lang_env(monkeypatch)
    monkeypatch.setenv("LANGUAGE", "ja.UTF-8")
    assert _system_language() == "ja"


def test_system_language_skips_C(monkeypatch):  # noqa: N802
    _clear_lang_env(monkeypatch)
    monkeypatch.setenv("LANGUAGE", "C")
    monkeypatch.setenv("LANG", "es")
    assert _system_language() == "es"


def test_system_language_skips_POSIX(monkeypatch):  # noqa: N802
    _clear_lang_env(monkeypatch)
    monkeypatch.setenv("LANGUAGE", "POSIX")
    monkeypatch.setenv("LANG", "it")
    assert _system_language() == "it"


def test_system_language_skips_empty_value(monkeypatch):
    _clear_lang_env(monkeypatch)
    monkeypatch.setenv("LANGUAGE", "")
    monkeypatch.setenv("LANG", "pt")
    assert _system_language() == "pt"


def test_system_language_uses_LC_ALL(monkeypatch):  # noqa: N802
    _clear_lang_env(monkeypatch)
    monkeypatch.setenv("LC_ALL", "zh")
    assert _system_language() == "zh"


def test_system_language_uses_LC_MESSAGES(monkeypatch):  # noqa: N802
    _clear_lang_env(monkeypatch)
    monkeypatch.setenv("LC_MESSAGES", "ko")
    assert _system_language() == "ko"


def test_system_language_uses_LANG(monkeypatch):  # noqa: N802
    _clear_lang_env(monkeypatch)
    monkeypatch.setenv("LANG", "nl")
    assert _system_language() == "nl"


def test_system_language_falls_back_to_locale_getlocale(monkeypatch):
    _clear_lang_env(monkeypatch)
    monkeypatch.setattr(i18n_mod.locale, "getlocale", lambda: ("sv_SE", "UTF-8"))
    assert _system_language() == "sv"


def test_system_language_returns_en_when_getlocale_is_none(monkeypatch):
    _clear_lang_env(monkeypatch)
    monkeypatch.setattr(i18n_mod.locale, "getlocale", lambda: (None, None))
    assert _system_language() == "en"


# ---------------------------------------------------------------------------
# available_languages
# ---------------------------------------------------------------------------


def test_available_languages_returns_list_of_tuples():
    langs = available_languages()
    assert isinstance(langs, list)
    assert all(isinstance(item, tuple) and len(item) == 2 for item in langs)


def test_available_languages_includes_en_and_fr():
    codes = {code for code, _ in available_languages()}
    assert "en" in codes and "fr" in codes


def test_available_languages_correct_names():
    langs = dict(available_languages())
    assert langs["en"] == "English"
    assert langs["fr"] == "Français"


def test_available_languages_sorted_by_code():
    codes = [code for code, _ in available_languages()]
    assert codes == sorted(codes)


def test_available_languages_skips_on_file_not_found(monkeypatch, tmp_path):
    fake_mo = tmp_path / "xx" / "LC_MESSAGES" / "pbpicat.mo"
    fake_mo.parent.mkdir(parents=True)
    fake_mo.touch()
    monkeypatch.setattr(i18n_mod, "_LOCALE_DIR", tmp_path)
    with patch("pbpicat.i18n.gettext.translation", side_effect=FileNotFoundError):
        assert available_languages() == []


def test_available_languages_falls_back_to_code_when_name_untranslated(monkeypatch, tmp_path):
    fake_mo = tmp_path / "zz" / "LC_MESSAGES" / "pbpicat.mo"
    fake_mo.parent.mkdir(parents=True)
    fake_mo.touch()
    monkeypatch.setattr(i18n_mod, "_LOCALE_DIR", tmp_path)
    with patch("pbpicat.i18n.gettext.translation", return_value=gettext.NullTranslations()):
        assert available_languages() == [("zz", "zz")]


# ---------------------------------------------------------------------------
# setup
# ---------------------------------------------------------------------------


def test_setup_installs_fr(qapp, monkeypatch):
    monkeypatch.setattr("pbpicat.config.load_config", lambda: {"language": "fr"})
    setup(qapp)
    assert builtins.__dict__["_"]("Ready.") == "Prêt."


def test_setup_installs_en(qapp, monkeypatch):
    monkeypatch.setattr("pbpicat.config.load_config", lambda: {"language": "en"})
    setup(qapp)
    assert builtins.__dict__["_"]("Ready.") == "Ready."


def test_setup_uses_system_language_when_no_override(qapp, monkeypatch):
    monkeypatch.setattr("pbpicat.config.load_config", lambda: {"language": ""})
    monkeypatch.setenv("LANGUAGE", "fr")
    setup(qapp)
    assert builtins.__dict__["_"]("Ready.") == "Prêt."


def test_setup_language_key_absent_from_config(qapp, monkeypatch):
    monkeypatch.setattr("pbpicat.config.load_config", lambda: {})
    monkeypatch.setenv("LANGUAGE", "en")
    setup(qapp)
    assert builtins.__dict__["_"]("Ready.") == "Ready."


def test_setup_falls_back_to_null_for_unknown_lang(qapp, monkeypatch):
    monkeypatch.setattr("pbpicat.config.load_config", lambda: {"language": "xx"})
    setup(qapp)
    assert builtins.__dict__["_"]("Ready.") == "Ready."


def test_setup_installs_qt_translator(qapp, monkeypatch):
    monkeypatch.setattr("pbpicat.config.load_config", lambda: {"language": "en"})
    with patch.object(qapp, "installTranslator") as mock_install:
        setup(qapp)
    mock_install.assert_called_once()
    assert isinstance(mock_install.call_args[0][0], _GettextTranslator)


def test_setup_is_idempotent(qapp, monkeypatch):
    monkeypatch.setattr("pbpicat.config.load_config", lambda: {"language": "fr"})
    setup(qapp)
    setup(qapp)
    assert builtins.__dict__["_"]("Ready.") == "Prêt."
