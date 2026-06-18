#!/usr/bin/env bats
# =============================================================================
# tests/test_glava_colorswitch.bats
# Testy dla scripts/glava-colorswitch
#
# Pokrywa: wejście w tryb czerwony (flaga + cp preset + pkill + restart),
#          wyjście z trybu czerwonego (flaga usunięta + wywołanie
#          glava-colors-auto), tworzenie katalogu CONFIG jeśli nie istnieje.
#
# glava-colors-auto jest wołane przez ścieżkę $HOME/.local/bin/ — mockujemy
# je jako osobny skrypt w tej lokalizacji, nie testujemy jego wnętrza tutaj
# (ma własne, odrębne testy).
# =============================================================================

setup_file() {
    for candidate in \
        "$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)/scripts/glava-colorswitch" \
        "$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)/glava-colorswitch"; do
        if [ -f "$candidate" ]; then
            export SCRIPT="$candidate"
            chmod +x "$SCRIPT"
            return
        fi
    done
    echo "BŁĄD: nie znaleziono glava-colorswitch" >&2
    exit 1
}

setup() {
    TEST_HOME="$(mktemp -d)"
    export TEST_HOME

    CONFIG_DIR="$TEST_HOME/.config/glava"
    mkdir -p "$CONFIG_DIR/graph" "$TEST_HOME/.local/bin"
    export CONFIG_DIR
    export FLAG="$CONFIG_DIR/red.shift"
    export REDFRAG="$CONFIG_DIR/graph_colors.frag"
    export LIVEFRAG="$CONFIG_DIR/graph/1.frag"
    export TEST_LOG="$TEST_HOME/calls.log"

    # WAŻNE: glava-colorswitch ma `export PATH=/usr/bin:/bin:/usr/local/bin`
    # na początku (zabezpieczenie przed nieczystym PATH z cron) — to
    # CAŁKOWICIE nadpisuje PATH ustawiony przez bats, więc mockowanie
    # pkill/glava przez katalog dopisany do PATH nie działa. Musimy
    # podmieniać te binaria fizycznie w /usr/bin, z bezpiecznym
    # backup/restore (nigdy rm przed potwierdzeniem backupu — patrz
    # incydent z test_build_glava_deb.bats).
    for bin in pkill glava; do
        if [ -e "/usr/bin/$bin" ]; then
            cp -a "/usr/bin/$bin" "/usr/bin/$bin.bak.$$"
        fi
    done
    printf '#!/bin/bash\nexit 0\n' > /usr/bin/pkill
    chmod +x /usr/bin/pkill
    cat > /usr/bin/glava << 'EOF'
#!/bin/bash
sleep 5 &
exit 0
EOF
    chmod +x /usr/bin/glava

    # Mock glava-colors-auto w $HOME/.local/bin/ — ścieżka hardkodowana
    # w skrypcie jako $HOME/.local/bin, nie podlega nadpisaniu PATH.
    cat > "$TEST_HOME/.local/bin/glava-colors-auto" << 'EOF'
#!/bin/bash
echo "GLAVA_COLORS_AUTO_CALLED" >> "$TEST_LOG"
exit 0
EOF
    chmod +x "$TEST_HOME/.local/bin/glava-colors-auto"

    echo "vec3 bottom = vec3(1.0, 0.0, 0.0);" > "$REDFRAG"
}

