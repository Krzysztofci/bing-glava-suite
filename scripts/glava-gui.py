#!/usr/bin/env python3
# =============================================================================
# glava-gui.py
# Szkielet okna GLava Control Center.
# Zakładki: Główna (stała) | ✦ Moduł (dynamiczna) | Zaawansowane (stała)
# =============================================================================
import tkinter as tk
from tkinter import ttk
import os
import sys
import json
import datetime
import subprocess

# Dodaj katalog scripts do ścieżki importów
_SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, _SCRIPT_DIR)

from gui.theme import apply_theme, COLORS, TFrame, TLabel, TSeparator
from gui.core import (
    load_settings, save_settings, load_lang, available_langs,
    read_active_module, write_active_module,
    GLAVA_MODULES, WALLPAPER, FLAG_RED, FLAG_MANUAL, WALLPAPER_LOCK,
    CONFIG_DIR,
)
from gui.glava import glava_is_running

# Domyślne wymiary okna
WIN_W_DEFAULT = 650
WIN_H_DEFAULT = 500
WIN_W_MIN     = 500
WIN_H_MIN     = 400

GUI_CONF = os.path.join(CONFIG_DIR, "gui.conf")


# ─────────────────────────────────────────────────────────────────────────────
# Zapis / odczyt gui.conf
# ─────────────────────────────────────────────────────────────────────────────

