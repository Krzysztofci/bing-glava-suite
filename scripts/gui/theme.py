# gui/theme.py
# Centralny motyw GUI — Dark Carbon / Flat Remix Red.
#
# Użycie:
#   from ..theme import COLORS, T_FRAME, T_LF, T_LABEL, T_BTN
#   from ..theme import BTN_APPLY, BTN_SAVE, BTN_DELETE, BTN_RESET
#   from ..theme import themed_frame, themed_lf, themed_label, apply_theme
# =============================================================================
import tkinter as tk
from tkinter import ttk

# ─────────────────────────────────────────────────────────────────────────────
# Paleta
# ─────────────────────────────────────────────────────────────────────────────
COLORS = {
    "bg0":        "#252525",
    "bg1":        "#2f2f2f",
    "bg2":        "#383838",
    "bg3":        "#424242",
    "border":     "#1e1e1e",
    "border2":    "#4a4a4a",
    "red":        "#e53935",
    "red_h":      "#ef5350",
    "red_dim":    "#b71c1c",
    "text":       "#eeeeee",
    "text2":      "#9e9e9e",
    "text3":      "#757575",
    "green":      "#43a047",
    "green_dim":  "#1b5e20",
    "blue":       "#42a5f5",
    "amber":      "#ffa726",
    "amber_dim":  "#3e2a00",
    "brown":      "#5d3a2a",
    "brown_dim":  "#2a1a10",
    "slider_fill":    "#e53935",
    "slider_fill_sh": "#1565c0",
    "slider_track":   "#383838",
    "slider_border":  "#4a4a4a",
    "slider_focus":   "#e53935",
}

# ─────────────────────────────────────────────────────────────────────────────
# Słowniki kwargs dla widgetów — rozpakuj przez **
# ─────────────────────────────────────────────────────────────────────────────

# Frame
T_FRAME = {"bg": COLORS["bg1"]}
T_FRAME0 = {"bg": COLORS["bg0"]}   # dla ramek najwyższego poziomu

# LabelFrame
T_LF = {
    "bg":                   COLORS["bg1"],
    "fg":                   COLORS["text2"],
    "relief":               "flat",
    "highlightbackground":  COLORS["border2"],
    "highlightthickness":   1,
}

# Label
T_LABEL = {"bg": COLORS["bg1"], "fg": COLORS["text2"]}
T_LABEL2 = {"bg": COLORS["bg1"], "fg": COLORS["text3"]}  # hint / jednostka

# Checkbutton
T_CHECK = {
    "bg":              COLORS["bg1"],
    "fg":              COLORS["text2"],
    "activebackground":COLORS["bg2"],
    "activeforeground":COLORS["text"],
    "selectcolor":     COLORS["bg2"],
    "relief":          "flat",
    "bd":              0,
}

# Entry
T_ENTRY = {
    "bg":                   COLORS["bg2"],
    "fg":                   COLORS["text"],
    "insertbackground":     COLORS["text"],
    "relief":               "flat",
    "highlightbackground":  COLORS["border2"],
    "highlightthickness":   1,
    "bd":                   0,
}

# Przyciski
BTN_APPLY = {
    "bg":              COLORS["green_dim"],
    "fg":              "#a5d6a7",
    "activebackground":"#2e7d32",
    "activeforeground":"#c8e6c9",
    "relief":          "flat",
    "bd":              0,
    "font":            ("Arial", 8),
    "cursor":          "hand2",
}
BTN_SAVE = {
    "bg":              COLORS["bg2"],
    "fg":              COLORS["text2"],
    "activebackground":COLORS["bg3"],
    "activeforeground":COLORS["text"],
    "relief":          "flat",
    "bd":              0,
    "font":            ("Arial", 8),
    "cursor":          "hand2",
}
BTN_DELETE = {
    "bg":              COLORS["red_dim"],
    "fg":              "#ef9a9a",
    "activebackground":"#c62828",
    "activeforeground":"#ffcdd2",
    "relief":          "flat",
    "bd":              0,
    "font":            ("Arial", 8),
    "cursor":          "hand2",
}
BTN_RESET = {
    "bg":              COLORS["brown_dim"],
    "fg":              "#a1887f",
    "activebackground":"#3a2010",
    "activeforeground":"#bcaaa4",
    "relief":          "flat",
    "bd":              0,
    "font":            ("Arial", 8),
    "cursor":          "hand2",
}
BTN_TOGGLE = {
    "bg":              COLORS["bg2"],
    "fg":              COLORS["text"],
    "activebackground":COLORS["bg3"],
    "activeforeground":COLORS["text"],
    "relief":          "flat",
    "bd":              0,
    "font":            ("Arial", 9),
    "cursor":          "hand2",
}
BTN_FETCH = {
    "bg":              "#1a2a3a",
    "fg":              "#90caf9",
    "activebackground":"#1e3a5f",
    "activeforeground":"#bbdefb",
    "relief":          "flat",
    "bd":              0,
    "font":            ("Arial", 8),
    "cursor":          "hand2",
}

