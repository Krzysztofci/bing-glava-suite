#!/usr/bin/env python3
# =============================================================================
# glava-gui.py
# Szkielet okna GLava Control Center.
# Zakładki: Główna (stała) | ✦ Moduł (dynamiczna) | Zaawansowane (stała)
#
# Motyw: Forest-ttk-theme (rdbende, MIT License)
# https://github.com/rdbende/Forest-ttk-theme
# =============================================================================
import tkinter as tk
from tkinter import ttk
import os
import sys
import json
import datetime
import subprocess

_SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, _SCRIPT_DIR)

from gui.theme import apply_theme, COLORS, TFrame, TLabel, TSeparator, get_theme_names
from gui.widgets import _ensure_shift_style
from gui.core import (
    load_settings, save_settings, load_lang, available_langs,
    read_active_module, write_active_module,
    GLAVA_MODULES, WALLPAPER, FLAG_RED, FLAG_MANUAL, WALLPAPER_LOCK,
    CONFIG_DIR,
)
from gui.glava import glava_is_running

WIN_W_DEFAULT = 1040
WIN_H_DEFAULT = 768
WIN_W_MIN     = 600
WIN_H_MIN     = 460

GUI_CONF = os.path.join(CONFIG_DIR, "gui.conf")


# ─────────────────────────────────────────────────────────────────────────────
# Zapis / odczyt gui.conf
# ─────────────────────────────────────────────────────────────────────────────

def load_gui_conf():
    defaults = {
        "width":  WIN_W_DEFAULT,
        "height": WIN_H_DEFAULT,
        "x":      None,
        "y":      None,
        "theme":  "forest-dark",
    }
    if os.path.exists(GUI_CONF):
        try:
            with open(GUI_CONF) as f:
                data = json.load(f)
            for k in defaults:
                if k in data:
                    defaults[k] = data[k]
        except Exception:
            pass
    else:
        save_gui_conf(defaults)
    return defaults


def save_gui_conf(conf):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(GUI_CONF, "w") as f:
        json.dump(conf, f, indent=4)


# ─────────────────────────────────────────────────────────────────────────────
# Główna klasa GUI
# ─────────────────────────────────────────────────────────────────────────────

