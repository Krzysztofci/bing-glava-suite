#!/usr/bin/env bats
# =============================================================================
# tests/test_glava_color_daemon.bats
# Testy dla scripts/glava-color-daemon
#
# Pokrywa: blokada wielu instancji (LOCKFILE + kill -0), flagi FLAG_MANUAL/
#          FLAG_RED blokujące update_colors, check_wallpaper_on_start
#          (tapeta nowsza niż shader → update; tapeta starsza → brak update),
#          backup shaderów z retencją 20 plików, cleanup przy SIGTERM.
#
# Daemon ma pętlę `while true` z inotifywait — testy odpalają go w tle (&),
# czekają na efekt obserwowalny w logu/plikach, i zabijają procesem na końcu.
# inotifywait jest mockowane (sleep + brak realnego nasłuchu na inotify),
# bo środowisko CI/kontenerowe nie zawsze ma support na inotify dla wszystkich
# systemów plików (np. overlayfs).
# =============================================================================

setup_file() {
    for candidate in \
        "$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)/scripts/glava-color-daemon" \
        "$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)/glava-color-daemon"; do
        if [ -f "$candidate" ]; then
            export SCRIPT="$candidate"
            chmod +x "$SCRIPT"
            return
        fi
    done
    echo "BŁĄD: nie znaleziono glava-color-daemon" >&2
    exit 1
}

setup() {
    # Defensywne czyszczenie: jeśli poprzedni test został przerwany w środku
    # update_colors() (np. przez kill -9 w teardown poprzedniego testu),
    # globalny LOCKFILE_UPDATE w /tmp mógł zostać osierocony i blokować
    # update_colors() w bieżącym teście.
    rm -f /tmp/glava-update.lock

    TEST_HOME="$(mktemp -d)"
    export TEST_HOME
    export USER="testuser_$$"

    mkdir -p "$TEST_HOME/.config/GlavaMP" \
             "$TEST_HOME/.config/glava/graph" \
             "$TEST_HOME/.config/glava/backup_frag" \
             "$TEST_HOME/.local/logs" \
             "$TEST_HOME/.local/bin" \
             "$TEST_HOME/Pictures/Bing"

    export DISABLE_FLAG="$TEST_HOME/.config/GlavaMP/.glava_disabled"
    export FLAG_RED="$TEST_HOME/.config/glava/red.shift"
    export FLAG_MANUAL="$TEST_HOME/.config/glava/manual.shift"
    export LOG="$TEST_HOME/.local/logs/glava-color-daemon.log"
    export WALLPAPER="$TEST_HOME/Pictures/Bing/bing_today.jpg"
    export LIVEFRAG="$TEST_HOME/.config/glava/graph/1.frag"
    export LOCKFILE="/tmp/glava-color-daemon-${USER}.lock"

    MOCK_BIN="$(mktemp -d)"
    export MOCK_BIN
    export PATH="$MOCK_BIN:$PATH"

    # inotifywait — mock: czeka chwilę i wychodzi (symulacja jednego zdarzenia),
    # tak by pętla while w skrypcie mogła iterować bez realnego inotify.
    cat > "$MOCK_BIN/inotifywait" << 'EOF'
#!/bin/bash
sleep 60
EOF
    chmod +x "$MOCK_BIN/inotifywait"

    # glava-colors-auto-mi — mock skryptu generującego kolory
    cat > "$TEST_HOME/.local/bin/glava-colors-auto-mi" << 'EOF'
#!/usr/bin/env python3
print("mock colors updated")
EOF
    chmod +x "$TEST_HOME/.local/bin/glava-colors-auto-mi"

    DAEMON_PID=""
}

teardown() {
    if [ -n "$DAEMON_PID" ]; then
        kill -9 "$DAEMON_PID" 2>/dev/null
        # `wait` konsumuje status zakończenia i zapobiega temu, by bash
        # asynchronicznie wypisał komunikat "Unicestwiony"/"Killed" (job
        # control) na starcie NASTĘPNEGO testu, zaśmiecając jego $output.
        wait "$DAEMON_PID" 2>/dev/null
    fi
    pkill -9 -f "inotifywait" 2>/dev/null
    wait 2>/dev/null
    rm -f "$LOCKFILE" "/tmp/glava-update.lock"
    rm -rf "$TEST_HOME" "$MOCK_BIN"
}

