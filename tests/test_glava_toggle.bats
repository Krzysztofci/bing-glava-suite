#!/usr/bin/env bats
# =============================================================================
# tests/test_glava_toggle.bats
# Testy dla scripts/glava-toggle
#
# Pokrywa: toggle OFF (gdy glava działa → pkill + touch flag),
#          toggle ON (gdy glava nie działa → rm flag + start),
#          flaga .glava_disabled tworzona/usuwana w odpowiednich momentach.
#
# UWAGA architektoniczna: ten skrypt jest single-instance (operuje na
# ~/.config/glava/.glava_disabled, jeden globalny pkill -x glava) — taki
# sam wzorzec jak glava-colors-auto i glava-colorswitch. Testy weryfikują
# zachowanie TAKIE JAKIE JEST, nie oceniają architektury.
# =============================================================================

setup_file() {
    for candidate in \
        "$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)/scripts/glava-toggle" \
        "$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)/glava-toggle"; do
        if [ -f "$candidate" ]; then
            export SCRIPT="$candidate"
            chmod +x "$SCRIPT"
            return
        fi
    done
    echo "BŁĄD: nie znaleziono glava-toggle" >&2
    exit 1
}

setup() {
    TEST_HOME="$(mktemp -d)"
    export TEST_HOME
    mkdir -p "$TEST_HOME/.config/glava"
    export FLAG="$TEST_HOME/.config/glava/.glava_disabled"

    MOCK_BIN="$(mktemp -d)"
    export MOCK_BIN
    export PATH="$MOCK_BIN:$PATH"

    # Domyślnie: glava NIE działa (pgrep fail), pkill no-op
    printf '#!/bin/bash\nexit 1\n' > "$MOCK_BIN/pgrep"
    chmod +x "$MOCK_BIN/pgrep"
    printf '#!/bin/bash\nexit 0\n' > "$MOCK_BIN/pkill"
    chmod +x "$MOCK_BIN/pkill"

    # Mock glava — startuje i "działa" w tle (nie blokuje testu)
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
# Toggle OFF — glava aktualnie działa
# ---------------------------------------------------------------------------

@test "glava działa (pgrep sukces) → toggle OFF: pkill wywołany, flaga ustawiona" {
    printf '#!/bin/bash\nexit 0\n' > "$MOCK_BIN/pgrep"

    # Śledzimy czy pkill faktycznie został wywołany
    cat > "$MOCK_BIN/pkill" << EOF
#!/bin/bash
echo "PKILL_CALLED \$@" >> "$TEST_HOME/calls.log"
exit 0
EOF
    chmod +x "$MOCK_BIN/pkill"

    run_script
    [ "$status" -eq 0 ]
    [ -f "$FLAG" ]
    grep -q "PKILL_CALLED -x glava" "$TEST_HOME/calls.log"
}

@test "toggle OFF nie wywołuje glava --desktop (nie startuje nowego procesu)" {
    printf '#!/bin/bash\nexit 0\n' > "$MOCK_BIN/pgrep"

    cat > "$MOCK_BIN/glava" << EOF
#!/bin/bash
echo "GLAVA_STARTED" >> "$TEST_HOME/calls.log"
exit 0
EOF
    chmod +x "$MOCK_BIN/glava"

    run_script
    [ "$status" -eq 0 ]
    [ ! -f "$TEST_HOME/calls.log" ] || ! grep -q "GLAVA_STARTED" "$TEST_HOME/calls.log"
}

# ---------------------------------------------------------------------------
# Toggle ON — glava nie działa
# ---------------------------------------------------------------------------

@test "glava nie działa (pgrep fail) → toggle ON: flaga usunięta, glava wystartowana" {
    printf '#!/bin/bash\nexit 1\n' > "$MOCK_BIN/pgrep"
    touch "$FLAG"   # flaga istnieje z poprzedniego stanu OFF

    cat > "$MOCK_BIN/glava" << EOF
#!/bin/bash
echo "GLAVA_STARTED \$@" >> "$TEST_HOME/calls.log"
sleep 5 &
exit 0
EOF
    chmod +x "$MOCK_BIN/glava"

    run_script
    [ "$status" -eq 0 ]
    [ ! -f "$FLAG" ]
    grep -q "GLAVA_STARTED --desktop" "$TEST_HOME/calls.log"
}

@test "toggle ON nie wywołuje pkill" {
    printf '#!/bin/bash\nexit 1\n' > "$MOCK_BIN/pgrep"

    cat > "$MOCK_BIN/pkill" << EOF
#!/bin/bash
echo "PKILL_CALLED" >> "$TEST_HOME/calls.log"
exit 0
EOF
    chmod +x "$MOCK_BIN/pkill"

    run_script
    [ "$status" -eq 0 ]
    [ ! -f "$TEST_HOME/calls.log" ] || ! grep -q "PKILL_CALLED" "$TEST_HOME/calls.log"
}

@test "toggle ON gdy flaga nie istniała wcześniej → brak błędu (rm -f jest bezpieczny)" {
    printf '#!/bin/bash\nexit 1\n' > "$MOCK_BIN/pgrep"
    # Brak pliku FLAG na starcie
    run_script
    [ "$status" -eq 0 ]
    [ ! -f "$FLAG" ]
}

# ---------------------------------------------------------------------------
# Idempotencja / kolejne przebiegi
# ---------------------------------------------------------------------------

@test "dwa kolejne toggle (OFF→ON) odtwarzają stan: flaga usunięta na końcu" {
    # Pierwszy przebieg: glava działa → OFF
    printf '#!/bin/bash\nexit 0\n' > "$MOCK_BIN/pgrep"
    run_script
    [ "$status" -eq 0 ]
    [ -f "$FLAG" ]

    # Drugi przebieg: teraz glava "nie działa" → ON
    printf '#!/bin/bash\nexit 1\n' > "$MOCK_BIN/pgrep"
    run_script
    [ "$status" -eq 0 ]
    [ ! -f "$FLAG" ]
}
