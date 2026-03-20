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
CONFIG_DIR="$TARGET_HOME/.config/systemd/user"
LOG_DIR="$TARGET_HOME/.local/logs"

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
# KROK 5b: Szablon shadera GLava (graph_red.frag)
# =============================================================================
section "Konfiguracja szablonu GLava"

GLAVA_CONFIG="$TARGET_HOME/.config/glava"
SHADER_SRC="$SCRIPT_DIR/config/graph_red.frag"
SHADER_DST="$GLAVA_CONFIG/graph_red.frag"

mkdir -p "$GLAVA_CONFIG"
chown "$TARGET_USER:$TARGET_USER" "$GLAVA_CONFIG"

if [ -f "$SHADER_SRC" ]; then
    if [ -f "$SHADER_DST" ]; then
        warn "Plik $SHADER_DST już istnieje — pomijam (nie nadpisuję)."
    else
        cp "$SHADER_SRC" "$SHADER_DST"
        chown "$TARGET_USER:$TARGET_USER" "$SHADER_DST"
        info "Zainstalowano szablon shadera: $SHADER_DST"
    fi
else
    warn "Brak pliku config/graph_red.frag — skopiuj go ręcznie do ~/.config/glava/"
fi

# =============================================================================
# KROK 5c: Konfiguracja modułu GLava (rc.glsl, graph.glsl, graph/1.frag)
# =============================================================================
section "Konfiguracja modułu GLava"

GLAVA_CONFIG_SRC="$SCRIPT_DIR/glava-config"

if [ -d "$GLAVA_CONFIG_SRC" ]; then
    # rc.glsl — tylko jeśli nie istnieje (nie nadpisujemy istniejącej konfiguracji)
    if [ ! -f "$GLAVA_CONFIG/rc.glsl" ]; then
        cp "$GLAVA_CONFIG_SRC/rc.glsl" "$GLAVA_CONFIG/rc.glsl"
        chown "$TARGET_USER:$TARGET_USER" "$GLAVA_CONFIG/rc.glsl"
        info "Zainstalowano rc.glsl"
    else
        warn "Plik rc.glsl już istnieje — pomijam."
    fi
    # graph.glsl i graph/1.frag — szablon aktywnego shadera
    mkdir -p "$GLAVA_CONFIG/graph"
    cp "$GLAVA_CONFIG_SRC/graph.glsl" "$GLAVA_CONFIG/graph.glsl"
    cp "$GLAVA_CONFIG_SRC/graph/1.frag" "$GLAVA_CONFIG/graph/1.frag"
    chown -R "$TARGET_USER:$TARGET_USER" "$GLAVA_CONFIG/graph"
    chown "$TARGET_USER:$TARGET_USER" "$GLAVA_CONFIG/graph.glsl"
    info "Zainstalowano konfigurację modułu graph."
else
    warn "Brak katalogu glava-config — pomijam konfigurację GLava."
fi

# =============================================================================
# KROK 6: Usługa systemd użytkownika
# =============================================================================
section "Konfiguracja usługi systemd"

SERVICE_SRC="$SCRIPT_DIR/systemd/glava-color-daemon.service"
SERVICE_DST="$CONFIG_DIR/glava-color-daemon.service"

cp "$SERVICE_SRC" "$SERVICE_DST"
chown "$TARGET_USER:$TARGET_USER" "$SERVICE_DST"

# Utwórz katalog wants jeśli nie istnieje
sudo -u "$TARGET_USER" mkdir -p "$CONFIG_DIR/default.target.wants"

sudo -u "$TARGET_USER" \
    XDG_RUNTIME_DIR="/run/user/$TARGET_UID" \
    DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$TARGET_UID/bus" \
    systemctl --user daemon-reload

sudo -u "$TARGET_USER" \
    XDG_RUNTIME_DIR="/run/user/$TARGET_UID" \
    DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$TARGET_UID/bus" \
    systemctl --user enable glava-color-daemon.service

info "Usługa systemd skonfigurowana i włączona (uruchomi się przy następnym logowaniu)."
warn "Aby uruchomić teraz: sudo -u $TARGET_USER systemctl --user start glava-color-daemon"

# =============================================================================
# KROK 7: Cron dla bing-downloader (root)
# =============================================================================
section "Konfiguracja cron (root)"

CRON_LINE="0 * * * * $BIN_DIR/bing-downloader.sh >> $LOG_DIR/bing-downloader.log 2>&1"
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
echo ""
warn "WAŻNE: Po instalacji uruchom GLava: glava --copy-config"
warn "       Następnie uruchom usługę:   systemctl --user start glava-color-daemon"
echo ""
info "Gotowe! Wyloguj się i zaloguj ponownie, aby usługa systemd wystartowała."
