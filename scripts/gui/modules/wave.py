# =============================================================================
# gui/modules/wave.py
#
# Wzorzec GUI: bars.py v5 (grid w LabelFrame, ttk.*, Forest-ttk-theme)
# =============================================================================
import os, re, math
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from ..core import CONFIG_DIR, GLAVA_DIR, RC_GLSL
from ..core import (
    get_shader_profiles_for_module,
    save_shader_profile_for_module,
    delete_shader_profile_for_module,
)
from ..widgets import AccelSlider

def _wave_glsl():   return os.path.join(GLAVA_DIR, "wave.glsl")
def _smooth_glsl(): return os.path.join(GLAVA_DIR, "smooth_parameters.glsl")
def _wave_tmpl():   return os.path.join(GLAVA_DIR, "wave_colors.frag")
def _wave_1frag():  return os.path.join(GLAVA_DIR, "wave", "1.frag")

# (klucz, etykieta, min, max, domyślna, jednostka, tooltip)
SHAPE_PARAMS = [
    ("MIN_THICKNESS", "Min. grubość linii",  1,  20,  1, "px",
     "Minimalna grubość linii fali w pikselach\n(przy niskiej amplitudzie)"),
    ("MAX_THICKNESS", "Maks. grubość linii", 1,  40,  6, "px",
     "Maksymalna grubość linii fali w pikselach\n(przy wysokiej amplitudzie)"),
    ("AMPLIFY",       "Wzmocnienie",        50, 800, 500, "",
     "Wzmocnienie amplitudy sygnału audio\nWiększe = wyższe fale"),
]

# (klucz, etykieta, min, max, domyślna, jednostka, krok, tooltip)
SMOOTH_PARAMS = [
    ("setgravitystep",  "Grawitacja",      0.1, 20.0,  4.2, "",   0.1,
     "Szybkość opadania po szczycie"),
    ("setsmoothfactor", "Wygładzanie",   0.001,  0.1, 0.025, "", 0.001,
     "Rozmiar jądra wygładzającego FFT"),
    ("setavgframes",    "Klatek avg",        1,   16,     5, "",     1,
     "Liczba klatek do uśredniania"),
    ("setfftscale",     "Skala FFT",       1.0, 30.0,  10.2, "",   0.1,
     "Skala częstotliwości FFT"),
    ("setfftcutoff",    "Odcięcie basów",  0.0,  1.0,   0.3, "",  0.01,
     "Odcięcie najniższych częstotliwości FFT"),
]

FLAG_PARAMS = []
ALL_DEFINE_KEYS = {p[0] for p in SHAPE_PARAMS} | {
    "ROTATE", "WAVE_LENGTH", "CENTER_OFFSET_X", "CENTER_OFFSET_Y"}


def build_params(parent, app, T):
    WaveParamWidget(parent, app, T).build()


def collect_params(app):
    p = _read_defines(_wave_glsl(), SHAPE_PARAMS)
    p["WAVE_LENGTH"]     = _read_int(_wave_glsl(), "WAVE_LENGTH", 0)
    p["CENTER_OFFSET_X"] = _read_int(_wave_glsl(), "CENTER_OFFSET_X", 0)
    p["CENTER_OFFSET_Y"] = _read_int(_wave_glsl(), "CENTER_OFFSET_Y", 0)
    p["ROTATE"]          = _read_rotate(_wave_glsl())
    p.update(_read_smooth(_smooth_glsl()))
    return p


def apply_params(params, app):
    _write_defines(_wave_glsl(), params, SHAPE_PARAMS)
    for key in ("WAVE_LENGTH", "CENTER_OFFSET_X", "CENTER_OFFSET_Y"):
        if key in params:
            _write_int(_wave_glsl(), key, int(params[key]))
    if "ROTATE" in params:
        _write_rotate(_wave_glsl(), float(params["ROTATE"]))
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
    for key in ("WAVE_LENGTH", "CENTER_OFFSET_X", "CENTER_OFFSET_Y"):
        _write_int(_wave_glsl(), key, 0)
    _write_rotate(_wave_glsl(), 0.0)


