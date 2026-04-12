# =============================================================================
# gui/modules/wave.py
# Plugin parametrów dla modułu wave.
#
# Plik konfiguracyjny: ~/.config/glava/wave.glsl
#
# Obsługiwane parametry:
#   MIN_THICKNESS int   minimalna grubość linii (px)
#   MAX_THICKNESS int   maksymalna grubość linii (px)
#   AMPLIFY       int   wzmocnienie amplitudy
# =============================================================================

import os, re
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from ..core import CONFIG_DIR, GLAVA_DIR, RC_GLSL
from ..core import (
    get_shader_profiles_for_module,
    save_shader_profile_for_module,
    delete_shader_profile_for_module,
)

def _wave_glsl():  return os.path.join(GLAVA_DIR, "wave.glsl")
def _smooth_glsl(): return os.path.join(GLAVA_DIR, "smooth_parameters.glsl")
def _wave_tmpl():  return os.path.join(GLAVA_DIR, "wave_colors.frag")
def _wave_1frag(): return os.path.join(GLAVA_DIR, "wave", "1.frag")

SHAPE_PARAMS = [
    ("MIN_THICKNESS", "Min. grubość linii",  1,  20,  1, "px",
     "Minimalna grubość linii fali w pikselach\n(przy niskiej amplitudzie)"),
    ("MAX_THICKNESS", "Maks. grubość linii", 1,  40, 6, "px",
     "Maksymalna grubość linii fali w pikselach\n(przy wysokiej amplitudzie)"),
    ("AMPLIFY",       "Wzmocnienie",        50, 800, 500, "",
     "Wzmocnienie amplitudy sygnału audio\nWiększe = wyższe fale"),
]

SMOOTH_PARAMS = [
    ("setgravitystep",  "Grawitacja",      0.1, 20.0,  4.2, "",   0.1,
     "Szybkość opadania po szczycie"),
    ("setsmoothfactor", "Wygładzanie",   0.001,  0.1, 0.025, "", 0.001,
     "Rozmiar jądra wygładzającego FFT\nMniejsze = bardziej responsywne"),
    ("setavgframes",    "Klatek avg",        1,   16,     5, "",     1,
     "Liczba klatek do uśredniania"),
    ("setfftscale",     "Skala FFT",       1.0, 30.0,  10.2, "",   0.1,
     "Skala częstotliwości FFT"),
    ("setfftcutoff",    "Odcięcie basów",  0.0,  1.0,   0.3, "",  0.01,
     "Odcięcie najniższych częstotliwości FFT"),
]

FLAG_PARAMS = []  # wave nie ma przełączników boolowskich

ALL_DEFINE_KEYS = {p[0] for p in SHAPE_PARAMS}


def build_params(parent, app, T):
    WaveParamWidget(parent, app, T).build()


def collect_params(app):
    p = _read_defines(_wave_glsl(), SHAPE_PARAMS)
    p.update(_read_smooth(_smooth_glsl()))
    return p


def apply_params(params, app):
    _write_defines(_wave_glsl(), params, SHAPE_PARAMS)
    _write_smooth(_smooth_glsl(), params)


def reset_shader(app):
    import shutil
    tmpl = _wave_tmpl()
    live = _wave_1frag()
    if os.path.exists(tmpl):
        os.makedirs(os.path.dirname(live), exist_ok=True)
        shutil.copy2(tmpl, live)
    defaults = {p[0]: p[4] for p in SHAPE_PARAMS}
    _write_defines(_wave_glsl(), defaults, SHAPE_PARAMS)


