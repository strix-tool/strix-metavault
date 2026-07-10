#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Strix i18n — leichtgewichtige Mehrsprachigkeit für die Strix-Desktop-Tools.

Erkennt beim ersten Start automatisch die Sprache des Betriebssystems, erlaubt
eine manuelle Auswahl (die von der App in ihrer Konfiguration gespeichert wird)
und fällt immer auf Englisch zurück. Die Übersetzungen liegen als eine JSON-Datei
pro Sprache im Ordner ``i18n/`` neben der App (``i18n/<code>.json``); Englisch ist
der Durchreiche-Standard und braucht keine Datei.

Dieses Modul ist bewusst abhängigkeitsfrei und über alle Python-Tools portabel.
"""

import json
import locale
import os
import sys

# (Code, muttersprachlicher Name) — dieselben 13 Sprachen wie auf der Website.
LANGS = [
    ("en", "English"), ("de", "Deutsch"), ("fr", "Français"), ("es", "Español"),
    ("it", "Italiano"), ("pt-BR", "Português (BR)"), ("pl", "Polski"),
    ("uk", "Українська"), ("ru", "Русский"), ("sv", "Svenska"),
    ("zh-CN", "简体中文"), ("ja", "日本語"), ("ko", "한국어"),
]
LANG_CODES = [c for c, _n in LANGS]
LANG_NAME = dict(LANGS)

# Primäres Sprachkürzel des Systems -> unser Code (Sonderfälle ohne Region).
_PRIMARY = {"pt": "pt-BR", "zh": "zh-CN"}


def detect_os_lang(default="en"):
    """Ermittelt aus der Systemumgebung einen unserer Sprachcodes."""
    raw = ""
    try:
        raw = locale.getdefaultlocale()[0] or ""
    except Exception:
        raw = ""
    if not raw:
        for var in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
            val = os.environ.get(var, "")
            if val:
                raw = val
                break
    raw = raw.replace("-", "_").split(".")[0].split(":")[0]
    if not raw:
        return default
    parts = raw.split("_")
    prim = parts[0].lower()
    region = parts[1].upper() if len(parts) > 1 else ""
    combo = ("%s-%s" % (prim, region)) if region else prim
    for c in LANG_CODES:                       # exakte Übereinstimmung (pt_BR -> pt-BR)
        if c.lower() == combo.lower():
            return c
    if prim in _PRIMARY:                        # Sonderfall-Zuordnung
        return _PRIMARY[prim]
    for c in LANG_CODES:                        # nur Primärkürzel (de_AT -> de)
        if c.split("-")[0].lower() == prim:
            return c
    return default


def _app_dir():
    # Unter PyInstaller liegen die per --add-data gebündelten Dateien in _MEIPASS.
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


class Translator:
    """Lädt bei Bedarf ``i18n/<lang>.json`` und übersetzt englische Quelltexte."""

    def __init__(self, lang="en", i18n_dir=None):
        self.dir = i18n_dir or os.path.join(_app_dir(), "i18n")
        self._cache = {}
        self.lang = "en"
        self._map = {}
        self.set(lang)

    def set(self, lang):
        self.lang = lang if lang in LANG_CODES else "en"
        self._map = {} if self.lang == "en" else self._load(self.lang)
        return self.lang

    def _load(self, lang):
        if lang in self._cache:
            return self._cache[lang]
        data = {}
        try:
            with open(os.path.join(self.dir, "%s.json" % lang), "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                data = loaded
        except Exception:
            data = {}
        self._cache[lang] = data
        return data

    def __call__(self, s, **kw):
        t = self._map.get(s, s)
        if kw:
            try:
                return t.format(**kw)
            except Exception:
                return s.format(**kw)
        return t
