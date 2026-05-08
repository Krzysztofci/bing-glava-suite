# =============================================================================
# gui/modules/radial.py  v3
#
# Plik konfiguracyjny: ~/.config/glava/radial.glsl
# Wygładzanie:         ~/.config/glava/smooth_parameters.glsl
#
# Wzorzec GUI: bars.py v5 (grid w LabelFrame, ttk.*, Forest-ttk-theme)
# =============================================================================

import os, re, math
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from ..core import CONFIG_DIR, GLAVA_DIR, RC_GLSL
from ..widgets import AccelSlider
from ..core import (
    get_shader_profiles_for_module,
    save_shader_profile_for_module,
    delete_shader_profile_for_module,
)
from ..geometry import get_screen_info

def _radial_glsl():  return os.path.join(GLAVA_DIR, "radial.glsl")
def _smooth_glsl():  return os.path.join(GLAVA_DIR, "smooth_parameters.glsl")
def _radial_tmpl():  return os.path.join(GLAVA_DIR, "radial_colors.frag")
def _radial_1frag(): return os.path.join(GLAVA_DIR, "radial", "1.frag")

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
SMOOTH_PARAMS = [
    ("setgravitystep",  "Grawitacja",     0.1, 20.0,  4.2, 0.1,
     "Szybkość opadania słupków po szczycie"),
    ("setsmoothfactor", "Wygładzanie",  0.001,  0.1, 0.025, 0.001,
     "Rozmiar jądra wygładzającego FFT\nMniejsze = bardziej responsywne"),
    ("setavgframes",    "Klatek avg",      1,   16,     5, 1,
     "Liczba klatek do uśredniania"),
    ("setfftscale",     "Skala FFT",     1.0, 30.0,  10.2, 0.1,
     "Skala częstotliwości FFT"),
    ("setfftcutoff",    "Odcięcie basów", 0.0,  1.0,   0.3, 0.01,
     "Odcięcie najniższych częstotliwości FFT"),
]

FLAG_PARAMS = [
    ("INVERT", "Zamień kanały L/R",
     "Zamienia lewy i prawy kanał audio"),
]


# ─── API ─────────────────────────────────────────────────────────────────────

def build_params(parent, app, T):
    RadialParamWidget(parent, app, T).build()


def collect_params(app):
    raw = _read_raw(_radial_glsl())
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
    p.update(_read_flags(_radial_glsl()))
    p.update(_read_smooth(_smooth_glsl()))
    return p


def apply_params(params, app):
    int_keys = {p[0] for p in SHAPE_INT_PARAMS} | {"CENTER_OFFSET_X", "CENTER_OFFSET_Y"}
    for key, val in params.items():
        if key in int_keys:
            _write_define_int(_radial_glsl(), key, int(val))
    float_keys = {p[0] for p in SHAPE_FLOAT_PARAMS}
    for key, val in params.items():
        if key in float_keys:
            step = next(p[5] for p in SHAPE_FLOAT_PARAMS if p[0] == key)
            _write_define_float(_radial_glsl(), key, float(val), step)
    if "ROTATE_DEG" in params:
        glsl_val = _deg_to_rotate(int(params["ROTATE_DEG"]))
        _write_define_raw(_radial_glsl(), "ROTATE", glsl_val)
    _write_flags(_radial_glsl(), params)
    _write_smooth(_smooth_glsl(), params)


def reset_shader(app):
    import shutil
    tmpl, live = _radial_tmpl(), _radial_1frag()
    if os.path.exists(tmpl):
        os.makedirs(os.path.dirname(live), exist_ok=True)
        shutil.copy2(tmpl, live)
    for key, _, _, _, default, _, _ in SHAPE_INT_PARAMS:
        _write_define_int(_radial_glsl(), key, default)
    for key, _, _, _, default, step, _ in SHAPE_FLOAT_PARAMS:
        _write_define_float(_radial_glsl(), key, default, step)
    _write_define_raw(_radial_glsl(), "ROTATE", "(PI / 2)")
    _write_define_int(_radial_glsl(), "CENTER_OFFSET_X", 0)
    _write_define_int(_radial_glsl(), "CENTER_OFFSET_Y", 0)
    _write_flags(_radial_glsl(), {p[0]: 0 for p in FLAG_PARAMS})


# ─── Widget ───────────────────────────────────────────────────────────────────

