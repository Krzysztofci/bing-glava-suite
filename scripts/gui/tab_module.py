# =============================================================================
# gui/tab_module.py
# Zakładka dynamiczna — zmienia zawartość przy zmianie active_module.
# Deleguje budowanie sekcji parametrów do gui/modules/<moduł>.py
# =============================================================================

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import os

from .core import (
    GLAVA_MODULES, CONFIG_DIR,
    get_live_frag, get_template,
    get_shader_profiles_for_module,
    save_shader_profile_for_module,
    delete_shader_profile_for_module,
)
from .glava import glava_restart


def build_tab_module(parent, app):
    tab = TabModule(parent, app)
    tab.build()


class TabModule:
    def __init__(self, parent, app):
        self.parent = parent
        self.app    = app
        self.T      = app.T
        self.module = app.active_module

    def build(self):
        outer = tk.Frame(self.parent, padx=6, pady=6)
        outer.pack(fill="both", expand=True)
        # Parametry modułu — plugin buduje całą zawartość łącznie z profilami
        self._build_module_params(outer)

    def _build_module_params(self, parent):
        """
        Wczytuje moduł z gui/modules/<name>.py i deleguje budowanie.
        Jeśli moduł nie ma jeszcze swojego pliku — pokazuje placeholder.
        """
        try:
            mod = _load_module_plugin(self.module)
            mod.build_params(parent, self.app, self.T)
        except ImportError:
            _build_placeholder(parent, self.module, self.T)

    def _apply_profile(self):
        name = self.profile_var.get()
        if not name:
            return
        profiles = get_shader_profiles_for_module(self.module)
        if name not in profiles:
            return
        try:
            mod = _load_module_plugin(self.module)
            mod.apply_params(profiles[name], self.app)
            glava_restart(self.module, after_fn=self.app.update_status)
        except ImportError:
            pass

    def _save_profile(self):
        name = simpledialog.askstring(
            self.T.get("dialog_profile_title", "Nowy profil szadera"),
            self.T.get("dialog_profile_name",  "Podaj nazwę:"))
        if not name:
            return
        try:
            mod = _load_module_plugin(self.module)
            params = mod.collect_params(self.app)
            save_shader_profile_for_module(self.module, name, params)
            self._refresh_profile_cb()
            self.profile_var.set(name)
        except ImportError:
            messagebox.showwarning(
                "", self.T.get("warn_no_plugin",
                               "Brak wtyczki parametrów dla tego modułu."))

    def _delete_profile(self):
        name = self.profile_var.get()
        if not name:
            return
        if messagebox.askyesno(
                "", f"{self.T.get('dialog_delete_confirm', 'Usuń')} '{name}'?"):
            delete_shader_profile_for_module(self.module, name)
            self._refresh_profile_cb()

    def _refresh_profile_cb(self):
        names = sorted(get_shader_profiles_for_module(self.module).keys())
        self.profile_cb["values"] = names
        if names:
            self.profile_cb.current(0)

    def _reset_shader(self):
        T = self.T
        module = self.module
        if not messagebox.askyesno(
                T.get("btn_reset_shader", "Reset szadera"),
                T.get("confirm_reset_shader",
                      "Przywrócić domyślny shader?\nWszystkie zmiany zostaną utracone.")):
            return
        try:
            mod = _load_module_plugin(module)
            if hasattr(mod, "reset_shader"):
                mod.reset_shader(self.app)
            else:
                # Fallback — ogólny reset tylko 1.frag
                import shutil
                tmpl = get_template(module)
                live = get_live_frag(module)
                if os.path.exists(tmpl):
                    os.makedirs(os.path.dirname(live), exist_ok=True)
                    shutil.copy2(tmpl, live)
        except ImportError:
            import shutil
            tmpl = get_template(module)
            live = get_live_frag(module)
            if os.path.exists(tmpl):
                os.makedirs(os.path.dirname(live), exist_ok=True)
                shutil.copy2(tmpl, live)
        # Przebuduj zakładkę żeby suwaki pokazały nowe wartości
        self.app.rebuild_module_tab()
        messagebox.showinfo("", T.get("reset_done", "Shader przywrócony."))
        glava_restart(module, after_fn=self.app.update_status)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_module_plugin(module_name):
    """
    Importuje gui/modules/<module_name>.py jako plugin.
    Każdy plugin musi eksportować:
      build_params(parent, app, T)   — buduje widgety parametrów
      collect_params(app)            — zwraca dict aktualnych wartości
      apply_params(params, app)      — wpisuje wartości do shadera
    """
    import importlib
    return importlib.import_module(f"gui.modules.{module_name}")


def _build_placeholder(parent, module, T):
    """Pokazywany gdy moduł nie ma jeszcze wtyczki parametrów."""
    lf = tk.LabelFrame(parent,
                        text=T.get("section_shape", "Kształt i dynamika"),
                        font=("Arial", 8, "bold"), padx=4, pady=4)
    lf.pack(fill="x")
    tk.Label(lf,
             text=T.get("label_no_plugin",
                        f"Parametry dla modułu '{module}'\nzostaną dodane wkrótce."),
             font=("Arial", 9), fg="gray50", justify="left").pack(pady=8)
