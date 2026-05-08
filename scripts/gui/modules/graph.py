# =============================================================================
# gui/modules/graph.py
#
# Plik konfiguracyjny: ~/.config/glava/graph.glsl
# Parametry wygładzania: ~/.config/glava/smooth_parameters.glsl (wspólne)
#
# Wzorzec GUI: bars.py v5 (grid w LabelFrame, ttk.*, Forest-ttk-theme)
# =============================================================================

import os, re
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from ..core import CONFIG_DIR, GLAVA_DIR, RC_GLSL
from ..widgets import AccelSlider
from ..core import (
    get_shader_profiles_for_module,
    save_shader_profile_for_module,
    delete_shader_profile_for_module,
)

def _graph_glsl():  return os.path.join(GLAVA_DIR, "graph.glsl")
def _smooth_glsl(): return os.path.join(GLAVA_DIR, "smooth_parameters.glsl")
def _graph_tmpl():  return os.path.join(GLAVA_DIR, "graph_colors.frag")
def _graph_1frag(): return os.path.join(GLAVA_DIR, "graph", "1.frag")

# (klucz, etykieta, min, max, domyślna, jednostka, tooltip)
SHAPE_PARAMS = [
    ("VSCALE",   "Wzmocnienie",   50, 800, 350, "",
     "Skala pionowa sygnału audio\nWiększe = wyższy wykres"),
    ("GRADIENT", "Rozświetlenie",  0, 100,   0, "%",
     "Rozświetlenie środka wykresu\n0 = brak, 100 = maksymalne"),
]

# (klucz, etykieta, min, max, domyślna, jednostka, krok, tooltip)
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

# (klucz, etykieta, domyślna, tooltip)
FLAG_PARAMS = [
    ("DIRECTION",      "Kierunek: do środka",    1, "Zmienia kierunek rysowania wykresu"),
    ("DRAW_OUTLINE",   "Rysuj obramowanie",       0, "Dodaje linię obramowania wokół wykresu"),
    ("DRAW_HIGHLIGHT", "Podświetlenie krawędzi",  0, "Dodaje efekt blasku na górnej krawędzi"),
    ("ANTI_ALIAS",     "Wygładzanie krawędzi",    1, "Wymaga ustawienia przezroczystości xroot lub none"),
    ("JOIN_CHANNELS",  "Łącz kanały w środku",    1, "Łączy lewy i prawy kanał w jedną spójną formę"),
    ("INVERT",         "Odbicie pionowe",          0, "Odwraca wykres do góry nogami"),
]

ALL_DEFINE_KEYS = {p[0] for p in SHAPE_PARAMS} | {p[0] for p in FLAG_PARAMS}


def build_params(parent, app, T):
    GraphParamWidget(parent, app, T).build()


def collect_params(app):
    p = {}
    p.update(_read_defines(_graph_glsl(), SHAPE_PARAMS))
    p.update(_read_flag_defines(_graph_glsl()))
    p.update(_read_smooth(_smooth_glsl()))
    return p


def apply_params(params, app):
    _write_defines(_graph_glsl(), params, SHAPE_PARAMS)
    _write_flag_defines(_graph_glsl(), params)
    _write_smooth(_smooth_glsl(), params)


def reset_shader(app):
    import shutil
    tmpl = _graph_tmpl()
    live = _graph_1frag()
    if os.path.exists(tmpl):
        os.makedirs(os.path.dirname(live), exist_ok=True)
        shutil.copy2(tmpl, live)
    defaults = {p[0]: p[4] for p in SHAPE_PARAMS}
    defaults.update({p[0]: 0 for p in FLAG_PARAMS})
    defaults["DIRECTION"] = 1
    defaults["DRAW_HIGHLIGHT"] = 1
    _write_defines(_graph_glsl(), defaults, SHAPE_PARAMS)
    _write_flag_defines(_graph_glsl(), defaults)