class WaveParamWidget:
    def __init__(self, parent, app, T):
        self.parent = parent
        self.app    = app
        self.T      = T
        self.vars   = {}

    def build(self):
        current = collect_params(self.app)

        left  = tk.Frame(self.parent)
        right = tk.Frame(self.parent)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        right.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        self.parent.columnconfigure(0, weight=1, uniform="wc")
        self.parent.columnconfigure(1, weight=1, uniform="wc")
        self.parent.rowconfigure(0, weight=1)

        self._build_shape(left, current)
        self._build_smooth(right, current)
        self._build_profiles(right)

    def _build_shape(self, parent, current):
        lf = tk.LabelFrame(parent, text="Kształt",
                           font=("Arial", 9, "bold"), padx=5, pady=4)
        lf.pack(fill="x", pady=(0, 4))
        for p in SHAPE_PARAMS:
            self._slider_row(lf, p, current)

        tk.Label(parent,
                 text="Wave nie ma przełączników.\nKolory ustawiane na zakładce Główna.",
                 font=("Arial", 8), fg="gray50", justify="left"
                 ).pack(anchor="w", pady=(8, 0))

    def _build_smooth(self, parent, current):
        lf = tk.LabelFrame(parent, text="Wygładzanie",
                           font=("Arial", 9, "bold"), padx=5, pady=4)
        lf.pack(fill="x", pady=(0, 4))
        for p in SMOOTH_PARAMS:
            self._float_slider_row(lf, p, current)
        tk.Label(lf, text="⚠ Wpływa na wszystkie moduły",
                 font=("Arial", 7), fg="#bf360c").pack(anchor="w", pady=(4, 0))

    def _debounce_smooth(self, key, value):
        _write_smooth(_smooth_glsl(), {key: value})
        self._schedule_restart()

    def _float_slider_row(self, parent, param_def, current):
        key, label, vmin, vmax, default, unit, step, tooltip = param_def
        cur = float(current.get(key, default))
        var = tk.DoubleVar(value=cur)
        self.vars[key] = var
        dec = len(str(step).rstrip("0").split(".")[-1]) if "." in str(step) else 0
        fmt = f"{{:.{dec}f}}"
        entry_var = tk.StringVar(value=fmt.format(cur))
        row = tk.Frame(parent)
        row.pack(fill="x", pady=2)
        tk.Label(row, text=label, font=("Arial", 9),
                 width=16, anchor="w").pack(side="left")
        _tip(row, "?", tooltip)
        slider = tk.Scale(row, variable=var, from_=vmin, to=vmax,
                          resolution=step, orient="horizontal",
                          showvalue=False, sliderlength=12)
        slider.pack(side="left", fill="x", expand=True, padx=(3, 0))
        entry = tk.Entry(row, textvariable=entry_var,
                         width=6, font=("Arial", 9), justify="right")
        entry.pack(side="left", padx=(3, 0))
        tk.Label(row, text=unit if unit else "  ",
                 font=("Arial", 9), fg="gray50", width=3).pack(side="left")
        def on_slide(val, ev=entry_var, k=key):
            ev.set(fmt.format(float(val)))
            self._debounce_smooth(k, float(val))
        def on_entry(event, sv=var, ev=entry_var, lo=vmin, hi=vmax, k=key):
            try:
                v = max(float(lo), min(float(hi), float(ev.get())))
                sv.set(v); ev.set(fmt.format(v))
                self._debounce_smooth(k, v)
            except ValueError:
                ev.set(fmt.format(sv.get()))
        slider.config(command=on_slide)
        entry.bind("<Return>",   on_entry)
        entry.bind("<FocusOut>", on_entry)

    def _build_profiles(self, parent):
        lf = tk.LabelFrame(parent, text="Profile szadera wave",
                           font=("Arial", 9, "bold"), padx=5, pady=4)
        lf.pack(fill="x", pady=(0, 4))

        profiles = get_shader_profiles_for_module("wave")
        names    = sorted(profiles.keys())
        self.profile_var = tk.StringVar()
        self.profile_cb  = ttk.Combobox(lf, textvariable=self.profile_var,
                                        values=names, state="readonly",
                                        font=("Arial", 9))
        self.profile_cb.pack(fill="x", pady=(0, 3))
        if names: self.profile_cb.current(0)

        tk.Label(lf, text="Ksztalt (kolory bez zmian)",
                 font=("Arial", 7), fg="gray50").pack(anchor="w")

        btn_row = tk.Frame(lf)
        btn_row.pack(fill="x", pady=(4, 0))
        tk.Button(btn_row, text="Zastosuj", command=self._apply_profile,
                  bg="#00695c", fg="white", font=("Arial", 8)
                  ).pack(side="left", expand=True, fill="x", padx=(0, 2))
        tk.Button(btn_row, text="Zapisz", command=self._save_profile,
                  bg="#37474f", fg="white", font=("Arial", 8)
                  ).pack(side="left", expand=True, fill="x", padx=(0, 2))
        tk.Button(btn_row, text="Usun", command=self._delete_profile,
                  bg="#b71c1c", fg="white", font=("Arial", 8)
                  ).pack(side="left")

        rf = tk.LabelFrame(parent, text="Reset",
                           font=("Arial", 9, "bold"), padx=5, pady=4)
        rf.pack(fill="x", pady=(4, 0))
        tk.Button(rf, text="Reset szadera wave", command=self._reset_shader,
                  bg="#5d4037", fg="white", font=("Arial", 8)
                  ).pack(fill="x")

    def _slider_row(self, parent, param_def, current):
        key, label, vmin, vmax, default, unit, tooltip = param_def
        cur = int(current.get(key, default))
        var = tk.IntVar(value=cur)
        self.vars[key] = var
        entry_var = tk.StringVar(value=str(cur))
        setattr(self, f"_entry_{key}", entry_var)

        row = tk.Frame(parent)
        row.pack(fill="x", pady=2)
        tk.Label(row, text=label, font=("Arial", 9),
                 width=16, anchor="w").pack(side="left")
        _tip(row, "?", tooltip)
        slider = tk.Scale(row, variable=var, from_=vmin, to=vmax,
                          orient="horizontal", showvalue=False, sliderlength=12)
        slider.pack(side="left", fill="x", expand=True, padx=(3, 0))
        entry = tk.Entry(row, textvariable=entry_var,
                         width=5, font=("Arial", 9), justify="right")
        entry.pack(side="left", padx=(3, 0))
        tk.Label(row, text=unit if unit else "  ",
                 font=("Arial", 9), fg="gray50", width=3).pack(side="left")

        def on_slide(val, ev=entry_var, k=key):
            v = self._clamp_thickness(k, int(float(val)))
            var.set(v); ev.set(str(v))
            self._debounce(k, v)

        def on_entry(event, sv=var, ev=entry_var, lo=vmin, hi=vmax, k=key):
            try:
                v = max(lo, min(hi, int(ev.get())))
                v = self._clamp_thickness(k, v)
                sv.set(v); ev.set(str(v))
                self._debounce(k, v)
            except ValueError:
                ev.set(str(sv.get()))

        slider.config(command=on_slide)
        entry.bind("<Return>",   on_entry)
        entry.bind("<FocusOut>", on_entry)

    def _clamp_thickness(self, key, value):
        if key == "MIN_THICKNESS" and "MAX_THICKNESS" in self.vars:
            max_v = self.vars["MAX_THICKNESS"].get()
            if value > max_v:
                self.vars["MAX_THICKNESS"].set(value)
                if hasattr(self, "_entry_MAX_THICKNESS"):
                    self._entry_MAX_THICKNESS.set(str(value))
                _write_defines(_wave_glsl(), {"MAX_THICKNESS": value}, SHAPE_PARAMS)
        elif key == "MAX_THICKNESS" and "MIN_THICKNESS" in self.vars:
            min_v = self.vars["MIN_THICKNESS"].get()
            if value < min_v:
                self.vars["MIN_THICKNESS"].set(value)
                if hasattr(self, "_entry_MIN_THICKNESS"):
                    self._entry_MIN_THICKNESS.set(str(value))
                _write_defines(_wave_glsl(), {"MIN_THICKNESS": value}, SHAPE_PARAMS)
        return value

    def _debounce(self, key, value):
        _write_defines(_wave_glsl(), {key: value}, SHAPE_PARAMS)
        self._schedule_restart()

    def _schedule_restart(self):
        if hasattr(self, "_rjob"):
            try: self.app.root.after_cancel(self._rjob)
            except Exception: pass
        from gui.glava import glava_restart
        self._rjob = self.app.root.after(
            300, lambda: glava_restart("wave", after_fn=self.app.update_status))

    def _apply_profile(self):
        name = self.profile_var.get()
        if not name: return
        profiles = get_shader_profiles_for_module("wave")
        if name not in profiles: return
        apply_params(profiles[name], self.app)
        self.app.rebuild_module_tab()
        from gui.glava import glava_restart
        glava_restart("wave", after_fn=self.app.update_status)

    def _save_profile(self):
        name = simpledialog.askstring("Nowy profil", "Podaj nazwę:")
        if not name: return
        save_shader_profile_for_module("wave", name, collect_params(self.app))
        self._refresh_cb()
        self.profile_var.set(name)

    def _delete_profile(self):
        name = self.profile_var.get()
        if name and messagebox.askyesno("", f"Usunac '{name}'?"):
            delete_shader_profile_for_module("wave", name)
            self._refresh_cb()

    def _refresh_cb(self):
        names = sorted(get_shader_profiles_for_module("wave").keys())
        self.profile_cb["values"] = names
        if names: self.profile_cb.current(0)

    def _reset_shader(self):
        if messagebox.askyesno("Reset", "Przywrocic domyslny shader wave?"):
            reset_shader(self.app)
            self.app.rebuild_module_tab()
            from gui.glava import glava_restart
            glava_restart("wave", after_fn=self.app.update_status)


