# =============================================================================
# gui/modules/circle.py
# Plugin parametrów dla modułu circle.
#
# Plik konfiguracyjny: ~/.config/glava/circle.glsl
#
# Obsługiwane parametry:
#   C_RADIUS        int   promień okręgu w px
#   C_LINE          int   grubość linii wizualizacji
#   AMPLIFY         int   wzmocnienie amplitudy
#   ROTATE          float obrót (radiany) — GUI pokazuje stopnie
#   CENTER_OFFSET_X int   przesunięcie X (±screen_w/2)
#   CENTER_OFFSET_Y int   przesunięcie Y (±screen_h/2)
#   C_FILL          0/1   wypełnij przestrzeń wewnątrz okręgu
#   C_SMOOTH        0/1   wygładzanie post-processing (tylko xroot)
#   INVERT          0/1   zamiana L/R
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

def _circle_glsl():  return os.path.join(GLAVA_DIR, "circle.glsl")
def _smooth_glsl():  return os.path.join(GLAVA_DIR, "smooth_parameters.glsl")
def _circle_tmpl():  return os.path.join(GLAVA_DIR, "circle_colors.frag")
def _circle_1frag(): return os.path.join(GLAVA_DIR, "circle", "1.frag")

SHAPE_PARAMS = [
    ("C_RADIUS", "Promień okręgu",  50, 400, 128, "px",
     "Promień bazowego okręgu w pikselach"),
    ("C_LINE",   "Grubość linii",    0,  20,   2, "px",
     "Grubość linii wizualizacji\n"
     "Steruje też szerokością obszaru rysowania"),
    ("AMPLIFY",  "Wzmocnienie",     50, 800, 150, "",
     "Wzmocnienie amplitudy sygnału audio"),
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

# C_SMOOTH niezaimplementowane w shaderze circle/1.frag — ukryte do czasu wdrożenia
_UNIMPLEMENTED = {"C_SMOOTH"}

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
    p.update(_read_defines(_circle_glsl(), SHAPE_PARAMS))
    p.update(_read_flag_defines(_circle_glsl()))
    p.update(_read_smooth(_smooth_glsl()))
    rotate_raw = _read_raw_define(_circle_glsl(), "ROTATE") or "(PI / 2)"
    p["ROTATE_DEG"] = _rotate_to_deg(rotate_raw)
    try:    p["CENTER_OFFSET_X"] = int(_read_raw_define(_circle_glsl(), "CENTER_OFFSET_X") or 0)
    except: p["CENTER_OFFSET_X"] = 0
    try:    p["CENTER_OFFSET_Y"] = int(_read_raw_define(_circle_glsl(), "CENTER_OFFSET_Y") or 0)
    except: p["CENTER_OFFSET_Y"] = 0
    return p


def apply_params(params, app):
    _write_defines(_circle_glsl(), params, SHAPE_PARAMS)
    _write_flag_defines(_circle_glsl(), params)
    _write_smooth(_smooth_glsl(), params)
    if "ROTATE_DEG" in params:
        _write_raw_define(_circle_glsl(), "ROTATE", _deg_to_rotate(int(params["ROTATE_DEG"])))
    for key in ("CENTER_OFFSET_X", "CENTER_OFFSET_Y"):
        if key in params:
            _write_raw_define(_circle_glsl(), key, int(params[key]))


def reset_shader(app):
    import shutil
    tmpl = _circle_tmpl()
    live = _circle_1frag()
    if os.path.exists(tmpl):
        os.makedirs(os.path.dirname(live), exist_ok=True)
        shutil.copy2(tmpl, live)
    defaults = {p[0]: p[4] for p in SHAPE_PARAMS}
    defaults.update({p[0]: 0 for p in FLAG_PARAMS})
    defaults["C_SMOOTH"] = 1
    _write_defines(_circle_glsl(), defaults, SHAPE_PARAMS)
    _write_flag_defines(_circle_glsl(), defaults)
    _write_raw_define(_circle_glsl(), "ROTATE", "(PI / 2)")
    _write_raw_define(_circle_glsl(), "CENTER_OFFSET_X", 0)
    _write_raw_define(_circle_glsl(), "CENTER_OFFSET_Y", 0)


class CircleParamWidget:
    def __init__(self, parent, app, T):
        self.parent = parent
        self.app    = app
        self.T      = T
        self.vars   = {}
        try:
            from ..geometry import get_screen_info
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
        self.parent.columnconfigure(0, weight=1, uniform="cc")
        self.parent.columnconfigure(1, weight=1, uniform="cc")
        self.parent.rowconfigure(0, weight=1)

        self._build_shape(left, current)
        self._build_rotate(left, current)
        self._build_position(left, current)
        self._build_flags(left, current)
        self._build_smooth(right, current)
        self._build_profiles(right)

    def _build_shape(self, parent, current):
        # TUTAJ TWORZYMY BRAKUJĄCY 'lf'
        lf = tk.LabelFrame(parent, text=self.T.get("section_shape", "Kształt"), font=("Arial", 9, "bold"), padx=5, pady=4)
        lf.pack(fill="x", pady=(0, 4))
        # ... (kod tworzący ramkę Kształt) ...
        
        mapping = {
            "C_RADIUS": "label_radius",
            "C_LINE": "label_line_thickness",
            "AMPLIFY": "label_gain",
            "ROTATE": "label_rotate",
            "CENTER_OFFSET_X": "label_offset_x",
            "CENTER_OFFSET_Y": "label_offset_y"
        }

        for p in SHAPE_PARAMS:
            p_list = list(p)
            json_key = mapping.get(p[0])
            if json_key:
                p_list[1] = self.T.get(json_key, p[1]) # Tłumaczenie etykiety
                # TO JEST KLUCZOWE: pobranie tooltipa z JSON
                translated_tip = self.T.get(json_key.replace("label_", "tooltip_"), p[6])
                p_list[6] = translated_tip
            
            self._slider_row(lf, tuple(p_list), current)

    def _build_position(self, parent, current):
        lf = tk.LabelFrame(parent, text=self.T.get("section_position", "Screen position"),
                           font=("Arial", 9, "bold"), padx=5, pady=4)
        lf.pack(fill="x", pady=(0, 4))
        max_x = self._sw // 2
        max_y = self._sh // 2

        # Zmieniamy pętlę, żeby przekazać klucz (np. "label_offset_x")
        for key, lang_key, default, max_val in [
            ("CENTER_OFFSET_X", "label_offset_x", 0, max_x),
            ("CENTER_OFFSET_Y", "label_offset_y", 0, max_y),
        ]:
            cur = int(current.get(key, default))
            var = tk.IntVar(value=cur)
            self.vars[key] = var
            entry_var = tk.StringVar(value=str(cur))
            row = tk.Frame(lf)
            row.pack(fill="x", pady=2)

            # Pobieramy etykietę i tooltip z pliku JSON
            label_text = self.T.get(lang_key, lang_key)
            tooltip_text = self.T.get(lang_key.replace("label_", "tooltip_"), 
                                     f"Przesuwa środek wizualizacji\nZakres: ±{max_val}px")

            tk.Label(row, text=label_text, font=("Arial", 9),
                     width=16, anchor="w").pack(side="left")
            
            # Tutaj wstawiamy tooltip pobrany z JSON
            _tip(row, "?", tooltip_text)

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

    def _debounce_int(self, key, value):
        if key in ("CENTER_OFFSET_X", "CENTER_OFFSET_Y"):
            _write_raw_define(_circle_glsl(), key, int(value))
        else:
            _write_defines(_circle_glsl(), {key: value}, SHAPE_PARAMS)
        self._schedule_restart()

    def _build_rotate(self, parent, current):
        lf = tk.LabelFrame(parent, text=self.T.get("section_rotation", self.T.get("label_rotation", "Rotation")),
                           font=("Arial", 9, "bold"), padx=5, pady=4)
        lf.pack(fill="x", pady=(0, 4))
        cur = int(current.get("ROTATE_DEG", 90))
        self.rotate_var = tk.IntVar(value=cur)
        entry_var = tk.StringVar(value=str(cur))
        row = tk.Frame(lf)
        row.pack(fill="x", pady=2)
        
        # Etykieta (już ją masz)
        tk.Label(row, text=self.T.get("section_rotation", self.T.get("label_rotation", "Rotation")), font=("Arial", 9),
                 width=16, anchor="w").pack(side="left")

        # --- TA LINIA JEST NOWA ---
        _tip(row, "?", self.T.get("tooltip_rotate", "Obrót wizualizacji"))
        # --------------------------

        # Suwak (już go masz)
        slider = tk.Scale(row, variable=self.rotate_var,
                          from_=0, to=360, orient="horizontal",
                          showvalue=False, sliderlength=12)
        slider.pack(side="left", fill="x", expand=True, padx=(3, 0))
        
        entry = tk.Entry(row, textvariable=entry_var,
                         width=4, font=("Arial", 9), justify="right")
        entry.pack(side="left", padx=(3, 0))
        tk.Label(row, text="°", font=("Arial", 9),
                 fg="gray50", width=2).pack(side="left")

        def on_slide(val, ev=entry_var):
            ev.set(str(int(float(val))))
            self._write_rotate()
        def on_entry(event):
            try:
                v = max(0, min(360, int(entry_var.get())))
                self.rotate_var.set(v); entry_var.set(str(v))
                self._write_rotate()
            except ValueError:
                entry_var.set(str(self.rotate_var.get()))
        slider.config(command=on_slide)
        entry.bind("<Return>",   on_entry)
        entry.bind("<FocusOut>", on_entry)

    def _build_smooth(self, parent, current):
        lf = tk.LabelFrame(parent, text=self.T.get("section_smoothing", "Wygładzanie"), 
                           font=("Arial", 9, "bold"), padx=5, pady=4)
        lf.pack(fill="x", pady=(0, 4))

        # Twoje sprawdzone mapowanie z bars.py
        mapping = {
            "setgravitystep": "label_gravity",
            "setsmoothfactor": "label_smooth_factor",
            "setavgframes": "label_avg_frames",
            "setfftscale": "label_fft_scale",
            "setfftcutoff": "label_bass_cutoff"
        }

        for p in SMOOTH_PARAMS:
            p_list = list(p)
            
            # ZABEZPIECZENIE: Jeśli krotka w circle ma 7 elementów, 
            # wstawiamy brakujący 'step' na indeksie 6, żeby p_list[7] (tooltip) był na swoim miejscu.
            if len(p_list) == 7:
                p_list.insert(6, 0.0001) # domyślny krok dla suwaków float

            json_key = mapping.get(p_list[0])
            if json_key:
                # Tłumaczenie nazwy suwaka
                p_list[1] = self.T.get(json_key, p_list[1])
                # Tłumaczenie tooltipa (pytajnika)
                tip_key = json_key.replace("label_", "tooltip_")
                p_list[7] = self.T.get(tip_key, p_list[7])
            
            # Wywołanie poprawnej funkcji renderującej (zgodnie z bars)
            self._float_slider_row(lf, tuple(p_list), current)

    def _build_flags(self, parent, current):
        lf = tk.LabelFrame(parent, text=self.T.get("section_switches", "Przełączniki"), 
                           font=("Arial", 9, "bold"), padx=5, pady=4)
        lf.pack(fill="x")

        # Mapa: Techniczny klucz -> Klucz w Twoim JSON
        mapping_flags = {
            "C_FILL":   "label_grad_fill",
            "C_SMOOTH": "label_circle_sharp",
            "INVERT":   "label_swap_lr"
        }

        for key, label, tooltip in FLAG_PARAMS:
            if key in _UNIMPLEMENTED:
                continue
            raw = current.get(key, 0)
            var = tk.BooleanVar(value=bool(int(raw)))
            self.vars[key] = var
            
            json_key = mapping_flags.get(key)
            if json_key:
                translated_label = self.T.get(json_key, label)
                tip_key = json_key.replace("label_", "tooltip_")
                translated_tip = self.T.get(tip_key, tooltip)
            else:
                translated_label = label
                translated_tip = tooltip

            # Jeśli JSON zwrócił pusty tooltip, weź domyślny z kodu
            if not translated_tip or translated_tip == tip_key:
                translated_tip = tooltip

            row = tk.Frame(lf)
            row.pack(fill="x", pady=1)
            tk.Checkbutton(row, text=translated_label, variable=var, font=("Arial", 9),
                           command=lambda k=key, v=var: self._write_flag(k, v)).pack(side="left")
            _tip(row, "?", translated_tip)

    def _build_profiles(self, parent):
        lf = tk.LabelFrame(parent, text=self.T.get("section_profiles_circle", "Shader profiles circle"),
                           font=("Arial", 9, "bold"), padx=5, pady=4)
        lf.pack(fill="x", pady=(0, 4))

        profiles = get_shader_profiles_for_module("circle")
        names    = sorted(profiles.keys())
        self.profile_var = tk.StringVar()
        self.profile_cb  = ttk.Combobox(lf, textvariable=self.profile_var,
                                        values=names, state="readonly",
                                        font=("Arial", 9))
        self.profile_cb.pack(fill="x", pady=(0, 3))
        if names: self.profile_cb.current(0)

        tk.Label(lf, text=self.T.get("label_profiles_hint_shape", "Shape & options (colors unchanged)"),
                 font=("Arial", 7), fg="gray50").pack(anchor="w")

        btn_row = tk.Frame(lf)
        btn_row.pack(fill="x", pady=(4, 0))
        tk.Button(btn_row, text=self.T.get("btn_apply", "Apply"), command=self._apply_profile,
                  bg="#00695c", fg="white", font=("Arial", 8)
                  ).pack(side="left", expand=True, fill="x", padx=(0, 2))
        tk.Button(btn_row, text=self.T.get("btn_save_new", "Save new"), command=self._save_profile,
                  bg="#37474f", fg="white", font=("Arial", 8)
                  ).pack(side="left", expand=True, fill="x", padx=(0, 2))
        tk.Button(btn_row, text=self.T.get("btn_delete", "Delete"), command=self._delete_profile,
                  bg="#b71c1c", fg="white", font=("Arial", 8)
                  ).pack(side="left")

        rf = tk.LabelFrame(parent, text=self.T.get("section_reset", "Reset"),
                           font=("Arial", 9, "bold"), padx=5, pady=4)
        rf.pack(fill="x", pady=(4, 0))
        tk.Button(rf, text=self.T.get("btn_reset_shader_circle", "Reset circle shader"), command=self._reset_shader,
                  bg="#5d4037", fg="white", font=("Arial", 8)
                  ).pack(fill="x")

    def _slider_row(self, parent, param_def, current):
        key, label, vmin, vmax, default, unit, tooltip = param_def
        cur = int(current.get(key, default))
        var = tk.IntVar(value=cur)
        self.vars[key] = var
        entry_var = tk.StringVar(value=str(cur))

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
            ev.set(str(int(float(val))))
            self._debounce(k, int(float(val)))

        def on_entry(event, sv=var, ev=entry_var, lo=vmin, hi=vmax, k=key):
            try:
                v = max(lo, min(hi, int(ev.get())))
                sv.set(v); ev.set(str(v))
                self._debounce(k, v)
            except ValueError:
                ev.set(str(sv.get()))

        slider.config(command=on_slide)
        entry.bind("<Return>",   on_entry)
        entry.bind("<FocusOut>", on_entry)

    def _write_rotate(self):
        deg = int(self.rotate_var.get())
        glsl_val = f"{deg * 3.14159265359 / 180.0:.6f}"
        _write_raw_define(_circle_glsl(), "ROTATE", glsl_val)
        self._schedule_restart()

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

    def _write_flag(self, key, var):
        _write_flag_defines(_circle_glsl(), {key: 1 if var.get() else 0})
        self._schedule_restart()

    def _debounce(self, key, value):
        _write_defines(_circle_glsl(), {key: value}, SHAPE_PARAMS)
        self._schedule_restart()

    def _schedule_restart(self):
        if hasattr(self, "_rjob"):
            try: self.app.root.after_cancel(self._rjob)
            except Exception: pass
        from gui.glava import glava_restart
        self._rjob = self.app.root.after(
            300, lambda: glava_restart("circle", extra_flags=getattr(self.app, "extra_flags", "--desktop"), after_fn=self.app.update_status))

    def _apply_profile(self):
        name = self.profile_var.get()
        if not name: return
        profiles = get_shader_profiles_for_module("circle")
        if name not in profiles: return
        apply_params(profiles[name], self.app)
        self.app.rebuild_module_tab()
        from gui.glava import glava_restart
        glava_restart("circle", extra_flags=getattr(self.app, "extra_flags", "--desktop"), after_fn=self.app.update_status)

    def _save_profile(self):
        name = simpledialog.askstring(
            self.T.get("dialog_profile_title", "Nowy profil"),
            self.T.get("dialog_profile_name", "Enter profile name:"))
        if not name:
            return
        existing = get_shader_profiles_for_module("circle")
        if name in existing:
            if not messagebox.askyesno(
                    self.T.get("dialog_overwrite_title", "Nadpisać profil?"),
                    self.T.get("dialog_overwrite_msg",
                               "Profil '{}' już istnieje. Nadpisać?").format(name)):
                return
        save_shader_profile_for_module("circle", name, collect_params(self.app))
        self._refresh_cb()
        self.profile_var.set(name)

    def _delete_profile(self):
        name = self.profile_var.get()
        if name and messagebox.askyesno("", self.T.get("dialog_delete_confirm", "Are you sure you want to delete profile") + f" '{name}'?"):
            delete_shader_profile_for_module("circle", name)
            self._refresh_cb()

    def _refresh_cb(self):
        names = sorted(get_shader_profiles_for_module("circle").keys())
        self.profile_cb["values"] = names
        if names: self.profile_cb.current(0)

    def _reset_shader(self):
        if messagebox.askyesno(self.T.get("section_reset", "Reset"), self.T.get("confirm_reset_circle", "Restore default circle shader?")):
            reset_shader(self.app)
            self.app.rebuild_module_tab()
            from gui.glava import glava_restart
            glava_restart("circle", extra_flags=getattr(self.app, "extra_flags", "--desktop"), after_fn=self.app.update_status)


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

def _read_flag_defines(path):
    result = {p[0]: 0 for p in FLAG_PARAMS}
    if not os.path.exists(path): return result
    with open(path) as f: content = f.read()
    for p in FLAG_PARAMS:
        m = re.search(rf'^#define\s+{p[0]}\s+(\S+)', content, re.MULTILINE)
        if m:
            try: result[p[0]] = int(m.group(1))
            except ValueError: pass
    return result

def _write_flag_defines(path, params):
    if not os.path.exists(path): return
    keys = {p[0] for p in FLAG_PARAMS}
    with open(path) as f: content = f.read()
    for key, val in params.items():
        if key not in keys: continue
        new = re.sub(rf'^(#define\s+{key}\s+)\S+', rf'\g<1>{val}',
                     content, flags=re.MULTILINE)
        content = new if new != content else content + f"\n#define {key} {val}\n"
    with open(path, "w") as f: f.write(content)

def _read_raw_define(path, key):
    if not os.path.exists(path): return None
    with open(path) as f: content = f.read()
    m = re.search(rf'^#define\s+{key}\s+(.+)$', content, re.MULTILINE)
    return m.group(1).strip() if m else None

def _write_raw_define(path, key, val):
    if not os.path.exists(path): return
    with open(path) as f: content = f.read()
    # Usuń wszystkie wystąpienia tego define (zapobiega duplikacji)
    content = re.sub(rf'^#define\s+{key}\s+.*$\n?', '', content, flags=re.MULTILINE)
    # Znajdź miejsce wstawienia — po ostatnim #define lub na końcu
    m = list(re.finditer(r'^#define\s+\w+', content, re.MULTILINE))
    if m:
        insert_pos = m[-1].end()
        rest = content[insert_pos:]
        eol = rest.find('\n')
        insert_pos += eol + 1 if eol >= 0 else len(rest)
        content = content[:insert_pos] + f"#define {key} {val}\n" + content[insert_pos:]
    else:
        content = content.rstrip() + f"\n#define {key} {val}\n"
    with open(path, "w") as f: f.write(content)

def _rotate_to_deg(raw):
    """Konwertuje wartość GLSL ROTATE (radiany) na stopnie 0-360."""
    # obsługa starych wartości symbolicznych
    sym = {"0": 0, "(PI / 2)": 90, "PI": 180, "(3 * PI / 2)": 270}
    if raw.strip() in sym:
        return sym[raw.strip()]
    try:
        rad = float(raw.strip())
        deg = round(rad * 180.0 / 3.14159265359)
        return deg % 360
    except ValueError:
        return 90

def _deg_to_rotate(deg):
    return f"{deg * 3.14159265359 / 180.0:.6f}"

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
        sv = str(int(val)) if key == "setavgframes" else f"{float(val):.4f}".rstrip("0").rstrip(".")
        new = re.sub(rf'^(#request\s+{key}\s+)\S+', rf'\g<1>{sv}',
                     content, flags=re.MULTILINE)
        content = new if new != content else content + f"\n#request {key} {sv}\n"
    with open(path, "w") as f: f.write(content)

def _tip(parent, label, text):
    import tkinter as tk
    if not text: return
    lbl = tk.Label(parent, text=label, font=("Arial", 8),
                   fg="#1565c0", cursor="question_arrow",
                   relief="groove", padx=2)
    lbl.pack(side="left", padx=(2, 0))
    tip_window = [None]
    def show(e):
        x = lbl.winfo_rootx() + 20
        y = lbl.winfo_rooty() + 20
        tw = tk.Toplevel(lbl)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(tw, text=text, justify="left", bg="#ffffcc", relief="solid", bd=1,
                 font=("Arial", 8), padx=4, pady=2).pack()
        tip_window[0] = tw
    def hide(e):
        if tip_window[0]: tip_window[0].destroy(); tip_window[0] = None
    lbl.bind("<Enter>", show)
    lbl.bind("<Leave>", hide)
