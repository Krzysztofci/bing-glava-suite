# =============================================================================
# gui/modules/bars.py  v5
#
# Układ zakładki Bars ✦:
#   Lewa kolumna:  Kształt (suwaki) + Przełączniki
#   Prawa kolumna: Wygładzanie (suwaki) + [Audio | Profile szadera]
#
# Wiersz suwaka: [Etykieta 120px][?][ ────suwak──── ][wartość 42px][jednostka]
# Tryb expert: odczytywany z app.expert_mode (BooleanVar w glava-gui.py)
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

# ─── Ścieżki ─────────────────────────────────────────────────────────────────

def _bars_glsl():   return os.path.join(GLAVA_DIR, "bars.glsl")
def _smooth_glsl(): return os.path.join(GLAVA_DIR, "smooth_parameters.glsl")
def _bars_1frag():  return os.path.join(GLAVA_DIR, "bars", "1.frag")
def _bars_tmpl():   return os.path.join(GLAVA_DIR, "bars_colors.frag")

# ─── Definicje parametrów ────────────────────────────────────────────────────
# (klucz, etykieta, min, max, domyślna, jednostka, tooltip)

SHAPE_PARAMS = [
    ("BAR_WIDTH",        "Szerokość słupka",   1,  40,   5, "px",
     "Szerokość pojedynczego słupka w pikselach"),
    ("BAR_GAP",          "Odstęp",             0,  20,   1, "px",
     "Odstęp między słupkami w pikselach\n0 = słupki stykają się"),
    ("BAR_OUTLINE_WIDTH","Obramowanie",         0,  10,   1, "px",
     "Grubość obramowania słupka\n0 = brak obramowania"),
    ("C_LINE",           "Linia środkowa",      0,  10,   1, "px",
     "Grubość poziomej linii bazowej w pikselach\n"
     "Rysowana przy podstawie słupków\n0 = wyłączona"),
    ("AMPLIFY",          "Wzmocnienie",        50, 800, 300, "",
     "Mnożnik amplitudy sygnału audio\nWiększe = wyższe słupki"),
]

# (klucz, etykieta, tooltip)
FLAG_PARAMS = [
    ("DIRECTION",  "Odwróć spektrum",
     "Odwraca kolejność częstotliwości\nBas po prawej, treble po lewej"),
    ("FLIP",       "Odbicie pionowe",
     "Słupki rosną z góry okna zamiast z dołu"),
    ("MIRROR_YX",  "Pionowy pasek (Y=X)",
     "Obraca wizualizację o 90°\nRysuje pionowy pasek po lewej stronie okna\n"
     "Z 'Odbicie pionowe' = po prawej stronie"),
    ("INVERT",     "Zamień kanały L/R",
     "Zamienia lewy i prawy kanał audio\nDziała tylko przy Lustro L/R = wyłączone"),
    ("DISABLE_MONO", "Wyłącz tryb mono",
     "Wymusza wyświetlanie dwóch kanałów\nnawet gdy Lustro L/R jest włączone"),
]

# (klucz, etykieta, min, max, domyślna, jednostka, krok, tooltip)
SMOOTH_PARAMS = [
    ("setgravitystep",  "Grawitacja",      0.1, 20.0,  4.2, "",   0.1,
     "Szybkość opadania słupków po szczycie\nWiększe = szybszy zanik"),
    ("setsmoothfactor", "Wygładzanie",   0.001,  0.1, 0.025, "", 0.001,
     "Rozmiar jądra wygładzającego FFT\nMniejsze = bardziej responsywne\n"
     "Większe = płynniejsze ale wolniejsze"),
    ("setavgframes",    "Klatek avg",        1,   16,     5, "",     1,
     "Liczba klatek do uśredniania\nWiększe = płynniejsze ale z opóźnieniem\n"
     "Na T420/Intel HD3000 max ~10 bez spadku FPS"),
    ("setfftscale",     "Skala FFT",       1.0, 30.0,  10.2, "",   0.1,
     "Skala częstotliwości FFT\nNiższe = więcej miejsca na niskie częstotliwości"),
    ("setfftcutoff",    "Odcięcie basów",  0.0,  1.0,   0.3, "",  0.01,
     "Odcięcie najniższych częstotliwości FFT\n"
     "Efekt widoczny przy niskim wygładzaniu\n"
     "0 = brak odcięcia, 1 = odcięcie wszystkiego"),
]

