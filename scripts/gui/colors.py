# =============================================================================
# gui/colors.py
# Logika kolorów: odczyt z shadera, zapis do shadera, toggle HSV/RGB.
# Brak importów tkinter.
# =============================================================================

import os
import re
from .core import (
    HSV_MODE_PATTERN, FLAG_RED, FLAG_MANUAL,
    get_live_frag, get_template,
)


def hex_to_vec3(hex_color):
    """'#rrggbb' → (r_f, g_f, b_f) w zakresie 0.0–1.0"""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return r / 255.0, g / 255.0, b / 255.0


def vec3_to_hex(r_f, g_f, b_f):
    """(r_f, g_f, b_f) → '#rrggbb'"""
    return "#{:02x}{:02x}{:02x}".format(
        int(r_f * 255), int(g_f * 255), int(b_f * 255)
    )


def read_colors_from_frag(frag_path):
    """
    Odczytuje kolory bottom/mid/top z pliku .frag.
    Zwraca dict {'bottom': '#rrggbb', 'mid': '#rrggbb', 'top': '#rrggbb'}
    lub None jeśli plik nie istnieje lub brak wektorów.
    """
    if not os.path.exists(frag_path):
        return None
    with open(frag_path) as f:
        content = f.read()
    result = {}
    for key in ("bottom", "mid", "top"):
        m = re.search(
            rf"vec3\s+{key}\s*=\s*vec3\s*\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*\)\s*;",
            content
        )
        if m:
            result[key] = vec3_to_hex(float(m.group(1)), float(m.group(2)), float(m.group(3)))
    if len(result) == 3:
        return result
    return None


def write_colors_to_frag(module, colors, gradient_mode="rgb"):
    """
    Zapisuje kolory do live frag aktywnego modułu (kopiując z szablonu).
    Ustawia flagę manual.shift i red.shift.
    Zwraca (True, "") przy sukcesie lub (False, komunikat_błędu).

    colors: {'bottom': '#rrggbb', 'mid': '#rrggbb', 'top': '#rrggbb'}
    """
    tmpl = get_template(module)
    live = get_live_frag(module)

    if not os.path.exists(tmpl):
        return False, f"Brak szablonu: {tmpl}"

    with open(tmpl) as f:
        lines = f.readlines()

    os.makedirs(os.path.dirname(live), exist_ok=True)
    with open(live, "w") as f:
        for line in lines:
            written = False
            for k in ("bottom", "mid", "top"):
                if f"vec3 {k}" in line:
                    r_f, g_f, b_f = hex_to_vec3(colors[k])
                    f.write(f"vec3 {k} = vec3({r_f:.2f}, {g_f:.2f}, {b_f:.2f});\n")
                    written = True
                    break
            if not written:
                f.write(line)

    # Ustaw tryb gradientu jeśli shader to obsługuje
    with open(live) as f:
        src = f.read()
    if "#define HSV_MODE" in src:
        hsv_val = "1" if gradient_mode == "hsv" else "0"
        src = HSV_MODE_PATTERN.sub(f"#define HSV_MODE {hsv_val}", src)

    if "#define HSV_MODE" in src:
        with open(live, "w") as f:
            f.write(src)

    # Ustaw flagi
    open(FLAG_RED, "a").close()
    open(FLAG_MANUAL, "a").close()

    return True, ""


def set_gradient_mode(module, mode):
    """
    Przełącza HSV/RGB w szablonie i live frag danego modułu.
    mode: 'rgb' lub 'hsv'
    """
    hsv_val = "1" if mode == "hsv" else "0"
    for fpath in (get_template(module), get_live_frag(module)):
        if not os.path.exists(fpath):
            continue
        with open(fpath) as f:
            src = f.read()
        if "#define HSV_MODE" not in src:
            continue
        new_src = HSV_MODE_PATTERN.sub(f"#define HSV_MODE {hsv_val}", src)
        with open(fpath, "w") as f:
            f.write(new_src)




def shader_supports_hsv(module):
    """
    Zwraca True jeśli aktywny shader modułu obsługuje przełącznik HSV.
    Sprawdza najpierw live frag, potem szablon.
    """
    for path in (get_live_frag(module), get_template(module)):
        if os.path.exists(path):
            with open(path) as f:
                return "#define HSV_MODE" in f.read()
    return False
