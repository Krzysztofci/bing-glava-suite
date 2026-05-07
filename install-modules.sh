#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_DIR="$HOME/.config/glava"
BIN_DIR="$HOME/.local/bin"

echo "==> Tworzenie katalogów i kopiowanie plików .glsl..."
for module in bars circle wave radial graph; do
    mkdir -p "$CONFIG_DIR/$module"
    cp -rf "/etc/xdg/glava/$module/" "$CONFIG_DIR/$module/"
    cp -f "/etc/xdg/glava/$module.glsl" "$CONFIG_DIR/$module.glsl"
    echo "    Nadpisano: $module i $module.glsl"
done

echo "==> Instalacja szablonów shaderów..."
for frag in bars_colors.frag circle_colors.frag wave_colors.frag radial_colors.frag graph_colors.frag; do
    src="$SCRIPT_DIR/config/$frag"
    dst="$CONFIG_DIR/$frag"
    if [ -f "$src" ]; then
        cp -f "$src" "$dst"
        echo "    Nadpisano: $frag"
    fi
done

echo "==> Aktualizacja skryptów..."
for script in glava-colors-auto glava-gui.py glava-toggle; do
    cp -f "$SCRIPT_DIR/scripts/$script" "$BIN_DIR/$script"
    chmod +x "$BIN_DIR/$script"
    echo "    $script zaktualizowany."
done

echo ""
echo "==> Gotowe!"