class WaveParamWidget:
    def __init__(self, parent, app, T):
        self.parent = parent
        self.app    = app
        self.T      = T
        self.vars   = {}
        self._accel_sliders = {}
        try:
            from ..geometry import get_screen_info
            si = get_screen_info()
            self._diag   = int(math.sqrt(si[0]**2 + si[1]**2) * 1.1)
            self._half_x = si[0] // 2
            self._half_y = si[1] // 2
        except Exception:
            self._diag   = 1920
            self._half_x = 800
            self._half_y = 450

    def build(self):
        current = collect_params(self.app)

        left  = ttk.Frame(self.parent)
        right = ttk.Frame(self.parent)
        left.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)
        right.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)
        self.parent.columnconfigure(0, weight=1, uniform="wc")
        self.parent.columnconfigure(1, weight=1, uniform="wc")
        self.parent.rowconfigure(0, weight=1)

        self._build_shape(left, current)
        self._build_position(left, current)
        self._build_smooth(right, current)
        self._build_profiles(right)

    # ── Kształt ───────────────────────────────────────────────────────────────

    def _build_shape(self, parent, current):
        lf = ttk.LabelFrame(parent,
                            text=self.T.get("section_shape", "Kształt i dynamika"),
                            padding=(15, 10))
        lf.pack(fill="x", padx=10, pady=10)
        lf.columnconfigure(2, weight=1)

        mapping = {
            "MIN_THICKNESS": ("label_line_min",  "tooltip_line_min"),
            "MAX_THICKNESS": ("label_line_max",  "tooltip_line_max"),
            "AMPLIFY":       ("label_gain",      "tooltip_gain"),
        }

        for idx, p in enumerate(SHAPE_PARAMS):
            lk, tk_ = mapping.get(p[0], (None, None))
            label   = self.T.get(lk, p[1]) if lk else p[1]
            tooltip = self.T.get(tk_, p[6]) if tk_ else p[6]
            self._int_row(lf, p[0], label, p[2], p[3],
                          int(current.get(p[0], p[4])), p[5], tooltip, idx)

        # WAVE_LENGTH
        row_idx = len(SHAPE_PARAMS)
        wl_val = int(current.get("WAVE_LENGTH", 0))

        ttk.Label(lf, text=self.T.get("label_wave_length", "Długość fali"),
                  width=12, anchor="w").grid(
            row=row_idx, column=0, padx=(10, 5), pady=5, sticky="w")
        t = _tip(lf, "?", self.T.get("tooltip_wave_length",
                 "Długość fali w pikselach. 0 = pełna szerokość ekranu."))
        if t: t.grid(row=row_idx, column=1, padx=5, pady=5)

        wl_slider = AccelSlider(lf, vmin=0, vmax=self._diag,
                                value=wl_val, step=1,
                                on_change=self._on_wave_length)
        wl_slider.grid(row=row_idx, column=2, padx=10, pady=5, sticky="ew")
        ttk.Label(lf, text="px", width=4).grid(
            row=row_idx, column=3, padx=(5, 10), pady=5, sticky="e")
        self._accel_sliders["WAVE_LENGTH"] = wl_slider

    def _on_wave_length(self, val):
        _write_int(_wave_glsl(), "WAVE_LENGTH", int(val))
        self._schedule_restart()

    # ── Pozycja i rotacja ─────────────────────────────────────────────────────

    def _build_position(self, parent, current):
        lf = ttk.LabelFrame(parent,
                            text=self.T.get("label_wave_position", "Pozycja i obrót"),
                            padding=(15, 10))
        lf.pack(fill="x", padx=10, pady=10)
        lf.columnconfigure(2, weight=1)

        # ROTATE
        cur_deg = int(round(math.degrees(_read_rotate(_wave_glsl()))))
        cur_deg = max(-180, min(180, cur_deg))

        ttk.Label(lf, text=self.T.get("label_rotation", "Obrót"),
                  width=12, anchor="w").grid(
            row=0, column=0, padx=(10, 5), pady=5, sticky="w")
        t = _tip(lf, "?", self.T.get("tooltip_rotate_wave",
                 "Obrót fali. -180 = zgodnie ze wskazówkami zegara, +180 = przeciwnie."))
        if t: t.grid(row=0, column=1, padx=5, pady=5)

        rot_slider = AccelSlider(lf, vmin=-180, vmax=180,
                                 value=cur_deg, step=1,
                                 on_change=self._on_rotate)
        rot_slider.grid(row=0, column=2, padx=10, pady=5, sticky="ew")
        ttk.Label(lf, text="°", width=4).grid(
            row=0, column=3, padx=(5, 10), pady=5, sticky="e")
        self._accel_sliders["ROTATE"] = rot_slider

        # CENTER_OFFSET_X / Y
        for row_idx, (key, lk, max_val, unit) in enumerate([
            ("CENTER_OFFSET_X", "label_offset_x", self._half_x, "px"),
            ("CENTER_OFFSET_Y", "label_offset_y", self._half_y, "px"),
        ], start=1):
            cur = int(current.get(key, 0))
            ttk.Label(lf, text=self.T.get(lk, key),
                      width=12, anchor="w").grid(
                row=row_idx, column=0, padx=(10, 5), pady=5, sticky="w")
            t = _tip(lf, "?", self.T.get(lk.replace("label_", "tooltip_"), ""))
            if t: t.grid(row=row_idx, column=1, padx=5, pady=5)

            slider = AccelSlider(lf, vmin=-max_val, vmax=max_val,
                                 value=cur, step=1,
                                 on_change=lambda v, k=key: self._on_offset(k, v))
            slider.grid(row=row_idx, column=2, padx=10, pady=5, sticky="ew")
            ttk.Label(lf, text=unit, width=4).grid(
                row=row_idx, column=3, padx=(5, 10), pady=5, sticky="e")
            self._accel_sliders[key] = slider

        # Odblokuj pełny zakres
        #self._unlock_var = tk.BooleanVar(value=False)
        #unlock_row = ttk.Frame(lf)
        #unlock_row.grid(row=4, column=0, columnspan=4,
        #                padx=10, pady=(6, 0), sticky="w")
        #ttk.Checkbutton(
        #    unlock_row,
        #    text=self.T.get("label_unlock_range", "Odblokuj pełny zakres"),
        #    variable=self._unlock_var,
        #    command=self._on_unlock_toggle,
        #).pack(side="left")
        #_tip(unlock_row, "?", self.T.get("tooltip_unlock_range",
        #     "Rozszerza zakres długości fali 3× i offsetów do przekątnej ekranu"))

    def _on_rotate(self, val):
        _write_rotate(_wave_glsl(), math.radians(float(val)))
        self._schedule_restart()

    def _on_offset(self, key, val):
        _write_int(_wave_glsl(), key, int(val))
        self._schedule_restart()

    def _on_unlock_toggle(self):
        unlocked = self._unlock_var.get()
        diag = self._diag
        s = self._accel_sliders.get("WAVE_LENGTH")
        if s: s.set_range(0, int(diag * 3.0) if unlocked else diag)
        sx = self._accel_sliders.get("CENTER_OFFSET_X")
        if sx: sx.set_range(-(diag if unlocked else self._half_x),
                             diag if unlocked else self._half_x)
        sy = self._accel_sliders.get("CENTER_OFFSET_Y")
        if sy: sy.set_range(-(diag if unlocked else self._half_y),
                             diag if unlocked else self._half_y)

    # ── Wygładzanie ───────────────────────────────────────────────────────────

    def _build_smooth(self, parent, current):
        lf = ttk.LabelFrame(parent,
                            text=self.T.get("section_smoothing", "Wygładzanie"),
                            padding=(15, 10))
        lf.pack(fill="x", padx=10, pady=10)
        lf.columnconfigure(2, weight=1)

        mapping = {
            "setgravitystep":  ("label_gravity",      "tooltip_gravity"),
            "setsmoothfactor": ("label_smooth_factor", "tooltip_smooth_factor"),
            "setavgframes":    ("label_avg_frames",    "tooltip_avg_frames"),
            "setfftscale":     ("label_fft_scale",     "tooltip_fft_scale"),
            "setfftcutoff":    ("label_bass_cutoff",   "tooltip_bass_cutoff"),
        }

        for idx, p in enumerate(SMOOTH_PARAMS):
            lk, tk_ = mapping.get(p[0], (None, None))
            label   = self.T.get(lk, p[1]) if lk else p[1]
            tooltip = self.T.get(tk_, p[7]) if tk_ else p[7]
            self._float_row(lf, p[0], label, p[2], p[3],
                            float(current.get(p[0], p[4])),
                            p[6], tooltip, idx)

        ttk.Label(lf, text=self.T.get("audio_affects_all",
                                       "⚠ Wpływa na wszystkie moduły")).grid(
            row=len(SMOOTH_PARAMS), column=0, columnspan=4,
            padx=10, pady=(4, 0), sticky="w")

    # ── Profile ───────────────────────────────────────────────────────────────

    def _build_profiles(self, parent):
        lf = ttk.LabelFrame(parent,
                            text=self.T.get("section_profiles_wave", "Shader profiles wave"),
                            padding=(15, 10))
        lf.pack(fill="x", padx=10, pady=10)

        profiles = get_shader_profiles_for_module("wave")
        names    = sorted(profiles.keys())
        self.profile_var = tk.StringVar()
        self.profile_cb  = ttk.Combobox(lf, textvariable=self.profile_var,
                                        values=names, state="readonly")
        self.profile_cb.pack(fill="x", pady=(0, 3))
        if names: self.profile_cb.current(0)

        ttk.Label(lf, text=self.T.get("label_profiles_hint_wave",
                                       "Kształt (kolory bez zmian)")).pack(anchor="w")

        btn_row = ttk.Frame(lf)
        btn_row.pack(fill="x", pady=(4, 0))
        ttk.Button(btn_row, text=self.T.get("btn_apply", "Zastosuj"),
                   command=self._apply_profile,
                   style="Accent.TButton").pack(side="left", expand=True,
                                                fill="x", padx=(0, 2))
        ttk.Button(btn_row, text=self.T.get("btn_save_new", "Zapisz nowy"),
                   command=self._save_profile).pack(side="left", expand=True,
                                                     fill="x", padx=(0, 2))
        ttk.Button(btn_row, text=self.T.get("btn_delete", "Usuń"),
                   command=self._delete_profile).pack(side="left")

        ttk.Button(lf, text=self.T.get("btn_reset_shader_wave", "Reset szadera wave"),
                   command=self._reset_shader,
                   style="Accent.TButton").pack(fill="x", pady=(4, 0))

    # ── Wiersze suwaków (grid) ────────────────────────────────────────────────

    def _int_row(self, parent, key, label, vmin, vmax, value, unit, tooltip, row_idx):
        var = tk.IntVar(value=value)
        self.vars[key] = var

        ttk.Label(parent, text=label, width=12, anchor="w").grid(
            row=row_idx, column=0, padx=(10, 5), pady=5, sticky="w")
        t = _tip(parent, "?", tooltip)
        if t: t.grid(row=row_idx, column=1, padx=5, pady=5)

        def on_change(v):
            v = self._clamp_thickness(key, int(round(v)))
            var.set(v)
            self._write_shape(key, v)

        slider = AccelSlider(parent, vmin=vmin, vmax=vmax, value=value,
                             step=1, on_change=on_change)
        slider.grid(row=row_idx, column=2, padx=10, pady=5, sticky="ew")
        ttk.Label(parent, text=unit if unit else " ", width=4).grid(
            row=row_idx, column=3, padx=(5, 10), pady=5, sticky="e")
        self._accel_sliders[key] = slider

    def _float_row(self, parent, key, label, vmin, vmax, value, step, tooltip, row_idx):
        dec = _decimals(step)
        var = tk.DoubleVar(value=value)
        self.vars[key] = var

        ttk.Label(parent, text=label, width=12, anchor="w").grid(
            row=row_idx, column=0, padx=(10, 5), pady=5, sticky="w")
        t = _tip(parent, "?", tooltip)
        if t: t.grid(row=row_idx, column=1, padx=5, pady=5)

        def on_change(v):
            var.set(v)
            self._debounce_smooth(key, v)

        slider = AccelSlider(parent, vmin=vmin, vmax=vmax, value=value,
                             step=step, is_float=True, decimals=dec,
                             on_change=on_change)
        slider.grid(row=row_idx, column=2, padx=10, pady=5, sticky="ew")
        ttk.Label(parent, text=" ", width=4).grid(
            row=row_idx, column=3, padx=(5, 10), pady=5, sticky="e")
        self._accel_sliders[key] = slider

    def _clamp_thickness(self, key, value):
        # MIN nie może przekroczyć MAX
        if key == "MIN_THICKNESS" and "MAX_THICKNESS" in self.vars:
            mx = self.vars["MAX_THICKNESS"].get()
            if value > mx:
                # aktualizuj zmienną
                self.vars["MAX_THICKNESS"].set(value)
                # aktualizuj suwak
                self._accel_sliders["MAX_THICKNESS"].set(value)
                # zapisz do GLSL
                _write_defines(_wave_glsl(), {"MAX_THICKNESS": value}, SHAPE_PARAMS)

        # MAX nie może spaść poniżej MIN
        elif key == "MAX_THICKNESS" and "MIN_THICKNESS" in self.vars:
            mn = self.vars["MIN_THICKNESS"].get()
            if value < mn:
                self.vars["MIN_THICKNESS"].set(value)
                self._accel_sliders["MIN_THICKNESS"].set(value)
                _write_defines(_wave_glsl(), {"MIN_THICKNESS": value}, SHAPE_PARAMS)

        return value


    # ── Zapis ─────────────────────────────────────────────────────────────────

    def _write_shape(self, key, value):
        _write_defines(_wave_glsl(), {key: value}, SHAPE_PARAMS)
        self._schedule_restart()

    def _debounce_smooth(self, key, value):
        _write_smooth(_smooth_glsl(), {key: value})
        self._schedule_restart()

    def _schedule_restart(self):
        if hasattr(self, "_rjob"):
            try: self.app.root.after_cancel(self._rjob)
            except Exception: pass
        from gui.glava import glava_restart
        self._rjob = self.app.root.after(
            300, lambda: glava_restart(
                "wave",
                extra_flags=getattr(self.app, "extra_flags", "--desktop"),
                after_fn=self.app.update_status))

    def _apply_profile(self):
        name = self.profile_var.get()
        if not name: return
        profiles = get_shader_profiles_for_module("wave")
        if name not in profiles: return
        apply_params(profiles[name], self.app)
        self.app.rebuild_module_tab()
        from gui.glava import glava_restart
        glava_restart("wave", extra_flags=getattr(self.app, "extra_flags", "--desktop"),
                      after_fn=self.app.update_status)

    def _save_profile(self):
        name = simpledialog.askstring(
            self.T.get("dialog_profile_title", "Nowy profil"),
            self.T.get("dialog_profile_name", "Podaj nazwę profilu:"))
        if not name: return
        existing = get_shader_profiles_for_module("wave")
        if name in existing:
            if not messagebox.askyesno(
                    self.T.get("dialog_overwrite_title", "Nadpisać profil?"),
                    self.T.get("dialog_overwrite_msg",
                               "Profil '{}' już istnieje. Nadpisać?").format(name)):
                return
        save_shader_profile_for_module("wave", name, collect_params(self.app))
        self._refresh_cb()
        self.profile_var.set(name)

    def _delete_profile(self):
        name = self.profile_var.get()
        if name and messagebox.askyesno(
                "", self.T.get("dialog_delete_confirm",
                               "Czy na pewno usunąć profil") + f" '{name}'?"):
            delete_shader_profile_for_module("wave", name)
            self._refresh_cb()

    def _refresh_cb(self):
        names = sorted(get_shader_profiles_for_module("wave").keys())
        self.profile_cb["values"] = names
        if names: self.profile_cb.current(0)

    def _reset_shader(self):
        if messagebox.askyesno(
                self.T.get("section_reset", "Reset"),
                self.T.get("confirm_reset_wave", "Przywrócić domyślny shader wave?")):
            reset_shader(self.app)
            self.app.rebuild_module_tab()
            from gui.glava import glava_restart
            glava_restart("wave", extra_flags=getattr(self.app, "extra_flags", "--desktop"),
                          after_fn=self.app.update_status)


