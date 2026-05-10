# =============================================================================
# gui/modules/base.py
# Klasa bazowa dla wszystkich *ParamWidget.
# Zawiera boilerplate: __init__, build(), _schedule_restart, _apply_profile,
# _save_profile, _delete_profile, _refresh_cb, _expert.
# =============================================================================

import tkinter as tk
import tkinter.ttk as ttk
from tkinter import messagebox, simpledialog
import os

from ..core import (
    get_shader_profiles_for_module,
    save_shader_profile_for_module,
    delete_shader_profile_for_module,
    GLAVA_DIR, RC_GLSL, SMOOTH_PARAMS,
)

from . import glsl_io
RESTART_DELAY_MS = 300


class BaseParamWidget:
    """
    Klasa bazowa dla BarsParamWidget, CircleParamWidget itd.

    Podklasa MUSI zdefiniować:
        MODULE_NAME: str       — np. "bars", "circle"
        build_left(left, current)
        build_right(right, current)

    Podklasa MOŻE nadpisać:
        _init_extra()          — dodatkowa inicjalizacja (screen info itp.)
        _reset_shader(self)
    """

    MODULE_NAME: str = ""

    def __init__(self, parent, app, T):
        self.parent = parent
        self.app    = app
        self.T      = T
        self.vars   = {}
        self._init_extra()

    def _init_extra(self):
        """Hook dla podklas — dodatkowa inicjalizacja w __init__."""
        pass

    # ── Szkielet UI ───────────────────────────────────────────────────────────

    def build(self):
        import importlib
        mod = importlib.import_module(f"gui.modules.{self.MODULE_NAME}")
        current = mod.collect_params(self.app)

        left  = ttk.Frame(self.parent)
        right = ttk.Frame(self.parent)
        left.grid( row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)
        right.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)
        self.parent.columnconfigure(0, weight=1, uniform="col")
        self.parent.columnconfigure(1, weight=1, uniform="col")
        self.parent.rowconfigure(0, weight=1)

        self.build_left(left, current)
        self.build_right(right, current)

    def build_left(self, parent, current):
        """Nadpisz w podklasie — lewa kolumna."""
        raise NotImplementedError

    def build_right(self, parent, current):
        """Nadpisz w podklasie — prawa kolumna."""
        raise NotImplementedError

    # ── Restart GLava ─────────────────────────────────────────────────────────

    def _schedule_restart(self):
        if hasattr(self, "_rjob"):
            try:
                self.app.root.after_cancel(self._rjob)
            except Exception:
                pass
        from gui.glava import glava_restart
        mod = self.MODULE_NAME
        self._rjob = self.app.root.after(
            RESTART_DELAY_MS,
            lambda: glava_restart(
                mod,
                extra_flags=getattr(self.app, "extra_flags", "--desktop"),
                after_fn=self.app.update_status,
            ),
        )

    # ── Zapis GLSL ───────────────────────────────────────────────────────────
    def _debounce(self, key, value, target="module"):
        if target == "module":
            glsl_io.write_defines(self._module_glsl, {key: value}, self.SHAPE_PARAMS)
        elif target == "smooth":
            glsl_io.write_smooth(self._smooth_glsl, {key: value}, SMOOTH_PARAMS)
        elif target == "rc":
            glsl_io.write_int_req(RC_GLSL, key, int(value))
        self._schedule_restart()

    # ── Profile ───────────────────────────────────────────────────────────────

    def _apply_profile(self):
        name = self.profile_var.get()
        if not name:
            return
        profiles = get_shader_profiles_for_module(self.MODULE_NAME)
        if name not in profiles:
            return
        # Każdy moduł eksportuje apply_params i collect_params na poziomie modułu.
        # Importujemy dynamicznie żeby uniknąć cyklicznych importów.
        import importlib
        mod = importlib.import_module(f"gui.modules.{self.MODULE_NAME}")
        mod.apply_params(profiles[name], self.app)
        self.app.rebuild_module_tab()
        from gui.glava import glava_restart
        glava_restart(
            self.MODULE_NAME,
            extra_flags=getattr(self.app, "extra_flags", "--desktop"),
            after_fn=self.app.update_status,
        )

    def _save_profile(self):
        name = simpledialog.askstring(
            self.T.get("dialog_profile_title", "Nowy profil"),
            self.T.get("dialog_profile_name",  "Enter profile name:"),
        )
        if not name:
            return
        existing = get_shader_profiles_for_module(self.MODULE_NAME)
        if name in existing:
            if not messagebox.askyesno(
                self.T.get("dialog_overwrite_title", "Nadpisać profil?"),
                self.T.get("dialog_overwrite_msg",
                           "Profil '{}' już istnieje. Nadpisać?").format(name),
            ):
                return
        import importlib
        mod = importlib.import_module(f"gui.modules.{self.MODULE_NAME}")
        save_shader_profile_for_module(self.MODULE_NAME, name, mod.collect_params(self.app))
        self._refresh_cb()
        self.profile_var.set(name)

    def _delete_profile(self):
        name = self.profile_var.get()
        if name and messagebox.askyesno(
            "",
            self.T.get("dialog_delete_confirm",
                       "Are you sure you want to delete profile") + f" '{name}'?",
        ):
            delete_shader_profile_for_module(self.MODULE_NAME, name)
            self._refresh_cb()

    def _refresh_cb(self):
        names = sorted(get_shader_profiles_for_module(self.MODULE_NAME).keys())
        self.profile_cb["values"] = names
        if names:
            self.profile_cb.current(0)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _expert(self):
        """Odczytuje stan trybu expert z głównego okna."""
        try:
            return self.app.expert_mode.get()
        except AttributeError:
            return False

    # ── Ścieżki GLSL ─────────────────────────────────────────────────────────
    @property
    def _module_glsl(self):
        return os.path.join(GLAVA_DIR, f"{self.MODULE_NAME}.glsl")

    @property
    def _smooth_glsl(self):
        return os.path.join(GLAVA_DIR, "smooth_parameters.glsl")

    # ── Detachable sections ───────────────────────────────────────────────────

    def _detachable_lf(self, parent, title, build_fn, current):
        return make_detachable_lf(parent, title, build_fn, current,
                                  self.app.root, self._on_detach_close)

    def _on_detach_close(self, tw):
        _close_detached(tw, self.app, rebuild_fn=self.app.rebuild_module_tab)