class GlavaGUI:
    def __init__(self, root):
        self.root          = root
        self.settings      = load_settings()
        self.T             = load_lang(self.settings.get("lang", "pl"))
        self.langs         = available_langs()
        self.active_module = read_active_module()
        self.gui_conf      = load_gui_conf()

        self._setup_window()
        self._build_header()
        self._build_notebook()
        self._build_statusbar()
        self._schedule_status_update()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._resize_after = None
        self.root.bind("<Configure>", self._on_configure)

    # ─────────────────────────────────────────────────────────────────────────
    # Okno
    # ─────────────────────────────────────────────────────────────────────────

    def _setup_window(self):
        self.root.title(self.T.get("title", "GLava Control Center"))
        self.root.resizable(True, True)
        self.root.minsize(WIN_W_MIN, WIN_H_MIN)

        w = max(self.gui_conf.get("width",  WIN_W_DEFAULT), WIN_W_MIN)
        h = max(self.gui_conf.get("height", WIN_H_DEFAULT), WIN_H_MIN)
        x = self.gui_conf.get("x")
        y = self.gui_conf.get("y")

        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()

        if x is not None and y is not None:
            x = max(0, min(x, sw - w))
            y = max(0, min(y, sh - h))
        else:
            x = (sw - w) // 2
            y = (sh - h) // 2

        self.root.geometry(f"{w}x{h}+{x}+{y}")

        icon_path = os.path.join(_SCRIPT_DIR, "icon", "glava-gui.png")
        if os.path.exists(icon_path):
            try:
                img = tk.PhotoImage(file=icon_path)
                self.root.iconphoto(True, img)
                self.root._icon = img
            except Exception:
                pass

    # ─────────────────────────────────────────────────────────────────────────
    # Nagłówek: tytuł + wybór języka + tryb expert
    # ─────────────────────────────────────────────────────────────────────────

    def _build_header(self):
        T = self.T

        header = ttk.Frame(self.root, padding=(8, 4, 8, 0))
        header.pack(fill="x")

        # Tytuł po lewej
        ttk.Label(
            header,
            text=T.get("title", "GLava Control Center"),
            font=("TkDefaultFont", 10, "bold"),
        ).pack(side="left")

        # Język + Expert po prawej
        right = ttk.Frame(header)
        right.pack(side="right")

        # Expert mode — Switch z Forest
        self.expert_mode = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            right,
            text=T.get("label_expert_mode", "Tryb expert"),
            variable=self.expert_mode,
            style="Switch",
            command=self._on_expert_toggle,
        ).pack(side="right", padx=(10, 0))

        # Wybór języka
        ttk.Label(right,
                  text=T.get("section_language", "Język") + ":").pack(side="left", padx=(0, 4))
        self.lang_var = tk.StringVar(value=self.settings.get("lang", "pl"))
        lang_cb = ttk.Combobox(
            right,
            textvariable=self.lang_var,
            values=list(self.langs.keys()),
            width=6,
            state="readonly",
        )
        lang_cb.pack(side="left")
        lang_cb.bind("<<ComboboxSelected>>", self._on_lang_change)

        ttk.Separator(self.root).pack(fill="x", pady=(4, 0))

    # ─────────────────────────────────────────────────────────────────────────
    # Zakładki — ttk.Notebook
    # ─────────────────────────────────────────────────────────────────────────

    def _build_notebook(self):
        T = self.T

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=4, pady=4)

        self.frames = {}
        tab_defs = [
            ("main",     T.get("tab_main",     "Główna")),
            ("module",   self._module_tab_label()),
            ("advanced", T.get("tab_advanced", "Zaawansowane")),
        ]

        for key, label in tab_defs:
            frame = ttk.Frame(self.notebook, padding=(8, 6))
            self.notebook.add(frame, text=label)
            self.frames[key] = frame

        self._tab_keys = [k for k, _ in tab_defs]

        self._populate_tabs()

        # Pokazuj właściwą zakładkę po kliknięciu
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    def _module_tab_label(self):
        T = self.T
        name = T.get(f"module_{self.active_module}", self.active_module.capitalize())
        return f"{name} ✦"

    def _on_tab_changed(self, event=None):
        idx = self.notebook.index("current")
        key = self._tab_keys[idx]
        if key == "main" and hasattr(self, "_tab_main_ref"):
            self._tab_main_ref.refresh_geometry()

    def _show_tab(self, key):
        """Przełącza na zakładkę o podanym kluczu."""
        if key in self._tab_keys:
            idx = self._tab_keys.index(key)
            self.notebook.select(idx)

    def _refresh_module_tab_label(self):
        idx = self._tab_keys.index("module")
        self.notebook.tab(idx, text=self._module_tab_label())

    def _populate_tabs(self):
        from gui.tab_main     import build_tab_main
        from gui.tab_module   import build_tab_module
        from gui.tab_advanced import build_tab_advanced

        for frame in self.frames.values():
            for w in frame.winfo_children():
                w.destroy()

        build_tab_main(self.frames["main"], self)
        build_tab_module(self.frames["module"], self)
        build_tab_advanced(self.frames["advanced"], self)

    def rebuild_module_tab(self):
        from gui.tab_module import build_tab_module
        for w in self.frames["module"].winfo_children():
            w.destroy()
        build_tab_module(self.frames["module"], self)
        self._refresh_module_tab_label()

    # ─────────────────────────────────────────────────────────────────────────
    # Pasek statusu
    # ─────────────────────────────────────────────────────────────────────────

    def _build_statusbar(self):
        ttk.Separator(self.root, orient="horizontal").pack(fill="x", side="bottom")
        self.status_label = ttk.Label(
            self.root,
            text="...",
            font=("TkDefaultFont", 8),
            anchor="w",
            padding=(8, 3),
        )
        self.status_label.pack(fill="x", side="bottom")

    def _schedule_status_update(self):
        self.update_status()
        self.root.after(3000, self._schedule_status_update)

    def update_status(self):
        T = self.T
        running = glava_is_running()
        module  = read_active_module()

        if running:
            if os.path.exists(FLAG_MANUAL):
                mode = T.get("mode_manual", "tryb ręczny")
            elif os.path.exists(FLAG_RED):
                mode = T.get("mode_red",    "tryb RED")
            else:
                mode = T.get("mode_auto",   "tryb AUTO")
            status = f"● {T.get('status_active', 'GLava aktywna')} [{module}] [{mode}]"
        else:
            status = f"○ {T.get('status_inactive', 'GLava wyłączona')}"

        if os.path.exists(WALLPAPER):
            dt = datetime.datetime.fromtimestamp(
                os.path.getmtime(WALLPAPER)
            ).strftime("%d %b %Y %H:%M")
            status += f"   |   {T.get('label_wallpaper', 'Tapeta')}: {dt}"
        else:
            status += f"   |   {T.get('label_no_wallpaper', 'brak tapety')}"

        if os.path.exists(WALLPAPER_LOCK):
            status += f"   |   🔒 {T.get('label_wallpaper_locked', 'zablokowana')}"

        self.status_label.config(text=status)

    # ─────────────────────────────────────────────────────────────────────────
    # Zapis stanu okna
    # ─────────────────────────────────────────────────────────────────────────

    def _save_gui_conf(self):
        """Publiczny dostęp do zapisu gui_conf — używany przez tab_advanced."""
        save_gui_conf(self.gui_conf)

    def _on_configure(self, event=None):
        if self._resize_after:
            self.root.after_cancel(self._resize_after)
        self._resize_after = self.root.after(500, self._save_window_state)

    def _save_window_state(self):
        try:
            geo = self.root.geometry()  # "WxH+X+Y"
            import re
            m = re.match(r'(\d+)x(\d+)\+(-?\d+)\+(-?\d+)', geo)
            if m:
                w, h, x, y = int(m[1]), int(m[2]), int(m[3]), int(m[4])
                self.gui_conf.update({"width": w, "height": h, "x": x, "y": y})
                save_gui_conf(self.gui_conf)
        except Exception:
            pass

    def _on_close(self):
        self._save_window_state()
        self.root.destroy()

    # ─────────────────────────────────────────────────────────────────────────
    # Zmiana języka / expert
    # ─────────────────────────────────────────────────────────────────────────

    def _on_lang_change(self, event=None):
        lang = self.lang_var.get()
        self.settings["lang"] = lang
        save_settings(self.settings)
        self._restart = True
        # Anuluj debounced zapis i zapisz aktualną pozycję
        if self._resize_after:
            self.root.after_cancel(self._resize_after)
            self._resize_after = None
        self._save_window_state()
        self.root.destroy()

    def _on_expert_toggle(self):
        self.rebuild_module_tab()
        self._rebuild_advanced_tab()

    def _rebuild_advanced_tab(self):
        frame = self.frames.get("advanced")
        if not frame:
            return
        for w in frame.winfo_children():
            w.destroy()
        from gui.tab_advanced import build_tab_advanced
        build_tab_advanced(frame, self)


