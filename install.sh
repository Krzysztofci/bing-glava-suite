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
SHARE_DIR="$TARGET_HOME/.local/share/bing-glava-suite"
CONFIG_DIR="$TARGET_HOME/.config/systemd/user"
LOG_DIR="$TARGET_HOME/.local/logs"
GLAVA_CONFIG="$TARGET_HOME/.config/glava"
BING_CONFIG_DIR="$TARGET_HOME/.config/bing-glava"

info "Instalacja dla użytkownika: $TARGET_USER ($TARGET_HOME)"

# =============================================================================
# KROK 2: Interwał crona
# =============================================================================
section "Konfiguracja crona"

echo -e "Co ile minut pobierać tapetę Bing? (domyślnie: ${BLD}15${RST}, dla 1h wpisz 60)"
read -rp "Interwał [minuty]: " INPUT_CRON
INPUT_CRON="${INPUT_CRON:-15}"

if ! [[ "$INPUT_CRON" =~ ^[0-9]+$ ]] || [ "$INPUT_CRON" -lt 1 ] || [ "$INPUT_CRON" -gt 1440 ]; then
    warn "Nieprawidłowa wartość — ustawiam domyślne 15 minut."
    INPUT_CRON=15
fi

if [ "$INPUT_CRON" -eq 60 ]; then
    CRON_SCHEDULE="0 * * * *"
else
    CRON_SCHEDULE="*/$INPUT_CRON * * * *"
fi
info "Interwał crona: $CRON_SCHEDULE ($INPUT_CRON minut)"

# =============================================================================
# KROK 3: Zależności systemowe
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

GLAVA_INSTALLED=false
if ! command -v glava &>/dev/null; then
    warn "GLava nie została znaleziona w PATH."
    echo -e "Pobrać i zainstalować GLava automatycznie? [T/n]"
    read -rp "" INSTALL_GLAVA
    INSTALL_GLAVA="${INSTALL_GLAVA:-T}"
    if [[ "$INSTALL_GLAVA" =~ ^[Tt]$ ]]; then
        info "Pobieram paczkę GLava z GitHub Releases..."
        GLAVA_URL=$(curl -s https://api.github.com/repos/Krzysztofci/bing-glava-suite/releases/latest \
            | jq -r '.assets[] | select(.name | endswith(".deb")) | .browser_download_url')
        if [ -z "$GLAVA_URL" ]; then
            warn "Nie udało się pobrać URL paczki GLava. Zainstaluj ręcznie."
        else
            GLAVA_DEB="/tmp/glava_latest.deb"
            wget -q --show-progress -O "$GLAVA_DEB" "$GLAVA_URL"
            dpkg -i "$GLAVA_DEB" || apt-get install -f -y
            rm -f "$GLAVA_DEB"
            info "GLava zainstalowana."
            GLAVA_INSTALLED=true
        fi
    else
        warn "Kontynuuję bez GLava — demon nie będzie działał."
    fi
else
    GLAVA_INSTALLED=true
fi

# =============================================================================
# KROK 4: Katalogi
# =============================================================================
section "Tworzenie katalogów"

mkdir -p "$BIN_DIR" "$CONFIG_DIR" "$LOG_DIR" \
         "$TARGET_HOME/Pictures/Bing" \
         "$SHARE_DIR/lang" \
         "$BING_CONFIG_DIR" \
         "/usr/share/backgrounds/linuxmint"

chown -R "$TARGET_USER:$TARGET_USER" \
    "$TARGET_HOME/.config/systemd" \
    "$BIN_DIR" "$LOG_DIR" \
    "$TARGET_HOME/Pictures/Bing" \
    "$SHARE_DIR" \
    "$BING_CONFIG_DIR"

info "Katalogi gotowe."

# =============================================================================
# KROK 5: Systemowy skrypt bing-downloader.sh → /usr/local/bin/
# =============================================================================
section "Instalacja systemowego skryptu pobierania tapet"

