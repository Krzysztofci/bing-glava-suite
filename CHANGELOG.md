# Changelog

All notable changes to this project are documented here.  
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### Planned: Module profiles

A module profile bundles everything that defines a GLava layout into a single
named preset: the visualizer module, its colors, and its screen geometry.

One click switches all three at once — no separate steps for module, colors,
and position.

---

## [0.3.0] — feature/modular-gui — in testing

The modular GUI release. Focus: per-module control panels, unified shader
architecture, full 5-module support.

### Added
- Modular GUI architecture — each GLava module has its own dedicated control
  panel (`bars.py`, `circle.py`, `graph.py`, `radial.py`, `wave.py`)
- Per-module shape parameters with live sliders and debounced restart
- Per-module shader profiles (save, load, delete named presets)
- Per-module shader reset to defaults
- Smoothing parameters panel in all modules (gravity, smoothing factor,
  avg frames, FFT scale, FFT cutoff)
- Position offsets (CENTER_OFFSET_X/Y) in radial and circle modules
- Rotation slider 0–360° replacing 4-option combobox in radial and circle
- Circle module: full parameter support (C_RADIUS, C_LINE, AMPLIFY, ROTATE,
  offsets, C_FILL, C_SMOOTH, INVERT)
- Wave module: linked MIN/MAX thickness sliders (move together on collision)
- Graph module: GRADIENT parameter repurposed as center brightness control
- Audio section in Advanced tab (setbufsize, setsamplesize, setsamplerate,
  setframerate, setmirror, setinterpolate) with expert mode expansion
- Expert mode now rebuilds Advanced tab to show extended audio buffer options
- GLava extra flags field in Advanced tab reads current process flags
- Auto-geometry now saves and restarts GLava immediately without extra click

### Changed
- All modules now use unified geometry: full screen height with Y=-panel_height
  (previously circle/radial/wave used work area height)
- GLAVA_MODULES list sorted alphabetically: bars, circle, graph, radial, wave
- Default active module changed from graph to bars
- graph_red.frag renamed to graph_colors.frag for naming consistency
- Installer: graph module merged with other modules (no longer treated
  separately), all 5 modules installed equally
- install-modules.sh updated to include graph
- Codebase grew from ~2359 to ~5974 lines (2.5× increase due to modularization)

### Removed
- graph2 module references removed throughout codebase and installer
- Hardcoded C_LINE override in circle/1.frag (now controlled by GUI)
- Dead shader parameters C_LINE_WIDTH and C_AMPLIFY from circle module

### Fixed
- Circle module: CENTER_OFFSET_X/Y now correctly read from file on GUI load
- Radial module: rotation value correctly converted between degrees and radians
- Geometry calculation unified — no more wrong 860px height for circle/wave/radial

---

## [0.2.2] — 2026-04-06

### Fixed
- glava-colors-auto now uses `HSV_MODE` define instead of replacing `gradient_color` function
- `restore_auto` no longer resets HSV mode
- Auto-geometry values now populate fields after dialog closes
- Module switch now correctly reflects HSV/RGB state in radio buttons
- Missing live `.frag` triggers `apply_manual` automatically

---

## [0.2.2-pre] — Pending testing

### Added
- New tool: `tools/gradient_compare.py` for comparing RGB vs HSV gradients.
- GUI now detects `HSV_MODE` directly from shader files when switching modules.

### Changed
- Enabled functional HSV support across all shader modules.
- GUI updates gradient mode and radio buttons based on live shader state.
- GUI shows a warning label (⚠ RGB only) for shaders without HSV support.
- Updated GLava configuration defaults (`circle.glsl`, `rc.glsl`).

### Fixed
- Corrected and standardized `t` calculations in multiple shader modules

---

## [0.2.1] — Hotfix release

### Added
- Lock/unlock mechanism for wallpaper.
- Increased automation — less manual intervention required
- New functions in the GUI control panel

### Changed
- Updated GUI to support the new lock/unlock wallpaper functionality.
- Updated `bing-downloader.sh` and `bing-fetch-user.sh`.
- Updated language JSON files.

### Fixed
- Bars module: corrected gradient color mapping
- Corrected logic in wallpaper lock/unlock function

---

## [0.2.0] — feature/new-architecture (first pass)

### Added
- Multi-module support: bars, circle, wave, radial (previously: graph only)
- Auto-detect geometry based on screen resolution and taskbar height
- Cinnamon desktop compatibility
- GLava autostart on login
- Uninstall script
- English translations in GUI

### Changed
- Root no longer executes scripts inside user directories
- Systemd service and directory ownership handling hardened
- Installer rewritten with multiple rounds of fixes

### Fixed
- GUI geometry functions
- Systemd directory ownership
- Active shader colors no longer overwritten on reinstall
- Daemon now checks wallpaper vs shader timestamp on start

---

## [0.1.0-beta]

### Added
- GUI control panel (Tkinter) — first version
- Color presets system
- GLava auto-install from GitHub Releases (pre-built .deb)
- MIT license

---

## [0.1.0-alpha]

### Added
- First public release on GitHub
- Bing wallpaper downloader
- KMeans color extraction from wallpaper
- Automatic GLava shader update on wallpaper change
- systemd user service (inotify daemon)
- glava-toggle

---

## [pre-alpha] — not tagged, local only

- Started as a standalone wallpaper download script
- Added GLava after looking for audio visualization
- Added color extraction, manual controls
- Complex enough to put on GitHub

---

## Versioning notes

- `0.x.0` — significant feature additions or architectural changes
- `0.x.y` — fixes and small improvements
- `1.0.0` — when stable enough for general use without caveats
