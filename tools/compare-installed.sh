#!/bin/bash
# =============================================================================
# tools/compare-installed.sh
# Porównuje pliki z repo ze zainstalowanymi odpowiednikami.
#
# Mapowanie katalogów:
#   scripts/gui/*              → ~/.local/bin/GlavaMP/gui/*
#   scripts/glava-gui.py       → ~/.local/bin/GlavaMP/glava-gui.py
#   scripts/glava-*            → ~/.local/bin/ (skrypty główne)
#   scripts/glava-colors-auto-mi → ~/.local/bin/ (skrypt Python w local/bin)
#   scripts/bing-downloader.sh → /usr/local/bin/
#   scripts/bing-fetch-meta.sh → /usr/local/bin/GlavaMP/
#   scripts/build-glava-deb.sh → (skrypt developerski, nie instalowany)
# =============================================================================

REPO_SCRIPTS="$HOME/bing-glava-suite/scripts"
LOCAL_BIN="$HOME/.local/bin"
GLAVAMP="$HOME/.local/bin/GlavaMP"

# ── Kolory ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
GRAY='\033[0;37m'
BOLD='\033[1m'
NC='\033[0m'

# ── Liczniki i listy (pliki tymczasowe zamiast subshell) ──────────────────────
TMPDIR_CS=$(mktemp -d)
echo 0 > "$TMPDIR_CS/diff"
echo 0 > "$TMPDIR_CS/missing"
echo 0 > "$TMPDIR_CS/skip"
echo 0 > "$TMPDIR_CS/ok"
> "$TMPDIR_CS/diff_list"
> "$TMPDIR_CS/missing_list"

cleanup() { rm -rf "$TMPDIR_CS"; }
trap cleanup EXIT

inc() { echo $(( $(cat "$TMPDIR_CS/$1") + 1 )) > "$TMPDIR_CS/$1"; }

# ── Funkcja sprawdzania ───────────────────────────────────────────────────────
check() {
    local repo_file="$1"
    local installed="$2"
    local label="$3"

    if [ ! -f "$installed" ]; then
        echo -e "  ${RED}✗ BRAK${NC}      ${BOLD}$label${NC}"
        echo -e "    ${GRAY}repo:       $repo_file${NC}"
        echo -e "    ${GRAY}oczekiwano: $installed${NC}"
        inc missing
        echo "BRAK|$label|$repo_file|$installed" >> "$TMPDIR_CS/missing_list"
        return
    fi

    if ! diff -q "$repo_file" "$installed" > /dev/null 2>&1; then
        echo -e "  ${YELLOW}≠ RÓŻNI SIĘ${NC} ${BOLD}$label${NC}"
        echo -e "    ${GRAY}repo:       $repo_file${NC}"
        echo -e "    ${GRAY}instalacja: $installed${NC}"
        inc diff
        echo "DIFF|$label|$repo_file|$installed" >> "$TMPDIR_CS/diff_list"
    else
        echo -e "  ${GREEN}✓ OK${NC}        $label"
        inc ok
    fi
}

skip() {
    local label="$1"
    local reason="$2"
    echo -e "  ${CYAN}~ POMINIĘTO${NC} ${BOLD}$label${NC} ${GRAY}($reason)${NC}"
    inc skip
}

# ── Nagłówek ─────────────────────────────────────────────────────────────────
echo -e "${BOLD}============================================================${NC}"
echo -e "${BOLD} Porównanie repo vs instalacja${NC}"
echo -e " ${GRAY}Repo:       $REPO_SCRIPTS${NC}"
echo -e " ${GRAY}Instalacja: $GLAVAMP${NC}"
echo -e "${BOLD}============================================================${NC}"

# ── Pliki GlavaMP (glava-gui.py + gui/**) ────────────────────────────────────
echo ""
echo -e "${BOLD}[ GlavaMP — $GLAVAMP ]${NC}"

