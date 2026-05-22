# =============================================================================
# gui/modules/glsl_io.py
# Wspólna warstwa I/O dla modułów szaderów.
# Obsługuje odczyt/zapis plików .glsl (#define, #request) oraz tooltip _tip.
# =============================================================================

import os
import re
import tkinter as tk
import tkinter.ttk as ttk


# ─────────────────────────────────────────────────────────────────────────────
# Pomocnicze
# ─────────────────────────────────────────────────────────────────────────────

def decimals(step):
    """Liczba miejsc po przecinku wynikająca z wartości kroku."""
    s = str(step)
    return len(s.rstrip("0").split(".")[-1]) if "." in s else 0


# ─────────────────────────────────────────────────────────────────────────────
# #define — parametry kształtu (int)
# ─────────────────────────────────────────────────────────────────────────────

def read_defines(path, param_defs):
    """
    Czyta wartości #define z pliku .glsl.
    param_defs: lista krotek — indeks 0 = klucz, indeks 4 = wartość domyślna.
    Zwraca dict {klucz: wartość_int}.
    """
    result = {p[0]: p[4] for p in param_defs}
    if not os.path.exists(path):
        return result
    with open(path) as f:
        content = f.read()
    for p in param_defs:
        m = re.search(rf'^#define\s+{p[0]}\s+(\S+)', content, re.MULTILINE)
        if m:
            try:
                result[p[0]] = int(m.group(1))
            except ValueError:
                pass
    return result


def write_defines(path, params, param_defs):
    """
    Zapisuje #define do pliku .glsl.
    Usuwa duplikaty danego klucza, zostawia jeden czysty wpis.
    Jeśli klucz nie istnieje w pliku — dopisuje na końcu.
    """
    if not os.path.exists(path):
        return
    keys = {p[0] for p in param_defs}
    with open(path) as f:
        content = f.read()
    for key, val in params.items():
        if key not in keys:
            continue
        pattern = rf'^#define\s+{key}\s+\S+[ \t]*$'
        matches = re.findall(pattern, content, re.MULTILINE)
        if matches:
            first_pos = re.search(pattern, content, re.MULTILINE).start()
            content = re.sub(pattern, '', content, flags=re.MULTILINE)
            content = re.sub(r'\n{3,}', '\n\n', content)
            content = content[:first_pos] + f'#define {key} {val}\n' + content[first_pos:]
        else:
            content = content.rstrip() + f'\n#define {key} {val}\n'
    with open(path, "w") as f:
        f.write(content)


# ─────────────────────────────────────────────────────────────────────────────
# #define — flagi (0/1)
# ─────────────────────────────────────────────────────────────────────────────

def read_flag_defines(path, flag_params):
    """
    Czyta wartości flag #define z pliku .glsl.
    flag_params: lista krotek — indeks 0 = klucz.
    Zwraca dict {klucz: int(0|1)}.
    """
    result = {p[0]: 0 for p in flag_params}
    if not os.path.exists(path):
        return result
    with open(path) as f:
        content = f.read()
    for p in flag_params:
        m = re.search(rf'^#define\s+{p[0]}\s+(\S+)', content, re.MULTILINE)
        if m:
            try:
                result[p[0]] = int(m.group(1))
            except ValueError:
                pass
    return result


def write_flag_defines(path, params, flag_params):
    """
    Jak write_defines ale dla flag — ta sama logika deduplikacji.
    """
    if not os.path.exists(path):
        return
    keys = {p[0] for p in flag_params}
    with open(path) as f:
        content = f.read()
    for key, val in params.items():
        if key not in keys:
            continue
        pattern = rf'^#define\s+{key}\s+\S+[ \t]*$'
        matches = re.findall(pattern, content, re.MULTILINE)
        if matches:
            first_pos = re.search(pattern, content, re.MULTILINE).start()
            content = re.sub(pattern, '', content, flags=re.MULTILINE)
            content = re.sub(r'\n{3,}', '\n\n', content)
            content = content[:first_pos] + f'#define {key} {val}\n' + content[first_pos:]
        else:
            content = content.rstrip() + f'\n#define {key} {val}\n'
    with open(path, "w") as f:
        f.write(content)


# ─────────────────────────────────────────────────────────────────────────────
# #define — surowe wartości (radial: floaty, wyrażenia PI itp.)
# ─────────────────────────────────────────────────────────────────────────────

def read_raw(path):
    """
    Czyta wszystkie #define z pliku jako surowe stringi.
    Zwraca dict {klucz: string_wartości}.
    Używane przez radial (floaty, wyrażenia z PI).
    """
    result = {}
    if not os.path.exists(path):
        return result
    with open(path) as f:
        content = f.read()
    for m in re.finditer(r'^#define\s+(\w+)\s+(.+)', content, re.MULTILINE):
        key = m.group(1)
        if key not in result:
            result[key] = m.group(2).strip()
    return result


def write_define_int(path, key, val):
    """Zapisuje #define KEY val (int) — tryb append/replace bez deduplikacji pozycji."""
    if not os.path.exists(path):
        return
    with open(path) as f:
        content = f.read()
    content = re.sub(rf'^#define\s+{key}\s+\S+[ \t]*\n?', '',
                     content, flags=re.MULTILINE)
    content = content.rstrip() + f'\n#define {key} {val}\n'
    with open(path, "w") as f:
        f.write(content)


def write_define_float(path, key, val, step):
    """Zapisuje #define KEY val (float, precyzja wynika z kroku)."""
    dec = decimals(step)
    write_define_raw(path, key, f"{val:.{dec}f}")