DOWNLOADER_SRC="$SCRIPT_DIR/scripts/bing-downloader.sh"
DOWNLOADER_DST="/usr/local/bin/bing-downloader.sh"

cp "$DOWNLOADER_SRC" "$DOWNLOADER_DST"
chmod 755 "$DOWNLOADER_DST"
chown root:root "$DOWNLOADER_DST"
info "Zainstalowano: $DOWNLOADER_DST (właściciel: root)"

# =============================================================================
# KROK 6: Skrypty użytkownika → ~/.local/bin/
# =============================================================================
section "Instalacja skryptów użytkownika"

USER_SCRIPTS=(
    glava-colorswitch
    glava-toggle
    glava-colors-auto
    glava-color-daemon
    bing-fetch-user.sh
)

for script in "${USER_SCRIPTS[@]}"; do
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

# =============================================================================
# KROK 7: GUI (Python)
# =============================================================================
section "Instalacja GUI"

cp "$SCRIPT_DIR/scripts/glava-gui.py" "$BIN_DIR/glava-gui.py"
chmod 755 "$BIN_DIR/glava-gui.py"
chown "$TARGET_USER:$TARGET_USER" "$BIN_DIR/glava-gui.py"

cat > "$BIN_DIR/glava-gui" <<WRAPPER
#!/bin/bash
exec python3 "$BIN_DIR/glava-gui.py" "\$@"
WRAPPER
chmod 755 "$BIN_DIR/glava-gui"
chown "$TARGET_USER:$TARGET_USER" "$BIN_DIR/glava-gui"
info "Zainstalowano GUI (wrapper: glava-gui)"

# Pliki językowe
if [ -d "$SCRIPT_DIR/lang" ]; then
    cp "$SCRIPT_DIR/lang/"*.json "$SHARE_DIR/lang/"
    chown -R "$TARGET_USER:$TARGET_USER" "$SHARE_DIR/lang"
    info "Zainstalowano pliki językowe."
fi

# =============================================================================
# KROK 8: Plik konfiguracyjny użytkownika
# =============================================================================
section "Konfiguracja użytkownika (region Bing)"

BING_CONF="$BING_CONFIG_DIR/config"
if [ ! -f "$BING_CONF" ]; then
    cp "$SCRIPT_DIR/config/bing-glava.conf" "$BING_CONF"
    chown "$TARGET_USER:$TARGET_USER" "$BING_CONF"
    info "Utworzono plik konfiguracyjny: $BING_CONF"
else
    warn "Plik konfiguracyjny już istnieje — pomijam (zachowuję ustawienia)."
fi

# =============================================================================
# KROK 9: Konfiguracja GLava
# =============================================================================
section "Konfiguracja GLava"

mkdir -p "$GLAVA_CONFIG/graph" "$GLAVA_CONFIG/util"
chown -R "$TARGET_USER:$TARGET_USER" "$GLAVA_CONFIG"

BACKUP_DIR="$GLAVA_CONFIG/backup_install"
mkdir -p "$BACKUP_DIR"

backup_file() {
    local src="$1"
    local bdir="$2"
    if [ -f "$src" ]; then
        cp "$src" "$bdir/$(basename "$src").bak"
    fi
}

# graph_red.frag
backup_file "$GLAVA_CONFIG/graph_red.frag" "$BACKUP_DIR"
cp "$SCRIPT_DIR/config/graph_red.frag" "$GLAVA_CONFIG/graph_red.frag"
chown "$TARGET_USER:$TARGET_USER" "$GLAVA_CONFIG/graph_red.frag"
info "Zainstalowano graph_red.frag"

# rc.glsl
if [ -f "$SCRIPT_DIR/glava-config/rc.glsl" ]; then
    backup_file "$GLAVA_CONFIG/rc.glsl" "$BACKUP_DIR"
    cp "$SCRIPT_DIR/glava-config/rc.glsl" "$GLAVA_CONFIG/rc.glsl"
    chown "$TARGET_USER:$TARGET_USER" "$GLAVA_CONFIG/rc.glsl"
    info "Zainstalowano rc.glsl"
