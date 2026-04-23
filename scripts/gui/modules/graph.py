# =============================================================================
# gui/modules/graph.py
# Plugin parametrów dla modułu graph.
#
# Plik konfiguracyjny: ~/.config/glava/graph.glsl
# Parametry wygładzania: ~/.config/glava/smooth_parameters.glsl (wspólne)
#
# Obsługiwane parametry (graph.glsl):
#   VSCALE        int   skala pionowa (wzmocnienie)
#   GRADIENT      int   szybkość gradientu w px
#   DIRECTION     -1/1  kierunek rysowania (-1=na zewnątrz, 1=do środka)
#   DRAW_OUTLINE  0/1   rysuj obramowanie
#   DRAW_HIGHLIGHT 0/1  rysuj podświetlenie krawędzi
#   ANTI_ALIAS    0/1   wygładzanie krawędzi (wymaga xroot/none opacity)
#   JOIN_CHANNELS 0/1   łącz kanały w środku
#   INVERT        0/1   odbicie pionowe
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

def _graph_glsl():  return os.path.join(GLAVA_DIR, "graph.glsl")
def _smooth_glsl(): return os.path.join(GLAVA_DIR, "smooth_parameters.glsl")
def _graph_tmpl():  return os.path.join(GLAVA_DIR, "graph_colors.frag")
def _graph_1frag(): return os.path.join(GLAVA_DIR, "graph", "1.frag")

