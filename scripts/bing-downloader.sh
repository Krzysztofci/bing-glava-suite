#!/bin/bash
# =============================================================================
# bing-downloader.sh
# Systemowy skrypt pobierający tapetę Bing dla wskazanego użytkownika.
# Instalowany w /usr/local/bin/ — nie może być edytowany przez użytkownika.
# Uruchamiany z crona jako root z nazwą użytkownika jako argumentem.
#
# Użycie:
#   /usr/local/bin/bing-downloader.sh <nazwa_użytkownika> [--no-lightdm] [--force]
#
# Flagi:
#   --no-lightdm  Pomija aktualizację ekranu logowania LightDM
#   --force       Wymusza pobranie nawet jeśli URL się nie zmienił
# =============================================================================

# --- Argument: nazwa użytkownika ---
TARGET_USER="$1"
if [ -z "$TARGET_USER" ]; then
    echo "Użycie: $0 <nazwa_użytkownika> [--no-lightdm] [--force]"
    exit 1
fi

if ! id "$TARGET_USER" &>/dev/null; then
    echo "Użytkownik '$TARGET_USER' nie istnieje."
    exit 1
fi

# --- Flagi ---

NO_LIGHTDM=false
FORCE=false
for arg in "${@:2}"; do
    case "$arg" in
        --no-lightdm) NO_LIGHTDM=true ;;
        --force)      FORCE=true ;;
    esac
done

# --- Ścieżki ---
TARGET_HOME=$(getent passwd "$TARGET_USER" | cut -d: -f6)
LOCK_FILE="$TARGET_HOME/.config/GlavaMP/wallpaper.lock"
if [ -f "$LOCK_FILE" ]; then
    exit 0
fi
CONFIG_FILE="$TARGET_HOME/.config/bing-glava/config"
PICTURES_DIR="$TARGET_HOME/Pictures/Bing"
FULL_PATH="$PICTURES_DIR/bing_today.jpg"
TEMP_PATH="$PICTURES_DIR/bing_temp.jpg"
URL_CACHE="$PICTURES_DIR/last_url.txt"
LOGIN_BACKGROUND="/usr/share/backgrounds/login-bing.jpg"
MINT_DEFAULT="/usr/share/backgrounds/linuxmint/default_background.jpg"

mkdir -p "$PICTURES_DIR"

# --- Odczyt konfiguracji użytkownika ---
BING_REGION="de-DE"
if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE"
fi

# --- KROK 1: Pobierz URL tapety ---
JSON_DATA=$(/usr/bin/curl -s --connect-timeout 10 \
    "https://www.bing.com/HPImageArchive.aspx?format=js&idx=0&n=1&mkt=$BING_REGION")

if [ -z "$JSON_DATA" ]; then
    echo "Brak połączenia z siecią. Przerywam."
    exit 1
fi

URL_PATH=$(echo "$JSON_DATA" | /usr/bin/jq -r '.images[0].url')
URL_UHD=$(echo "$URL_PATH" | sed 's/1920x1080/UHD/g')
FULL_URL="https://www.bing.com$URL_UHD"

# --- KROK 2: Sprawdź, czy tapeta się zmieniła ---
if [ "$FORCE" = false ] && [ -f "$URL_CACHE" ]; then
    OLD_URL=$(cat "$URL_CACHE")
    if [ "$OLD_URL" = "$FULL_URL" ]; then
        exit 0
    fi
fi

# --- KROK 3: Pobierz do pliku tymczasowego ---
if /usr/bin/wget -q --tries=2 --timeout=15 -O "$TEMP_PATH" "$FULL_URL"; then
    if [ -s "$TEMP_PATH" ]; then
        mv "$TEMP_PATH" "$FULL_PATH"
        echo "$FULL_URL" > "$URL_CACHE"
    else
        rm -f "$TEMP_PATH"
        echo "Pobrany plik jest pusty. Przerywam."
        exit 1
    fi
else
    echo "Błąd pobierania. Zachowuję starą tapetę."
    exit 1
fi

# --- KROK 4: Uprawnienia ---
chown "$TARGET_USER:$TARGET_USER" "$FULL_PATH" "$URL_CACHE"
chmod 644 "$FULL_PATH"

# --- KROK 5: Ekran logowania (pomijany z --no-lightdm) ---
if [ "$NO_LIGHTDM" = false ]; then
    cp "$FULL_PATH" "$LOGIN_BACKGROUND"
    chmod 644 "$LOGIN_BACKGROUND"
    ln -sf "$LOGIN_BACKGROUND" "$MINT_DEFAULT"
fi

# --- KROK 6: Aktualizacja środowiska graficznego ---
USER_ID=$(id -u "$TARGET_USER")
DBUS_ADDR="unix:path=/run/user/$USER_ID/bus"

# XFCE
if pgrep -u "$TARGET_USER" -x "xfdesktop" > /dev/null; then
    PROPS=$(sudo su -c "DBUS_SESSION_BUS_ADDRESS=$DBUS_ADDR /usr/bin/xfconf-query \
        -c xfce4-desktop -l | grep workspace.*last-image" "$TARGET_USER")
    for PROP in $PROPS; do
        sudo su -c "DBUS_SESSION_BUS_ADDRESS=$DBUS_ADDR /usr/bin/xfconf-query \
            -c xfce4-desktop -p $PROP -s $FULL_PATH" "$TARGET_USER"
    done
fi

# Cinnamon
if pgrep -u "$TARGET_USER" -x "cinnamon" > /dev/null; then
    sudo -u "$TARGET_USER" DBUS_SESSION_BUS_ADDRESS="$DBUS_ADDR" \
        gsettings set org.cinnamon.desktop.background picture-uri "file://$FULL_PATH" 2>/dev/null
    sudo -u "$TARGET_USER" DBUS_SESSION_BUS_ADDRESS="$DBUS_ADDR" \
        gsettings set org.cinnamon.desktop.background picture-options 'zoom' 2>/dev/null
fi
