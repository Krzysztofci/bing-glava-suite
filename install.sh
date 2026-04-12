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
section "Sprawdzanie środowiska"

if [ "$EUID" -ne 0 ]; then
    echo -e "${YEL}"
    echo "  Ten instalator wymaga uprawnień administratora (sudo)."
    echo "  Jest to potrzebne wyłącznie do:"
    echo "    • ustawienia tapety na ekranie logowania LightDM"
    echo "    • instalacji systemowego skryptu pobierania tapet"
    echo ""
    echo "  Uruchom ponownie jako:"
    echo -e "  ${BLD}sudo ./install.sh${RST}"
    echo -e "${RST}"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# =============================================================================
# KROK 1: Użytkownik docelowy
# =============================================================================
section "Konfiguracja użytkownika"

echo -e "Dla jakiego użytkownika instalować? (Enter = bieżący: ${BLD}$SUDO_USER${RST})"
read -rp "Nazwa użytkownika: " INPUT_USER
TARGET_USER="${INPUT_USER:-$SUDO_USER}"

if [ -z "$TARGET_USER" ]; then
    error "Nie można ustalić nazwy użytkownika. Uruchom przez: sudo ./install.sh"
fi
if ! id "$TARGET_USER" &>/dev/null; then
    error "Użytkownik '$TARGET_USER' nie istnieje."
fi

TARGET_HOME=$(getent passwd "$TARGET_USER" | cut -d: -f6)
TARGET_UID=$(id -u "$TARGET_USER")

# Ścieżki instalacji
BIN_DIR="$TARGET_HOME/.local/bin"
GLAVAMP_DIR="$TARGET_HOME/.local/bin/GlavaMP"
SHARE_DIR="$TARGET_HOME/.local/share/bing-glava-suite"
SYSTEMD_DIR="$TARGET_HOME/.config/systemd/user"
LOG_DIR="$TARGET_HOME/.local/logs"
GLAVA_CONFIG="$TARGET_HOME/.config/glava"
BING_CONFIG_DIR="$TARGET_HOME/.config/bing-glava"

info "Instalacja dla użytkownika: $TARGET_USER ($TARGET_HOME)"

# =============================================================================
# KROK 2: Interwał crona
# =============================================================================
section "Konfiguracja crona"

echo -e "Co ile minut pobierać tapetę Bing? (Enter = ${BLD}15${RST}, dla godziny wpisz 60)"
read -rp "Interwał [minuty]: " INPUT_CRON
INPUT_CRON="${INPUT_CRON:-15}"

if ! [[ "$INPUT_CRON" =~ ^[0-9]+$ ]] || [ "$INPUT_CRON" -lt 1 ] || [ "$INPUT_CRON" -gt 1440 ]; then
    warn "Nieprawidłowa wartość — ustawiam 15 minut."
    INPUT_CRON=15
fi

if [ "$INPUT_CRON" -eq 60 ]; then
    CRON_SCHEDULE="0 * * * *"
else
    CRON_SCHEDULE="*/$INPUT_CRON * * * *"
fi
info "Interwał crona: co $INPUT_CRON minut"

# =============================================================================
# KROK 3: Zależności
# =============================================================================
section "Instalacja zależności"

APT_PACKAGES=(curl wget jq inotify-tools python3 python3-pil
              python3-sklearn python3-numpy python3-tk)
MISSING=()
for pkg in "${APT_PACKAGES[@]}"; do
    dpkg -s "$pkg" &>/dev/null || MISSING+=("$pkg")
done

