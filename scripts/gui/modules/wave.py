# =============================================================================
# gui/modules/wave.py
#
# Wzorzec GUI: bars.py v5 (grid w LabelFrame, ttk.*, Forest-ttk-theme)
# =============================================================================
import os, math
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from ..core import CONFIG_DIR, GLAVA_DIR, RC_GLSL, SMOOTH_PARAMS
from ..widgets import AccelSlider
from . import glsl_io
from ..core import get_shader_profiles_for_module
from .base import BaseParamWidget

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

FLAG_PARAMS = []
ALL_DEFINE_KEYS = {p[0] for p in SHAPE_PARAMS} | {
    "ROTATE", "WAVE_LENGTH", "CENTER_OFFSET_X", "CENTER_OFFSET_Y"}


def build_params(parent, app, T):
    WaveParamWidget(parent, app, T).build()


def collect_params(app):
    p = glsl_io.read_defines(_wave_glsl(), SHAPE_PARAMS)
    raw = glsl_io.read_raw(_wave_glsl())
    try:    p["WAVE_LENGTH"]     = int(raw.get("WAVE_LENGTH", 0))
    except: p["WAVE_LENGTH"]     = 0
    try:    p["CENTER_OFFSET_X"] = int(raw.get("CENTER_OFFSET_X", 0))
    except: p["CENTER_OFFSET_X"] = 0
    try:    p["CENTER_OFFSET_Y"] = int(raw.get("CENTER_OFFSET_Y", 0))
    except: p["CENTER_OFFSET_Y"] = 0
    try:    p["ROTATE"]          = float(raw.get("ROTATE", "0.0"))
    except: p["ROTATE"]          = 0.0
    p.update(glsl_io.read_smooth(_smooth_glsl(), SMOOTH_PARAMS))
    return p


def apply_params(params, app):
    glsl_io.write_defines(_wave_glsl(), params, SHAPE_PARAMS)
    for key in ("WAVE_LENGTH", "CENTER_OFFSET_X", "CENTER_OFFSET_Y"):
        if key in params:
            glsl_io.write_define_int(_wave_glsl(), key, int(params[key]))
    if "ROTATE" in params:
        glsl_io.write_define_raw(_wave_glsl(), "ROTATE", f"{float(params['ROTATE']):.6f}")
    glsl_io.write_smooth(_smooth_glsl(), params, SMOOTH_PARAMS)


def reset_shader(app):
    import shutil
    tmpl = _wave_tmpl()
    live = _wave_1frag()
    if os.path.exists(tmpl):
        os.makedirs(os.path.dirname(live), exist_ok=True)
        shutil.copy2(tmpl, live)
    defaults = {p[0]: p[4] for p in SHAPE_PARAMS}
    glsl_io.write_defines(_wave_glsl(), defaults, SHAPE_PARAMS)
    for key in ("WAVE_LENGTH", "CENTER_OFFSET_X", "CENTER_OFFSET_Y"):
        glsl_io.write_define_int(_wave_glsl(), key, 0)
    glsl_io.write_define_raw(_wave_glsl(), "ROTATE", "0.000000")