# ─────────────────────────────────────────────────────────────────────────────
# Fabryki widgetów — używaj zamiast tk.Frame/LabelFrame/Label
# ─────────────────────────────────────────────────────────────────────────────

def TFrame(parent, level=1, **kw):
    """Frame z tłem motywu. level=0=bg0, 1=bg1(default), 2=bg2."""
    bg = {0: COLORS["bg0"], 1: COLORS["bg1"], 2: COLORS["bg2"]}.get(level, COLORS["bg1"])
    return tk.Frame(parent, bg=bg, **kw)


def TLabelFrame(parent, text="", **kw):
    """LabelFrame z motywem — zawsze ciemne tło i jasna etykieta."""
    return tk.LabelFrame(
        parent, text=text,
        bg=COLORS["bg1"], fg=COLORS["text2"],
        relief="flat",
        highlightbackground=COLORS["border2"],
        highlightcolor=COLORS["border2"],
        highlightthickness=1,
        **kw
    )
    # Tytuł sekcji
    tk.Label(outer, text=text, font=font,
             bg=COLORS["bg1"], fg=COLORS["text2"],
             anchor="w").pack(fill="x", padx=padx, pady=(pady, 2))
    # Zwróć inner frame — do niego trafiają dzieci jak do LabelFrame
    inner = tk.Frame(outer, bg=COLORS["bg1"])
    inner.pack(fill="both", expand=True, padx=padx, pady=(0, pady))
    # Zachowaj referencję do outer żeby pack() działał na właściwym widgecie
    inner._outer = outer
    # Nadpisz pack/grid/place żeby działały na outer
    _orig_pack = inner.pack

    def _pack(**kw2):
        outer.pack(**kw2)
    def _grid(**kw2):
        outer.grid(**kw2)
    def _place(**kw2):
        outer.place(**kw2)

    inner.pack  = _pack   # type: ignore
    inner.grid  = _grid   # type: ignore
    inner.place = _place  # type: ignore

    return inner


def TLabel(parent, text="", secondary=False, **kw):
    """Label z motywem."""
    fg = COLORS["text3"] if secondary else COLORS["text2"]
    return tk.Label(parent, text=text,
                    bg=COLORS["bg1"], fg=fg, **kw)


def TCheckbutton(parent, **kw):
    """Checkbutton z motywem."""
    return tk.Checkbutton(
        parent,
        bg=COLORS["bg1"], fg=COLORS["text2"],
        activebackground=COLORS["bg2"],
        activeforeground=COLORS["text"],
        selectcolor=COLORS["red_dim"],
        relief="flat", bd=0,
        **kw
    )


def TEntry(parent, **kw):
    """Entry z motywem."""
    return tk.Entry(
        parent,
        bg=COLORS["bg2"], fg=COLORS["text"],
        insertbackground=COLORS["text"],
        relief="flat",
        highlightbackground=COLORS["border2"],
        highlightthickness=1,
        bd=0,
        **kw
    )


def TSeparator(parent, **kw):
    """Poziomy separator."""
    return tk.Frame(parent, bg=COLORS["bg0"], height=1, **kw)


# ─────────────────────────────────────────────────────────────────────────────
# apply_theme — minimalna wersja: tylko okno główne i ttk
# ─────────────────────────────────────────────────────────────────────────────

