# =============================================================================
# gui/modules/radial.py  v2
#
# Plik konfiguracyjny: ~/.config/glava/radial.glsl
# Wygładzanie:         ~/.config/glava/smooth_parameters.glsl
#
# Parametry:
#   C_RADIUS        int    promień okręgu bazowego (px)
#   C_LINE          int    grubość linii okręgu (px)
#   NBARS           int    liczba słupków
#   BAR_WIDTH       float  szerokość słupka (px)
#   AMPLIFY         int    wzmocnienie amplitudy
#   GRADIENT        int    wypełnienie gradientem koła (%)
#   BAR_ALIAS_FACTOR float  ostrość krawędzi słupków
#   C_ALIAS_FACTOR  float  ostrość krawędzi okręgu
#   CENTER_OFFSET_X int    przesunięcie X (±screen_w/2)
#   CENTER_OFFSET_Y int    przesunięcie Y (±screen_h/2)
#   ROTATE          float  obrót (radiany) — GUI pokazuje stopnie
#   INVERT          0/1    zamiana L/R
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
from ..geometry import get_screen_info

def _radial_glsl():  return os.path.join(GLAVA_DIR, "radial.glsl")
def _smooth_glsl():  return os.path.join(GLAVA_DIR, "smooth_parameters.glsl")
def _radial_tmpl():  return os.path.join(GLAVA_DIR, "radial_colors.frag")
def _radial_1frag(): return os.path.join(GLAVA_DIR, "radial", "1.frag")

# Obrót — mapowanie stopnie → wyrażenie GLSL
ROTATE_OPTIONS = [
    ("0°",    "0"),
    ("90°",   "(PI / 2)"),
    ("180°",  "PI"),
    ("270°",  "(3 * PI / 2)"),
]

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

# Float params — (klucz, etykieta, min, max, domyślna, krok, tooltip)
SHAPE_FLOAT_PARAMS = [
    ("BAR_WIDTH",        "Szerokość słupka",  1.0, 20.0, 4.5, 0.5,
     "Szerokość pojedynczego słupka w pikselach"),
    ("BAR_ALIAS_FACTOR", "Ostrość słupków",   0.5,  5.0, 1.2, 0.1,
     "Ostrość krawędzi słupków\nWymaga opacity: xroot\nWiększe = bardziej zdefiniowane krawędzie"),
    ("C_ALIAS_FACTOR",   "Ostrość okręgu",    0.5,  5.0, 1.8, 0.1,
     "Ostrość krawędzi środkowego okręgu\nWymaga opacity: xroot"),
]

# Parametry wygładzania — smooth_parameters.glsl
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

    # Int params
    for key, _, _, _, default, _, _ in SHAPE_INT_PARAMS:
        try:    p[key] = int(raw.get(key, default))
        except: p[key] = default

    # Float params
    for key, _, _, _, default, _, _ in SHAPE_FLOAT_PARAMS:
        try:    p[key] = float(raw.get(key, default))
        except: p[key] = default

    # ROTATE — odczytaj i przelicz na stopnie
    rotate_raw = raw.get("ROTATE", "(PI / 2)")
    p["ROTATE_DEG"] = _rotate_to_deg(rotate_raw)

    # Offset X/Y
    try:    p["CENTER_OFFSET_X"] = int(raw.get("CENTER_OFFSET_X", 0))
    except: p["CENTER_OFFSET_X"] = 0
    try:    p["CENTER_OFFSET_Y"] = int(raw.get("CENTER_OFFSET_Y", 0))
    except: p["CENTER_OFFSET_Y"] = 0

    # Flagi
    p.update(_read_flags(_radial_glsl()))

    # Wygładzanie
    p.update(_read_smooth(_smooth_glsl()))

    return p


def apply_params(params, app):
    # Int
    int_keys = {p[0] for p in SHAPE_INT_PARAMS} | {"CENTER_OFFSET_X", "CENTER_OFFSET_Y"}
    for key, val in params.items():
        if key in int_keys:
            _write_define_int(_radial_glsl(), key, int(val))

    # Float
    float_keys = {p[0] for p in SHAPE_FLOAT_PARAMS}
    for key, val in params.items():
        if key in float_keys:
            step = next(p[5] for p in SHAPE_FLOAT_PARAMS if p[0] == key)
            _write_define_float(_radial_glsl(), key, float(val), step)

    # ROTATE
    if "ROTATE_DEG" in params:
        glsl_val = _deg_to_rotate(int(params["ROTATE_DEG"]))
        _write_define_raw(_radial_glsl(), "ROTATE", glsl_val)

    # Flagi
    _write_flags(_radial_glsl(), params)

    # Wygładzanie
    _write_smooth(_smooth_glsl(), params)


