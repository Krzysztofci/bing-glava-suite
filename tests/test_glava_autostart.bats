#!/usr/bin/env bats
# =============================================================================
# tests/test_glava_autostart.bats
# Testy dla scripts/glava-autostart.sh
#
# Pokrywa: flaga .glava_disabled, brak instances.json (fallback domyślny),
#          uszkodzony instances.json (fallback domyślny), pusta lista instancji,
#          pomijanie instancji z brakującym katalogiem config, zapis PID,
#          fallback gdy żadna instancja nie wystartowała, izolacja XDG_CONFIG_HOME
#          dla inst_id>0 vs inst_id=0.
#
# Skrypt działa w przestrzeni użytkownika (bez root) — mockujemy tylko `glava`
# przez PATH, bo to jedyny zewnętrzny binarz.
# =============================================================================

setup_file() {
    for candidate in \
        "$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)/scripts/glava-autostart.sh" \
        "$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)/glava-autostart.sh"; do
        if [ -f "$candidate" ]; then
            export SCRIPT="$candidate"
            chmod +x "$SCRIPT"
            return
        fi
    done
    echo "BŁĄD: nie znaleziono glava-autostart.sh" >&2
    exit 1
}

setup() {
    # Izolowany $HOME — skrypt czyta $HOME/.config/GlavaMP/instances.json
    # i pisze do $HOME/.local/logs/glava-autostart.log
    TEST_HOME="$(mktemp -d)"
    export TEST_HOME
    mkdir -p "$TEST_HOME/.config/GlavaMP" "$TEST_HOME/.local/logs"

    INSTANCES_FILE="$TEST_HOME/.config/GlavaMP/instances.json"
    LOG_FILE="$TEST_HOME/.local/logs/glava-autostart.log"
    DISABLE_FLAG="$TEST_HOME/.config/GlavaMP/.glava_disabled"
    export INSTANCES_FILE LOG_FILE DISABLE_FLAG

    MOCK_BIN="$(mktemp -d)"
    export MOCK_BIN
    export PATH="$MOCK_BIN:$PATH"

    # Mock glava — domyślnie "działa", zwraca natychmiast (symulacja procesu w tle)
    # Faktyczny proces pozostaje żywy na tyle długo by Popen go zarejestrował.
    cat > "$MOCK_BIN/glava" << 'EOF'
#!/bin/bash
sleep 5 &
exit 0
EOF
    chmod +x "$MOCK_BIN/glava"
}

teardown() {
    rm -rf "$TEST_HOME" "$MOCK_BIN"
}

run_script() {
    HOME="$TEST_HOME" run bash "$SCRIPT"
}

# ---------------------------------------------------------------------------
# glava niedostępne w PATH
# ---------------------------------------------------------------------------

@test "glava niedostępne w PATH → exit 1, log błędu" {
    rm -f "$MOCK_BIN/glava"
    # Filtrowanie PATH po katalogach jest błędne: jeśli `glava` jest
    # zainstalowana w /usr/bin (typowa lokalizacja), usunięcie tego katalogu
    # z PATH zabiera też mkdir/date/python3/bash — skrypt pada z exit 127
    # ("command not found"), zanim dojdzie do sprawdzenia samej glava.
    #
    # Właściwe podejście: wstrzykujemy do bash funkcję `command`, która
    # przechwytuje wyłącznie zapytanie o `glava` i kłamie że jej nie ma,
    # przepuszczając wszystkie inne wywołania do prawdziwego builtina.
    # Działa niezależnie od tego, czy i gdzie glava jest naprawdę zainstalowana.
    run env HOME="$TEST_HOME" bash -c '
        command() {
            if [ "$1" = "-v" ] && [ "$2" = "glava" ]; then
                return 1
            fi
            builtin command "$@"
        }
        export -f command
        bash "'"$SCRIPT"'"
    '
    [ "$status" -eq 1 ]
    [[ "$(cat "$LOG_FILE")" == *"glava not found in PATH"* ]]
}

# ---------------------------------------------------------------------------
# Flaga .glava_disabled
# ---------------------------------------------------------------------------

@test ".glava_disabled obecny → skrypt nie startuje żadnej instancji" {
    mkdir -p "$TEST_HOME/.config/glava"
    cat > "$INSTANCES_FILE" << 'EOF'
[{"inst_id": 0, "module": "bars", "active": true}]
EOF
    touch "$DISABLE_FLAG"

    run_script
    [ "$status" -eq 0 ]
    # Logika disabled jest WEWNĄTRZ heredoc pythona, więc samo bash exit 0,
    # ale log musi pokazać że autostart był wstrzymany.
    [[ "$(cat "$LOG_FILE")" == *"disabled"* ]] || [[ "$(cat "$LOG_FILE")" == *"skipping autostart"* ]]
}

@test "brak .glava_disabled → autostart kontynuuje normalnie" {
    mkdir -p "$TEST_HOME/.config/glava"
    cat > "$INSTANCES_FILE" << 'EOF'
[{"inst_id": 0, "module": "bars", "active": true}]
EOF
    run_script
    [ "$status" -eq 0 ]
    [[ "$(cat "$LOG_FILE")" != *"disabled"* ]]
}

# ---------------------------------------------------------------------------
# Brak instances.json
# ---------------------------------------------------------------------------

@test "brak instances.json → fallback do domyślnej instancji (bash poziom)" {
    rm -f "$INSTANCES_FILE"
    run_script
    [ "$status" -eq 0 ]
    [[ "$(cat "$LOG_FILE")" == *"no instances.json"* ]]
}

# ---------------------------------------------------------------------------
# Uszkodzony / pusty instances.json
# ---------------------------------------------------------------------------