class RadialParamWidget:
    def __init__(self, parent, app, T):
        self.parent = parent
        self.app    = app
        self.T      = T
        self.vars   = {}
        try:
            si = get_screen_info()
            self._sw, self._sh = si[0], si[1]
        except Exception:
            self._sw, self._sh = 1600, 900

    def build(self):
        current = collect_params(self.app)

        left  = ttk.Frame(self.parent)
        right = ttk.Frame(self.parent)
        left.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)
        right.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)
        self.parent.columnconfigure(0, weight=1, uniform="rc")
        self.parent.columnconfigure(1, weight=1, uniform="rc")
        self.parent.rowconfigure(0, weight=1)

        self._build_shape(left, current)
        self._build_position(left, current)
        self._build_smooth(right, current)
        self._build_flags(right, current)
        self._build_profiles(right)

    # ── Kształt ──────────────────────────────────────────────────────────────

    def _build_shape(self, parent, current):
        lf = ttk.LabelFrame(parent,
                            text=self.T.get("section_shape", "Shape & dynamics"),
                            padding=(15, 10))
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
        t = _tip(lf, "?", self.T.get("tooltip_rotate", "Obrót wizualizacji"))
        if t: t.grid(row=row_idx, column=1, padx=5, pady=5)

        def on_rot_change(v):
            self.rotate_var.set(int(round(v)))
            self._write_rotate()

        rot_slider = AccelSlider(lf, vmin=0, vmax=360,
                                 value=cur_rot, step=1,
                                 on_change=on_rot_change)
        rot_slider.grid(row=row_idx, column=2, padx=10, pady=5, sticky="ew")
        ttk.Label(lf, text="°", width=4).grid(
            row=row_idx, column=3, padx=(5, 10), pady=5, sticky="e")

    # ── Pozycja ───────────────────────────────────────────────────────────────

    def _build_position(self, parent, current):
        lf = ttk.LabelFrame(parent,
                            text=self.T.get("section_position", "Screen position"),
                            padding=(15, 10))
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
            t = _tip(lf, "?", tooltip_text)
            if t: t.grid(row=row_idx, column=1, padx=5, pady=5)

            def on_change(v, k=key, sv=var):
                sv.set(int(round(v)))
                self._debounce_int(k, int(round(v)))

            slider = AccelSlider(lf, vmin=-max_val, vmax=max_val,
                                 value=cur, step=1,
                                 on_change=on_change)
            slider.grid(row=row_idx, column=2, padx=10, pady=5, sticky="ew")
            ttk.Label(lf, text=unit, width=4).grid(
                row=row_idx, column=3, padx=(5, 10), pady=5, sticky="e")

    # ── Przełączniki ──────────────────────────────────────────────────────────

    def _build_flags(self, parent, current):
        lf = ttk.LabelFrame(parent, text=self.T.get("section_switches", "Przełączniki"), padding=(15, 10))
        lf.pack(fill="x", padx=10, pady=10)

        # Konfiguracja kolumn, żeby pasowały do tych z suwaków
        lf.columnconfigure(2, weight=1)

        mapping_flags = {"INVERT": "label_swap_lr"}

        for idx, (key, label, tooltip) in enumerate(FLAG_PARAMS):
            raw = current.get(key, 0)
            var = tk.BooleanVar(value=bool(int(raw)))
            self.vars[key] = var
            
            json_key = mapping_flags.get(key)
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
                t = _tip(lf, "?", translated_tip)
                if t:
                    # padx=(0, 5) przyciąga go do tekstu po lewej
                    t.grid(row=idx, column=1, sticky="w", padx=(0, 5), pady=2)

    # ── Wygładzanie ───────────────────────────────────────────────────────────

    def _build_smooth(self, parent, current):
        lf = ttk.LabelFrame(parent,
                            text=self.T.get("section_smoothing", "Smoothing"),
                            padding=(15, 10))
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
                p_list[6] = self.T.get(lang_key.replace("label_", "tooltip_"), p[6])
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
        t = _tip(parent, "?", tooltip)
        if t: t.grid(row=row_idx, column=1, padx=5, pady=5)

        def on_change(v, k=key):
            var.set(int(round(v)))
            self._debounce_int(k, int(round(v)))

        slider = AccelSlider(parent, vmin=vmin, vmax=vmax, value=cur,
                             step=1, on_change=on_change)
        slider.grid(row=row_idx, column=2, padx=10, pady=5, sticky="ew")
        ttk.Label(parent, text=unit if unit else " ", width=4).grid(
            row=row_idx, column=3, padx=(5, 10), pady=5, sticky="e")

    def _float_row(self, parent, param_def, current, row_idx):
        key, label, vmin, vmax, default, step, tooltip = param_def
        cur = float(current.get(key, default))
        var = tk.DoubleVar(value=cur)
        self.vars[key] = var
        dec = _decimals(step)

        ttk.Label(parent, text=label, width=12, anchor="w").grid(
            row=row_idx, column=0, padx=(10, 5), pady=5, sticky="w")
        t = _tip(parent, "?", tooltip)
        if t: t.grid(row=row_idx, column=1, padx=5, pady=5)

        def on_change(v, k=key):
            var.set(v)
            self._debounce_float(k, float(v), step)

        slider = AccelSlider(parent, vmin=vmin, vmax=vmax, value=cur,
                             step=step, is_float=True, decimals=dec,
                             on_change=on_change)
        slider.grid(row=row_idx, column=2, padx=10, pady=5, sticky="ew")
        ttk.Label(parent, text=" ", width=4).grid(
            row=row_idx, column=3, padx=(5, 10), pady=5, sticky="e")

    def _smooth_row(self, parent, param_def, current, row_idx):
        key, label, vmin, vmax, default, step, tooltip = param_def
        try:    cur = float(current.get(key, default))
        except: cur = float(default)
        var = tk.DoubleVar(value=cur)
        self.vars[key] = var
        dec = _decimals(step)

        ttk.Label(parent, text=label, width=12, anchor="w").grid(
            row=row_idx, column=0, padx=(10, 5), pady=5, sticky="w")
        t = _tip(parent, "?", tooltip)
        if t: t.grid(row=row_idx, column=1, padx=5, pady=5)

        def on_change(v, k=key):
            var.set(v)
            self._debounce_smooth(k, float(v))

        slider = AccelSlider(parent, vmin=vmin, vmax=vmax, value=cur,
                             step=step, is_float=True, decimals=dec,
                             on_change=on_change)
        slider.grid(row=row_idx, column=2, padx=10, pady=5, sticky="ew")
        ttk.Label(parent, text=" ", width=4).grid(
            row=row_idx, column=3, padx=(5, 10), pady=5, sticky="e")

    # ── Zapis ─────────────────────────────────────────────────────────────────

    def _debounce_int(self, key, value):
        _write_define_int(_radial_glsl(), key, int(value))
        self._schedule_restart()

    def _debounce_float(self, key, value, step):
        _write_define_float(_radial_glsl(), key, value, step)
        self._schedule_restart()

    def _debounce_smooth(self, key, value):
        p = next(x for x in SMOOTH_PARAMS if x[0] == key)
        step = p[5]
        dec = _decimals(step)
        sv = str(int(value)) if key == "setavgframes" else f"{value:.{dec}f}"
        _write_request(_smooth_glsl(), key, sv)
        self._schedule_restart()

    def _write_rotate(self):
        deg = int(self.rotate_var.get())
        glsl_val = f"{deg * 3.14159265359 / 180.0:.6f}"
        _write_define_raw(_radial_glsl(), "ROTATE", glsl_val)
        self._schedule_restart()

    def _write_flag(self, key, var):
        _write_define_int(_radial_glsl(), key, 1 if var.get() else 0)
        self._schedule_restart()

    def _schedule_restart(self):
        if hasattr(self, "_rjob"):
            try: self.app.root.after_cancel(self._rjob)
            except Exception: pass
        from gui.glava import glava_restart
        self._rjob = self.app.root.after(
            300, lambda: glava_restart(
                "radial",
                extra_flags=getattr(self.app, "extra_flags", "--desktop"),
                after_fn=self.app.update_status))

    def _apply_profile(self):
        name = self.profile_var.get()
        if not name: return
        profiles = get_shader_profiles_for_module("radial")
        if name not in profiles: return
        apply_params(profiles[name], self.app)
        self.app.rebuild_module_tab()
        from gui.glava import glava_restart
        glava_restart("radial", extra_flags=getattr(self.app, "extra_flags", "--desktop"),
                      after_fn=self.app.update_status)

    def _save_profile(self):
        name = simpledialog.askstring(
            self.T.get("dialog_profile_title", "Nowy profil"),
            self.T.get("dialog_profile_name", "Enter profile name:"))
        if not name: return
        existing = get_shader_profiles_for_module("radial")
        if name in existing:
            if not messagebox.askyesno(
                    self.T.get("dialog_overwrite_title", "Nadpisać profil?"),
                    self.T.get("dialog_overwrite_msg",
                               "Profil '{}' już istnieje. Nadpisać?").format(name)):
                return
        save_shader_profile_for_module("radial", name, collect_params(self.app))
        self._refresh_cb()
        self.profile_var.set(name)

    def _delete_profile(self):
        name = self.profile_var.get()
        if name and messagebox.askyesno(
                "", self.T.get("dialog_delete_confirm",
                               "Are you sure you want to delete profile") + f" '{name}'?"):
            delete_shader_profile_for_module("radial", name)
            self._refresh_cb()

    def _refresh_cb(self):
        names = sorted(get_shader_profiles_for_module("radial").keys())
        self.profile_cb["values"] = names
        if names: self.profile_cb.current(0)

    def _reset_shader(self):
        if messagebox.askyesno(
                self.T.get("section_reset", "Reset"),
                self.T.get("confirm_reset_radial", "Restore default radial shader?")):
            reset_shader(self.app)
            self.app.rebuild_module_tab()
            from gui.glava import glava_restart
            glava_restart("radial", extra_flags=getattr(self.app, "extra_flags", "--desktop"),
                          after_fn=self.app.update_status)


