# Installing GLava

### Option 1 — pre-built .deb package (recommended, Ubuntu 24.04 / Linux Mint 22.x)

Download `glava_1.6.3_amd64.deb` from [Releases](https://github.com/Krzysztofci/bing-glava-suite/releases):

```bash
sudo dpkg -i glava_1.6.3_amd64.deb
# If dependency errors occur:
sudo apt --fix-broken install
```

### Option 2 — compile from source

For other distributions or architectures:

```bash
# Build dependencies
sudo apt install -y \
    libpulse-dev libgl-dev libglx-dev libx11-dev libxext-dev \
    libxrender-dev libxcomposite-dev meson ninja-build \
    pkg-config gcc g++ git

# Clone the source
git clone https://github.com/jarcode-foss/glava
cd glava

# GCC 13 compatibility fixes (Ubuntu 24.04+)
sed -i '/#include <error.h>/a #include <cstdio>\n#include <cerrno>' glfft/glfft_gl_interface.hpp
sed -i '/#include "glfft.hpp"/a #include <stdexcept>' glfft/glfft_wisdom.cpp
sed -i '1s/^/#include <cstdio>\n/' glfft/glfft_gl_interface.cpp
sed -i 's/__attribute__((noreturn, visibility("default"))) void (\*glava_abort)/extern __attribute__((noreturn, visibility("default"))) void (*glava_abort)/' glava/glava.h
sed -i 's/__attribute__((noreturn, visibility("default"))) void (\*glava_return)/extern __attribute__((noreturn, visibility("default"))) void (*glava_return)/' glava/glava.h

# Build and install
meson build --prefix /usr -Ddisable_obs=true
ninja -C build
sudo ninja -C build install
```

### Post-install configuration

```bash
glava --copy-config
sudo chown -R $USER:$USER ~/.config/glava

# Replace symlinks with actual directories
rm -rf ~/.config/glava/bars && cp -r /etc/xdg/glava/bars ~/.config/glava/bars
rm -rf ~/.config/glava/graph && cp -r /etc/xdg/glava/graph ~/.config/glava/graph
sudo chown -R $USER:$USER ~/.config/glava
```

> **Note:** Warnings about `using "window" transform explicitly is deprecated` are expected and harmless.
