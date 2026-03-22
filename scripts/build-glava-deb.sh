#!/bin/bash
# =============================================================================
# build-glava-deb.sh
# Buduje paczkę .deb z zainstalowanej GLavy (skompilowanej ze źródeł).
# Uruchom na systemie gdzie GLava jest już zainstalowana.
# Wynikowy plik .deb umieszcza w bieżącym katalogu.
# =============================================================================
set -e

RED='\033[0;31m'
GRN='\033[0;32m'
YEL='\033[1;33m'
RST='\033[0m'

info() { echo -e "${GRN}[✓]${RST} $*"; }
warn() { echo -e "${YEL}[!]${RST} $*"; }
error() { echo -e "${RED}[✗]${RST} $*"; exit 1; }

# Sprawdź czy GLava jest zainstalowana
command -v glava &>/dev/null || error "GLava nie jest zainstalowana w PATH."
command -v dpkg-deb &>/dev/null || error "dpkg-deb nie jest dostępne."

# Pobierz wersję
GLAVA_VERSION=$(glava --version 2>&1 | grep -oP 'v\K[0-9]+\.[0-9]+\.[0-9]+' | head -1)
GLAVA_VERSION="${GLAVA_VERSION:-1.6.3}"
ARCH=$(dpkg --print-architecture)
PKG_NAME="glava_${GLAVA_VERSION}_${ARCH}"

info "Budowanie paczki: $PKG_NAME.deb"
info "Architektura: $ARCH"

# Katalog roboczy
BUILD_DIR="/tmp/$PKG_NAME"
rm -rf "$BUILD_DIR"

# Struktura katalogów
mkdir -p "$BUILD_DIR/DEBIAN"
mkdir -p "$BUILD_DIR/usr/bin"
mkdir -p "$BUILD_DIR/usr/lib/x86_64-linux-gnu"
mkdir -p "$BUILD_DIR/usr/share/glava/resources"
mkdir -p "$BUILD_DIR/etc/xdg/glava"

# Kopiuj pliki binarne
info "Kopiowanie pliku binarnego..."
cp /usr/bin/glava "$BUILD_DIR/usr/bin/glava"
chmod 755 "$BUILD_DIR/usr/bin/glava"

info "Kopiowanie biblioteki współdzielonej..."
cp /usr/lib/x86_64-linux-gnu/libglava.so "$BUILD_DIR/usr/lib/x86_64-linux-gnu/libglava.so"
chmod 644 "$BUILD_DIR/usr/lib/x86_64-linux-gnu/libglava.so"

info "Kopiowanie zasobów..."
cp /usr/share/glava/resources/glava.bmp "$BUILD_DIR/usr/share/glava/resources/glava.bmp"

info "Kopiowanie domyślnej konfiguracji..."
cp -r /etc/xdg/glava/. "$BUILD_DIR/etc/xdg/glava/"
# Usuń błędny symlink jeśli istnieje
rm -f "$BUILD_DIR/etc/xdg/glava/util/util"

# Oblicz rozmiar zainstalowanego pakietu (w KB)
INSTALLED_SIZE=$(du -sk "$BUILD_DIR" | cut -f1)

# Plik control
cat > "$BUILD_DIR/DEBIAN/control" << CONTROL
Package: glava
Version: ${GLAVA_VERSION}
Architecture: ${ARCH}
Maintainer: bing-glava-suite <https://github.com/Krzysztofci/bing-glava-suite>
Installed-Size: ${INSTALLED_SIZE}
Depends: libpulse0, libx11-6, libxext6, libxrender1, libxcomposite1,
 libxcb1, libx11-xcb1, libdbus-1-3, libsndfile1, libapparmor1,
 libvorbis0a, libvorbisenc2, libopus0, libogg0, libmp3lame0,
 libgcrypt20, liblz4-1, liblzma5, libzstd1
Description: GLava — OpenGL audio visualizer for Linux desktop
 GLava is an OpenGL audio spectrum visualizer that renders
 directly to the desktop root window (or as a floating window).
 Supports XFCE, Cinnamon and other X11 desktop environments.
 .
 This package was built from source ${GLAVA_VERSION}
 for Ubuntu 24.04 / Linux Mint 22.x (${ARCH}).
 .
 Part of bing-glava-suite project.
Homepage: https://github.com/jarcode-foss/glava
CONTROL

# Skrypt post-install
cat > "$BUILD_DIR/DEBIAN/postinst" << 'POSTINST'
#!/bin/bash
ldconfig
POSTINST
chmod 755 "$BUILD_DIR/DEBIAN/postinst"

# Buduj paczkę
OUTPUT_DIR="$(pwd)"
info "Budowanie paczki .deb..."
dpkg-deb --build --root-owner-group "$BUILD_DIR" "$OUTPUT_DIR/${PKG_NAME}.deb"

info "Gotowe: $OUTPUT_DIR/${PKG_NAME}.deb"
info "Rozmiar: $(du -sh "$OUTPUT_DIR/${PKG_NAME}.deb" | cut -f1)"

# Weryfikacja
info "Weryfikacja zawartości paczki:"
dpkg-deb --contents "$OUTPUT_DIR/${PKG_NAME}.deb" | grep -E "glava|libglava"

rm -rf "$BUILD_DIR"
