#!/usr/bin/env python3
# =============================================================================
# glava-gui.py
# Panel sterowania GLava + Bing wallpaper suite.
# =============================================================================

import tkinter as tk
from tkinter import colorchooser, messagebox, simpledialog, ttk
import os
import subprocess
import re

# ─────────────────────────────────────────────────────────────────────────────
# Bloki gradientu (RGB / HSV) — podmieniane w szablonie shadera
# ─────────────────────────────────────────────────────────────────────────────

GRADIENT_BLOCK_RGB = """// ── gradient 3-kolorowy ──────────────────────────────────────────────────────
// GRADIENT_MODE: rgb
vec3 bottom = vec3(0.5, 0.0, 0.0);
vec3 mid    = vec3(0.9, 0.1, 0.1);
vec3 top    = vec3(0.8, 0.8, 0.8);

vec4 gradient_color(float t) {
    // RGB: proste mieszanie kolorów
    vec3 col = t < 0.5
        ? mix(bottom, mid, t * 2.0)
        : mix(mid, top, (t - 0.5) * 2.0);
    return vec4(col, 1.0);
}
// ─────────────────────────────────────────────────────────────────────────────"""

GRADIENT_BLOCK_HSV = """// ── gradient 3-kolorowy ──────────────────────────────────────────────────────
// GRADIENT_MODE: hsv
vec3 bottom = vec3(0.5, 0.0, 0.0);
vec3 mid    = vec3(0.9, 0.1, 0.1);
vec3 top    = vec3(0.8, 0.8, 0.8);

vec3 rgb2hsv(vec3 c) {
    vec4 K = vec4(0.0, -1.0/3.0, 2.0/3.0, -1.0);
    vec4 p = mix(vec4(c.bg, K.wz), vec4(c.gb, K.xy), step(c.b, c.g));
    vec4 q = mix(vec4(p.xyw, c.r), vec4(c.r, p.yzx), step(p.x, c.r));
    float d = q.x - min(q.w, q.y);
    float e = 1.0e-10;
    return vec3(abs(q.z + (q.w - q.y) / (6.0 * d + e)), d / (q.x + e), q.x);
}
vec3 hsv2rgb(vec3 c) {
    vec4 K = vec4(1.0, 2.0/3.0, 1.0/3.0, 3.0);
    vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
    return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
}
vec4 gradient_color(float t) {
    // HSV: interpolacja przez przestrzeń HSV — czyste przejścia kolorów
    vec3 hsv_a = rgb2hsv(t < 0.5 ? bottom : mid);
    vec3 hsv_b = rgb2hsv(t < 0.5 ? mid    : top);
    float lt   = t < 0.5 ? t * 2.0 : (t - 0.5) * 2.0;
    float dh = hsv_b.x - hsv_a.x;
    if (dh > 0.5)  dh -= 1.0;
    if (dh < -0.5) dh += 1.0;
    vec3 hsv = vec3(hsv_a.x + dh * lt, mix(hsv_a.y, hsv_b.y, lt), mix(hsv_a.z, hsv_b.z, lt));
    return vec4(hsv2rgb(hsv), 1.0);
}
// ─────────────────────────────────────────────────────────────────────────────"""

GRADIENT_PATTERN = re.compile(
    r'// ── gradient 3-kolorowy.*?// ─{20,}',
    re.DOTALL
)
import json
import glob
import datetime

USER_HOME     = os.path.expanduser("~")
CONFIG_DIR    = os.path.join(USER_HOME, ".config/glava")
BIN_DIR       = os.path.join(USER_HOME, ".local/bin")
BINGCONF_DIR  = os.path.join(USER_HOME, ".config/bing-glava")
BINGCONF_FILE = os.path.join(BINGCONF_DIR, "config")
RC_GLSL       = os.path.join(CONFIG_DIR, "rc.glsl")
FLAG_RED      = os.path.join(CONFIG_DIR, "red.shift")
FLAG_MANUAL   = os.path.join(CONFIG_DIR, "manual.shift")
PRESETS_FILE  = os.path.join(CONFIG_DIR, "presets.json")
WALLPAPER     = os.path.join(USER_HOME, "Pictures/Bing/bing_today.jpg")
SETTINGS_FILE = os.path.join(CONFIG_DIR, "gui_settings.json")
ACTIVE_MODULE_FILE = os.path.join(CONFIG_DIR, "active_module")

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
LANG_DIR   = os.path.join(SCRIPT_DIR, "..", "lang")
if not os.path.isdir(LANG_DIR):
    LANG_DIR = os.path.join(SCRIPT_DIR, "lang")