def write_define_raw(path, key, val_str):
    """Zapisuje #define KEY val_str (surowy string — dowolna wartość, np. wyrażenie PI)."""
    if not os.path.exists(path):
        return
    with open(path) as f:
        content = f.read()
    content = re.sub(rf'^#define\s+{key}\s+.+\n?', '',
                     content, flags=re.MULTILINE)
    content = content.rstrip() + f'\n#define {key} {val_str}\n'
    with open(path, "w") as f:
        f.write(content)


# ─────────────────────────────────────────────────────────────────────────────
# #request — smooth_parameters.glsl
# ─────────────────────────────────────────────────────────────────────────────

def read_smooth(path, smooth_params):
    """
    Czyta wartości #request z smooth_parameters.glsl.
    smooth_params: lista krotek — indeks 0 = klucz, indeks 4 = domyślna.
    Zwraca dict {klucz: wartość}.
    """
    result = {p[0]: p[4] for p in smooth_params}
    if not os.path.exists(path):
        return result
    with open(path) as f:
        content = f.read()
    for p in smooth_params:
        m = re.search(rf'^#request\s+{p[0]}\s+(\S+)', content, re.MULTILINE)
        if m:
            try:
                result[p[0]] = int(m.group(1)) if p[0] == "setavgframes" \
                               else float(m.group(1))
            except ValueError:
                pass
    return result


def write_smooth(path, params, smooth_params):
    """
    Zapisuje #request do smooth_parameters.glsl (in-place replace).
    smooth_params: lista krotek — step na indeksie -2 (przedostatni element).
    Obsługuje zarówno 6-krotkę jak i 8-krotkę przez indeks -2.
    """
    if not os.path.exists(path):
        return
    keys = {p[0] for p in smooth_params}
    with open(path) as f:
        content = f.read()
    for key, val in params.items():
        if key not in keys:
            continue
        p = next(x for x in smooth_params if x[0] == key)
        dec = decimals(p[-2])   # indeks -2: step działa dla 6-krotek i 8-krotek
        sv = str(int(val)) if key == "setavgframes" else f"{float(val):.{dec}f}"
        content = re.sub(rf'^(#request\s+{key}\s+)\S+', rf'\g<1>{sv}',
                         content, flags=re.MULTILINE)
    with open(path, "w") as f:
        f.write(content)


# ─────────────────────────────────────────────────────────────────────────────
# #request — rc.glsl (int, bool, raw string)
# ─────────────────────────────────────────────────────────────────────────────

def read_int_req(path, key, default):
    """Czyta #request KEY wartość (int) z rc.glsl."""
    if not os.path.exists(path):
        return {key: default}
    with open(path) as f:
        content = f.read()
    m = re.search(rf'^#request\s+{key}\s+(\S+)', content, re.MULTILINE)
    try:
        return {key: int(m.group(1))} if m else {key: default}
    except ValueError:
        return {key: default}


def write_int_req(path, key, val):
    """Zapisuje #request KEY val (int) do rc.glsl."""
    if not os.path.exists(path):
        return
    with open(path) as f:
        content = f.read()
    content = re.sub(rf'^(#request\s+{key}\s+)\S+', rf'\g<1>{val}',
                     content, flags=re.MULTILINE)
    with open(path, "w") as f:
        f.write(content)


def read_bool_req(path, key):
    """Czyta #request KEY true/false z rc.glsl."""
    if not os.path.exists(path):
        return {key: False}
    with open(path) as f:
        content = f.read()
    m = re.search(rf'^#request\s+{key}\s+(\S+)', content, re.MULTILINE)
    return {key: (m.group(1) == "true")} if m else {key: False}


def write_bool_req(path, key, val):
    """Zapisuje #request KEY true/false do rc.glsl."""
    if not os.path.exists(path):
        return
    with open(path) as f:
        content = f.read()
    sv = "true" if val else "false"
    content = re.sub(rf'^(#request\s+{key}\s+)\S+', rf'\g<1>{sv}',
                     content, flags=re.MULTILINE)
    with open(path, "w") as f:
        f.write(content)


def write_request(path, key, val_str):
    """Zapisuje #request KEY val_str (surowy string) do dowolnego pliku .glsl."""
    if not os.path.exists(path):
        return
    with open(path) as f:
        content = f.read()
    content = re.sub(rf'^(#request\s+{key}\s+)\S+', rf'\g<1>{val_str}',
                     content, flags=re.MULTILINE)
    with open(path, "w") as f:
        f.write(content)


# ─────────────────────────────────────────────────────────────────────────────
# Tooltip
# ─────────────────────────────────────────────────────────────────────────────

def tip(parent, label, text):
    """
    Tworzy etykietę '?' z tooltipem.
    Kolory pobierane ze stylów TTK — brak hardkodowanych wartości.
    Zwraca widget ttk.Label lub None jeśli text jest pusty.
    """
    if not text:
        return None
    lbl = ttk.Label(parent, text=label, cursor="question_arrow")
    tip_window = [None]

    def show(e):
        x = lbl.winfo_rootx() + 20
        y = lbl.winfo_rooty() + 20
        tw = tk.Toplevel(lbl)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        ttk.Label(tw, text=text, justify="left").pack(padx=5, pady=2)
        tip_window[0] = tw

    def hide(e):
        if tip_window[0]:
            tip_window[0].destroy()
            tip_window[0] = None

    lbl.bind("<Enter>", show)
    lbl.bind("<Leave>", hide)
    return lbl

def read_all_defines(path):
    """Czyta wszystkie #define z pliku .glsl. Zwraca dict {klucz: wartość_str}."""
    result = {}
    if not os.path.exists(path):
        return result
    with open(path) as f:
        content = f.read()
    for m in re.finditer(r'^#define\s+(\w+)\s+(\S+)', content, re.MULTILINE):
        result[m.group(1)] = m.group(2)
    return result