@test "uszkodzony JSON w instances.json → fallback, log błędu odczytu" {
    mkdir -p "$TEST_HOME/.config/glava"
    echo "{ to nie jest poprawny json" > "$INSTANCES_FILE"
    run_script
    [ "$status" -eq 0 ]
    [[ "$(cat "$LOG_FILE")" == *"failed to read instances.json"* ]]
}

@test "pusta lista instancji [] → log 'nothing to start', brak fallbacku" {
    echo "[]" > "$INSTANCES_FILE"
    run_script
    [ "$status" -eq 0 ]
    [[ "$(cat "$LOG_FILE")" == *"nothing to start"* ]]
}

# ---------------------------------------------------------------------------
# Pomijanie instancji z brakującym katalogiem config
# ---------------------------------------------------------------------------

@test "katalog config dla inst_id nie istnieje → instancja pominięta, log skip" {
    # Nie tworzymy ~/.config/glava — inst_id=0 będzie pominięte
    cat > "$INSTANCES_FILE" << 'EOF'
[{"inst_id": 0, "module": "bars", "active": true}]
EOF
    run_script
    [ "$status" -eq 0 ]
    [[ "$(cat "$LOG_FILE")" == *"config dir missing"* ]]
    [[ "$(cat "$LOG_FILE")" == *"skipping"* ]]
}

@test "inst_id>0 sprawdza katalog glava-inst-{id}, nie domyślny ~/.config/glava" {
    # Tworzymy TYLKO katalog dla inst_id=2, nie dla inst_id=0
    mkdir -p "$TEST_HOME/.config/glava-inst-2/glava"
    cat > "$INSTANCES_FILE" << 'EOF'
[{"inst_id": 0, "module": "bars", "active": true},
 {"inst_id": 2, "module": "wave", "active": true}]
EOF
    run_script
    [ "$status" -eq 0 ]
    # inst_id=0 pominięte (brak ~/.config/glava)
    [[ "$(cat "$LOG_FILE")" == *"inst 0: config dir missing"* ]]
    # inst_id=2 wystartowane (katalog istnieje)
    [[ "$(cat "$LOG_FILE")" == *"inst 2: started"* ]]
}

# ---------------------------------------------------------------------------
# Start instancji i zapis PID
# ---------------------------------------------------------------------------

@test "instancja z istniejącym katalogiem config → start + log z PID" {
    mkdir -p "$TEST_HOME/.config/glava"
    cat > "$INSTANCES_FILE" << 'EOF'
[{"inst_id": 0, "module": "bars", "active": true}]
EOF
    run_script
    [ "$status" -eq 0 ]
    [[ "$(cat "$LOG_FILE")" == *"inst 0: started (module=bars"* ]]
    [[ "$(cat "$LOG_FILE")" == *"started 1 instance"* ]]
}

@test "uruchomiona instancja zapisuje plik PID w GlavaMP/inst-{id}.pid" {
    mkdir -p "$TEST_HOME/.config/glava"
    cat > "$INSTANCES_FILE" << 'EOF'
[{"inst_id": 0, "module": "bars", "active": true}]
EOF
    run_script
    [ "$status" -eq 0 ]
    [ -f "$TEST_HOME/.config/GlavaMP/inst-0.pid" ]
    # PID powinien być liczbą
    pid_content=$(cat "$TEST_HOME/.config/GlavaMP/inst-0.pid")
    [[ "$pid_content" =~ ^[0-9]+$ ]]
}

@test "wiele instancji → każda dostaje własny plik PID" {
    mkdir -p "$TEST_HOME/.config/glava" "$TEST_HOME/.config/glava-inst-3/glava"
    cat > "$INSTANCES_FILE" << 'EOF'
[{"inst_id": 0, "module": "bars", "active": true},
 {"inst_id": 3, "module": "circle", "active": true}]
EOF
    run_script
    [ "$status" -eq 0 ]
    [ -f "$TEST_HOME/.config/GlavaMP/inst-0.pid" ]
    [ -f "$TEST_HOME/.config/GlavaMP/inst-3.pid" ]
}

# ---------------------------------------------------------------------------
# Fallback gdy żadna instancja nie wystartowała
# ---------------------------------------------------------------------------

@test "wszystkie instancje pominięte (brak katalogów) → fallback do domyślnej" {
    # Brak ~/.config/glava i brak glava-inst-N dla podanych ID
    cat > "$INSTANCES_FILE" << 'EOF'
[{"inst_id": 5, "module": "bars", "active": true}]
EOF
    run_script
    [ "$status" -eq 0 ]
    [[ "$(cat "$LOG_FILE")" == *"inst 5: config dir missing"* ]]
    [[ "$(cat "$LOG_FILE")" == *"no instances started, falling back to default"* ]]
}

# ---------------------------------------------------------------------------
# Domyślny moduł "bars" gdy brak pola module
# ---------------------------------------------------------------------------

@test "instancja bez pola module → domyślnie używa 'bars' w logu" {
    mkdir -p "$TEST_HOME/.config/glava"
    cat > "$INSTANCES_FILE" << 'EOF'
[{"inst_id": 0, "active": true}]
EOF
    run_script
    [ "$status" -eq 0 ]
    [[ "$(cat "$LOG_FILE")" == *"module=bars"* ]]
}

# ---------------------------------------------------------------------------
# Tworzenie katalogu logów jeśli nie istnieje
# ---------------------------------------------------------------------------

@test "katalog .local/logs nieistniejący → tworzony automatycznie" {
    rm -rf "$TEST_HOME/.local/logs"
    cat > "$INSTANCES_FILE" << 'EOF'
[]
EOF
    run_script
    [ "$status" -eq 0 ]
    [ -d "$TEST_HOME/.local/logs" ]
    [ -f "$LOG_FILE" ]
}
