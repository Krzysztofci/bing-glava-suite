#!/usr/bin/env python3
"""
glava_watch.py — multi-instance GLava file watcher
Śledzi zmiany w plikach .glsl, .frag, .json, .conf, .ini
dla wszystkich instancji GLava (glava-inst-0, glava-inst-1, ...).

Użycie:
    python3 glava_watch.py [--verbose] [--mode simple|compact|full]

    --verbose        pokaż wszystkie zmienione linie (bez limitu)
    --mode simple    STARA / NOWA linia (domyślny)
    --mode compact   - stara / + nowa bez ndiff
    --mode full      ndiff z markerami ?
"""

import os
import sys
import time
import difflib
import re
from pathlib import Path

# =============================================================================
# KONFIGURACJA
# =============================================================================

USER_HOME      = os.path.expanduser("~")
CONFIG_HOME    = os.path.join(USER_HOME, ".config")
GLAVAMP_DIR    = os.path.join(CONFIG_HOME, "GlavaMP")

WATCH_EXTENSIONS = {".glsl", ".frag", ".json", ".conf", ".ini"}
SKIP_DIRS        = {"backup_install", ".git", "__pycache__"}
POLL_INTERVAL    = 0.4

VERBOSE   = "--verbose" in sys.argv or "-v" in sys.argv
DIFF_MODE = "simple"
for _a in sys.argv:
    if _a.startswith("--mode="):
        DIFF_MODE = _a.split("=", 1)[1]
if "--mode" in sys.argv:
    _i = sys.argv.index("--mode")
    if _i + 1 < len(sys.argv):
        DIFF_MODE = sys.argv[_i + 1]

# =============================================================================
# KOLORY ANSI
# =============================================================================

RESET   = "\033[0m"
BOLD    = "\033[1m"
RED     = "\033[91m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
BLUE    = "\033[94m"
MAGENTA = "\033[95m"
CYAN    = "\033[96m"
GRAY    = "\033[90m"
WHITE   = "\033[97m"

# Paleta kolorów dla instancji (cykliczna)
INST_COLORS = [CYAN, MAGENTA, YELLOW, GREEN, BLUE, WHITE]

def inst_color(inst_id: int) -> str:
    return INST_COLORS[inst_id % len(INST_COLORS)]

# =============================================================================
# WYKRYWANIE INSTANCJI
# =============================================================================

def find_instances() -> dict:
    """
    Zwraca dict: {inst_id: {"xdg": path, "glava": path, "conf": path}}
    Skanuje ~/.config/glava-inst-* i ~/.config/GlavaMP/inst-*.
    """
    instances = {}

    # ~/.config/glava-inst-N
    pattern = re.compile(r"^glava-inst-(\d+)$")
    if os.path.isdir(CONFIG_HOME):
        for entry in os.scandir(CONFIG_HOME):
            m = pattern.match(entry.name)
            if m and entry.is_dir():
                iid = int(m.group(1))
                xdg_dir   = entry.path
                glava_dir = os.path.join(xdg_dir, "glava")
                conf_dir  = os.path.join(GLAVAMP_DIR, f"inst-{iid}")
                instances[iid] = {
                    "xdg":   xdg_dir,
                    "glava": glava_dir,
                    "conf":  conf_dir,
                }

    return instances

# =============================================================================
# SNAPSHOT
# =============================================================================

def build_snapshot(instances: dict) -> dict:
    """
    Zwraca {path: {"lines": [...], "inst_id": int}}
    dla wszystkich instancji.
    """
    snapshot = {}

    for iid, dirs in instances.items():
        watch_roots = []
        if os.path.isdir(dirs["glava"]):
            watch_roots.append(dirs["glava"])
        if os.path.isdir(dirs["conf"]):
            watch_roots.append(dirs["conf"])

        for root_path in watch_roots:
            for root, dirs_list, files in os.walk(root_path):
                dirs_list[:] = [d for d in dirs_list if d not in SKIP_DIRS]
                for fname in files:
                    if Path(fname).suffix.lower() not in WATCH_EXTENSIONS:
                        continue
                    full = os.path.join(root, fname)
                    try:
                        with open(full, "r", encoding="utf-8", errors="ignore") as f:
                            snapshot[full] = {
                                "lines":   f.readlines(),
                                "inst_id": iid,
                            }
                    except OSError:
                        pass

    return snapshot

# =============================================================================
# ETYKIETY
# =============================================================================

def label_for(path: str, inst_id: int, instances: dict) -> str:
    """Krótka etykieta: '[inst-N] rc.glsl' lub '[inst-N] GlavaMP/inst-N/profiles.json'"""
    dirs = instances.get(inst_id, {})
    glava_dir = dirs.get("glava", "")
    conf_dir  = dirs.get("conf",  "")

    if glava_dir and path.startswith(glava_dir):
        rel = os.path.relpath(path, glava_dir)
        return f"glava › {rel}"
    if conf_dir and path.startswith(conf_dir):
        rel = os.path.relpath(path, conf_dir)
        return f"GlavaMP › {rel}"
    return path

def inst_tag(inst_id: int) -> str:
    color = inst_color(inst_id)
    return f"{color}{BOLD}[inst-{inst_id}]{RESET}"

# =============================================================================
# DIFF
# =============================================================================

def print_diff(old_lines: list, new_lines: list):
    if DIFF_MODE == "full":
        _diff_full(old_lines, new_lines)
    elif DIFF_MODE == "compact":
        _diff_compact(old_lines, new_lines)
    else:
        _diff_simple(old_lines, new_lines)

