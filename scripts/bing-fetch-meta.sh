#!/bin/bash
# =============================================================================
# bing-fetch-meta.sh
# Pobiera metadane i miniatury dla wszystkich regionów Bing.
# Zapisuje ~/Pictures/Bing/metadata.json i ~/Pictures/Bing/thumbs/*.jpg
# Uruchamiany przez cron lub ręcznie.
# =============================================================================

PICTURES_DIR="$HOME/Pictures/Bing"
THUMBS_DIR="$PICTURES_DIR/thumbs"
META_FILE="$PICTURES_DIR/metadata.json"
BING_REGIONS=("de-DE" "en-US" "en-GB" "fr-FR" "es-ES" "it-IT" "pt-BR" "ja-JP" "zh-CN" "pl-PL")

mkdir -p "$THUMBS_DIR"

# Wczytaj istniejące metadane jeśli są
if [ -f "$META_FILE" ]; then
    OLD_META=$(cat "$META_FILE")
else
    OLD_META="{}"
fi

NEW_META="{}"

for REGION in "${BING_REGIONS[@]}"; do
    echo "Odpytuję: $REGION"

    JSON=$(curl -s --connect-timeout 10 \
        "https://www.bing.com/HPImageArchive.aspx?format=js&idx=0&n=1&mkt=$REGION")

    if [ -z "$JSON" ]; then
        echo "  Brak odpowiedzi dla $REGION, pomijam."
        continue
    fi

    # Wyciągnij pola
    TITLE=$(echo "$JSON"     | python3 -c "import sys,json; d=json.load(sys.stdin)['images'][0]; print(d.get('title',''))")
    COPYRIGHT=$(echo "$JSON" | python3 -c "import sys,json; d=json.load(sys.stdin)['images'][0]; print(d.get('copyright',''))")
    STARTDATE=$(echo "$JSON" | python3 -c "import sys,json; d=json.load(sys.stdin)['images'][0]; print(d.get('startdate',''))")
    ENDDATE=$(echo "$JSON"   | python3 -c "import sys,json; d=json.load(sys.stdin)['images'][0]; print(d.get('enddate',''))")
    URLBASE=$(echo "$JSON"   | python3 -c "import sys,json; d=json.load(sys.stdin)['images'][0]; print(d.get('urlbase',''))")

    if [ -z "$URLBASE" ]; then
        echo "  Brak urlbase dla $REGION, pomijam."
        continue
    fi

    # Wyciągnij image_id np. OHR.SichuanTea
    IMAGE_ID=$(echo "$URLBASE" | python3 -c "
import sys, re
m = re.search(r'OHR\.[A-Za-z]+', sys.stdin.read())
print(m.group(0) if m else '')
")

    # Nazwa pliku miniatury — pełny id z urlbase + rozmiar
    THUMB_ID=$(echo "$URLBASE" | sed 's|/th?id=||')
    THUMB_FILE="$THUMBS_DIR/${THUMB_ID}_320x180.jpg"
    THUMB_URL="https://www.bing.com/th?id=${THUMB_ID}_320x180.jpg"

    # Pobierz miniaturę tylko jeśli image_id się zmienił lub plik nie istnieje
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
        curl -s --connect-timeout 10 -o "$THUMB_FILE" "$THUMB_URL"
        if [ ! -s "$THUMB_FILE" ]; then
            echo "  Błąd pobierania miniatury dla $REGION"
            rm -f "$THUMB_FILE"
            THUMB_FILE=""
        fi
    else
        echo "  Miniatura aktualna: $IMAGE_ID"
    fi

    # Dodaj do nowych metadanych
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

# Usuń stare miniatury których image_id nie ma już w żadnym regionie
echo "Czyszczę stare miniatury..."
python3 - << PYEOF
import json, os, glob

meta_file = '$META_FILE'
thumbs_dir = '$THUMBS_DIR'

try:
    with open(meta_file) as f:
        old = json.load(f)
    active_thumbs = set(v.get('thumb_file','') for v in old.values())
except:
    active_thumbs = set()

new_meta_str = '''$NEW_META'''
try:
    new = json.loads(new_meta_str)
    new_thumbs = set(v.get('thumb_file','') for v in new.values())
except:
    new_thumbs = set()

for f in glob.glob(os.path.join(thumbs_dir, '*.jpg')):
    if f not in new_thumbs:
        print(f'  Usuwam: {os.path.basename(f)}')
        os.remove(f)
PYEOF

# Zapisz nowe metadane
echo "$NEW_META" > "$META_FILE"
echo "Gotowe. Metadane zapisane: $META_FILE"