# ─── _tip ────────────────────────────────────────────────────────────────────

def _tip(parent, label, text):
    if not text: return None
    lbl = ttk.Label(parent, text=label, cursor="question_arrow")
    tip_window = [None]
    def show(e):
        x = lbl.winfo_rootx() + 20
        y = lbl.winfo_rooty() + 20
        tw = tk.Toplevel(lbl)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.configure(bg="")
        ttk.Label(tw, text=text, justify="left").pack(padx=5, pady=2)
        tip_window[0] = tw
    def hide(e):
        if tip_window[0]: tip_window[0].destroy(); tip_window[0] = None
    lbl.bind("<Enter>", show)
    lbl.bind("<Leave>", hide)
    return lbl


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _decimals(step):
    s = str(step)
    return len(s.rstrip("0").split(".")[-1]) if "." in s else 0


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
        content = re.sub(rf'^#define\s+{key}\s+\S+\n?', '',
                         content, flags=re.MULTILINE)
        content = content.rstrip() + f"\n#define {key} {val}\n"
    with open(path, "w") as f: f.write(content)

def _read_int(path, key, default=0):
    if not os.path.exists(path): return default
    with open(path) as f: content = f.read()
    m = re.search(rf'^#define\s+{key}\s+(-?\d+)', content, re.MULTILINE)
    if m:
        try: return int(m.group(1))
        except ValueError: pass
    return default

