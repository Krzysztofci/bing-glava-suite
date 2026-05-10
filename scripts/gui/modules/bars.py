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

import os
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from ..core import CONFIG_DIR, GLAVA_DIR, RC_GLSL, SMOOTH_PARAMS
from ..widgets import AccelSlider
from ..theme import (BTN_APPLY, BTN_SAVE, BTN_DELETE, BTN_RESET,
                     COLORS, TFrame, TLabelFrame, TLabel, TCheckbutton, TEntry)
from . import glsl_io
from ..core import get_shader_profiles_for_module
from .base import BaseParamWidget

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

ALL_DEFINE_KEYS = {p[0] for p in SHAPE_PARAMS} | {p[0] for p in FLAG_PARAMS}
ALL_SMOOTH_KEYS = {p[0] for p in SMOOTH_PARAMS}


# ─── API dla tab_module.py ────────────────────────────────────────────────────

def build_params(parent, app, T):
    BarsParamWidget(parent, app, T).build()


def collect_params(app):
    p = {}
    p.update(glsl_io.read_defines(_bars_glsl(), SHAPE_PARAMS))
    p.update(glsl_io.read_flag_defines(_bars_glsl(), FLAG_PARAMS))
    p.update(glsl_io.read_smooth(_smooth_glsl(), SMOOTH_PARAMS))
    # Usunięto odczyt bufsize, samplesize, setmirror i setinterpolate
    return p

def apply_params(params, app):
    glsl_io.write_defines(_bars_glsl(), params, SHAPE_PARAMS)
    glsl_io.write_flag_defines(_bars_glsl(), params, FLAG_PARAMS)
    glsl_io.write_smooth(_smooth_glsl(), params, SMOOTH_PARAMS)
    # Usunięto zapisywanie parametrów do RC_GLSL

def reset_shader(app):
    import shutil
    tmpl, live = _bars_tmpl(), _bars_1frag()
    if os.path.exists(tmpl):
        os.makedirs(os.path.dirname(live), exist_ok=True)
        shutil.copy2(tmpl, live)
    defaults = {p[0]: p[4] for p in SHAPE_PARAMS}
    defaults.update({p[0]: 0 for p in FLAG_PARAMS})
    glsl_io.write_defines(_bars_glsl(), defaults, SHAPE_PARAMS)
    glsl_io.write_flag_defines(_bars_glsl(), defaults, FLAG_PARAMS)


# ─── Widget GUI ───────────────────────────────────────────────────────────────