# ─────────────────────────────────────────────────────────────────────────────
# Tooltip helper (globalny, używany w tab_*)
# ─────────────────────────────────────────────────────────────────────────────

def _bind_tooltip(widget, text):
    tip = [None]
    def show(e):
        x = widget.winfo_rootx() + 20
        y = widget.winfo_rooty() + 20
        tip[0] = tk.Toplevel(widget)
        tip[0].wm_overrideredirect(True)
        tip[0].wm_geometry(f"+{x}+{y}")
        tk.Label(tip[0], text=text, justify="left",
                 bg="#ffffcc", fg="#333333",
                 relief="solid", bd=1,
                 font=("TkDefaultFont", 8), padx=4, pady=2).pack()
    def hide(e):
        if tip[0]:
            tip[0].destroy()
            tip[0] = None
    widget.bind("<Enter>", show)
    widget.bind("<Leave>", hide)


if __name__ == "__main__":
    while True:
        root = tk.Tk(className="glavamasterpanel")
        root.withdraw()
        _conf = load_gui_conf()
        _theme = _conf.get("theme", "forest-dark")
        apply_theme(root, theme=_theme)
        _ensure_shift_style(root)
        app = GlavaGUI(root)
        root.deiconify()
        root.mainloop()
        # mainloop() kończy się po destroy() — sprawdź czy to był restart
        if not getattr(app, "_restart", False):
            break
