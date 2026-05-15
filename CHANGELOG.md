# Changelog — bing-glava-suite

---

## [1.0.0] — 2026-05-15

### Multi-instance GLava Studio

This release is a milestone. The application transitions from a single-instance
GLava controller to a full **multi-instance visualization studio** — multiple
independent GLava processes running simultaneously, each with isolated
configuration, dedicated controls, and persistent state.

---

### ✨ New Features

#### Multi-instance Architecture
- **Parallel GLava instances** — run Bars, Wave, Circle, Graph, Radial
  simultaneously, each in its own tab
- **Per-instance process management** — each GLava runs as a tracked
  `subprocess.Popen`; closing a tab stops only that instance (SIGTERM → SIGKILL)
- **Isolated configuration** — each instance gets its own
  `~/.config/glava-inst-{id}/` directory with copied GLSL files and symlinks
  to shared shaders
- **Persistent state** — open tabs, module choices, and custom tab names
  survive application restarts via `instances.json`
- **Source-of-truth from rc.glsl** — module is read directly from the
  instance's `rc.glsl` at startup; `instances.json` serves as fallback only

#### InstanceTabBar (`gui/instance_tab_bar.py`) — new file
- Custom tab bar widget built on `ttk.Notebook` with `height=0` (tab strip only)
- Native Forest-ttk-theme appearance — tabs identical to standard notebook tabs
- `✦` suffix in tab labels with automatic numbering (`Bars ✦`, `Bars ✦2`, …)
- `[✚]` Menubutton opens module selector + "Load workspace" option
- Right-click context menu per tab: Rename / Save session / Save workspace /
  Duplicate / Close
- `content_parent` parameter allows placing tab content in a separate frame
  (used for full-width rendering below the tab strip)
- `show_separator` parameter controls whether the widget draws its own separator

#### Advanced Panel — broadcast audio/FPS to all instances
- `setbufsize`, `setsamplesize`, `setsamplerate`, `setframerate` and
  mirror/interpolation flags are now written to **every** instance's `rc.glsl`
  simultaneously
- All instances are restarted in parallel threads after the debounce delay
- Single-instance fallback preserved

#### New API in `GlavaGUI`
- `get_active_rc_glsl()` — returns `rc.glsl` path for the currently selected tab
- `get_active_glava_dir()` — returns the GLava config directory for the active instance
- `restart_active_instance(module, after_fn)` — restarts only the active instance
- `_inst_modules[inst_id]` — tracks the module per tab

---

### 🔧 Modified Files

| File | Change summary |
|------|---------------|
| `glava-gui.py` | Full rewrite of notebook section; instances dict; process dict; persistence |
| `gui/glava.py` | `glava_start()` returns `Popen`; added `glava_stop_instance`, `glava_restart_instance`, `read_rc_module`; global `pkill` limited to `glava_stop_all()` |
| `gui/instance_tab_bar.py` | **New file** — InstanceTabBar widget |
| `gui/instance.py` | Added `update_instance()` helper |
| `gui/tab_main.py` | All rc.glsl I/O via `app.get_active_rc_glsl()`; restart via `app.restart_active_instance()` |
| `gui/tab_module.py` | Restart via `app.restart_active_instance()` with fallback |
| `gui/tab_advanced.py` | `_write_request` broadcasts to all instances; parallel restart |
| `gui/modules/base.py` | `_schedule_restart()` and `_debounce()` use active-instance API |
| `gui/modules/bars.py` | Instance-specific GLSL paths via `app.active_instance` |
| `gui/modules/wave.py` | As above |
| `gui/modules/circle.py` | As above |
| `gui/modules/graph.py` | As above |
| `gui/modules/radial.py` | As above |

---

### 🏗 Architecture: Before → After

| Aspect | v0.5.x | v1.0.0 |
|--------|--------|--------|
| GLava processes | 1 global | N independent, tracked by PID |
| Config isolation | Single `~/.config/glava/` | Per-instance `~/.config/glava-inst-{id}/` |
| Process termination | `pkill -x glava` (kills all) | SIGTERM per Popen → SIGKILL fallback |
| Tab UI | Static `ttk.Notebook` (Main/Module/Advanced) | Dynamic InstanceTabBar + static Main/Advanced |
| State persistence | None | Full via `instances.json` |
| Audio/FPS settings | Active instance only | Broadcast to all instances, parallel restart |
| Module source of truth | `instances.json` | `rc.glsl` (JSON as fallback) |

