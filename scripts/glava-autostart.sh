#!/bin/bash
# =============================================================================
# glava-autostart.sh
# Uruchamia wszystkie zarejestrowane instancje GLava przy starcie systemu.
#
# Czyta instances.json i dla każdej instancji:
#   - inst_id=0 : uruchamia glava --desktop (domyślny ~/.config/glava)
#   - inst_id>0 : uruchamia glava --desktop z XDG_CONFIG_HOME=~/.config/glava-inst-{id}
#
# Używane przez ~/.config/autostart/glava.desktop
# =============================================================================

INSTANCES_FILE="$HOME/.config/GlavaMP/instances.json"
LOG_FILE="$HOME/.local/logs/glava-autostart.log"

mkdir -p "$(dirname "$LOG_FILE")"
echo "[$(date)] glava-autostart: start" >> "$LOG_FILE"

# Sprawdz czy glava jest dostepne
if ! command -v glava &>/dev/null; then
    echo "[$(date)] glava-autostart: glava not found in PATH" >> "$LOG_FILE"
    exit 1
fi

# Sprawdz czy instances.json istnieje
if [ ! -f "$INSTANCES_FILE" ]; then
    echo "[$(date)] glava-autostart: no instances.json, starting default instance" >> "$LOG_FILE"
    glava --desktop &
    exit 0
fi

# Parsuj instances.json przez python3 (dostepny wsedzie gdzie tkinter dziala)
python3 - << 'PYEOF'
import json, os, subprocess, sys

HOME = os.path.expanduser("~")
INSTANCES_FILE = os.path.join(HOME, ".config/GlavaMP/instances.json")
LOG_FILE = os.path.join(HOME, ".local/logs/glava-autostart.log")

def log(msg):
    with open(LOG_FILE, "a") as f:
        import datetime
        f.write(f"[{datetime.datetime.now()}] glava-autostart: {msg}\n")

try:
    with open(INSTANCES_FILE) as f:
        instances = json.load(f)
except Exception as e:
    log(f"failed to read instances.json: {e}")
    # Fallback — uruchom domyslna instancje
    subprocess.Popen(["glava", "--desktop"],
                     stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL)
    sys.exit(0)

if not instances:
    log("instances.json empty, starting default")
    subprocess.Popen(["glava", "--desktop"],
                     stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL)
    sys.exit(0)

started = 0
for inst in instances:
    inst_id = inst.get("inst_id", 0)
    module  = inst.get("module", "bars")

    env = os.environ.copy()

    if inst_id == 0:
        # Instancja 0 — domyslny ~/.config/glava, bez nadpisywania XDG
        config_dir = os.path.join(HOME, ".config/glava")
    else:
        # Instancja N — izolowany katalog
        xdg_dir    = os.path.join(HOME, f".config/glava-inst-{inst_id}")
        config_dir = os.path.join(xdg_dir, "glava")
        env["XDG_CONFIG_HOME"] = xdg_dir

    # Pomij jesli katalog konfiguracyjny nie istnieje
    if not os.path.isdir(config_dir):
        log(f"inst {inst_id}: config dir missing ({config_dir}), skipping")
        continue

    try:
        proc = subprocess.Popen(
            ["glava", "--desktop"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )
        log(f"inst {inst_id}: started (module={module}, pid={proc.pid})")
        started += 1
    except Exception as e:
        log(f"inst {inst_id}: failed to start: {e}")

if started == 0:
    log("no instances started, falling back to default")
    subprocess.Popen(["glava", "--desktop"],
                     stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL)
else:
    log(f"started {started} instance(s)")
PYEOF
