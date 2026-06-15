# =============================================================================
# gui/modules/circle.py
#
# Wzorzec GUI: bars.py v5 (grid w LabelFrame, ttk.*, Forest-ttk-theme)
# =============================================================================
import os
import tkinter as tk
from tkinter import messagebox, ttk

from ..core import SMOOTH_PARAMS, get_shader_profiles_for_module
from ..widgets import SimpleSlider
from . import glsl_io
from .base import BaseParamWidget

# (klucz, etykieta, min, max, domyślna, jednostka, tooltip)
SHAPE_PARAMS = [
    ("C_RADIUS", "Promień okręgu",  50, 400, 128, "px",
     "Promień bazowego okręgu w pikselach"),
    ("C_LINE",   "Grubość linii",    0,  20,   2, "px",
     "Grubość linii wizualizacji\nSteruje też szerokością obszaru rysowania"),
    ("AMPLIFY",  "Wzmocnienie",     50, 800, 150, "",
     "Wzmocnienie amplitudy sygnału audio"),
]

# (klucz, etykieta, min, max, domyślna, jednostka, krok, tooltip)

# C_SMOOTH niezaimplementowane w shaderze — ukryte do czasu wdrożenia
_UNIMPLEMENTED = {"C_SMOOTH"}

# (klucz, etykieta, tooltip)
FLAG_PARAMS = [
    ("C_FILL",   "Wypełnij wnętrze",
     "Wypełnia przestrzeń między linią a wewnętrznym okręgiem"),
    ("C_SMOOTH", "Wygładzanie (post-proc)",
     "Wygładzanie obrazu post-processing\nDziała tylko z opacity: xroot"),
    ("INVERT",   "Zamień kanały L/R",
     "Zamienia lewy i prawy kanał audio"),
]

ALL_DEFINE_KEYS = {p[0] for p in SHAPE_PARAMS} | {p[0] for p in FLAG_PARAMS}


def build_params(parent, app, T):
    CircleParamWidget(parent, app, T).build()


def collect_params(app):
    p = {}
    p.update(glsl_io.read_defines(app.active_instance.module_glsl('circle'), SHAPE_PARAMS))
    p.update(glsl_io.read_flag_defines(app.active_instance.module_glsl('circle'), FLAG_PARAMS))
    p.update(glsl_io.read_smooth(app.active_instance.smooth_glsl, SMOOTH_PARAMS))
    raw = glsl_io.read_raw(app.active_instance.module_glsl('circle'))
    rotate_raw = raw.get("ROTATE", "(PI / 2)")
    p["ROTATE_DEG"] = _rotate_to_deg(rotate_raw)
    try:    p["CENTER_OFFSET_X"] = int(raw.get("CENTER_OFFSET_X", 0))
    except: p["CENTER_OFFSET_X"] = 0
    try:    p["CENTER_OFFSET_Y"] = int(raw.get("CENTER_OFFSET_Y", 0))
    except: p["CENTER_OFFSET_Y"] = 0
    return p


def apply_params(params, app):
    glsl_io.write_defines(app.active_instance.module_glsl('circle'), params, SHAPE_PARAMS)
    glsl_io.write_flag_defines(app.active_instance.module_glsl('circle'), params, FLAG_PARAMS)
    glsl_io.write_smooth(app.active_instance.smooth_glsl, params, SMOOTH_PARAMS)
    if "ROTATE_DEG" in params:
        glsl_io.write_define_raw(app.active_instance.module_glsl('circle'), "ROTATE", _deg_to_rotate(int(params["ROTATE_DEG"])))
    for key in ("CENTER_OFFSET_X", "CENTER_OFFSET_Y"):
        if key in params:
            glsl_io.write_define_raw(app.active_instance.module_glsl('circle'), key, int(params[key]))


def reset_shader(app):
    import shutil
    tmpl = app.active_instance.module_tmpl('circle')
    live = app.active_instance.module_frag('circle')
    if os.path.exists(tmpl):
        os.makedirs(os.path.dirname(live), exist_ok=True)
        shutil.copy2(tmpl, live)
    defaults = {p[0]: p[4] for p in SHAPE_PARAMS}
    defaults.update({p[0]: 0 for p in FLAG_PARAMS})
    defaults["C_SMOOTH"] = 1
    glsl_io.write_defines(app.active_instance.module_glsl('circle'), defaults, SHAPE_PARAMS)
    glsl_io.write_flag_defines(app.active_instance.module_glsl('circle'), defaults, FLAG_PARAMS)
    glsl_io.write_define_raw(app.active_instance.module_glsl('circle'), "ROTATE", "(PI / 2)")
    glsl_io.write_define_raw(app.active_instance.module_glsl('circle'), "CENTER_OFFSET_X", 0)
    glsl_io.write_define_raw(app.active_instance.module_glsl('circle'), "CENTER_OFFSET_Y", 0)


