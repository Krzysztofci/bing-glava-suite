# Changelog — bing-glava-suite

---

## [1.0.0-RC5] — 2026-06-29

### Release Candidate 5 — 100% logic test coverage

---

### 🧪 Testing & coverage

Full logic-coverage push across the entire codebase, tracked with the
project's custom `logic-cov` AST-based analyzer (cross-referenced against
`pytest-cov`). **Logic coverage: 61% → 100% (2951/2951 logic statements,
zero missing)** across every file in `scripts/gui/` and `scripts/glava-gui.py`.

- All GUI parameter widgets (`bars`, `circle`, `radial`, `wave`) — closed
  remaining gaps in screen-info fallback handling, nested slider/offset
  callbacks, and inter-dependent parameter clamping (wave thickness min/max).
- `gui/instance_tab_bar.py` — covered remaining `TclError`/`IndexError`
  defensive branches (rename/relabel on a destroyed tab, index-map refresh
  race).
- `gui/widgets.py` — covered the success path of the custom slider-thumb
  styling (`_ensure_shift_style`), previously only exercised through its
  fallback branch.
- `gui/glava.py` — closed remaining exception-handling branches (PID file
  I/O, SIGTERM→SIGKILL escalation, legacy `glava_restart`/`glava_stop`
  paths) and the `instance=`-aware PID-write path in `glava_start`.
- **`glava-gui.py` workspace save/load** (`_save_workspace`, `_load_workspace`,
  `_save_window_state`) — first-ever test coverage for these modal-dialog
  flows (previously 75% file coverage, now 100%). Includes the full
  per-instance recreation pipeline (GLSL defines, smoothing parameters,
  geometry, colors, restart) and both dialogs' cancel/error paths.
- **`scripts/glava-colors-auto-mi`** (multi-instance wallpaper-color
  auto-updater, invoked by the color daemon/cron) — first-ever test suite
  (39 tests, 100% statement coverage). This script has no `.py` extension
  and sits outside the project's configured coverage scope, so it was
  previously completely unmeasured despite running in production on every
  wallpaper refresh.

### 🐛 Bug fixes

- **`gui/glava.py::glava_start` — removed leftover debug instrumentation.**
  An unconditional, untry/excepted debug-log block (timestamp + 5-frame
  stack trace) was writing to `~/.local/logs/glava-start.log` on *every*
  single GLava start — including every automated restart triggered by
  `glava-colors-auto-mi` on wallpaper change. No rotation, no cap, real
  disk usage in normal operation. Also silently broke the function's own
  docstring (dead code after the debug block, since a docstring only
  counts as one if it's the first statement). Removed; real docstring restored.
- `gui/tab_advanced.py` — removed two confirmed-unreachable dead branches
  (`_read_request_int` except clause, `_restart_all` dead `continue`),
  found and verified during coverage analysis (including cross-file
  interaction with `glava-gui.py`'s `restart_active_instance`).
- `gui/tab_main.py` — fixed a resource leak (`open(path).read()` without
  `with`) in `_update_geometry_for_module`.
- `.github/workflows/test.yml` — removed a duplicate "Run tests" step that
  was running pytest twice per job; replaced `sleep 1` before Xvfb startup
  with an `xdpyinfo` poll loop; bumped Xvfb resolution so the default
  1040×768 window fits without clamping.

### 🔍 Known issues (carried over from RC4, still open)

- Shader profile save (bars) does not include `setbufsize`, `setsamplesize`,
  `setmirror`, `setinterpolate`
- Audio buffer size change affects visualizer bar width (unintended side effect)
- FPS change affects animation speed and bar height in bars module
- Daemon logs in Advanced tab are sparse — only color changes logged,
  other events not covered; log may show stale data

### 📌 Tooling note (not a product issue — logged for the `logic-cov` backlog)

`logic-cov`'s name-based heuristic classifies `gui/theme.py::TCheckbutton`
as `LOGIC` (matches `"check"` inside `"tcheckbutton"`) despite being a
trivial `ttk.Checkbutton` wrapper identical in nature to `TFrame`/`TLabel`/
`TEntry`/`TSeparator` (deliberately untested elsewhere in the suite). A
placeholder test was added purely to close the reported gap — see
`tests/test_theme.py` for the rationale comment. Full write-up of this and
other `logic-cov` findings (extension-based blind spot for shebang scripts,
GUI-weight masking real logic in heavily-widget-laden functions, and a
proposed test-map feature for the tool's own roadmap) is in
`logic-cov-feedback.md`.

---

## [1.0.0-RC4] — 2026-06-15

### Release Candidate 4 — CI infrastructure & daemon fix

---

### 🐛 Bug fixes

#### glava-color-daemon: startup color update removed
- Removed startup check that updated colors when wallpaper was newer than shader.
  This caused unwanted color updates on daemon start regardless of actual need.

#### Geometry auto-calculation off-by-one
- Taskbar height 39px now correctly sets Y offset to -39px (was -40px).

### 🔧 Infrastructure

- Added GitHub Actions CI — pytest on Python 3.10 / 3.11 / 3.12 + Ruff linting
- Added Codecov coverage reporting (42%)
- Added `pyproject.toml` with Ruff configuration and project metadata
- Ruff auto-fix: removed trailing whitespace from blank lines across 19 files

### 🔍 Known issues (deferred to future release)

- Shader profile save (bars) does not include `setbufsize`, `setsamplesize`,
  `setmirror`, `setinterpolate`
- Audio buffer size change affects visualizer bar width (unintended side effect)
- FPS change affects animation speed and bar height in bars module
- Daemon logs in Advanced tab are sparse — only color changes logged,
  other events not covered; log may show stale data

---

## [1.0.0-RC3] — 2026-06-14

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

## [1.0.0-RC2] — 2026-06-11

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

## [1.0.0-RC1] — 2026-06-07

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
  Forest-ttk-theme visually. Custom TTK color picker planned for a future release.
- **Workspace auto-load** — workspace is not automatically loaded on GUI start;
  must be loaded manually via the 🗁 button.

> Issues fixed in RC2: duplicate processes on Advanced tab parameter change,
> toggle deadlock, workspace smoothing parameters not saved/restored.

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