# Audio — potęgi 2
BUF_NORMAL    = [512, 1024, 2048, 4096]
BUF_EXPERT    = [128, 256, 512, 1024, 2048, 4096, 8192, 16384]
SAMPLE_NORMAL = [256, 512, 1024, 2048]
SAMPLE_EXPERT = [256, 512, 1024, 2048, 4096]

RC_BOOL_PARAMS = [
    ("setmirror",      "Lustro L/R (mono)",
     "Uśrednia lewy i prawy kanał\nPrzy włączonym INVERT nie działa"),
    ("setinterpolate", "Interpolacja ramek",
     "Wygładza animację między klatkami audio\n"
     "Poprawia płynność ale dodaje minimalne opóźnienie"),
]

ALL_DEFINE_KEYS = {p[0] for p in SHAPE_PARAMS} | {p[0] for p in FLAG_PARAMS}
ALL_SMOOTH_KEYS = {p[0] for p in SMOOTH_PARAMS}


# ─── API dla tab_module.py ────────────────────────────────────────────────────

def build_params(parent, app, T):
    BarsParamWidget(parent, app, T).build()


def collect_params(app):
    p = {}
    p.update(_read_defines(_bars_glsl(), SHAPE_PARAMS))
    p.update(_read_flag_defines(_bars_glsl()))
    p.update(_read_smooth(_smooth_glsl()))
    p.update(_read_int_req(RC_GLSL, "setbufsize",    4096))
    p.update(_read_int_req(RC_GLSL, "setsamplesize", 1024))
    for key, _, _ in RC_BOOL_PARAMS:
        p.update(_read_bool_req(RC_GLSL, key))
    return p


def apply_params(params, app):
    _write_defines(_bars_glsl(), params, SHAPE_PARAMS)
    _write_flag_defines(_bars_glsl(), params)
    _write_smooth(_smooth_glsl(), params)
    for key in ("setbufsize", "setsamplesize"):
        if key in params:
            _write_int_req(RC_GLSL, key, int(params[key]))
    for key, _, _ in RC_BOOL_PARAMS:
        if key in params:
            _write_bool_req(RC_GLSL, key, params[key])


def reset_shader(app):
    import shutil
    tmpl, live = _bars_tmpl(), _bars_1frag()
    if os.path.exists(tmpl):
        os.makedirs(os.path.dirname(live), exist_ok=True)
        shutil.copy2(tmpl, live)
    defaults = {p[0]: p[4] for p in SHAPE_PARAMS}
    defaults.update({p[0]: 0 for p in FLAG_PARAMS})
    _write_defines(_bars_glsl(), defaults, SHAPE_PARAMS)
    _write_flag_defines(_bars_glsl(), defaults)


# ─── Widget GUI ───────────────────────────────────────────────────────────────