# ─── Helpers ROTATE ──────────────────────────────────────────────────────────

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

def _decimals(step):
    s = str(step)
    return len(s.rstrip("0").split(".")[-1]) if "." in s else 0


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


# ─── I/O ─────────────────────────────────────────────────────────────────────

def _read_raw(path):
    result = {}
    if not os.path.exists(path): return result
    with open(path) as f: content = f.read()
    for m in re.finditer(r'^#define\s+(\w+)\s+(.+)', content, re.MULTILINE):
        key = m.group(1)
        if key not in result:
            result[key] = m.group(2).strip()
    return result

def _write_define_int(path, key, val):
    if not os.path.exists(path): return
    with open(path) as f: content = f.read()
    content = re.sub(rf'^#define\s+{key}\s+\S+[ \t]*\n?', '',
                     content, flags=re.MULTILINE)
    content = content.rstrip() + f'\n#define {key} {val}\n'
    with open(path, "w") as f: f.write(content)

def _write_define_float(path, key, val, step):
    dec = _decimals(step)
    _write_define_raw(path, key, f"{val:.{dec}f}")

def _write_define_raw(path, key, val_str):
    if not os.path.exists(path): return
    with open(path) as f: content = f.read()
    content = re.sub(rf'^#define\s+{key}\s+.+\n?', '',
                     content, flags=re.MULTILINE)
    content = content.rstrip() + f'\n#define {key} {val_str}\n'
    with open(path, "w") as f: f.write(content)

