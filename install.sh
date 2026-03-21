#!/bin/bash
# =============================================================================
# install.sh — Instalator projektu bing-glava-suite
# =============================================================================
set -e

RED='\033[0;31m'
GRN='\033[0;32m'
YEL='\033[1;33m'
BLD='\033[1m'
RST='\033[0m'

info()    { echo -e "${GRN}[✓]${RST} $*"; }
warn()    { echo -e "${YEL}[!]${RST} $*"; }
error()   { echo -e "${RED}[✗]${RST} $*"; exit 1; }
section() { echo -e "\n${BLD}═══ $* ═══${RST}"; }

# Backup pliku przed nadpisaniem
backup_file() {
    local FILE="$1"
    local BACKUP_DIR="$2"
    if [ -f "$FILE" ]; then
        mkdir -p "$BACKUP_DIR"
        cp "$FILE" "$BACKUP_DIR/$(basename "$FILE").bak"
        chown -R "$TARGET_USER:$TARGET_USER" "$BACKUP_DIR"
        info "Backup: $(basename "$FILE") → $BACKUP_DIR"
    fi
}

# =============================================================================
# KROK 0: Podstawowe sprawdzenia
# =============================================================================
section "Sprawdzanie środowiska"

if [ "$EUID" -ne 0 ]; then
    error "Instalator musi być uruchomiony jako root (sudo ./install.sh)"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# =============================================================================
# KROK 1: Nazwa użytkownika
# =============================================================================
section "Konfiguracja użytkownika"

echo -e "Dla jakiego użytkownika instalować? (pozostaw puste = bieżący: ${BLD}$SUDO_USER${RST})"
read -rp "Nazwa użytkownika: " INPUT_USER
TARGET_USER="${INPUT_USER:-$SUDO_USER}"

if [ -z "$TARGET_USER" ]; then
    error "Nie można ustalić nazwy użytkownika. Uruchom przez sudo."
fi

if ! id "$TARGET_USER" &>/dev/null; then
    error "Użytkownik '$TARGET_USER' nie istnieje."
fi

TARGET_HOME=$(getent passwd "$TARGET_USER" | cut -d: -f6)
TARGET_UID=$(id -u "$TARGET_USER")
BIN_DIR="$TARGET_HOME/.local/bin"
CONFIG_DIR="$TARGET_HOME/.config/systemd/user"
LOG_DIR="$TARGET_HOME/.local/logs"
GLAVA_CONFIG="$TARGET_HOME/.config/glava"
BACKUP_DIR="$GLAVA_CONFIG/backup_install"

info "Instalacja dla użytkownika: $TARGET_USER ($TARGET_HOME)"

# =============================================================================
# KROK 2: Zależności systemowe
# =============================================================================
section "Instalacja zależności systemowych"

APT_PACKAGES=(curl wget jq inotify-tools python3 python3-pil python3-sklearn
              python3-numpy python3-tk)

MISSING=()
for pkg in "${APT_PACKAGES[@]}"; do
    if ! dpkg -s "$pkg" &>/dev/null; then
        MISSING+=("$pkg")
    fi
done

