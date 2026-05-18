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
# KROK 0: Sprawdzenia
# =============================================================================
section "Checking environment"

if [ "$EUID" -ne 0 ]; then
    echo -e "${YEL}"
    echo "  This uninstaller requires administrator privileges (sudo)."
    echo ""
    echo "  Run again as:"
    echo -e "  ${BLD}sudo ./uninstall.sh${RST}"
    echo -e "${RST}"
    exit 1
fi

# =============================================================================
# KROK 1: Użytkownik docelowy
# =============================================================================
section "User configuration"

echo -e "For which user should the uninstallation be performed? (Enter = current: ${BLD}$SUDO_USER${RST})"
read -rp "Username: " INPUT_USER
TARGET_USER="${INPUT_USER:-$SUDO_USER}"

if [ -z "$TARGET_USER" ]; then
    error "Unable to determine username. Run with: sudo ./uninstall.sh"
fi
if ! id "$TARGET_USER" &>/dev/null; then
    error "User '$TARGET_USER' does not exist."
fi

TARGET_HOME=$(getent passwd "$TARGET_USER" | cut -d: -f6)
TARGET_UID=$(id -u "$TARGET_USER")

# Ścieżki instalacji (zgodne z install.sh)
BIN_DIR="$TARGET_HOME/.local/bin"
GLAVAMP_DIR="$TARGET_HOME/.local/bin/GlavaMP"
GLAVAMP_CONF_DIR="$TARGET_HOME/.config/GlavaMP"
SHARE_DIR="$TARGET_HOME/.local/share/bing-glava-suite"
SYSTEMD_DIR="$TARGET_HOME/.config/systemd/user"
LOG_DIR="$TARGET_HOME/.local/logs"
GLAVA_CONFIG="$TARGET_HOME/.config/glava"
BING_CONFIG_DIR="$TARGET_HOME/.config/bing-glava"
BING_CONF="$BING_CONFIG_DIR/config"
ACTIVE_MODULE_FILE="$GLAVA_CONFIG/active_module"

info "Uninstalling for user: $TARGET_USER ($TARGET_HOME)"

# =============================================================================
# POTWIERDZENIE
# =============================================================================
section "Confirmation"

echo ""
echo -e "  The following will be ${RED}permanently removed${RST}:"
echo -e "  • GUI and scripts:       ${BLD}$GLAVAMP_DIR/${RST}"
echo -e "  • GUI config:            ${BLD}$GLAVAMP_CONF_DIR/${RST}"
echo -e "  • Language files:        ${BLD}$SHARE_DIR/${RST}"
echo -e "  • Bing config:           ${BLD}$BING_CONFIG_DIR/${RST}"
echo -e "  • System script:         ${BLD}/usr/local/bin/bing-downloader.sh${RST}"
echo -e "  • systemd service:       ${BLD}glava-color-daemon${RST}"
echo -e "  • Cron entry:            ${BLD}bing-downloader.sh${RST}"
echo -e "  • Autostart entry:       ${BLD}glava.desktop${RST}"
echo -e "  • .desktop shortcuts"
echo ""
echo -e "  ${YEL}The following will be preserved by default:${RST}"
echo -e "  • Downloaded wallpapers: ${BLD}$TARGET_HOME/Pictures/Bing/${RST}"
echo -e "  • GLava config:          ${BLD}$GLAVA_CONFIG/${RST}  (with backup)"
echo -e "  • GLava itself:          ${BLD}(not uninstalled)${RST}"
echo ""
read -rp "Continue? [y/N]: " CONFIRM
if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

# =============================================================================
# Opcje dodatkowe
# =============================================================================
section "Additional options"

echo -e "Remove downloaded wallpapers (${BLD}$TARGET_HOME/Pictures/Bing/${RST})? [y/N]"
read -rp "" REMOVE_WALLPAPERS
REMOVE_WALLPAPERS="${REMOVE_WALLPAPERS:-N}"

echo -e "Remove GLava configuration (${BLD}$GLAVA_CONFIG/${RST})? [y/N]"
read -rp "" REMOVE_GLAVA_CONFIG
REMOVE_GLAVA_CONFIG="${REMOVE_GLAVA_CONFIG:-N}"