if not os.path.isdir(LANG_DIR):
    LANG_DIR = os.path.join(USER_HOME, ".local/share/bing-glava-suite/lang")

BING_REGIONS = [
    "de-DE", "en-US", "en-GB", "fr-FR", "es-ES",
    "it-IT", "pt-BR", "ja-JP", "zh-CN", "pl-PL",
]

# Dostępne moduły GLava z opisami (klucze do tłumaczeń)
GLAVA_MODULES = ["graph", "bars", "circle", "wave", "radial"]

# Szablony dla każdego modułu
MODULE_TEMPLATES = {
    "graph":  "graph_red.frag",
    "bars":   "bars_colors.frag",
    "circle": "circle_colors.frag",
    "wave":   "wave_colors.frag",
    "radial": "radial_colors.frag",
}

MODULE_LIVEFRAGS = {
    "graph":  "graph/1.frag",
    "bars":   "bars/1.frag",
    "circle": "circle/1.frag",
    "wave":   "wave/1.frag",
    "radial": "radial/1.frag",
}


# ─────────────────────────────────────────────────────────────────────────────

def read_active_module():
    if os.path.exists(ACTIVE_MODULE_FILE):
        with open(ACTIVE_MODULE_FILE) as f:
            m = f.read().strip()
        if m in GLAVA_MODULES:
            return m
    return "graph"


def write_active_module(module):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(ACTIVE_MODULE_FILE, "w") as f:
        f.write(module)


def get_live_frag(module=None):
    if module is None:
        module = read_active_module()
    return os.path.join(CONFIG_DIR, MODULE_LIVEFRAGS.get(module, "graph/1.frag"))


def get_template(module=None):
    if module is None:
        module = read_active_module()
    return os.path.join(CONFIG_DIR, MODULE_TEMPLATES.get(module, "graph_red.frag"))


# ─────────────────────────────────────────────────────────────────────────────

def read_bing_config():
    cfg = {"BING_REGION": "de-DE"}
    if os.path.exists(BINGCONF_FILE):
        with open(BINGCONF_FILE) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    cfg[key.strip()] = val.strip()
    return cfg


def write_bing_config(cfg):
    os.makedirs(BINGCONF_DIR, exist_ok=True)
    lines = ["# bing-glava — konfiguracja użytkownika\n"]
    for key, val in cfg.items():
        lines.append(f"{key}={val}\n")
    with open(BINGCONF_FILE, "w") as f:
        f.writelines(lines)


# ─────────────────────────────────────────────────────────────────────────────

def load_lang(lang_code):
    path = os.path.join(LANG_DIR, f"{lang_code}.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    fallback = os.path.join(LANG_DIR, "en.json")
    if os.path.exists(fallback):
        with open(fallback) as f:
            return json.load(f)
    return {}


def available_langs():
    langs = {}
    for f in sorted(glob.glob(os.path.join(LANG_DIR, "*.json"))):
        code = os.path.splitext(os.path.basename(f))[0]
        try:
            with open(f) as fp:
                data = json.load(fp)
            langs[code] = data.get("lang_name", code)
        except Exception:
            langs[code] = code
    return langs if langs else {"pl": "Polski", "en": "English"}


# ─────────────────────────────────────────────────────────────────────────────

def load_settings():
    defaults = {"lang": "pl", "gradient_mode": "rgb"}
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE) as f:
                data = json.load(f)
            defaults.update(data)
        except Exception:
            pass
    return defaults


def save_settings(settings):
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=4)


# ─────────────────────────────────────────────────────────────────────────────

def read_geometry():
    if not os.path.exists(RC_GLSL):
        screen_w, screen_h, work_h = get_screen_info()
        panel_h = screen_h - work_h
        return calc_geometry("graph", screen_w, screen_h, panel_h)
    with open(RC_GLSL) as f:
        content = f.read()
    m = re.search(r'#request\s+setgeometry\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)', content)
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
    # Fallback jeśli wpis nie istnieje w rc.glsl
    screen_w, screen_h, work_h = get_screen_info()
    panel_h = screen_h - work_h
    return calc_geometry("graph", screen_w, screen_h, panel_h)