fi

# graph.glsl i graph/1.frag
if [ -f "$SCRIPT_DIR/glava-config/graph.glsl" ]; then
    backup_file "$GLAVA_CONFIG/graph.glsl" "$BACKUP_DIR"
    backup_file "$GLAVA_CONFIG/graph/1.frag" "$BACKUP_DIR"
    cp "$SCRIPT_DIR/glava-config/graph.glsl" "$GLAVA_CONFIG/graph.glsl"
    cp "$SCRIPT_DIR/glava-config/graph/1.frag" "$GLAVA_CONFIG/graph/1.frag"
    chown -R "$TARGET_USER:$TARGET_USER" "$GLAVA_CONFIG/graph"
    chown "$TARGET_USER:$TARGET_USER" "$GLAVA_CONFIG/graph.glsl"
    info "Zainstalowano konfigurację modułu graph."
fi

# util/
if [ -d "$SCRIPT_DIR/glava-config/util" ]; then
    mkdir -p "$GLAVA_CONFIG/util"
    cp -r "$SCRIPT_DIR/glava-config/util/." "$GLAVA_CONFIG/util/"
    chown -R "$TARGET_USER:$TARGET_USER" "$GLAVA_CONFIG/util"
    info "Zainstalowano katalog util."
fi

# smooth_parameters.glsl
if [ -f "$SCRIPT_DIR/glava-config/smooth_parameters.glsl" ]; then
    cp "$SCRIPT_DIR/glava-config/smooth_parameters.glsl" "$GLAVA_CONFIG/smooth_parameters.glsl"
    chown "$TARGET_USER:$TARGET_USER" "$GLAVA_CONFIG/smooth_parameters.glsl"
    info "Zainstalowano smooth_parameters.glsl"
fi

chown -R "$TARGET_USER:$TARGET_USER" "$BACKUP_DIR"

# =============================================================================
# KROK 9b: Pliki .desktop (menu aplikacji)
# =============================================================================
section "Instalacja skrótów w menu"

DESKTOP_SRC="$SCRIPT_DIR/desktop"
DESKTOP_DST="$TARGET_HOME/.local/share/applications"

mkdir -p "$DESKTOP_DST"
chown "$TARGET_USER:$TARGET_USER" "$DESKTOP_DST"

