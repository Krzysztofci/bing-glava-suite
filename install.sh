#!/bin/bash
# =============================================================================
# install.sh — Instalator bing-glava-suite
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
    echo "  This installer requires administrator privileges (sudo)."
    echo "  They are needed only for:"
    echo "    • installing the system wallpaper downloader script"
    echo "    • enabling the systemd linger for the target user"
    echo ""
    echo "  Run again as:"
    echo -e "  ${BLD}sudo ./install.sh${RST}"
    echo -e "${RST}"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# =============================================================================
# KROK 1: Użytkownik docelowy
# =============================================================================
section "User configuration"

echo -e "For which user should the installation be performed? (Enter = current: ${BLD}$SUDO_USER${RST})"
read -rp "Username: " INPUT_USER
TARGET_USER="${INPUT_USER:-$SUDO_USER}"

if [ -z "$TARGET_USER" ]; then
    error "Unable to determine username. Run with: sudo ./install.sh"
fi
if ! id "$TARGET_USER" &>/dev/null; then
    error "User '$TARGET_USER' does not exist."
fi

TARGET_HOME=$(getent passwd "$TARGET_USER" | cut -d: -f6)
TARGET_UID=$(id -u "$TARGET_USER")

# Ścieżki instalacji
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

info "Installing for user: $TARGET_USER ($TARGET_HOME)"

# =============================================================================
# KROK 2: Interwał crona
# =============================================================================
section "Cron configuration"

echo -e "How often should the Bing wallpaper be downloaded? (Enter = ${BLD}15${RST}, for one hour enter 60)"
read -rp "Interval [minutes]: " INPUT_CRON
INPUT_CRON="${INPUT_CRON:-15}"

if ! [[ "$INPUT_CRON" =~ ^[0-9]+$ ]] || [ "$INPUT_CRON" -lt 1 ] || [ "$INPUT_CRON" -gt 1440 ]; then
    warn "Invalid value — using 15 minutes."
    INPUT_CRON=15
fi

if [ "$INPUT_CRON" -eq 60 ]; then
    CRON_SCHEDULE="0 * * * *"
else
    CRON_SCHEDULE="*/$INPUT_CRON * * * *"
fi
info "Interval: every $INPUT_CRON minutes"

# =============================================================================
# KROK 3: Zależności
# =============================================================================
section "Installing dependencies"

APT_PACKAGES=(curl wget jq inotify-tools python3 python3-pil
              python3-sklearn python3-numpy python3-tk)
MISSING=()
for pkg in "${APT_PACKAGES[@]}"; do
    dpkg -s "$pkg" &>/dev/null || MISSING+=("$pkg")
done