echo -e "Remove log directory (${BLD}$LOG_DIR/${RST})? [y/N]"
read -rp "" REMOVE_LOGS
REMOVE_LOGS="${REMOVE_LOGS:-N}"

# =============================================================================
# KROK 14 (odwrócony): Usługa systemd
# =============================================================================
section "Stopping and disabling systemd service"

SERVICE_FILE="$SYSTEMD_DIR/glava-color-daemon.service"

if [ -d "/run/user/$TARGET_UID" ]; then
    sudo -u "$TARGET_USER" \
        XDG_RUNTIME_DIR="/run/user/$TARGET_UID" \
        DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$TARGET_UID/bus" \
        systemctl --user stop glava-color-daemon.service 2>/dev/null && \
        info "Service stopped." || warn "Service was not running."

    sudo -u "$TARGET_USER" \
        XDG_RUNTIME_DIR="/run/user/$TARGET_UID" \
        DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$TARGET_UID/bus" \
        systemctl --user disable glava-color-daemon.service 2>/dev/null && \
        info "Service disabled." || warn "Service was not enabled."

    sudo -u "$TARGET_USER" \
        XDG_RUNTIME_DIR="/run/user/$TARGET_UID" \
        DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$TARGET_UID/bus" \
        systemctl --user daemon-reload 2>/dev/null || true
else
    warn "No active session — attempting to disable service directly."
    if [ -f "$SERVICE_FILE" ]; then
        # Usuń symlink z wants/ jeśli istnieje
        WANTS_DIR="$SYSTEMD_DIR/default.target.wants"
        rm -f "$WANTS_DIR/glava-color-daemon.service"
        warn "Removed wants/ symlink (if present)."
    fi
fi

if [ -f "$SERVICE_FILE" ]; then
    rm -f "$SERVICE_FILE"
    info "Removed: $SERVICE_FILE"
else
    warn "Service file not found — skipping."
fi

# =============================================================================
# KROK 15 (odwrócony): Cron
# =============================================================================
section "Removing wallpaper cron job"

EXISTING=$(crontab -l 2>/dev/null || true)
if echo "$EXISTING" | grep -q "bing-downloader.sh $TARGET_USER"; then
    NEW_CRON=$(echo "$EXISTING" \
        | grep -v "bing-downloader.sh $TARGET_USER" \
        | grep -v "# bing-glava-suite:$TARGET_USER")
    echo "$NEW_CRON" | crontab -
    info "Cron entry removed for user: $TARGET_USER"
else
    warn "No cron entry found for $TARGET_USER — skipping."
fi

# =============================================================================
# KROK 13 (odwrócony): Autostart GLava
# =============================================================================
section "Removing GLava autostart"

AUTOSTART_FILE="$TARGET_HOME/.config/autostart/glava.desktop"
if [ -f "$AUTOSTART_FILE" ]; then
    rm -f "$AUTOSTART_FILE"
    info "Removed: $AUTOSTART_FILE"
else
    warn "Autostart entry not found — skipping."
fi

# =============================================================================
# KROK 12 (odwrócony): Skróty w menu aplikacji
# =============================================================================
section "Removing application menu shortcuts"

DESKTOP_DST="$TARGET_HOME/.local/share/applications"
for f in "$DESKTOP_DST/GlavaMP.desktop" \
         "$DESKTOP_DST/glava-gui.desktop" \
         "$DESKTOP_DST/bing-glava.desktop"; do
    if [ -f "$f" ]; then
        rm -f "$f"
        info "Removed: $(basename "$f")"
    fi
done

# Usuń wszystkie .desktop z bing-glava-suite (szersza siatka)
find "$DESKTOP_DST" -maxdepth 1 -name "*.desktop" \
    -exec grep -l "GlavaMP\|glava-gui\|bing-glava" {} \; \
    | while read -r f; do
        rm -f "$f"
        info "Removed: $(basename "$f")"
    done

sudo -u "$TARGET_USER" update-desktop-database "$DESKTOP_DST" 2>/dev/null || true

# =============================================================================
# KROK 10 (odwrócony): Konfiguracja GLava
# =============================================================================
section "GLava configuration"

