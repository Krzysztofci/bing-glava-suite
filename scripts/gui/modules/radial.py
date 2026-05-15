# =============================================================================
# gui/modules/radial.py  v3
#
# Plik konfiguracyjny: ~/.config/glava/radial.glsl
# Wygładzanie:         ~/.config/glava/smooth_parameters.glsl
#
# Wzorzec GUI: bars.py v5 (grid w LabelFrame, ttk.*, Forest-ttk-theme)
# =============================================================================

import os, math
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from ..core import CONFIG_DIR, GLAVA_DIR, RC_GLSL, SMOOTH_PARAMS
from ..widgets import SimpleSlider
from ..geometry import get_screen_info
from . import glsl_io
from ..core import get_shader_profiles_for_module
from .base import BaseParamWidget


# (klucz, etykieta, min, max, domyślna, jednostka, tooltip)
SHAPE_INT_PARAMS = [
    ("C_RADIUS",  "Promień okręgu",   20,  600, 128, "px",
     "Promień bazowego okręgu wizualizacji w pikselach"),
    ("C_LINE",    "Linia okręgu",      0,   50,   2, "px",
     "Grubość linii rysującej środkowy okrąg\n0 = wyłączona"),
    ("NBARS",     "Liczba słupków",   10,  400, 160, "",
     "Liczba słupków radialnych\nParzyste wartości dają najlepszy efekt"),
    ("AMPLIFY",   "Wzmocnienie",       50, 800, 300, "",
     "Wzmocnienie amplitudy sygnału audio"),
    ("GRADIENT",  "Wypełnienie koła",   0, 100,   0, "%",
     "Szybkość przejścia gradientu kolorów w pikselach"),
]

# (klucz, etykieta, min, max, domyślna, krok, tooltip)
SHAPE_FLOAT_PARAMS = [
    ("BAR_WIDTH",        "Szerokość słupka",  1.0, 20.0, 4.5, 0.5,
     "Szerokość pojedynczego słupka w pikselach"),
    ("BAR_ALIAS_FACTOR", "Ostrość słupków",   0.5,  5.0, 1.2, 0.1,
     "Ostrość krawędzi słupków\nWymaga opacity: xroot"),
    ("C_ALIAS_FACTOR",   "Ostrość okręgu",    0.5,  5.0, 1.8, 0.1,
     "Ostrość krawędzi środkowego okręgu\nWymaga opacity: xroot"),
]

# (klucz, etykieta, min, max, domyślna, krok, tooltip)

FLAG_PARAMS = [
    ("INVERT", "Zamień kanały L/R", "label_swap_lr",
     "Zamienia lewy i prawy kanał audio"),
]


# ─── API ─────────────────────────────────────────────────────────────────────

def build_params(parent, app, T):
    RadialParamWidget(parent, app, T).build()


def collect_params(app):
    raw = glsl_io.read_raw(app.active_instance.module_glsl('radial'))
    p = {}
    for key, _, _, _, default, _, _ in SHAPE_INT_PARAMS:
        try:    p[key] = int(raw.get(key, default))
        except: p[key] = default
    for key, _, _, _, default, _, _ in SHAPE_FLOAT_PARAMS:
        try:    p[key] = float(raw.get(key, default))
        except: p[key] = default
    rotate_raw = raw.get("ROTATE", "(PI / 2)")
    p["ROTATE_DEG"] = _rotate_to_deg(rotate_raw)
    try:    p["CENTER_OFFSET_X"] = int(raw.get("CENTER_OFFSET_X", 0))
    except: p["CENTER_OFFSET_X"] = 0
    try:    p["CENTER_OFFSET_Y"] = int(raw.get("CENTER_OFFSET_Y", 0))
    except: p["CENTER_OFFSET_Y"] = 0
    p.update(glsl_io.read_flag_defines(app.active_instance.module_glsl('radial'), FLAG_PARAMS))
    p.update(glsl_io.read_smooth(app.active_instance.smooth_glsl, SMOOTH_PARAMS))
    return p


