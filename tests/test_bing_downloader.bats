#!/usr/bin/env bats
# =============================================================================
# tests/test_bing_downloader.bats
# Testy dla scripts/bing-downloader.sh
#
# Uwaga techniczna: skrypt używa /usr/bin/curl i /usr/bin/jq (full path),
# więc nie można ich mockować przez PATH — testy uruchamiane jako root
# w CI, podmieniamy pliki w /usr/bin i ZAWSZE przywracamy oryginał w teardown,
# niezależnie od tego czy test nadpisał mock ponownie w swoim ciele.
# =============================================================================

setup_file() {
    for candidate in \
        "$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)/scripts/bing-downloader.sh" \
        "$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)/bing-downloader.sh"; do
        if [ -f "$candidate" ]; then
            export SCRIPT="$candidate"
            chmod +x "$SCRIPT"
            return
        fi
    done
    echo "BŁĄD: nie znaleziono bing-downloader.sh" >&2
    exit 1
}

setup() {
    TEST_HOME="$(mktemp -d)"
    export TEST_HOME

    PICTURES_DIR="$TEST_HOME/Pictures/Bing"
    THUMBS_DIR="$PICTURES_DIR/thumbs"
    CONFIG_DIR="$TEST_HOME/.config/bing-glava"
    GLAVACONF_DIR="$TEST_HOME/.config/GlavaMP"
    mkdir -p "$PICTURES_DIR" "$THUMBS_DIR" "$CONFIG_DIR" "$GLAVACONF_DIR"

    export CONFIG_FILE="$CONFIG_DIR/config"
    export LOCK_FILE="$GLAVACONF_DIR/wallpaper.lock"
    export URL_CACHE="$PICTURES_DIR/last_url.txt"

    MOCK_BIN="$(mktemp -d)"
    export MOCK_BIN
    export PATH="$MOCK_BIN:$PATH"

    # pgrep MUSI zwracać exit 1 (brak procesu) — inaczej skrypt wchodzi
    # do bloków XFCE/Cinnamon i próbuje wywołać `sudo`, którego nie ma w kontenerze CI.
    for cmd in chown chmod xfconf-query gsettings; do
        printf '#!/bin/bash\nexit 0\n' > "$MOCK_BIN/$cmd"
        chmod +x "$MOCK_BIN/$cmd"
    done
    printf '#!/bin/bash\nexit 1\n' > "$MOCK_BIN/pgrep"
    chmod +x "$MOCK_BIN/pgrep"

    cat > "$MOCK_BIN/getent" << GETENT_EOF
#!/bin/bash
echo "testuser:x:1000:1000::$TEST_HOME:/bin/bash"
GETENT_EOF
    chmod +x "$MOCK_BIN/getent"

    printf '#!/bin/bash\nexit 0\n' > "$MOCK_BIN/id"
    chmod +x "$MOCK_BIN/id"

    # Backup oryginałów /usr/bin/{curl,jq,wget} — ZAWSZE, niezależnie od testu.
    # PID jest stały w ramach jednego testu bats (setup/test/teardown),
    # więc backup zapisany tu i przywrócony w teardown nie koliduje między testami.
    for bin in curl jq wget; do
        if [ -f "/usr/bin/$bin" ]; then
            cp "/usr/bin/$bin" "/usr/bin/$bin.bak.$$"
        fi
    done

    # Domyślne mocki — brak sieci
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
    # Przywróć oryginalne binaria niezależnie od tego co test zrobił w środku
    for bin in curl jq wget; do
        if [ -f "/usr/bin/$bin.bak.$$" ]; then
            mv "/usr/bin/$bin.bak.$$" "/usr/bin/$bin"
        fi
    done
    rm -rf "$TEST_HOME" "$MOCK_BIN"
}

run_script() {
    run bash "$SCRIPT" "testuser" "$@"
}

# ---------------------------------------------------------------------------
# Walidacja argumentów
# ---------------------------------------------------------------------------

@test "brak argumentu użytkownika → exit 1 z komunikatem Użycie" {
    run bash "$SCRIPT"
    [ "$status" -eq 1 ]
    [[ "$output" == *"Użycie"* ]]
}

@test "nieistniejący użytkownik → exit 1" {
    printf '#!/bin/bash\nexit 1\n' > "$MOCK_BIN/id"
    run bash "$SCRIPT" "nieistniejacy_user_xyz"
    [ "$status" -eq 1 ]
    [[ "$output" == *"nie istnieje"* ]]
}

# ---------------------------------------------------------------------------
# Parsowanie BING_REGION — bezpieczeństwo (punkt 3)
# ---------------------------------------------------------------------------

@test "brak pliku config → exit 1 przez brak sieci (curl pusty)" {
    run_script --no-lightdm
    [ "$status" -eq 1 ]
    [[ "$output" == *"Brak połączenia"* ]]
}

@test "poprawny BING_REGION=pl-PL → akceptowany, exit przez brak sieci" {
    echo "BING_REGION=pl-PL" > "$CONFIG_FILE"
    run_script --no-lightdm
    [ "$status" -eq 1 ]
    [[ "$output" == *"Brak połączenia"* ]]
    [[ "$output" != *"syntax error"* ]]
}

