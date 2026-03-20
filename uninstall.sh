#!/bin/bash
# =============================================================================
# uninstall.sh — Deinstalator projektu bing-glava-suite
# =============================================================================

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
# Sprawdzenia
# =============================================================================
section "Sprawdzanie środowiska"

if [ "$EUID" -ne 0 ]; then
    error "Deinstalator musi być uruchomiony jako root (sudo ./uninstall.sh)"
fi

echo -e "Dla jakiego użytkownika deinstalować? (pozostaw puste = bieżący: ${BLD}$SUDO_USER${RST})"
read -rp "Nazwa użytkownika: " INPUT_USER
TARGET_USER="${INPUT_USER:-$SUDO_USER}"

if [ -z "$TARGET_USER" ]; then
    error "Nie można ustalić nazwy użytkownika."
fi

if ! id "$TARGET_USER" &>/dev/null; then
    error "Użytkownik '$TARGET_USER' nie istnieje."
fi

TARGET_HOME=$(getent passwd "$TARGET_USER" | cut -d: -f6)
TARGET_UID=$(id -u "$TARGET_USER")
BIN_DIR="$TARGET_HOME/.local/bin"
CONFIG_DIR="$TARGET_HOME/.config/systemd/user"

info "Deinstalacja dla użytkownika: $TARGET_USER ($TARGET_HOME)"

echo ""
echo -e "${RED}Uwaga: ta operacja usunie skrypty, usługę systemd i wpis cron.${RST}"
echo -e "Tapety w ~/Pictures/Bing/ oraz konfiguracja GLava NIE zostaną usunięte."
echo ""
read -rp "Kontynuować? [t/N] " CONFIRM
CONFIRM="${CONFIRM:-N}"
if [[ ! "$CONFIRM" =~ ^[Tt]$ ]]; then
    echo "Przerwano."
    exit 0
fi

# =============================================================================
# Usługa systemd
# =============================================================================
section "Usuwanie usługi systemd"

sudo -u "$TARGET_USER" \
    XDG_RUNTIME_DIR="/run/user/$TARGET_UID" \
    DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$TARGET_UID/bus" \
    systemctl --user disable --now glava-color-daemon.service 2>/dev/null || true

rm -f "$CONFIG_DIR/glava-color-daemon.service"
rm -f "$CONFIG_DIR/default.target.wants/glava-color-daemon.service"

sudo -u "$TARGET_USER" \
    XDG_RUNTIME_DIR="/run/user/$TARGET_UID" \
    DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$TARGET_UID/bus" \
    systemctl --user daemon-reload 2>/dev/null || true

info "Usługa systemd usunięta."

# =============================================================================
# Skrypty
# =============================================================================
section "Usuwanie skryptów"

SCRIPTS=(
    bing-downloader.sh
    glava-color-daemon
    glava-colors-auto
    glava-colorswitch
    glava-toggle
    glava-gui
    glava-gui.py
)

for script in "${SCRIPTS[@]}"; do
    rm -f "$BIN_DIR/$script"
done

info "Skrypty usunięte."

# =============================================================================
# Cron
# =============================================================================
section "Usuwanie wpisu cron"

EXISTING=$(crontab -l 2>/dev/null || true)
if echo "$EXISTING" | grep -q "bing-downloader.sh"; then
    echo "$EXISTING" | grep -v "bing-downloader.sh" | grep -v "# bing-glava-suite" | crontab -
    info "Wpis cron usunięty."
else
    warn "Brak wpisu cron — pomijam."
fi

# =============================================================================
# Ekran logowania
# =============================================================================
section "Przywracanie ekranu logowania"

if [ -L "/usr/share/backgrounds/linuxmint/default_background.jpg" ]; then
    ln -sf "/usr/share/backgrounds/linuxmint/linuxmint.jpg" \
        "/usr/share/backgrounds/linuxmint/default_background.jpg"
    info "Przywrócono domyślne tło ekranu logowania."
fi

rm -f "/usr/share/backgrounds/login-bing.jpg"
info "Usunięto tapetę ekranu logowania."

# =============================================================================
# Podsumowanie
# =============================================================================
section "Deinstalacja zakończona"

echo ""
echo -e "  Zachowane:  ${BLD}$TARGET_HOME/Pictures/Bing/${RST} (tapety)"
echo -e "  Zachowane:  ${BLD}$TARGET_HOME/.config/glava/${RST} (konfiguracja GLava)"
echo -e "  Zachowane:  ${BLD}$TARGET_HOME/.local/logs/${RST} (logi)"
echo ""
info "Gotowe."
