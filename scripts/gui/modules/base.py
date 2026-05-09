# =============================================================================
# gui/modules/base.py
# Klasa bazowa dla wszystkich *ParamWidget.
# Zawiera boilerplate: __init__, build(), _schedule_restart, _apply_profile,
# _save_profile, _delete_profile, _refresh_cb, _expert.
# =============================================================================

import tkinter.ttk as ttk
from tkinter import messagebox, simpledialog

from ..core import (
    get_shader_profiles_for_module,
    save_shader_profile_for_module,
    delete_shader_profile_for_module,
)

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
