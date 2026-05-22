#!/usr/bin/env python3
# =============================================================================
# glava-gui.py
# GLava Control Center — główne okno aplikacji.
#
# Architektura multiinstancji:
#   self.instances  : dict[inst_id, GlavaInstance]
#   self.processes  : dict[inst_id, subprocess.Popen | None]
#   self._inst_tabs : dict[inst_id, TabModule]   — jeden obiekt per zakładka
#
# Każda instancja GLava ma własny XDG_CONFIG_HOME (→ GlavaInstance.xdg_dir).
# Zamknięcie zakładki zatrzymuje TYLKO jej Popen, usuwa katalog konfiguracyjny
# i wyrejestrowuje instancję. Instancja 0 jest domyślna i nieusuwalna.
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
import re
import subprocess

_SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, _SCRIPT_DIR)

from gui.theme   import apply_theme, COLORS, TFrame, TLabel, TSeparator, get_theme_names
from gui.widgets import _ensure_shift_style
from gui.core    import (
    load_settings, save_settings, load_lang, available_langs,
    read_active_module, write_active_module,
    GLAVA_MODULES, WALLPAPER, FLAG_RED, FLAG_MANUAL, WALLPAPER_LOCK,
    CONFIG_DIR,
)
from gui.glava   import (
    glava_is_running, glava_start,
    glava_stop_instance, glava_restart_instance, glava_stop_all,
    adopt_instance, write_pid, clear_pid, read_pid, is_pid_running,
    read_rc_module,
)
from gui.instance import (
    GlavaInstance, next_inst_id,
    register_instance, unregister_instance, update_instance,
)
from gui.instance_tab_bar import InstanceTabBar

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
        self.root     = root
        self.settings = load_settings()
        self.T        = load_lang(self.settings.get("lang", "pl"))
        self.langs    = available_langs()

        self.active_module = read_active_module()
        self.gui_conf      = load_gui_conf()

        # ── Rejestr instancji ──────────────────────────────────────────────
        # instances[inst_id]  = GlavaInstance
        # processes[inst_id]  = Popen | None
        # _inst_modules[iid]  = ostatni uruchomiony moduł (str)
        self.instances:     dict = {}
        self.processes:     dict = {}
        self._inst_modules: dict = {}
        self._active_inst_id: int | None = None

        self._load_saved_instances()

        # active_instance — wskazuje na instancję w aktywnej zakładce
        first_id = next(iter(self.instances), None)
        self._active_inst_id = first_id
        self.active_instance = self.instances[first_id] if first_id is not None else None

        self._setup_window()
        self._build_header()
        self._build_notebook()
        self._build_statusbar()
        self._schedule_status_update()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._resize_after = None
        self.root.bind("<Configure>", self._on_configure)

    # ─────────────────────────────────────────────────────────────────────────
    # Wczytanie zapisanych instancji z instances.json
    # ─────────────────────────────────────────────────────────────────────────

    def _load_saved_instances(self):
        """
        Wczytuje rejestr instancji z instances.json i odtwarza sesję.
        Instancje, których katalog nie istnieje, są pomijane (sprzątanie).
        """
        from gui.instance import load_instances, save_instances

        saved   = load_instances()
        cleaned = []

        for entry in saved:
            iid  = entry["inst_id"]
            inst = GlavaInstance(iid)

            if not inst.exists():
                continue    # katalog zniknął — pomijamy, sprzątamy rejestr

            rc_module   = read_rc_module(inst.rc_glsl)
            json_module = entry.get("module")
            module      = rc_module or json_module or GLAVA_MODULES[0]

            entry["module"] = module
            self.instances[iid]     = inst
            self._inst_modules[iid] = module

            _pid, adopted_proc = adopt_instance(iid)
            if adopted_proc is not None:
                self.processes[iid] = adopted_proc
            else:
                self.processes[iid] = None

            cleaned.append(entry)

        save_instances(cleaned)