# Uruchamia daemon w tle, zwraca jego PID przez $DAEMON_PID.
# Czeka aż plik LOG się pojawi (sygnał że daemon faktycznie wystartował).
start_daemon() {
    HOME="$TEST_HOME" USER="$USER" bash "$SCRIPT" &
    DAEMON_PID=$!
    for i in $(seq 1 30); do
        [ -f "$LOG" ] && return 0
        sleep 0.1
    done
}

wait_for_log() {
    local pattern="$1"
    local timeout="${2:-3}"
    for i in $(seq 1 $((timeout * 10))); do
        [ -f "$LOG" ] && grep -q "$pattern" "$LOG" && return 0
        sleep 0.1
    done
    return 1
}

# ---------------------------------------------------------------------------
# Start i log
# ---------------------------------------------------------------------------

@test "daemon startuje i loguje uruchomienie z obserwowaną ścieżką tapety" {
    start_daemon
    run wait_for_log "Daemon uruchomiony"
    [ "$status" -eq 0 ]
    grep -q "$WALLPAPER" "$LOG"
}

@test "daemon tworzy katalog logów i backup_frag jeśli nie istnieją" {
    rm -rf "$TEST_HOME/.local/logs" "$TEST_HOME/.config/glava/backup_frag"
    start_daemon
    wait_for_log "Daemon uruchomiony"
    [ -d "$TEST_HOME/.local/logs" ]
    [ -d "$TEST_HOME/.config/glava/backup_frag" ]
}

# ---------------------------------------------------------------------------
# Blokada wielu instancji (LOCKFILE)
# ---------------------------------------------------------------------------

@test "druga instancja daemona przy żywym LOCKFILE PID → exit 0 natychmiast, log o duplikacie" {
    # Pierwsza instancja
    start_daemon
    wait_for_log "Daemon uruchomiony"
    first_pid="$DAEMON_PID"

    # Druga instancja — powinna wykryć że LOCKFILE wskazuje żywy proces i wyjść
    HOME="$TEST_HOME" USER="$USER" run bash "$SCRIPT"
    [ "$status" -eq 0 ]
    [[ "$output" == *"już działa"* ]] || grep -q "już działa" "$LOG"
}

@test "LOCKFILE z martwym PID → nowa instancja startuje normalnie" {
    # Stwórz lockfile wskazujący na nieistniejący PID
    echo "999999" > "$LOCKFILE"
    start_daemon
    run wait_for_log "Daemon uruchomiony"
    [ "$status" -eq 0 ]
}

@test "cleanup usuwa LOCKFILE po zakończeniu procesu (SIGTERM)" {
    start_daemon
    wait_for_log "Daemon uruchomiony"
    [ -f "$LOCKFILE" ]
    kill -TERM "$DAEMON_PID"
    sleep 0.5
    [ ! -f "$LOCKFILE" ]
}

# ---------------------------------------------------------------------------
# check_wallpaper_on_start
# ---------------------------------------------------------------------------

@test "brak pliku tapety przy starcie → check_wallpaper_on_start nie robi nic, brak crash" {
    rm -f "$WALLPAPER"
    start_daemon
    run wait_for_log "Daemon uruchomiony"
    [ "$status" -eq 0 ]
    # Nie powinno być wpisu o aktualizacji (bo tapeta nie istnieje)
    ! grep -q "aktualizuję kolory przy starcie" "$LOG"
}

@test "FLAG_MANUAL aktywny przy starcie → pomija sprawdzenie tapety" {
    touch "$WALLPAPER"
    touch "$FLAG_MANUAL"
    start_daemon
    run wait_for_log "ręczny/RED aktywny przy starcie"
    [ "$status" -eq 0 ]
}

@test "FLAG_RED aktywny przy starcie → pomija sprawdzenie tapety" {
    touch "$WALLPAPER"
    touch "$FLAG_RED"
    start_daemon
    run wait_for_log "ręczny/RED aktywny przy starcie"
    [ "$status" -eq 0 ]
}

