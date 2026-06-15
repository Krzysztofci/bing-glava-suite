# bing-glava-suite

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform: Linux](https://img.shields.io/badge/Platform-Linux-blue?logo=linux&logoColor=white)](https://github.com/Krzysztofci/bing-glava-suite)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Release](https://img.shields.io/badge/Release-v1.0.0--RC3-orange)](https://github.com/Krzysztofci/bing-glava-suite/releases)
[![Made for GLava](https://img.shields.io/badge/Made%20for-GLava-purple)](https://github.com/jarcode-foss/glava)
[![Tests](https://github.com/Krzysztofci/bing-glava-suite/actions/workflows/test.yml/badge.svg)](https://github.com/Krzysztofci/bing-glava-suite/actions/workflows/test.yml)
[![Coverage](https://codecov.io/gh/Krzysztofci/bing-glava-suite/branch/main/graph/badge.svg)](https://codecov.io/gh/Krzysztofci/bing-glava-suite)

**Multi-instance GLava visualization studio for Linux desktop.**

Automated Bing wallpaper downloads + GLava audio visualizer with full
multi-instance control — run multiple independent visualizations simultaneously,
each with its own shader, geometry, and color scheme.

Tested on **Linux Mint 22 XFCE/Cinnamon**, Intel HD 3000 (ThinkPad T420).

> 🇵🇱 [Polska wersja dokumentacji](README_PL.md)

---

## Features

- **Multiple GLava instances** — Bars, Wave, Circle, Graph, Radial running
  in parallel, each in its own tab
- **Per-instance isolation** — separate config directory, separate GLava
  process, separate shader settings
- **Persistent sessions** — open tabs and settings survive application restarts
- **Automated Bing wallpaper** — daily download with region selection
- **KMeans color sync** — extract dominant colors from wallpaper and apply to
  all GLava instances automatically
- **Forest-ttk-theme** — clean dark/light UI consistent throughout
- **Geometry auto-calculation** — correct size/position per screen and taskbar
- **Shader profiles** — save and restore parameter sets per module
- **Full i18n** — Polish and English UI, switchable at runtime

---

## Screenshots

![Multi-instance GUI demo](screenshots/Demo-1.0.0-MI.gif)

| Bars | Graph | Circle |
|------|-------|--------|
| ![Bars](screenshots/bars.gif) | ![Graph](screenshots/graph.gif) | ![Circle](screenshots/circle.gif) |

| Radial | Wave |
|--------|------|
| ![Radial](screenshots/radial.gif) | ![Wave](screenshots/wave.gif) |

---

## Installation

### Requirements

- Linux Mint 22 / Ubuntu 24.04 (recommended)
- Python 3.10+
- Tkinter (`python3-tk`)
- Pillow (`python3-pil`) — for color extraction
- GLava — use the pre-built `.deb` in Releases or build from source (see [BUILDING.md](BUILDING.md))

### Quick install

```bash
git clone -b feature/modular-gui https://github.com/Krzysztofci/bing-glava-suite.git
cd bing-glava-suite
sudo ./install.sh
```

The installer:
1. Copies scripts to `~/.local/bin/`
2. Copies GUI to `~/.local/bin/GlavaMP/`
3. Copies GLava config template from `/etc/xdg/glava/`
4. Installs systemd user service (`glava-color-daemon`)
5. Adds `~/.local/bin` to `PATH` in `.bashrc`
6. Sets up cron for daily wallpaper download
7. Creates desktop autostart entry for GLava

### Manual run (no install)

```bash
cd scripts
python3 glava-gui.py
```

---

## Usage

### Adding instances

Click `[✚]` in the tab bar → select a module (Bars / Wave / Circle / Graph /
Radial). A new tab appears and GLava starts automatically with the selected
module and its own isolated configuration.

### Tab controls

| Action | Result |
|--------|--------|
| Click tab | Switch active instance |
| Right-click tab | Context menu: Rename / Change shader / Save workspace / Duplicate / Close |
| `[✚]` button | Add new instance |
| 🖫 button | Save current workspace |
| 🗁 button | Load saved workspace |
| Close tab | Stops that instance's GLava process only |

### Main panel

Controls colors, gradients, wallpaper, and geometry. Changes apply to the
**currently selected tab**.

### Module tab

Per-instance shader parameters — shape, smoothing, flags. Each tab has
independent settings. Shader profiles can be saved and restored.

### Advanced panel

Audio settings (`setbufsize`, `setsamplesize`, `setsamplerate`) and FPS limit
apply to the **active instance only**. Expert mode unlocks additional options.

### Enabling / Disabling GLava

The Enable/Disable toggle in the Main panel:
- **Disable** — stops all GLava processes
- **Enable** — starts all registered instances in parallel

---

## Directory structure

```
~/.config/
├── glava/                        ← Template directory (not an instance)
├── glava-inst-1/glava/           ← Instance 1 (copied from template)
├── glava-inst-2/glava/           ← Instance 2
└── GlavaMP/
    ├── instances.json            ← Tab registry + persistent state
    ├── profiles.json             ← Shader profiles (global, per module)
    ├── presets.json              ← Color presets
    ├── gui.conf                  ← Window geometry
    └── themes/                   ← Forest-ttk-theme files
```

---

## Known limitations (v1.0.0-RC3)

- Color picker uses system Tk dialog — does not match Forest-ttk-theme.
  Custom TTK picker planned for a future release.
- Shader profiles are global per module, not per instance.
- Workspace is not auto-loaded on GUI start — use 🗁 to load manually.
- In some configurations, process count may double on boot (autostart + daemon).
  Workaround: toggle OFF/ON after login.

---

## Technical notes

- Process management: SIGTERM → 2s wait → SIGKILL per instance
- `XDG_CONFIG_HOME` set per instance so GLava reads the correct config dir
- Module source of truth: `rc.glsl` `#request mod <name>` line
- All shader writes go through `app.active_instance` — no global path
- No new Python dependencies beyond stdlib + Tkinter + Pillow

---

## Documentation

| File | Description |
|------|-------------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Code architecture and design decisions |
| [BUILDING.md](BUILDING.md) | Building GLava from source |
| [TESTING.md](TESTING.md) | Manual test scenarios |
| [CHANGELOG.md](CHANGELOG.md) | Version history |

---

## License

MIT — see [LICENSE](LICENSE)

GLava: GPLv3
Forest-ttk-theme: MIT