#    def _load_saved_instances(self):
#        """
#        Wczytuje rejestr instancji z instances.json i odtwarza
#        self.instances / self.processes / self._inst_modules.
#        Instancje, których katalog konfiguracyjny nie istnieje, są pomijane
#        i usuwane z rejestru (sprzątanie po nieprawidłowym zamknięciu).
#        """
#        from gui.instance import load_instances, save_instances
#
#        saved   = load_instances()          # [{inst_id, name, module, active}, ...]
#        cleaned = []
#
#        for entry in saved:
#            iid    = entry["inst_id"]
#            inst   = GlavaInstance(iid)
#
#            # inst_id=0 zawsze jest ważna (domyślny ~/.config/glava)
#            if iid != 0 and not inst.exists():
#                continue    # katalog zniknął — pomijamy, nie dodajemy do cleaned
#
#            # Zrodlo prawdy: rc.glsl instancji
#            # Fallback 1: instances.json
#            # Fallback 2: aktywny modul globalny (tylko dla inst 0)
#            # NIGDY nie uzywamy hardkodowanego "bars"
#            rc_module  = read_rc_module(inst.rc_glsl)
#            json_module = entry.get("module")
#            if rc_module:
#                module = rc_module
#            elif json_module and json_module in GLAVA_MODULES:
#                module = json_module
#            elif iid == 0:
#                module = read_active_module() or GLAVA_MODULES[0]
#            else:
#                module = GLAVA_MODULES[0]
#            entry["module"] = module   # zaktualizuj wpis do zapisu
#
#            self.instances[iid]     = inst
#            self._inst_modules[iid] = module
#
#            # Sprobuj adoptowac istniejacy proces (z autostartu lub poprzedniej sesji)
#            _pid, adopted_proc = adopt_instance(iid)
#            if adopted_proc is not None:
#                self.processes[iid] = adopted_proc
#            else:
#                self.processes[iid] = None
#
#            cleaned.append(entry)
#
#        # Upewnij się że inst 0 zawsze jest
#        if 0 not in self.instances:
#            inst0 = GlavaInstance(0)
#            self.instances[0]     = inst0
#            self.processes[0]     = None
#            self._inst_modules[0] = self.active_module
#            cleaned.insert(0, {"inst_id": 0, "name": "Default",
#                                "module": self.active_module, "active": True})
#
#        # Zapisz oczyszczony rejestr (usuwa instancje bez katalogu)
#        save_instances(cleaned)

    # ─────────────────────────────────────────────────────────────────────────
    # Okno
    # ─────────────────────────────────────────────────────────────────────────

    def _setup_window(self):
        self.root.withdraw()
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

        ttk.Label(
            header,
            text=T.get("title", "GLava Control Center"),
            font=("TkDefaultFont", 12, "bold"),
        ).pack(side="left")

        right = ttk.Frame(header)
        right.pack(side="right")

        from gui.core import GLAVA_DISABLE_FLAG
        self.glava_enabled_var = tk.BooleanVar(
            value=not os.path.exists(GLAVA_DISABLE_FLAG)
        )
        ttk.Checkbutton(
            right,
            text=T.get("label_glava_enabled", "GLava"),
            variable=self.glava_enabled_var,
            style="Switch",
            command=self._on_glava_toggle,
        ).pack(side="right", padx=(10, 0))

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
    # Główny obszar: InstanceTabBar + panele Main / Advanced / Module
    # ─────────────────────────────────────────────────────────────────────────

    def _build_notebook(self):
        T     = self.T
        style = ttk.Style()

        outer = ttk.Frame(self.root)
        outer.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.main_border = ttk.Frame(outer, style="Card")
        self.main_border.pack(fill="both", expand=True)

        # ── Pasek nawigacji ────────────────────────────────────────────────
        top_bar = ttk.Frame(self.main_border, padding=(2, 0, 2, 0))
        top_bar.pack(side="top", fill="x")

        style.configure("Nav.Toolbutton", padding=[4, 0], font=("TkDefaultFont", 9))

        self._btn_main = ttk.Button(
            top_bar, text=T.get("tab_main", "Main"),
            style="Nav.Toolbutton", command=self._show_main,
        )
        self._btn_main.pack(side="left", pady=(2, 0))

        self._btn_advanced = ttk.Button(
            top_bar, text=T.get("tab_advanced", "Advanced"),
            style="Nav.Toolbutton", command=self._show_advanced,
        )
        self._btn_advanced.pack(side="right", pady=(2, 0))

        self.inst_bar = InstanceTabBar(
            top_bar,
            on_select=self._on_inst_select,
            on_add=self._on_inst_add,
            on_close=self._on_inst_close,
            on_action=self._on_inst_action,
            content_parent=self.main_border,
        )
        self.inst_bar.pack(side="left", fill="x", expand=True)

        # ── Separator ──────────────────────────────────────────────────────
        sep_color = style.lookup("TSeparator", "background") or "#454545"
        tk.Frame(self.main_border, height=1, bg=sep_color).pack(fill="x", side="top")

        # ── Panele statyczne (Main, Advanced) ─────────────────────────────
        self._frame_main     = ttk.Frame(self.main_border, padding=(4, 4))
        self._frame_advanced = ttk.Frame(self.main_border, padding=(4, 4))

        # ── Odtwarzaj zakładki z rejestru instancji ─────────────────────────
        from gui.instance import load_instances
        saved_order = load_instances()   # zachowuje kolejność z pliku

        labels_to_save = []  # (iid, label) do synchronizacji po zbudowaniu tab bar

        for entry in saved_order:
            iid    = entry["inst_id"]
            # Uzyj modulu z self._inst_modules (zsynchronizowanego z rc.glsl)
            # NIE z instances.json ktory moze byc nieaktualny
            module = self._inst_modules.get(iid, entry.get("module", "bars"))
            name   = entry.get("name")
            if iid not in self.instances:
                continue

            # Jeśli name wygląda jak autogenerowana ("Default", "Instance N")
            # lub jest None — pozwólmy add_tab wygenerować świeżą etykietę.
            # Nazwy nadane ręcznie przez użytkownika (rename) są zachowywane.
            import re as _re
            is_auto = (name is None
                       or name == "Default"
                       or bool(_re.fullmatch(r'Instance \d+', name)))
            label_to_pass = None if is_auto else name

            # Wybierz zakladke oznaczona jako active w instances.json
            # Fallback na iid==0 jesli zadna nie ma active=True
            _any_active = any(e.get("active") for e in saved_order)
            should_select = (bool(entry.get("active")) or
                             (iid == 0 and not _any_active))
            self.inst_bar.add_tab(iid, module=module, label=label_to_pass,
                                  select=should_select)

            # Zbierz faktyczną etykietę (autogenerowane zapisz z powrotem)
            if is_auto:
                labels_to_save.append(iid)

        # Synchronizuj autogenerowane etykiety do rejestru
        for iid in labels_to_save:
            actual = self.inst_bar._tabs.get(iid, {}).get("label")
            if actual:
                try:
                    update_instance(iid, name=actual)
                except Exception:
                    pass

        # ── Zbuduj panele statyczne ────────────────────────────────────────
        self._populate_static_tabs()

        # ── Aktywny panel — domyslnie Main po pelnym renderze
        self._active_panel = "instances"
        self.root.after(50, self._show_main)
        self._sync_processes_from_pids()

    def _sync_processes_from_pids(self):
        """Synchronizuje self.processes z plikami PID — daemon mógł zmienić procesy."""
        from gui.glava import adopt_instance, read_pid
        for iid in list(self.instances.keys()):
            current = self.processes.get(iid)
            file_pid = read_pid(iid)

            # Sprawdź czy aktualny proc zgadza się z PID w pliku
            if current is not None:
                current_pid = getattr(current, 'pid', None)
                if current.poll() is not None:
                    # Proces martwy
                    self.processes[iid] = None
                    current = None
                elif file_pid is not None and current_pid != file_pid:
                    # Daemon zmienił proces — adoptuj nowy
                    self.processes[iid] = None
                    current = None

            # Jeśli brak proc — spróbuj adoptować z PID pliku
            if current is None:
                _pid, proc = adopt_instance(iid)
                if proc is not None:
                    self.processes[iid] = proc

        # Powtarzaj co 3 sekundy
        self.root.after(3000, self._sync_processes_from_pids)
    

    # ─────────────────────────────────────────────────────────────────────────
    # Budowanie zawartości zakładki instancji
    # ─────────────────────────────────────────────────────────────────────────

    def _build_inst_frame(self, inst_id):
        """
        Buduje (lub odbudowuje) zawartość zakładki instancji inst_id.
        TabModule jest tworzony z właściwą instancją ustawioną jako active_instance.
        """
        from gui.tab_module import build_tab_module

        frame = self.inst_bar.get_frame(inst_id)
        if frame is None:
            return

        # Usuń poprzednią zawartość
        for w in frame.winfo_children():
            w.destroy()

        # Ustaw active_instance na czas budowania zakładki
        prev_inst    = self.active_instance
        prev_mod     = self.active_module
        self.active_instance = self.instances[inst_id]
        self.active_module   = self._inst_modules.get(inst_id, self.active_module)

        build_tab_module(frame, self)

        self.active_instance = prev_inst
        self.active_module   = prev_mod

    # ─────────────────────────────────────────────────────────────────────────
    # Panele statyczne (Main, Advanced)
    # ─────────────────────────────────────────────────────────────────────────

    def _populate_static_tabs(self):
        from gui.tab_main     import build_tab_main
        from gui.tab_advanced import build_tab_advanced
        build_tab_main(self._frame_main, self)
        build_tab_advanced(self._frame_advanced, self)

    # ─────────────────────────────────────────────────────────────────────────
    # Przełączanie widoków
    # ─────────────────────────────────────────────────────────────────────────

    def _show_main(self):
        self._frame_advanced.pack_forget()
        self.inst_bar._content_frame.pack_forget()
        self._frame_main.pack(fill="both", expand=True)
        self._active_panel = "main"
        # Odśwież geometrię w panelu Main — czyta z rc.glsl aktywnej instancji
        if hasattr(self, "_tab_main_ref"):
            self._tab_main_ref.refresh_geometry()

    def _show_advanced(self):
        self._frame_main.pack_forget()
        self.inst_bar._content_frame.pack_forget()
        self._frame_advanced.pack(fill="both", expand=True)
        self._active_panel = "advanced"

    def _show_instances(self):
        self._frame_main.pack_forget()
        self._frame_advanced.pack_forget()
        self.inst_bar._content_frame.pack(fill="both", expand=True)
        self._active_panel = "instances"

    # ─────────────────────────────────────────────────────────────────────────
    # Callbacki InstanceTabBar
    # ─────────────────────────────────────────────────────────────────────────

    def _on_inst_select(self, inst_id):
        """Użytkownik kliknął zakładkę instancji."""
        self._active_inst_id = inst_id
        self.active_instance = self.instances.get(inst_id)
        self.active_module   = self._inst_modules.get(inst_id, self.active_module)
        self._show_instances()
        # Zbuduj zawartość zakładki jeśli pusta (lazy init)
        frame = self.inst_bar.get_frame(inst_id)
        if frame is not None and not frame.winfo_children():
            self._build_inst_frame(inst_id)
        # Odśwież UI tab_main dla nowej aktywnej instancji
        if hasattr(self, "_tab_main_ref"):
            self._tab_main_ref.refresh_active_instance()

    def _on_inst_add(self, module_name, source_inst=None):
        """
        Tworzy nową instancję.
        source_inst — GlavaInstance źródłowa (duplikowanie); None = szablon.
        """
        iid  = next_inst_id()
        inst = GlavaInstance(iid)
        inst.create(source=source_inst)
        register_instance(iid, module=module_name)

        self.instances[iid]     = inst
        self.processes[iid]     = None
        self._inst_modules[iid] = module_name

        self.inst_bar.add_tab(iid, module=module_name, select=True)
        self._build_inst_frame(iid)

        # Synchronizuj faktyczną etykietę (wygenerowaną przez add_tab) do rejestru
        actual_label = self.inst_bar._tabs.get(iid, {}).get("label")
        if actual_label:
            try:
                update_instance(iid, name=actual_label)
            except Exception:
                pass

        # Uruchom GLava dla nowej instancji
        def _after_start(proc):
            self.processes[iid] = proc
            self.root.after(0, self.update_status)

        glava_restart_instance(
            instance=inst,
            module=module_name,
            proc=self.processes.get(iid),
            after_fn=_after_start,
        )

    def _on_inst_close(self, inst_id):
        """
        Zamknięcie zakładki:
        - zatrzymuje TYLKO proces tej instancji
        - usuwa katalog konfiguracyjny instancji
        - wyrejestrowuje z instances.json
        """
        # Zatrzymaj tylko ten proces i usun jego PID
        proc = self.processes.pop(inst_id, None)
        glava_stop_instance(proc)
        clear_pid(inst_id)

        # Usuń zakładkę z UI
        self.inst_bar.remove_tab(inst_id)

        # Usuń z rejestrów
        inst = self.instances.pop(inst_id, None)
        self._inst_modules.pop(inst_id, None)

        # Usuń katalog konfiguracyjny instancji
        if inst is not None:
            try:
                inst.destroy()
            except Exception:
                pass

        # Wyrejestruj z instances.json
        try:
            unregister_instance(inst_id)
        except Exception:
            pass

        # Ustaw aktywną na pierwszą pozostałą (lub None jeśli brak)
        if self._active_inst_id == inst_id:
            first_id = next(iter(self.instances), None)
            self._active_inst_id = first_id
            self.active_instance = self.instances[first_id] if first_id is not None else None
            self.active_module   = self._inst_modules.get(first_id, read_active_module()) if first_id is not None else None

        self.update_status()

    def _on_inst_action(self, inst_id, action, *args):
        """Menu kontekstowe zakładki."""
        if action == "duplicate":
            module = self._inst_modules.get(inst_id, self.active_module)
            source_inst = self.instances.get(inst_id)
            self._on_inst_add(module, source_inst=source_inst)
        elif action == "rename":
            # InstanceTabBar już pokazał dialog i zmienił etykietę w UI.
            # Synchronizujemy nową nazwę do instances.json.
            new_label = self.inst_bar._tabs.get(inst_id, {}).get("label")
            if new_label:
                try:
                    update_instance(inst_id, name=new_label)
                except Exception:
                    pass
        elif action == "change_shader":
            module = args[0] if args else self._inst_modules.get(inst_id, self.active_module)
            self._inst_modules[inst_id] = module
            try:
                update_instance(inst_id, module=module)
            except Exception:
                pass
            inst = self.instances.get(inst_id)
            if inst is None:
                return
            proc = self.processes.get(inst_id)
            def _after(new_proc, _iid=inst_id):
                self.processes[_iid] = new_proc
                self.root.after(0, self.update_status)
            glava_restart_instance(
                instance=inst,
                module=module,
                proc=proc,
                after_fn=_after,
            )
            # Odbuduj zakładkę jeśli to aktywna instancja
            if inst_id == self._active_inst_id:
                self.active_module = module
                self.rebuild_module_tab()

    # ─────────────────────────────────────────────────────────────────────────
    # API dla tab_main / tab_module — operują na active_instance
    # ─────────────────────────────────────────────────────────────────────────

    def restart_active_instance(self, module=None, after_fn=None):
        """
        Restartuje proces GLava aktywnej instancji.
        Używane przez tab_main i tab_module zamiast globalnego glava_restart().
        Debounce 300ms — wielokrotne wywołania scalają się w jedno.
        """
        iid    = self._active_inst_id
        inst   = self.active_instance
        module = module or self._inst_modules.get(iid, self.active_module)

        self._inst_modules[iid] = module
        try:
            update_instance(iid, module=module)
        except Exception:
            pass

        # Anuluj poprzednie oczekujące wywołanie
        if not hasattr(self, "_restart_after"):
            self._restart_after = {}
        if iid in self._restart_after and self._restart_after[iid]:
            try:
                self.root.after_cancel(self._restart_after[iid])
            except Exception:
                pass
            self._restart_after[iid] = None

        def _do_restart():
            self._restart_after[iid] = None
            old_proc = self.processes.get(iid)
            self.processes[iid] = None

            def _after(proc, _iid=iid, _fn=after_fn):
                self.processes[_iid] = proc
                self.root.after(0, self.update_status)
                if _fn:
                    self.root.after(0, _fn)

            glava_restart_instance(
                instance=inst,
                module=module,
                proc=old_proc,
                after_fn=_after,
            )

        self._restart_after[iid] = self.root.after(300, _do_restart)

    def get_active_rc_glsl(self):
        """Zwraca ścieżkę rc.glsl aktywnej instancji (używane przez tab_main)."""
        if self.active_instance is None:
            return None
        return self.active_instance.rc_glsl

    def get_active_glava_dir(self):
        """Zwraca katalog glava aktywnej instancji."""
        if self.active_instance is None:
            return None
        return self.active_instance.glava_dir

    # ─────────────────────────────────────────────────────────────────────────
    # Kompatybilność wsteczna (tab_main, tab_module, tab_advanced używają tych)
    # ─────────────────────────────────────────────────────────────────────────

    def _module_tab_label(self):
        name = self.T.get(f"module_{self.active_module}", self.active_module.capitalize())
        return f"{name} ✦"

    def _on_tab_changed(self, event=None):
        pass  # zastąpione przez _on_inst_select

    def _show_tab(self, key):
        if key == "main":
            self._show_main()
        elif key == "advanced":
            self._show_advanced()
        else:
            self._show_instances()

    def _refresh_module_tab_label(self):
        iid  = self._active_inst_id
        mod  = self._inst_modules.get(iid, self.active_module)
        name = self.T.get(f"module_{mod}", mod.capitalize())
        self.inst_bar.set_label(iid, f"{name} ✦")

    def _populate_tabs(self):
        """Kompatybilność wsteczna."""
        self._populate_static_tabs()

    def rebuild_module_tab(self):
        """Przebudowuje zakładkę aktywnej instancji (po zmianie modułu)."""
        self._build_inst_frame(self._active_inst_id)
        self._refresh_module_tab_label()

    @property
    def frames(self):
        """Kompatybilność wsteczna dla tab_main/tab_advanced."""
        return {
            "main":     self._frame_main,
            "advanced": self._frame_advanced,
        }

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
        T       = self.T
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
        save_gui_conf(self.gui_conf)

    def _on_configure(self, event=None):
        if self._resize_after:
            self.root.after_cancel(self._resize_after)
        self._resize_after = self.root.after(500, self._save_window_state)

    def _save_window_state(self):
        try:
            geo = self.root.geometry()
            m = re.match(r'(\d+)x(\d+)\+(-?\d+)\+(-?\d+)', geo)
            if m:
                w, h, x, y = int(m[1]), int(m[2]), int(m[3]), int(m[4])
                self.gui_conf.update({"width": w, "height": h, "x": x, "y": y})
                save_gui_conf(self.gui_conf)
        except Exception:
            pass

    def _on_close(self):
        self._save_window_state()
        self._save_active_instance()
        for after_id in str(self.root.tk.call("after", "info")).split():
            try: self.root.after_cancel(after_id)
            except: pass
        self.root.destroy()

    def _save_active_instance(self):
        """Zapisuje aktywną instancję do instances.json (pole active=True).
        Jeśli brak aktywnej (None), wszystkie wpisy dostają active=False."""
        try:
            from gui.instance import load_instances, save_instances
            instances = load_instances()
            active_iid = self._active_inst_id  # może być None
            for entry in instances:
                entry["active"] = (active_iid is not None and
                                   entry["inst_id"] == active_iid)
            save_instances(instances)
        except Exception:
            pass
    # ─────────────────────────────────────────────────────────────────────────
    # Zmiana języka / tryb expert
    # ─────────────────────────────────────────────────────────────────────────

    def _on_lang_change(self, event=None):
        lang = self.lang_var.get()
        self.settings["lang"] = lang
        save_settings(self.settings)
        self._restart = True
        if self._resize_after:
            self.root.after_cancel(self._resize_after)
            self._resize_after = None
        self._save_window_state()
        self.root.destroy()

    def _on_expert_toggle(self):
        self.rebuild_module_tab()
        self._rebuild_advanced_tab()

    def _on_glava_toggle(self):
        """Włącza/wyłącza wszystkie instancje GLava bez zamykania zakładek."""
        from gui.core import GLAVA_DISABLE_FLAG
        from gui.glava import glava_stop_instance, glava_restart_instance
        enabled = self.glava_enabled_var.get()
        if enabled:
            # Usuń flagę i uruchom wszystkie instancje
            try:
                os.remove(GLAVA_DISABLE_FLAG)
            except FileNotFoundError:
                pass
            for iid, inst in self.instances.items():
                module = self._inst_modules.get(iid, self.active_module)
                proc   = self.processes.get(iid)
                self.processes[iid] = None
                def _after(new_proc, _iid=iid):
                    self.processes[_iid] = new_proc
                    self.root.after(0, self.update_status)
                glava_restart_instance(instance=inst, module=module,
                                       proc=proc, after_fn=_after)
        else:
            # Postaw flagę i zatrzymaj wszystkie instancje
            os.makedirs(os.path.dirname(GLAVA_DISABLE_FLAG), exist_ok=True)
            open(GLAVA_DISABLE_FLAG, "w").close()
            for iid in list(self.processes.keys()):
                proc = self.processes.pop(iid, None)
                glava_stop_instance(proc)
                clear_pid(iid)
            # Dodatkowo pkill na wypadek procesów poza kontrolą GUI
            import subprocess as _sp
            _sp.run(["pkill", "-x", "glava"], capture_output=True)
            self.root.after(500, self.update_status)

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


# ─────────────────────────────────────────────────────────────────────────────
# Punkt wejścia
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    while True:
        root = tk.Tk(className="glavamasterpanel")
        root.withdraw()
        _conf  = load_gui_conf()
        _theme = _conf.get("theme", "forest-dark")
        apply_theme(root, theme=_theme)
        _ensure_shift_style(root)
        app = GlavaGUI(root)
        root.deiconify()
        root.mainloop()
        if not getattr(app, "_restart", False):
            break
