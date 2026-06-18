#!/usr/bin/env bats
# =============================================================================
# tests/test_build_glava_deb.bats
# Testy dla scripts/build-glava-deb.sh
#
# Pokrywa: walidacja glava/dpkg-deb w PATH, fallback wersji 1.6.3 gdy
#          `glava --version` nie zwraca rozpoznawalnego formatu, budowa
#          struktury katalogów .deb, usunięcie błędnego symlinka util/util,
#          generowanie pliku control z poprawnymi polami, finalny dpkg-deb
#          --build i sprzątanie BUILD_DIR.
#
# UWAGA: skrypt ma `set -e` — każdy mock musi kończyć się exit 0 na ścieżce
# sukcesu, inaczej cały skrypt przerwie się przedwcześnie. Realny dpkg-deb
# i dpkg są używane (dostępne w środowisku testowym), nie mockowane —
# testujemy więc faktyczne budowanie .deb na fałszywych plikach źródłowych.
# =============================================================================

setup_file() {
    for candidate in \
        "$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)/scripts/build-glava-deb.sh" \
        "$(cd "$(dirname "$BATS_TEST_FILENAME")/.." && pwd)/build-glava-deb.sh"; do
        if [ -f "$candidate" ]; then
            export SCRIPT="$candidate"
            chmod +x "$SCRIPT"
            return
        fi
    done
    echo "BŁĄD: nie znaleziono build-glava-deb.sh" >&2
    exit 1
}

setup() {
    WORK_DIR="$(mktemp -d)"
    export WORK_DIR
    cd "$WORK_DIR"

    MOCK_BIN="$(mktemp -d)"
    export MOCK_BIN
    export PATH="$MOCK_BIN:$PATH"

    # Mock glava — domyślnie zwraca wersję w rozpoznawalnym formacie
    cat > "$MOCK_BIN/glava" << 'EOF'
#!/bin/bash
[ "$1" = "--version" ] && echo "glava v1.8.2-release"
exit 0
EOF
    chmod +x "$MOCK_BIN/glava"

    # Skrypt odwołuje się do plików systemowych z pełną ścieżką (/usr/bin/glava
    # itd.) niezależnie od PATH — podmieniamy je tymczasowo, z backupem.
    # Tworzymy fałszywe pliki źródłowe żeby `cp` miał co kopiować.
    #
    # WAŻNE: jeśli prawdziwa GLava jest zainstalowana i aktualnie wykonywana
    # (np. przez glava-color-daemon w tle), Linux blokuje nadpisanie pliku
    # wykonywalnego in-place ("Plik wykonywalny zajęty"). `rm` na pliku nie
    # wymaga że jest "wolny" — usuwa tylko wpis z katalogu, a żyjący proces
    # nadal trzyma swój własny deskryptor do starego inode. Dlatego najpierw
    # `rm -f`, potem tworzymy nowy plik pod tą samą nazwą.
    for f in /usr/bin/glava \
             /usr/lib/x86_64-linux-gnu/libglava.so \
             /usr/share/glava/resources/glava.bmp; do
        mkdir -p "$(dirname "$f")"
        if [ -e "$f" ]; then
            cp -a "$f" "$f.bak.$$" 2>/dev/null || true
        fi
        rm -f "$f"
    done
    echo "fake glava binary" > /usr/bin/glava
    chmod +x /usr/bin/glava
    echo "fake shared lib" > /usr/lib/x86_64-linux-gnu/libglava.so
    echo "fake bitmap" > /usr/share/glava/resources/glava.bmp

    if [ -d /etc/xdg/glava ]; then
        mv /etc/xdg/glava "/etc/xdg/glava.bak.$$"
    fi
    mkdir -p /etc/xdg/glava/util
    echo "fake config" > /etc/xdg/glava/rc.glsl
    ln -sf /nonexistent /etc/xdg/glava/util/util   # symlink który skrypt powinien usunąć
}

teardown() {
    cd /
    # Przywróć oryginalne pliki systemowe
    for f in /usr/bin/glava \
             /usr/lib/x86_64-linux-gnu/libglava.so \
             /usr/share/glava/resources/glava.bmp; do
        rm -f "$f"
        [ -e "$f.bak.$$" ] && mv "$f.bak.$$" "$f"
    done
    rm -rf /etc/xdg/glava
    [ -d "/etc/xdg/glava.bak.$$" ] && mv "/etc/xdg/glava.bak.$$" /etc/xdg/glava

    rm -rf "$WORK_DIR" "$MOCK_BIN"
    rm -rf /tmp/glava_*
}

run_script() {
    run bash "$SCRIPT" "$@"
}

# ---------------------------------------------------------------------------
# Walidacja wymaganych komend
# ---------------------------------------------------------------------------

@test "glava niedostępna w PATH → exit 1 z komunikatem błędu" {
    rm -f "$MOCK_BIN/glava"
    run env HOME="$WORK_DIR" bash -c '
        command() {
            if [ "$1" = "-v" ] && [ "$2" = "glava" ]; then return 1; fi
            builtin command "$@"
        }
        export -f command
        bash "'"$SCRIPT"'"
    '
    [ "$status" -eq 1 ]
    [[ "$output" == *"GLava nie jest zainstalowana"* ]]
}