if [ ${#MISSING[@]} -gt 0 ]; then
    info "Missing packages: ${MISSING[*]}"
    apt-get update -qq
    apt-get install -y "${MISSING[@]}"
else
    info "All required packages are installed."
fi

# GLava
GLAVA_INSTALLED=false
if command -v glava &>/dev/null; then
    GLAVA_INSTALLED=true
    info "GLava is installed."
else
    warn "GLava was not found."
    echo -e "Download and install GLava automatically? [Y/n]"
    read -rp "" INSTALL_GLAVA
    INSTALL_GLAVA="${INSTALL_GLAVA:-Y}"
    if [[ "$INSTALL_GLAVA" =~ ^[Yy]$ ]]; then
        info "Downloading GLava from GitHub Releases..."
        GLAVA_URL=$(curl -s https://api.github.com/repos/Krzysztofci/bing-glava-suite/releases/latest \
            | jq -r '.assets[] | select(.name | endswith(".deb")) | .browser_download_url')
        if [ -z "$GLAVA_URL" ]; then
            warn "Failed to fetch GLava package URL. Install manually."
        else
            GLAVA_DEB="/tmp/glava_latest.deb"
            wget -q --show-progress -O "$GLAVA_DEB" "$GLAVA_URL"
            dpkg -i "$GLAVA_DEB" || apt-get install -f -y
            rm -f "$GLAVA_DEB"
            GLAVA_INSTALLED=true
            info "GLava installed."
        fi
    else
        warn "Continuing without GLava — the visualizer will not work."
    fi
fi

# =============================================================================
# KROK 4: Katalogi
# =============================================================================
section "Creating directories"

mkdir -p \
    "$BIN_DIR" \
    "$GLAVAMP_DIR/gui/modules" \
    "$GLAVAMP_DIR/icon" \
    "$GLAVAMP_CONF_DIR" \
    "$SHARE_DIR/lang" \
    "$SYSTEMD_DIR" \
    "$LOG_DIR" \
    "$TARGET_HOME/Pictures/Bing" \
    "$BING_CONFIG_DIR" \
    "$GLAVA_CONFIG/util" \
    "$TARGET_HOME/.local/share/icons/hicolor/48x48/apps" \
    "$TARGET_HOME/.local/share/applications" \
    "$TARGET_HOME/.config/autostart" \
    "/usr/share/backgrounds/linuxmint"

chown -R "$TARGET_USER:$TARGET_USER" \
    "$BIN_DIR" \
    "$SHARE_DIR" \
    "$LOG_DIR" \
    "$TARGET_HOME/Pictures/Bing" \
    "$BING_CONFIG_DIR" \
    "$GLAVAMP_CONF_DIR" \
    "$GLAVA_CONFIG" \
    "$TARGET_HOME/.local/share/icons" \
    "$TARGET_HOME/.local/share/applications" \
    "$TARGET_HOME/.config/autostart"

info "Directories ready."

# =============================================================================
# KROK 5: Systemowy skrypt pobierania tapet
# =============================================================================
section "Installing wallpaper downloader script"

cp "$SCRIPT_DIR/scripts/bing-downloader.sh" /usr/local/bin/bing-downloader.sh
chmod 755 /usr/local/bin/bing-downloader.sh
chown root:root /usr/local/bin/bing-downloader.sh
info "Installed: /usr/local/bin/bing-downloader.sh"

# =============================================================================
# KROK 6: Skrypty użytkownika → ~/.local/bin/
# =============================================================================
section "Installing user scripts"

for script in glava-colorswitch glava-toggle glava-colors-auto \
              glava-color-daemon bing-fetch-user.sh; do
    src="$SCRIPT_DIR/scripts/$script"
    dst="$BIN_DIR/$script"
    [ -f "$src" ] || error "Missing file: $src"
    cp "$src" "$dst"
    chmod 755 "$dst"
    chown "$TARGET_USER:$TARGET_USER" "$dst"
    info "Installed: $dst"
done

# =============================================================================
# KROK 7: GUI Python → ~/.local/bin/GlavaMP/
# =============================================================================
section "Installing GUI"

# Główny plik GUI
cp "$SCRIPT_DIR/scripts/glava-gui.py" "$GLAVAMP_DIR/glava-gui.py"
chmod 644 "$GLAVAMP_DIR/glava-gui.py"

# Moduły gui/
for pyfile in core.py colors.py geometry.py glava.py \
              tab_main.py tab_module.py tab_advanced.py; do
    src="$SCRIPT_DIR/scripts/gui/$pyfile"
    [ -f "$src" ] || error "Missing file: $src"
    cp "$src" "$GLAVAMP_DIR/gui/$pyfile"
done
touch "$GLAVAMP_DIR/gui/__init__.py"

# Pluginy modułów
for mod_plugin in "$SCRIPT_DIR/scripts/gui/modules/"*.py; do
    fname="$(basename "$mod_plugin")"
    [ "$fname" = "__init__.py" ] && continue
    cp "$mod_plugin" "$GLAVAMP_DIR/gui/modules/$fname"
    info "Module plugin: $fname"
done
touch "$GLAVAMP_DIR/gui/modules/__init__.py"

# Ikona
cp -r "$SCRIPT_DIR/scripts/icon/"* "$GLAVAMP_DIR/icon/"
cp "$SCRIPT_DIR/scripts/icon/glava-gui.png" \
    "$TARGET_HOME/.local/share/icons/hicolor/48x48/apps/glava-gui.png"

chown -R "$TARGET_USER:$TARGET_USER" "$GLAVAMP_DIR"
chown "$TARGET_USER:$TARGET_USER" \
    "$TARGET_HOME/.local/share/icons/hicolor/48x48/apps/glava-gui.png"

# Wrapper wykonywalny → ~/.local/bin/glava-gui
cat > "$BIN_DIR/glava-gui" << WRAPPER
#!/bin/bash
exec python3 "$GLAVAMP_DIR/glava-gui.py" "\$@"
WRAPPER
chmod 755 "$BIN_DIR/glava-gui"
chown "$TARGET_USER:$TARGET_USER" "$BIN_DIR/glava-gui"
info "Installed: GUI (GlavaMP)"

# =============================================================================
# KROK 8: Profile i pliki językowe
# =============================================================================
section "Installing presets and language files"

if [ ! -f "$GLAVAMP_CONF_DIR/presets.json" ]; then
    cp "$SCRIPT_DIR/config/default_presets.json" "$GLAVAMP_CONF_DIR/presets.json"
    chown "$TARGET_USER:$TARGET_USER" "$GLAVAMP_CONF_DIR/presets.json"
    info "Installed: default_presets.json"
else
    info "presets.json already exists — skipping."
fi
if [ ! -f "$GLAVAMP_CONF_DIR/profiles.json" ]; then
    cp "$SCRIPT_DIR/config/default_profiles.json" "$GLAVAMP_CONF_DIR/profiles.json"
    chown "$TARGET_USER:$TARGET_USER" "$GLAVAMP_CONF_DIR/profiles.json"
    info "Installed: default_profiles.json"
else
    info "profiles.json already exists — skipping."
fi

cp "$SCRIPT_DIR/lang/"*.json "$SHARE_DIR/lang/"
chown -R "$TARGET_USER:$TARGET_USER" "$SHARE_DIR/lang"
info "Installed: language files"

# =============================================================================
# KROK 9: Konfiguracja Bing
# =============================================================================
section "Bing configuration"

if [ ! -f "$BING_CONF" ]; then
    cp "$SCRIPT_DIR/config/bing-glava.conf" "$BING_CONF"
    chown "$TARGET_USER:$TARGET_USER" "$BING_CONF"
    info "Created: $BING_CONF"
else
    warn "Configuration already exists — keeping current settings."
fi

# =============================================================================
# KROK 10: Konfiguracja GLava
# =============================================================================
section "GLava configuration"

BACKUP_DIR="$GLAVA_CONFIG/backup_install"
mkdir -p "$BACKUP_DIR"
chown "$TARGET_USER:$TARGET_USER" "$BACKUP_DIR"

backup_file() {
    [ -f "$1" ] && cp "$1" "$BACKUP_DIR/$(basename "$1").bak" || true
}

# Pliki z repozytorium — zawsze instaluj (z backupem)
for f in rc.glsl smooth_parameters.glsl \
         bars.glsl circle.glsl wave.glsl radial.glsl graph.glsl; do
    src="$SCRIPT_DIR/glava-config/$f"
    dst="$GLAVA_CONFIG/$f"
    if [ -f "$src" ]; then
        backup_file "$dst"
        cp "$src" "$dst"
        chown "$TARGET_USER:$TARGET_USER" "$dst"
        info "Installed: $f"
    fi
done

# util/ — zawsze instaluj z repozytorium
rm -rf "$GLAVA_CONFIG/util"
cp -r "$SCRIPT_DIR/glava-config/util" "$GLAVA_CONFIG/util"
chown -R "$TARGET_USER:$TARGET_USER" "$GLAVA_CONFIG/util"
info "Installed: util/"

# Brakujące pliki systemowe GLava — dociągnij z /etc/xdg/glava
for f in /etc/xdg/glava/*.glsl; do
    [ -f "$f" ] || continue
    fname="$(basename "$f")"
    dst="$GLAVA_CONFIG/$fname"
    if [ ! -f "$dst" ]; then
        cp "$f" "$dst"
        chown "$TARGET_USER:$TARGET_USER" "$dst"
        info "Pulled from system: $fname"
    fi
done

# Katalogi modułów — dociągnij z /etc/xdg/glava jeśli nie istnieją
for module in bars circle wave radial graph; do
    dst_dir="$GLAVA_CONFIG/$module"
    if [ ! -d "$dst_dir" ]; then
        if [ -d "/etc/xdg/glava/$module" ]; then
            cp -r "/etc/xdg/glava/$module" "$dst_dir"
            chown -R "$TARGET_USER:$TARGET_USER" "$dst_dir"
            info "Pulled from system: $module/"
        else
            warn "Missing /etc/xdg/glava/$module — skipping."
        fi
    else
        info "Directory $module/ already exists — skipping."
    fi
done

# Szablony kolorów (*_colors.frag) — zapytaj o nadpisanie
echo -e "\nOverwrite existing color shader files (*_colors.frag)?"
echo -e "[Y]es (recommended) / [n]o / [a]sk for each"
read -rp "Choice: " OVERWRITE_CHOICE
OVERWRITE_CHOICE="${OVERWRITE_CHOICE:-Y}"

for module in bars circle wave radial graph; do
    src="$SCRIPT_DIR/config/${module}_colors.frag"
    dst="$GLAVA_CONFIG/${module}_colors.frag"
    [ -f "$src" ] || { warn "Missing in repo: ${module}_colors.frag — skipping."; continue; }

    COPY_FILE=true
    if [ -f "$dst" ]; then
        case "$OVERWRITE_CHOICE" in
            [Nn]) COPY_FILE=false ;;
            [Aa])
                echo -e "${module}_colors.frag already exists. Overwrite? [y/N]"
                read -rp "" ans
                [[ "$ans" =~ ^[Yy]$ ]] && COPY_FILE=true || COPY_FILE=false
                ;;
        esac
    fi

    if [ "$COPY_FILE" = true ]; then
        backup_file "$dst"
        cp "$src" "$dst"
        chown "$TARGET_USER:$TARGET_USER" "$dst"
        info "Installed: ${module}_colors.frag"
    else
        warn "Skipped: ${module}_colors.frag"
    fi
done

chown -R "$TARGET_USER:$TARGET_USER" "$BACKUP_DIR"

# Domyślny aktywny moduł
if [ ! -f "$ACTIVE_MODULE_FILE" ]; then
    echo "bars" > "$ACTIVE_MODULE_FILE"
    chown "$TARGET_USER:$TARGET_USER" "$ACTIVE_MODULE_FILE"
    info "Default module set: bars"
fi

# =============================================================================
# KROK 11: Auto-konfiguracja geometrii GLava
# =============================================================================
section "Auto-configuring GLava geometry"

SCREEN_W=1600; SCREEN_H=900; WORK_H=860  # fallback

if command -v xprop &>/dev/null; then
    XAUTH_FILE="${XAUTHORITY:-}"
    if [ -z "$XAUTH_FILE" ] || [ ! -f "$XAUTH_FILE" ]; then
        XAUTH_FILE="$(getent passwd "$SUDO_USER" | cut -d: -f6)/.Xauthority"
    fi
    XPROP_OUT=$(sudo -u "$TARGET_USER" \
        DISPLAY="${DISPLAY:-:0}" \
        XAUTHORITY="$XAUTH_FILE" \
        xprop -root _NET_WORKAREA _NET_DESKTOP_GEOMETRY 2>/dev/null || true)

    DG=$(echo "$XPROP_OUT" | grep "_NET_DESKTOP_GEOMETRY" | grep -o '[0-9]*' | tr '\n' ' ')
    WA=$(echo "$XPROP_OUT" | grep "_NET_WORKAREA"         | grep -o '[0-9]*' | tr '\n' ' ')

    DG_W=$(echo "$DG" | awk '{print $1}')
    DG_H=$(echo "$DG" | awk '{print $2}')
    WA_H=$(echo "$WA" | awk '{print $4}')

    if [ -n "$DG_W" ] && [ -n "$DG_H" ] && [ -n "$WA_H" ]; then
        SCREEN_W=$DG_W
        SCREEN_H=$DG_H
        WORK_H=$WA_H
        info "Detected: ${SCREEN_W}×${SCREEN_H}, work area: ${WORK_H}px"
    else
        warn "Could not detect geometry via xprop — using fallback ${SCREEN_W}×${SCREEN_H}."
    fi
else
    warn "xprop unavailable — using fallback ${SCREEN_W}×${SCREEN_H}."
fi

PANEL_H=$((SCREEN_H - WORK_H))
info "Detected panel height: ${PANEL_H}px"

set_glava_geometry() {
    local x=$1 y=$2 w=$3 h=$4
    local rc="$GLAVA_CONFIG/rc.glsl"
    if [ -f "$rc" ]; then
        sed -i "s/#request setgeometry [0-9-]* [0-9-]* [0-9-]* [0-9-]*/#request setgeometry $x $y $w $h/" "$rc"
        info "GLava geometry: X=$x Y=$y W=$w H=$h"
    fi
}

ACTIVE_MOD="bars"
[ -f "$ACTIVE_MODULE_FILE" ] && ACTIVE_MOD=$(cat "$ACTIVE_MODULE_FILE")

case "$ACTIVE_MOD" in
    graph|bars)
        set_glava_geometry 0 "-$PANEL_H" "$SCREEN_W" "$SCREEN_H"
        ;;
    circle|radial|wave)
        set_glava_geometry 0 0 "$SCREEN_W" "$SCREEN_H"
        ;;
    *)
        set_glava_geometry 0 "-$PANEL_H" "$SCREEN_W" "$SCREEN_H"
        ;;