def apply_params(params, app):
    int_keys = {p[0] for p in SHAPE_INT_PARAMS} | {"CENTER_OFFSET_X", "CENTER_OFFSET_Y"}
    for key, val in params.items():
        if key in int_keys:
            glsl_io.write_define_int(app.active_instance.module_glsl('radial'), key, int(val))
    float_keys = {p[0] for p in SHAPE_FLOAT_PARAMS}
    for key, val in params.items():
        if key in float_keys:
            step = next(p[5] for p in SHAPE_FLOAT_PARAMS if p[0] == key)
            glsl_io.write_define_float(app.active_instance.module_glsl('radial'), key, float(val), step)
    if "ROTATE_DEG" in params:
        glsl_io.write_define_raw(app.active_instance.module_glsl('radial'), "ROTATE", _deg_to_rotate(int(params["ROTATE_DEG"])))
    glsl_io.write_flag_defines(app.active_instance.module_glsl('radial'), params, FLAG_PARAMS)
    glsl_io.write_smooth(app.active_instance.smooth_glsl, params, SMOOTH_PARAMS)


def reset_shader(app):
    import shutil
    tmpl, live = app.active_instance.module_tmpl('radial'), app.active_instance.module_frag('radial')
    if os.path.exists(tmpl):
        os.makedirs(os.path.dirname(live), exist_ok=True)
        shutil.copy2(tmpl, live)
    for key, _, _, _, default, _, _ in SHAPE_INT_PARAMS:
        glsl_io.write_define_int(app.active_instance.module_glsl('radial'), key, default)
    for key, _, _, _, default, step, _ in SHAPE_FLOAT_PARAMS:
        glsl_io.write_define_float(app.active_instance.module_glsl('radial'), key, default, step)
    glsl_io.write_define_raw(app.active_instance.module_glsl('radial'), "ROTATE", "(PI / 2)")
    glsl_io.write_define_int(app.active_instance.module_glsl('radial'), "CENTER_OFFSET_X", 0)
    glsl_io.write_define_int(app.active_instance.module_glsl('radial'), "CENTER_OFFSET_Y", 0)
    glsl_io.write_flag_defines(app.active_instance.module_glsl('radial'), {p[0]: 0 for p in FLAG_PARAMS}, FLAG_PARAMS)


# ─── Widget ───────────────────────────────────────────────────────────────────