def write_geometry(x, y, w, h):
    if not os.path.exists(RC_GLSL):
        return False
    with open(RC_GLSL) as f:
        content = f.read()
    new = re.sub(
        r'(#request\s+setgeometry\s+)-?\d+\s+-?\d+\s+-?\d+\s+-?\d+',
        f'\\g<1>{x} {y} {w} {h}',
        content
    )
    with open(RC_GLSL, "w") as f:
        f.write(new)
    return True


# ─────────────────────────────────────────────────────────────────────────────

def sudo_run_zenity(cmd):
    import shutil
    if shutil.which("zenity"):
        passwd = subprocess.run(
            ["zenity", "--password", "--title=Autoryzacja"],
            capture_output=True, text=True
        ).stdout.strip()
        if not passwd:
            return False
        result = subprocess.run(
            ["sudo", "-S"] + cmd,
            input=passwd + "\n",
            capture_output=True, text=True
        )
        return result.returncode == 0
    else:
        result = subprocess.run(["sudo"] + cmd)
        return result.returncode == 0


# ─────────────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────────────
# Wykrywanie geometrii ekranu i paska zadań
# ─────────────────────────────────────────────────────────────────────────────

# Moduły centrowane względem okna (środek ekranu)
MODULES_CENTERED = {"circle", "radial", "wave"}
# Moduły rysowane od dołu okna (podstawa na pasku/krawędzi)
MODULES_BOTTOM   = {"graph", "graph2", "bars"}

def get_screen_info():
    """
    Zwraca (screen_w, screen_h, work_h) używając _NET_WORKAREA i _NET_DESKTOP_GEOMETRY.
    Fallback: xrandr.
    """
    try:
        # _NET_WORKAREA: x, y, w, h (powtórzone dla każdego wirtualnego pulpitu)
        r = subprocess.run(["xprop", "-root", "_NET_WORKAREA"],
                           capture_output=True, text=True)
        wa = re.findall(r'\d+', r.stdout)
        # _NET_DESKTOP_GEOMETRY: w, h
        r2 = subprocess.run(["xprop", "-root", "_NET_DESKTOP_GEOMETRY"],
                            capture_output=True, text=True)
        dg = re.findall(r'\d+', r2.stdout)
        if len(wa) >= 4 and len(dg) >= 2:
            screen_w = int(dg[0])
            screen_h = int(dg[1])
            work_h   = int(wa[3])   # wysokość obszaru roboczego (bez paska)
            return screen_w, screen_h, work_h
    except Exception:
        pass
    # Fallback: xrandr
    try:
        r = subprocess.run(["xrandr", "--current"], capture_output=True, text=True)
        m = re.search(r'current (\d+) x (\d+)', r.stdout)
        if m:
            w, h = int(m.group(1)), int(m.group(2))
            return w, h, h   # brak info o pasku → work_h = screen_h
    except Exception:
        pass
    return 1600, 900, 860   # ostateczny fallback


def calc_geometry(module, screen_w, screen_h, panel_h):
    """
    Oblicza (x, y, w, h) dla danego modułu na podstawie rozdzielczości i paska.

    graph / graph2 / bars:
        Podstawa wizualizacji leży na górnej krawędzi paska zadań.
        Y ujemne przesuwa dół okna nad pasek.
        H = screen_h zapewnia że wizualizacja ma pełną wysokość do dyspozycji.

    circle / radial / wave:
        Centrowane w pełnym ekranie.
        X=0, Y=0, W=screen_w, H=screen_h.
    """
    if module in MODULES_BOTTOM:
        x = 0
        y = -panel_h      # przesuń okno w górę o wysokość paska
        w = screen_w
        h = screen_h
    else:
        # MODULES_CENTERED
        x = 0
        y = 0
        w = screen_w
        h = screen_h
    return x, y, w, h