def reset_shader(app):
    import shutil
    tmpl, live = _radial_tmpl(), _radial_1frag()
    if os.path.exists(tmpl):
        os.makedirs(os.path.dirname(live), exist_ok=True)
        shutil.copy2(tmpl, live)
    # Przywróć domyślne wartości w radial.glsl
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
        # Pobierz rozdzielczość dla zakresu offsetów
        try:
            si = get_screen_info()
            self._sw, self._sh = si[0], si[1]
        except Exception:
            self._sw, self._sh = 1600, 900

    def build(self):
        current = collect_params(self.app)

        left  = tk.Frame(self.parent)
        right = tk.Frame(self.parent)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        right.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        self.parent.columnconfigure(0, weight=1, uniform="rc")
        self.parent.columnconfigure(1, weight=1, uniform="rc")
        self.parent.rowconfigure(0, weight=1)

        self._build_shape(left, current)
        self._build_position(left, current)
        self._build_flags(left, current)
        self._build_smooth(right, current)
        self._build_profiles(right)

    # ── Kształt ──────────────────────────────────────────────────────────────

    def _build_shape(self, parent, current):
        lf = tk.LabelFrame(parent, text=T.get("section_shape", "Kształt"),
                           font=("Arial", 9, "bold"), padx=5, pady=4)
        lf.pack(fill="x", pady=(0, 4))

        for p in SHAPE_INT_PARAMS:
            self._int_row(lf, p, current)

        for p in SHAPE_FLOAT_PARAMS:
            self._float_row(lf, p, current)

        # ROTATE — suwak 0-360°
        cur_rot = int(current.get('ROTATE_DEG', 90))
        self.rotate_var = tk.IntVar(value=cur_rot)
        rot_entry_var = tk.StringVar(value=str(cur_rot))
        rot_row = tk.Frame(lf)
        rot_row.pack(fill="x", pady=2)
        tk.Label(rot_row, text=T.get("section_rotation", T.get("label_rotation", "Obrót")), font=("Arial", 9),
                 width=16, anchor="w").pack(side="left")
        _tip(rot_row, "?", "Obrót wizualizacji\n0° = domyślny\n90° = obrót w prawo")
        rot_slider = tk.Scale(rot_row, variable=self.rotate_var,
                              from_=0, to=360, orient="horizontal",
                              showvalue=False, sliderlength=12)
        rot_slider.pack(side="left", fill="x", expand=True, padx=(3, 0))
        rot_entry = tk.Entry(rot_row, textvariable=rot_entry_var,
                             width=4, font=("Arial", 9), justify="right")
        rot_entry.pack(side="left", padx=(3, 0))
        tk.Label(rot_row, text="°", font=("Arial", 9),
                 fg="gray50", width=2).pack(side="left")

        def on_rot_slide(val, ev=rot_entry_var):
            ev.set(str(int(float(val))))
            self._write_rotate()
        def on_rot_entry(event):
            try:
                v = max(0, min(360, int(rot_entry_var.get())))
                self.rotate_var.set(v); rot_entry_var.set(str(v))
                self._write_rotate()
            except ValueError:
                rot_entry_var.set(str(self.rotate_var.get()))
        rot_slider.config(command=on_rot_slide)
        rot_entry.bind("<Return>",   on_rot_entry)
        rot_entry.bind("<FocusOut>", on_rot_entry)

    # ── Pozycja ───────────────────────────────────────────────────────────────

    def _build_position(self, parent, current):
        lf = tk.LabelFrame(parent, text=T.get("section_position", "Pozycja na ekranie"),
                           font=("Arial", 9, "bold"), padx=5, pady=4)
        lf.pack(fill="x", pady=(0, 4))

        max_x = self._sw // 2
        max_y = self._sh // 2

        for key, label, default, max_val in [
            ("CENTER_OFFSET_X", T.get("label_offset_x", "Przesunięcie X"), 0, max_x),
            ("CENTER_OFFSET_Y", T.get("label_offset_y", "Przesunięcie Y"), 0, max_y),
        ]:
            cur = int(current.get(key, default))
            var = tk.IntVar(value=cur)
            self.vars[key] = var
            entry_var = tk.StringVar(value=str(cur))

            row = tk.Frame(lf)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=label, font=("Arial", 9),
                     width=16, anchor="w").pack(side="left")
            _tip(row, "?",
                 f"Przesuwa środek wizualizacji\n"
                 f"Zakres: ±{max_val}px (połowa {'szerokości' if 'X' in key else 'wysokości'} ekranu)\n"
                 f"0 = środek ekranu")
            slider = tk.Scale(row, variable=var,
                              from_=-max_val, to=max_val,
                              orient="horizontal", showvalue=False,
                              sliderlength=12)
            slider.pack(side="left", fill="x", expand=True, padx=(3, 0))
            entry = tk.Entry(row, textvariable=entry_var,
                             width=6, font=("Arial", 9), justify="right")
            entry.pack(side="left", padx=(3, 0))
            tk.Label(row, text="px", font=("Arial", 9),
                     fg="gray50", width=3).pack(side="left")

            def on_slide(val, ev=entry_var, k=key):
                ev.set(str(int(float(val))))
                self._debounce_int(k, int(float(val)))

            def on_entry(event, sv=var, ev=entry_var,
                         lo=-max_val, hi=max_val, k=key):
                try:
                    v = max(lo, min(hi, int(ev.get())))
                    sv.set(v); ev.set(str(v))
                    self._debounce_int(k, v)
                except ValueError:
                    ev.set(str(sv.get()))

            slider.config(command=on_slide)
            entry.bind("<Return>",   on_entry)
            entry.bind("<FocusOut>", on_entry)

    # ── Przełączniki ──────────────────────────────────────────────────────────

    def _build_flags(self, parent, current):
        lf = tk.LabelFrame(parent, text=T.get("section_switches", "Przełączniki"),
                           font=("Arial", 9, "bold"), padx=5, pady=4)
        lf.pack(fill="x")
        for key, label, tooltip in FLAG_PARAMS:
            var = tk.BooleanVar(value=bool(int(current.get(key, 0))))
            self.vars[key] = var
            row = tk.Frame(lf)
            row.pack(fill="x", pady=1)
            tk.Checkbutton(row, text=label, variable=var,
                           font=("Arial", 9),
                           command=lambda k=key, v=var: self._write_flag(k, v)
                           ).pack(side="left")
            _tip(row, "?", tooltip)

    # ── Wygładzanie ───────────────────────────────────────────────────────────

    def _build_smooth(self, parent, current):
        lf = tk.LabelFrame(parent, text=T.get("section_smoothing", "Wygładzanie"),
                           font=("Arial", 9, "bold"), padx=5, pady=4)
        lf.pack(fill="x", pady=(0, 4))
        for p in SMOOTH_PARAMS:
            self._smooth_row(lf, p, current)
        tk.Label(lf, text=T.get("audio_affects_all", "⚠ Wpływa na wszystkie moduły"),
                 font=("Arial", 7), fg="#bf360c").pack(anchor="w", pady=(4, 0))

    # ── Profile ───────────────────────────────────────────────────────────────

    def _build_profiles(self, parent):
        lf = tk.LabelFrame(parent, text=T.get("section_profiles_radial", "Profile szadera radial"),
                           font=("Arial", 9, "bold"), padx=5, pady=4)
        lf.pack(fill="x", pady=(0, 4))

        profiles = get_shader_profiles_for_module("radial")
        names    = sorted(profiles.keys())
        self.profile_var = tk.StringVar()
        self.profile_cb  = ttk.Combobox(lf, textvariable=self.profile_var,
                                        values=names, state="readonly",
                                        font=("Arial", 9))
        self.profile_cb.pack(fill="x", pady=(0, 3))
        if names: self.profile_cb.current(0)
        tk.Label(lf, text=T.get("label_profiles_hint_radial", "Kształt + wygładzanie (kolory bez zmian)"),
                 font=("Arial", 7), fg="gray50").pack(anchor="w")
        btn_row = tk.Frame(lf)
        btn_row.pack(fill="x", pady=(4, 0))
        tk.Button(btn_row, text=T.get("btn_apply", "Zastosuj"), command=self._apply_profile,
                  bg="#00695c", fg="white", font=("Arial", 8)
                  ).pack(side="left", expand=True, fill="x", padx=(0, 2))
        tk.Button(btn_row, text=T.get("btn_save_new", "Zapisz"), command=self._save_profile,
                  bg="#37474f", fg="white", font=("Arial", 8)
                  ).pack(side="left", expand=True, fill="x", padx=(0, 2))
        tk.Button(btn_row, text=T.get("btn_delete", "Usuń"), command=self._delete_profile,
                  bg="#b71c1c", fg="white", font=("Arial", 8)
                  ).pack(side="left")

        rf = tk.LabelFrame(parent, text=T.get("section_reset", "Reset"),
                           font=("Arial", 9, "bold"), padx=5, pady=4)
        rf.pack(fill="x", pady=(4, 0))
        tk.Button(rf, text=T.get("btn_reset_shader_radial", "Reset szadera radial"), command=self._reset_shader,
                  bg="#5d4037", fg="white", font=("Arial", 8)
                  ).pack(fill="x")

    # ── Wiersze suwaków ───────────────────────────────────────────────────────

    def _int_row(self, parent, param_def, current):
        key, label, vmin, vmax, default, unit, tooltip = param_def
        cur = int(current.get(key, default))
        var = tk.IntVar(value=cur)
        self.vars[key] = var
        entry_var = tk.StringVar(value=str(cur))
        self._make_slider_row(parent, key, label, unit, tooltip,
                              var, entry_var, vmin, vmax,
                              lambda v: self._debounce_int(key, v))

    def _float_row(self, parent, param_def, current):
        key, label, vmin, vmax, default, step, tooltip = param_def
        cur = float(current.get(key, default))
        var = tk.DoubleVar(value=cur)
        self.vars[key] = var
        dec = _decimals(step)
        fmt = f"{{:.{dec}f}}"
        entry_var = tk.StringVar(value=fmt.format(cur))
        self._make_slider_row(parent, key, label, "", tooltip,
                              var, entry_var, vmin, vmax,
                              lambda v: self._debounce_float(key, float(v), step),
                              resolution=step, fmt=fmt)

    def _smooth_row(self, parent, param_def, current):
        key, label, vmin, vmax, default, step, tooltip = param_def
        try:    cur = float(current.get(key, default))
        except: cur = float(default)
        var = tk.DoubleVar(value=cur)
        self.vars[key] = var
        dec = _decimals(step)
        fmt = f"{{:.{dec}f}}"
        entry_var = tk.StringVar(value=fmt.format(cur))
        self._make_slider_row(parent, key, label, "", tooltip,
                              var, entry_var, vmin, vmax,
                              lambda v: self._debounce_smooth(key, float(v)),
                              resolution=step, fmt=fmt)

    def _make_slider_row(self, parent, key, label, unit, tooltip,
                         var, entry_var, vmin, vmax, on_change,
                         resolution=1, fmt=None):
        row = tk.Frame(parent)
        row.pack(fill="x", pady=2)
        tk.Label(row, text=label, font=("Arial", 9),
                 width=16, anchor="w").pack(side="left")
        _tip(row, "?", tooltip)
        slider = tk.Scale(row, variable=var, from_=vmin, to=vmax,
                          resolution=resolution,
                          orient="horizontal", showvalue=False,
                          sliderlength=12)
        slider.pack(side="left", fill="x", expand=True, padx=(3, 0))
        entry = tk.Entry(row, textvariable=entry_var,
                         width=6, font=("Arial", 9), justify="right")
        entry.pack(side="left", padx=(3, 0))
        tk.Label(row, text=unit if unit else "  ",
                 font=("Arial", 9), fg="gray50", width=3).pack(side="left")

        def on_slide(val):
            v = float(val)
            entry_var.set(fmt.format(v) if fmt else str(int(v)))
            on_change(v)

        def on_entry(event):
            try:
                raw = float(entry_var.get())
                v = max(float(vmin), min(float(vmax), raw))
                var.set(v)
                entry_var.set(fmt.format(v) if fmt else str(int(v)))
                on_change(v)
            except ValueError:
                entry_var.set(fmt.format(var.get()) if fmt else str(int(var.get())))

        slider.config(command=on_slide)
        entry.bind("<Return>",   on_entry)
        entry.bind("<FocusOut>", on_entry)

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
            300, lambda: glava_restart("radial", extra_flags=getattr(self.app, "extra_flags", "--desktop"), after_fn=self.app.update_status))

    def _apply_profile(self):
        name = self.profile_var.get()
        if not name: return
        profiles = get_shader_profiles_for_module("radial")
        if name not in profiles: return
        apply_params(profiles[name], self.app)
        self.app.rebuild_module_tab()
        from gui.glava import glava_restart
        glava_restart("radial", extra_flags=getattr(self.app, "extra_flags", "--desktop"), after_fn=self.app.update_status)

    def _save_profile(self):
        name = simpledialog.askstring("Nowy profil", T.get("dialog_profile_name", "Podaj nazwę:"))
        if not name: return
        save_shader_profile_for_module("radial", name, collect_params(self.app))
        self._refresh_cb()
        self.profile_var.set(name)

    def _delete_profile(self):
        name = self.profile_var.get()
        if name and messagebox.askyesno("", T.get("dialog_delete_confirm", "Czy na pewno usunąć profil") + f" '{name}'?"):
            delete_shader_profile_for_module("radial", name)
            self._refresh_cb()

    def _refresh_cb(self):
        names = sorted(get_shader_profiles_for_module("radial").keys())
        self.profile_cb["values"] = names
        if names: self.profile_cb.current(0)

    def _reset_shader(self):
        if messagebox.askyesno(T.get("section_reset", "Reset"), T.get("confirm_reset_radial", "Przywrócić domyślny shader radial?")):
            reset_shader(self.app)
            self.app.rebuild_module_tab()
            from gui.glava import glava_restart
            glava_restart("radial", extra_flags=getattr(self.app, "extra_flags", "--desktop"), after_fn=self.app.update_status)


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


