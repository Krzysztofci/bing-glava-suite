#!/bin/bash
# =============================================================================
# tools/compare-installed.sh
# Porównuje pliki z repo ze zainstalowanymi odpowiednikami.
#
# Mapowanie katalogów:
#   scripts/gui/*          → ~/.local/bin/GlavaMP/gui/*
#   scripts/glava-gui.py   → ~/.local/bin/GlavaMP/glava-gui.py
#   scripts/glava-*        → ~/.local/bin/ (skrypty główne)
#   scripts/bing-downloader.sh → /usr/local/bin/
#   scripts/bing-fetch-meta.sh → /usr/local/bin/GlavaMP/
#   scripts/build-glava-deb.sh → (skrypt developerski, nie instalowany)
# =============================================================================

REPO_SCRIPTS="$HOME/bing-glava-suite/scripts"
LOCAL_BIN="$HOME/.local/bin"
GLAVAMP="$HOME/.local/bin/GlavaMP"

DIFF=0
MISSING=0
SKIP=0

check() {
    local repo_file="$1"
    local installed="$2"
    local label="$3"

    if [ ! -f "$installed" ]; then
        echo "  BRAK:     $label"
        echo "            repo:      $repo_file"
        echo "            oczekiwano: $installed"
        MISSING=$((MISSING + 1))
        return
    fi

    if ! diff -q "$repo_file" "$installed" > /dev/null 2>&1; then
        echo "  RÓŻNI SIĘ: $label"
        echo "            repo:      $repo_file"
        echo "            instalacja: $installed"
        DIFF=$((DIFF + 1))
    fi
}

echo "============================================================"
echo " Porównanie repo vs instalacja"
echo " Repo:      $REPO_SCRIPTS"
echo " Instalacja: $GLAVAMP"
echo "============================================================"

# ── Pliki GlavaMP (glava-gui.py + gui/**)  ───────────────────────────────────
echo ""
echo "[ GlavaMP — $GLAVAMP ]"
find "$REPO_SCRIPTS" -type f \( -name "*.py" -o -name "*.tcl" \) \
    -not -path "*/\__pycache__/*" | sort | while read repo_file; do
    rel=${repo_file#$REPO_SCRIPTS/}
    installed="$GLAVAMP/$rel"
    check "$repo_file" "$installed" "$rel"
done

# ── Skrypty bash w ~/.local/bin/ ─────────────────────────────────────────────
echo ""
echo "[ Skrypty bash — $LOCAL_BIN ]"
for script in \
    glava-autostart.sh \
    glava-color-daemon \
    glava-colors-auto \
    glava-colors-auto-mi \
    glava-toggle \
    glava-colorswitch \
    glava-autostart \
    wizual_record.sh \
    wizual_to_gif.sh
do
    repo_file="$REPO_SCRIPTS/$script"
    installed="$LOCAL_BIN/$script"
    [ -f "$repo_file" ] && check "$repo_file" "$installed" "$script"
done

# ── bing-downloader.sh → /usr/local/bin/ ─────────────────────────────────────
echo ""
echo "[ /usr/local/bin/ ]"
check "$REPO_SCRIPTS/bing-downloader.sh" "/usr/local/bin/bing-downloader.sh" "bing-downloader.sh"

# ── bing-fetch-meta.sh → /usr/local/bin/GlavaMP/ ─────────────────────────────
echo ""
echo "[ /usr/local/bin/GlavaMP/ ]"
check "$REPO_SCRIPTS/bing-fetch-meta.sh" "/usr/local/bin/GlavaMP/bing-fetch-meta.sh" "bing-fetch-meta.sh"

# ── build-glava-deb.sh — skrypt developerski, nie instalowany ────────────────
echo ""
echo "[ Skrypty developerskie — nie instalowane ]"
echo "  POMINIĘTO: build-glava-deb.sh (skrypt budowania .deb, nie instalowany)"
SKIP=$((SKIP + 1))

# ── Podsumowanie ─────────────────────────────────────────────────────────────
echo ""
echo "============================================================"
echo " Podsumowanie:"
echo "   Różnią się: $DIFF"
echo "   Brak:       $MISSING"
echo "   Pominięto:  $SKIP"
echo "============================================================"