class BarsParamWidget(BaseParamWidget):
    MODULE_NAME  = "bars"
    SHAPE_PARAMS = SHAPE_PARAMS

    def _init_extra(self):
        self._buf_cb    = None
        self._sample_cb = None

    def build_left(self, parent, current):
        self._build_shape(parent, current)
        self._build_flags(parent, current)

    def build_right(self, parent, current):
        self._build_smooth(parent, current)
        self._build_profiles(parent)
    def _build_shape(self, parent, current):
        title = self.T.get("section_shape", "Kształt")
        lf = self._detachable_lf(parent, title, self._build_shape, current)

        mapping = {
            "BAR_WIDTH": "label_bar_width",
            "BAR_GAP": "label_bar_gap",
            "BAR_OUTLINE_WIDTH": "label_border",
            "C_LINE": "label_center_line",
            "AMPLIFY": "label_gain"
        }

        for idx, p in enumerate(SHAPE_PARAMS):
            p_list = list(p)
            json_key = mapping.get(p[0])
            if json_key:
                p_list[1] = self.T.get(json_key, p[1])
                tk_key = json_key.replace("label_", "tooltip_")
                p_list[6] = self.T.get(tk_key, p[6])
            self._slider_row(lf, tuple(p_list), current, "module", idx)

    # ── Przełączniki ─────────────────────────────────────────────────────────

    def _build_flags(self, parent, current):
        title = self.T.get("section_switches", "Przełączniki")
        lf = self._detachable_lf(parent, title, self._build_flags, current)
        lf.columnconfigure(2, weight=1)

        mapping_flags = {
            "DIRECTION":    "label_invert_spectrum",
            "FLIP":         "label_flip_v",
            "MIRROR_YX":    "label_vertical_bar",
            "INVERT":       "label_swap_lr",
            "DISABLE_MONO": "label_disable_mono"
        }

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
                t = glsl_io.tip(lf, "?", translated_tip)
                if t:
                    # padx=(0, 5) przyciąga go do tekstu po lewej
                    t.grid(row=idx, column=1, sticky="w", padx=(0, 5), pady=2)

    # ── Wygładzanie ───────────────────────────────────────────────────────────

    def _build_smooth(self, parent, current):
        title = self.T.get("section_smoothing", "Wygładzanie")
        lf = self._detachable_lf(parent, title, self._build_smooth, current)

        mapping = {
            "setgravitystep": "label_gravity",
            "setsmoothfactor": "label_smooth_factor",
            "setavgframes": "label_avg_frames",
            "setfftscale": "label_fft_scale",
            "setfftcutoff": "label_bass_cutoff"
        }

        for idx, p in enumerate(SMOOTH_PARAMS):
            p_list = list(p)
            json_key = mapping.get(p[0])
            
            if json_key:
                p_list[1] = self.T.get(json_key, p[1])
                # Używamy indeksu 7, bo SMOOTH_PARAMS ma 8 elementów (przez dodany 'step')
                p_list[7] = self.T.get(json_key.replace("label_", "tooltip_"), p[7])
            
            # Ważne: zmienione na _float_slider_row, żeby obsłużyć 8 parametrów
            self._float_slider_row(lf, tuple(p_list), current, idx)

    # ── Profile szadera (prawa kolumna, pod wygładzaniem) ────────────────────

    def _build_profiles(self, parent):
        lf = ttk.LabelFrame(parent, text=self.T.get("section_profiles_bars", "Shader profiles bars"), padding=(15, 10))
        lf.pack(fill="x", padx=10, pady=10) # pady=10 zapewni odstępy między sekcjami jak w example.py

        profiles = get_shader_profiles_for_module("bars")
        names    = sorted(profiles.keys())
        self.profile_var = tk.StringVar()
        self.profile_cb  = ttk.Combobox(lf, textvariable=self.profile_var,
                                        values=names, state="readonly")
        self.profile_cb.pack(fill="x", pady=(0, 3))
        if names: self.profile_cb.current(0)

        ttk.Label(
            lf,
            text=self.T.get("label_profiles_hint_bars", "Shape & dynamics (colors unchanged)"),
            #font=("Arial", 7),
            #foreground=COLORS["text3"]
        ).pack(anchor="w")

        btn_row = ttk.Frame(lf)
        btn_row.pack(fill="x", pady=(4, 0))
        ttk.Button(
            btn_row, 
            text=self.T.get("btn_apply", "Apply"),
            command=self._apply_profile,
            style="Accent.TButton"  # Styl z Twojego przykładu
        ).pack(side="left", expand=True, fill="x", padx=(0, 2))
        ttk.Button(
            btn_row,
            text=self.T.get("btn_save_new", "Save new"),
            command=self._save_profile,
            #style="Accent.TButton"  # Styl z Twojego przykładu
        ).pack(side="left", expand=True, fill="x", padx=(0, 2))
        ttk.Button(
            btn_row,
            text=self.T.get("btn_delete", "Delete"),
            command=self._delete_profile,
            # Styl z Twojego przykładu            
        ).pack(side="left")
        ttk.Button(lf, text=self.T.get("btn_reset_shader_bars", "Reset bars shader"),
            command=self._reset_shader,
            style="Accent.TButton"
        ).pack(fill="x", pady=(4, 0))

    def _combo_row(self, parent, label, key, values, cur, tooltip):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=label, width=13, anchor="w").pack(side="left")
        var = self.vars[key]
        cb = ttk.Combobox(row, textvariable=var,
                          values=[str(v) for v in values],
                          width=6, state="readonly")
        cb.pack(side="left")
        glsl_io.tip(row, "?", tooltip)

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

    def _slider_row(self, parent, param_def, current, target, row_idx):
        key, label, vmin, vmax, default, unit, tooltip = param_def
        cur = int(current.get(key, default))
        var = tk.IntVar(value=cur)
        self.vars[key] = var

        # Konfigurujemy kolumnę z suwakiem, aby była elastyczna
        parent.columnconfigure(index=2, weight=1)

        # 1. Etykieta (Kolumna 0)
        ttk.Label(parent, text=label, width=12, anchor="w").grid(
            row=row_idx, column=0, padx=(10, 5), pady=5, sticky="w"
        )       
        
        if tooltip:
            t = glsl_io.tip(parent, "?", tooltip)
            if t: 
                t.grid(row=row_idx, column=1, padx=5, pady=5)

        def on_change(v, k=key, tgt=target):
            iv = int(round(v))
            var.set(iv)
            self._debounce(k, iv, tgt)

        # 3. Suwak (Kolumna 2)
        slider = AccelSlider(parent, vmin=vmin, vmax=vmax, value=cur,
                             step=1, on_change=on_change)
        slider.grid(row=row_idx, column=2, padx=10, pady=5, sticky="ew")

        # 4. Jednostka (Kolumna 3) - TERAZ JEST W DOBREJ LINII
        ttk.Label(parent, text=unit if unit else " ", width=4).grid(
            row=row_idx, column=3, padx=(5, 10), pady=5, sticky="e"
        )

    # ── Wiersz suwaka float ───────────────────────────────────────────────────

    def _float_slider_row(self, parent, param_def, current, row_idx):
        # Rozpakowanie 8 elementów (bezpieczne, bo to pętla dedykowana dla Smooth)
        key, label, vmin, vmax, default, unit, step, tooltip = param_def
    
        try:
            cur = float(current.get(key, default))
        except (ValueError, TypeError):
            cur = float(default)
        
        var = tk.DoubleVar(value=cur)
        self.vars[key] = var
        dec = glsl_io.decimals(step)

        parent.columnconfigure(2, weight=1)

    # Etykieta - zwiększamy szerokość do 18, żeby pasowała do flag!
        ttk.Label(parent, text=label, width=18, anchor="w").grid(
            row=row_idx, column=0, padx=(10, 5), pady=5, sticky="w"
        )

        if tooltip:
            t = glsl_io.tip(parent, "?", tooltip)
            if t: t.grid(row=row_idx, column=1, padx=5, pady=5)

        # POPRAWKA: Funkcja on_change z bezpiecznikiem
        def on_change(v, k=key, mi=vmin, ma=vmax):
            # Bezpiecznik: nie pozwól wartości wyjść poza min/max
            val = max(mi, min(ma, float(v)))
            var.set(val)
            self._debounce(k, val, "smooth")

        # Tworzenie suwaka
        slider = AccelSlider(parent, vmin=vmin, vmax=vmax, value=cur,
                             step=step, is_float=True, decimals=dec,
                         on_change=on_change)
        slider.grid(row=row_idx, column=2, padx=10, pady=5, sticky="ew")

        # Pusta etykieta dla wyrównania do jednostek z sekcji Shape
        ttk.Label(parent, text=" ", width=4).grid(row=row_idx, column=3)

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
        glsl_io.write_flag_defines(_bars_glsl(), {key: val}, FLAG_PARAMS)
        if key in ("FLIP", "MIRROR_YX"):
            self._update_geometry()
        self._schedule_restart()

    def _update_geometry(self):
        """Koryguje geometrię rc.glsl na podstawie aktualnych flag FLIP i MIRROR_YX."""
        try:
            from ..geometry import get_screen_info, calc_geometry, write_geometry
            from ..core import RC_GLSL
            # Odczytaj aktualne wartości flag z pliku
            current = glsl_io.read_flag_defines(_bars_glsl(), FLAG_PARAMS)
            flipped   = bool(current.get("FLIP", 0))
            mirror_yx = bool(current.get("MIRROR_YX", 0))
            si = get_screen_info()
            # si: (screen_w, screen_h, work_h, top, bottom, left, right)
            x, y, w, h = calc_geometry(
                "bars", si[0], si[1], si[4], si[3],
                flipped=flipped, mirror_yx=mirror_yx,
                left_reserved=si[5], right_reserved=si[6]
            )
            write_geometry(RC_GLSL, x, y, w, h)
        except Exception:
            pass

    def _write_bool_rc(self, key, var):
        glsl_io.write_bool_req(RC_GLSL, key, var.get())
        self._schedule_restart()