# ─── I/O ─────────────────────────────────────────────────────────────────────

def _read_raw(path):
    """Zwraca dict klucz→wartość_string (pierwsze wystąpienie każdego klucza)."""
    result = {}
    if not os.path.exists(path): return result
    with open(path) as f: content = f.read()
    for m in re.finditer(r'^#define\s+(\w+)\s+(.+)', content, re.MULTILINE):
        key = m.group(1)
        if key not in result:
            result[key] = m.group(2).strip()
    return result

def _write_define_int(path, key, val):
    """Zapisuje #define KEY val (int) — usuwa duplikaty."""
    if not os.path.exists(path): return
    with open(path) as f: content = f.read()
    pattern = rf'^#define\s+{key}\s+\S+[ \t]*$'
    matches = list(re.finditer(pattern, content, re.MULTILINE))
    if matches:
        first = matches[0].start()
        content = re.sub(pattern, '', content, flags=re.MULTILINE)
        content = re.sub(r'\n{3,}', '\n\n', content)
        content = content[:first] + f'#define {key} {val}\n' + content[first:]
    else:
        content = content.rstrip() + f'\n#define {key} {val}\n'
    with open(path, "w") as f: f.write(content)

def _write_define_float(path, key, val, step):
    """Zapisuje #define KEY val (float) — usuwa duplikaty."""
    dec = _decimals(step)
    _write_define_raw(path, key, f"{val:.{dec}f}")

def _write_define_raw(path, key, val_str):
    """Zapisuje #define KEY val_str (dowolny string) — usuwa duplikaty."""
    if not os.path.exists(path): return
    with open(path) as f: content = f.read()
    # Dla ROTATE wyrażenie może zawierać nawiasy — dopasuj do końca linii
    pattern = rf'^#define\s+{key}\s+.+$'
    matches = list(re.finditer(pattern, content, re.MULTILINE))
    if matches:
        first = matches[0].start()
        content = re.sub(pattern, '', content, flags=re.MULTILINE)
        content = re.sub(r'\n{3,}', '\n\n', content)
        content = content[:first] + f'#define {key} {val_str}\n' + content[first:]
    else:
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
