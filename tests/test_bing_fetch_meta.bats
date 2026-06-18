#!/usr/bin/env bats
# =============================================================================
# tests/test_bing_fetch_meta.bats
# Testy dla scripts/bing-fetch-meta.sh
#
# Pokrywa: domyślny TARGET_USER (whoami), brak sieci (early exit 0),
#          pętla po regionach (brak odpowiedzi → skip), pobieranie miniatur
#          (nowa vs aktualna), czyszczenie starych miniatur, zapis metadata.json.
#
# Skrypt działa bez root, używa curl/jq BEZ pełnej ścieżki (przez PATH) —
# w przeciwieństwie do bing-downloader.sh. To ułatwia mockowanie: wystarczy
# PATH, bez podmiany /usr/bin.
# =============================================================================

setup_file() {
    for candidate in \
        "$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)/scripts/bing-fetch-meta.sh" \
        "$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)/bing-fetch-meta.sh"; do
        if [ -f "$candidate" ]; then
            export SCRIPT="$candidate"
            chmod +x "$SCRIPT"
            return
        fi
    done
    echo "BŁĄD: nie znaleziono bing-fetch-meta.sh" >&2
    exit 1
}

setup() {
    TEST_HOME="$(mktemp -d)"
    export TEST_HOME

    PICTURES_DIR="$TEST_HOME/Pictures/Bing"
    THUMBS_DIR="$PICTURES_DIR/thumbs"
    mkdir -p "$THUMBS_DIR"
    export PICTURES_DIR THUMBS_DIR
    export META_FILE="$PICTURES_DIR/metadata.json"

    MOCK_BIN="$(mktemp -d)"
    export MOCK_BIN
    export PATH="$MOCK_BIN:$PATH"

    # getent — zwraca TEST_HOME dla dowolnego użytkownika podanego jako arg
    cat > "$MOCK_BIN/getent" << GETENT_EOF
#!/bin/bash
echo "\$2:x:1000:1000::$TEST_HOME:/bin/bash"
GETENT_EOF
    chmod +x "$MOCK_BIN/getent"

    # curl — skrypt wywołuje DWA różne sposoby:
    # 1) curl -s connect-timeout 5 "https://www.bing.com" (sprawdzenie sieci, brak -o)
    # 2) curl -s connect-timeout 10 "...HPImageArchive..." (JSON per region)
    # 3) curl -s connect-timeout 10 -o file URL (pobranie miniatury)
    # Domyślnie: sieć "działa", JSON pusty (brak odpowiedzi per region)
    cat > "$MOCK_BIN/curl" << 'EOF'
#!/bin/bash
# Wykryj tryb -o (pobranie do pliku)
out=""
args=("$@")
for ((i=0; i<${#args[@]}; i++)); do
    if [[ "${args[$i]}" == "-o" ]]; then
        out="${args[$((i+1))]}"
    fi
done
if [[ "$*" == *"www.bing.com\""* ]] && [[ "$*" != *"HPImageArchive"* ]] && [ -z "$out" ]; then
    # Sprawdzenie samej dostępności bing.com (curl -s ... "https://www.bing.com")
    exit 0
fi
if [ -n "$out" ]; then
    # Pobranie miniatury — domyślnie nic nie zapisujemy (puste/błąd)
    exit 0
fi
echo ""
EOF
    chmod +x "$MOCK_BIN/curl"
}

teardown() {
    rm -rf "$TEST_HOME" "$MOCK_BIN"
}

run_script() {
    run bash "$SCRIPT" "testuser"
}

# ---------------------------------------------------------------------------
# Domyślny TARGET_USER
# ---------------------------------------------------------------------------

@test "brak argumentu → TARGET_USER z whoami, nie crashuje" {
    run bash "$SCRIPT"
    # Status zależy od realnego $HOME bieżącego usera w kontenerze — sprawdzamy
    # tylko że się nie wywaliło z błędem składni / brakiem zmiennej.
    [[ "$output" != *"unbound variable"* ]]
}

# ---------------------------------------------------------------------------
# Brak sieci — early exit
# ---------------------------------------------------------------------------

@test "brak połączenia z bing.com → exit 0, komunikat, brak pętli regionów" {
    cat > "$MOCK_BIN/curl" << 'EOF'
#!/bin/bash
exit 1
EOF
    chmod +x "$MOCK_BIN/curl"

    run_script
    [ "$status" -eq 0 ]
    [[ "$output" == *"Brak polaczenia"* ]]
    [[ "$output" != *"Odpytuję"* ]]
}

@test "sieć dostępna → kontynuuje do pętli regionów" {
    run_script
    [ "$status" -eq 0 ]
    [[ "$output" == *"Odpytuję: de-DE"* ]]
}

# ---------------------------------------------------------------------------
# Pętla regionów — brak odpowiedzi
# ---------------------------------------------------------------------------

@test "wszystkie regiony bez odpowiedzi → log skip dla każdego, plik metadata zapisany" {
    run_script
    [ "$status" -eq 0 ]
    [[ "$output" == *"Brak odpowiedzi dla de-DE"* ]]
    [[ "$output" == *"Brak odpowiedzi dla pl-PL"* ]]
    [ -f "$META_FILE" ]
}

@test "wszystkie 10 regionów Bing są odpytywane" {
    run_script
    for region in de-DE en-US en-GB fr-FR es-ES it-IT pt-BR ja-JP zh-CN pl-PL; do
        [[ "$output" == *"Odpytuję: $region"* ]]
    done
}

# ---------------------------------------------------------------------------
# Pełny happy path — JSON z danymi
# ---------------------------------------------------------------------------

@test "region z poprawnym JSON → urlbase sparsowane, próba pobrania miniatury" {
    cat > "$MOCK_BIN/curl" << 'EOF'
#!/bin/bash
args=("$@")
out=""
for ((i=0; i<${#args[@]}; i++)); do
    if [[ "${args[$i]}" == "-o" ]]; then out="${args[$((i+1))]}"; fi
done
if [[ "$*" == *"HPImageArchive"* ]]; then
    echo '{"images":[{"title":"Test","copyright":"(c) Test","startdate":"20260601","enddate":"20260602","urlbase":"/th?id=OHR.TestImg_EN-US1920x1080"}]}'
    exit 0
fi
if [ -n "$out" ]; then
    echo "fake_thumb_data" > "$out"
    exit 0
fi
exit 0
EOF
    chmod +x "$MOCK_BIN/curl"

    run_script
    [ "$status" -eq 0 ]
    [[ "$output" == *"Pobieram miniaturę: OHR.TestImg"* ]]
    [ -f "$META_FILE" ]
    grep -q "OHR.TestImg" "$META_FILE"
}

@test "urlbase brak pola → region pominięty z komunikatem" {
    cat > "$MOCK_BIN/curl" << 'EOF'
#!/bin/bash
if [[ "$*" == *"HPImageArchive"* ]]; then
    echo '{"images":[{"title":"NoUrlbase"}]}'
    exit 0
fi
exit 0
EOF
    chmod +x "$MOCK_BIN/curl"

    run_script
    [ "$status" -eq 0 ]
    [[ "$output" == *"Brak urlbase"* ]]
}

# ---------------------------------------------------------------------------
# Pominięcie pobierania miniatury gdy image_id się nie zmienił
# ---------------------------------------------------------------------------

@test "ten sam image_id i plik miniatury istnieje → miniatura nie jest ponownie pobierana" {
    # Pre-seed metadata.json z istniejącym image_id dla de-DE
    cat > "$META_FILE" << 'EOF'
{"de-DE": {"image_id": "OHR.Existing", "thumb_file": "thumb_path"}}
EOF
    # THUMB_ID = urlbase po usunięciu prefiksu "/th?id=" (sed), więc dla
    # urlbase="/th?id=OHR.Existing" plik to thumbs/OHR.Existing_320x180.jpg
    THUMB_PATH="$THUMBS_DIR/OHR.Existing_320x180.jpg"
    touch "$THUMB_PATH"

    cat > "$MOCK_BIN/curl" << 'EOF'
#!/bin/bash
if [[ "$*" == *"HPImageArchive"*"de-DE"* ]]; then
    echo '{"images":[{"title":"X","urlbase":"/th?id=OHR.Existing"}]}'
    exit 0
fi
if [[ "$*" == *"HPImageArchive"* ]]; then
    exit 0
fi
exit 0
EOF
    chmod +x "$MOCK_BIN/curl"

    run_script
    [ "$status" -eq 0 ]
    [[ "$output" == *"Miniatura aktualna: OHR.Existing"* ]]
}

# ---------------------------------------------------------------------------
# Struktura katalogów
# ---------------------------------------------------------------------------

@test "thumbs/ tworzony jeśli nie istnieje" {
    rm -rf "$THUMBS_DIR"
    run_script
    [ -d "$THUMBS_DIR" ]
}

@test "brak metadata.json na starcie → traktowane jako {}, nie crashuje" {
    rm -f "$META_FILE"
    run_script
    [ "$status" -eq 0 ]
    [ -f "$META_FILE" ]
}
