#!/bin/bash
# =============================================================================
# uninstall.sh — Deinstalator bing-glava-suite
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

# =============================================================================
# KROK 0: Sprawdzenie uprawnień
# =============================================================================
section "Sprawdzanie środowiska"

if [ "$EUID" -ne 0 ]; then
    error "Deinstalator musi być uruchomiony jako root (sudo ./uninstall.sh)"
fi

# =============================================================================
# KROK 1: Ustalenie użytkownika
# =============================================================================
section "Ustalanie użytkownika"

echo -e "Dla jakiego użytkownika usunąć instalację? (pozostaw puste = $SUDO_USER)"
read -rp "Nazwa użytkownika: " INPUT_USER
TARGET_USER="${INPUT_USER:-$SUDO_USER}"

if ! id "$TARGET_USER" &>/dev/null; then
    error "Użytkownik '$TARGET_USER' nie istnieje."
fi

TARGET_HOME=$(getent passwd "$TARGET_USER" | cut -d: -f6)
TARGET_UID=$(id -u "$TARGET_USER")

BIN_DIR="$TARGET_HOME/.local/bin"
SHARE_DIR="$TARGET_HOME/.local/share/bing-glava-suite"
CONFIG_DIR="$TARGET_HOME/.config/systemd/user"
LOG_DIR="$TARGET_HOME/.local/logs"
GLAVA_CONFIG="$TARGET_HOME/.config/glava"
BING_CONFIG_DIR="$TARGET_HOME/.config/bing-glava"

info "Deinstalacja dla użytkownika: $TARGET_USER"

# =============================================================================
# KROK 2: Usuwanie skryptów użytkownika
# =============================================================================
section "Usuwanie skryptów użytkownika"

USER_SCRIPTS=(
    glava-colorswitch
    glava-toggle
    glava-colors-auto
    glava-color-daemon
    bing-fetch-user.sh
    glava-gui
    glava-gui.py
)

for script in "${USER_SCRIPTS[@]}"; do
    if [ -f "$BIN_DIR/$script" ]; then
        rm -f "$BIN_DIR/$script"
        info "Usunięto: $BIN_DIR/$script"
    fi
done

# =============================================================================
# KROK 3: Usuwanie systemowego skryptu
# =============================================================================
section "Usuwanie systemowego skryptu"

if [ -f /usr/local/bin/bing-downloader.sh ]; then
    rm -f /usr/local/bin/bing-downloader.sh
    info "Usunięto: /usr/local/bin/bing-downloader.sh"
fi

# =============================================================================
# KROK 4: Usuwanie katalogów
# =============================================================================
section "Usuwanie katalogów"

rm -rf "$SHARE_DIR"
rm -rf "$BING_CONFIG_DIR"
rm -rf "$TARGET_HOME/Pictures/Bing"
rm -rf "$LOG_DIR/bing-downloader.log"

info "Usunięto katalogi konfiguracyjne i dane."

# =============================================================================
# KROK 5: Usuwanie .desktop
# =============================================================================
section "Usuwanie skrótów z menu"

DESKTOP_DST="$TARGET_HOME/.local/share/applications"

rm -f "$DESKTOP_DST/glava.desktop"
rm -f "$DESKTOP_DST/bing-glava.desktop" 2>/dev/null || true

info "Usunięto skróty .desktop."

# =============================================================================
# KROK 6: Usuwanie autostartu
# =============================================================================
section "Usuwanie autostartu"

rm -f "$TARGET_HOME/.config/autostart/glava.desktop"

info "Usunięto autostart GLava."

# =============================================================================
# KROK 7: Usuwanie usługi systemd
# =============================================================================
section "Usuwanie usługi systemd"

SERVICE="$CONFIG_DIR/glava-color-daemon.service"

sudo -u "$TARGET_USER" \
    XDG_RUNTIME_DIR="/run/user/$TARGET_UID" \
    systemctl --user disable glava-color-daemon.service 2>/dev/null || true

rm -f "$SERVICE"
rm -f "$CONFIG_DIR/default.target.wants/glava-color-daemon.service"

info "Usunięto usługę systemd."

# =============================================================================
# KROK 8: Usuwanie wpisu cron
# =============================================================================
section "Usuwanie wpisu cron"

CRON_MARKER="# bing-glava-suite:$TARGET_USER"

EXISTING=$(crontab -l 2>/dev/null || true)
NEW_CRONTAB=$(echo "$EXISTING" | grep -v "bing-downloader.sh $TARGET_USER" | grep -v "$CRON_MARKER")

echo "$NEW_CRONTAB" | crontab -

info "Usunięto wpis cron."

# =============================================================================
# KROK 9: Usunięcie pakietu GLava (opcjonalnie)
# =============================================================================
section "Pakiet GLava"

REMOVE_GLAVA=false

if dpkg -s glava &>/dev/null; then
    echo -e "Wykryto pakiet GLava. Usunąć go? [T/n]"
    read -rp "" REMOVE_GLAVA_INPUT
    REMOVE_GLAVA_INPUT="${REMOVE_GLAVA_INPUT:-T}"

    if [[ "$REMOVE_GLAVA_INPUT" =~ ^[Tt]$ ]]; then
        REMOVE_GLAVA=true
        apt-get remove -y glava
        info "Pakiet GLava został usunięty."
    else
        warn "Pozostawiono pakiet GLava."
    fi
else
    warn "Pakiet GLava nie jest zainstalowany."
fi

# =============================================================================
# KROK 10: Usuwanie konfiguracji GLava (tylko jeśli GLava usunięta)
# =============================================================================
if [ "$REMOVE_GLAVA" = true ]; then
    section "Usuwanie konfiguracji GLava"

    rm -rf "$GLAVA_CONFIG/graph_colors.frag"
    rm -rf "$GLAVA_CONFIG/graph.glsl"
    rm -rf "$GLAVA_CONFIG/graph/1.frag"
    rm -rf "$GLAVA_CONFIG/util"
    rm -rf "$GLAVA_CONFIG/smooth_parameters.glsl"
    rmdir "$GLAVA_CONFIG/graph" 2>/dev/null || true
    rmdir "$GLAVA_CONFIG" 2>/dev/null || true

    info "Usunięto konfigurację GLava zainstalowaną przez bing-glava-suite."
else
    section "Konfiguracja GLava"
    warn "GLava pozostała zainstalowana — konfiguracja nie została usunięta."
fi


# =============================================================================
# KONIEC
# =============================================================================
section "Deinstalacja zakończona"

info "Wszystkie składniki bing-glava-suite zostały usunięte."
echo -e "Możesz teraz usunąć katalog źródłowy projektu, jeśli chcesz."

