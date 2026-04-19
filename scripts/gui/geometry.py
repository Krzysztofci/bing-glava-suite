import os
# =============================================================================
# gui/geometry.py
# Detekcja ekranu i pasków zadań, obliczanie geometrii GLava.
# Brak importów tkinter — środowiskowo neutralny.
# =============================================================================

import subprocess
import re


# ─────────────────────────────────────────────────────────────────────────────
# Klasyfikacja modułów
# ─────────────────────────────────────────────────────────────────────────────
# NOTE:
# Historyczne grupowanie modułów według sposobu pozycjonowania.
# Obecnie NIEWYKORZYSTYWANE — wszystkie moduły używają pełnoekranowego okna
# z korekcją Y, a korekcja centrowania modułów centered odbywa się w shaderach
# (CENTER_OFFSET_X/Y).
# Pozostawione na przyszłość, jeśli wrócimy do precyzyjnego centrowania.
# Moduły rysowane od dołu okna (graph, bars)
# TODO (future):
# Rozbudować geometrię o:
# - centrowanie względem obszaru roboczego (top/bottom_reserved)
# - pozycjonowanie modułów od góry, dołu, lewo/prawo
# - obsługę obrotów (90/180/270°)
# - dynamiczne XYWH zależne od orientacji modułu
# Obecnie uproszczona wersja dla stabilności.
MODULES_BOTTOM   = {"graph", "bars"}
# Moduły centrowane w obszarze roboczym (circle, radial, wave)
MODULES_CENTERED = {"circle", "radial", "wave"}


# ─────────────────────────────────────────────────────────────────────────────
# Detekcja rozmiaru ekranu i pasków (3 warstwy)
# ─────────────────────────────────────────────────────────────────────────────

def _get_screen_size_xrandr():
    """Zwraca (screen_w, screen_h) z xrandr. Fallback: (1600, 900)."""
    try:
        r = subprocess.run(["xrandr", "--current"], capture_output=True, text=True)
        m = re.search(r'current (\d+) x (\d+)', r.stdout)
        if m:
            return int(m.group(1)), int(m.group(2))
    except Exception:
        pass
    return 1600, 900


def get_strut_reserved():
    """
    Skanuje wszystkie okna X11 przez _NET_WM_STRUT_PARTIAL (standard EWMH).
    Zwraca (top_reserved, bottom_reserved) — piksele zajęte przy górnej
    i dolnej krawędzi ekranu przez paski zadań.

    Obsługuje dowolną liczbę pasków i dowolne ich pozycje.
    Działa na: XFCE, Cinnamon, GNOME, KDE, Openbox, i3+polybar, tint2.

    _NET_WM_STRUT_PARTIAL: left right top bottom
                           left_start_y left_end_y right_start_y right_end_y
                           top_start_x top_end_x bottom_start_x bottom_end_x
    """
    max_top    = 0
    max_bottom = 0
    try:
        r = subprocess.run(["xprop", "-root", "_NET_CLIENT_LIST"],
                           capture_output=True, text=True)
        win_ids = re.findall(r'0x[0-9a-fA-F]+', r.stdout)
        for wid in win_ids:
            res = subprocess.run(
                ["xprop", "-id", wid, "_NET_WM_STRUT_PARTIAL"],
                capture_output=True, text=True
            )
            nums = re.findall(r'\d+', res.stdout)
            if len(nums) >= 4:
                top    = int(nums[2])
                bottom = int(nums[3])
                if top    > max_top:    max_top    = top
                if bottom > max_bottom: max_bottom = bottom
    except Exception:
        pass
    return max_top, max_bottom


def get_screen_info():
    """
    Zwraca (screen_w, screen_h, work_h, top_reserved, bottom_reserved).

    Warstwa 1 — _NET_WM_STRUT_PARTIAL: skanuje wszystkie okna X11,
                zbiera rezerwacje wszystkich pasków (góra + dół).
    Warstwa 2 — _NET_WORKAREA: fallback gdy STRUT dał 0.
    Warstwa 3 — brak pasków: work_h = screen_h.
    """
    screen_w, screen_h = _get_screen_size_xrandr()

    # Warstwa 1: STRUT_PARTIAL
    top_reserved, bottom_reserved = get_strut_reserved()
    if top_reserved > 0 or bottom_reserved > 0:
        work_h = screen_h - top_reserved - bottom_reserved
        return screen_w, screen_h, work_h, top_reserved, bottom_reserved

    # Warstwa 2: _NET_WORKAREA
    try:
        r = subprocess.run(["xprop", "-root", "_NET_WORKAREA"],
                           capture_output=True, text=True)
        wa = re.findall(r'\d+', r.stdout)
        # Format: x y w h [powtórzone dla każdego wirtualnego pulpitu]
        # wa[1] = y offset od góry, wa[3] = wysokość obszaru roboczego
        if len(wa) >= 4:
            work_y = int(wa[1])
            work_h = int(wa[3])
            if 0 < work_h <= screen_h:
                bottom_reserved = screen_h - work_y - work_h
                return screen_w, screen_h, work_h, work_y, max(0, bottom_reserved)
    except Exception:
        pass

    # Warstwa 3: brak info o paskach
    return screen_w, screen_h, screen_h, 0, 0


# ─────────────────────────────────────────────────────────────────────────────
# Obliczanie optymalnej geometrii dla modułu
# ─────────────────────────────────────────────────────────────────────────────

def calc_geometry(module, screen_w, screen_h, bottom_reserved, top_reserved=0):
    """
    Oblicza (x, y, w, h) dla danego modułu.

    MODULES_BOTTOM (graph, bars):
        Podstawa wizualizacji leży na górnej krawędzi dolnego paska.
        Y ujemne przesuwa dół okna GLava dokładnie nad pasek.
        H = screen_h — okno obejmuje cały ekran, GLava rysuje od dołu.

    MODULES_CENTERED (circle, radial, wave):
        Okno wypełnia obszar roboczy między paskami.
        Y = top_reserved, H = screen_h - top_reserved - bottom_reserved.
    """
    # Wszystkie moduły używają pełnego ekranu z korekcją Y
    # Korekta pozycji przez CENTER_OFFSET_X/Y w shaderze
    return 0, -bottom_reserved, screen_w, screen_h


# ─────────────────────────────────────────────────────────────────────────────
# Odczyt i zapis geometrii z rc.glsl
# ─────────────────────────────────────────────────────────────────────────────

def read_geometry(rc_glsl_path):
    """
    Odczytuje geometrię z linii #request setgeometry w rc.glsl.
    Zwraca (x, y, w, h) lub None gdy brak wpisu.
    """
    if not os.path.exists(rc_glsl_path):
        return None
    with open(rc_glsl_path) as f:
        content = f.read()
    m = re.search(
        r'#request\s+setgeometry\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)',
        content
    )
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
    return None


def write_geometry(rc_glsl_path, x, y, w, h):
    """
    Zapisuje geometrię do rc.glsl. Zwraca True przy sukcesie.
    """
    if not os.path.exists(rc_glsl_path):
        return False
    with open(rc_glsl_path) as f:
        content = f.read()
    new = re.sub(
        r'(#request\s+setgeometry\s+)-?\d+\s+-?\d+\s+-?\d+\s+-?\d+',
        f'\\g<1>{x} {y} {w} {h}',
        content
    )
    with open(rc_glsl_path, "w") as f:
        f.write(new)
    return True