def _write_int(path, key, value):
    if not os.path.exists(path): return
    with open(path) as f: content = f.read()
    content = re.sub(rf'^#define\s+{key}\s+-?\d+\n?', '',
                     content, flags=re.MULTILINE)
    content = content.rstrip() + f"\n#define {key} {int(value)}\n"
    with open(path, "w") as f: f.write(content)

def _read_rotate(path):
    if not os.path.exists(path): return 0.0
    with open(path) as f: content = f.read()
    m = re.search(r'^#define\s+ROTATE\s+([0-9.eE+\-]+)', content, re.MULTILINE)
    if m:
        try: return float(m.group(1))
        except ValueError: pass
    return 0.0

def _write_rotate(path, rad):
    if not os.path.exists(path): return
    with open(path) as f: content = f.read()
    val = f"{rad:.6f}"
    content = re.sub(r'^#define\s+ROTATE\s+[0-9.eE+\-]+\n?', '',
                     content, flags=re.MULTILINE)
    content = content.rstrip() + f"\n#define ROTATE {val}\n"
    with open(path, "w") as f: f.write(content)

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
    with open(path, "r") as f: 
        content = f.read()
    
    modified = False
    for key, val in params.items():
        if key not in keys: continue
        
        p = next(x for x in SMOOTH_PARAMS if x[0] == key)
        dec = _decimals(p[6])
        sv = str(int(val)) if key == "setavgframes" else f"{float(val):.{dec}f}"
        
        # Poprawiony wzorzec: szuka #request, potem klucza, potem dowolnych znaków do końca linii
        pattern = rf'^#request\s+{key}\s+.*$'
        replacement = f"#request {key} {sv}"
        
        if re.search(pattern, content, flags=re.MULTILINE):
            # Jeśli klucz istnieje, podmień go
            content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
        else:
            # Jeśli klucza nie ma, dodaj go na końcu
            content = content.rstrip() + f"\n{replacement}\n"
        modified = True

    if modified:
        with open(path, "w") as f: 
            f.write(content)