if [ -d "$DESKTOP_SRC" ]; then
    for f in "$DESKTOP_SRC"/*.desktop "$DESKTOP_SRC"/*.directory; do
        [ -f "$f" ] || continue
        cp "$f" "$DESKTOP_DST/"
        chown "$TARGET_USER:$TARGET_USER" "$DESKTOP_DST/$(basename "$f")"
        info "Zainstalowano: $(basename "$f")"
    done
    sudo -u "$TARGET_USER" update-desktop-database "$DESKTOP_DST" 2>/dev/null || true
else
    warn "Brak katalogu desktop/ — pomijam."
fi

# =============================================================================
# KROK 9c: Autostart GLava
# =============================================================================
section "Konfiguracja autostartu GLava"

AUTOSTART_DIR="$TARGET_HOME/.config/autostart"
mkdir -p "$AUTOSTART_DIR"
chown "$TARGET_USER:$TARGET_USER" "$AUTOSTART_DIR"

if [ "$GLAVA_INSTALLED" = true ]; then
    cat > "$AUTOSTART_DIR/glava.desktop" << AUTOSTART
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
    chown "$TARGET_USER:$TARGET_USER" "$AUTOSTART_DIR/glava.desktop"
    info "Dodano autostart GLava: $AUTOSTART_DIR/glava.desktop"
else
    warn "GLava nie jest zainstalowana — pomijam autostart."
fi

# =============================================================================
# KROK 10: Usługa systemd użytkownika
# =============================================================================
section "Konfiguracja usługi systemd"

SERVICE_SRC="$SCRIPT_DIR/systemd/glava-color-daemon.service"
SERVICE_DST="$CONFIG_DIR/glava-color-daemon.service"

cp "$SERVICE_SRC" "$SERVICE_DST"
chown "$TARGET_USER:$TARGET_USER" "$SERVICE_DST"

sudo -u "$TARGET_USER" mkdir -p "$CONFIG_DIR/default.target.wants"
chown "$TARGET_USER:$TARGET_USER" "$CONFIG_DIR/default.target.wants"

sudo -u "$TARGET_USER" \
    XDG_RUNTIME_DIR="/run/user/$TARGET_UID" \
    DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$TARGET_UID/bus" \
    systemctl --user daemon-reload

sudo -u "$TARGET_USER" \
    XDG_RUNTIME_DIR="/run/user/$TARGET_UID" \
    DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$TARGET_UID/bus" \
    systemctl --user enable glava-color-daemon.service

info "Usługa systemd skonfigurowana i włączona."
warn "Aby uruchomić teraz: systemctl --user start glava-color-daemon"

# =============================================================================
# KROK 11: Cron (root)
# =============================================================================
section "Konfiguracja cron (root)"

CRON_LINE="$CRON_SCHEDULE /usr/local/bin/bing-downloader.sh $TARGET_USER >> $LOG_DIR/bing-downloader.log 2>&1"
CRON_MARKER="# bing-glava-suite:$TARGET_USER"

EXISTING=$(crontab -l 2>/dev/null || true)
if echo "$EXISTING" | grep -q "bing-downloader.sh $TARGET_USER"; then
    # Zaktualizuj istniejący wpis
    NEW_CRONTAB=$(echo "$EXISTING" | grep -v "bing-downloader.sh $TARGET_USER" | grep -v "# bing-glava-suite:$TARGET_USER")
    (echo "$NEW_CRONTAB"; echo "$CRON_MARKER"; echo "$CRON_LINE") | crontab -
    info "Zaktualizowano wpis cron dla użytkownika $TARGET_USER."
else
    (echo "$EXISTING"; echo "$CRON_MARKER"; echo "$CRON_LINE") | crontab -
    info "Dodano wpis cron: $CRON_SCHEDULE dla $TARGET_USER."
fi

# =============================================================================
# KROK 12: Pierwsze pobranie tapety
# =============================================================================
section "Pierwsze pobranie tapety"

echo -e "Pobrać tapetę Bing teraz? [T/n]"
read -rp "" RUN_NOW
RUN_NOW="${RUN_NOW:-T}"

if [[ "$RUN_NOW" =~ ^[Tt]$ ]]; then
    info "Uruchamiam bing-downloader.sh..."
    /usr/local/bin/bing-downloader.sh "$TARGET_USER" && \
        info "Tapeta pobrana." || \
        warn "Pobieranie nie powiodło się. Spróbuj ręcznie później."
fi

# =============================================================================
# PODSUMOWANIE
# =============================================================================
section "Instalacja zakończona"

echo ""
echo -e "  Skrypty użytkownika: ${BLD}$BIN_DIR/${RST}"
echo -e "  Skrypt systemowy:    ${BLD}/usr/local/bin/bing-downloader.sh${RST}"
echo -e "  Konfiguracja Bing:   ${BLD}$BING_CONF${RST}"
echo -e "  Logi:                ${BLD}$LOG_DIR/${RST}"
echo -e "  Tapety Bing:         ${BLD}$TARGET_HOME/Pictures/Bing/${RST}"
echo -e "  Usługa systemd:      ${BLD}glava-color-daemon.service${RST}"
echo -e "  GUI:                 ${BLD}glava-gui${RST}"
echo ""
warn "Po instalacji GLava uruchom: glava --copy-config"
warn "Następnie uruchom usługę:   systemctl --user start glava-color-daemon"
echo ""
info "Gotowe! Wyloguj się i zaloguj ponownie, aby usługa systemd wystartowała."