esac

# =============================================================================
# KROK 12: Skróty w menu aplikacji
# =============================================================================
section "Application menu shortcuts"

DESKTOP_DST="$TARGET_HOME/.local/share/applications"
for f in "$SCRIPT_DIR/desktop"/*.desktop; do
    [ -f "$f" ] || continue
    cp "$f" "$DESKTOP_DST/"
    chown "$TARGET_USER:$TARGET_USER" "$DESKTOP_DST/$(basename "$f")"
    info "Installed: $(basename "$f")"
done
sudo -u "$TARGET_USER" update-desktop-database "$DESKTOP_DST" 2>/dev/null || true

# =============================================================================
# KROK 13: Autostart GLava
# =============================================================================
section "GLava autostart"

if [ "$GLAVA_INSTALLED" = true ]; then
    cat > "$TARGET_HOME/.config/autostart/glava.desktop" << AUTOSTART
[Desktop Entry]
Version=1.0
Type=Application
Name=GLava
Comment=OpenGL audio visualizer
Exec=glava --desktop
Icon=multimedia-audio-player
Terminal=false
Categories=AudioVideo;
X-GNOME-Autostart-enabled=true
StartupNotify=false
AUTOSTART
    chown "$TARGET_USER:$TARGET_USER" "$TARGET_HOME/.config/autostart/glava.desktop"
    info "Added GLava autostart."
else
    warn "GLava not installed — skipping autostart."
fi

# =============================================================================
# KROK 14: Usługa systemd
# =============================================================================
section "Color daemon (systemd service)"

cp "$SCRIPT_DIR/systemd/glava-color-daemon.service" "$SYSTEMD_DIR/glava-color-daemon.service"
chown -R "$TARGET_USER:$TARGET_USER" "$SYSTEMD_DIR"

loginctl show-user "$TARGET_USER" 2>/dev/null | grep -q "Linger=yes" || \
    loginctl enable-linger "$TARGET_USER"

if [ -d "/run/user/$TARGET_UID" ]; then
    sudo -u "$TARGET_USER" \
        XDG_RUNTIME_DIR="/run/user/$TARGET_UID" \
        DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$TARGET_UID/bus" \
        systemctl --user daemon-reload
    sudo -u "$TARGET_USER" \
        XDG_RUNTIME_DIR="/run/user/$TARGET_UID" \
        DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$TARGET_UID/bus" \
        systemctl --user enable glava-color-daemon.service
    info "Service configured and enabled."
else
    warn "No active session — service will start on next login."
fi

# =============================================================================
# KROK 15: Cron
# =============================================================================
section "Wallpaper download schedule"

CRON_LINE="$CRON_SCHEDULE /usr/local/bin/bing-downloader.sh $TARGET_USER >> $LOG_DIR/bing-downloader.log 2>&1"
CRON_MARKER="# bing-glava-suite:$TARGET_USER"
EXISTING=$(crontab -l 2>/dev/null || true)

if echo "$EXISTING" | grep -q "bing-downloader.sh $TARGET_USER"; then
    NEW_CRON=$(echo "$EXISTING" \
        | grep -v "bing-downloader.sh $TARGET_USER" \
        | grep -v "# bing-glava-suite:$TARGET_USER")
    (echo "$NEW_CRON"; echo "$CRON_MARKER"; echo "$CRON_LINE") | crontab -
    info "Updated wallpaper download schedule."
else
    (echo "$EXISTING"; echo "$CRON_MARKER"; echo "$CRON_LINE") | crontab -
    info "Added schedule: every $INPUT_CRON minutes."
fi

# =============================================================================
# KROK 16: Pierwsze pobranie tapety
# =============================================================================
section "First wallpaper download"

echo -e "Download today's Bing wallpaper now? [Y/n]"
read -rp "" RUN_NOW
RUN_NOW="${RUN_NOW:-Y}"
if [[ "$RUN_NOW" =~ ^[Yy]$ ]]; then
    /usr/local/bin/bing-downloader.sh "$TARGET_USER" && \
        info "Wallpaper downloaded successfully." || \
        warn "Failed to download wallpaper — try again later."
fi

# =============================================================================
# PODSUMOWANIE
# =============================================================================
section "Installation complete"
echo ""
echo -e "  GUI:                 ${BLD}glava-gui${RST}"
echo -e "  GUI modules:         ${BLD}$GLAVAMP_DIR/${RST}"
echo -e "  Bing configuration:  ${BLD}$BING_CONF${RST}"
echo -e "  Wallpapers:          ${BLD}$TARGET_HOME/Pictures/Bing/${RST}"
echo -e "  Logs:                ${BLD}$LOG_DIR/${RST}"
echo ""
warn "To start the service without logging out:"
echo -e "  ${BLD}systemctl --user start glava-color-daemon${RST}"
echo ""
info "Done! Log out and log back in to start everything automatically."