@test "dpkg-deb niedostępne → exit 1 z komunikatem błędu" {
    run env HOME="$WORK_DIR" bash -c '
        command() {
            if [ "$1" = "-v" ] && [ "$2" = "dpkg-deb" ]; then return 1; fi
            builtin command "$@"
        }
        export -f command
        bash "'"$SCRIPT"'"
    '
    [ "$status" -eq 1 ]
    [[ "$output" == *"dpkg-deb nie jest dostępne"* ]]
}

# ---------------------------------------------------------------------------
# Wykrywanie wersji GLava
# ---------------------------------------------------------------------------

@test "rozpoznawalny format wersji → użyty w nazwie paczki" {
    run_script
    [ "$status" -eq 0 ]
    [[ "$output" == *"glava_1.8.2_"* ]]
}

@test "nierozpoznawalny format wersji → fallback do 1.6.3" {
    cat > "$MOCK_BIN/glava" << 'EOF'
#!/bin/bash
[ "$1" = "--version" ] && echo "wersja w nieznanym formacie XYZ"
exit 0
EOF
    chmod +x "$MOCK_BIN/glava"
    run_script
    [ "$status" -eq 0 ]
    [[ "$output" == *"glava_1.6.3_"* ]]
}

@test "glava --version zwraca błąd (exit != 0) → fallback do 1.6.3, brak crash" {
    cat > "$MOCK_BIN/glava" << 'EOF'
#!/bin/bash
[ "$1" = "--version" ] && exit 1
exit 0
EOF
    chmod +x "$MOCK_BIN/glava"
    run_script
    [ "$status" -eq 0 ]
    [[ "$output" == *"glava_1.6.3_"* ]]
}

# ---------------------------------------------------------------------------
# Struktura .deb i happy path
# ---------------------------------------------------------------------------

@test "happy path → paczka .deb tworzona w katalogu bieżącym" {
    run_script
    [ "$status" -eq 0 ]
    deb_file=$(ls "$WORK_DIR"/glava_*.deb 2>/dev/null)
    [ -n "$deb_file" ]
    [ -f "$deb_file" ]
}

@test "BUILD_DIR jest usuwany po zakończeniu (sprzątanie /tmp)" {
    run_script
    [ "$status" -eq 0 ]
    # Po zakończeniu skryptu katalog roboczy /tmp/glava_* nie powinien istnieć
    leftover=$(find /tmp -maxdepth 1 -name "glava_*" -type d 2>/dev/null)
    [ -z "$leftover" ]
}

@test "błędny symlink util/util jest usuwany z paczki" {
    run_script
    [ "$status" -eq 0 ]
    deb_file=$(ls "$WORK_DIR"/glava_*.deb)
    run dpkg-deb --contents "$deb_file"
    [[ "$output" != *"util/util"* ]]
}

@test "wygenerowany control zawiera poprawną wersję i architekturę" {
    run_script
    [ "$status" -eq 0 ]
    deb_file=$(ls "$WORK_DIR"/glava_*.deb)
    run dpkg-deb --info "$deb_file"
    [[ "$output" == *"Version: 1.8.2"* ]]
    [[ "$output" == *"Package: glava"* ]]
}

@test "paczka .deb zawiera binarkę glava i bibliotekę libglava.so" {
    run_script
    [ "$status" -eq 0 ]
    deb_file=$(ls "$WORK_DIR"/glava_*.deb)
    run dpkg-deb --contents "$deb_file"
    [[ "$output" == *"usr/bin/glava"* ]]
    [[ "$output" == *"libglava.so"* ]]
}

@test "skrypt postinst zawiera ldconfig" {
    run_script
    [ "$status" -eq 0 ]
    deb_file=$(ls "$WORK_DIR"/glava_*.deb)
    extract_dir="$WORK_DIR/extracted"
    mkdir -p "$extract_dir"
    dpkg-deb --control "$deb_file" "$extract_dir"
    grep -q "ldconfig" "$extract_dir/postinst"
}

@test "weryfikacja na końcu wypisuje zawartość paczki (glava|libglava)" {
    run_script
    [ "$status" -eq 0 ]
    [[ "$output" == *"Weryfikacja zawartości paczki"* ]]
    [[ "$output" == *"usr/bin/glava"* ]]
}

# ---------------------------------------------------------------------------
# set -e: błąd w środku przerywa cały skrypt
# ---------------------------------------------------------------------------

@test "set -e: błąd przy cp biblioteki przerywa skrypt, brak częściowej paczki" {
    rm -f /usr/lib/x86_64-linux-gnu/libglava.so
    run_script
    [ "$status" -ne 0 ]
    # Żadna paczka .deb nie powinna zostać utworzona po przerwaniu w środku.
    # Używamy glob bezpośrednio (nullglob), nie `ls`, bo `ls` na braku
    # dopasowania zwraca status != 0 i z `set -e` w bats potrafi to
    # propagować przez command substitution nawet z przekierowanym stderr.
    shopt -s nullglob
    deb_files=("$WORK_DIR"/glava_*.deb)
    shopt -u nullglob
    [ "${#deb_files[@]}" -eq 0 ]
}