class CircleParamWidget(BaseParamWidget):
    MODULE_NAME  = "circle"
    SHAPE_PARAMS = SHAPE_PARAMS

    def _init_extra(self):
        try:
            from ..geometry import get_screen_info
            si = get_screen_info()
            self._sw, self._sh = si[0], si[1]
        except Exception:
            self._sw, self._sh = 1600, 900

    def build_left(self, parent, current):
        self._build_shape(parent, current)
        self._build_rotate(parent, current)
        self._build_position(parent, current)
        self._build_flags(parent, current)

    def build_right(self, parent, current):
        self._build_smooth(parent, current)
        self._build_profiles(parent)
    def _build_shape(self, parent, current):
        title = self.T.get("section_shape", "Kształt")
        lf = self._detachable_lf(parent, title, self._build_shape, current)
        lf.pack(fill="x", padx=10, pady=10)
        lf.columnconfigure(2, weight=1)

        mapping = {
            "C_RADIUS": "label_radius",
            "C_LINE":   "label_line_thickness",
            "AMPLIFY":  "label_gain",
        }

        for idx, p in enumerate(SHAPE_PARAMS):
            p_list = list(p)
            jk = mapping.get(p[0])
            if jk:
                p_list[1] = self.T.get(jk, p[1])
                p_list[6] = self.T.get(jk.replace("label_", "tooltip_"), p[6])
            self._slider_row(lf, tuple(p_list), current, idx)

    # ── Rotacja ───────────────────────────────────────────────────────────────

    def _build_rotate(self, parent, current):
        title = self.T.get("section_rotate", "Rotacja")
        lf = self._detachable_lf(parent, title, self._build_rotate, current)
        lf.pack(fill="x", padx=10, pady=10)
        lf.columnconfigure(2, weight=1)

        cur = int(current.get("ROTATE_DEG", 90))
        self.rotate_var = tk.IntVar(value=cur)

        ttk.Label(lf, text=self.T.get("label_rotation", "Rotation"),
                  width=12, anchor="w").grid(
            row=0, column=0, padx=(10, 5), pady=5, sticky="w")
        t = glsl_io.tip(lf, "?", self.T.get("tooltip_rotate", "Obrót wizualizacji"))
        if t: t.grid(row=0, column=1, padx=5, pady=5)

        def on_rot(v):
            self.rotate_var.set(int(round(v)))
            self._write_rotate()

        rot_slider = SimpleSlider(lf, vmin=0, vmax=360, value=cur, step=1,
                                 on_change=on_rot)
        rot_slider.grid(row=0, column=2, padx=10, pady=5, sticky="ew")
        ttk.Label(lf, text="°", width=4).grid(
            row=0, column=3, padx=(5, 10), pady=5, sticky="e")

    # ── Pozycja ───────────────────────────────────────────────────────────────

    def _build_position(self, parent, current):
        title = self.T.get("section_position", "Pozycja")
        lf = self._detachable_lf(parent, title, self._build_position, current)
        lf.pack(fill="x", padx=10, pady=10)
        lf.columnconfigure(2, weight=1)

        max_x = self._sw // 2
        max_y = self._sh // 2

        for row_idx, (key, lk, max_val) in enumerate([
            ("CENTER_OFFSET_X", "label_offset_x", max_x),
            ("CENTER_OFFSET_Y", "label_offset_y", max_y),
        ]):
            cur = int(current.get(key, 0))
            var = tk.IntVar(value=cur)
            self.vars[key] = var

            ttk.Label(lf, text=self.T.get(lk, key),
                      width=12, anchor="w").grid(
                row=row_idx, column=0, padx=(10, 5), pady=5, sticky="w")
            t = glsl_io.tip(lf, "?", self.T.get(lk.replace("label_", "tooltip_"),
                     f"Przesuwa środek wizualizacji\nZakres: ±{max_val}px"))
            if t: t.grid(row=row_idx, column=1, padx=5, pady=5)

            def on_offset(v, k=key, sv=var):
                sv.set(int(round(v)))
                self._debounce_int(k, int(round(v)))

            slider = SimpleSlider(lf, vmin=-max_val, vmax=max_val,
                                 value=cur, step=1, on_change=on_offset)
            slider.grid(row=row_idx, column=2, padx=10, pady=5, sticky="ew")
            ttk.Label(lf, text="px", width=4).grid(
                row=row_idx, column=3, padx=(5, 10), pady=5, sticky="e")

    # ── Przełączniki ──────────────────────────────────────────────────────────

    #def _build_flags(self, parent, current):
    #    lf = ttk.LabelFrame(parent,
    #                        text=self.T.get("section_switches", "Przełączniki"),
    #                        padding=(15, 10))
    #    lf.pack(fill="x", padx=10, pady=10)
    def _build_flags(self, parent, current):
        title = self.T.get("section_switches", "Przełączniki")
        lf = self._detachable_lf(parent, title, self._build_flags, current)
        lf.pack(fill="x", padx=10, pady=10)

        # Konfiguracja kolumn, żeby pasowały do tych z suwaków
        lf.columnconfigure(2, weight=1)

        mapping = {
            "C_FILL":  "label_grad_fill",
            "C_SMOOTH": "label_smooth_post",
            "INVERT":  "label_swap_lr",
        }

    #    for key, label_def, tip_def in FLAG_PARAMS:
    #        if key in _UNIMPLEMENTED:
    #            continue
    #        raw = current.get(key, 0)
    #        var = tk.BooleanVar(value=bool(int(raw)))
    #        self.vars[key] = var