if [ ${#MISSING[@]} -gt 0 ]; then
    info "Instaluję brakujące pakiety: ${MISSING[*]}"
    apt-get update -qq
    apt-get install -y "${MISSING[@]}"
else
    info "Wszystkie wymagane pakiety są zainstalowane."
fi

# GLava
GLAVA_INSTALLED=false
if command -v glava &>/dev/null; then
    GLAVA_INSTALLED=true
    info "GLava jest zainstalowana."
else
    warn "GLava nie została znaleziona."
    echo -e "Pobrać i zainstalować GLava automatycznie? [T/n]"
    read -rp "" INSTALL_GLAVA
    INSTALL_GLAVA="${INSTALL_GLAVA:-T}"
    if [[ "$INSTALL_GLAVA" =~ ^[Tt]$ ]]; then
        info "Pobieram GLava z GitHub Releases..."
        GLAVA_URL=$(curl -s https://api.github.com/repos/Krzysztofci/bing-glava-suite/releases/latest \
            | jq -r '.assets[] | select(.name | endswith(".deb")) | .browser_download_url')
        if [ -z "$GLAVA_URL" ]; then
            warn "Nie udało się pobrać URL paczki GLava. Zainstaluj ręcznie."
        else
            GLAVA_DEB="/tmp/glava_latest.deb"
            wget -q --show-progress -O "$GLAVA_DEB" "$GLAVA_URL"
            dpkg -i "$GLAVA_DEB" || apt-get install -f -y
            rm -f "$GLAVA_DEB"
            GLAVA_INSTALLED=true
            info "GLava zainstalowana."
        fi
    else
        warn "Kontynuuję bez GLava — wizualizator nie będzie działał."
    fi
fi

# =============================================================================
# KROK 4: Katalogi
# =============================================================================
section "Tworzenie katalogów"

mkdir -p \
    "$BIN_DIR" \
    "$GLAVAMP_DIR/gui/modules" \
    "$GLAVAMP_DIR/icon" \
    "$SHARE_DIR/lang" \
    "$SYSTEMD_DIR" \
    "$LOG_DIR" \
    "$TARGET_HOME/Pictures/Bing" \
    "$BING_CONFIG_DIR" \
    "$GLAVA_CONFIG/graph" \
    "$GLAVA_CONFIG/util" \
    "/usr/share/backgrounds/linuxmint"

chown -R "$TARGET_USER:$TARGET_USER" \
    "$BIN_DIR" \
    "$SHARE_DIR" \
    "$LOG_DIR" \
    "$TARGET_HOME/Pictures/Bing" \
    "$BING_CONFIG_DIR" \
    "$GLAVA_CONFIG"

info "Katalogi gotowe."

# =============================================================================
# KROK 5: Systemowy skrypt pobierania tapet
# =============================================================================
section "Instalacja skryptu pobierania tapet"

cp "$SCRIPT_DIR/scripts/bing-downloader.sh" /usr/local/bin/bing-downloader.sh
chmod 755 /usr/local/bin/bing-downloader.sh
chown root:root /usr/local/bin/bing-downloader.sh
info "Zainstalowano: /usr/local/bin/bing-downloader.sh"

# =============================================================================
# KROK 6: Skrypty użytkownika → ~/.local/bin/
# =============================================================================
section "Instalacja skryptów użytkownika"

for script in glava-colorswitch glava-toggle glava-colors-auto \
              glava-color-daemon bing-fetch-user.sh; do
    src="$SCRIPT_DIR/scripts/$script"
    dst="$BIN_DIR/$script"
    [ -f "$src" ] || error "Brak pliku: $src"
    cp "$src" "$dst"
    chmod 755 "$dst"
    chown "$TARGET_USER:$TARGET_USER" "$dst"
    info "Zainstalowano: $dst"
done

# =============================================================================
# KROK 7: GUI Python → ~/.local/bin/GlavaMP/
# =============================================================================
section "Instalacja GUI"

# Główny plik GUI
cp "$SCRIPT_DIR/scripts/glava-gui.py" "$GLAVAMP_DIR/glava-gui.py"
chmod 644 "$GLAVAMP_DIR/glava-gui.py"

# Moduły gui/
cp "$SCRIPT_DIR/scripts/gui/core.py"         "$GLAVAMP_DIR/gui/core.py"
cp "$SCRIPT_DIR/scripts/gui/colors.py"       "$GLAVAMP_DIR/gui/colors.py"
cp "$SCRIPT_DIR/scripts/gui/geometry.py"     "$GLAVAMP_DIR/gui/geometry.py"
cp "$SCRIPT_DIR/scripts/gui/glava.py"        "$GLAVAMP_DIR/gui/glava.py"
cp "$SCRIPT_DIR/scripts/gui/tab_main.py"     "$GLAVAMP_DIR/gui/tab_main.py"
cp "$SCRIPT_DIR/scripts/gui/tab_module.py"   "$GLAVAMP_DIR/gui/tab_module.py"
cp "$SCRIPT_DIR/scripts/gui/tab_advanced.py" "$GLAVAMP_DIR/gui/tab_advanced.py"

# Pliki __init__.py
touch "$GLAVAMP_DIR/gui/__init__.py"
touch "$GLAVAMP_DIR/gui/modules/__init__.py"

# Pluginy modułów
for mod_plugin in "$SCRIPT_DIR/scripts/gui/modules/"*.py; do
    fname="$(basename "$mod_plugin")"
    [ "$fname" = "__init__.py" ] && continue
    cp "$mod_plugin" "$GLAVAMP_DIR/gui/modules/$fname"
    info "Plugin modułu: $fname"
done

# Ikona
cp -r "$SCRIPT_DIR/scripts/icon/"* "$GLAVAMP_DIR/icon/"

# Ikona systemowa
mkdir -p "$TARGET_HOME/.local/share/icons/hicolor/48x48/apps"
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
info "Zainstalowano GUI (GlavaMP)"
info "Uruchamianie: glava-gui"

# =============================================================================
# KROK 8: Pliki językowe
# =============================================================================
section "Instalacja plików językowych"

if [ -d "$SCRIPT_DIR/lang" ]; then
    cp "$SCRIPT_DIR/lang/"*.json "$SHARE_DIR/lang/"
    chown -R "$TARGET_USER:$TARGET_USER" "$SHARE_DIR/lang"
    info "Zainstalowano pliki językowe."
fi

# =============================================================================
# KROK 9: Konfiguracja Bing
# =============================================================================
section "Konfiguracja Bing"

BING_CONF="$BING_CONFIG_DIR/config"
if [ ! -f "$BING_CONF" ]; then
    cp "$SCRIPT_DIR/config/bing-glava.conf" "$BING_CONF"
    chown "$TARGET_USER:$TARGET_USER" "$BING_CONF"
    info "Utworzono konfigurację: $BING_CONF"
else
    warn "Konfiguracja już istnieje — zachowuję ustawienia."
fi

# =============================================================================
# KROK 10: Konfiguracja GLava
# =============================================================================
section "Konfiguracja GLava"

BACKUP_DIR="$GLAVA_CONFIG/backup_install"
mkdir -p "$BACKUP_DIR"
chown "$TARGET_USER:$TARGET_USER" "$BACKUP_DIR"

backup_file() {
    [ -f "$1" ] && cp "$1" "$BACKUP_DIR/$(basename "$1").bak" || true
}

# Pliki konfiguracyjne GLava
for f in rc.glsl smooth_parameters.glsl bars.glsl circle.glsl wave.glsl radial.glsl; do
    if [ -f "$SCRIPT_DIR/glava-config/$f" ]; then
        backup_file "$GLAVA_CONFIG/$f"
        cp "$SCRIPT_DIR/glava-config/$f" "$GLAVA_CONFIG/$f"
        chown "$TARGET_USER:$TARGET_USER" "$GLAVA_CONFIG/$f"
        info "Zainstalowano: $f"
    fi
done

# util/
if [ -d "$SCRIPT_DIR/glava-config/util" ]; then
    rm -rf "$GLAVA_CONFIG/util"
    cp -r "$SCRIPT_DIR/glava-config/util" "$GLAVA_CONFIG/util"
    chown -R "$TARGET_USER:$TARGET_USER" "$GLAVA_CONFIG/util"
    info "Zainstalowano: util/"
fi

# Plik konfiguracyjny graph.glsl
if [ -f "$SCRIPT_DIR/glava-config/graph.glsl" ]; then
    backup_file "$GLAVA_CONFIG/graph.glsl"
    cp "$SCRIPT_DIR/glava-config/graph.glsl" "$GLAVA_CONFIG/graph.glsl"
    chown "$TARGET_USER:$TARGET_USER" "$GLAVA_CONFIG/graph.glsl"
    info "Zainstalowano: graph.glsl"
fi
# Domyślny aktywny moduł
ACTIVE_MODULE_FILE="$GLAVA_CONFIG/active_module"
if [ ! -f "$ACTIVE_MODULE_FILE" ]; then
    echo "bars" > "$ACTIVE_MODULE_FILE"
    chown "$TARGET_USER:$TARGET_USER" "$ACTIVE_MODULE_FILE"
    info "Domyślny moduł: bars"
fi

# =============================================================================
# KROK 10b: Dodatkowe moduły GLava
# =============================================================================
section "Instalacja dodatkowych modułów GLava"

echo -e "Zainstalować dodatkowe moduły wizualizatora? (bars, circle, wave, radial, graph)"
echo -e "Umożliwia przełączanie między różnymi stylami wizualizacji. [T/n]"
read -rp "" INSTALL_EXTRA
INSTALL_EXTRA="${INSTALL_EXTRA:-T}"

if [[ "$INSTALL_EXTRA" =~ ^[Tt]$ ]]; then

    echo -e "Nadpisać istniejące pliki szaderów? [T]ak / [n]ie / [p]ytaj"
    read -rp "" OVERWRITE_CHOICE
    OVERWRITE_CHOICE="${OVERWRITE_CHOICE:-T}"

    EXTRA_MODULES=(bars circle wave radial graph)

    for module in "${EXTRA_MODULES[@]}"; do

        # .glsl parametry — kopiuj z /etc/xdg/glava jeśli nie istnieje
        if [ ! -f "$GLAVA_CONFIG/$module.glsl" ]; then
            if [ -f "/etc/xdg/glava/$module.glsl" ]; then
                cp "/etc/xdg/glava/$module.glsl" "$GLAVA_CONFIG/$module.glsl"
                chown "$TARGET_USER:$TARGET_USER" "$GLAVA_CONFIG/$module.glsl"
                info "Skopiowano: $module.glsl"
            fi
        fi

        # Katalog modułu z /etc/xdg/glava
        if [ ! -d "$GLAVA_CONFIG/$module" ]; then
            if [ -d "/etc/xdg/glava/$module" ]; then
                cp -r "/etc/xdg/glava/$module" "$GLAVA_CONFIG/$module"
                chown -R "$TARGET_USER:$TARGET_USER" "$GLAVA_CONFIG/$module"
                info "Skopiowano katalog: $module/"
            fi
        fi

        # Szablon kolorów z repozytorium
        FRAG_SRC="$SCRIPT_DIR/config/${module}_colors.frag"
        FRAG_DST="$GLAVA_CONFIG/${module}_colors.frag"

        [ -f "$FRAG_SRC" ] || continue

        COPY_FILE=true
        if [ -f "$FRAG_DST" ]; then
            case "$OVERWRITE_CHOICE" in
                [Nn]) COPY_FILE=false ;;
                [Pp])
                    echo -e "${module}_colors.frag już istnieje. Nadpisać? [t/N]"
                    read -rp "" ans
                    [[ "$ans" =~ ^[Tt]$ ]] && COPY_FILE=true || COPY_FILE=false
                    ;;
            esac
        fi

        if [ "$COPY_FILE" = true ]; then
            backup_file "$FRAG_DST"
            cp "$FRAG_SRC" "$FRAG_DST"
            chown "$TARGET_USER:$TARGET_USER" "$FRAG_DST"
            info "Zainstalowano: ${module}_colors.frag"
        else
            warn "Pominięto: ${module}_colors.frag"
        fi
    done

    # smooth_parameters.glsl — kopiuj z /etc/xdg/glava jeśli brak w repo
    if [ ! -f "$GLAVA_CONFIG/smooth_parameters.glsl" ]; then
        if [ -f "/etc/xdg/glava/smooth_parameters.glsl" ]; then
            cp "/etc/xdg/glava/smooth_parameters.glsl" \
               "$GLAVA_CONFIG/smooth_parameters.glsl"
            chown "$TARGET_USER:$TARGET_USER" "$GLAVA_CONFIG/smooth_parameters.glsl"
            info "Skopiowano: smooth_parameters.glsl"
        fi
    fi