teardown() {
    # Bezpieczne przywracanie — backup jest warunkiem usunięcia, nigdy
    # odwrotnie. Jeśli backup nie istnieje, usuwamy tylko plik jednoznacznie
    # rozpoznany jako nasza fałszywka testowa.
    for bin in pkill glava; do
        if [ -e "/usr/bin/$bin.bak.$$" ]; then
            mv -f "/usr/bin/$bin.bak.$$" "/usr/bin/$bin"
        elif [ -e "/usr/bin/$bin" ]; then
            if head -c 20 "/usr/bin/$bin" 2>/dev/null | grep -q "^#!/bin/bash$"; then
                content=$(cat "/usr/bin/$bin" 2>/dev/null)
                if [[ "$content" == *"sleep 5"* ]] || [[ "$content" == "#!/bin/bash
exit 0" ]]; then
                    rm -f "/usr/bin/$bin"
                fi
            fi
        fi
    done
    rm -rf "$TEST_HOME" "$MOCK_BIN" 2>/dev/null
}

run_script() {
    HOME="$TEST_HOME" TEST_LOG="$TEST_LOG" run bash "$SCRIPT"
}

# ---------------------------------------------------------------------------
# Wejście w tryb czerwony (FLAG nie istnieje na starcie)
# ---------------------------------------------------------------------------

@test "brak FLAG → wejście w tryb czerwony: flaga ustawiona" {
    run_script
    [ "$status" -eq 0 ]
    [ -f "$FLAG" ]
}

@test "wejście w tryb czerwony → preset skopiowany do LIVEFRAG" {
    run_script
    [ "$status" -eq 0 ]
    [ -f "$LIVEFRAG" ]
    diff -q "$REDFRAG" "$LIVEFRAG"
}

@test "wejście w tryb czerwony → pkill wywołany przed restartem" {
    cp -a /usr/bin/pkill /usr/bin/pkill.tmpbak
    cat > /usr/bin/pkill << EOF
#!/bin/bash
echo "PKILL_CALLED \$@" >> "$TEST_HOME/calls.log"
exit 0
EOF
    chmod +x /usr/bin/pkill

    run_script
    mv -f /usr/bin/pkill.tmpbak /usr/bin/pkill

    [ "$status" -eq 0 ]
    grep -q "PKILL_CALLED -x glava" "$TEST_HOME/calls.log"
}

@test "wejście w tryb czerwony → glava --desktop wystartowane" {
    cp -a /usr/bin/glava /usr/bin/glava.tmpbak
    cat > /usr/bin/glava << EOF
#!/bin/bash
echo "GLAVA_STARTED \$@" >> "$TEST_HOME/calls.log"
sleep 5 &
exit 0
EOF
    chmod +x /usr/bin/glava

    run_script
    # glava-colorswitch woła `glava --desktop &` w tle — główny proces
    # skryptu (i `run_script`) może zakończyć się przed tym, jak podproces
    # w tle zdąży dopisać do logu. Krótkie oczekiwanie na plik/wpis.
    for i in $(seq 1 20); do
        [ -f "$TEST_HOME/calls.log" ] && grep -q "GLAVA_STARTED" "$TEST_HOME/calls.log" && break
        sleep 0.1
    done
    mv -f /usr/bin/glava.tmpbak /usr/bin/glava

    [ "$status" -eq 0 ]
    grep -q "GLAVA_STARTED --desktop" "$TEST_HOME/calls.log"
}

@test "wejście w tryb czerwony → glava-colors-auto NIE jest wywoływane" {
    run_script
    [ "$status" -eq 0 ]
    [ ! -f "$TEST_HOME/calls.log" ] || ! grep -q "GLAVA_COLORS_AUTO_CALLED" "$TEST_HOME/calls.log"
}

# ---------------------------------------------------------------------------
# Wyjście z trybu czerwonego (FLAG istnieje na starcie)
# ---------------------------------------------------------------------------

@test "FLAG istnieje → wyjście z trybu czerwonego: flaga usunięta" {
    touch "$FLAG"
    run_script
    [ "$status" -eq 0 ]
    [ ! -f "$FLAG" ]
}

@test "wyjście z trybu czerwonego → glava-colors-auto wywołane" {
    touch "$FLAG"
    run_script
    [ "$status" -eq 0 ]
    grep -q "GLAVA_COLORS_AUTO_CALLED" "$TEST_HOME/calls.log"
}

@test "wyjście z trybu czerwonego → pkill NIE jest wywoływane bezpośrednio przez colorswitch" {
    touch "$FLAG"
    cp -a /usr/bin/pkill /usr/bin/pkill.tmpbak
    cat > /usr/bin/pkill << EOF
#!/bin/bash
echo "PKILL_CALLED" >> "$TEST_HOME/calls.log"
exit 0
EOF
    chmod +x /usr/bin/pkill

    run_script
    mv -f /usr/bin/pkill.tmpbak /usr/bin/pkill

    [ "$status" -eq 0 ]
    # colorswitch sam nie woła pkill w branchu wyjścia — to deleguje do
    # glava-colors-auto (które jest tu mockiem, więc nie wywoła swojego
    # wewnętrznego pkill).
    [ ! -f "$TEST_HOME/calls.log" ] || ! grep -q "PKILL_CALLED" "$TEST_HOME/calls.log"
}

@test "wyjście z trybu czerwonego → glava --desktop NIE jest wywoływane bezpośrednio przez colorswitch" {
    touch "$FLAG"
    cp -a /usr/bin/glava /usr/bin/glava.tmpbak
    cat > /usr/bin/glava << EOF
#!/bin/bash
echo "GLAVA_STARTED_DIRECT" >> "$TEST_HOME/calls.log"
exit 0
EOF
    chmod +x /usr/bin/glava

    run_script
    mv -f /usr/bin/glava.tmpbak /usr/bin/glava

    [ "$status" -eq 0 ]
    [ ! -f "$TEST_HOME/calls.log" ] || ! grep -q "GLAVA_STARTED_DIRECT" "$TEST_HOME/calls.log"
}

# ---------------------------------------------------------------------------
# Struktura katalogów
# ---------------------------------------------------------------------------

@test "UWAGA architektoniczna: brak katalogu graph/ → cp zawodzi po cichu, skrypt mimo to kontynuuje (brak set -e)" {
    rm -rf "$CONFIG_DIR/graph"
    run_script
    # Skrypt NIE ma `set -e` i nie sprawdza exit code `cp` — błąd jest
    # po cichu ignorowany, a pkill/restart i tak się wykonują. To jest
    # ukryta zależność od tego, że GUI wcześniej stworzyło katalog graph/
    # (np. przy pierwszym przełączeniu na ten moduł). Dokumentujemy to
    # zachowanie, nie naprawiamy go tutaj.
    [ "$status" -eq 0 ]
    [ ! -f "$LIVEFRAG" ]
    [ -f "$FLAG" ]
}

@test "CONFIG katalog tworzony jeśli nie istnieje" {
    rm -rf "$CONFIG_DIR"
    # REDFRAG też przepadł wraz z CONFIG_DIR — musimy go odtworzyć po mkdir
    # ale skrypt sam robi tylko mkdir -p "$CONFIG", nie odtwarza REDFRAG.
    # Test sprawdza tylko że mkdir się wykonał bez crashu (cp może zawiednąć
    # na nieistniejącym REDFRAG, ale to nie jest celem tego testu).
    run_script
    [ -d "$CONFIG_DIR" ]
}

# ---------------------------------------------------------------------------
# Idempotencja
# ---------------------------------------------------------------------------

@test "dwa kolejne przebiegi (wejście→wyjście) odtwarzają stan: flaga usunięta" {
    run_script   # wejście
    [ "$status" -eq 0 ]
    [ -f "$FLAG" ]

    run_script   # wyjście
    [ "$status" -eq 0 ]
    [ ! -f "$FLAG" ]
}
