# Changelog — bing-glava-suite

---

## [1.0.0-RC2] — 2026-06-11

### Bug fixes after RC1 testing

- **fix:** Duplicate GLava processes when changing FPS or audio parameters
  in the Advanced tab — `_debounce_request` now respects the
  `_restart_in_progress` lock used by the rest of the GUI
- **fix:** Toggle on/off deadlock — rapidly clicking the toggle could leave
  the lock permanently set, making it impossible to re-enable GLava without
  restarting the GUI; fixed by releasing the lock when no instances are registered
- **fix:** Workspace save/load did not preserve smoothing parameters
  (`gravity`, `smooth factor`, `avg frames`, `FFT scale`, `bass cutoff`);
  values were read with a `#define`-only parser but `smooth_parameters.glsl`
  uses `#request` exclusively — both save and load paths corrected

### Documentation
- ROADMAP and ROADMAP_PL: Wayland entry removed (X11-only by design),
  GitHub Issues linked for all planned features
- TESTING.md: corrected scenario descriptions 2.5, 3.1, 3.3, 4.1, 4.4,
  7.2 (removed), 8.1, 8.2 based on RC1 testing findings
- GitHub Pages project website added with feature matrix and screenshots

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