def apply_theme(root: tk.Tk):
    """
    Ustaw tło okna głównego, globalne opcje tk i style ttk.
    option_add musi być wywołane PRZED tworzeniem widgetów.
    """
    root.configure(bg=COLORS["bg0"])

    # Globalne opcje — działają dla widgetów tworzonych PO tym wywołaniu
    root.option_add("*Background",                COLORS["bg1"])
    root.option_add("*Foreground",                COLORS["text2"])
    root.option_add("*activeBackground",          COLORS["bg2"])
    root.option_add("*activeForeground",          COLORS["text"])
    root.option_add("*selectBackground",          COLORS["red_dim"])
    root.option_add("*selectForeground",          COLORS["text"])
    root.option_add("*highlightBackground",       COLORS["border2"])
    root.option_add("*highlightColor",            COLORS["red"])
    root.option_add("*highlightThickness",        "0")
    root.option_add("*insertBackground",          COLORS["text"])
    root.option_add("*troughColor",               COLORS["bg2"])
    root.option_add("*relief",                    "flat")
    root.option_add("*bd",                        "0")

    # Entry
    root.option_add("*Entry.Background",          COLORS["bg2"])
    root.option_add("*Entry.Foreground",          COLORS["text"])
    root.option_add("*Entry.insertBackground",    COLORS["text"])
    root.option_add("*Entry.highlightThickness",  "1")
    root.option_add("*Entry.highlightBackground", COLORS["border2"])
    root.option_add("*Entry.highlightColor",      COLORS["red"])
    root.option_add("*Entry.relief",              "flat")
    root.option_add("*Entry.bd",                  "0")

    # Label
    root.option_add("*Label.Background",          COLORS["bg1"])
    root.option_add("*Label.Foreground",          COLORS["text2"])
    root.option_add("*Label.relief",              "flat")
    root.option_add("*Label.bd",                  "0")

    # Button
    root.option_add("*Button.Background",         COLORS["bg2"])
    root.option_add("*Button.Foreground",         COLORS["text2"])
    root.option_add("*Button.activeBackground",   COLORS["bg3"])
    root.option_add("*Button.activeForeground",   COLORS["text"])
    root.option_add("*Button.highlightThickness", "0")
    root.option_add("*Button.highlightBackground",COLORS["bg2"])
    root.option_add("*Button.relief",             "flat")
    root.option_add("*Button.bd",                 "0")

    # Checkbutton
    root.option_add("*Checkbutton.Background",          COLORS["bg1"])
    root.option_add("*Checkbutton.Foreground",          COLORS["text2"])
    root.option_add("*Checkbutton.activeBackground",    COLORS["bg1"])
    root.option_add("*Checkbutton.activeForeground",    COLORS["text"])
    root.option_add("*Checkbutton.selectColor",         COLORS["bg2"])
    root.option_add("*Checkbutton.highlightThickness",  "0")
    root.option_add("*Checkbutton.relief",              "flat")
    root.option_add("*Checkbutton.bd",                  "0")

    # LabelFrame
    root.option_add("*LabelFrame.Background",           COLORS["bg1"])
    root.option_add("*LabelFrame.Foreground",           COLORS["text2"])
    root.option_add("*LabelFrame.highlightBackground",  COLORS["border2"])
    root.option_add("*LabelFrame.highlightColor",        COLORS["border2"])
    root.option_add("*LabelFrame.highlightThickness",   "1")
    root.option_add("*LabelFrame.relief",               "flat")
    root.option_add("*LabelFrame.bd",                   "0")

    # Frame
    root.option_add("*Frame.Background",          COLORS["bg1"])
    root.option_add("*Frame.highlightThickness",  "0")
    root.option_add("*Frame.relief",              "flat")
    root.option_add("*Frame.bd",                  "0")

    # Scale (legacy)
    root.option_add("*Scale.Background",          COLORS["bg1"])
    root.option_add("*Scale.troughColor",         COLORS["bg2"])
    root.option_add("*Scale.highlightThickness",  "0")

    style = ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        pass

    # Combobox
    style.configure("TCombobox",
        fieldbackground=COLORS["bg2"],
        background=COLORS["bg2"],
        foreground=COLORS["text"],
        selectbackground=COLORS["red_dim"],
        selectforeground=COLORS["text"],
        arrowcolor=COLORS["text2"],
        bordercolor=COLORS["border2"],
        darkcolor=COLORS["border"],
        lightcolor=COLORS["border2"],
        relief="flat",
        padding=3,
    )
    style.map("TCombobox",
        fieldbackground=[("readonly", COLORS["bg2"]),
                         ("focus",    COLORS["bg2"])],
        foreground=[("readonly", COLORS["text"])],
        background=[("readonly", COLORS["bg2"]),
                    ("active",   COLORS["bg3"])],
    )
    # Dropdown lista
    root.option_add("*TCombobox*Listbox.background",        COLORS["bg2"])
    root.option_add("*TCombobox*Listbox.foreground",        COLORS["text"])
    root.option_add("*TCombobox*Listbox.selectBackground",  COLORS["red_dim"])
    root.option_add("*TCombobox*Listbox.selectForeground",  COLORS["text"])
    root.option_add("*TCombobox*Listbox.relief",            "flat")
    root.option_add("*TCombobox*Listbox.bd",                "0")
    root.option_add("*TCombobox*Listbox.highlightThickness","1")
    root.option_add("*TCombobox*Listbox.highlightBackground", COLORS["border2"])
    root.option_add("*TCombobox*Listbox.highlightColor",    COLORS["border2"])

    # Scrollbar
    style.configure("TScrollbar",
        background=COLORS["bg2"],
        troughcolor=COLORS["bg1"],
        arrowcolor=COLORS["text3"],
        bordercolor=COLORS["border"],
        relief="flat",
    )
