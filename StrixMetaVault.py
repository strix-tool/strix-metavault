#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Strix MetaVault - Desktop-Oberfläche (mit Theme)
================================================
Metadaten-Entferner + verschlüsselter 7z-Archivierer. Dunkles / helles Theme.
Mehrsprachig (13 Sprachen): Sprache wird beim Start aus dem Betriebssystem
erkannt und lässt sich oben rechts jederzeit umstellen.

Sicherheit: Diese Oberfläche zeigt das erzeugte Passwort nur ein einziges Mal in
einem modalen Fenster an; es wird niemals auf die Festplatte oder ins Log
geschrieben. Die eigentliche Arbeit erledigt strix_metavault_core abgesichert.
"""

import os
import sys
import json
import hmac
import queue
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import strix_metavault_core as mv
from strix_i18n import Translator, LANGS, LANG_CODES, LANG_NAME, detect_os_lang

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    HAVE_DND = True
except Exception:
    HAVE_DND = False

APP_NAME = "Strix MetaVault"
APP_TITLE = APP_NAME
FONT = "Segoe UI" if os.name == "nt" else "DejaVu Sans"
MONO = "Consolas" if os.name == "nt" else "DejaVu Sans Mono"

# Modulweiter Übersetzer; nach dem Lesen der Konfiguration in main() neu gesetzt.
_TR = Translator()


def _(s, **kw):
    return _TR(s, **kw)


# --------------------------------------------------------------------------- #
#  Theme-Paletten
# --------------------------------------------------------------------------- #
PALETTES = {
    "dark": {
        "bg": "#0f1115", "surface": "#171a21", "surface2": "#1e222b",
        "border": "#2a2f3a", "text": "#e6e9ef", "subtext": "#9aa4b2",
        "accent": "#4f8cff", "accent_hover": "#6ba0ff", "accent_text": "#ffffff",
        "danger": "#ff5c5c", "success": "#33c27f", "warn": "#f0b34a",
        "sel": "#2d3646", "on_pill": "#0f1115",
    },
    "light": {
        "bg": "#f4f6fb", "surface": "#ffffff", "surface2": "#eef1f7",
        "border": "#d6dbe6", "text": "#1b2430", "subtext": "#5b6472",
        "accent": "#2f6bff", "accent_hover": "#1f5af0", "accent_text": "#ffffff",
        "danger": "#d23b3b", "success": "#17915a", "warn": "#b7791f",
        "sel": "#d8e3ff", "on_pill": "#ffffff",
    },
}


def _config_path() -> str:
    if os.name == "nt":
        root = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        root = os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(root, APP_NAME, "config.json")


def load_config() -> dict:
    try:
        with open(_config_path(), "r", encoding="utf-8") as f:
            d = json.load(f)
            if isinstance(d, dict):
                return d
    except Exception:
        pass
    return {}


def save_config(**kw) -> None:
    try:
        p = _config_path()
        os.makedirs(os.path.dirname(p), exist_ok=True)
        cur = load_config()
        cur.update(kw)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(cur, f)
    except Exception:
        pass


def load_theme() -> str:
    t = load_config().get("theme")
    return t if t in PALETTES else "dark"


def load_lang() -> str:
    # Gespeicherte Auswahl hat Vorrang, sonst Sprache des Betriebssystems.
    saved = load_config().get("lang")
    if saved in LANG_CODES:
        return saved
    return detect_os_lang()


def default_output_dir() -> str:
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    return desktop if os.path.isdir(desktop) else os.path.expanduser("~")


def open_folder(path: str) -> None:
    try:
        if os.name == "nt":
            os.startfile(path)                # noqa
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception:
        pass


# --------------------------------------------------------------------------- #
#  Stil anwenden (ttk + Options-Datenbank)
# --------------------------------------------------------------------------- #
def apply_style(root: tk.Tk, style: ttk.Style, p: dict) -> None:
    try:
        style.theme_use("clam")
    except Exception:
        pass
    base = (FONT, 10)
    root.configure(bg=p["bg"])

    style.configure(".", background=p["bg"], foreground=p["text"],
                    fieldbackground=p["surface2"], bordercolor=p["border"],
                    lightcolor=p["border"], darkcolor=p["border"],
                    focuscolor=p["accent"], font=base)

    style.configure("App.TFrame", background=p["bg"])
    style.configure("Card.TFrame", background=p["surface"])
    style.configure("Header.TFrame", background=p["bg"])
    style.configure("Divider.TFrame", background=p["accent"])

    style.configure("Card.TLabelframe", background=p["surface"],
                    bordercolor=p["border"], relief="solid", borderwidth=1)
    style.configure("Card.TLabelframe.Label", background=p["surface"],
                    foreground=p["subtext"], font=(FONT, 10, "bold"))

    style.configure("H1.TLabel", background=p["bg"], foreground=p["text"],
                    font=(FONT, 17, "bold"))
    style.configure("Sub.TLabel", background=p["bg"], foreground=p["subtext"],
                    font=(FONT, 10))
    style.configure("Body.TLabel", background=p["bg"], foreground=p["text"])
    style.configure("Card.TLabel", background=p["surface"], foreground=p["text"])
    style.configure("CardSub.TLabel", background=p["surface"],
                    foreground=p["subtext"], font=(FONT, 9))

    # Schaltflächen
    style.configure("TButton", background=p["surface2"], foreground=p["text"],
                    bordercolor=p["border"], focusthickness=0, relief="flat",
                    padding=(12, 7))
    style.map("TButton",
              background=[("active", p["border"]), ("pressed", p["border"])],
              foreground=[("disabled", p["subtext"])])

    style.configure("Accent.TButton", background=p["accent"],
                    foreground=p["accent_text"], font=(FONT, 10, "bold"),
                    padding=(16, 9), relief="flat", bordercolor=p["accent"])
    style.map("Accent.TButton",
              background=[("active", p["accent_hover"]),
                          ("pressed", p["accent_hover"]),
                          ("disabled", p["surface2"])],
              foreground=[("disabled", p["subtext"])])

    style.configure("Ghost.TButton", background=p["bg"], foreground=p["subtext"],
                    bordercolor=p["border"], relief="flat", padding=(10, 6))
    style.map("Ghost.TButton",
              background=[("active", p["surface2"])],
              foreground=[("active", p["text"])])

    # Kontrollkästchen / Optionsfelder auf Kartenfläche
    for w in ("TCheckbutton", "TRadiobutton"):
        style.configure(w, background=p["surface"], foreground=p["text"],
                        focuscolor=p["surface"], indicatorcolor=p["surface2"])
        style.map(w,
                  background=[("active", p["surface"])],
                  foreground=[("disabled", p["subtext"])],
                  indicatorcolor=[("selected", p["accent"]),
                                  ("!selected", p["surface2"])])

    style.configure("TEntry", fieldbackground=p["surface2"], foreground=p["text"],
                    bordercolor=p["border"], insertcolor=p["text"], padding=4)
    style.map("TEntry", bordercolor=[("focus", p["accent"])])

    style.configure("TSpinbox", fieldbackground=p["surface2"], foreground=p["text"],
                    bordercolor=p["border"], arrowcolor=p["subtext"], padding=3)

    style.configure("TCombobox", fieldbackground=p["surface2"],
                    background=p["surface2"], foreground=p["text"],
                    bordercolor=p["border"], arrowcolor=p["subtext"], padding=3)
    style.map("TCombobox",
              fieldbackground=[("readonly", p["surface2"])],
              foreground=[("readonly", p["text"])],
              selectbackground=[("readonly", p["surface2"])],
              selectforeground=[("readonly", p["text"])])

    style.configure("Accent.Horizontal.TProgressbar",
                    troughcolor=p["surface2"], background=p["accent"],
                    bordercolor=p["border"], lightcolor=p["accent"],
                    darkcolor=p["accent"])

    style.configure("Vertical.TScrollbar", troughcolor=p["surface"],
                    background=p["surface2"], bordercolor=p["border"],
                    arrowcolor=p["subtext"])
    style.map("Vertical.TScrollbar", background=[("active", p["border"])])

    # Farben der Combobox-Aufklappliste
    root.option_add("*TCombobox*Listbox.background", p["surface2"])
    root.option_add("*TCombobox*Listbox.foreground", p["text"])
    root.option_add("*TCombobox*Listbox.selectBackground", p["accent"])
    root.option_add("*TCombobox*Listbox.selectForeground", p["accent_text"])


# --------------------------------------------------------------------------- #
#  Einmaliger Passwort-Dialog (mit Theme)
# --------------------------------------------------------------------------- #
class PasswordDialog(tk.Toplevel):
    def __init__(self, parent, palette, password: str, archive_path: str):
        super().__init__(parent)
        self.p = palette
        self._password = password
        self._clip_job = None
        self.title(_("Password — shown only once"))
        self.resizable(False, False)
        self.configure(bg=self.p["surface"], padx=20, pady=18)
        self.transient(parent)
        self.grab_set()

        ttk.Label(self, text=_("Your archive password"), style="Card.TLabel",
                  font=(FONT, 13, "bold")).pack(anchor="w")

        warn = tk.Label(self,
                        text=_("This password was not saved anywhere and will not be "
                               "shown again. Save it in a password manager now — if you "
                               "lose it, the archive cannot be opened."),
                        bg=self.p["surface"], fg=self.p["danger"],
                        justify="left", font=(FONT, 9), wraplength=420)
        warn.pack(anchor="w", pady=(6, 12))

        row = ttk.Frame(self, style="Card.TFrame"); row.pack(fill="x")
        self.var = tk.StringVar(value=password)
        self.entry = ttk.Entry(row, textvariable=self.var, width=42, show="•",
                               font=(MONO, 12))
        self.entry.configure(state="readonly")
        self.entry.pack(side="left", fill="x", expand=True)
        self._revealed = False
        self.reveal_btn = ttk.Button(row, text=_("Show"), width=8,
                                      style="Ghost.TButton", command=self._toggle)
        self.reveal_btn.pack(side="left", padx=(8, 0))

        btns = ttk.Frame(self, style="Card.TFrame"); btns.pack(fill="x", pady=(14, 2))
        ttk.Button(btns, text=_("Copy to clipboard"), command=self._copy).pack(side="left")
        self.status = tk.Label(btns, text="", bg=self.p["surface"],
                               fg=self.p["success"], font=(FONT, 9))
        self.status.pack(side="left", padx=12)

        ttk.Label(self, text=_("Archive:") + "  " + os.path.basename(archive_path),
                  style="CardSub.TLabel").pack(anchor="w", pady=(8, 2))

        ttk.Button(self, text=_("I saved the password — Close"), style="Accent.TButton",
                   command=self._close).pack(anchor="e", pady=(12, 0))

        self.protocol("WM_DELETE_WINDOW", self._close)
        self.bind("<Escape>", lambda e: self._close())
        self.entry.focus_set()
        self.update_idletasks()
        self._center(parent)

    def _center(self, parent):
        try:
            px, py = parent.winfo_rootx(), parent.winfo_rooty()
            pw, ph = parent.winfo_width(), parent.winfo_height()
            w, h = self.winfo_width(), self.winfo_height()
            self.geometry(f"+{px + (pw - w) // 2}+{py + (ph - h) // 3}")
        except Exception:
            pass

    def _toggle(self):
        self._revealed = not self._revealed
        self.entry.configure(show="" if self._revealed else "•")
        self.reveal_btn.configure(text=_("Hide") if self._revealed else _("Show"))

    def _copy(self):
        self.clipboard_clear()
        self.clipboard_append(self._password)
        self.status.configure(text=_("Copied — clipboard clears in 60 s"))
        if self._clip_job:
            self.after_cancel(self._clip_job)
        self._clip_job = self.after(60000, self._clear_clip)

    def _clear_clip(self):
        try:
            cur = self.clipboard_get()
            if hmac.compare_digest(cur, self._password):
                self.clipboard_clear()
                self.clipboard_append("")
                self.status.configure(text=_("Clipboard cleared"))
        except Exception:
            pass
        self._clip_job = None

    def _close(self):
        if self._clip_job:
            try:
                self.after_cancel(self._clip_job)
            except Exception:
                pass
            # Zwischenablage JETZT löschen, falls sie noch unser Passwort enthält —
            # ein Schließen vor Ablauf des 60-s-Timers würde das Passwort sonst
            # dauerhaft in der Zwischenablage des Systems belassen (im Widerspruch
            # zum Versprechen „wird in 60 s gelöscht").
            self._clear_clip()
        self._password = ""
        self.var.set("")
        self.grab_release()
        self.destroy()


# --------------------------------------------------------------------------- #
#  Hauptanwendung
# --------------------------------------------------------------------------- #
class StrixMetaVaultApp:
    # Englische Bezeichnung (kanonisch) + 7z-Kompressionsstufe. Die Anzeige wird
    # über _() übersetzt; ausgewählt wird über den Index, also sprachunabhängig.
    COMPRESSION = [("Store (0)", 0), ("Fast (1)", 1),
                   ("Normal (5)", 5), ("Maximum (9)", 9)]

    def __init__(self, root):
        self.root = root
        self.theme = load_theme()
        self.p = PALETTES[self.theme]
        self.style = ttk.Style(root)

        root.title(APP_NAME + " — " + _("Metadata Remover & Encrypted Archiver"))
        # Fenster an den Bildschirm anpassen, damit die Log-Karte unten immer
        # sichtbar ist (auf Laptops lief ein fest 900px hohes Fenster unten heraus).
        _sw, _sh = root.winfo_screenwidth(), root.winfo_screenheight()
        root.geometry("%dx%d" % (min(880, _sw - 80), min(820, _sh - 100)))
        root.minsize(640, 480)

        self.files = []
        self.msg_q = queue.Queue()
        self.running = False
        self.last_output_dir = None
        self.tools = mv.tool_status()
        self._pills = []
        self._manual = []          # (Widget, Rolle) für Live-Neufärbung
        self.comp_index = 2        # Standard: Normal (5)

        self._init_vars()
        apply_style(root, self.style, self.p)
        self._build_ui()
        self._apply_theme(self.theme, persist=False)
        self._refresh_file_list()
        self._sync_states()
        self.root.after(120, self._poll_queue)

    def _init_vars(self):
        # Einmal erzeugt und auf self gehalten, damit der Zustand beim
        # Sprachwechsel (Neuaufbau der Oberfläche) erhalten bleibt.
        self.v_clean = tk.BooleanVar(value=True)
        self.v_archive = tk.BooleanVar(value=True)
        self.v_encnames = tk.BooleanVar(value=True)
        self.v_randname = tk.BooleanVar(value=True)
        self.v_preserve = tk.BooleanVar(value=True)
        self.v_deep = tk.BooleanVar(value=True)
        self.v_secure = tk.BooleanVar(value=True)
        self.v_symbols = tk.BooleanVar(value=True)
        self.v_ambig = tk.BooleanVar(value=False)
        self.v_pwlen = tk.IntVar(value=24)
        self.v_pwmode = tk.StringVar(value="random")
        self.v_custompw = tk.StringVar(value="")
        self.v_outdir = tk.StringVar(value=default_output_dir())

    # ---------------- Sprache ----------------
    def _set_language(self, code):
        if code not in LANG_CODES or code == _TR.lang:
            return
        _TR.set(code)
        save_config(lang=code)
        self._rebuild()

    def _rebuild(self):
        # Zustand bleibt auf self erhalten (self.files, die tk-Variablen,
        # comp_index, Theme); nur die Widgets werden mit neuen Texten neu gebaut.
        self._pills = []
        self._manual = []
        for child in list(self.root.winfo_children()):
            child.destroy()
        apply_style(self.root, self.style, self.p)
        self.root.title(APP_NAME + " — " + _("Metadata Remover & Encrypted Archiver"))
        self._build_ui()
        self._apply_theme(self.theme, persist=False)
        self._refresh_file_list()
        self._sync_states()

    # ---------------- Theme ----------------
    def _apply_theme(self, name, persist=True):
        self.theme = name
        self.p = PALETTES[name]
        apply_style(self.root, self.style, self.p)
        self._recolor_manual()
        if hasattr(self, "theme_btn"):
            self.theme_btn.configure(
                text=(_("Light theme") if name == "dark" else _("Dark theme")))
        if persist:
            save_config(theme=name)

    def _toggle_theme(self):
        self._apply_theme("light" if self.theme == "dark" else "dark")

    def _register_manual(self, widget, role):
        self._manual.append((widget, role))
        return widget

    def _recolor_manual(self):
        p = self.p
        for w, role in self._manual:
            try:
                if role == "listbox":
                    w.configure(bg=p["surface2"], fg=p["text"],
                                selectbackground=p["sel"], selectforeground=p["text"],
                                highlightbackground=p["border"],
                                highlightcolor=p["accent"])
                elif role == "log":
                    w.configure(bg=p["surface2"], fg=p["text"],
                                insertbackground=p["text"],
                                highlightbackground=p["border"],
                                highlightcolor=p["border"])
                elif role == "hintbar":
                    w.configure(bg=p["surface"], fg=p["subtext"])
                elif role == "canvasbg":
                    w.configure(bg=p["bg"])
            except Exception:
                pass
        self._recolor_pills()

    def _recolor_pills(self):
        p = self.p
        for lbl, ok, required in self._pills:
            color = p["success"] if ok else (p["danger"] if required else p["warn"])
            lbl.configure(bg=color, fg=p["on_pill"])

    # ---------------- Oberfläche ----------------
    def _build_ui(self):
        outer = self.root
        # Alles lebt in einer vertikal scrollbaren Canvas, damit kein Abschnitt
        # abgeschnitten wird oder unabhängig von der Fenster-/Bildschirmgröße
        # „aus dem Fenster rutscht".
        canvas = tk.Canvas(outer, highlightthickness=0, bd=0, bg=self.p["bg"])
        vsb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview,
                            style="Vertical.TScrollbar")
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self._register_manual(canvas, "canvasbg")
        root = ttk.Frame(canvas, style="App.TFrame")
        _win = canvas.create_window((0, 0), window=root, anchor="nw")
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfigure(_win, width=e.width))
        root.bind("<Configure>",
                  lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))

        # Kopfbereich
        header = ttk.Frame(root, style="Header.TFrame")
        header.pack(fill="x", padx=18, pady=(16, 0))
        left = ttk.Frame(header, style="Header.TFrame"); left.pack(side="left")
        ttk.Label(left, text=APP_TITLE, style="H1.TLabel").pack(anchor="w")
        ttk.Label(left, text=_("Strip metadata · encrypt into an archive"),
                  style="Sub.TLabel").pack(anchor="w")

        # Sprachauswahl + Theme-Umschalter (oben rechts)
        self.theme_btn = ttk.Button(header, text=_("Light theme"), style="Ghost.TButton",
                                    command=self._toggle_theme)
        self.theme_btn.pack(side="right", pady=6)
        self.lang_cmb = ttk.Combobox(header, width=14, state="readonly",
                                     values=[LANG_NAME[c] for c in LANG_CODES])
        try:
            self.lang_cmb.current(LANG_CODES.index(_TR.lang))
        except Exception:
            self.lang_cmb.current(0)
        self.lang_cmb.pack(side="right", padx=(0, 8), pady=6)
        self.lang_cmb.bind(
            "<<ComboboxSelected>>",
            lambda e: self._set_language(LANG_CODES[self.lang_cmb.current()]))
        ttk.Label(header, text="🌐", style="Sub.TLabel").pack(side="right", padx=(0, 4))

        ttk.Frame(root, style="Divider.TFrame", height=2).pack(fill="x",
                                                               padx=18, pady=(10, 4))

        # Statusanzeige der Werkzeuge (Pills)
        pillbar = ttk.Frame(root, style="App.TFrame")
        pillbar.pack(fill="x", padx=18, pady=(6, 2))
        ttk.Label(pillbar, text=_("Tools:"), style="Body.TLabel").pack(side="left",
                                                                       padx=(0, 8))
        self._make_pill(pillbar, "7-Zip", self.tools["7z"], required=True)
        self._make_pill(pillbar, "ExifTool", self.tools["exiftool"], required=False)
        self._make_pill(pillbar, "pikepdf", self.tools["pikepdf"], required=False)
        self.tool_hint = self._register_manual(
            tk.Label(root, justify="left", anchor="w", font=(FONT, 9),
                     bg=self.p["surface"], fg=self.p["subtext"]),
            "hintbar")
        hint = self._tool_hint_text()
        if hint:
            self.tool_hint.configure(text=hint)
            self.tool_hint.pack(fill="x", padx=18, pady=(2, 4))

        # Karte „Dateien / Ordner"
        flf = ttk.Labelframe(root, text="  " + _("Files / Folders") + "  ",
                             style="Card.TLabelframe")
        flf.pack(fill="both", expand=True, padx=18, pady=8)
        lst_row = ttk.Frame(flf, style="Card.TFrame")
        lst_row.pack(fill="both", expand=True, padx=10, pady=(10, 6))
        self.listbox = self._register_manual(
            tk.Listbox(lst_row, selectmode="extended", height=7, activestyle="none",
                       borderwidth=0, highlightthickness=1,
                       font=(FONT, 10)), "listbox")
        self.listbox.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(lst_row, orient="vertical", command=self.listbox.yview,
                           style="Vertical.TScrollbar")
        sb.pack(side="left", fill="y")
        self.listbox.configure(yscrollcommand=sb.set)
        if HAVE_DND:
            self.listbox.drop_target_register(DND_FILES)
            self.listbox.dnd_bind("<<Drop>>", self._on_drop)

        fbtns = ttk.Frame(flf, style="Card.TFrame")
        fbtns.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(fbtns, text=_("Add files"), command=self._add_files).pack(side="left")
        ttk.Button(fbtns, text=_("Add folder"), command=self._add_folder).pack(side="left", padx=6)
        ttk.Button(fbtns, text=_("Remove selected"), command=self._remove_selected).pack(side="left")
        ttk.Button(fbtns, text=_("Clear"), command=self._clear_files).pack(side="left", padx=6)
        hinttext = _("Tip: drag & drop supported.") if HAVE_DND else _("(drag & drop: pip install tkinterdnd2)")
        ttk.Label(fbtns, text=hinttext, style="CardSub.TLabel").pack(side="right")

        # Karte „Optionen"
        opt = ttk.Labelframe(root, text="  " + _("Options") + "  ", style="Card.TLabelframe")
        opt.pack(fill="x", padx=18, pady=8)
        g = ttk.Frame(opt, style="Card.TFrame"); g.pack(fill="x", padx=12, pady=10)

        r = 0
        ttk.Checkbutton(g, text=_("Strip metadata (EXIF / Office / PDF)"),
                        variable=self.v_clean, command=self._sync_states
                        ).grid(row=r, column=0, columnspan=2, sticky="w"); r += 1
        ttk.Checkbutton(g, text=_("Keep color profile (ICC) and orientation"),
                        variable=self.v_preserve).grid(row=r, column=0, sticky="w", pady=2)
        ttk.Checkbutton(g, text=_("Office: also remove author names in comments / tracked changes"),
                        variable=self.v_deep).grid(row=r, column=1, sticky="w", pady=2); r += 1

        ttk.Separator(g).grid(row=r, column=0, columnspan=2, sticky="ew", pady=10); r += 1

        ttk.Checkbutton(g, text=_("Create an encrypted 7z archive"),
                        variable=self.v_archive, command=self._sync_states
                        ).grid(row=r, column=0, columnspan=2, sticky="w"); r += 1
        self.chk_encnames = ttk.Checkbutton(
            g, text=_("Encrypt file/folder names inside the archive (-mhe)"),
            variable=self.v_encnames)
        self.chk_encnames.grid(row=r, column=0, sticky="w", pady=2)
        self.chk_randname = ttk.Checkbutton(
            g, text=_("Randomize the output file name"), variable=self.v_randname)
        self.chk_randname.grid(row=r, column=1, sticky="w", pady=2); r += 1

        comp_row = ttk.Frame(g, style="Card.TFrame"); comp_row.grid(row=r, column=0, sticky="w", pady=2)
        ttk.Label(comp_row, text=_("Compression:"), style="Card.TLabel").pack(side="left", padx=(0, 6))
        self.cmb_comp = ttk.Combobox(comp_row, width=14, state="readonly",
                                     values=[_(l) for l, _v in self.COMPRESSION])
        self.cmb_comp.current(self.comp_index)
        self.cmb_comp.bind("<<ComboboxSelected>>",
                           lambda e: setattr(self, "comp_index", self.cmb_comp.current()))
        self.cmb_comp.pack(side="left")
        self.chk_secure = ttk.Checkbutton(g, text=_("Securely wipe temporary files"),
                                          variable=self.v_secure)
        self.chk_secure.grid(row=r, column=1, sticky="w", pady=2); r += 1

        pwf = ttk.Frame(g, style="Card.TFrame")
        pwf.grid(row=r, column=0, columnspan=2, sticky="ew", pady=(8, 0)); r += 1
        self.rb_rand = ttk.Radiobutton(pwf, text=_("Random password (recommended)"),
                                       variable=self.v_pwmode, value="random",
                                       command=self._sync_states)
        self.rb_rand.grid(row=0, column=0, sticky="w")
        len_row = ttk.Frame(pwf, style="Card.TFrame")
        len_row.grid(row=0, column=1, sticky="w", padx=(24, 0))
        ttk.Label(len_row, text=_("Length:"), style="Card.TLabel").pack(side="left")
        self.sp_len = ttk.Spinbox(len_row, from_=12, to=128, width=5,
                                  textvariable=self.v_pwlen)
        self.sp_len.pack(side="left", padx=(4, 12))
        self.chk_sym = ttk.Checkbutton(len_row, text=_("Symbols"), variable=self.v_symbols)
        self.chk_sym.pack(side="left")
        self.chk_amb = ttk.Checkbutton(len_row, text=_("Avoid ambiguous characters"),
                                       variable=self.v_ambig)
        self.chk_amb.pack(side="left", padx=(10, 0))
        self.rb_cust = ttk.Radiobutton(pwf, text=_("Use my own password:"),
                                       variable=self.v_pwmode, value="custom",
                                       command=self._sync_states)
        self.rb_cust.grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.ent_cust = ttk.Entry(pwf, textvariable=self.v_custompw, width=34, show="•")
        self.ent_cust.grid(row=1, column=1, sticky="w", pady=(6, 0))

        # Ausgabezeile
        outf = ttk.Frame(root, style="App.TFrame"); outf.pack(fill="x", padx=18, pady=(6, 2))
        ttk.Label(outf, text=_("Output folder:"), style="Body.TLabel").pack(side="left")
        ttk.Entry(outf, textvariable=self.v_outdir).pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(outf, text=_("Browse"), command=self._choose_outdir).pack(side="left")

        # Ausführungszeile
        runf = ttk.Frame(root, style="App.TFrame"); runf.pack(fill="x", padx=18, pady=(10, 2))
        self.run_btn = ttk.Button(runf, text=_("Run"), style="Accent.TButton",
                                  command=self._run)
        self.run_btn.pack(side="left")
        self.open_btn = ttk.Button(runf, text=_("Open output folder"),
                                   command=self._open_output, state="disabled")
        self.open_btn.pack(side="left", padx=8)
        self.prog = ttk.Progressbar(runf, mode="determinate",
                                    style="Accent.Horizontal.TProgressbar")
        self.prog.pack(side="left", fill="x", expand=True, padx=10)

        # Karte „Log"
        logf = ttk.Labelframe(root, text="  " + _("Log") + "  ", style="Card.TLabelframe")
        logf.pack(fill="both", expand=True, padx=18, pady=(6, 16))
        self.log = self._register_manual(
            tk.Text(logf, height=7, wrap="word", state="disabled",
                    borderwidth=0, highlightthickness=1, font=(MONO, 9)), "log")
        self.log.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=10)
        lsb = ttk.Scrollbar(logf, orient="vertical", command=self.log.yview,
                            style="Vertical.TScrollbar")
        lsb.pack(side="left", fill="y", pady=10)
        self.log.configure(yscrollcommand=lsb.set)

    def _make_pill(self, parent, text, ok, required):
        lbl = tk.Label(parent, text=text + ("  ✓" if ok else "  —"),
                       padx=10, pady=2, font=(FONT, 9, "bold"),
                       bg=self.p["success"] if ok else (self.p["danger"] if required else self.p["warn"]),
                       fg=self.p["on_pill"])
        lbl.pack(side="left", padx=4)
        self._pills.append((lbl, bool(ok), required))
        return lbl

    def _tool_hint_text(self):
        t = self.tools
        lines = []
        if not t["7z"]:
            lines.append(_("• 7-Zip is required for archiving (7-zip.org), or drop 7z.exe into the 'tools' folder."))
        if not t["exiftool"]:
            lines.append(_("• ExifTool is recommended (exiftool.org): broad cleaning for formats other than JPEG/PNG."))
        return "\n".join(lines)

    # ---------------- Datei-Handler ----------------
    def _add_files(self):
        for p in filedialog.askopenfilenames(title=_("Select files")):
            if p not in self.files:
                self.files.append(p)
        self._refresh_file_list()

    def _add_folder(self):
        p = filedialog.askdirectory(title=_("Select folder"))
        if p and p not in self.files:
            self.files.append(p)
        self._refresh_file_list()

    def _remove_selected(self):
        for i in reversed(self.listbox.curselection()):
            del self.files[i]
        self._refresh_file_list()

    def _clear_files(self):
        self.files.clear()
        self._refresh_file_list()

    def _on_drop(self, event):
        for p in self.root.tk.splitlist(event.data):
            if p not in self.files:
                self.files.append(p)
        self._refresh_file_list()

    def _refresh_file_list(self):
        self.listbox.delete(0, "end")
        for p in self.files:
            tag = "[DIR] " if os.path.isdir(p) else ""
            self.listbox.insert("end", tag + p)

    def _choose_outdir(self):
        p = filedialog.askdirectory(title=_("Output folder"), initialdir=self.v_outdir.get())
        if p:
            self.v_outdir.set(p)

    # ---------------- Zustandsabgleich ----------------
    def _sync_states(self):
        arch = self.v_archive.get()
        st = "normal" if arch else "disabled"
        for w in (self.chk_encnames, self.chk_randname, self.chk_secure,
                  self.rb_rand, self.rb_cust):
            w.configure(state=st)
        self.cmb_comp.configure(state="readonly" if arch else "disabled")
        rand = arch and self.v_pwmode.get() == "random"
        for w in (self.sp_len, self.chk_sym, self.chk_amb):
            w.configure(state="normal" if rand else "disabled")
        self.ent_cust.configure(
            state="normal" if (arch and self.v_pwmode.get() == "custom") else "disabled")

    # ---------------- Protokoll ----------------
    def _log(self, msg):
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _custom_password_ok(self, arch_opts):
        """Ein benutzerdefiniertes Archivpasswort prüfen. Gibt False zurück (und
        zeigt eine Meldung), wenn der Lauf abgebrochen werden soll: leer, unter
        der harten Untergrenze oder wenn der/die Nutzer/in ein schwaches, aber
        akzeptables Passwort ablehnt."""
        if not (arch_opts.make_archive and arch_opts.password_mode == "custom"):
            return True
        if not arch_opts.custom_password:
            messagebox.showwarning(APP_NAME, _("Custom password cannot be empty."))
            return False
        score, label, acceptable, warns = mv.password_strength(arch_opts.custom_password)
        if not acceptable:
            messagebox.showwarning(
                APP_NAME,
                _("Custom password is too weak to protect your archive.") + "\n\n"
                + _("Please {advice}.", advice="; ".join(warns)))
            return False
        if score < 3 and not messagebox.askyesno(
                APP_NAME,
                _("Password strength: {label}.", label=label) + "\n\n"
                + _("Suggestions: {advice}.",
                    advice="; ".join(warns or [_("use a longer, more varied password")]))
                + "\n\n"
                + _("A weak password can be brute-forced even though the archive "
                    "itself is AES-256 encrypted.") + "\n\n"
                + _("Use this password anyway?")):
            return False
        return True

    # ---------------- Ausführung ----------------
    def _run(self):
        if self.running:
            return
        if not self.files:
            messagebox.showwarning(APP_NAME, _("Add files or a folder first."))
            return
        if not self.v_clean.get() and not self.v_archive.get():
            messagebox.showwarning(APP_NAME, _("Select at least one action: cleaning or archiving."))
            return
        outdir = self.v_outdir.get().strip() or default_output_dir()
        comp = self.COMPRESSION[self.comp_index][1]
        clean_opts = mv.CleanOptions(preserve_color=self.v_preserve.get(),
                                     deep_office=self.v_deep.get())
        arch_opts = mv.ArchiveOptions(
            make_archive=self.v_archive.get(),
            encrypt_names=self.v_encnames.get(),
            compression=comp,
            password_mode=self.v_pwmode.get(),
            custom_password=self.v_custompw.get().strip(),
            password_length=int(self.v_pwlen.get() or 24),
            password_symbols=self.v_symbols.get(),
            password_avoid_ambiguous=self.v_ambig.get(),
            randomize_filename=self.v_randname.get(),
        )
        if not self._custom_password_ok(arch_opts):
            return

        self.running = True
        self.run_btn.configure(state="disabled")
        self.open_btn.configure(state="disabled")
        self.prog.configure(value=0, maximum=100)
        self._log("=" * 50)
        self._log(_("Started…"))

        inputs = list(self.files)
        exiftool, seven = self.tools["exiftool"], self.tools["7z"]
        do_clean, secure = self.v_clean.get(), self.v_secure.get()

        def worker():
            # Jede Ausnahme (z. B. ein nicht beschreibbarer Ausgabepfad, der schon
            # in makedirs VOR dem try von run_pipeline auslöst) muss trotzdem ein
            # Endergebnis posten - sonst stirbt der Thread stumm und die Oberfläche
            # bleibt für immer blockiert.
            try:
                rr = mv.run_pipeline(
                    inputs, outdir, clean_opts, arch_opts, do_clean=do_clean,
                    exiftool=exiftool, seven_zip=seven, secure_delete=secure,
                    log=lambda m: self.msg_q.put(("log", m)),
                    progress=lambda i, n: self.msg_q.put(("prog", (i, n))))
            except Exception as e:  # noqa: BLE001 - jeden Fehler an die Oberfläche melden
                rr = type("_Fail", (), {"ok": False, "error": str(e), "warnings": []})()
            self.msg_q.put(("done", rr))

        threading.Thread(target=worker, daemon=True).start()

    def _poll_queue(self):
        try:
            while True:
                kind, payload = self.msg_q.get_nowait()
                if kind == "log":
                    self._log(payload)
                elif kind == "prog":
                    i, n = payload
                    self.prog.configure(maximum=max(n, 1), value=i)
                elif kind == "done":
                    self._on_done(payload)
        except queue.Empty:
            pass
        self.root.after(120, self._poll_queue)

    def _on_done(self, rr):
        self.running = False
        self.run_btn.configure(state="normal")
        self.prog.configure(value=self.prog["maximum"])

        if not rr.ok:
            self._log(_("ERROR:") + " " + (rr.error or _("unknown error")))
            messagebox.showerror(APP_NAME, rr.error or _("Operation failed."))
            return

        if rr.warnings:
            self._log(_("Warnings:"))
            for w in rr.warnings:
                self._log("  • " + w)

        if rr.archive_path:
            self.last_output_dir = os.path.dirname(rr.archive_path)
            self._log(_("Done →") + " " + rr.archive_path)
        elif rr.output_dir_used:
            self.last_output_dir = rr.output_dir_used
            self._log(_("Done →") + " " + rr.output_dir_used)
        self.open_btn.configure(state="normal")

        if rr.password:
            PasswordDialog(self.root, self.p, rr.password, rr.archive_path or "")
            rr.password = None

        if rr.warnings:
            messagebox.showwarning(
                APP_NAME,
                _("Finished, but some items were skipped or could not be cleaned:") + "\n\n"
                + "\n".join("• " + w for w in rr.warnings[:12])
                + ("\n…" if len(rr.warnings) > 12 else ""))
        else:
            messagebox.showinfo(APP_NAME, _("Completed successfully."))

    def _open_output(self):
        if self.last_output_dir and os.path.isdir(self.last_output_dir):
            open_folder(self.last_output_dir)


def main():
    _TR.set(load_lang())
    root = TkinterDnD.Tk() if HAVE_DND else tk.Tk()
    try:
        root.iconbitmap(os.path.join(
            getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))),
            "metavault.ico"))
    except Exception:
        pass
    StrixMetaVaultApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
