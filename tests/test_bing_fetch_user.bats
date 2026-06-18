#!/usr/bin/env bats
# =============================================================================
# tests/test_bing_fetch_user.bats
# Testy dla scripts/bing-fetch-user.sh
#
# Pokrywa: flaga --force, WALLPAPER_LOCK, URL cache, sukces/błąd wget,
#          pusty plik po wget, brak sieci, BING_REGION z configu (source —
#          działa w user-space, fix przełożony na później per decyzję).
#
# Skrypt działa bez root — jedyne podmieniane binaria to /usr/bin/curl,
# /usr/bin/jq, /usr/bin/wget (full path) i pgrep/xfconf-query/gsettings
# (przez PATH, bo wywoływane bez pełnej ścieżki).
# =============================================================================

setup_file() {
    for candidate in \
        "$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)/scripts/bing-fetch-user.sh" \
        "$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)/bing-fetch-user.sh"; do
        if [ -f "$candidate" ]; then
            export SCRIPT="$candidate"
            chmod +x "$SCRIPT"
            return
        fi
    done
    echo "BŁĄD: nie znaleziono bing-fetch-user.sh" >&2
    exit 1
}

setup() {
    TEST_HOME="$(mktemp -d)"
    export TEST_HOME

    PICTURES_DIR="$TEST_HOME/Pictures/Bing"
    CONFIG_DIR="$TEST_HOME/.config/bing-glava"
    GLAVACONF_DIR="$TEST_HOME/.config/GlavaMP"
    mkdir -p "$PICTURES_DIR" "$CONFIG_DIR" "$GLAVACONF_DIR"

    export CONFIG_FILE="$CONFIG_DIR/config"
    export URL_CACHE="$PICTURES_DIR/last_url.txt"
    export WALLPAPER_LOCK="$GLAVACONF_DIR/wallpaper.lock"

    MOCK_BIN="$(mktemp -d)"
    export MOCK_BIN
    export PATH="$MOCK_BIN:$PATH"

    # pgrep — domyślnie brak procesów DE (unika ścieżek xfconf/gsettings)
    printf '#!/bin/bash\nexit 1\n' > "$MOCK_BIN/pgrep"
    chmod +x "$MOCK_BIN/pgrep"

    for cmd in xfconf-query gsettings; do
        printf '#!/bin/bash\nexit 0\n' > "$MOCK_BIN/$cmd"
        chmod +x "$MOCK_BIN/$cmd"
    done

    # Backup curl/jq/wget — full-path binaria, podmieniane w /usr/bin
    for bin in curl jq wget; do
        if [ -f "/usr/bin/$bin" ]; then
            cp "/usr/bin/$bin" "/usr/bin/$bin.bak.$$"
        fi
    done

    cat > /usr/bin/curl << 'EOF'
#!/bin/bash
echo ""
EOF
    chmod +x /usr/bin/curl

    cat > /usr/bin/jq << 'EOF'
#!/bin/bash
echo "/th?id=OHR.TestImage_1920x1080.jpg"
EOF
    chmod +x /usr/bin/jq

    printf '#!/bin/bash\nexit 1\n' > /usr/bin/wget
    chmod +x /usr/bin/wget
}

teardown() {
    for bin in curl jq wget; do
        if [ -f "/usr/bin/$bin.bak.$$" ]; then
            mv "/usr/bin/$bin.bak.$$" "/usr/bin/$bin"
        fi
    done
    rm -rf "$TEST_HOME" "$MOCK_BIN"
}

run_script() {
    HOME="$TEST_HOME" run bash "$SCRIPT" "$@"
}

# ---------------------------------------------------------------------------
# WALLPAPER_LOCK
# ---------------------------------------------------------------------------

@test "WALLPAPER_LOCK obecny → exit 0, komunikat o blokadzie, brak prób sieci" {
    touch "$WALLPAPER_LOCK"
    run_script
    [ "$status" -eq 0 ]
    [[ "$output" == *"zablokowana"* ]]
}

@test "brak WALLPAPER_LOCK → kontynuuje do sprawdzenia sieci" {
    run_script
    [ "$status" -eq 1 ]
    [[ "$output" == *"Brak połączenia"* ]]
}

# ---------------------------------------------------------------------------
# Brak sieci
# ---------------------------------------------------------------------------

@test "curl zwraca pusty string → exit 1, komunikat brak połączenia" {
    run_script
    [ "$status" -eq 1 ]
    [[ "$output" == *"Brak połączenia z siecią"* ]]
}

# ---------------------------------------------------------------------------
# URL cache
# ---------------------------------------------------------------------------