# =============================================================================
# Funkcje modułowe — dostępne dla klas spoza hierarchii BaseParamWidget
# (np. TabMain)
# =============================================================================

def make_detachable_lf(parent, title, build_fn, current, root, on_close_fn):
    """
    Tworzy ttk.LabelFrame z ikoną ⊞ w prawym górnym rogu.
    on_close_fn(tw) — callback wywoływany po zamknięciu okna.
    Zwraca lf — caller wypełnia go normalnie.
    """
    lf = ttk.LabelFrame(parent, text=title, padding=(15, 10))
    lf.pack(fill="x", padx=10, pady=10)

    def _place_icon(event=None):
        btn = ttk.Label(lf, text=" ⊞ ", cursor="hand2")
        btn.place(relx=1.0, x=-4, y=-30, anchor="ne")
        btn.bind("<Button-1>",
                 lambda e: detach_section(title, build_fn, current,
                                          root, on_close_fn))
        lf.unbind("<Map>")

    lf.bind("<Map>", _place_icon)
    return lf


def detach_section(title, build_fn, current, root, on_close_fn):
    """
    Odpina sekcję do Toplevel topmost.
    iconify() PO deiconify(tw) — unikamy 2s blokady animacji Cinnamon.
    """
    tw = tk.Toplevel(root)
    tw.withdraw()
    tw.title(title)
    tw.resizable(True, True)
    tw.attributes("-topmost", True)

    frame = ttk.Frame(tw, padding=(8, 8))
    frame.pack(fill="both", expand=True)
    build_fn(frame, current)

    btn_frame = ttk.Frame(tw)
    btn_frame.pack(fill="x", padx=8, pady=(0, 8))
    ttk.Button(btn_frame, text="✕  Close",
               command=lambda: on_close_fn(tw)).pack(side="right")

    tw.update_idletasks()
    sw = tw.winfo_screenwidth()
    sh = tw.winfo_screenheight()
    ww = tw.winfo_reqwidth()
    wh = tw.winfo_reqheight()
    x = sw - ww - 20
    y = max(40, (sh - wh) // 2)
    tw.geometry(f"{ww}x{wh}+{x}+{y}")
    tw.deiconify()
    tw.update()
    tw.protocol("WM_DELETE_WINDOW", lambda: on_close_fn(tw))

    root.after(0, root.iconify)


def _close_detached(tw, app, rebuild_fn=None):
    """Zamyka okno, przywraca root, opcjonalnie przebudowuje zakładkę."""
    try:
        tw.destroy()
    except Exception:
        pass
    try:
        app.root.deiconify()
        app.root.lift()
    except Exception:
        pass
    if rebuild_fn:
        try:
            rebuild_fn()
        except Exception:
            pass