if [[ "$REMOVE_GLAVA_CONFIG" =~ ^[Yy]$ ]]; then
    if [ -d "$GLAVA_CONFIG" ]; then
        rm -rf "$GLAVA_CONFIG"
        info "Removed: $GLAVA_CONFIG"
    else
        warn "GLava config directory not found — skipping."
    fi
else
    # Usuń tylko pliki zainstalowane przez suite, zachowaj resztę
    warn "Keeping GLava config — removing only suite-installed files."

    # active_module
    rm -f "$ACTIVE_MODULE_FILE" && info "Removed: active_module" || true

    # Pliki .glsl zainstalowane przez suite
    for f in rc.glsl smooth_parameters.glsl \
              bars.glsl circle.glsl wave.glsl radial.glsl graph.glsl; do
        if [ -f "$GLAVA_CONFIG/$f" ]; then
            # Przywróć backup jeśli istnieje
            bak="$GLAVA_CONFIG/backup_install/$f.bak"
            if [ -f "$bak" ]; then
                cp "$bak" "$GLAVA_CONFIG/$f"
                chown "$TARGET_USER:$TARGET_USER" "$GLAVA_CONFIG/$f"
                info "Restored from backup: $f"
            else
                rm -f "$GLAVA_CONFIG/$f"
                info "Removed: $f"
            fi
        fi
    done

    # Szablony kolorów (*_colors.frag)
    for module in bars circle wave radial graph; do
        frag="$GLAVA_CONFIG/${module}_colors.frag"
        bak="$GLAVA_CONFIG/backup_install/${module}_colors.frag.bak"
        if [ -f "$frag" ]; then
            if [ -f "$bak" ]; then
                cp "$bak" "$frag"
                chown "$TARGET_USER:$TARGET_USER" "$frag"
                info "Restored from backup: ${module}_colors.frag"
            else
                rm -f "$frag"
                info "Removed: ${module}_colors.frag"
            fi
        fi

        # Przywrócone live shadery
        live_file="$GLAVA_CONFIG/$module/1.frag"
        live_bak="$GLAVA_CONFIG/backup_install/1.frag.bak"
        if [ -f "$live_bak" ]; then
            cp "$live_bak" "$live_file"
            chown "$TARGET_USER:$TARGET_USER" "$live_file"
            info "Restored live shader backup: $module/1.frag"
        fi
    done

    # util/
    if [ -d "$GLAVA_CONFIG/util" ]; then
        rm -rf "$GLAVA_CONFIG/util"
        info "Removed: $GLAVA_CONFIG/util/"
    fi

    # Backup katalogu (już niepotrzebny)
    if [ -d "$GLAVA_CONFIG/backup_install" ]; then
        rm -rf "$GLAVA_CONFIG/backup_install"
        info "Removed: backup_install/"
    fi
fi

# =============================================================================
# KROK 9 (odwrócony): Konfiguracja Bing
# =============================================================================
section "Removing Bing configuration"

if [ -d "$BING_CONFIG_DIR" ]; then
    rm -rf "$BING_CONFIG_DIR"
    info "Removed: $BING_CONFIG_DIR"
else
    warn "Bing config directory not found — skipping."
fi

# =============================================================================
# KROK 8 (odwrócony): Profile i pliki językowe
# =============================================================================
section "Removing presets and language files"

if [ -d "$SHARE_DIR" ]; then
    rm -rf "$SHARE_DIR"
    info "Removed: $SHARE_DIR"
else
    warn "Share directory not found — skipping."
fi

if [ -d "$GLAVAMP_CONF_DIR" ]; then
    rm -rf "$GLAVAMP_CONF_DIR"
    info "Removed: $GLAVAMP_CONF_DIR"
else
    warn "GlavaMP config directory not found — skipping."
fi

# =============================================================================
# KROK 7 (odwrócony): GUI Python
# =============================================================================
section "Removing GUI"

if [ -d "$GLAVAMP_DIR" ]; then
    rm -rf "$GLAVAMP_DIR"
    info "Removed: $GLAVAMP_DIR"
else
    warn "GlavaMP directory not found — skipping."
fi

# Wrapper executable
if [ -f "$BIN_DIR/glava-gui" ]; then
    rm -f "$BIN_DIR/glava-gui"
    info "Removed: $BIN_DIR/glava-gui"
