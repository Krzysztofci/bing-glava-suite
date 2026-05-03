# gui/theme.py
# Motyw GUI — Forest-ttk-theme (rdbende, MIT License)
# https://github.com/rdbende/Forest-ttk-theme
#
# Zamiast budować własny motyw od zera, używamy Forest-dark jako bazy.
# Jedyna niestandardowa warstwa to AccelSlider (canvas), który motyw TTK
# nie może obsłużyć — tam używamy kolorów wyekstrahowanych z Forest-dark.
#
# Dostępne motywy: "forest-dark", "forest-light"
# Przyszłe motywy: dodaj plik .tcl + katalog z PNG do gui/themes/
# =============================================================================
import os
import tkinter as tk
from tkinter import ttk

# ─────────────────────────────────────────────────────────────────────────────
# Ścieżka do katalogu z motywami
# ─────────────────────────────────────────────────────────────────────────────
_THEMES_DIR = os.path.join(os.path.dirname(__file__), "themes")

# ─────────────────────────────────────────────────────────────────────────────
# Rejestr dostępnych motywów
# { nazwa_ttk: ścieżka_do_.tcl }
# ─────────────────────────────────────────────────────────────────────────────
AVAILABLE_THEMES = {
    "forest-dark":         os.path.join(_THEMES_DIR, "forest-dark.tcl"),
    "forest-light":        os.path.join(_THEMES_DIR, "forest-light.tcl"),
}

# ─────────────────────────────────────────────────────────────────────────────
# Paleta kolorów dla widgetów canvas (AccelSlider) i tk.* widgetów,
# które TTK nie stylizuje. Wyekstrahowane z Forest-dark/light.
# ─────────────────────────────────────────────────────────────────────────────
_PALETTE = {
    "forest-dark": {
        "bg":           "#313131",
        "bg_entry":     "#313131",
        "fg":           "#eeeeee",
        "fg2":          "#aaaaaa",
        "fg3":          "#777777",
        "select_bg":    "#217346",
        "select_fg":    "#ffffff",
        "border":       "#4a4a4a",
        # AccelSlider — canvas
        "slider_fill":       "#217346",
        "slider_fill_shift": "#e6a817",
        "slider_track":      "#3d3d3d",
        "slider_border":     "#4a4a4a",
        "slider_handle":     "#43a047",
        "slider_handle_sh":  "#f5c518",
        "slider_text":       "#cccccc",
        # ── Aliasy kompatybilności — stary kod używający COLORS["bg1"] itp. ──
        "bg0":      "#252525",
        "bg1":      "#313131",
        "bg2":      "#3d3d3d",
        "bg3":      "#4a4a4a",
        "text":     "#eeeeee",
        "text2":    "#aaaaaa",
        "text3":    "#777777",
        "red":      "#e53935",
        "red_h":    "#ef5350",
        "red_dim":  "#1b3a2a",
        "green":    "#43a047",
        "green_dim":"#1b5e20",
        "blue":     "#42a5f5",
        "amber":    "#ffa726",
        "amber_dim":"#3e2a00",
        "border2":  "#4a4a4a",
    },
    "forest-light": {
        "bg":           "#ffffff",
        "bg_entry":     "#ffffff",
        "fg":           "#000000",
        "fg2":          "#555555",
        "fg3":          "#888888",
        "select_bg":    "#217346",
        "select_fg":    "#ffffff",
        "border":       "#cccccc",
        # AccelSlider — canvas
        "slider_fill":       "#217346",
        "slider_fill_shift": "#e6a817",
        "slider_track":      "#e0e0e0",
        "slider_border":     "#cccccc",
        "slider_handle":     "#43a047",
        "slider_handle_sh":  "#f5c518",
        "slider_text":       "#333333",
        # ── Aliasy kompatybilności ──
        "bg0":      "#f0f0f0",
        "bg1":      "#ffffff",
        "bg2":      "#e8e8e8",
        "bg3":      "#d8d8d8",
        "text":     "#000000",
        "text2":    "#444444",
        "text3":    "#888888",
        "red":      "#c62828",
        "red_h":    "#e53935",
        "red_dim":  "#1a3d2a",
        "green":    "#2e7d32",
        "green_dim":"#1b5e20",
        "blue":     "#1565c0",
        "amber":    "#e65100",
        "amber_dim":"#fff3e0",
        "border2":  "#cccccc",
    },
}

# Aktywna paleta — aktualizowana przez apply_theme()
COLORS: dict = dict(_PALETTE["forest-dark"])

# Aktywna nazwa motywu
ACTIVE_THEME: str = "forest-dark"