---

### 📂 Directory Layout

```
~/.config/
├── glava/                        ← Instance 0 (default, non-deletable)
│   ├── rc.glsl
│   ├── bars.glsl, wave.glsl, …
│   └── bars/, wave/, …  (shader subdirs)
├── glava-inst-1/glava/           ← Instance 1 (copied GLSL + symlinks)
├── glava-inst-2/glava/           ← Instance 2
└── GlavaMP/
    ├── instances.json            ← Registry + persistent tab state
    ├── inst-1/                   ← GUI settings for instance 1
    ├── inst-2/
    └── …
```

---

### ⚠ Known Limitations

- GLava must be in `PATH`
- No new Python dependencies (stdlib + Tkinter only)
- Instance 0 (`~/.config/glava`) is non-deletable by design
- Workspace save/load (session files) — UI present, persistence not yet implemented

---

### 🧪 Quick Test

```bash
python3 glava-gui.py
# 1. Default tab (Instance 0 / Bars) opens automatically
# 2. Click [✚] → select Wave → new tab "Wave ✦" appears, GLava starts
# 3. Click [✚] → select Bars → "Bars ✦2" appears alongside the first
# 4. Right-click any tab → Rename, Duplicate, or Close
# 5. Change FPS in Advanced → all instances restart in parallel
# 6. Close and reopen app → all tabs restored
```

---

---

## Polski — Notatki do wersji 1.0.0

### Multiinstancja GLava Studio

Ta wersja to kamień milowy. Aplikacja przechodzi z kontrolera jednej instancji
GLava do pełnego **studia wizualizacji wieloinstancyjnej** — wiele niezależnych
procesów GLava działających równocześnie, każdy z izolowaną konfiguracją,
dedykowanymi kontrolkami i trwałym stanem.

### Co nowego

- **Równoległe instancje GLava** — Bars, Wave, Circle, Graph, Radial
  jednocześnie, każda w osobnej zakładce
- **Zarządzanie procesami per instancja** — zamknięcie zakładki zatrzymuje
  tylko ten jeden proces (SIGTERM → SIGKILL)
- **Izolowana konfiguracja** — każda instancja ma własny katalog
  `~/.config/glava-inst-{id}/`
- **Trwały stan** — otwarte zakładki, wybrane moduły i własne nazwy zakładek
  przeżywają restart aplikacji (`instances.json`)
- **Nowy widget InstanceTabBar** — pasek zakładek z natywnym wyglądem
  Forest-ttk-theme, przycisk `[✚]` z menu wyboru modułu, menu kontekstowe
  (prawy klik)
- **Ustawienia audio/FPS** w zakładce Zaawansowane są teraz broadcast do
  wszystkich instancji i restartują je równolegle

### Znane ograniczenia

- Zapis/odczyt workspace (zestawów sesji) — interfejs obecny, zapis na dysk
  jeszcze niezaimplementowany
- Instancja 0 (`~/.config/glava`) jest nieusuwalna z założenia

---

## [0.5.0] — 2026-04-xx

Modular GUI rewrite — five shader modules with dedicated control panels,
unified geometry calculation, debounced restart logic, i18n framework,
Forest-ttk-theme integration, GLava pre-built `.deb` for Ubuntu 24.04/Mint 22.x.

## [0.2.2] — 2026-04-xx

Fixed wave/graph gradient, HSV/RGB gradient system using `#define HSV_MODE`,
wallpaper lock feature, `gradient_compare.py` tool.

## [0.2.0] — 2026-03-xx

Critical shader bug fixes (bars gradient, circle gradient), redesigned
gradient system.

## [0.1.0] — 2026-03-xx

Initial release: wallpaper downloader + GLava controller, systemd daemon,
KMeans color extraction, basic Tkinter GUI.