@test "BING_REGION=invalid → ignorowany, fallback de-DE, brak crash" {
    echo "BING_REGION=invalid_region" > "$CONFIG_FILE"
    run_script --no-lightdm
    [ "$status" -eq 1 ]
    [[ "$output" != *"syntax error"* ]]
}

@test "injection w BING_REGION → nie wykonuje się" {
    echo "BING_REGION=de-DE; echo INJECTED_MARKER" > "$CONFIG_FILE"
    run_script --no-lightdm
    [[ "$output" != *"INJECTED_MARKER"* ]]
}

@test "BING_REGION z cudzysłowami → ignorowany przez regex, brak crash" {
    printf 'BING_REGION="pl-PL"\n' > "$CONFIG_FILE"
    run_script --no-lightdm
    [ "$status" -eq 1 ]
    [[ "$output" != *"syntax error"* ]]
}

@test "BING_REGION z backslashem → ignorowany przez regex" {
    printf 'BING_REGION=de-DE\\\necho INJECTED\n' > "$CONFIG_FILE"
    run_script --no-lightdm
    [[ "$output" != *"INJECTED"* ]]
}

@test "wszystkie poprawne locale (en-US, ja-JP, zh-CN) → akceptowane" {
    for region in en-US ja-JP zh-CN pt-BR fr-FR; do
        echo "BING_REGION=$region" > "$CONFIG_FILE"
        run_script --no-lightdm
        [ "$status" -eq 1 ]
        [[ "$output" != *"syntax error"* ]]
    done
}

# ---------------------------------------------------------------------------
# LOCK_FILE
# ---------------------------------------------------------------------------

@test "LOCK_FILE obecny → exit 0, nie pobiera tapety" {
    touch "$LOCK_FILE"
    run_script --no-lightdm
    [ "$status" -eq 0 ]
    [[ "$output" != *"Brak połączenia"* ]]
}

@test "brak LOCK_FILE → kontynuuje, exit 1 przez brak sieci" {
    run_script --no-lightdm
    [ "$status" -eq 1 ]
    [[ "$output" == *"Brak połączenia"* ]]
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
    run_script --no-lightdm
    [ "$status" -eq 0 ]
}

@test "flaga --force → pomija cache, próbuje pobrać (wget fail → exit 1)" {
    echo "https://www.bing.com/stary_url.jpg" > "$URL_CACHE"
    cat > /usr/bin/curl << 'EOF'
#!/bin/bash
echo '{"images":[{"url":"/th?id=OHR.NewImage_1920x1080.jpg"}]}'
EOF
    run_script --no-lightdm --force
    [ "$status" -eq 1 ]
    [[ "$output" == *"Błąd pobierania"* ]]
}

# ---------------------------------------------------------------------------
# Pobieranie tapety — pełny happy path
# ---------------------------------------------------------------------------

@test "wget sukces → tapeta zapisana, exit 0" {
    cat > /usr/bin/curl << 'EOF'
#!/bin/bash
echo '{"images":[{"url":"/th?id=OHR.NewImage_1920x1080.jpg"}]}'
EOF
    cat > /usr/bin/jq << 'EOF'
#!/bin/bash
echo "/th?id=OHR.NewImage_1920x1080.jpg"
EOF
    cat > /usr/bin/wget << 'WGETEOF'
#!/bin/bash
out=""
while [[ $# -gt 0 ]]; do
    if [[ "$1" == "-O" ]]; then out="$2"; shift 2; continue; fi
    shift
done
[ -n "$out" ] && echo "fake_jpeg_data" > "$out"
exit 0
WGETEOF
    chmod +x /usr/bin/wget

    run_script --no-lightdm
    [ "$status" -eq 0 ]
    [ -f "$TEST_HOME/Pictures/Bing/bing_today.jpg" ]
}

@test "wget zapisuje pusty plik → traktowane jako błąd, exit 1" {
    cat > /usr/bin/curl << 'EOF'
#!/bin/bash
echo '{"images":[{"url":"/th?id=OHR.NewImage_1920x1080.jpg"}]}'
EOF
    cat > /usr/bin/jq << 'EOF'
#!/bin/bash
echo "/th?id=OHR.NewImage_1920x1080.jpg"
EOF
    cat > /usr/bin/wget << 'WGETEOF'
#!/bin/bash
out=""
while [[ $# -gt 0 ]]; do
    if [[ "$1" == "-O" ]]; then out="$2"; shift 2; continue; fi
    shift
done
# Tworzy plik, ale pusty (symulacja przerwanego pobierania)
[ -n "$out" ] && touch "$out"
exit 0
WGETEOF
    chmod +x /usr/bin/wget

    run_script --no-lightdm
    [ "$status" -eq 1 ]
    [[ "$output" == *"pusty"* ]]
}

# ---------------------------------------------------------------------------
# Struktura katalogów
# ---------------------------------------------------------------------------

@test "skrypt tworzy Pictures/Bing i thumbs/ jeśli nie istnieją" {
    rm -rf "$TEST_HOME/Pictures"
    run_script --no-lightdm
    [ -d "$TEST_HOME/Pictures/Bing" ]
    [ -d "$TEST_HOME/Pictures/Bing/thumbs" ]
}