def _diff_simple(old_lines, new_lines):
    """Styl wersji 1: STARA / NOWA para linii."""
    max_len = max(len(old_lines), len(new_lines))
    shown   = 0
    limit   = 999 if VERBOSE else 12

    for i in range(max_len):
        old = old_lines[i].rstrip() if i < len(old_lines) else None
        new = new_lines[i].rstrip() if i < len(new_lines) else None
        if old == new:
            continue
        if shown >= limit:
            print(f"  {GRAY}… (użyj --verbose by zobaczyć wszystkie zmiany){RESET}")
            break
        if old is None:
            print(f"  {GREEN}DODANO : {new}{RESET}")
        elif new is None:
            print(f"  {RED}USUNIETO: {old}{RESET}")
        else:
            print(f"  {RED}STARA  : {old}{RESET}")
            print(f"  {GREEN}NOWA   : {new}{RESET}")
        shown += 1

def _diff_compact(old_lines, new_lines):
    max_len = max(len(old_lines), len(new_lines))
    shown   = 0
    limit   = 999 if VERBOSE else 12

    for i in range(max_len):
        old = old_lines[i].rstrip() if i < len(old_lines) else None
        new = new_lines[i].rstrip() if i < len(new_lines) else None
        if old == new:
            continue
        if shown >= limit:
            print(f"  {GRAY}… --verbose{RESET}")
            break
        if old is not None:
            print(f"  {RED}- {old}{RESET}")
        if new is not None:
            print(f"  {GREEN}+ {new}{RESET}")
        shown += 1

def _diff_full(old_lines, new_lines):
    for line in difflib.ndiff(old_lines, new_lines):
        prefix  = line[:2]
        content = line[2:].rstrip()
        if not content:
            continue
        if prefix == "- ":
            print(f"  {RED}- {content}{RESET}")
        elif prefix == "+ ":
            print(f"  {GREEN}+ {content}{RESET}")
        elif prefix == "? ":
            print(f"  {YELLOW}? {content}{RESET}")

# =============================================================================
# GŁÓWNA PĘTLA
# =============================================================================

def print_header(instances: dict):
    print(f"\n{BOLD}{'═' * 60}{RESET}")
    print(f"  {WHITE}{BOLD}glava_watch — multi-instance monitor{RESET}")
    print(f"{'═' * 60}")
    print(f"  Tryb diff : {BOLD}{DIFF_MODE}{RESET}"
          f"{'  (pełny)' if VERBOSE else '  (użyj --verbose dla pełnych diffów)'}")
    print(f"  Rozszerzenia: {', '.join(sorted(WATCH_EXTENSIONS))}")
    print()
    if instances:
        print(f"  Znalezione instancje:")
        for iid in sorted(instances):
            tag  = inst_tag(iid)
            gdir = instances[iid]["glava"]
            cdir = instances[iid]["conf"]
            print(f"    {tag}  glava={gdir}")
            if os.path.isdir(cdir):
                print(f"    {'':10}  conf ={cdir}")
    else:
        print(f"  {YELLOW}Brak katalogów glava-inst-*  —  uruchom GUI i dodaj zakładkę.{RESET}")
    print(f"\n{'─' * 60}\n")

def main():
    instances    = find_instances()
    print_header(instances)

    last_snapshot = build_snapshot(instances)
    last_inst_ids = set(instances.keys())

    print(f"  {len(last_snapshot)} plik(ów) zaindeksowanych. Ctrl+C aby zatrzymać.\n")

    try:
        while True:
            time.sleep(POLL_INTERVAL)

            # ── Wykryj nowe/usunięte instancje ────────────────────────────
            instances     = find_instances()
            current_ids   = set(instances.keys())

            for iid in current_ids - last_inst_ids:
                print(f"{inst_tag(iid)}  {GREEN}NOWA INSTANCJA  "
                      f"{instances[iid]['glava']}{RESET}")
            for iid in last_inst_ids - current_ids:
                color = inst_color(iid)
                print(f"{color}{BOLD}[inst-{iid}]{RESET}  "
                      f"{RED}INSTANCJA USUNIĘTA{RESET}")

            last_inst_ids = current_ids

            # ── Snapshot ───────────────────────────────────────────────────
            current_snapshot = build_snapshot(instances)
            ts = time.strftime("%H:%M:%S")

            prev_paths = set(last_snapshot)
            curr_paths = set(current_snapshot)

            # Nowe pliki
            for path in sorted(curr_paths - prev_paths):
                iid  = current_snapshot[path]["inst_id"]
                lbl  = label_for(path, iid, instances)
                print(f"{inst_tag(iid)}  {GREEN}[{ts}] NOWY     {lbl}{RESET}")

            # Usunięte pliki
            for path in sorted(prev_paths - curr_paths):
                iid  = last_snapshot[path]["inst_id"]
                lbl  = label_for(path, iid, instances)
                print(f"{inst_tag(iid)}  {RED}[{ts}] USUNIĘTY {lbl}{RESET}")

            # Zmodyfikowane pliki
            for path in sorted(curr_paths & prev_paths):
                old = last_snapshot[path]
                new = current_snapshot[path]
                if old["lines"] == new["lines"]:
                    continue
                iid = new["inst_id"]
                lbl = label_for(path, iid, instances)
                print(f"{inst_tag(iid)}  {CYAN}[{ts}] ZMIANA   {lbl}{RESET}")
                print_diff(old["lines"], new["lines"])
                print()

            last_snapshot = current_snapshot

    except KeyboardInterrupt:
        print(f"\n{YELLOW}Zatrzymano.{RESET}\n")


if __name__ == "__main__":
    main()