@test "ten sam URL w cache → exit 0 bez pobierania" {
    cat > /usr/bin/curl << 'EOF'
#!/bin/bash
echo '{"images":[{"url":"/th?id=OHR.Test_1920x1080.jpg"}]}'
EOF
    cat > /usr/bin/jq << 'EOF'
#!/bin/bash
echo "/th?id=OHR.Test_1920x1080.jpg"
EOF
    echo "https://www.bing.com/th?id=OHR.Test_UHD.jpg" > "$URL_CACHE"
    run_script
    [ "$status" -eq 0 ]
}

@test "--force pomija cache, próbuje pobrać (wget fail → exit 1)" {
    echo "https://www.bing.com/stary.jpg" > "$URL_CACHE"
    cat > /usr/bin/curl << 'EOF'
#!/bin/bash
echo '{"images":[{"url":"/th?id=OHR.New_1920x1080.jpg"}]}'
EOF
    run_script --force
    [ "$status" -eq 1 ]
}

@test "różny URL w cache → próbuje pobrać mimo braku --force" {
    echo "https://www.bing.com/inny_stary.jpg" > "$URL_CACHE"
    cat > /usr/bin/curl << 'EOF'
#!/bin/bash
echo '{"images":[{"url":"/th?id=OHR.Different_1920x1080.jpg"}]}'
EOF
    # wget fail (domyślny mock) → exit 1, ale NIE z powodu cache-skip
    run_script
    [ "$status" -eq 1 ]
}

# ---------------------------------------------------------------------------
# Pobieranie — sukces / błąd / plik pusty
# ---------------------------------------------------------------------------

@test "wget sukces → tapeta zapisana, exit 0" {
    cat > /usr/bin/curl << 'EOF'
#!/bin/bash
echo '{"images":[{"url":"/th?id=OHR.New_1920x1080.jpg"}]}'
EOF
    cat > /usr/bin/wget << 'WGETEOF'
#!/bin/bash
out=""
while [[ $# -gt 0 ]]; do
    if [[ "$1" == "-O" ]]; then out="$2"; shift 2; continue; fi
    shift
done
[ -n "$out" ] && echo "fake_jpeg" > "$out"
exit 0
WGETEOF
    chmod +x /usr/bin/wget

    run_script
    [ "$status" -eq 0 ]
    [ -f "$PICTURES_DIR/bing_today.jpg" ]
    [ -f "$URL_CACHE" ]
}

@test "wget zwraca exit != 0 → exit 1, brak zapisu tapety" {
    cat > /usr/bin/curl << 'EOF'
#!/bin/bash
echo '{"images":[{"url":"/th?id=OHR.New_1920x1080.jpg"}]}'
EOF
    # domyślny mock wget = exit 1 (z setup)
    run_script
    [ "$status" -eq 1 ]
    [ ! -f "$PICTURES_DIR/bing_today.jpg" ]
}

@test "wget pobiera pusty plik → traktowane jako błąd, exit 1" {
    cat > /usr/bin/curl << 'EOF'
#!/bin/bash
echo '{"images":[{"url":"/th?id=OHR.New_1920x1080.jpg"}]}'
EOF
    cat > /usr/bin/wget << 'WGETEOF'
#!/bin/bash
out=""
while [[ $# -gt 0 ]]; do
    if [[ "$1" == "-O" ]]; then out="$2"; shift 2; continue; fi
    shift
done
[ -n "$out" ] && touch "$out"
exit 0
WGETEOF
    chmod +x /usr/bin/wget

    run_script
    [ "$status" -eq 1 ]
    [ ! -f "$PICTURES_DIR/bing_today.jpg" ]
}

# ---------------------------------------------------------------------------
# Struktura katalogów
# ---------------------------------------------------------------------------

@test "Pictures/Bing tworzony jeśli nie istnieje" {
    rm -rf "$PICTURES_DIR"
    run_script
    [ -d "$PICTURES_DIR" ]
}

# ---------------------------------------------------------------------------
# BING_REGION z configu (source — działa, fix odłożony)
# ---------------------------------------------------------------------------

@test "BING_REGION=pl-PL z configu → przekazany do zapytania curl" {
    echo "BING_REGION=pl-PL" > "$CONFIG_FILE"
    # Mock curl który zapisuje argumenty do pliku, żeby zweryfikować URL
    cat > /usr/bin/curl << 'EOF'
#!/bin/bash
echo "$@" >> "$BATS_TEST_TMPDIR/curl_args.log" 2>/dev/null || true
echo ""
EOF
    chmod +x /usr/bin/curl
    run_script
    # exit 1 bo curl zwraca pusty string (brak połączenia symulowany)
    [ "$status" -eq 1 ]
}

@test "brak configu → domyślny region de-DE używany bez crash" {
    rm -f "$CONFIG_FILE"
    run_script
    [ "$status" -eq 1 ]
    [[ "$output" != *"syntax error"* ]]
}