# ─────────────────────────────────────────────────────────────────────────────
# apply_theme — ładuje Forest-ttk-theme i ustawia paletę canvas
# ─────────────────────────────────────────────────────────────────────────────

def apply_theme(root: tk.Tk, theme: str = "forest-dark"):
    """
    Ładuje wybrany motyw Forest-ttk-theme i aktywuje go.

    Parametry:
        root   — okno główne tk.Tk
        theme  — "forest-dark" (domyślnie) lub "forest-light"
    """
    global COLORS, ACTIVE_THEME

    if theme not in AVAILABLE_THEMES:
        theme = "forest-dark"

    tcl_path = AVAILABLE_THEMES[theme]
    if not os.path.exists(tcl_path):
        raise FileNotFoundError(
            f"Plik motywu nie istnieje: {tcl_path}\n"
            f"Upewnij się, że katalog gui/themes/ zawiera pliki Forest-ttk-theme."
        )

    # Załaduj plik .tcl motywu
    root.tk.call("source", tcl_path)
    style = ttk.Style(root)
    style.theme_use(theme)

    # Zaktualizuj globalną paletę canvas
    COLORS = dict(_PALETTE.get(theme, _PALETTE["forest-dark"]))
    ACTIVE_THEME = theme


def get_theme_names() -> list:
    """Zwraca listę załadowanych nazw motywów."""
    return list(AVAILABLE_THEMES.keys())


# ─────────────────────────────────────────────────────────────────────────────
# Fabryki widgetów — cienkie wrappery nad ttk.*
# Używaj ich zamiast tk.Frame / tk.Label itp. dla spójności z motywem.
# ─────────────────────────────────────────────────────────────────────────────

# Opcje tk.* których ttk.* NIE obsługuje — filtrowane w fabrykach
_TTK_UNSUPPORTED = frozenset([
    'bg', 'fg', 'background', 'foreground',
    'activebackground', 'activeforeground',
    'disabledforeground', 'selectcolor',
    'highlightbackground', 'highlightcolor', 'highlightthickness',
    'insertbackground', 'relief', 'bd', 'font', 'cursor',
    'padx', 'pady', 'ipadx', 'ipady',
])

def _ttk_kw(kw):
    """Usuwa opcje nieobsługiwane przez ttk.* z przekazanych kwargs."""
    return {k: v for k, v in kw.items() if k not in _TTK_UNSUPPORTED}


def TFrame(parent, level=1, **kw):
    """ttk.Frame — ignoruje 'level' (zachowany dla kompatybilności)."""
    return ttk.Frame(parent, **_ttk_kw(kw))


def TLabelFrame(parent, text="", **kw):
    """ttk.LabelFrame z motywem — filtruje opcje tk.LabelFrame.
    Domyślnie padding=(8, 6) jak w przykładzie Forest."""
    kw.setdefault("padding", (8, 6))
    return ttk.LabelFrame(parent, text=text, **_ttk_kw(kw))


def TLabel(parent, text="", secondary=False, **kw):
    """ttk.Label z motywem — filtruje opcje tk.Label."""
    return ttk.Label(parent, text=text, **_ttk_kw(kw))


def TCheckbutton(parent, **kw):
    """ttk.Checkbutton z motywem."""
    return ttk.Checkbutton(parent, **_ttk_kw(kw))


def TEntry(parent, **kw):
    """ttk.Entry z motywem."""
    return ttk.Entry(parent, **_ttk_kw(kw))


def TSeparator(parent, orient="horizontal", **kw):
    """ttk.Separator."""
    return ttk.Separator(parent, orient=orient, **_ttk_kw(kw))


# ─────────────────────────────────────────────────────────────────────────────
# Style przycisków — konwencja: przekaż style= do ttk.Button
# ─────────────────────────────────────────────────────────────────────────────
#
# Forest-dark oferuje dwa style przycisków:
#   ""              — standardowy (szary)
#   "Accent.TButton"— akcentowany (zielony)
#
# Definiujemy stałe dla czytelności kodu w modułach.
BTN_STYLE_DEFAULT = ""
BTN_STYLE_ACCENT  = "Accent.TButton"

# Aliasy dla wstecznej kompatybilności z kodem który importował słowniki BTN_*
# Każdy z nich to kwargs do ttk.Button — jedyna zmiana to style= zamiast bg/fg
BTN_APPLY  = {"style": "Accent.TButton"}
BTN_SAVE   = {"style": ""}
BTN_DELETE = {"style": "Accent.TButton"}   # nadpisz style w kodzie jeśli chcesz inny
BTN_RESET  = {"style": ""}
BTN_TOGGLE = {"style": ""}
BTN_FETCH  = {"style": "Accent.TButton"}
