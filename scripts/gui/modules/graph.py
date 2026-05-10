# =============================================================================
# gui/modules/graph.py
#
# Plik konfiguracyjny: ~/.config/glava/graph.glsl
# Parametry wygładzania: ~/.config/glava/smooth_parameters.glsl (wspólne)
#
# Wzorzec GUI: bars.py v5 (grid w LabelFrame, ttk.*, Forest-ttk-theme)
# =============================================================================

import os
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from ..core import CONFIG_DIR, GLAVA_DIR, RC_GLSL, SMOOTH_PARAMS
from ..widgets import AccelSlider
from . import glsl_io
from ..core import get_shader_profiles_for_module
from .base import BaseParamWidget

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
    p.update(glsl_io.read_defines(_graph_glsl(), SHAPE_PARAMS))
    p.update(glsl_io.read_flag_defines(_graph_glsl(), FLAG_PARAMS))
    p.update(glsl_io.read_smooth(_smooth_glsl(), SMOOTH_PARAMS))
    return p


def apply_params(params, app):
    glsl_io.write_defines(_graph_glsl(), params, SHAPE_PARAMS)
    glsl_io.write_flag_defines(_graph_glsl(), params, FLAG_PARAMS)
    glsl_io.write_smooth(_smooth_glsl(), params, SMOOTH_PARAMS)


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
    glsl_io.write_defines(_graph_glsl(), defaults, SHAPE_PARAMS)
    glsl_io.write_flag_defines(_graph_glsl(), defaults, FLAG_PARAMS)


class GraphParamWidget(BaseParamWidget):
    MODULE_NAME  = "graph"
    SHAPE_PARAMS = SHAPE_PARAMS

    def build_left(self, parent, current):
        self._build_shape(parent, current)
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
        title = self.T.get("section_switches", "Przełączniki")
        lf = self._detachable_lf(parent, title, self._build_flags, current)
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
                t = glsl_io.tip(lf, "?", translated_tip)
                if t:
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
        t = glsl_io.tip(parent, "?", tooltip)
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
        dec = glsl_io.decimals(step)

        ttk.Label(parent, text=label, width=12, anchor="w").grid(
            row=row_idx, column=0, padx=(10, 5), pady=5, sticky="w")
        t = glsl_io.tip(parent, "?", tooltip)
        if t: t.grid(row=row_idx, column=1, padx=5, pady=5)

        def on_change(v, k=key):
            var.set(v)
            self._debounce(k, v, "smooth")

        slider = AccelSlider(parent, vmin=vmin, vmax=vmax, value=cur,
                             step=step, is_float=True, decimals=dec,
                             on_change=on_change)
        slider.grid(row=row_idx, column=2, padx=10, pady=5, sticky="ew")
        ttk.Label(parent, text=" ", width=4).grid(
            row=row_idx, column=3, padx=(5, 10), pady=5, sticky="e")

    # ── Zapis ─────────────────────────────────────────────────────────────────

    def _write_flag(self, key, var):
        val = 1 if var.get() else (-1 if key == "DIRECTION" else 0)
        glsl_io.write_flag_defines(_graph_glsl(), {key: val}, FLAG_PARAMS)
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

    def _reset_shader(self):
        if messagebox.askyesno(self.T.get("section_reset", "Reset"),
                               self.T.get("confirm_reset_graph", "Restore default graph shader?")):
            reset_shader(self.app)
            self.app.rebuild_module_tab()
            from gui.glava import glava_restart
            glava_restart("graph", extra_flags=getattr(self.app, "extra_flags", "--desktop"),
                          after_fn=self.app.update_status)