class BarsParamWidget:
    def __init__(self, parent, app, T):
        self.parent = parent
        self.app    = app
        self.T      = T
        self.vars   = {}
        self._buf_cb    = None
        self._sample_cb = None

    def _expert(self):
        """Odczytuje stan trybu expert z głównego okna."""
        try:
            return self.app.expert_mode.get()
        except AttributeError:
            return False

    def build(self):
        current = collect_params(self.app)

        left  = tk.Frame(self.parent)
        right = tk.Frame(self.parent)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        right.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        self.parent.columnconfigure(0, weight=1, uniform="bc")
        self.parent.columnconfigure(1, weight=1, uniform="bc")
        self.parent.rowconfigure(0, weight=1)

        # Lewa: Kształt + Przełączniki + Audio
        self._build_shape(left, current)
        self._build_flags(left, current)
        self._build_audio(left, current)

        # Prawa: Wygładzanie + Profile szadera
        self._build_smooth(right, current)
        self._build_profiles(right)

    # ── Kształt ──────────────────────────────────────────────────────────────

    def _build_shape(self, parent, current):
        lf = tk.LabelFrame(parent, text=self.T.get("section_shape", "Shape & dynamics"),
                           font=("Arial", 9, "bold"), padx=5, pady=4)
        lf.pack(fill="x", pady=(0, 4))
        for p in SHAPE_PARAMS:
            self._slider_row(lf, p[:6], current, "bars_glsl", p[6])

    # ── Przełączniki ─────────────────────────────────────────────────────────

    def _build_flags(self, parent, current):
        lf = tk.LabelFrame(parent, text=self.T.get("section_switches", "Switches"),
                           font=("Arial", 9, "bold"), padx=5, pady=4)
        lf.pack(fill="x")
        for key, label, tooltip in FLAG_PARAMS:
            raw = current.get(key, 0)
            var = tk.BooleanVar(value=bool(int(raw)))
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
        lf = tk.LabelFrame(parent, text=self.T.get("section_smoothing", "Smoothing"),
                           font=("Arial", 9, "bold"), padx=5, pady=4)
        lf.pack(fill="x", pady=(0, 4))
        for p in SMOOTH_PARAMS:
            self._float_slider_row(lf, p, current)
        tk.Label(lf, text=self.T.get("audio_affects_all", "⚠ Affects all modules"),
                 font=("Arial", 7), fg="#bf360c").pack(anchor="w", pady=(4, 0))

    # ── Audio (lewa kolumna, pod przełącznikami) ─────────────────────────────

    def _build_audio(self, parent, current):
        lf = tk.LabelFrame(parent, text=self.T.get("section_audio", "Audio"),
                           font=("Arial", 9, "bold"), padx=5, pady=4)
        lf.pack(fill="x", pady=(4, 0))

        buf_cur = int(current.get("setbufsize", 4096))
        self.vars["setbufsize"] = tk.StringVar(value=str(buf_cur))
        vals = BUF_EXPERT if self._expert() else BUF_NORMAL
        if buf_cur not in vals:
            buf_cur = min(vals, key=lambda x: abs(x - buf_cur))
            self.vars["setbufsize"].set(str(buf_cur))
        self._buf_cb = self._combo_row(
            lf, "Bufor audio", "setbufsize", vals, buf_cur,
            "Rozmiar bufora FFT — potega 2\n"
            "Wiekszy = wiecej 'grawitacji'\n"
            "512 = szybki, 4096 = ciezki")

        smp_cur = int(current.get("setsamplesize", 1024))
        self.vars["setsamplesize"] = tk.StringVar(value=str(smp_cur))
        svals = SAMPLE_EXPERT if self._expert() else SAMPLE_NORMAL
        if smp_cur not in svals:
            smp_cur = min(svals, key=lambda x: abs(x - smp_cur))
            self.vars["setsamplesize"].set(str(smp_cur))
        self._sample_cb = self._combo_row(
            lf, "Rozmiar probki", "setsamplesize", svals, smp_cur,
            "256=172UPS 512=86UPS 1024=43UPS 2048=21UPS\nZawsze <= bufor audio")

        for key, label, tooltip in RC_BOOL_PARAMS:
            raw = current.get(key, False)
            val = raw if isinstance(raw, bool) else (str(raw) == "true")
            var = tk.BooleanVar(value=val)
            self.vars[key] = var
            brow = tk.Frame(lf)
            brow.pack(fill="x", pady=1)
            tk.Checkbutton(brow, text=label, variable=var,
                           font=("Arial", 9),
                           command=lambda k=key, v=var: self._write_bool_rc(k, v)
                           ).pack(side="left")
            _tip(brow, "?", tooltip)

    # ── Profile szadera (prawa kolumna, pod wygładzaniem) ────────────────────

    def _build_profiles(self, parent):
        lf = tk.LabelFrame(parent, text=self.T.get("section_profiles_bars", "Shader profiles bars"),
                           font=("Arial", 9, "bold"), padx=5, pady=4)
        lf.pack(fill="x", pady=(4, 0))

        profiles = get_shader_profiles_for_module("bars")
        names    = sorted(profiles.keys())
        self.profile_var = tk.StringVar()
        self.profile_cb  = ttk.Combobox(lf, textvariable=self.profile_var,
                                        values=names, state="readonly",
                                        font=("Arial", 9))
        self.profile_cb.pack(fill="x", pady=(0, 3))
        if names: self.profile_cb.current(0)

        tk.Label(lf, text=self.T.get("label_profiles_hint_bars", "Shape & dynamics (colors unchanged)"),
                 font=("Arial", 7), fg="gray50").pack(anchor="w")

        btn_row = tk.Frame(lf)
        btn_row.pack(fill="x", pady=(4, 0))
        tk.Button(btn_row, text=self.T.get("btn_apply", "Apply"),
                  command=self._apply_profile,
                  bg="#00695c", fg="white", font=("Arial", 8)
                  ).pack(side="left", expand=True, fill="x", padx=(0, 2))
        tk.Button(btn_row, text=self.T.get("btn_save_new", "Save new"),
                  command=self._save_profile,
                  bg="#37474f", fg="white", font=("Arial", 8)
                  ).pack(side="left", expand=True, fill="x", padx=(0, 2))
        tk.Button(btn_row, text=self.T.get("btn_delete", "Delete"),
                  command=self._delete_profile,
                  bg="#b71c1c", fg="white", font=("Arial", 8)
                  ).pack(side="left")

        tk.Button(lf, text=self.T.get("btn_reset_shader_bars", "Reset bars shader"),
                  command=self._reset_shader,
                  bg="#5d4037", fg="white", font=("Arial", 8)
                  ).pack(fill="x", pady=(4, 0))

    def _combo_row(self, parent, label, key, values, cur, tooltip):
        row = tk.Frame(parent)
        row.pack(fill="x", pady=2)
        tk.Label(row, text=label, font=("Arial", 9),
                 width=13, anchor="w").pack(side="left")
        var = self.vars[key]
        cb = ttk.Combobox(row, textvariable=var,
                          values=[str(v) for v in values],
                          width=6, state="readonly", font=("Arial", 9))
        cb.pack(side="left")
        _tip(row, "?", tooltip)

        def on_select(e, k=key):
            try:
                v = int(var.get())
                self._validate_buf_sample(k, v)
                _write_int_req(RC_GLSL, k, int(self.vars[k].get()))
                self._schedule_restart()
            except ValueError:
                pass
        cb.bind("<<ComboboxSelected>>", on_select)
        return cb

    def _validate_buf_sample(self, changed, new_val):
        try:
            buf    = int(self.vars["setbufsize"].get())
            sample = int(self.vars["setsamplesize"].get())
        except (ValueError, KeyError):
            return
        svals = SAMPLE_EXPERT if self._expert() else SAMPLE_NORMAL
        if changed == "setbufsize" and sample > new_val:
            valid = max(v for v in svals if v <= new_val)
            self.vars["setsamplesize"].set(str(valid))
            _write_int_req(RC_GLSL, "setsamplesize", valid)
        elif changed == "setsamplesize" and new_val > buf:
            valid = max(v for v in svals if v <= buf)
            self.vars["setsamplesize"].set(str(valid))

    # ── Wiersz suwaka int — etykieta(stała) + ? + suwak + wartość + jednostka ─

    def _slider_row(self, parent, param_def, current, target, tooltip=""):
        key, label, vmin, vmax, default, unit = param_def
        cur = int(current.get(key, default))
        var = tk.IntVar(value=cur)
        self.vars[key] = var
        entry_var = tk.StringVar(value=str(cur))

        row = tk.Frame(parent)
        row.pack(fill="x", pady=2)

        # Etykieta stałej szerokości
        tk.Label(row, text=label, font=("Arial", 9),
                 width=16, anchor="w").pack(side="left")
        if tooltip:
            _tip(row, "?", tooltip)

        # Suwak — zajmuje całe dostępne miejsce
        slider = tk.Scale(row, variable=var, from_=vmin, to=vmax,
                          orient="horizontal", showvalue=False,
                          sliderlength=12, font=("Arial", 7))
        slider.pack(side="left", fill="x", expand=True, padx=(3, 0))

        # Pole wartości
        entry = tk.Entry(row, textvariable=entry_var,
                         width=5, font=("Arial", 9), justify="right")
        entry.pack(side="left", padx=(3, 0))

        # Jednostka (lub spacja dla wyrównania)
        tk.Label(row, text=unit if unit else "  ",
                 font=("Arial", 9), fg="gray50", width=3
                 ).pack(side="left")

        def on_slide(val, ev=entry_var, k=key, tgt=target):
            ev.set(str(int(float(val))))
            self._debounce(k, int(float(val)), tgt)

        def on_entry(event, sv=var, ev=entry_var,
                     lo=vmin, hi=vmax, k=key, tgt=target):
            try:
                v = max(lo, min(hi, int(ev.get())))
                sv.set(v); ev.set(str(v))
                self._debounce(k, v, tgt)
            except ValueError:
                ev.set(str(sv.get()))

        slider.config(command=on_slide)
        entry.bind("<Return>",   on_entry)
        entry.bind("<FocusOut>", on_entry)

    # ── Wiersz suwaka float ───────────────────────────────────────────────────

    def _float_slider_row(self, parent, param_def, current):
        key, label, vmin, vmax, default, unit, step, tooltip = param_def
        try:
            cur = float(current.get(key, default))
        except (ValueError, TypeError):
            cur = float(default)
        var = tk.DoubleVar(value=cur)
        self.vars[key] = var
        dec = _decimals(step)
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
        # spacja dla wyrównania (brak jednostki)
        tk.Label(row, text="  ", font=("Arial", 9), width=2).pack(side="left")

        def on_slide(val, ev=entry_var, k=key, f=fmt):
            ev.set(f.format(float(val)))
            self._debounce(k, float(val), "smooth")

        def on_entry(event, sv=var, ev=entry_var,
                     lo=vmin, hi=vmax, k=key, f=fmt):
            try:
                v = max(lo, min(hi, float(ev.get())))
                sv.set(v); ev.set(f.format(v))
                self._debounce(k, v, "smooth")
            except ValueError:
                ev.set(f.format(sv.get()))

        slider.config(command=on_slide)
        entry.bind("<Return>",   on_entry)
        entry.bind("<FocusOut>", on_entry)

    # ── Profile szadera — callbacki ──────────────────────────────────────────

    def _apply_profile(self):
        name = self.profile_var.get()
        if not name: return
        profiles = get_shader_profiles_for_module("bars")
        if name not in profiles: return
        apply_params(profiles[name], self.app)
        # Odśwież widgety
        self.app.rebuild_module_tab()
        from gui.glava import glava_restart
        glava_restart("bars", extra_flags=getattr(self.app, "extra_flags", "--desktop"), after_fn=self.app.update_status)

    def _save_profile(self):
        name = simpledialog.askstring("Nowy profil szadera", self.T.get("dialog_profile_name", "Enter profile name:"))
        if not name: return
        params = collect_params(self.app)
        save_shader_profile_for_module("bars", name, params)
        self._refresh_profile_cb()
        self.profile_var.set(name)

    def _delete_profile(self):
        name = self.profile_var.get()
        if not name: return
        if messagebox.askyesno("", self.T.get("dialog_delete_confirm", "Are you sure you want to delete profile") + f" '{name}'?"):
            delete_shader_profile_for_module("bars", name)
            self._refresh_profile_cb()

    def _refresh_profile_cb(self):
        names = sorted(get_shader_profiles_for_module("bars").keys())
        self.profile_cb["values"] = names
        if names: self.profile_cb.current(0)

    def _reset_shader(self):
        if not messagebox.askyesno(self.T.get("btn_reset_shader", "Reset shader"),
                self.T.get("confirm_reset_bars", "Restore default bars shader?") +
                "\nWartości kształtu wrócą do domyślnych."):
            return
        reset_shader(self.app)
        self.app.rebuild_module_tab()
        from gui.glava import glava_restart
        glava_restart("bars", extra_flags=getattr(self.app, "extra_flags", "--desktop"), after_fn=self.app.update_status)

    # ── Zapis ─────────────────────────────────────────────────────────────────

    def _write_flag(self, key, var):
        val = 1 if var.get() else 0
        _write_flag_defines(_bars_glsl(), {key: val})
        self._schedule_restart()

    def _write_bool_rc(self, key, var):
        _write_bool_req(RC_GLSL, key, var.get())
        self._schedule_restart()

    def _debounce(self, key, value, target):
        if target == "bars_glsl":
            _write_defines(_bars_glsl(), {key: value}, SHAPE_PARAMS)
        elif target == "smooth":
            _write_smooth(_smooth_glsl(), {key: value})
        elif target == "rc":
            _write_int_req(RC_GLSL, key, int(value))
        self._schedule_restart()

    def _schedule_restart(self):
        if hasattr(self, "_rjob"):
            try: self.app.root.after_cancel(self._rjob)
            except Exception: pass
        from gui.glava import glava_restart
        self._rjob = self.app.root.after(
            300, lambda: glava_restart("bars", extra_flags=getattr(self.app, "extra_flags", "--desktop"), after_fn=self.app.update_status))