class GraphParamWidget:
    def __init__(self, parent, app, T):
        self.parent = parent
        self.app    = app
        self.T      = T
        self.vars   = {}

    def build(self):
        current = collect_params(self.app)

        left  = ttk.Frame(self.parent)
        right = ttk.Frame(self.parent)
        left.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)
        right.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)
        self.parent.columnconfigure(0, weight=1, uniform="gc")
        self.parent.columnconfigure(1, weight=1, uniform="gc")
        self.parent.rowconfigure(0, weight=1)

        self._build_shape(left, current)
        self._build_flags(left, current)
        self._build_smooth(right, current)
        self._build_profiles(right)

    # ── Kształt ──────────────────────────────────────────────────────────────

    def _build_shape(self, parent, current):
        lf = ttk.LabelFrame(parent, text=self.T.get("section_shape", "Kształt"),
                            padding=(15, 10))
        lf.pack(fill="x", padx=10, pady=10)
        lf.columnconfigure(2, weight=1)

        mapping = {
            "VSCALE":   "label_gain",
            "GRADIENT": "label_gradient",
        }

        for idx, p in enumerate(SHAPE_PARAMS):
            p_list = list(p)
            json_key = mapping.get(p[0])
            if json_key:
                p_list[1] = self.T.get(json_key, p[1])
                p_list[6] = self.T.get(json_key.replace("label_", "tooltip_"), p[6])
            self._slider_row(lf, tuple(p_list), current, idx)

    # ── Przełączniki ─────────────────────────────────────────────────────────

    def _build_flags(self, parent, current):
        lf = ttk.LabelFrame(parent, text=self.T.get("section_switches", "Przełączniki"), padding=(15, 10))
        lf.pack(fill="x", padx=10, pady=10)

        # Konfiguracja kolumn, żeby pasowały do tych z suwaków
        lf.columnconfigure(2, weight=1)

        mapping_flags = {
            "DIRECTION":      "label_inward",
            "DRAW_OUTLINE":   "label_draw_border",
            "DRAW_HIGHLIGHT": "label_edge_glow",
            "ANTI_ALIAS":     "label_edge_smooth",
            "JOIN_CHANNELS":  "label_join_center",
            "INVERT":         "label_invert_spectrum",
        }

        # Zmieniona pętla - pobieramy cały element 'p', a potem wyciągamy interesujące nas dane
        for idx, p in enumerate(FLAG_PARAMS):
            key = p[0]      # Pierwszy element to zawsze klucz (np. "DRAW_FILL")
            label = p[1]    # Drugi to etykieta domyślna
            tooltip = p[-1] # Ostatni to zawsze tooltip
            
            raw = current.get(key, 0)
            var = tk.BooleanVar(value=bool(int(raw)))
            self.vars[key] = var
            
            json_key = mapping_flags.get(key)
            translated_label = self.T.get(json_key, label) if json_key else label
            tip_key = json_key.replace("label_", "tooltip_") if json_key else None
            translated_tip = self.T.get(tip_key, tooltip) if tip_key else tooltip

            # Rysowanie Checkbuttona
            ttk.Checkbutton(
                lf,
                text=translated_label,
                width=18, 
                variable=var,
                command=lambda k=key, v=var: self._write_flag(k, v)
            ).grid(row=idx, column=0, sticky="w", pady=2, padx=(10, 0))
            
            # Rysowanie pytajnika z tooltipem
            if translated_tip:
                t = _tip(lf, "?", translated_tip)
                if t:
                    t.grid(row=idx, column=1, sticky="w", padx=(0, 5), pady=2)

    # ── Wygładzanie ───────────────────────────────────────────────────────────

    def _build_smooth(self, parent, current):
        lf = ttk.LabelFrame(parent, text=self.T.get("section_smoothing", "Wygładzanie"),
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
            json_key = mapping.get(p[0])
            if json_key:
                p_list[1] = self.T.get(json_key, p[1])
                p_list[7] = self.T.get(json_key.replace("label_", "tooltip_"), p[7])
            self._float_slider_row(lf, tuple(p_list), current, idx)

    # ── Profile ───────────────────────────────────────────────────────────────

    def _build_profiles(self, parent):
        lf = ttk.LabelFrame(parent,
                            text=self.T.get("section_profiles_graph", "Shader profiles graph"),
                            padding=(15, 10))
        lf.pack(fill="x", padx=10, pady=10)

        profiles = get_shader_profiles_for_module("graph")
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
                   command=self._delete_profile).pack(side="left")

        ttk.Button(lf, text=self.T.get("btn_reset_shader_graph", "Reset graph shader"),
                   command=self._reset_shader,
                   style="Accent.TButton").pack(fill="x", pady=(4, 0))

    # ── Wiersze suwaków (grid) ────────────────────────────────────────────────

    def _slider_row(self, parent, param_def, current, row_idx):
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
            self._debounce(k, int(round(v)))

        slider = AccelSlider(parent, vmin=vmin, vmax=vmax, value=cur,
                             step=1, on_change=on_change)
        slider.grid(row=row_idx, column=2, padx=10, pady=5, sticky="ew")
        ttk.Label(parent, text=unit if unit else " ", width=4).grid(
            row=row_idx, column=3, padx=(5, 10), pady=5, sticky="e")

    def _float_slider_row(self, parent, param_def, current, row_idx):
        key, label, vmin, vmax, default, unit, step, tooltip = param_def
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
            self._debounce_smooth(k, v)

        slider = AccelSlider(parent, vmin=vmin, vmax=vmax, value=cur,
                             step=step, is_float=True, decimals=dec,
                             on_change=on_change)
        slider.grid(row=row_idx, column=2, padx=10, pady=5, sticky="ew")
        ttk.Label(parent, text=" ", width=4).grid(
            row=row_idx, column=3, padx=(5, 10), pady=5, sticky="e")

    # ── Zapis ─────────────────────────────────────────────────────────────────

    def _write_flag(self, key, var):
        val = 1 if var.get() else (-1 if key == "DIRECTION" else 0)
        _write_flag_defines(_graph_glsl(), {key: val})
        if key == "INVERT":
            self._update_geometry_for_flip(bool(val))
        self._schedule_restart()

    def _update_geometry_for_flip(self, flipped):
        try:
            from ..geometry import get_screen_info, calc_geometry, write_geometry
            from ..core import RC_GLSL
            si = get_screen_info()
            x, y, w, h = calc_geometry("graph", si[0], si[1], si[4], si[3],
                                        flipped=flipped)
            write_geometry(RC_GLSL, x, y, w, h)
        except Exception:
            pass

    def _debounce(self, key, value):
        _write_defines(_graph_glsl(), {key: value}, SHAPE_PARAMS)
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
                "graph",
                extra_flags=getattr(self.app, "extra_flags", "--desktop"),
                after_fn=self.app.update_status))

    def _apply_profile(self):
        name = self.profile_var.get()
        if not name: return
        profiles = get_shader_profiles_for_module("graph")
        if name not in profiles: return
        apply_params(profiles[name], self.app)
        self.app.rebuild_module_tab()
        from gui.glava import glava_restart
        glava_restart("graph", extra_flags=getattr(self.app, "extra_flags", "--desktop"),
                      after_fn=self.app.update_status)

    def _save_profile(self):
        name = simpledialog.askstring("Nowy profil",
                                      self.T.get("dialog_profile_name", "Enter profile name:"))
        if not name: return
        save_shader_profile_for_module("graph", name, collect_params(self.app))
        self._refresh_cb()
        self.profile_var.set(name)

    def _delete_profile(self):
        name = self.profile_var.get()
        if name and messagebox.askyesno(
                "", self.T.get("dialog_delete_confirm",
                               "Are you sure you want to delete profile") + f" '{name}'?"):
            delete_shader_profile_for_module("graph", name)
            self._refresh_cb()

    def _refresh_cb(self):
        names = sorted(get_shader_profiles_for_module("graph").keys())
        self.profile_cb["values"] = names
        if names: self.profile_cb.current(0)

    def _reset_shader(self):
        if messagebox.askyesno(self.T.get("section_reset", "Reset"),
                               self.T.get("confirm_reset_graph", "Restore default graph shader?")):
            reset_shader(self.app)
            self.app.rebuild_module_tab()
            from gui.glava import glava_restart
            glava_restart("graph", extra_flags=getattr(self.app, "extra_flags", "--desktop"),
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
        dec = _decimals(p[6])
        sv = str(int(val)) if key == "setavgframes" else f"{float(val):.{dec}f}"
        content = re.sub(rf'^#request\s+{key}\s+\S+\n?', '',
                         content, flags=re.MULTILINE)
        content = content.rstrip() + f"\n#request {key} {sv}\n"
    with open(path, "w") as f: f.write(content)