if [ ${#MISSING[@]} -gt 0 ]; then
    info "Instaluję brakujące pakiety: ${MISSING[*]}"
    apt-get update -qq
    apt-get install -y "${MISSING[@]}"
else
    info "Wszystkie wymagane pakiety są już zainstalowane."
fi

if ! command -v glava &>/dev/null; then
    warn "GLava nie została znaleziona w PATH."
    warn "Zainstaluj GLava ręcznie (https://github.com/jarcode-foss/glava)"
    warn "Kontynuuję instalację, ale demon nie będzie działał bez GLava."
fi

# =============================================================================
# KROK 3: Katalogi
# =============================================================================
section "Tworzenie katalogów"

mkdir -p "$BIN_DIR"
mkdir -p "$CONFIG_DIR"
mkdir -p "$LOG_DIR"
mkdir -p "$TARGET_HOME/Pictures/Bing"
mkdir -p "/usr/share/backgrounds/linuxmint"

chown -R "$TARGET_USER:$TARGET_USER" "$BIN_DIR" "$LOG_DIR" \
    "$TARGET_HOME/Pictures/Bing"

info "Katalogi gotowe."

# =============================================================================
# KROK 4: Instalacja skryptów bash
# =============================================================================
section "Instalacja skryptów"

BASH_SCRIPTS=(
    glava-colorswitch
    glava-toggle
    glava-colors-auto
    glava-color-daemon
)

for script in "${BASH_SCRIPTS[@]}"; do
    SRC="$SCRIPT_DIR/scripts/$script"
    DST="$BIN_DIR/$script"
    if [ ! -f "$SRC" ]; then
        error "Brak pliku źródłowego: $SRC"
    fi
    cp "$SRC" "$DST"
    chmod 755 "$DST"
    chown "$TARGET_USER:$TARGET_USER" "$DST"
    info "Zainstalowano: $DST"
done

SRC="$SCRIPT_DIR/scripts/bing-downloader.sh"
DST_DOWNLOADER="$BIN_DIR/bing-downloader.sh"
sed "s/__USER__/$TARGET_USER/g" "$SRC" > "$DST_DOWNLOADER"
chmod 755 "$DST_DOWNLOADER"
chown "$TARGET_USER:$TARGET_USER" "$DST_DOWNLOADER"
info "Zainstalowano (z podmianą użytkownika): $DST_DOWNLOADER"

# =============================================================================
# KROK 5: Instalacja GUI (Python)
# =============================================================================
section "Instalacja GUI"

SRC="$SCRIPT_DIR/scripts/glava-gui.py"
DST="$BIN_DIR/glava-gui.py"
cp "$SRC" "$DST"
chmod 755 "$DST"
chown "$TARGET_USER:$TARGET_USER" "$DST"

cat > "$BIN_DIR/glava-gui" <<WRAPPER
#!/bin/bash
exec python3 "$BIN_DIR/glava-gui.py" "\$@"
WRAPPER
chmod 755 "$BIN_DIR/glava-gui"
chown "$TARGET_USER:$TARGET_USER" "$BIN_DIR/glava-gui"
info "Zainstalowano GUI: $DST (wrapper: glava-gui)"

# =============================================================================
# KROK 5b: Konfiguracja GLava
# Wszystkie pliki są nadpisywane — oryginały trafiają do backup_install/
# =============================================================================
section "Konfiguracja GLava"

mkdir -p "$GLAVA_CONFIG"
chown "$TARGET_USER:$TARGET_USER" "$GLAVA_CONFIG"

# graph_red.frag — szablon shadera z placeholderami kolorów
backup_file "$GLAVA_CONFIG/graph_red.frag" "$BACKUP_DIR"
cp "$SCRIPT_DIR/config/graph_red.frag" "$GLAVA_CONFIG/graph_red.frag"
chown "$TARGET_USER:$TARGET_USER" "$GLAVA_CONFIG/graph_red.frag"
info "Zainstalowano graph_red.frag"

# rc.glsl — konfiguracja główna GLava (moduł, geometria, ustawienia)
backup_file "$GLAVA_CONFIG/rc.glsl" "$BACKUP_DIR"
cp "$SCRIPT_DIR/glava-config/rc.glsl" "$GLAVA_CONFIG/rc.glsl"
chown "$TARGET_USER:$TARGET_USER" "$GLAVA_CONFIG/rc.glsl"
info "Zainstalowano rc.glsl"

# graph.glsl i graph/1.frag — aktywny shader używany przez glava-colors-auto
mkdir -p "$GLAVA_CONFIG/graph"
backup_file "$GLAVA_CONFIG/graph.glsl" "$BACKUP_DIR"
backup_file "$GLAVA_CONFIG/graph/1.frag" "$BACKUP_DIR"
cp "$SCRIPT_DIR/glava-config/graph.glsl" "$GLAVA_CONFIG/graph.glsl"
cp "$SCRIPT_DIR/glava-config/graph/1.frag" "$GLAVA_CONFIG/graph/1.frag"
chown -R "$TARGET_USER:$TARGET_USER" "$GLAVA_CONFIG/graph"
chown "$TARGET_USER:$TARGET_USER" "$GLAVA_CONFIG/graph.glsl"
info "Zainstalowano konfigurację modułu graph."

# util — shadery pomocnicze wymagane przez moduł graph
if [ -d "$SCRIPT_DIR/glava-config/util" ]; then
    cp -r "$SCRIPT_DIR/glava-config/util" "$GLAVA_CONFIG/util"
    chown -R "$TARGET_USER:$TARGET_USER" "$GLAVA_CONFIG/util"
    info "Zainstalowano katalog util."
fi

# smooth_parameters.glsl — parametry wygładzania audio
if [ -f "$SCRIPT_DIR/glava-config/smooth_parameters.glsl" ]; then
    cp "$SCRIPT_DIR/glava-config/smooth_parameters.glsl" "$GLAVA_CONFIG/smooth_parameters.glsl"
    chown "$TARGET_USER:$TARGET_USER" "$GLAVA_CONFIG/smooth_parameters.glsl"
    info "Zainstalowano smooth_parameters.glsl"
fi

if [ -d "$BACKUP_DIR" ]; then
    info "Kopie zapasowe zapisano w: $BACKUP_DIR"
fi

# =============================================================================
# KROK 5d: Pliki .desktop (wpisy w menu aplikacji)
# =============================================================================
section "Instalacja wpisów menu"

DESKTOP_DIR="$TARGET_HOME/.local/share/applications"
DESKTOP_SRC="$SCRIPT_DIR/desktop"

mkdir -p "$DESKTOP_DIR"
chown "$TARGET_USER:$TARGET_USER" "$DESKTOP_DIR"

if [ -d "$DESKTOP_SRC" ]; then
    for f in "$DESKTOP_SRC"/*.desktop; do
        cp "$f" "$DESKTOP_DIR/"
        chown "$TARGET_USER:$TARGET_USER" "$DESKTOP_DIR/$(basename $f)"
    done
    info "Zainstalowano wpisy menu w: $DESKTOP_DIR"
    # Odśwież cache menu
    sudo -u "$TARGET_USER" update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
else
    warn "Brak katalogu desktop — pomijam wpisy menu."
fi

# =============================================================================
# KROK 6: Usługa systemd użytkownika
# =============================================================================
section "Konfiguracja usługi systemd"

SERVICE_SRC="$SCRIPT_DIR/systemd/glava-color-daemon.service"
SERVICE_DST="$CONFIG_DIR/glava-color-daemon.service"

cp "$SERVICE_SRC" "$SERVICE_DST"
chown "$TARGET_USER:$TARGET_USER" "$SERVICE_DST"

sudo -u "$TARGET_USER" mkdir -p "$CONFIG_DIR/default.target.wants"

sudo -u "$TARGET_USER" \
    XDG_RUNTIME_DIR="/run/user/$TARGET_UID" \
    DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$TARGET_UID/bus" \
    systemctl --user daemon-reload

sudo -u "$TARGET_USER" \
    XDG_RUNTIME_DIR="/run/user/$TARGET_UID" \
    DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$TARGET_UID/bus" \
    systemctl --user enable glava-color-daemon.service

info "Usługa systemd skonfigurowana i włączona."
warn "Aby uruchomić teraz: sudo -u $TARGET_USER systemctl --user start glava-color-daemon"

# =============================================================================
# KROK 7: Cron dla bing-downloader (root)
# =============================================================================
section "Konfiguracja cron (root)"

CRON_LINE="*/15 * * * * $BIN_DIR/bing-downloader.sh >> $LOG_DIR/bing-downloader.log 2>&1"
CRON_MARKER="# bing-glava-suite"

EXISTING=$(crontab -l 2>/dev/null || true)
if echo "$EXISTING" | grep -q "bing-downloader.sh"; then
    warn "Wpis cron dla bing-downloader już istnieje, pomijam."
else
    (echo "$EXISTING"; echo "$CRON_MARKER"; echo "$CRON_LINE") | crontab -
    info "Dodano wpis cron (co godzinę, jako root)."
fi

# =============================================================================
# KROK 8: Pierwsze uruchomienie downloadera
# =============================================================================
section "Pierwsze pobranie tapety"

echo -e "Pobrać tapetę Bing teraz? [T/n]"
read -rp "" RUN_NOW
RUN_NOW="${RUN_NOW:-T}"

if [[ "$RUN_NOW" =~ ^[Tt]$ ]]; then
    info "Uruchamiam bing-downloader.sh..."
    bash "$DST_DOWNLOADER" && info "Tapeta pobrana." || warn "Pobieranie nie powiodło się. Spróbuj ręcznie później."
fi

# =============================================================================
# PODSUMOWANIE
# =============================================================================
section "Instalacja zakończona"

echo ""
echo -e "  Skrypty:          ${BLD}$BIN_DIR/${RST}"
echo -e "  Logi:             ${BLD}$LOG_DIR/${RST}"
echo -e "  Tapety Bing:      ${BLD}$TARGET_HOME/Pictures/Bing/${RST}"
echo -e "  Usługa systemd:   ${BLD}glava-color-daemon.service${RST}"
echo -e "  GUI:              ${BLD}glava-gui${RST} (lub python3 $BIN_DIR/glava-gui.py)"
echo -e "  Backupy GLava:    ${BLD}$BACKUP_DIR/${RST}"
echo ""
warn "WAŻNE: Jeśli nie masz jeszcze konfiguracji GLava, uruchom: glava --copy-config"
warn "       Następnie uruchom usługę: systemctl --user start glava-color-daemon"
echo ""
info "Gotowe! Wyloguj się i zaloguj ponownie, aby usługa systemd wystartowała."