def _read_flags(path):
    result = {p[0]: 0 for p in FLAG_PARAMS}
    if not os.path.exists(path): return result
    with open(path) as f: content = f.read()
    for p in FLAG_PARAMS:
        m = re.search(rf'^#define\s+{p[0]}\s+(\S+)', content, re.MULTILINE)
        if m:
            try: result[p[0]] = int(m.group(1))
            except ValueError: pass
    return result

def _write_flags(path, params):
    for key, _, _ in FLAG_PARAMS:
        if key in params:
            _write_define_int(path, key, int(params[key]))

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
        p = next(x for x in SMOOTH_PARAMS if x[0] == key)
        dec = _decimals(p[5])
        sv = str(int(val)) if key == "setavgframes" else f"{float(val):.{dec}f}"
        content = re.sub(rf'^(#request\s+{key}\s+)\S+', rf'\g<1>{sv}',
                         content, flags=re.MULTILINE)
    with open(path, "w") as f: f.write(content)

def _write_request(path, key, val_str):
    if not os.path.exists(path): return
    with open(path) as f: content = f.read()
    content = re.sub(rf'^(#request\s+{key}\s+)\S+', rf'\g<1>{val_str}',
                     content, flags=re.MULTILINE)
    with open(path, "w") as f: f.write(content)