else
    warn "Pominięto dodatkowe moduły."
fi

# =============================================================================
# KROK 11: Auto-konfiguracja geometrii GLava
# =============================================================================
section "Auto-konfiguracja geometrii GLava"

SCREEN_W=1600; SCREEN_H=900; PANEL_H=40  # fallback

if command -v xprop &>/dev/null; then
    XPROP_OUT=$(sudo -u "$TARGET_USER" \
        DISPLAY=:0 \
        XAUTHORITY="$TARGET_HOME/.Xauthority" \
        xprop -root _NET_CLIENT_LIST 2>/dev/null || true)

    # Skanuj STRUT_PARTIAL dla wszystkich okien
    MAX_BOTTOM=0
    WIN_IDS=$(echo "$XPROP_OUT" | grep -o '0x[0-9a-fA-F]*')
    for wid in $WIN_IDS; do
        STRUT=$(sudo -u "$TARGET_USER" \
            DISPLAY=:0 \
            XAUTHORITY="$TARGET_HOME/.Xauthority" \
            xprop -id "$wid" _NET_WM_STRUT_PARTIAL 2>/dev/null || true)
        BOT=$(echo "$STRUT" | grep -o '[0-9]*' | sed -n '4p')
        if [ -n "$BOT" ] && [ "$BOT" -gt "$MAX_BOTTOM" ]; then
            MAX_BOTTOM=$BOT
        fi
    done

    # Rozmiar ekranu z xrandr
    XRANDR_OUT=$(sudo -u "$TARGET_USER" \
        DISPLAY=:0 \
        XAUTHORITY="$TARGET_HOME/.Xauthority" \
        xrandr --current 2>/dev/null || true)
    RES=$(echo "$XRANDR_OUT" | grep -o 'current [0-9]* x [0-9]*' | head -1)
    if [ -n "$RES" ]; then
        SCREEN_W=$(echo "$RES" | awk '{print $2}')
        SCREEN_H=$(echo "$RES" | awk '{print $4}')
    fi

    [ "$MAX_BOTTOM" -gt 0 ] && PANEL_H=$MAX_BOTTOM
    info "Wykryto: ${SCREEN_W}×${SCREEN_H}, pasek zadań: ${PANEL_H}px"
