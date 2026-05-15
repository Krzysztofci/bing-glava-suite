# bing-glava-suite

**Multi-instance GLava visualization studio for Linux desktop.**

Automated Bing wallpaper downloads + GLava audio visualizer with full
multi-instance control — run multiple independent visualizations simultaneously,
each with its own shader, geometry, and color scheme.

Tested on **Linux Mint 22 XFCE/Cinnamon**, Intel HD 3000 (ThinkPad T420).

---

## Features

- **Multiple GLava instances** — Bars, Wave, Circle, Graph, Radial running
  in parallel, each in its own tab
- **Per-instance isolation** — separate config directory, separate GLava
  process, separate shader settings
- **Persistent sessions** — open tabs and settings survive application restarts
- **Automated Bing wallpaper** — daily download with region selection
- **KMeans color sync** — extract dominant colors from wallpaper → apply to
  all GLava instances
- **Forest-ttk-theme** — clean dark/light UI
- **Geometry auto-calculation** — correct size/position per screen and taskbar
- **Shader profiles** — save and restore parameter sets per module

---

## Screenshots

*(add screenshots here)*

---

## Installation

### Requirements

- Linux (Mint 22 / Ubuntu 24.04 recommended)
- Python 3.10+
- Tkinter (`python3-tk`)
- Pillow (`python3-pil`) — for color extraction
- GLava — use the pre-built `.deb` in Releases or build from source

### Quick install

```bash
git clone https://github.com/Krzysztofci/bing-glava-suite.git
cd bing-glava-suite
./install.sh
```

The installer:
1. Copies files to `~/.local/bin/GlavaMP/`
2. Copies system GLava config from `/etc/xdg/glava/` if no user config exists
3. Installs systemd user service for wallpaper daemon
4. Creates desktop entry

### Manual run (no install)

```bash
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
| Right-click tab | Context menu: Rename / Duplicate / Save session / Close |
| `[✚]` button | Add new instance |
| Close tab | Stops that instance's GLava process only |

### Main panel

Controls colors, gradients, and color presets. Changes apply to the
**currently selected tab** (the one with the green underline).

### Module tab

Per-instance shader parameters — shape, smoothing, flags. Each tab has
independent settings.

### Advanced panel

Audio settings (`setbufsize`, `setsamplesize`, `setsamplerate`) and FPS limit
are **broadcast to all instances simultaneously** and trigger a parallel restart
of all GLava processes.

### Enabling / Disabling GLava

The Enable/Disable button in the Main panel:
- **Disable** — stops all GLava processes (`pkill`)
- **Enable** — starts all registered instances in parallel, each with its
  correct module and `XDG_CONFIG_HOME`

---

## Directory structure

```
~/.config/
├── glava/                    ← Instance 0 (default, non-deletable)
├── glava-inst-1/glava/       ← Instance 1
├── glava-inst-2/glava/       ← Instance 2
└── GlavaMP/
    ├── instances.json        ← Tab registry + persistent state
    ├── inst-1/               ← GUI profiles/presets for instance 1
    ├── inst-2/
    ├── gui.conf              ← Window geometry
    └── themes/               ← Forest-ttk-theme files
```

---

## Technical notes

- Process management: SIGTERM → 2s wait → SIGKILL per instance
- `XDG_CONFIG_HOME` set per instance so GLava reads the correct config dir
- Module source of truth: `rc.glsl` `#request mod <name>` line
  (not `instances.json`)
- All shader writes go through `app.active_instance` — no global path
- No new Python dependencies beyond stdlib + Tkinter + Pillow

---

## License

MIT — see [LICENSE](LICENSE)

GLava: GPLv3
Forest-ttk-theme: MIT

---

---

## Polski

### bing-glava-suite — wieloinstancyjne studio wizualizacji GLava

Automatyczne pobieranie tapet Bing + pełna kontrola GLava z obsługą wielu
niezależnych instancji uruchomionych jednocześnie.

Testowane na **Linux Mint 22 XFCE/Cinnamon**, Intel HD 3000 (ThinkPad T420).

### Funkcje

- **Wiele instancji GLava** — Bars, Wave, Circle, Graph, Radial równocześnie,
  każda w osobnej zakładce
- **Izolacja per instancja** — osobny katalog konfiguracyjny, osobny proces
  GLava, osobne ustawienia shaderów
- **Trwałe sesje** — zakładki i ustawienia przeżywają restart aplikacji
- **Automatyczne tapety Bing** — codzienne pobieranie z wyborem regionu
- **Synchronizacja kolorów KMeans** — ekstrakcja dominujących kolorów z tapety
  i aplikowanie do wszystkich instancji GLava
- **Auto-geometria** — automatyczne obliczanie rozmiaru i pozycji okna GLava
- **Profile shaderów** — zapis i odczyt zestawów parametrów per moduł

### Instalacja

```bash
git clone https://github.com/Krzysztofci/bing-glava-suite.git
cd bing-glava-suite
./install.sh
```

### Użytkowanie

Kliknij `[✚]` na pasku zakładek → wybierz moduł → nowa zakładka pojawia się
i GLava startuje automatycznie. Prawy klik na zakładce otwiera menu kontekstowe
(Zmień nazwę / Duplikuj / Zamknij).

Ustawienia w zakładce **Zaawansowane** (audio, FPS) są aplikowane do
**wszystkich instancji** jednocześnie.

### Struktura katalogów

```
~/.config/
├── glava/                    ← Instancja 0 (domyślna, nieusuwalna)
├── glava-inst-1/glava/       ← Instancja 1
└── GlavaMP/
    ├── instances.json        ← Rejestr zakładek i stan sesji
    └── …
```

### Licencja

MIT — patrz [LICENSE](LICENSE)