fi

# Ikona
ICON_FILE="$TARGET_HOME/.local/share/icons/hicolor/48x48/apps/glava-gui.png"
if [ -f "$ICON_FILE" ]; then
    rm -f "$ICON_FILE"
    info "Removed: glava-gui.png icon"
fi

# =============================================================================
# KROK 6 (odwrócony): Skrypty użytkownika
# =============================================================================
section "Removing user scripts"

for script in glava-colorswitch glava-toggle glava-colors-auto \
              glava-color-daemon glava-colors-auto-MI \
              bing-fetch-user.sh glava-autostart.sh; do
    dst="$BIN_DIR/$script"
    if [ -f "$dst" ]; then
        rm -f "$dst"
        info "Removed: $dst"
    else
        warn "Not found: $dst — skipping."
    fi
done

# =============================================================================
# KROK 5 (odwrócony): Systemowy skrypt pobierania tapet
# =============================================================================
section "Removing wallpaper downloader script"

if [ -f /usr/local/bin/bing-downloader.sh ]; then
    rm -f /usr/local/bin/bing-downloader.sh
    info "Removed: /usr/local/bin/bing-downloader.sh"
else
    warn "System script not found — skipping."
fi

# =============================================================================
# Opcjonalne: logi
# =============================================================================
if [[ "$REMOVE_LOGS" =~ ^[Yy]$ ]]; then
    section "Removing logs"
    # Usuń tylko logi suite, nie cały katalog logów
    rm -f "$LOG_DIR/bing-downloader.log"
    rm -f "$LOG_DIR/glava-color-daemon.log"
    info "Removed suite log files from $LOG_DIR/"
fi

# =============================================================================
# Opcjonalne: tapety
# =============================================================================
if [[ "$REMOVE_WALLPAPERS" =~ ^[Yy]$ ]]; then
    section "Removing downloaded wallpapers"
    if [ -d "$TARGET_HOME/Pictures/Bing" ]; then
        rm -rf "$TARGET_HOME/Pictures/Bing"
        info "Removed: $TARGET_HOME/Pictures/Bing/"
    else
        warn "Wallpaper directory not found — skipping."
    fi
fi

# =============================================================================
# KROK 4 (odwrócony): Katalogi — sprzątanie pustych
# =============================================================================
section "Cleaning up empty directories"

# Usuń katalogi suite tylko jeśli są puste
for d in \
    "$TARGET_HOME/.local/share/icons/hicolor/48x48/apps" \
    "$TARGET_HOME/.local/share/icons/hicolor/48x48" \
    "$TARGET_HOME/.local/share/icons/hicolor" \
    "$SYSTEMD_DIR/default.target.wants" \
    "$SYSTEMD_DIR"; do
    if [ -d "$d" ] && [ -z "$(ls -A "$d" 2>/dev/null)" ]; then
        rmdir "$d" 2>/dev/null && info "Removed empty dir: $d" || true
    fi
done

# =============================================================================
# Katalogi instancji GLava
# =============================================================================
section "Removing GLava instance directories"

for inst_dir in "$TARGET_HOME"/.config/glava-inst-*; do
    if [ -d "$inst_dir" ]; then
        rm -rf "$inst_dir"
        info "Removed: $inst_dir"
    fi
done

# =============================================================================
# PODSUMOWANIE
# =============================================================================
section "Uninstallation complete"
echo ""
info "bing-glava-suite has been removed."
echo ""

if [[ ! "$REMOVE_GLAVA_CONFIG" =~ ^[Yy]$ ]]; then
    warn "GLava configuration preserved at: ${BLD}$GLAVA_CONFIG/${RST}"
fi
if [[ ! "$REMOVE_WALLPAPERS" =~ ^[Yy]$ ]]; then
    warn "Wallpapers preserved at: ${BLD}$TARGET_HOME/Pictures/Bing/${RST}"
fi
if [[ ! "$REMOVE_LOGS" =~ ^[Yy]$ ]]; then
    warn "Log files preserved at: ${BLD}$LOG_DIR/${RST}"
fi

echo ""
warn "GLava itself was NOT uninstalled. To remove it manually:"
echo -e "  ${BLD}sudo apt remove glava${RST}"
echo ""
info "Done."