def load_gui_conf():
    """Wczytuje gui.conf. Przy pierwszym uruchomieniu tworzy plik z wartościami domyślnymi."""
    defaults = {
        "width":  WIN_W_DEFAULT,
        "height": WIN_H_DEFAULT,
        "x":      None,
        "y":      None,
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
        # Pierwsze uruchomienie — zapisz domyślny plik
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
        self.root = root
        self.settings      = load_settings()
        self.T             = load_lang(self.settings.get("lang", "pl"))
        self.langs         = available_langs()
        self.active_module = read_active_module()
        self.gui_conf      = load_gui_conf()

        self._setup_window()
        self._build_titlebar()
        self._build_tabs()
        self._build_statusbar()
        self._schedule_status_update()

        # Zapisz rozmiar i pozycję przy zamknięciu okna
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        # Zapisz też przy każdej zmianie rozmiaru (z debouncingiem)
        self._resize_after = None
        self.root.bind("<Configure>", self._on_configure)

    # ─────────────────────────────────────────────────────────────────────────
    # Okno
    # ─────────────────────────────────────────────────────────────────────────

    def _setup_window(self):
        self.root.title(self.T.get("title", "GLava Control Center"))
        self.root.resizable(True, True)
        self.root.minsize(WIN_W_MIN, WIN_H_MIN)

        # Wczytaj zapisany rozmiar
        w = self.gui_conf.get("width",  WIN_W_DEFAULT)
        h = self.gui_conf.get("height", WIN_H_DEFAULT)
        x = self.gui_conf.get("x")
        y = self.gui_conf.get("y")

        # Upewnij się że minimalne wymiary są zachowane
        w = max(w, WIN_W_MIN)
        h = max(h, WIN_H_MIN)

        self.root.update_idletasks()

        if x is not None and y is not None:
            # Sprawdź czy pozycja jest w granicach ekranu
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            x = max(0, min(x, sw - w))
            y = max(0, min(y, sh - h))
            self.root.geometry(f"{w}x{h}+{x}+{y}")
        else:
            # Wycentruj na ekranie
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            x  = (sw - w) // 2
            y  = (sh - h) // 2
            self.root.geometry(f"{w}x{h}+{x}+{y}")

        # Ikona
        icon_path = os.path.join(_SCRIPT_DIR, "icon", "glava-gui.png")
        if os.path.exists(icon_path):
            try:
                img = tk.PhotoImage(file=icon_path)
                self.root.iconphoto(True, img)
                self.root._icon = img
            except Exception:
                pass

    # ─────────────────────────────────────────────────────────────────────────
    # Obsługa zmiany rozmiaru i zamknięcia
    # ─────────────────────────────────────────────────────────────────────────

    def _on_configure(self, event=None):
        """Debounced zapis przy każdej zmianie rozmiaru/pozycji okna."""
        if self._resize_after:
            self.root.after_cancel(self._resize_after)
        self._resize_after = self.root.after(500, self._save_window_state)

    def _save_window_state(self):
        """Zapisuje aktualny rozmiar i pozycję do gui.conf."""
        try:
            geo = self.root.geometry()  # "WxH+X+Y"
            w = self.root.winfo_width()
            h = self.root.winfo_height()
            x = self.root.winfo_x()
            y = self.root.winfo_y()
            self.gui_conf.update({"width": w, "height": h, "x": x, "y": y})
            save_gui_conf(self.gui_conf)
        except Exception:
            pass

    def _on_close(self):
        """Zapisuje stan okna i zamyka aplikację."""
        self._save_window_state()
        self.root.destroy()

    # ─────────────────────────────────────────────────────────────────────────
    # Pasek tytułu (tytuł + wybór języka)
    # ─────────────────────────────────────────────────────────────────────────

    # Linia 173 to definicja:
    def _build_titlebar(self):
        # Ta linia (175) MUSI mieć wcięcie (4 spacje):
        bar = TFrame(self.root, level=0, pady=4)
        bar.pack(fill="x", padx=8)
        
        TLabel(bar, text=self.T.get("title", "GLava Control Center"),
               font=("Arial", 10, "bold")).pack(side="left")

        lang_frame = TFrame(bar, level=0)
        lang_frame.pack(side="right")
        
        TLabel(lang_frame, 
               text=self.T.get("section_language", "Język") + ":",
               font=("Arial", 9)).pack(side="left", padx=(0, 4))
        
        self.lang_var = tk.StringVar(value=self.settings.get("lang", "pl"))
        lang_cb = ttk.Combobox(lang_frame, textvariable=self.lang_var,
                               values=list(self.langs.keys()),
                               width=5, state="readonly")
        lang_cb.pack(side="left")
        lang_cb.bind("<<ComboboxSelected>>", self._on_lang_change)
    # ─────────────────────────────────────────────────────────────────────────
    # Zakładki
    # ─────────────────────────────────────────────────────────────────────────

    def _build_tabs(self):
        T = self.T

        # Pasek pod przyciski zakładek (ciemne tło bg0)
        tab_bar = TFrame(self.root, level=0)
        tab_bar.pack(fill="x", padx=0)

        self.expert_mode = tk.BooleanVar(value=False)
        expert_frame = TFrame(tab_bar, level=0)
        expert_frame.pack(side="right", padx=(0, 8))
        
        tk.Checkbutton(
            expert_frame,
            text=T.get("label_expert_mode", "Tryb expert"),
            variable=self.expert_mode,
            font=("Arial", 8), fg="#bf360c",
            bg=COLORS["bg0"],
            activebackground=COLORS["bg0"],
            selectcolor=COLORS["bg0"],
            command=self._on_expert_toggle,
        ).pack(side="left")

        TSeparator(self.root).pack(fill="x")

        self.tab_content = TFrame(self.root, level=1)
        self.tab_content.pack(fill="both", expand=True, padx=0, pady=0)

        self.frames = {}
        self._tab_buttons = {}

        # --- TUTAJ BYŁ BRAKUJĄCY ELEMENT ---
        tab_defs = [
            ("main",     T.get("tab_main",     "Główna")),
            ("module",   self._module_tab_label()),
            ("advanced", T.get("tab_advanced", "Zaawansowane")),
        ]
        # ------------------------------------
        for key, label in tab_defs:
            # Tworzymy ciemną bazę dla każdej zakładki
            # highlightthickness=0 usuwa białe obwódki focusa
            frame = tk.Frame(self.tab_content, 
                             bg=COLORS["bg1"], 
                             highlightthickness=0, 
                             bd=0)
            frame.place(relwidth=1, relheight=1)
            self.frames[key] = frame
            
            # Przycisk na pasku zakładek
            btn = tk.Button(
                tab_bar, text=label,
                font=("Arial", 9),
                bg=COLORS["bg0"],
                fg=COLORS["text2"],
                activebackground=COLORS["bg1"],
                activeforeground=COLORS["text"],
                relief="flat", bd=0,
                padx=12, pady=5,
                cursor="hand2",
                command=lambda k=key: self._show_tab(k),
            )
            btn.pack(side="left")
            self._tab_buttons[key] = btn

        # KLUCZOWE: Najpierw stworzyliśmy puste ciemne ramki, 
        # teraz wypełniamy je treścią (suwakami itd.)
        self._populate_tabs() 
        self._show_tab("main")

    def _module_tab_label(self):
        T = self.T
        name = T.get(f"module_{self.active_module}", self.active_module.capitalize())
        return f"{name} ✦"

    def _show_tab(self, key):
        self._active_tab = key
        self.frames[key].lift()
        self._update_tab_styles()
        if key == "main" and hasattr(self, "_tab_main_ref"):
            self._tab_main_ref.refresh_geometry()

    def _update_tab_styles(self):
        from gui.theme import COLORS
        for key, btn in self._tab_buttons.items():
            if key == self._active_tab:
                btn.config(
                    bg=COLORS["red_dim"], # Aktywna zakładka na czerwono
                    fg=COLORS["text"],
                    font=("Arial", 9, "bold")
                )
            else:
                btn.config(
                    bg=COLORS["bg1"],
                    fg=COLORS["text2"],
                    font=("Arial", 9)
                )

    def _refresh_module_tab_label(self):
        label = self._module_tab_label()
        self._tab_buttons["module"].config(text=label)

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
        from gui.theme import COLORS, TSeparator
        TSeparator(self.root).pack(fill="x", side="bottom")
        
        self.status_label = tk.Label(
            self.root,
            text="...",
            font=("Arial", 8, "italic"),
            bg=COLORS["bg0"], # Tło statusu
            anchor="w",
            pady=3,
        )
        self.status_label.pack(fill="x", side="bottom", padx=8)

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
            color  = "#2e7d32"
        else:
            status = f"○ {T.get('status_inactive', 'GLava wyłączona')}"
            color  = "#b71c1c"

        if os.path.exists(WALLPAPER):
            dt = datetime.datetime.fromtimestamp(
                os.path.getmtime(WALLPAPER)
            ).strftime("%d %b %Y %H:%M")
            status += f"   |   {T.get('label_wallpaper', 'Tapeta')}: {dt}"
        else:
            status += f"   |   {T.get('label_no_wallpaper', 'brak tapety')}"

        if os.path.exists(WALLPAPER_LOCK):
            status += f"   |   🔒 {T.get('label_wallpaper_locked', 'zablokowana')}"

        self.status_label.config(text=status, fg=color)

    # ─────────────────────────────────────────────────────────────────────────
    # Zmiana języka
    # ─────────────────────────────────────────────────────────────────────────

    def _on_lang_change(self, event=None):
        lang = self.lang_var.get()
        self.settings["lang"] = lang
        save_settings(self.settings)
        self.T = load_lang(lang)
        for w in self.root.winfo_children():
            w.destroy()
        self.__init__(self.root)

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
# Tooltip
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
                 bg="#ffffcc", relief="solid", bd=1,
                 font=("Arial", 8), padx=4, pady=2).pack()
    def hide(e):
        if tip[0]:
            tip[0].destroy()
            tip[0] = None
    widget.bind("<Enter>", show)
    widget.bind("<Leave>", hide)


if __name__ == "__main__":
    root = tk.Tk(className='glavamasterpanel')
    apply_theme(root)
    app = GlavaGUI(root)
    root.mainloop()
