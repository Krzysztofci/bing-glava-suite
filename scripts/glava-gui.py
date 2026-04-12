#!/usr/bin/env python3
# =============================================================================
# glava-gui.py
# Szkielet okna GLava Control Center.
# Rozmiar: 600 × 450 px (proporcje 4:3, poziomo).
# Zakładki: Główna (stała) | ✦ Moduł (dynamiczna) | Zaawansowane (stała)
# =============================================================================

import tkinter as tk
from tkinter import ttk
import os
import sys
import datetime
import subprocess

# Dodaj katalog scripts do ścieżki importów
_SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, _SCRIPT_DIR)

from gui.core import (
    load_settings, save_settings, load_lang, available_langs,
    read_active_module, write_active_module,
    GLAVA_MODULES, WALLPAPER, FLAG_RED, FLAG_MANUAL, WALLPAPER_LOCK,
)
from gui.glava import glava_is_running

WIN_W = 632
WIN_H = 474


class GlavaGUI:
    def __init__(self, root):
        self.root = root
        self.settings  = load_settings()
        self.T         = load_lang(self.settings.get("lang", "pl"))
        self.langs     = available_langs()
        self.active_module = read_active_module()

        self._setup_window()
        self._build_titlebar()
        self._build_tabs()
        self._build_statusbar()
        self._schedule_status_update()

    # ─────────────────────────────────────────────────────────────────────────
    # Okno
    # ─────────────────────────────────────────────────────────────────────────

    def _setup_window(self):
        self.root.title(self.T.get("title", "GLava Control Center"))
        self.root.resizable(False, False)
        self.root.geometry(f"{WIN_W}x{WIN_H}")

        # Wycentruj na ekranie
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x  = (sw - WIN_W) // 2
        y  = (sh - WIN_H) // 2
        self.root.geometry(f"{WIN_W}x{WIN_H}+{x}+{y}")

        # Ikona
        icon_path = os.path.join(_SCRIPT_DIR, "icon", "glava-gui.png")
        if os.path.exists(icon_path):
            try:
                img = tk.PhotoImage(file=icon_path)
                self.root.iconphoto(True, img)
                self.root._icon = img   # zapobiegamy GC
            except Exception:
                pass

    # ─────────────────────────────────────────────────────────────────────────
    # Pasek tytułu (tytuł + wybór języka)
    # ─────────────────────────────────────────────────────────────────────────

    def _build_titlebar(self):
        bar = tk.Frame(self.root, pady=4)
        bar.pack(fill="x", padx=8)

        tk.Label(bar, text=self.T.get("title", "GLava Control Center"),
                 font=("Arial", 10, "bold")).pack(side="left")

        # Wybór języka — prawa strona
        lang_frame = tk.Frame(bar)
        lang_frame.pack(side="right")
        tk.Label(lang_frame,
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

        # Pasek zakładek z "Tryb expert" po prawej
        tab_bar = tk.Frame(self.root, bd=0, relief="flat")
        tab_bar.pack(fill="x", padx=0)

        # Tryb expert — checkbox po prawej stronie paska zakładek
        # Przechowujemy jako atrybut instancji żeby plugins mogły go odczytać
        self.expert_mode = tk.BooleanVar(value=False)
        expert_frame = tk.Frame(tab_bar)
        expert_frame.pack(side="right", padx=(0, 8))
        tk.Checkbutton(
            expert_frame,
            text=T.get("label_expert_mode", "Tryb expert"),
            variable=self.expert_mode,
            font=("Arial", 8), fg="#bf360c",
            command=self._on_expert_toggle,
        ).pack(side="left")
        _bind_tooltip(expert_frame,
            T.get("tooltip_expert",
                  "Odblokowuje niestandardowe wartosci Audio\n"
                  "(bufor do 16384, probka do 4096)\n"
                  "Uwaga: bledne wartosci moga zawiesic GLava"))

        # Separator pod paskiem zakładek
        sep = tk.Frame(self.root, height=1, bg="#cccccc")
        sep.pack(fill="x")

        # Kontener na zawartość zakładki — stały rozmiar
        self.tab_content = tk.Frame(self.root)
        self.tab_content.pack(fill="both", expand=True, padx=0, pady=0)

        # Ramki zakładek — tworzymy z wyprzedzeniem
        self.frames = {}
        self._tab_buttons = {}

        tab_defs = [
            ("main",     T.get("tab_main",     "Główna")),
            ("module",   self._module_tab_label()),
            ("advanced", T.get("tab_advanced", "Zaawansowane")),
        ]

        for key, label in tab_defs:
            frame = tk.Frame(self.tab_content)
            frame.place(relwidth=1, relheight=1)
            self.frames[key] = frame

            btn = tk.Button(
                tab_bar, text=label,
                font=("Arial", 9),
                relief="flat", bd=0,
                padx=12, pady=5,
                cursor="hand2",
                command=lambda k=key: self._show_tab(k),
            )
            btn.pack(side="left")
            self._tab_buttons[key] = btn

        # Wypełnij zakładki zawartością
        self._populate_tabs()

        # Pokaż zakładkę Główna
        self._show_tab("main")

    def _module_tab_label(self):
        T = self.T
        name = T.get(f"module_{self.active_module}", self.active_module.capitalize())
        return f"{name} ✦"

    def _show_tab(self, key):
        self._active_tab = key
        self.frames[key].lift()
        self._update_tab_styles()

    def _update_tab_styles(self):
        for key, btn in self._tab_buttons.items():
            if key == self._active_tab:
                btn.config(
                    bg=self.root.cget("bg"),
                    fg="#1565c0",
                    font=("Arial", 9, "bold"),
                    relief="flat",
                )
            elif key == "module":
                btn.config(
                    bg=self.root.cget("bg"),
                    fg="#1565c0",
                    font=("Arial", 9),
                    relief="flat",
                )
            else:
                btn.config(
                    bg=self.root.cget("bg"),
                    fg="gray40",
                    font=("Arial", 9),
                    relief="flat",
                )

    def _refresh_module_tab_label(self):
        """Aktualizuje etykietę zakładki modułu po zmianie active_module."""
        label = self._module_tab_label()
        self._tab_buttons["module"].config(text=label)

    def _populate_tabs(self):
        """Wołane raz przy starcie i po zmianie języka."""
        from gui.tab_main     import build_tab_main
        from gui.tab_module   import build_tab_module
        from gui.tab_advanced import build_tab_advanced

        # Wyczyść stare widgety
        for frame in self.frames.values():
            for w in frame.winfo_children():
                w.destroy()

        build_tab_main(self.frames["main"], self)
        build_tab_module(self.frames["module"], self)
        build_tab_advanced(self.frames["advanced"], self)

    def rebuild_module_tab(self):
        """Przebudowuje tylko zakładkę modułu (po zmianie active_module)."""
        from gui.tab_module import build_tab_module
        for w in self.frames["module"].winfo_children():
            w.destroy()
        build_tab_module(self.frames["module"], self)
        self._refresh_module_tab_label()

    # ─────────────────────────────────────────────────────────────────────────
    # Pasek statusu
    # ─────────────────────────────────────────────────────────────────────────

    def _build_statusbar(self):
        sep = tk.Frame(self.root, height=1, bg="#cccccc")
        sep.pack(fill="x", side="bottom")

        self.status_label = tk.Label(
            self.root,
            text="...",
            font=("Arial", 8, "italic"),
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
        # Przebuduj całe UI
        for w in self.root.winfo_children():
            w.destroy()
        self.__init__(self.root)


# ─────────────────────────────────────────────────────────────────────────────

    def _on_expert_toggle(self):
        """Powiadamia aktywną zakładkę modułu o zmianie trybu expert."""
        # Przebuduj zakładkę modułu żeby zaktualizować zakresy comboboxów
        self.rebuild_module_tab()
        # Przebuduj zakładkę Zaawansowane
        self._rebuild_advanced_tab()

    def _rebuild_advanced_tab(self):
        frame = self.frames.get("advanced")
        if not frame: return
        for w in frame.winfo_children():
            w.destroy()
        from gui.tab_advanced import build_tab_advanced
        build_tab_advanced(frame, self)


def _bind_tooltip(widget, text):
    """Prosty tooltip — wyświetla dymek po najechaniu na widget."""
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
        if tip[0]: tip[0].destroy(); tip[0] = None
    widget.bind("<Enter>", show)
    widget.bind("<Leave>", hide)


if __name__ == "__main__":
    root = tk.Tk()
    GlavaGUI(root)
    root.mainloop()
