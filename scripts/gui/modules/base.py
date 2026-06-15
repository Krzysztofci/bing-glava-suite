# =============================================================================
# gui/modules/base.py
# Klasa bazowa dla wszystkich *ParamWidget.
# Zawiera boilerplate: __init__, build(), _schedule_restart, _apply_profile,
# _save_profile, _delete_profile, _refresh_cb, _expert.
# =============================================================================

import os
import tkinter as tk
import tkinter.ttk as ttk
from tkinter import messagebox

from ..core import (
    GLAVA_DIR,
    RC_GLSL,
    SMOOTH_PARAMS,
    delete_shader_profile_for_module,
    get_shader_profiles_for_module,
    save_shader_profile_for_module,
)
from . import glsl_io

RESTART_DELAY_MS = 300


def ask_string(parent, T, title, prompt, initialvalue=""):
    """TTK dialog zamiast simpledialog.askstring."""
    result = [None]
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.resizable(False, False)
    dlg.transient(parent)
    dlg.grab_set()
    ttk.Label(dlg, text=prompt).pack(padx=20, pady=(15, 4), anchor="w")
    var = tk.StringVar(value=initialvalue)
    entry = ttk.Entry(dlg, textvariable=var, width=30)
    entry.pack(padx=20, pady=(0, 10))
    entry.focus_set()
    entry.select_range(0, "end")
    btn_row = ttk.Frame(dlg)
    btn_row.pack(padx=20, pady=(0, 15), fill="x")
    def _ok():
        result[0] = var.get().strip() or None
        dlg.destroy()
    def _cancel():
        dlg.destroy()
    ok_text     = T.get("btn_apply", "OK")     if T else "OK"
    cancel_text = T.get("btn_cancel", "Cancel") if T else "Cancel"
    ttk.Button(btn_row, text=ok_text, style="Accent.TButton",
               command=_ok).pack(side="left", expand=True, fill="x", padx=(0, 4))
    ttk.Button(btn_row, text=cancel_text,
               command=_cancel).pack(side="left", expand=True, fill="x")
    dlg.bind("<Return>", lambda e: _ok())
    dlg.bind("<Escape>", lambda e: _cancel())
    dlg.wait_window()
    return result[0]



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

    MODULE_NAME:  str  = ""
    SHAPE_PARAMS: list = None  # podklasa ustawia własną listę; radial używa SHAPE_INT/FLOAT_PARAMS

    def __init__(self, parent, app, T, instance=None):
        self.parent    = parent
        self.app       = app
        self.T         = T
        self.vars      = {}
        # Gdy podane przez detach_section — ten widżet zawsze operuje na tej
        # konkretnej instancji, niezależnie od aktywnej karty w oknie głównym.
        # Gdy None — stare zachowanie: używa app.active_instance.
        self._instance = instance
        self._init_extra()

    def _get_instance(self):
        """Instancja docelowa: zamrożona (odpięty panel) lub aktywna (zakładka)."""
        if self._instance is not None:
            return self._instance
        return getattr(self.app, "active_instance", None)

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
        mod  = self.MODULE_NAME
        inst = self._get_instance()   # zamrożona lub active — pobrana TERAZ
        if hasattr(self.app, 'restart_active_instance'):
            self._rjob = self.app.root.after(
                RESTART_DELAY_MS,
                lambda i=inst: self.app.restart_active_instance(
                    module=mod,
                    instance=i,
                    after_fn=self.app.update_status,
                ),
            )
        else:
            from gui.glava import glava_restart
            self._rjob = self.app.root.after(
                RESTART_DELAY_MS,
                lambda i=inst: glava_restart(
                    mod,
                    extra_flags=getattr(self.app, "extra_flags", "--desktop"),
                    after_fn=self.app.update_status,
                    instance=i,
                ),
            )

    # ── Zapis GLSL ───────────────────────────────────────────────────────────
    def _debounce(self, key, value, target="module"):
        if target == "module":
            if self.SHAPE_PARAMS is None:
                raise NotImplementedError(f"{self.__class__.__name__} must define SHAPE_PARAMS")
            glsl_io.write_defines(self._module_glsl, {key: value}, self.SHAPE_PARAMS)
        elif target == "smooth":
            glsl_io.write_smooth(self._smooth_glsl, {key: value}, SMOOTH_PARAMS)
        elif target == "rc":
            rc_path = self.app.get_active_rc_glsl() if hasattr(self.app, 'get_active_rc_glsl') else RC_GLSL
            glsl_io.write_int_req(rc_path, key, int(value))
        self._schedule_restart()


    # ── Wiersze suwaków ───────────────────────────────────────────────────────

    def _slider_row(self, parent, param_def, current, row_idx, target="module"):
        """Int slider. param_def: (key, label, vmin, vmax, default, unit, tooltip)"""
        key, label, vmin, vmax, default, unit, tooltip = param_def
        cur = int(current.get(key, default))
        var = tk.IntVar(value=cur)
        self.vars[key] = var
        parent.columnconfigure(2, weight=1)
        ttk.Label(parent, text=label, width=12, anchor="w").grid(
            row=row_idx, column=0, padx=(10, 5), pady=5, sticky="w")
        t = glsl_io.tip(parent, "?", tooltip)
        if t:
            t.grid(row=row_idx, column=1, padx=5, pady=5)
        entry_var = tk.StringVar(value=str(cur))
        def on_change(v, k=key, tgt=target):
            iv = max(vmin, min(vmax, int(round(float(v)))))
            var.set(iv)
            entry_var.set(str(iv))
            self._debounce(k, iv, tgt)
        def on_entry(e, k=key, tgt=target):
            try:
                iv = int(round(float(entry_var.get())))
                iv = max(vmin, min(vmax, iv))
                var.set(iv)
                entry_var.set(str(iv))
                self._debounce(k, iv, tgt)
            except ValueError:
                entry_var.set(str(var.get()))
        scale = ttk.Scale(parent, from_=vmin, to=vmax,
                          orient="horizontal", variable=var,
                          command=on_change)
        scale.grid(row=row_idx, column=2, padx=10, pady=5, sticky="ew")
        entry = ttk.Entry(parent, textvariable=entry_var, width=6, justify="right")
        entry.grid(row=row_idx, column=3, padx=(0, 4), pady=5)
        entry.bind("<Return>",   on_entry)
        entry.bind("<FocusOut>", on_entry)
        ttk.Label(parent, text=unit if unit else " ", width=4).grid(
            row=row_idx, column=4, padx=(0, 10), pady=5, sticky="e")

    def _float_slider_row(self, parent, param_def, current, row_idx, target="smooth"):
        """Float slider. param_def: (key, label, vmin, vmax, default, unit, step, tooltip)"""
        key, label, vmin, vmax, default, unit, step, tooltip = param_def
        try:
            cur = float(current.get(key, default))
        except (ValueError, TypeError):
            cur = float(default)
        dec = glsl_io.decimals(step)
        var = tk.DoubleVar(value=cur)
        self.vars[key] = var
        parent.columnconfigure(2, weight=1)
        ttk.Label(parent, text=label, width=12, anchor="w").grid(
            row=row_idx, column=0, padx=(10, 5), pady=5, sticky="w")
        t = glsl_io.tip(parent, "?", tooltip)
        if t:
            t.grid(row=row_idx, column=1, padx=5, pady=5)
        entry_var = tk.StringVar(value=f"{cur:.{dec}f}")
        def on_change(v, k=key, tgt=target):
            fv = float(v)
            # snap do kroku
            if step > 0:
                fv = round(round(fv / step) * step, dec)
            fv = max(vmin, min(vmax, fv))
            var.set(fv)
            entry_var.set(f"{fv:.{dec}f}")
            self._debounce(k, fv, tgt)
        def on_entry(e, k=key, tgt=target):
            try:
                fv = float(entry_var.get())
                fv = max(vmin, min(vmax, fv))
                var.set(fv)
                entry_var.set(f"{fv:.{dec}f}")
                self._debounce(k, fv, tgt)
            except ValueError:
                entry_var.set(f"{var.get():.{dec}f}")
        scale = ttk.Scale(parent, from_=vmin, to=vmax,
                          orient="horizontal", variable=var,
                          command=on_change)
        scale.grid(row=row_idx, column=2, padx=10, pady=5, sticky="ew")
        entry = ttk.Entry(parent, textvariable=entry_var, width=6, justify="right")
        entry.grid(row=row_idx, column=3, padx=(0, 4), pady=5)
        entry.bind("<Return>",   on_entry)
        entry.bind("<FocusOut>", on_entry)
        ttk.Label(parent, text=unit if unit else " ", width=4).grid(
            row=row_idx, column=4, padx=(0, 10), pady=5, sticky="e")

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
        mod  = importlib.import_module(f"gui.modules.{self.MODULE_NAME}")
        inst = self._get_instance()
        # apply_params czyta app.active_instance — tymczasowo ustawiamy
        # zamrożoną instancję żeby zapis trafił do właściwego pliku GLSL
        _orig = getattr(self.app, "active_instance", None)
        if inst is not None:
            self.app.active_instance = inst
        try:
            mod.apply_params(profiles[name], self.app)
        finally:
            self.app.active_instance = _orig
        self.app.rebuild_module_tab()
        if hasattr(self.app, 'restart_active_instance'):
            self.app.restart_active_instance(
                module=self.MODULE_NAME,
                instance=inst,
                after_fn=self.app.update_status,
            )
        else:
            from gui.glava import glava_restart
            glava_restart(
                self.MODULE_NAME,
                extra_flags=getattr(self.app, "extra_flags", "--desktop"),
                after_fn=self.app.update_status,
                instance=inst,
            )

    def _save_profile(self):
        name = ask_string(
            self.parent, self.T,
            self.T.get("dialog_profile_title", "New profile"),
            self.T.get("dialog_profile_name",  "Enter profile name:"),
        )
        if not name:
            return
        existing = get_shader_profiles_for_module(self.MODULE_NAME)
        if name in existing:
            if not messagebox.askyesno(
                self.T.get("dialog_overwrite_title", "Overwrite profile?"),
                self.T.get("dialog_overwrite_msg",
                           "Profile '{}' already exists. Overwrite?").format(name),
            ):
                return
        import importlib
        mod  = importlib.import_module(f"gui.modules.{self.MODULE_NAME}")
        inst = self._get_instance()
        _orig = getattr(self.app, "active_instance", None)
        if inst is not None:
            self.app.active_instance = inst
        try:
            params = mod.collect_params(self.app)
        finally:
            self.app.active_instance = _orig
        save_shader_profile_for_module(self.MODULE_NAME, name, params)
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
        try:
            return self._get_instance().module_glsl(self.MODULE_NAME)
        except AttributeError:
            return os.path.join(GLAVA_DIR, f"{self.MODULE_NAME}.glsl")

    @property
    def _smooth_glsl(self):
        try:
            return self._get_instance().smooth_glsl
        except AttributeError:
            return os.path.join(GLAVA_DIR, "smooth_parameters.glsl")

    @property
    def _glsl(self):
        try:
            return self._get_instance().module_glsl(self.MODULE_NAME)
        except AttributeError:
            return os.path.join(GLAVA_DIR, f"{self.MODULE_NAME}.glsl")

    @property
    def _tmpl(self):
        try:
            return self._get_instance().module_tmpl(self.MODULE_NAME)
        except AttributeError:
            return os.path.join(GLAVA_DIR, f"{self.MODULE_NAME}_colors.frag")

    @property
    def _frag(self):
        try:
            return self._get_instance().module_frag(self.MODULE_NAME)
        except AttributeError:
            return os.path.join(GLAVA_DIR, self.MODULE_NAME, "1.frag")
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
        btn = ttk.Label(lf, text=" ⧉ ", cursor="hand2", font=("TkDefaultFont", 12))
        btn.place(relx=1.0, x=-4, y=-33, anchor="ne")
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

    try:
        import importlib
        orig_widget     = build_fn.__self__
        frozen_instance = getattr(orig_widget.app, "active_instance", None)

        # collect_params(app) czyta app.active_instance — tymczasowo podmieniamy
        # na zamrożoną instancję żeby odczytać właściwy plik GLSL
        _orig = getattr(orig_widget.app, "active_instance", None)
        if frozen_instance is not None:
            orig_widget.app.active_instance = frozen_instance
        try:
            mod_py  = importlib.import_module(f"gui.modules.{orig_widget.MODULE_NAME}")
            current = mod_py.collect_params(orig_widget.app)
        finally:
            orig_widget.app.active_instance = _orig

        # Nowy widżet z zamrożoną instancją — odizolowany od okna głównego.
        # Wszelkie _debounce, _schedule_restart i _apply_profile tego widżetu
        # zawsze trafią do frozen_instance, nie do aktualnie aktywnej karty.
        WidgetClass      = type(orig_widget)
        detached_widget  = WidgetClass(frame, orig_widget.app, orig_widget.T,
                                       instance=frozen_instance)
        method_name      = build_fn.__func__.__name__
        getattr(detached_widget, method_name)(frame, current)
    except Exception:
        # Fallback: stare zachowanie (bez zamrożenia instancji)
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