mapfile -t py_files < <(
    find "$REPO_SCRIPTS" -type f \( -name "*.py" -o -name "*.tcl" \) \
        -not -path "*/__pycache__/*" \
        -not -name "glava-colors-auto-mi" \
        | sort
)
for repo_file in "${py_files[@]}"; do
    rel=${repo_file#$REPO_SCRIPTS/}
    installed="$GLAVAMP/$rel"
    check "$repo_file" "$installed" "$rel"
done

# ── Skrypty bash w ~/.local/bin/ ─────────────────────────────────────────────
echo ""
echo -e "${BOLD}[ Skrypty bash — $LOCAL_BIN ]${NC}"
for script in \
    glava-autostart.sh \
    glava-color-daemon \
    glava-colors-auto \
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

# ── Skrypty Python w ~/.local/bin/ ───────────────────────────────────────────
echo ""
echo -e "${BOLD}[ Skrypty Python — $LOCAL_BIN ]${NC}"
for script in \
    glava-colors-auto-mi
do
    repo_file="$REPO_SCRIPTS/$script"
    installed="$LOCAL_BIN/$script"
    [ -f "$repo_file" ] && check "$repo_file" "$installed" "$script"
done

# ── /usr/local/bin/ ──────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}[ /usr/local/bin/ ]${NC}"
check "$REPO_SCRIPTS/bing-downloader.sh" "/usr/local/bin/bing-downloader.sh" "bing-downloader.sh"

# ── /usr/local/bin/GlavaMP/ ──────────────────────────────────────────────────
echo ""
echo -e "${BOLD}[ /usr/local/bin/GlavaMP/ ]${NC}"
check "$REPO_SCRIPTS/bing-fetch-meta.sh" "/usr/local/bin/GlavaMP/bing-fetch-meta.sh" "bing-fetch-meta.sh"

# ── Skrypty developerskie ─────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}[ Skrypty developerskie ]${NC}"
skip "build-glava-deb.sh" "skrypt budowania .deb, nie instalowany"

# ── Podsumowanie ─────────────────────────────────────────────────────────────
DIFF_N=$(cat "$TMPDIR_CS/diff")
MISSING_N=$(cat "$TMPDIR_CS/missing")
SKIP_N=$(cat "$TMPDIR_CS/skip")
OK_N=$(cat "$TMPDIR_CS/ok")
TOTAL=$(( OK_N + DIFF_N + MISSING_N ))

echo ""
echo -e "${BOLD}============================================================${NC}"
echo -e "${BOLD} Podsumowanie:${NC}  (sprawdzono: $TOTAL plików)"
echo -e "   ${GREEN}✓ Zgodne:     $OK_N${NC}"
[ "$DIFF_N"    -gt 0 ] && echo -e "   ${YELLOW}≠ Różnią się: $DIFF_N${NC}" \
                       || echo -e "   ${GRAY}≠ Różnią się: $DIFF_N${NC}"
[ "$MISSING_N" -gt 0 ] && echo -e "   ${RED}✗ Brak:       $MISSING_N${NC}" \
                       || echo -e "   ${GRAY}✗ Brak:       $MISSING_N${NC}"
echo -e "   ${CYAN}~ Pominięto:  $SKIP_N${NC}"

# ── Lista plików do skopiowania ───────────────────────────────────────────────
if [ "$DIFF_N" -gt 0 ] || [ "$MISSING_N" -gt 0 ]; then
    echo ""
    echo -e "${BOLD}============================================================${NC}"
    echo -e "${BOLD} Pliki do skopiowania (instalacja → repo):${NC}"
    echo -e "${BOLD}============================================================${NC}"

    if [ "$DIFF_N" -gt 0 ]; then
        echo -e " ${YELLOW}≠ Różnią się:${NC}"
        while IFS='|' read -r type label repo installed; do
            echo -e "   ${YELLOW}$label${NC}"
            echo -e "   ${GRAY}cp $installed \\\\${NC}"
            echo -e "   ${GRAY}    $repo${NC}"
            echo -e "   ${GRAY}   $installed${NC}"
            echo -e "   cp \"$installed\" \"$repo\""
        done < "$TMPDIR_CS/diff_list"
    fi

    if [ "$MISSING_N" -gt 0 ]; then
        echo ""
        echo -e " ${RED}✗ Brak w instalacji:${NC}"
        while IFS='|' read -r type label repo installed; do
            echo -e "   ${RED}$label${NC}"
            echo -e "   ${GRAY}cp $installed \\\\${NC}"
            echo -e "   ${GRAY}    $repo${NC}"
            echo -e "   ${GRAY}   $installed${NC}"
            echo -e "   cp \"$installed\" \"$repo\""
        done < "$TMPDIR_CS/missing_list"
    fi
fi

echo -e "${BOLD}============================================================${NC}"

[ $(( DIFF_N + MISSING_N )) -eq 0 ] && exit 0 || exit 1
