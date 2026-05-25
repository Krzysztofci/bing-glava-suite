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
PICTURES_DIR="$TARGET_HOME/Pictures/Bing"
THUMBS_DIR="$PICTURES_DIR/thumbs"
META_FILE="$PICTURES_DIR/metadata.json"
LOCK_FILE="$TARGET_HOME/.config/GlavaMP/wallpaper.lock"
CONFIG_FILE="$TARGET_HOME/.config/bing-glava/config"
FULL_PATH="$PICTURES_DIR/bing_today.jpg"
TEMP_PATH="$PICTURES_DIR/bing_temp.jpg"
URL_CACHE="$PICTURES_DIR/last_url.txt"
LOGIN_BACKGROUND="/usr/share/backgrounds/login-bing.jpg"
MINT_DEFAULT="/usr/share/backgrounds/linuxmint/default_background.jpg"

mkdir -p "$PICTURES_DIR" "$THUMBS_DIR"

# --- KROK 7: Miniatury i metadane dla wszystkich regionów Bing ---
BING_REGIONS=("de-DE" "en-US" "en-GB" "fr-FR" "es-ES" "it-IT" "pt-BR" "ja-JP" "zh-CN" "pl-PL")
THUMB_FETCHED=0

if [ -f "$META_FILE" ]; then
    OLD_META=$(cat "$META_FILE")
else
    OLD_META="{}"
fi

NEW_META="{}"

for REGION in "${BING_REGIONS[@]}"; do
    echo "Miniatury: odpytuję $REGION"

    REGION_JSON=$(/usr/bin/curl -s --connect-timeout 10 \
        "https://www.bing.com/HPImageArchive.aspx?format=js&idx=0&n=1&mkt=$REGION")

    if [ -z "$REGION_JSON" ]; then
        echo "  Brak odpowiedzi dla $REGION, pomijam."
        # Zachowaj stare metadane dla tego regionu
        OLD_REGION=$(echo "$OLD_META" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(json.dumps(d.get('$REGION', {})))
except:
    print('{}')
")
        if [ "$OLD_REGION" != "{}" ]; then
            NEW_META=$(echo "$NEW_META" | python3 -c "
import sys, json
data = json.load(sys.stdin)
data['$REGION'] = $OLD_REGION
print(json.dumps(data, ensure_ascii=False, indent=2))
")
        fi
        continue
    fi

    TITLE=$(echo "$REGION_JSON"     | python3 -c "import sys,json; d=json.load(sys.stdin)['images'][0]; print(d.get('title',''))")
    COPYRIGHT=$(echo "$REGION_JSON" | python3 -c "import sys,json; d=json.load(sys.stdin)['images'][0]; print(d.get('copyright',''))")
    STARTDATE=$(echo "$REGION_JSON" | python3 -c "import sys,json; d=json.load(sys.stdin)['images'][0]; print(d.get('startdate',''))")
    ENDDATE=$(echo "$REGION_JSON"   | python3 -c "import sys,json; d=json.load(sys.stdin)['images'][0]; print(d.get('enddate',''))")
    URLBASE=$(echo "$REGION_JSON"   | python3 -c "import sys,json; d=json.load(sys.stdin)['images'][0]; print(d.get('urlbase',''))")

    if [ -z "$URLBASE" ]; then
        echo "  Brak urlbase dla $REGION, pomijam."
        continue
    fi

    IMAGE_ID=$(echo "$URLBASE" | python3 -c "
import sys, re
m = re.search(r'OHR\.[A-Za-z]+', sys.stdin.read())
print(m.group(0) if m else '')
")

    THUMB_ID=$(echo "$URLBASE" | sed 's|/th?id=||')
    THUMB_FILE="$THUMBS_DIR/${THUMB_ID}_320x180.jpg"
    THUMB_TEMP="$THUMBS_DIR/${THUMB_ID}_320x180.tmp"
    THUMB_URL="https://www.bing.com/th?id=${THUMB_ID}_320x180.jpg"

    OLD_IMAGE_ID=$(echo "$OLD_META" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('$REGION', {}).get('image_id', ''))
except:
    print('')
")

    if [ ! -f "$THUMB_FILE" ] || [ "$OLD_IMAGE_ID" != "$IMAGE_ID" ]; then
        echo "  Pobieram miniaturę: $IMAGE_ID"
        if /usr/bin/wget -q --tries=2 --timeout=15 -O "$THUMB_TEMP" "$THUMB_URL"; then
            if [ -s "$THUMB_TEMP" ]; then
                mv "$THUMB_TEMP" "$THUMB_FILE"
                chown "$TARGET_USER:$TARGET_USER" "$THUMB_FILE"
                chmod 644 "$THUMB_FILE"
                THUMB_FETCHED=$((THUMB_FETCHED + 1))
            else
                rm -f "$THUMB_TEMP"
                echo "  Miniatura pusta dla $REGION, pomijam."
                THUMB_FILE=""
            fi
        else
            rm -f "$THUMB_TEMP"
            echo "  Błąd pobierania miniatury dla $REGION."
            THUMB_FILE=""
        fi
    else
        echo "  Miniatura aktualna: $IMAGE_ID"
    fi

    NEW_META=$(echo "$NEW_META" | python3 -c "
import sys, json
data = json.load(sys.stdin)
data['$REGION'] = {
    'title':      '''$TITLE''',
    'copyright':  '''$COPYRIGHT''',
    'startdate':  '$STARTDATE',
    'enddate':    '$ENDDATE',
    'urlbase':    '$URLBASE',
    'image_id':   '$IMAGE_ID',
    'thumb_file': '$THUMB_FILE',
}
print(json.dumps(data, ensure_ascii=False, indent=2))
")
done

# Usuń stare miniatury tylko jeśli pobrano przynajmniej jedną nową
if [ "$THUMB_FETCHED" -gt 0 ]; then
    echo "Pobrano $THUMB_FETCHED nowych miniatur — czyszczę stare."
    python3 - << PYEOF
import json, os, glob

thumbs_dir = '$THUMBS_DIR'

try:
    new = json.loads('''$NEW_META''')
    new_thumbs = set(v.get('thumb_file', '') for v in new.values())
except Exception as e:
    print(f'  Błąd parsowania metadanych: {e}')
    new_thumbs = set()

for f in glob.glob(os.path.join(thumbs_dir, '*.jpg')):
    if f not in new_thumbs:
        print(f'  Usuwam: {os.path.basename(f)}')
        os.remove(f)
PYEOF
fi

# Zapisz metadane (tylko jeśli cokolwiek pobrano lub jest to pierwsze uruchomienie)
if [ "$THUMB_FETCHED" -gt 0 ] || [ ! -f "$META_FILE" ]; then
    echo "$NEW_META" > "$META_FILE"
    chown "$TARGET_USER:$TARGET_USER" "$META_FILE"
    echo "Metadane zapisane: $META_FILE"
fi

# --- Sprawdzenie blokady tapety ---
if [ -f "$LOCK_FILE" ]; then
    exit 0
fi

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