# ─── Tooltip helper ──────────────────────────────────────────────────────────

def _tip(parent, label, text):
    """Dodaje znak ? z tooltipem do wiersza."""
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

def _decimals(step):
    s = str(step)
    return len(s.rstrip("0").split(".")[-1]) if "." in s else 0


# ─── I/O: bars.glsl ──────────────────────────────────────────────────────────

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
    """
    Zapisuje #define do pliku .glsl.
    Usuwa wszystkie duplikaty danego klucza, zostawia jeden czysty wpis.
    Jeśli klucz nie istnieje w pliku — dopisuje na końcu.
    """
    if not os.path.exists(path): return
    keys = {p[0] for p in param_defs}
    with open(path) as f: content = f.read()
    for key, val in params.items():
        if key not in keys: continue
        pattern = rf'^#define\s+{key}\s+\S+[ \t]*$'
        matches = re.findall(pattern, content, re.MULTILINE)
        if matches:
            # Usuń wszystkie wystąpienia, wstaw jedno na miejscu pierwszego
            first_pos = re.search(pattern, content, re.MULTILINE).start()
            content = re.sub(pattern, '', content, flags=re.MULTILINE)
            # Wyczyść wielokrotne puste linie
            content = re.sub(r'\n{3,}', '\n\n', content)
            # Wstaw nową definicję na początku bloku konfiguracyjnego
            content = content[:first_pos] + f'#define {key} {val}\n' + content[first_pos:]
        else:
            content = content.rstrip() + f'\n#define {key} {val}\n'
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
    """Jak _write_defines ale dla FLAG_PARAMS — ta sama logika deduplikacji."""
    if not os.path.exists(path): return
    keys = {p[0] for p in FLAG_PARAMS}
    with open(path) as f: content = f.read()
    for key, val in params.items():
        if key not in keys: continue
        pattern = rf'^#define\s+{key}\s+\S+[ \t]*$'
        matches = re.findall(pattern, content, re.MULTILINE)
        if matches:
            first_pos = re.search(pattern, content, re.MULTILINE).start()
            content = re.sub(pattern, '', content, flags=re.MULTILINE)
            content = re.sub(r'\n{3,}', '\n\n', content)
            content = content[:first_pos] + f'#define {key} {val}\n' + content[first_pos:]
        else:
            content = content.rstrip() + f'\n#define {key} {val}\n'
    with open(path, "w") as f: f.write(content)


