# Changelog — bing-glava-suite

---

## [1.0.0-RC3] — 2026-06-xx

### Release Candidate 3 — Detached panel instance routing fix

---

### 🐛 Bug fixes

#### Detached panels writing to wrong instance
- **Root cause:** `BaseParamWidget` always resolved the target instance via
  `app.active_instance` at the time of write/restart. Switching tabs in the
  main window while a panel was detached caused GLSL writes and GLava restarts
  to hit the wrong instance — e.g. manipulating a detached Radial panel would
  restart Bars (the newly active tab) with the Radial module.
- **Fix:** `BaseParamWidget.__init__` gains an optional `instance=` parameter.
  `detach_section()` now creates a **new widget** bound to the frozen
  `active_instance` at detach time, fully isolating it from main window state.
  All GLSL properties and `_schedule_restart()` go through `_get_instance()`,
  which returns the frozen instance when set.
- **`restart_active_instance()`** gains `instance=` parameter — when provided,
  operates on that specific instance instead of the currently active one.
  Pending restarts also carry the instance reference (3-tuple).

---

## [1.0.0-RC2] — 2026-06-xx

### Release Candidate 2 — Bug fixes & stability

---

### 🐛 Bug fixes

- **`_debounce_request` duplicate process bug** — fixed race condition causing
  multiple GLava processes to spawn
- **Deadlock in `_on_glava_toggle`** — fixed hang when `self.instances` is empty
- **Workspace save/load corruption** — `smooth_parameters.glsl` uses `#request`
  not `#define`; `read_all_defines` regex fixed to capture space-containing values

### 🔧 Other changes

- Bug and feature tracking migrated from desktop text files to GitHub Issues
- Feature list pruned of incorrect assumptions
- ROADMAP and CHANGELOG updated (bilingual)
- Wayland support permanently removed — users directed to WayVes

---

## [1.0.0-RC1] — 2026-06-xx

### Release Candidate 1 — Multi-instance GLava Studio

First release candidate of the multi-instance rewrite. Core functionality
is stable; known issues are documented below.

---

### ✨ New in RC1 (since v0.5.0)

#### Multi-instance Architecture
- Run multiple GLava visualizers simultaneously — Bars, Wave, Circle, Graph,
  Radial — each in its own tab with isolated config and process
- Per-instance `XDG_CONFIG_HOME` at `~/.config/glava-inst-{id}/glava/`
- All instances equal — any can be closed or deleted, including inst-0
- Persistent state via `instances.json` — tabs survive application restarts
- Module source of truth: `rc.glsl` `#request mod` line, not `instances.json`

#### InstanceTabBar
- Custom tab strip built on `ttk.Notebook` (height=0) with Forest-ttk-theme
- Tab labels: `Bars ✦`, `Bars ✦2`, etc. — auto-numbered per module
- `[✚]` Menubutton for adding instances and loading workspaces
- Right-click context menu: Rename / Change shader / Save workspace /
  Duplicate / Close
- Workspace save (🖫) and load (🗁) buttons in the tab bar

#### i18n — full Polish/English support
- All UI strings, dialogs, and menus go through `T.get()` — no hardcoded text
- `ask_string()` TTK helper replacing `simpledialog.askstring` for consistent
  look with Forest-ttk-theme
- `tk.Listbox` in Load workspace dialog styled to match Forest-dark theme
- New keys in `pl.json` and `en.json`: workspace dialogs, context menu labels,
  color/shader profile dialogs, log viewer, error messages

#### Installer improvements
- `~/.local/bin` added to `PATH` in `.bashrc` after installing user scripts
  (guarded by `LOCAL_BIN_PATH` marker, safe on reinstall)
- `systemctl --user start` now runs after `enable`, with `is-active` check
- Cleaner summary — removed redundant manual-start instructions

#### Process management
- `glava_stop_instance()` waits for process death before returning
- `_toggle_in_progress` lock prevents race conditions on rapid toggle
- `glava-color-daemon` sets `DISPLAY`/`DBUS_SESSION_BUS_ADDRESS`/`XAUTHORITY`
  automatically when missing (no hardcoded `:0` dependency)

---

### 🐛 Known Issues / Limitations

- **Process count on boot** — in some configurations, autostart + daemon may
  both launch instances resulting in 2× expected processes. Workaround: use
  toggle OFF/ON in GUI after login.
- **Color picker** — uses system `colorchooser` dialog (Tk); does not match
  Forest-ttk-theme visually. Custom TTK color picker planned for RC2.
- **Shader profiles** — currently global per module, not per instance.
  Per-instance profiles planned for a future release.
- **Workspace auto-load** — workspace is not automatically loaded on GUI start;
  must be loaded manually via the 🗁 button.

---

### 📂 Directory Layout

```
~/.config/
├── glava/                        ← Template directory (not an instance)
├── glava-inst-1/glava/           ← Instance 1
├── glava-inst-2/glava/           ← Instance 2
└── GlavaMP/
    ├── instances.json            ← Registry + persistent tab state
    ├── profiles.json             ← Shader profiles (global, per module)
    ├── presets.json              ← Color presets
    ├── gui.conf                  ← Window geometry
    └── themes/                   ← Forest-ttk-theme files
```

---

### 🧪 Quick Test

```bash
python3 glava-gui.py
# 1. Click [✚] → select Bars → tab "Bars ✦" appears, GLava starts
# 2. Click [✚] → select Wave → "Wave ✦" appears alongside
# 3. Right-click any tab → Rename, Duplicate, or Close
# 4. Change FPS in Advanced → active instance restarts
# 5. Save workspace (🖫) → close and reopen → load workspace (🗁)
```

---

## [0.5.0] — 2026-04-xx

Modular GUI rewrite — five shader modules with dedicated control panels,
unified geometry calculation, debounced restart logic, i18n framework,
Forest-ttk-theme integration, GLava pre-built `.deb` for Ubuntu 24.04 / Mint 22.x.

## [0.2.2] — 2026-04-xx

Fixed wave/graph gradient, HSV/RGB gradient system, wallpaper lock feature.

## [0.2.0] — 2026-03-xx

Critical shader bug fixes (bars, circle gradient), redesigned gradient system.

## [0.1.0] — 2026-03-xx

Initial release: wallpaper downloader + GLava controller, systemd daemon,
KMeans color extraction, basic Tkinter GUI.