class RadialParamWidget(BaseParamWidget):
    MODULE_NAME = "radial"

    def _init_extra(self):
        try:
            si = get_screen_info()
            self._sw, self._sh = si[0], si[1]
        except Exception:
            self._sw, self._sh = 1600, 900

    def build_left(self, parent, current):
        self._build_shape(parent, current)
        self._build_position(parent, current)

    def build_right(self, parent, current):
        self._build_smooth(parent, current)
        self._build_flags(parent, current)
        self._build_profiles(parent)
    def _build_shape(self, parent, current):
        title = self.T.get("section_shape", "Kształt")
        lf = self._detachable_lf(parent, title, self._build_shape, current)
        lf.pack(fill="x", padx=10, pady=10)
        lf.columnconfigure(2, weight=1)

        mapping = {
            "C_RADIUS":         "label_radius",
            "C_LINE":           "label_circle_line",
            "NBARS":            "label_bar_count",
            "AMPLIFY":          "label_gain",
            "GRADIENT":         "label_radial_fill",
            "BAR_WIDTH":        "label_bar_width",
            "BAR_ALIAS_FACTOR": "label_bar_sharp",
            "C_ALIAS_FACTOR":   "label_circle_sharp",
        }

        row_idx = 0
        for p in SHAPE_INT_PARAMS:
            p_list = list(p)
            json_key = mapping.get(p[0])
            if json_key:
                p_list[1] = self.T.get(json_key, p[1])
                p_list[6] = self.T.get(json_key.replace("label_", "tooltip_"), p[6])
            self._int_row(lf, tuple(p_list), current, row_idx)
            row_idx += 1

        for p in SHAPE_FLOAT_PARAMS:
            p_list = list(p)
            json_key = mapping.get(p[0])
            if json_key:
                p_list[1] = self.T.get(json_key, p[1])
                p_list[6] = self.T.get(json_key.replace("label_", "tooltip_"), p[6])
            self._float_row(lf, tuple(p_list), current, row_idx)
            row_idx += 1

        # ROTATE
        cur_rot = int(current.get("ROTATE_DEG", 90))
        self.rotate_var = tk.IntVar(value=cur_rot)

        ttk.Label(lf, text=self.T.get("label_rotation", "Rotation"),
                  width=12, anchor="w").grid(
            row=row_idx, column=0, padx=(10, 5), pady=5, sticky="w")
        t = glsl_io.tip(lf, "?", self.T.get("tooltip_rotate", "Obrót wizualizacji"))
        if t: t.grid(row=row_idx, column=1, padx=5, pady=5)

        def on_rot_change(v):
            self.rotate_var.set(int(round(v)))
            self._write_rotate()

        rot_slider = SimpleSlider(lf, vmin=0, vmax=360,
                                 value=cur_rot, step=1,
                                 on_change=on_rot_change)
        rot_slider.grid(row=row_idx, column=2, padx=10, pady=5, sticky="ew")
        ttk.Label(lf, text="°", width=4).grid(
            row=row_idx, column=3, padx=(5, 10), pady=5, sticky="e")

    # ── Pozycja ───────────────────────────────────────────────────────────────

    def _build_position(self, parent, current):
        title = self.T.get("section_position", "Pozycja")
        lf = self._detachable_lf(parent, title, self._build_position, current)
        lf.pack(fill="x", padx=10, pady=10)
        lf.columnconfigure(2, weight=1)

        max_x = self._sw // 2
        max_y = self._sh // 2

        for row_idx, (key, lang_key, default, max_val, unit) in enumerate([
            ("CENTER_OFFSET_X", "label_offset_x", 0, max_x, "px"),
            ("CENTER_OFFSET_Y", "label_offset_y", 0, max_y, "px"),
        ]):
            cur = int(current.get(key, default))
            var = tk.IntVar(value=cur)
            self.vars[key] = var

            label_text   = self.T.get(lang_key, lang_key)
            tooltip_text = self.T.get(lang_key.replace("label_", "tooltip_"), "")

            ttk.Label(lf, text=label_text, width=12, anchor="w").grid(
                row=row_idx, column=0, padx=(10, 5), pady=5, sticky="w")
            t = glsl_io.tip(lf, "?", tooltip_text)
            if t: t.grid(row=row_idx, column=1, padx=5, pady=5)

            def on_change(v, k=key, sv=var):
                sv.set(int(round(v)))
                self._debounce_int(k, int(round(v)))

            slider = SimpleSlider(lf, vmin=-max_val, vmax=max_val,
                                 value=cur, step=1,
                                 on_change=on_change)
            slider.grid(row=row_idx, column=2, padx=10, pady=5, sticky="ew")
            ttk.Label(lf, text=unit, width=4).grid(
                row=row_idx, column=3, padx=(5, 10), pady=5, sticky="e")

    # ── Przełączniki ──────────────────────────────────────────────────────────

    def _build_flags(self, parent, current):
        title = self.T.get("section_switches", "Przełączniki")
        lf = self._detachable_lf(parent, title, self._build_flags, current)
        lf.pack(fill="x", padx=10, pady=10)

        # Konfiguracja kolumn, żeby pasowały do tych z suwaków
        lf.columnconfigure(2, weight=1)

        for idx, (key, label, lang_key, tooltip) in enumerate(FLAG_PARAMS):
            raw = current.get(key, 0)
            var = tk.BooleanVar(value=bool(int(raw)))
            self.vars[key] = var

            translated_label = self.T.get(lang_key, label)
            tip_key = lang_key.replace("label_", "tooltip_")
            translated_tip = self.T.get(tip_key, tooltip)

            # Checkbox ląduje TYLKO w kolumnie 0. 
            # Ustawiamy width=20, żeby był tak samo szeroki jak etykiety suwaków wyżej.
            ttk.Checkbutton(
                lf,
                text=translated_label,
                width=18, 
                variable=var,
                command=lambda k=key, v=var: self._write_flag(k, v)
            ).grid(row=idx, column=0, sticky="w", pady=2, padx=(10, 0))
            
            # Pytajnik ląduje w kolumnie 1. 
            # Dzięki temu będzie w idealnym pionie z pytajnikami suwaków.
            if translated_tip:
                t = glsl_io.tip(lf, "?", translated_tip)
                if t:
                    # padx=(0, 5) przyciąga go do tekstu po lewej
                    t.grid(row=idx, column=1, sticky="w", padx=(0, 5), pady=2)

    # ── Wygładzanie ───────────────────────────────────────────────────────────

    def _build_smooth(self, parent, current):
        title = self.T.get("section_smoothing", "Wygładzanie")
        lf = self._detachable_lf(parent, title, self._build_smooth, current)
        lf.pack(fill="x", padx=10, pady=10)
        lf.columnconfigure(2, weight=1)

        mapping = {
            "setgravitystep":  "label_gravity",
            "setsmoothfactor": "label_smooth_factor",
            "setavgframes":    "label_avg_frames",
            "setfftscale":     "label_fft_scale",
            "setfftcutoff":    "label_bass_cutoff",
        }

        for idx, p in enumerate(SMOOTH_PARAMS):
            p_list = list(p)
            lang_key = mapping.get(p[0])
            if lang_key:
                p_list[1] = self.T.get(lang_key, p[1])
                p_list[7] = self.T.get(lang_key.replace("label_", "tooltip_"), p[7])
            self._smooth_row(lf, tuple(p_list), current, idx)

    # ── Profile ───────────────────────────────────────────────────────────────

    def _build_profiles(self, parent):
        lf = ttk.LabelFrame(parent,
                            text=self.T.get("section_profiles_radial", "Shader profiles radial"),
                            padding=(15, 10))
        lf.pack(fill="x", padx=10, pady=10)

        profiles = get_shader_profiles_for_module("radial")
        names    = sorted(profiles.keys())
        self.profile_var = tk.StringVar()
        self.profile_cb  = ttk.Combobox(lf, textvariable=self.profile_var,
                                        values=names, state="readonly")
        self.profile_cb.pack(fill="x", pady=(0, 3))
        if names: self.profile_cb.current(0)

        ttk.Label(lf, text=self.T.get("label_profiles_hint_radial",
                                       "Shape & smoothing (colors unchanged)")).pack(anchor="w")

        btn_row = ttk.Frame(lf)
        btn_row.pack(fill="x", pady=(4, 0))
        ttk.Button(btn_row, text=self.T.get("btn_apply", "Apply"),
                   command=self._apply_profile,
                   style="Accent.TButton").pack(side="left", expand=True,
                                                fill="x", padx=(0, 2))
        ttk.Button(btn_row, text=self.T.get("btn_save_new", "Save new"),
                   command=self._save_profile).pack(side="left", expand=True,
                                                     fill="x", padx=(0, 2))
        ttk.Button(btn_row, text=self.T.get("btn_delete", "Delete"),
                   command=self._delete_profile).pack(side="left")

        ttk.Button(lf, text=self.T.get("btn_reset_shader_radial", "Reset radial shader"),
                   command=self._reset_shader,
                   style="Accent.TButton").pack(fill="x", pady=(4, 0))

    # ── Wiersze suwaków (grid) ────────────────────────────────────────────────

    def _int_row(self, parent, param_def, current, row_idx):
        key, label, vmin, vmax, default, unit, tooltip = param_def
        cur = int(current.get(key, default))
        var = tk.IntVar(value=cur)
        self.vars[key] = var

        ttk.Label(parent, text=label, width=12, anchor="w").grid(
            row=row_idx, column=0, padx=(10, 5), pady=5, sticky="w")
        t = glsl_io.tip(parent, "?", tooltip)
        if t: t.grid(row=row_idx, column=1, padx=5, pady=5)

        def on_change(v, k=key):
            var.set(int(round(v)))
            self._debounce_int(k, int(round(v)))

        slider = SimpleSlider(parent, vmin=vmin, vmax=vmax, value=cur,
                             step=1, on_change=on_change)
        slider.grid(row=row_idx, column=2, padx=10, pady=5, sticky="ew")
        ttk.Label(parent, text=unit if unit else " ", width=4).grid(
            row=row_idx, column=3, padx=(5, 10), pady=5, sticky="e")

    def _float_row(self, parent, param_def, current, row_idx):
        key, label, vmin, vmax, default, step, tooltip = param_def
        cur = float(current.get(key, default))
        var = tk.DoubleVar(value=cur)
        self.vars[key] = var
        dec = glsl_io.decimals(step)

        ttk.Label(parent, text=label, width=12, anchor="w").grid(
            row=row_idx, column=0, padx=(10, 5), pady=5, sticky="w")
        t = glsl_io.tip(parent, "?", tooltip)
        if t: t.grid(row=row_idx, column=1, padx=5, pady=5)

        def on_change(v, k=key):
            var.set(v)
            self._debounce_float(k, float(v), step)

        slider = SimpleSlider(parent, vmin=vmin, vmax=vmax, value=cur,
                             step=step, is_float=True, decimals=dec,
                             on_change=on_change)
        slider.grid(row=row_idx, column=2, padx=10, pady=5, sticky="ew")
        ttk.Label(parent, text=" ", width=4).grid(
            row=row_idx, column=3, padx=(5, 10), pady=5, sticky="e")

    def _smooth_row(self, parent, param_def, current, row_idx):
        key, label, vmin, vmax, default, unit, step, tooltip = param_def
        try:    cur = float(current.get(key, default))
        except: cur = float(default)
        var = tk.DoubleVar(value=cur)
        self.vars[key] = var
        dec = glsl_io.decimals(step)

        ttk.Label(parent, text=label, width=12, anchor="w").grid(
            row=row_idx, column=0, padx=(10, 5), pady=5, sticky="w")
        t = glsl_io.tip(parent, "?", tooltip)
        if t: t.grid(row=row_idx, column=1, padx=5, pady=5)

        def on_change(v, k=key):
            var.set(v)
            self._debounce_smooth(k, float(v))

        slider = SimpleSlider(parent, vmin=vmin, vmax=vmax, value=cur,
                             step=step, is_float=True, decimals=dec,
                             on_change=on_change)
        slider.grid(row=row_idx, column=2, padx=10, pady=5, sticky="ew")
        ttk.Label(parent, text=" ", width=4).grid(
            row=row_idx, column=3, padx=(5, 10), pady=5, sticky="e")

    # ── Zapis ─────────────────────────────────────────────────────────────────

    def _debounce_int(self, key, value):
        glsl_io.write_define_int(self._glsl, key, int(value))
        self._schedule_restart()

    def _debounce_float(self, key, value, step):
        glsl_io.write_define_float(self._glsl, key, value, step)
        self._schedule_restart()

    def _debounce_smooth(self, key, value):
        p = next(x for x in SMOOTH_PARAMS if x[0] == key)
        step = p[6]
        dec = glsl_io.decimals(step)
        sv = str(int(value)) if key == "setavgframes" else f"{value:.{dec}f}"
        glsl_io.write_request(self._smooth_glsl, key, sv)
        self._schedule_restart()

    def _write_rotate(self):
        deg = int(self.rotate_var.get())
        glsl_io.write_define_raw(self._glsl, "ROTATE", _deg_to_rotate(deg))
        self._schedule_restart()

    def _write_flag(self, key, var):
        glsl_io.write_define_int(self._glsl, key, 1 if var.get() else 0)
        self._schedule_restart()

    def _reset_shader(self):
        if messagebox.askyesno(
                self.T.get("section_reset", "Reset"),
                self.T.get("confirm_reset_radial", "Restore default radial shader?")):
            reset_shader(self.app)
            self.app.rebuild_module_tab()
            if hasattr(self.app, 'restart_active_instance'):
                self.app.restart_active_instance(module="radial", after_fn=self.app.update_status)
            else:
                from gui.glava import glava_restart
                glava_restart("radial", extra_flags=getattr(self.app, "extra_flags", "--desktop"),
                              after_fn=self.app.update_status)


# ─── Helpers (rotation) ─────────────────────────────────────────────────────

def _rotate_to_deg(glsl_val):
    v = glsl_val.strip().replace(" ", "")
    sym = {"0": 0, "(PI/2)": 90, "PI": 180, "(3*PI/2)": 270}
    if v in sym:
        return sym[v]
    try:
        return round(float(v) * 180.0 / 3.14159265359) % 360
    except ValueError:
        return 90

def _deg_to_rotate(deg):
    return f"{deg * 3.14159265359 / 180.0:.6f}"