class GlavaControlCenter:
    def __init__(self, root):
        self.root = root
        self.settings = load_settings()
        self.T = load_lang(self.settings.get("lang", "pl"))
        self.langs = available_langs()
        self.bing_cfg = read_bing_config()
        self.current_colors = {"top": "#ffffff", "mid": "#888888", "bottom": "#000000"}
        self.presets = {}
        self.active_module = read_active_module()
        self.gradient_mode = self.settings.get("gradient_mode", "rgb")
        self.load_presets()
        self.root.title(self.T.get("title", "GLava Master Panel"))
        self.root.resizable(True, True)
        self.build_ui()
        self.update_status()

    def build_ui(self):
        for w in self.root.winfo_children():
            w.destroy()
        T = self.T

        # --- Pasek górny ---
        top_bar = tk.Frame(self.root)
        top_bar.pack(fill="x", padx=10, pady=(8, 2))
        tk.Label(top_bar, text=T.get("title", "GLava Master Panel"),
                 font=("Arial", 11, "bold")).pack(side="left")
        lang_frame = tk.Frame(top_bar)
        lang_frame.pack(side="right")
        tk.Label(lang_frame, text=T.get("section_language", "Język") + ":",
                 font=("Arial", 9)).pack(side="left", padx=(0, 4))
        self.lang_var = tk.StringVar(value=self.settings.get("lang", "pl"))
        lang_cb = ttk.Combobox(lang_frame, textvariable=self.lang_var,
                                values=list(self.langs.keys()), width=5, state="readonly")
        lang_cb.pack(side="left")
        lang_cb.bind("<<ComboboxSelected>>", self.change_language)

        # --- WIERSZ 0: Wybór motywu ---
        mf = tk.LabelFrame(self.root,
                            text=T.get("section_module", "Motyw GLava"),
                            font=("Arial", 9, "bold"), padx=8, pady=6)
        mf.pack(fill="x", padx=10, pady=(4, 2))
        module_row = tk.Frame(mf)
        module_row.pack(fill="x")
        tk.Label(module_row, text=T.get("label_module", "Aktywny motyw") + ":",
                 font=("Arial", 9)).pack(side="left")
        self.module_var = tk.StringVar(value=self.active_module)
        module_cb = ttk.Combobox(module_row, textvariable=self.module_var,
                                  values=GLAVA_MODULES, width=10, state="readonly")
        module_cb.pack(side="left", padx=(6, 12))
        module_cb.bind("<<ComboboxSelected>>", self.change_module)
        tk.Button(module_row, text=T.get("btn_apply_module", "Zastosuj motyw"),
                  command=self.apply_module, bg="#1565c0", fg="white",
                  font=("Arial", 9)).pack(side="left")

        # --- WIERSZ 1: Kolorystyka + Tryby ---
        row1 = tk.Frame(self.root)
        row1.pack(fill="x", padx=10, pady=4)

        # Kolorystyka
        cf = tk.LabelFrame(row1, text=T.get("section_colors", "Kolorystyka"),
                            font=("Arial", 9, "bold"), padx=6, pady=6)
        cf.pack(side="left", fill="both", expand=True, padx=(0, 4))
        btn_row = tk.Frame(cf)
        btn_row.pack(fill="x", pady=(0, 6))
        for key in ["top", "mid", "bottom"]:
            lbl = T.get(f"btn_{key}", key)
            btn = tk.Button(btn_row, text=lbl, command=lambda k=key: self.pick_color(k),
                            bg=self.current_colors[key], width=8, height=2)
            btn.pack(side="left", padx=2)
            setattr(self, f"btn_{key}", btn)
        tk.Button(cf, text=T.get("btn_apply_manual", "Zastosuj (ręczny)"),
                  command=self.apply_manual, bg="#2e7d32", fg="white",
                  font=("Arial", 9, "bold")).pack(fill="x", pady=(0, 3))
        tk.Button(cf, text=T.get("btn_capture", "Pobierz z ekranu"),
                  command=self.capture_current, bg="#f39c12", fg="white").pack(fill="x")
        # Radio: RGB / HSV
        grad_row = tk.Frame(cf)
        grad_row.pack(fill="x", pady=(6, 0))
        tk.Label(grad_row, text=T.get("label_gradient", "Gradient:"),
                 font=("Arial", 9)).pack(side="left")
        self.gradient_var = tk.StringVar(value=self.gradient_mode)
        for val, lbl in [("rgb", "RGB"), ("hsv", "HSV")]:
            tk.Radiobutton(grad_row, text=lbl, variable=self.gradient_var,
                           value=val, command=self.change_gradient_mode,
                           font=("Arial", 9)).pack(side="left", padx=(4, 0))

        # Tryby
        tf = tk.LabelFrame(row1, text=T.get("section_modes", "Tryby"),
                            font=("Arial", 9, "bold"), padx=6, pady=6)
        tf.pack(side="left", fill="both", expand=True, padx=(4, 0))
        tk.Button(tf, text=T.get("btn_fetch_wallpaper", "Pobierz tapetę Bing (pulpit)"),
                  command=self.fetch_wallpaper_user, bg="#1565c0", fg="white"
                  ).pack(fill="x", pady=(0, 3))
        tk.Button(tf, text=T.get("btn_fetch_wallpaper_full", "Pobierz tapetę Bing (pulpit + logowanie)"),
                  command=self.fetch_wallpaper_full, bg="#0d47a1", fg="white"
                  ).pack(fill="x", pady=(0, 6))
        tk.Button(tf, text=T.get("btn_restore_auto", "Przywróć Bing (auto)"),
                  command=self.restore_auto, bg="#37474f", fg="white").pack(fill="x", pady=(0, 3))
        tk.Button(tf, text=T.get("btn_toggle_glava", "Włącz / Wyłącz GLava"),
                  command=self.run_toggle, bg="#424242", fg="white").pack(fill="x")

        # --- WIERSZ 2: Profile + Geometria ---
        row2 = tk.Frame(self.root)
        row2.pack(fill="x", padx=10, pady=4)

        # Profile
        pf = tk.LabelFrame(row2, text=T.get("section_profiles", "Profile kolorów"),
                            font=("Arial", 9, "bold"), padx=6, pady=6)
        pf.pack(side="left", fill="both", expand=True, padx=(0, 4))
        self.listbox = tk.Listbox(pf, height=5, font=("Arial", 9))
        self.listbox.pack(fill="x", pady=(0, 6))
        self.refresh_listbox()
        bp = tk.Frame(pf)
        bp.pack(fill="x")
        tk.Button(bp, text=T.get("btn_load", "Wczytaj"),
                  command=self.load_selected_preset, bg="#546e7a", fg="white",
                  width=9).pack(side="left", padx=(0, 3), expand=True)
        tk.Button(bp, text=T.get("btn_save_new", "Zapisz nowy"),
                  command=self.save_new_preset, bg="#546e7a", fg="white",
                  width=9).pack(side="left", padx=(0, 3), expand=True)
        tk.Button(bp, text=T.get("btn_delete", "Usuń"),
                  command=self.delete_preset, bg="#b71c1c", fg="white",
                  width=6).pack(side="left")

        # Geometria
        gf = tk.LabelFrame(row2, text=T.get("section_geometry", "Geometria GLava"),
                            font=("Arial", 9, "bold"), padx=6, pady=6)
        gf.pack(side="left", fill="both", expand=True, padx=(4, 0))
        gx, gy, gw, gh = read_geometry()
        self.geo_vars = {}
        geo_grid = tk.Frame(gf)
        geo_grid.pack(fill="x", pady=(0, 6))
        for i, (key, val, lbl) in enumerate([
            ("x", gx, T.get("label_x", "X")),
            ("y", gy, T.get("label_y", "Y")),
            ("w", gw, T.get("label_w", "Szer.")),
            ("h", gh, T.get("label_h", "Wys.")),
        ]):
            tk.Label(geo_grid, text=lbl, font=("Arial", 9), width=4
                     ).grid(row=i//2, column=(i%2)*2, sticky="e", padx=(0, 2), pady=2)
            var = tk.StringVar(value=str(val))
            self.geo_vars[key] = var
            tk.Entry(geo_grid, textvariable=var, width=7, font=("Arial", 9)
                     ).grid(row=i//2, column=(i%2)*2+1, padx=(0, 8), pady=2)
        tk.Button(gf, text=T.get("btn_auto_geometry", "Auto-konfiguracja geometrii"),
                  command=self.detect_geometry_auto, bg="#37474f", fg="white",
                  font=("Arial", 9)).pack(fill="x", pady=(0, 4))
        tk.Button(gf, text=T.get("btn_apply_geometry", "Zastosuj geometrię"),
                  command=self.apply_geometry, bg="#1565c0", fg="white",
                  font=("Arial", 9)).pack(fill="x")

        # --- WIERSZ 3: Ustawienia ---
        sf = tk.LabelFrame(self.root, text=T.get("section_settings", "Ustawienia"),
                           font=("Arial", 9, "bold"), padx=8, pady=6)
        sf.pack(fill="x", padx=10, pady=4)
        s_row = tk.Frame(sf)
        s_row.pack(fill="x")
        tk.Label(s_row, text=T.get("label_region", "Region Bing") + ":",
                 font=("Arial", 9)).pack(side="left")
        self.region_var = tk.StringVar(value=self.bing_cfg.get("BING_REGION", "de-DE"))
        ttk.Combobox(s_row, textvariable=self.region_var, values=BING_REGIONS,
                     width=8, state="readonly").pack(side="left", padx=(4, 16))
        tk.Button(s_row, text=T.get("btn_save_settings", "Zapisz"),
                  command=self.save_settings_action, font=("Arial", 9)).pack(side="left")

        # --- STATUS ---
        self.status_label = tk.Label(self.root, text="...",
                                      font=("Arial", 9, "italic"), anchor="w")
        self.status_label.pack(fill="x", padx=12, pady=(2, 8))

    # ─────────────────────────────────────────────────────────────────────────
    # Moduł / motyw
    # ─────────────────────────────────────────────────────────────────────────

    def change_module(self, event=None):
        """Aktualizuje podgląd wybranego modułu bez restartu."""
        self.active_module = self.module_var.get()

    def apply_module(self):
        """Zapisuje wybrany moduł i restartuje GLava."""
        module = self.module_var.get()
        self.active_module = module
        write_active_module(module)
        # Sprawdź czy szablon istnieje
        tmpl = get_template(module)
        if not os.path.exists(tmpl):
            messagebox.showerror("",
                f"{self.T.get('error_no_template', 'Brak szablonu')}:\n{tmpl}\n\n"
                f"Skopiuj plik {MODULE_TEMPLATES[module]} do {CONFIG_DIR}/")
            return
        # Jeśli tryb auto — wygeneruj kolory dla nowego modułu
        if not os.path.exists(FLAG_RED) and not os.path.exists(FLAG_MANUAL):
            subprocess.Popen(["/bin/bash", os.path.join(BIN_DIR, "glava-colors-auto")])
            self.root.after(1500, self.update_status)
        else:
            self.restart_glava()
            self.root.after(500, self.update_status)

    # ─────────────────────────────────────────────────────────────────────────
    # Gradient RGB / HSV
    # ─────────────────────────────────────────────────────────────────────────

    def change_gradient_mode(self):
        mode = self.gradient_var.get()
        self.gradient_mode = mode
        self.settings["gradient_mode"] = mode
        save_settings(self.settings)
        # Podmień blok gradientu w aktywnym szablonie i live frag
        block = GRADIENT_BLOCK_HSV if mode == "hsv" else GRADIENT_BLOCK_RGB
        for path in [get_template(self.active_module), get_live_frag(self.active_module)]:
            if os.path.exists(path):
                with open(path) as f:
                    src = f.read()
                new_src = GRADIENT_PATTERN.sub(block, src)
                with open(path, "w") as f:
                    f.write(new_src)
        self.restart_glava()

    # ─────────────────────────────────────────────────────────────────────────
    # Język
    # ─────────────────────────────────────────────────────────────────────────

    def change_language(self, event=None):
        lang = self.lang_var.get()
        self.settings["lang"] = lang
        save_settings(self.settings)
        self.T = load_lang(lang)
        self.root.title(self.T.get("title", "GLava Master Panel"))
        self.build_ui()

    # ─────────────────────────────────────────────────────────────────────────
    # Presety
    # ─────────────────────────────────────────────────────────────────────────

    def load_presets(self):
        if os.path.exists(PRESETS_FILE):
            try:
                with open(PRESETS_FILE) as f:
                    self.presets = json.load(f)
                if "LAST_SESSION" in self.presets:
                    self.current_colors = self.presets["LAST_SESSION"]
            except Exception:
                self.presets = {}

    def save_presets_to_file(self):
        self.presets["LAST_SESSION"] = self.current_colors
        with open(PRESETS_FILE, "w") as f:
            json.dump(self.presets, f, indent=4)

    def refresh_listbox(self):
        self.listbox.delete(0, tk.END)
        for name in sorted(self.presets.keys()):
            if name != "LAST_SESSION":
                self.listbox.insert(tk.END, name)

    def save_new_preset(self):
        name = simpledialog.askstring(
            self.T.get("dialog_profile_title", "Nowy profil"),
            self.T.get("dialog_profile_name", "Podaj nazwę:"))
        if name:
            self.presets[name] = self.current_colors.copy()
            self.save_presets_to_file()
            self.refresh_listbox()

    def load_selected_preset(self):
        sel = self.listbox.curselection()
        if sel:
            name = self.listbox.get(sel[0])
            self.current_colors = self.presets[name].copy()
            for key in ["top", "mid", "bottom"]:
                getattr(self, f"btn_{key}").config(bg=self.current_colors[key])
            self.apply_manual()

    def delete_preset(self):
        sel = self.listbox.curselection()
        if sel:
            name = self.listbox.get(sel[0])
            if messagebox.askyesno("", f"{self.T.get('dialog_delete_confirm', 'Usuń')} '{name}'?"):
                del self.presets[name]
                self.save_presets_to_file()
                self.refresh_listbox()

    # ─────────────────────────────────────────────────────────────────────────
    # Kolory
    # ─────────────────────────────────────────────────────────────────────────

    def pick_color(self, key):
        color = colorchooser.askcolor(color=self.current_colors[key])[1]
        if color:
            self.current_colors[key] = color
            getattr(self, f"btn_{key}").config(bg=color)
            self.save_presets_to_file()

    def apply_manual(self):
        open(FLAG_RED, "a").close()
        open(FLAG_MANUAL, "a").close()
        tmpl = get_template(self.active_module)
        live = get_live_frag(self.active_module)
        if not os.path.exists(tmpl):
            messagebox.showerror("", f"{self.T.get('error_no_template', 'Brak szablonu')}:\n{tmpl}")
            return
        with open(tmpl) as f:
            lines = f.readlines()
        os.makedirs(os.path.dirname(live), exist_ok=True)
        with open(live, "w") as f:
            for line in lines:
                written = False
                for k in ["bottom", "mid", "top"]:
                    if f"vec3 {k}" in line:
                        rgb = tuple(int(self.current_colors[k].lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
                        vec = "vec3({:.2f}, {:.2f}, {:.2f})".format(rgb[0]/255, rgb[1]/255, rgb[2]/255)
                        f.write(f"vec3 {k} = {vec};\n")
                        written = True
                        break
                if not written:
                    f.write(line)
        # Zachowaj aktywny tryb gradientu
        block = GRADIENT_BLOCK_HSV if self.gradient_mode == "hsv" else GRADIENT_BLOCK_RGB
        with open(live, "r") as f:
            src = f.read()
        with open(live, "w") as f:
            f.write(GRADIENT_PATTERN.sub(block, src))
        self.save_presets_to_file()
        self.restart_glava()

    def capture_current(self):
        live = get_live_frag(self.active_module)
        if not os.path.exists(live):
            return
        with open(live) as f:
            content = f.read()
        for key in ["bottom", "mid", "top"]:
            m = re.search(rf"vec3\s+{key}\s*=\s*vec3\s*\((.*?)\)\s*;", content)
            if m:
                vals = [float(v.strip()) for v in m.group(1).split(",")]
                hex_c = "#%02x%02x%02x" % (int(vals[0]*255), int(vals[1]*255), int(vals[2]*255))
                self.current_colors[key] = hex_c
                getattr(self, f"btn_{key}").config(bg=hex_c)

    # ─────────────────────────────────────────────────────────────────────────
    # Tapeta
    # ─────────────────────────────────────────────────────────────────────────

    def fetch_wallpaper_user(self):
        self.root.focus()
        fetcher = os.path.join(BIN_DIR, "bing-fetch-user.sh")
        subprocess.Popen(["/bin/bash", fetcher, "--force"])
        self.root.after(4000, self.update_status)

    def fetch_wallpaper_full(self):
        self.root.focus()
        downloader = "/usr/local/bin/bing-downloader.sh"
        if not os.path.exists(downloader):
            downloader = os.path.join(BIN_DIR, "bing-downloader.sh")
        import getpass
        user = getpass.getuser()
        sudo_run_zenity([downloader, user, "--force"])
        self.root.after(4000, self.update_status)

    def restore_auto(self):
        for flag in (FLAG_RED, FLAG_MANUAL):
            if os.path.exists(flag):
                os.remove(flag)
        subprocess.Popen(["/bin/bash", os.path.join(BIN_DIR, "glava-colors-auto")])
        self.root.after(1000, self.update_status)

    def run_toggle(self):
        subprocess.run(["/bin/bash", os.path.join(BIN_DIR, "glava-toggle")])
        self.root.after(500, self.update_status)

    # ─────────────────────────────────────────────────────────────────────────
    # Geometria
    # ─────────────────────────────────────────────────────────────────────────

    def detect_resolution(self):
        try:
            result = subprocess.run(["xrandr", "--current"], capture_output=True, text=True)
            m = re.search(r'current (\d+) x (\d+)', result.stdout)
            if m:
                self.geo_vars["x"].set("0")
                self.geo_vars["w"].set(m.group(1))
        except Exception:
            pass

    def detect_geometry_auto(self):
        """Wykryj rozdzielczość i wysokość paska, ustaw optymalną geometrię dla aktywnego modułu."""
        screen_w, screen_h, work_h = get_screen_info()
        panel_h = screen_h - work_h
        module  = self.active_module
        x, y, w, h = calc_geometry(module, screen_w, screen_h, panel_h)
        self.geo_vars["x"].set(str(x))
        self.geo_vars["y"].set(str(y))
        self.geo_vars["w"].set(str(w))
        self.geo_vars["h"].set(str(h))
        info_msg = (
            f"{self.T.get('auto_geo_info', 'Wykryto')}: "
            f"{screen_w}\u00d7{screen_h}, "
            f"{self.T.get('auto_geo_panel', 'pasek zadań')}: {panel_h}px\n"
            f"X={x}  Y={y}  W={w}  H={h}"
        )
        messagebox.showinfo(
            self.T.get("auto_geo_title", "Auto-konfiguracja geometrii"),
            info_msg
        )

    def apply_geometry(self):
        try:
            x = int(self.geo_vars["x"].get())
            y = int(self.geo_vars["y"].get())
            w = int(self.geo_vars["w"].get())
            h = int(self.geo_vars["h"].get())
        except ValueError:
            messagebox.showerror("", "Wartości muszą być liczbami całkowitymi.")
            return
        if w <= 0 or h <= 0:
            messagebox.showerror("", "Szerokość i wysokość muszą być większe od zera.")
            return
        if write_geometry(x, y, w, h):
            messagebox.showinfo("", self.T.get("geometry_applied", "Geometria zaktualizowana."))
            self.restart_glava()

    # ─────────────────────────────────────────────────────────────────────────
    # Ustawienia
    # ─────────────────────────────────────────────────────────────────────────

    def save_settings_action(self):
        region = self.region_var.get()
        self.bing_cfg["BING_REGION"] = region
        write_bing_config(self.bing_cfg)
        self.root.focus()
        messagebox.showinfo("", self.T.get("settings_saved", "Zapisano."))

    # ─────────────────────────────────────────────────────────────────────────
    # GLava
    # ─────────────────────────────────────────────────────────────────────────

    def restart_glava(self):
        self._write_rc_module(self.active_module)
        subprocess.run(["pkill", "-x", "glava"])
        self.root.after(500, lambda: subprocess.Popen(
            ["glava", "--desktop"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))

    def _write_rc_module(self, module):
        """Zapisuje aktywny moduł do rc.glsl (#request mod ...)."""
        if not os.path.exists(RC_GLSL):
            return
        with open(RC_GLSL) as f:
            content = f.read()
        import re
        new = re.sub(r'^#request mod .*', f'#request mod {module}', content, flags=re.MULTILINE)
        with open(RC_GLSL, "w") as f:
            f.write(new)

    def update_status(self):
        T = self.T
        res = subprocess.run(["pgrep", "-x", "glava"], capture_output=True)
        running = res.returncode == 0
        module = read_active_module()
        if running:
            if os.path.exists(FLAG_MANUAL):
                mode = T.get("mode_manual", "tryb ręczny")
            elif os.path.exists(FLAG_RED):
                mode = T.get("mode_red", "tryb RED")
            else:
                mode = T.get("mode_auto", "tryb AUTO")
            status = f"● {T.get('status_active', 'GLava aktywna')} [{module}] [{mode}]"
            color = "green"
        else:
            status = f"○ {T.get('status_inactive', 'GLava wyłączona')}"
            color = "red"
        if os.path.exists(WALLPAPER):
            dt = datetime.datetime.fromtimestamp(
                os.path.getmtime(WALLPAPER)).strftime("%d %b %Y %H:%M")
            status += f"   |   {T.get('label_wallpaper', 'Tapeta')}: {dt}"
        else:
            status += f"   |   {T.get('label_no_wallpaper', 'brak tapety')}"
        self.status_label.config(text=status, fg=color)
        self.root.after(3000, self.update_status)


if __name__ == "__main__":
    root = tk.Tk()
    ICON_PATH = os.path.join(SCRIPT_DIR, "icon", "glava-gui.png")
    print("ICON_PATH =", ICON_PATH)
    print("EXISTS   =", os.path.exists(ICON_PATH))
    try:
        icon_img = tk.PhotoImage(file=ICON_PATH)
        root.iconphoto(True, icon_img)
        root._icon_img = icon_img
    except Exception as e:
        print("Nie udało się załadować ikony:", e)
    GlavaControlCenter(root)
    root.mainloop()