# ─── I/O: smooth_parameters.glsl ─────────────────────────────────────────────

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
        content = re.sub(rf'^(#request\s+{key}\s+)\S+', rf'\g<1>{sv}',
                         content, flags=re.MULTILINE)
    with open(path, "w") as f: f.write(content)


# ─── I/O: rc.glsl ────────────────────────────────────────────────────────────

def _read_int_req(path, key, default):
    if not os.path.exists(path): return {key: default}
    with open(path) as f: content = f.read()
    m = re.search(rf'^#request\s+{key}\s+(\S+)', content, re.MULTILINE)
    try: return {key: int(m.group(1))} if m else {key: default}
    except ValueError: return {key: default}

def _write_int_req(path, key, val):
    if not os.path.exists(path): return
    with open(path) as f: content = f.read()
    content = re.sub(rf'^(#request\s+{key}\s+)\S+', rf'\g<1>{val}',
                     content, flags=re.MULTILINE)
    with open(path, "w") as f: f.write(content)

def _read_bool_req(path, key):
    if not os.path.exists(path): return {key: False}
    with open(path) as f: content = f.read()
    m = re.search(rf'^#request\s+{key}\s+(\S+)', content, re.MULTILINE)
    return {key: (m.group(1) == "true")} if m else {key: False}

def _write_bool_req(path, key, val):
    if not os.path.exists(path): return
    with open(path) as f: content = f.read()
    sv = "true" if val else "false"
    content = re.sub(rf'^(#request\s+{key}\s+)\S+', rf'\g<1>{sv}',
                     content, flags=re.MULTILINE)
    with open(path, "w") as f: f.write(content)