# ─── I/O ─────────────────────────────────────────────────────────────────────

def _read_defines(path, param_defs):
    result = {p[0]: p[4] for p in param_defs}
    if not os.path.exists(path): return result
    with open(path) as f: content = f.read()
    for p in param_defs:
        m = re.search(rf'^#define\s+{p[0]}\s+(\S+)', content, re.MULTILINE)
        if m:
            try: result[p[0]] = int(m.group(1))
            except ValueError: pass
    return result

def _write_defines(path, params, param_defs):
    if not os.path.exists(path): return
    keys = {p[0] for p in param_defs}
    with open(path) as f: content = f.read()
    for key, val in params.items():
        if key not in keys: continue
        new = re.sub(rf'^(#define\s+{key}\s+)\S+', rf'\g<1>{val}',
                     content, flags=re.MULTILINE)
        content = new if new != content else content + f"\n#define {key} {val}\n"
    with open(path, "w") as f: f.write(content)

def _tip(parent, label, text):
    lbl = tk.Label(parent, text=label, font=("Arial", 8),
                   fg="#1565c0", cursor="question_arrow",
                   relief="groove", padx=2)
    lbl.pack(side="left", padx=(2, 0))
    tip = [None]
    def show(e):
        x = lbl.winfo_rootx() + 20
        y = lbl.winfo_rooty() + 20
        tip[0] = tk.Toplevel(lbl)
        tip[0].wm_overrideredirect(True)
        tip[0].wm_geometry(f"+{x}+{y}")
        tk.Label(tip[0], text=text, justify="left",
                 bg="#ffffcc", relief="solid", bd=1,
                 font=("Arial", 8), padx=4, pady=2).pack()
    def hide(e):
        if tip[0]: tip[0].destroy(); tip[0] = None
    lbl.bind("<Enter>", show)
    lbl.bind("<Leave>", hide)

def _read_smooth(path):
    result = {p[0]: p[4] for p in SMOOTH_PARAMS}
    if not os.path.exists(path): return result
    with open(path) as f: content = f.read()
    for p in SMOOTH_PARAMS:
        m = re.search(rf'^#request\s+{p[0]}\s+(\S+)', content, re.MULTILINE)
        if m:
            try:
                result[p[0]] = int(m.group(1)) if p[0] == "setavgframes" \
                    else float(m.group(1))
            except ValueError: pass
    return result

def _write_smooth(path, params):
    if not os.path.exists(path): return
    keys = {p[0] for p in SMOOTH_PARAMS}
    with open(path) as f: content = f.read()
    for key, val in params.items():
        if key not in keys: continue
        sv = str(int(val)) if key == "setavgframes" \
            else f"{float(val):.4f}".rstrip("0").rstrip(".")
        new = re.sub(rf'^(#request\s+{key}\s+)\S+', rf'\g<1>{sv}',
                     content, flags=re.MULTILINE)
        content = new if new != content else content + f"\n#request {key} {sv}\n"
    with open(path, "w") as f: f.write(content)
