# Changelog

All notable changes to this project are documented here.  
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased] — feature/new-architecture (active)

### Planned: Module profiles

A module profile bundles everything that defines a GLava layout into a single
named preset: the visualizer module, its colors, and its screen geometry.

One click switches all three at once — no separate steps for module, colors,
and position.

Useful for people who run multiple desktop layouts (e.g. different Conky
setups, presentation mode, minimal mode) and want to switch GLava to match
without manual reconfiguration.

Example profile "Minimal Bottom":
- module: graph
- colors: warm brown gradient
- geometry: full width, anchored above taskbar

Example profile "Circle Center":
- module: radial
- colors: grey/white
- geometry: centered on screen

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
- Bars module: corrected gradient color mapping — t is now calculated relative to bar height instead of full screen height, fixing the issue where only the bottom gradient color was visible.
- Corrected logic in wallpaper lock/unlock function (minor patch; prevents incorrect state switching).
---

## [0.2.0] — feature/new-architecture (first pass)

The architecture overhaul release. Focus: security, stability, multi-module support.

### Added
- Multi-module support: bars, circle, wave, radial (previously: graph only)
- Auto-detect geometry based on screen resolution and taskbar height
- Cinnamon desktop compatibility (wallpaper setting)
- GLava autostart on login
- Uninstall script
- English translations in GUI

### Changed
- Root no longer executes scripts inside user directories — security boundary clarified
- Systemd service and directory ownership handling hardened
- Installer rewritten with multiple rounds of fixes (linger, chown, permissions)
- Faster color reaction: daemon delay reduced from 5s to 0.5s

### Fixed
- GUI geometry functions (apply\_geometry, write\_geometry)
- Systemd directory ownership
- Active shader colors no longer overwritten on reinstall
- Daemon now checks wallpaper vs shader timestamp on start — avoids unnecessary restarts
- Desktop entry icon loading

---

## [0.1.0-beta]

### Added
- GUI control panel (Tkinter) — first version
- Color presets system
- GLava auto-install from GitHub Releases (pre-built .deb)
- MIT license

### Changed
- README expanded with English summary

---

## [0.1.0-alpha]

The point where scripts became a project worth publishing.

### Added
- First public release on GitHub
- Bing wallpaper downloader (cron, root script)
- KMeans color extraction from wallpaper
- Automatic GLava shader update on wallpaper change
- systemd user service (inotify daemon)
- glava-toggle (enable/disable GLava)

---

## [pre-alpha] — not tagged, local only

The origin story. Not a release — just context.

- Started as a standalone wallpaper download script (dissatisfied with Variety and similar tools)
- Added GLava after looking for audio visualization in a music player — no working packages for Mint, had to build from source
- Noticed GLava looked wrong after wallpaper changed — wrote color extraction script
- Added manual controls for wallpaper source and colors
- At that point it was complex enough to put on GitHub

---

## Versioning notes

This project does not yet follow strict semantic versioning.  
Rough intent going forward:

- `0.x.0` — significant feature additions or architectural changes  
- `0.x.y` — fixes and small improvements  
- `1.0.0` — when the suite is stable enough for general use without caveats