else
    warn "xprop niedostępny — używam wartości domyślnych ${SCREEN_W}×${SCREEN_H}."
fi

RC_FILE="$GLAVA_CONFIG/rc.glsl"
if [ -f "$RC_FILE" ]; then
    ACTIVE_MOD="bars"
    [ -f "$ACTIVE_MODULE_FILE" ] && ACTIVE_MOD=$(cat "$ACTIVE_MODULE_FILE")
    GEO="0 -$PANEL_H $SCREEN_W $SCREEN_H"
    sed -i "s/#request setgeometry [0-9-]* [0-9-]* [0-9-]* [0-9-]*/#request setgeometry $GEO/" "$RC_FILE"
    info "Geometria GLava: $GEO"
fi

# =============================================================================
# KROK 12: Pliki .desktop
# =============================================================================
section "Skróty w menu aplikacji"

DESKTOP_DST="$TARGET_HOME/.local/share/applications"
mkdir -p "$DESKTOP_DST"
if [ -d "$SCRIPT_DIR/desktop" ]; then
    for f in "$SCRIPT_DIR/desktop"/*.desktop; do
        [ -f "$f" ] || continue
        cp "$f" "$DESKTOP_DST/"
        chown "$TARGET_USER:$TARGET_USER" "$DESKTOP_DST/$(basename "$f")"
        info "Zainstalowano: $(basename "$f")"
    done
    sudo -u "$TARGET_USER" update-desktop-database "$DESKTOP_DST" 2>/dev/null || true
fi

# =============================================================================
# KROK 13: Autostart GLava
# =============================================================================
section "Autostart GLava"

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
    info "Dodano autostart GLava."
fi

# =============================================================================
# KROK 14: Usługa systemd
# =============================================================================
section "Usługa systemd (demon kolorów)"

SERVICE_DST="$SYSTEMD_DIR/glava-color-daemon.service"
cp "$SCRIPT_DIR/systemd/glava-color-daemon.service" "$SERVICE_DST"
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
    info "Usługa systemd skonfigurowana i włączona."
else
    warn "Brak aktywnej sesji — usługa uruchomi się przy następnym logowaniu."
fi

# =============================================================================
# KROK 15: Cron
# =============================================================================
section "Konfiguracja harmonogramu pobierania tapet"

CRON_LINE="$CRON_SCHEDULE /usr/local/bin/bing-downloader.sh $TARGET_USER >> $LOG_DIR/bing-downloader.log 2>&1"
CRON_MARKER="# bing-glava-suite:$TARGET_USER"
EXISTING=$(crontab -l 2>/dev/null || true)

if echo "$EXISTING" | grep -q "bing-downloader.sh $TARGET_USER"; then
    NEW_CRON=$(echo "$EXISTING" \
        | grep -v "bing-downloader.sh $TARGET_USER" \
        | grep -v "# bing-glava-suite:$TARGET_USER")
    (echo "$NEW_CRON"; echo "$CRON_MARKER"; echo "$CRON_LINE") | crontab -
    info "Zaktualizowano harmonogram pobierania tapet."
else
    (echo "$EXISTING"; echo "$CRON_MARKER"; echo "$CRON_LINE") | crontab -
    info "Dodano harmonogram: co $INPUT_CRON minut."
fi

# =============================================================================
# KROK 16: Pierwsze pobranie tapety
# =============================================================================
section "Pierwsze pobranie tapety"

echo -e "Pobrać dzisiejszą tapetę Bing teraz? [T/n]"
read -rp "" RUN_NOW
RUN_NOW="${RUN_NOW:-T}"
if [[ "$RUN_NOW" =~ ^[Tt]$ ]]; then
    /usr/local/bin/bing-downloader.sh "$TARGET_USER" && \
        info "Tapeta pobrana pomyślnie." || \
        warn "Nie udało się pobrać tapety — spróbuj ręcznie później."
fi

# =============================================================================
# PODSUMOWANIE
# =============================================================================
section "Instalacja zakończona"
echo ""
echo -e "  Panel GUI:           ${BLD}glava-gui${RST}"
echo -e "  Moduły GUI:          ${BLD}$GLAVAMP_DIR/${RST}"
echo -e "  Konfiguracja Bing:   ${BLD}$BING_CONF${RST}"
echo -e "  Tapety:              ${BLD}$TARGET_HOME/Pictures/Bing/${RST}"
echo -e "  Logi:                ${BLD}$LOG_DIR/${RST}"
echo ""
warn "Aby uruchomić usługę bez wylogowania:"
echo -e "  ${BLD}systemctl --user start glava-color-daemon${RST}"
echo ""
info "Gotowe! Wyloguj się i zaloguj ponownie, aby wszystko wystartowało automatycznie."
