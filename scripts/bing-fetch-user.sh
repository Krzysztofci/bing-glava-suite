#!/bin/bash
# =============================================================================
# bing-fetch-user.sh
# Lekki skrypt użytkownika — pobiera tapetę Bing i ustawia pulpit.
# Działa bez sudo. Nie dotyka ekranu logowania LightDM.
# Wywoływany przez GUI przy żądaniu zmiany tapety.
#
# Flagi:
#   --force   Wymusza pobranie nawet jeśli URL się nie zmienił
# =============================================================================

FORCE=false
for arg in "$@"; do
    [ "$arg" = "--force" ] && FORCE=true
done

CONFIG_FILE="$HOME/.config/bing-glava/config"
PICTURES_DIR="$HOME/Pictures/Bing"
FULL_PATH="$PICTURES_DIR/bing_today.jpg"
TEMP_PATH="$PICTURES_DIR/bing_temp.jpg"
URL_CACHE="$PICTURES_DIR/last_url.txt"

mkdir -p "$PICTURES_DIR"

# Odczyt konfiguracji
BING_REGION="de-DE"
if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE"
fi
# Sprawdź blokadę tapety
WALLPAPER_LOCK="$HOME/.config/bing-glava/wallpaper.lock"
if [ -f "$WALLPAPER_LOCK" ]; then
    echo "Tapeta zablokowana — pomijam pobieranie."
    exit 0
fi

# KROK 1: Pobierz URL
JSON_DATA=$(/usr/bin/curl -s --connect-timeout 10 \
    "https://www.bing.com/HPImageArchive.aspx?format=js&idx=0&n=1&mkt=$BING_REGION")

if [ -z "$JSON_DATA" ]; then
    echo "Brak połączenia z siecią."
    exit 1
fi

URL_PATH=$(echo "$JSON_DATA" | /usr/bin/jq -r '.images[0].url')
URL_UHD=$(echo "$URL_PATH" | sed 's/1920x1080/UHD/g')
FULL_URL="https://www.bing.com$URL_UHD"

# KROK 2: Sprawdź czy tapeta się zmieniła
if [ "$FORCE" = false ] && [ -f "$URL_CACHE" ]; then
    OLD_URL=$(cat "$URL_CACHE")
    if [ "$OLD_URL" = "$FULL_URL" ]; then
        exit 0
    fi
fi

# KROK 3: Pobierz
if /usr/bin/wget -q --tries=2 --timeout=15 -O "$TEMP_PATH" "$FULL_URL"; then
    if [ -s "$TEMP_PATH" ]; then
        mv "$TEMP_PATH" "$FULL_PATH"
        echo "$FULL_URL" > "$URL_CACHE"
    else
        rm -f "$TEMP_PATH"
        exit 1
    fi
else
    exit 1
fi

chmod 644 "$FULL_PATH"

# KROK 4: Ustaw tapetę pulpitu (bez sudo)
DBUS_ADDR="unix:path=/run/user/$(id -u)/bus"

# XFCE
if pgrep -x "xfdesktop" > /dev/null; then
    PROPS=$(DBUS_SESSION_BUS_ADDRESS="$DBUS_ADDR" /usr/bin/xfconf-query \
        -c xfce4-desktop -l 2>/dev/null | grep "workspace.*last-image")
    for PROP in $PROPS; do
        DBUS_SESSION_BUS_ADDRESS="$DBUS_ADDR" /usr/bin/xfconf-query \
            -c xfce4-desktop -p "$PROP" -s "$FULL_PATH"
    done
fi

# Cinnamon
if pgrep -x "cinnamon" > /dev/null; then
    DBUS_SESSION_BUS_ADDRESS="$DBUS_ADDR" \
        gsettings set org.cinnamon.desktop.background picture-uri "file://$FULL_PATH" 2>/dev/null
    DBUS_SESSION_BUS_ADDRESS="$DBUS_ADDR" \
        gsettings set org.cinnamon.desktop.background picture-options 'zoom' 2>/dev/null
fi
