Changelog

All notable changes to this project are documented here.Format based on Keep a Changelog.

[0.5.0] — 2026‑05‑05

### Added

- Advanced geometry engine (multi‑panel detection)Geometry detection now identifies taskbars and desktop panels on all four screen edges (top, bottom, left, right).Modules automatically adjust their available workspace and default positions based on the detected panel layout.
- Per‑module geometry systemEach module (bars, graph, circle, radial, wave) stores its own geometry (X/Y/W/H) independently.Geometry is no longer global — every shader remembers its own layout and restores it when selected.
- Modular GUI architectureEvery GLava module now has a dedicated configuration tab with its own parameters:
- Shape & Dynamics
- Position & Rotation
- Switches
- Smoothing
- Shader Profiles
- Unified Smoothing sectionGravity, smoothing, average frames, FFT scale and bass cutoff are now:
- globally consistent,
- shared across all shaders,
- saved inside each module’s profile.
- Per‑module shader profilesEach module supports its own preset system:
- Apply
- Save new
- Delete
- Reset shader
- Simple JSON‑based localization systemAdding a new language requires translating a single JSON file and placing it in the language directory.The application automatically detects and loads new languages — no code changes required.
- Full internationalization (i18n)
- Complete English and Polish translations
- All module tabs fully localized
- Language switching in the GUI
- Enhanced shader setUpdated and extended versions of GLava shaders with:
- additional parameters,
- improved dynamics,
- corrected upstream issues,
- better gradient handling,
- more consistent FFT behavior.
- New GUI theme systemForest‑dark theme with consistent styling across all widgets.
- Diagnostics tools
- View daemon logs
- Test panel detection

### Changed
- Geometry system completely redesigned
- Previously: simple resolution detection with fixed offsets
- Now: full multi‑panel detection, per‑module geometry memory, and precise control over position & rotation
- Modules no longer share geometry — each one behaves independently
- Color and gradient handling improved
- More stable RGB/HSV switching
- Corrected HSV_MODE behavior
- Better synchronization with shader state
- GUI overhaul
- Fully redesigned layout
- Clearer structure and workflow
- Better separation of module‑specific and global settings
- Improved ergonomics and visual consistency
- Shader performance and stability
- Corrected t calculations across modules
- Improved FFT scaling
- More stable amplitude handling
- Better visual consistency between modules

### Installer improvements
- Numerous fixes accumulated over 1.5 months
- More reliable file copying
- Corrected permissions and systemd logic
- Cleaner directory structure and safer operations

### Fixed
- Dozens of shader fixes across all modules
- Geometry detection and auto‑geometry stability
- i18n issues in PL/EN
- Profile loading/saving logic
- Manual mode color handling
- Wallpaper lock/unlock logic
- Installer bugs (chown, systemd, missing files)
- Edge cases in gradient and HSV mode switching

### Removed
- Old global geometry system
- Legacy GUI components from 0.2.x
- Deprecated shader files
- Unused code paths and obsolete logic

### Migration notes
- Profiles from 0.2.x are not compatible with 0.5.0.
- Each module requires initial configuration and profile save.
- Geometry is now per‑module — old XYWH settings are ignored.
- Localization files are fully modular: adding a new language requires only translating one JSON file and placing it in internal_lang/.

### Highlights
- Modular GUI with per‑module profiles
- Advanced geometry engine with multi‑panel detection
- Enhanced shaders with new parameters
- Full EN/PL localization
- Fully themed gui - dark/light versions
- 1.5 months of continuous refactoring and improvements

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