SHAPE_PARAMS = [
    ("VSCALE",   "Wzmocnienie",   50, 800, 350, "",
     "Skala pionowa sygnału audio\nWiększe = wyższy wykres"),
    ("GRADIENT", "Rozświetlenie",  0, 100,   0, "%",
     "Rozświetlenie środka wykresu\n0 = brak, 100 = maksymalne"),
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

FLAG_PARAMS = [
    ("DIRECTION",     "Kierunek: do środka", 1, "Zmienia kierunek rysowania wykresu (do wewnątrz lub na zewnątrz)"),
    ("DRAW_OUTLINE",   "Rysuj obramowanie",   0, "Dodaje linię obramowania wokół wykresu"),
    ("DRAW_HIGHLIGHT", "Podświetlenie krawędzi", 0, "Dodaje efekt blasku na górnej krawędzi"),
    ("ANTI_ALIAS",    "Wygładzanie krawędzi", 1, "Wymaga ustawienia przezroczystości xroot lub none"),
    ("JOIN_CHANNELS", "Łącz kanały w środku", 1, "Łączy lewy i prawy kanał w jedną spójną formę"),
    ("INVERT",        "Odbicie pionowe",      0, "Odwraca wykres do góry nogami"),
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

        left  = tk.Frame(self.parent)
        right = tk.Frame(self.parent)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        right.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        self.parent.columnconfigure(0, weight=1, uniform="gc")
        self.parent.columnconfigure(1, weight=1, uniform="gc")
        self.parent.rowconfigure(0, weight=1)

        self._build_shape(left, current)
        self._build_flags(left, current)
        self._build_smooth(right, current)
        self._build_profiles(right)

    def _build_shape(self, parent, current):
        # Definiujemy 'lf' na samym początku funkcji
        lf = tk.LabelFrame(parent, text=self.T.get("section_shape", "Kształt"),
                           font=("Arial", 9, "bold"), padx=5, pady=4)
        lf.pack(fill="x", pady=(0, 4))

        # Twoje SHAPE_PARAMS (zgodnie z plikiem mają 7 elementów)
        # Indeks 1 to label, Indeks 6 to tooltip
        mapping_shape = {
            "VSCALE":    "label_gain",
            "GRADIENT":  "label_gradient"
        }

        for p in SHAPE_PARAMS:
            p_list = list(p)
            json_key = mapping_shape.get(p[0])
            
            if json_key:
                # Tłumaczenie nazwy (Wzmocnienie / Gradient)
                p_list[1] = self.T.get(json_key, p[1])
                
                # Tłumaczenie tooltipa (indeks 6)
                # json_key.replace zamieni "label_gain" na "tooltip_gain"
                tip_key = json_key.replace("label_", "tooltip_")
                p_list[6] = self.T.get(tip_key, p[6])
            
            # Teraz 'lf' jest na pewno zdefiniowane i dostępne tutaj
            self._slider_row(lf, tuple(p_list), current)

    def _build_flags(self, parent, current):
        lf = tk.LabelFrame(parent, text=self.T.get("section_switches", "Przełączniki"),
                           font=("Arial", 9, "bold"), padx=5, pady=4)
        lf.pack(fill="x", pady=(0, 4))

        # Mapowanie technicznych nazw z FLAG_PARAMS na Twoje klucze label_ w pl.json
        mapping_flags = {
            "DIRECTION":      "label_inward",
            "DRAW_OUTLINE":   "label_draw_border",
            "DRAW_HIGHLIGHT": "label_edge_glow",
            "ANTI_ALIAS":     "label_edge_smooth",
            "JOIN_CHANNELS":  "label_join_center",
            "INVERT":         "label_invert_spectrum"
        }

        for i, p in enumerate(FLAG_PARAMS):
            key, label_def, default, tip_def = p
            
            # 1. Pobieramy etykietę z JSON
            json_key = mapping_flags.get(key)
            display_label = self.T.get(json_key, label_def)
            
            # 2. URUCHOMIENIE TOOLTIPÓW:
            # Jeśli mamy json_key (np. "label_inward"), zamieniamy go na "tooltip_inward"
            json_tip_key = json_key.replace("label_", "tooltip_") if json_key else None
            
            # Pobieramy opis z JSON, a jeśli go tam nie ma, bierzemy tip_def (angielski z kodu)
            display_tip = self.T.get(json_tip_key, tip_def)
            
            var = tk.BooleanVar(value=bool(int(current.get(key, default))))
            self.vars[key] = var
            
            row = tk.Frame(lf)
            row.pack(fill="x", anchor="w")
            
            cb = tk.Checkbutton(row, text=display_label, variable=var,
                                font=("Arial", 9),
                                command=lambda k=key, v=var: self._write_flag(k, v))
            cb.pack(side="left")
            
            # Wywołanie Twojej funkcji rysującej pytajnik (linia 255 w graph.py)
            if display_tip:
                _tip(row, "?", display_tip)

    def _build_smooth(self, parent, current):
        lf = tk.LabelFrame(parent, text=self.T.get("section_smooth", "Wygładzanie"),
                           font=("Arial", 9, "bold"), padx=5, pady=4)
        lf.pack(fill="x")

        # Wypełniamy mapowanie zgodnie z Twoim pl.json
        mapping = {
            "setgravitystep":  "label_gravity",
            "setsmoothfactor": "label_smooth_factor",
            "setavgframes":    "label_avg_frames",
            "setfftscale":     "label_fft_scale",
            "setfftcutoff":    "label_bass_cutoff"
        }

        for p in SMOOTH_PARAMS:
            p_list = list(p)
            
            # Twoja logika: jeśli lista ma 7 elementów, wstawiamy 'step' (0.0001) na indeks 6.
            # To sprawia, że oryginalny element z indeksu 6 (tooltip) ląduje na indeksie 7.
            if len(p_list) == 7:
                p_list.insert(6, 0.0001)

            json_key = mapping.get(p_list[0])
            if json_key:
                # 1. Tłumaczenie etykiety suwaka
                p_list[1] = self.T.get(json_key, p_list[1])
                
                # 2. Tłumaczenie tooltipa (SZUKAMY W JSON: label_ -> tooltip_)
                # Celujemy w indeks 7, bo tam teraz jest opis po wykonaniu .insert()
                tip_key = json_key.replace("label_", "tooltip_")
                p_list[7] = self.T.get(tip_key, p_list[7])
            
            # Wywołanie istniejącej metody dla liczb zmiennoprzecinkowych
            self._float_slider_row(lf, tuple(p_list), current)

    def _build_profiles(self, parent):
        lf = tk.LabelFrame(parent, text=self.T.get("section_profiles_graph", "Shader profiles graph"),
                           font=("Arial", 9, "bold"), padx=5, pady=4)
        lf.pack(fill="x", pady=(0, 4))

        profiles = get_shader_profiles_for_module("graph")
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
        tk.Button(rf, text=self.T.get("btn_reset_shader_graph", "Reset graph shader"), command=self._reset_shader,
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
        if key == "DIRECTION":
            val = 1 if var.get() else -1
        else:
            val = 1 if var.get() else 0
        _write_flag_defines(_graph_glsl(), {key: val})
        self._schedule_restart()

    def _debounce(self, key, value):
        _write_defines(_graph_glsl(), {key: value}, SHAPE_PARAMS)
        self._schedule_restart()

    def _schedule_restart(self):
        if hasattr(self, "_rjob"):
            try: self.app.root.after_cancel(self._rjob)
            except Exception: pass
        from gui.glava import glava_restart
        self._rjob = self.app.root.after(
            300, lambda: glava_restart("graph", extra_flags=getattr(self.app, "extra_flags", "--desktop"), after_fn=self.app.update_status))

    def _apply_profile(self):
        name = self.profile_var.get()
        if not name: return
        profiles = get_shader_profiles_for_module("graph")
        if name not in profiles: return
        apply_params(profiles[name], self.app)
        self.app.rebuild_module_tab()
        from gui.glava import glava_restart
        glava_restart("graph", extra_flags=getattr(self.app, "extra_flags", "--desktop"), after_fn=self.app.update_status)

    def _save_profile(self):
        name = simpledialog.askstring(
            self.T.get("dialog_profile_title", "Nowy profil"),
            self.T.get("dialog_profile_name", "Enter profile name:"))
        if not name:
            return
        existing = get_shader_profiles_for_module("graph")
        if name in existing:
            if not messagebox.askyesno(
                    self.T.get("dialog_overwrite_title", "Nadpisać profil?"),
                    self.T.get("dialog_overwrite_msg",
                               "Profil '{}' już istnieje. Nadpisać?").format(name)):
                return
        save_shader_profile_for_module("graph", name, collect_params(self.app))
        self._refresh_cb()
        self.profile_var.set(name)

    def _delete_profile(self):
        name = self.profile_var.get()
        if name and messagebox.askyesno("", self.T.get("dialog_delete_confirm", "Are you sure you want to delete profile") + f" '{name}'?"):
            delete_shader_profile_for_module("graph", name)
            self._refresh_cb()

    def _refresh_cb(self):
        names = sorted(get_shader_profiles_for_module("graph").keys())
        self.profile_cb["values"] = names
        if names: self.profile_cb.current(0)

    def _reset_shader(self):
        if messagebox.askyesno(self.T.get("section_reset", "Reset"), self.T.get("confirm_reset_graph", "Restore default graph shader?")):
            reset_shader(self.app)
            self.app.rebuild_module_tab()
            from gui.glava import glava_restart
            glava_restart("graph", extra_flags=getattr(self.app, "extra_flags", "--desktop"), after_fn=self.app.update_status)


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

#def _tip(parent, label, text):
#    lbl = tk.Label(parent, text=label, font=("Arial", 8),
#                   fg="#1565c0", cursor="question_arrow",
#                   relief="groove", padx=2)
#    lbl.pack(side="left", padx=(2, 0))
#    tip = [None]
#    def show(e):
#        x = lbl.winfo_rootx() + 20
#        y = lbl.winfo_rooty() + 20
#        tip[0] = tk.Toplevel(lbl)
#        tip[0].wm_overrideredirect(True)
#        tip[0].wm_geometry(f"+{x}+{y}")
#        tk.Label(tip[0], text=text, justify="left",
#                 bg="#ffffcc", relief="solid", bd=1,
#                 font=("Arial", 8), padx=4, pady=2).pack()
#    def hide(e):
#        if tip[0]: tip[0].destroy(); tip[0] = None
#    lbl.bind("<Enter>", show)
#    lbl.bind("<Leave>", hide)

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
