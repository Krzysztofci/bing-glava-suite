# =============================================================================
# gui/core.py
# Stałe, ścieżki, i18n, ustawienia, presety kolorów, profile szaderów.
# Brak importów tkinter — ten moduł jest środowiskowo neutralny.
# =============================================================================

import os
import json
import glob
import re

# ─────────────────────────────────────────────────────────────────────────────
# Ścieżki
# ─────────────────────────────────────────────────────────────────────────────

USER_HOME      = os.path.expanduser("~")
CONFIG_DIR     = os.path.join(USER_HOME, ".config/GlavaMP")
GLAVA_DIR      = os.path.join(USER_HOME, ".config/glava")
BINGCONF_DIR   = os.path.join(USER_HOME, ".config/bing-glava")
BIN_DIR        = os.path.join(USER_HOME, ".local/bin")

RC_GLSL        = os.path.join(GLAVA_DIR, "rc.glsl")
FLAG_RED       = os.path.join(GLAVA_DIR, "red.shift")
FLAG_MANUAL    = os.path.join(GLAVA_DIR, "manual.shift")
WALLPAPER_LOCK = os.path.join(BINGCONF_DIR, "wallpaper.lock")
ACTIVE_MODULE_FILE = os.path.join(GLAVA_DIR, "active_module")

BINGCONF_FILE  = os.path.join(BINGCONF_DIR, "config")
SETTINGS_FILE  = os.path.join(CONFIG_DIR, "gui_settings.json")
PRESETS_FILE   = os.path.join(CONFIG_DIR, "presets.json")        # profile kolorów
PROFILES_FILE  = os.path.join(CONFIG_DIR, "profiles.json")     # profile szaderów

WALLPAPER      = os.path.join(USER_HOME, "Pictures/Bing/bing_today.jpg")

# Katalog lang — szukamy względem lokalizacji tego pliku
_SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
_CANDIDATES = [
    os.path.join(_SCRIPT_DIR, "..", "..", "lang"),
    os.path.join(_SCRIPT_DIR, "..", "lang"),
    os.path.join(os.path.expanduser("~"), ".local/share/bing-glava-suite/lang"),
    os.path.join(USER_HOME, ".local/share/bing-glava-suite/lang"),
]
LANG_DIR = next((p for p in _CANDIDATES if os.path.isdir(p)),
                os.path.join(_SCRIPT_DIR, "..", "..", "lang"))

# ─────────────────────────────────────────────────────────────────────────────
# Moduły GLava
# ─────────────────────────────────────────────────────────────────────────────

GLAVA_MODULES = ["bars", "circle", "graph", "radial", "wave"]

MODULE_TEMPLATES = {
    "graph":  "graph_colors.frag",
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

BING_REGIONS = [
    "de-DE", "en-US", "en-GB", "fr-FR", "es-ES",
    "it-IT", "pt-BR", "ja-JP", "zh-CN", "pl-PL",
]

HSV_MODE_PATTERN = re.compile(r'#define HSV_MODE [01]')
# ─────────────────────────────────────────────────────────────────────────────
# Aktywny moduł
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
    return os.path.join(GLAVA_DIR, MODULE_LIVEFRAGS.get(module, "graph/1.frag"))


def get_template(module=None):
    if module is None:
        module = read_active_module()
    return os.path.join(GLAVA_DIR, MODULE_TEMPLATES.get(module, "graph_colors.frag"))


# ─────────────────────────────────────────────────────────────────────────────
# Ustawienia GUI
# ─────────────────────────────────────────────────────────────────────────────

def load_settings():
    defaults = {"lang": "en", "gradient_mode": "rgb"}
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
# Konfiguracja Bing
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
# i18n
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
# Profile kolorów (presets.json — tylko 3 kolory, bez modułu/geometrii)
# ─────────────────────────────────────────────────────────────────────────────

def load_color_presets():
    if os.path.exists(PRESETS_FILE):
        try:
            with open(PRESETS_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_color_presets(presets):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(PRESETS_FILE, "w") as f:
        json.dump(presets, f, indent=4)


# ─────────────────────────────────────────────────────────────────────────────
# Profile szaderów (profiles.json — kształt + dynamika per moduł, BEZ kolorów)
#
# Format:
# {
#   "bars": {
#     "Gruby bass": {"bar_width": 8, "bar_gap": 3, "smoothing": 4, ...},
#     "Delikatny":  {"bar_width": 2, "bar_gap": 1, "smoothing": 8, ...}
#   },
#   "circle": {
#     "Duże koło":  {"radius": 220, "thickness": 5, ...}
#   }
# }
# ─────────────────────────────────────────────────────────────────────────────

def load_shader_profiles():
    if os.path.exists(PROFILES_FILE):
        try:
            with open(PROFILES_FILE) as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {}


def save_shader_profiles(profiles):
    os.makedirs(BINGCONF_DIR, exist_ok=True)
    with open(PROFILES_FILE, "w") as f:
        json.dump(profiles, f, indent=4, ensure_ascii=False)


def get_shader_profiles_for_module(module):
    """Zwraca dict profili dla konkretnego modułu."""
    return load_shader_profiles().get(module, {})


def save_shader_profile_for_module(module, name, params):
    """Zapisuje pojedynczy profil dla modułu."""
    all_profiles = load_shader_profiles()
    if module not in all_profiles:
        all_profiles[module] = {}
    all_profiles[module][name] = params
    save_shader_profiles(all_profiles)


def delete_shader_profile_for_module(module, name):
    """Usuwa profil dla modułu. Zwraca True jeśli usunięto."""
    all_profiles = load_shader_profiles()
    if module in all_profiles and name in all_profiles[module]:
        del all_profiles[module][name]
        if not all_profiles[module]:
            del all_profiles[module]
        save_shader_profiles(all_profiles)
        return True
    return False