class WaveParamWidget(BaseParamWidget):
    MODULE_NAME  = "wave"
    SHAPE_PARAMS = SHAPE_PARAMS

    def _init_extra(self):
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

    def build_left(self, parent, current):
        self._build_shape(parent, current)
        self._build_position(parent, current)

    def build_right(self, parent, current):
        self._build_smooth(parent, current)
        self._build_profiles(parent)
    def _build_shape(self, parent, current):
        title = self.T.get("section_shape", "Kształt")
        lf = self._detachable_lf(parent, title, self._build_shape, current)
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
        t = glsl_io.tip(lf, "?", self.T.get("tooltip_wave_length",
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
        glsl_io.write_define_int(_wave_glsl(), "WAVE_LENGTH", int(val))
        self._schedule_restart()

    # ── Pozycja i rotacja ─────────────────────────────────────────────────────

    def _build_position(self, parent, current):
        title = self.T.get("section_position", "Pozycja")
        lf = self._detachable_lf(parent, title, self._build_position, current)
        lf.pack(fill="x", padx=10, pady=10)
        lf.columnconfigure(2, weight=1)

        # ROTATE
        cur_deg = int(round(math.degrees(float(glsl_io.read_raw(_wave_glsl()).get("ROTATE", "0.0")))))
        cur_deg = max(-180, min(180, cur_deg))

        ttk.Label(lf, text=self.T.get("label_rotation", "Obrót"),
                  width=12, anchor="w").grid(
            row=0, column=0, padx=(10, 5), pady=5, sticky="w")
        t = glsl_io.tip(lf, "?", self.T.get("tooltip_rotate_wave",
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
            t = glsl_io.tip(lf, "?", self.T.get(lk.replace("label_", "tooltip_"), ""))
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
        #glsl_io.tip(unlock_row, "?", self.T.get("tooltip_unlock_range",
        #     "Rozszerza zakres długości fali 3× i offsetów do przekątnej ekranu"))

    def _on_rotate(self, val):
        glsl_io.write_define_raw(_wave_glsl(), "ROTATE", f"{math.radians(float(val)):.6f}")
        self._schedule_restart()

    def _on_offset(self, key, val):
        glsl_io.write_define_int(_wave_glsl(), key, int(val))
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
        title = self.T.get("section_smoothing", "Wygładzanie")
        lf = self._detachable_lf(parent, title, self._build_smooth, current)
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
        t = glsl_io.tip(parent, "?", tooltip)
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
        dec = glsl_io.decimals(step)
        var = tk.DoubleVar(value=value)
        self.vars[key] = var

        ttk.Label(parent, text=label, width=12, anchor="w").grid(
            row=row_idx, column=0, padx=(10, 5), pady=5, sticky="w")
        t = glsl_io.tip(parent, "?", tooltip)
        if t: t.grid(row=row_idx, column=1, padx=5, pady=5)

        def on_change(v):
            var.set(v)
            self._debounce(key, v, "smooth")

        slider = AccelSlider(parent, vmin=vmin, vmax=vmax, value=value,
                             step=step, is_float=True, decimals=dec,
                             on_change=on_change)
        slider.grid(row=row_idx, column=2, padx=10, pady=5, sticky="ew")
        ttk.Label(parent, text=" ", width=4).grid(
            row=row_idx, column=3, padx=(5, 10), pady=5, sticky="e")
        self._accel_sliders[key] = slider

    def _clamp_thickness(self, key, value):
        if key == "MIN_THICKNESS" and "MAX_THICKNESS" in self.vars:
            mx = self.vars["MAX_THICKNESS"].get()
            if value > mx:
                self.vars["MAX_THICKNESS"].set(value)
                self._accel_sliders["MAX_THICKNESS"].set(value)
                glsl_io.write_defines(_wave_glsl(), {"MAX_THICKNESS": value}, SHAPE_PARAMS)
        elif key == "MAX_THICKNESS" and "MIN_THICKNESS" in self.vars:
            mn = self.vars["MIN_THICKNESS"].get()
            if value < mn:
                self.vars["MIN_THICKNESS"].set(value)
                self._accel_sliders["MIN_THICKNESS"].set(value)
                glsl_io.write_defines(_wave_glsl(), {"MIN_THICKNESS": value}, SHAPE_PARAMS)
        return value


    # ── Zapis ─────────────────────────────────────────────────────────────────

    def _write_shape(self, key, value):
        glsl_io.write_defines(_wave_glsl(), {key: value}, SHAPE_PARAMS)
        self._schedule_restart()

    def _reset_shader(self):
        if messagebox.askyesno(
                self.T.get("section_reset", "Reset"),
                self.T.get("confirm_reset_wave", "Przywrócić domyślny shader wave?")):
            reset_shader(self.app)
            self.app.rebuild_module_tab()
            from gui.glava import glava_restart
            glava_restart("wave", extra_flags=getattr(self.app, "extra_flags", "--desktop"),
                          after_fn=self.app.update_status)