#
#            jk = mapping.get(key)
#            display_label = self.T.get(jk, label_def) if jk else label_def
#            display_tip   = self.T.get(jk.replace("label_", "tooltip_"), tip_def) if jk else tip_def

#            row = ttk.Frame(lf)
#            row.pack(fill="x", pady=1)
#            ttk.Checkbutton(
#                row, text=display_label, variable=var,
#                command=lambda k=key, v=var: self._write_flag(k, v)
#            ).pack(side="left")
#            glsl_io.tip(row, "?", display_tip)
        for idx, (key, label, tooltip) in enumerate(FLAG_PARAMS):
            raw = current.get(key, 0)
            var = tk.BooleanVar(value=bool(int(raw)))
            self.vars[key] = var

            json_key = mapping.get(key)
            translated_label = self.T.get(json_key, label) if json_key else label
            tip_key = json_key.replace("label_", "tooltip_") if json_key else None
            translated_tip = self.T.get(tip_key, tooltip) if tip_key else tooltip

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
            jk = mapping.get(p[0])
            label   = self.T.get(jk, p[1]) if jk else p[1]
            tooltip = self.T.get(jk.replace("label_", "tooltip_"), p[7]) if jk else p[7]
            self._float_slider_row(lf, (p[0], label, p[2], p[3], p[4], p[5], p[6], tooltip), current, idx)

    # ── Profile ───────────────────────────────────────────────────────────────

    def _build_profiles(self, parent):
        lf = ttk.LabelFrame(parent,
                            text=self.T.get("section_profiles_circle", "Shader profiles circle"),
                            padding=(15, 10))
        lf.pack(fill="x", padx=10, pady=10)

        profiles = get_shader_profiles_for_module("circle")
        names    = sorted(profiles.keys())
        self.profile_var = tk.StringVar()
        self.profile_cb  = ttk.Combobox(lf, textvariable=self.profile_var,
                                        values=names, state="readonly")
        self.profile_cb.pack(fill="x", pady=(0, 3))
        if names: self.profile_cb.current(0)

        ttk.Label(lf, text=self.T.get("label_profiles_hint_shape",
                                       "Shape & options (colors unchanged)")).pack(anchor="w")

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
                   command=self._delete_profile,
                   style="Danger.TButton").pack(side="left")

        ttk.Button(lf, text=self.T.get("btn_reset_shader_circle", "Reset circle shader"),
                   command=self._reset_shader,
                   style="Accent.TButton").pack(fill="x", pady=(4, 0))

    def _write_rotate(self):
        deg = self.rotate_var.get()
        glsl_io.write_define_raw(self._glsl, "ROTATE", _deg_to_rotate(deg))
        self._schedule_restart()

    def _write_flag(self, key, var):
        glsl_io.write_flag_defines(self._glsl, {key: 1 if var.get() else 0}, FLAG_PARAMS)
        self._schedule_restart()

    def _debounce_int(self, key, value):
        if key in ("CENTER_OFFSET_X", "CENTER_OFFSET_Y"):
            glsl_io.write_define_raw(self._glsl, key, int(value))
        else:
            glsl_io.write_defines(self._glsl, {key: value}, SHAPE_PARAMS)
        self._schedule_restart()

    def _reset_shader(self):
        if messagebox.askyesno(self.T.get("section_reset", "Reset"),
                               self.T.get("confirm_reset_circle", "Restore default circle shader?")):
            reset_shader(self.app)
            self.app.rebuild_module_tab()
            if hasattr(self.app, 'restart_active_instance'):
                self.app.restart_active_instance(module="circle", after_fn=self.app.update_status)
            else:
                from gui.glava import glava_restart
                glava_restart("circle", extra_flags=getattr(self.app, "extra_flags", "--desktop"),
                              after_fn=self.app.update_status)


# ─── Helpers (rotation) ─────────────────────────────────────────────────────

def _rotate_to_deg(raw):
    sym = {"0": 0, "(PI / 2)": 90, "PI": 180, "(3 * PI / 2)": 270}
    if raw.strip() in sym:
        return sym[raw.strip()]
    try:
        rad = float(raw.strip())
        return round(rad * 180.0 / 3.14159265359) % 360
    except ValueError:
        return 90

def _deg_to_rotate(deg):
    return f"{deg * 3.14159265359 / 180.0:.6f}"


# ─── I/O ─────────────────────────────────────────────────────────────────────