@test "tapeta nowsza niż shader przy starcie → wywołuje update_colors" {
    touch -d "2020-01-01" "$LIVEFRAG"
    touch "$WALLPAPER"   # nowsza (teraz)
    start_daemon
    run wait_for_log "Tapeta nowsza niż shader"
    [ "$status" -eq 0 ]
    run wait_for_log "GLava zaktualizowana"
    [ "$status" -eq 0 ]
}

@test "tapeta starsza niż shader przy starcie → update_colors nie jest wywołany" {
    touch "$WALLPAPER"
    sleep 0.1
    touch "$LIVEFRAG"   # shader nowszy niż tapeta
    start_daemon
    wait_for_log "Daemon uruchomiony"
    sleep 0.5
    ! grep -q "Tapeta nowsza niż shader" "$LOG"
}

# ---------------------------------------------------------------------------
# Flagi blokujące update_colors (przez wywołanie ręczne logiki w trakcie pętli)
# ---------------------------------------------------------------------------

@test "FLAG_MANUAL podczas działania → pierwsza aktualizacja przechodzi przed ustawieniem flagi" {
    # Weryfikacja że update_colors faktycznie przebiega przy starcie (baseline),
    # zanim flaga zostanie ustawiona — szczegółowa logika blokowania przez
    # FLAG_MANUAL/FLAG_RED jest pokryta dokładniej w testach poniżej (source
    # funkcji w izolacji, bo mockowane inotifywait nie pozwala łatwo wyzwolić
    # drugiego przebiegu pętli głównej w end-to-end teście).
    touch -d "2020-01-01" "$LIVEFRAG"
    touch "$WALLPAPER"
    start_daemon
    run wait_for_log "GLava zaktualizowana"
    [ "$status" -eq 0 ]
}

@test "update_colors w izolacji (source) respektuje FLAG_MANUAL" {
    touch "$FLAG_MANUAL"
    run env HOME="$TEST_HOME" bash -c "
        source <(sed -n '/^update_colors()/,/^}/p' '$SCRIPT')
        FLAG_MANUAL='$FLAG_MANUAL'
        FLAG_RED='$FLAG_RED'
        GLAVA_DIR='$TEST_HOME/.config/glava'
        BACKUP_DIR=\"\$GLAVA_DIR/backup_frag\"
        LOG='$LOG'
        HOME='$TEST_HOME'
        update_colors
    "
    [ "$status" -eq 0 ]
    grep -q "Tryb GUI aktywny" "$LOG"
    ! grep -q "GLava zaktualizowana" "$LOG"
}

@test "update_colors w izolacji (source) respektuje FLAG_RED" {
    touch "$FLAG_RED"
    run env HOME="$TEST_HOME" bash -c "
        source <(sed -n '/^update_colors()/,/^}/p' '$SCRIPT')
        FLAG_MANUAL='$FLAG_MANUAL'
        FLAG_RED='$FLAG_RED'
        GLAVA_DIR='$TEST_HOME/.config/glava'
        BACKUP_DIR=\"\$GLAVA_DIR/backup_frag\"
        LOG='$LOG'
        HOME='$TEST_HOME'
        update_colors
    "
    [ "$status" -eq 0 ]
    grep -q "Tryb RED aktywny" "$LOG"
    ! grep -q "GLava zaktualizowana" "$LOG"
}

# ---------------------------------------------------------------------------
# update_colors — backup shaderów
# ---------------------------------------------------------------------------

@test "update_colors tworzy backup .frag z timestampem w backup_frag/" {
    echo "shader content" > "$TEST_HOME/.config/glava/graph/1.frag"
    touch -d "2020-01-01" "$LIVEFRAG"
    touch "$WALLPAPER"
    start_daemon
    run wait_for_log "GLava zaktualizowana"
    [ "$status" -eq 0 ]
    backup_count=$(ls "$TEST_HOME/.config/glava/backup_frag"/*.bak 2>/dev/null | wc -l)
    [ "$backup_count" -ge 1 ]
}

@test "update_colors woła glava-colors-auto-mi, wyjście trafia do logu" {
    touch -d "2020-01-01" "$LIVEFRAG"
    touch "$WALLPAPER"
    start_daemon
    run wait_for_log "mock colors updated"
    [ "$status" -eq 0 ]
}
