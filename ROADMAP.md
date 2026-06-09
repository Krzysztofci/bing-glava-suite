# Roadmap — GLava Master Panel / bing-glava-suite

This document collects planned features, improvements and ideas for future releases.
Priorities and timelines may shift based on testing results and community feedback.

> 🇵🇱 [Polska wersja](ROADMAP_PL.md)

---

## 🚀 Short term

### Bug fixes & improvements

- **Wallpaper source detection** — the color daemon currently watches `bing-today.jpg`
  directly via `inotifywait`. Planned: detect the desktop environment at startup
  (XFCE via `xfconf-query`, Cinnamon/GNOME via `gsettings`) and extract colors from
  the actually active desktop wallpaper.
  → [issue #TBD](../../issues)

- **Custom TTK color picker** — replace the system `colorchooser.askcolor` dialog with
  a native TTK widget consistent with Forest-ttk-theme.
  → [issue #TBD](../../issues)

### New features

- **Eyedropper / pick color from wallpaper** — allow the user to click anywhere on the
  wallpaper thumbnail to sample a color, instead of only using KMeans auto-extraction.
  → [issue #TBD](../../issues)

- **Tray icon** — a lightweight system tray indicator (via `pystray` or `AppIndicator3`)
  for quick Enable/Disable toggle and active instance status without opening the full GUI.
  → [issue #TBD](../../issues)

---

## 📦 Medium term

### Workspace improvements

- **Workspace manager** — dedicated dialog for managing, renaming and deleting
  saved workspaces.
  → [issue #TBD](../../issues)

### Installer

- **Dependency detection** — auto-detect missing system packages and prompt the user
  to install them rather than failing silently.
  → [issue #TBD](../../issues)

- **Broader Debian-based distribution support** — test and fix installer compatibility
  on Debian 12, Ubuntu 22.04, Pop!_OS and other Debian derivatives beyond
  Linux Mint 22 / Ubuntu 24.04.
  → [issue #TBD](../../issues)

---

## 🎬 Future / Unscheduled

- **GLava .deb with OBS plugin support** — a separate pre-built package with OBS
  virtual camera plugin compiled in.
  → [issue #TBD](../../issues)

- **Window manager compatibility** — test and fix compatibility with GNOME, KDE Plasma,
  MATE, LXQt, Openbox, i3/sway (X11). Each may require different autostart mechanisms,
  geometry detection and wallpaper source queries.
  → [issue #TBD](../../issues)

- **Optional modules / community shaders** — an in-app browser for installing
  community GLava shaders (e.g. NCS Spectrum). Requires OpenGL 4.2+ hardware
  and external testers.
  → [issue #TBD](../../issues)

- **AppImage / portable build** — self-contained package that does not require
  installation, for users who prefer not to run `sudo ./install.sh`.

---

## 💡 Ideas under consideration

- **Color history** — a rolling log of recent wallpaper-extracted palettes with
  the ability to reapply any of them.
  → [issue #TBD](../../issues)

- **Multi-monitor support** — per-monitor instance geometry presets.
  → [issue #TBD](../../issues)

- **CLI interface** — `glava-ctl` command for scripting instance management without GUI.
  → [issue #TBD](../../issues)

---

> **Wayland:** GLava requires X11. For Wayland users, see [WayVes](https://github.com/Roonil/WayVes).

---

*Last updated: 2026-06*
