# bing-glava-suite

Automatyczne tapety Bing z dopasowaniem kolorów GLava dla systemów Linux.

> **English summary below the Polish documentation.**

---

## Co to robi?

Projekt składa się z dwóch niezależnych, ale współpracujących mechanizmów:

**1. Pobieranie tapety Bing**
Codziennie (przez cron) skrypt pobiera dzisiejsze zdjęcie dnia z Bing w rozdzielczości UHD, ustawia je jako tapetę pulpitu (XFCE i/lub Cinnamon) oraz tło ekranu logowania LightDM.

**2. Automatyczne kolory GLava**
Usługa systemd nasłuchuje zmian pliku tapety. Gdy tapeta się zmieni, algorytm KMeans analizuje jej 3 dominujące kolory i aktualizuje shader GLava — wizualizator audio dopasowuje się do tapety bez żadnej ingerencji użytkownika.

**3. Ręczna kontrola (opcjonalna)**
Panel GUI pozwala ręcznie dobierać kolory, zapisywać własne presety i przełączać tryby. Daemon szanuje wybór użytkownika i nie nadpisuje ustawień ręcznych.

---

## Wymagania

### System
- Linux (testowano na Linux Mint 22.3 XFCE)
- Środowisko graficzne: **XFCE** (pełne wsparcie) lub **Cinnamon** (tapety)
- `systemd` z obsługą usług użytkownika (`systemctl --user`)
- Kompozytor okien (picom, compton lub wbudowany w XFCE/Cinnamon) — wymagany przez GLava

### Pakiety (instalowane automatycznie przez `install.sh`)
| Pakiet | Do czego |
|---|---|
| `curl`, `wget`, `jq` | Pobieranie tapety Bing |
| `inotify-tools` | Wykrywanie zmian tapety przez daemon |
| `python3`, `python3-pil`, `python3-sklearn`, `python3-numpy` | Analiza kolorów tapety |
| `python3-tk` | Panel GUI |

### Wymagane ręcznie
- **[GLava](https://github.com/jarcode-foss/glava)** — wizualizator audio (nie jest w standardowych repozytoriach, wymaga kompilacji ze źródeł)

---

## Instalacja GLava (wymagana przed instalacją projektu)

GLava nie jest dostępna w repozytoriach apt i wymaga kompilacji ze źródeł. Poniższe kroki działają na Ubuntu 24.04 / Linux Mint 22.x:

```bash
# Zależności do kompilacji
sudo apt install -y \
    libpulse-dev libgl-dev libglx-dev libx11-dev libxext-dev \
    libxrender-dev libxcomposite-dev meson ninja-build \
    pkg-config gcc g++ git

# Pobierz źródła
git clone https://github.com/jarcode-foss/glava
cd glava

# Poprawki kompatybilności z GCC 13 (Ubuntu 24.04+)
sed -i '/#include <error.h>/a #include <cstdio>\n#include <cerrno>' glfft/glfft_gl_interface.hpp
sed -i '/#include "glfft.hpp"/a #include <stdexcept>' glfft/glfft_wisdom.cpp
sed -i '1s/^/#include <cstdio>\n/' glfft/glfft_gl_interface.cpp
sed -i 's/__attribute__((noreturn, visibility("default"))) void (\*glava_abort)/extern __attribute__((noreturn, visibility("default"))) void (*glava_abort)/' glava/glava.h
sed -i 's/__attribute__((noreturn, visibility("default"))) void (\*glava_return)/extern __attribute__((noreturn, visibility("default"))) void (*glava_return)/' glava/glava.h

# Kompilacja i instalacja
meson build --prefix /usr -Ddisable_obs=true
ninja -C build
sudo ninja -C build install
```

### Konfiguracja GLava po instalacji

```bash
# Skopiuj domyślną konfigurację
glava --copy-config
sudo chown -R $USER:$USER ~/.config/glava

# Zastąp symlinki prawdziwymi katalogami (wymagane)
rm -rf ~/.config/glava/bars
cp -r /etc/xdg/glava/bars ~/.config/glava/bars
rm -rf ~/.config/glava/graph
cp -r /etc/xdg/glava/graph ~/.config/glava/graph
sudo chown -R $USER:$USER ~/.config/glava
```

> **Uwaga:** Warningi `using "window" transform explicitly is deprecated` są normalne i nie wpływają na działanie.

---

## Instalacja projektu

```bash
git clone https://github.com/TWÓJ_LOGIN/bing-glava-suite.git
cd bing-glava-suite
sudo ./install.sh
```

Instalator zapyta o nazwę użytkownika, zainstaluje zależności apt, skopiuje skrypty, zainstaluje szablon shadera, skonfiguruje cron i usługę systemd.

### Po instalacji

```bash
# Uruchom usługę systemd (bez wylogowywania)
systemctl --user start glava-color-daemon

# Pobierz pierwszą tapetę ręcznie (opcjonalnie, cron zrobi to automatycznie)
sudo ~/.local/bin/bing-downloader.sh
```

Przy kolejnych logowaniach usługa startuje automatycznie.

---

## Struktura projektu

```
bing-glava-suite/
├── install.sh                  # Instalator
├── UNLICENSE                   # Licencja (domena publiczna)
├── README.md
├── config/
│   └── graph_red.frag          # Szablon shadera GLava (wymagany)
├── scripts/
│   ├── bing-downloader.sh      # Pobieranie tapety Bing (cron, root)
│   ├── glava-color-daemon      # Demon inotifywait → auto kolory (systemd user)
│   ├── glava-colors-auto       # Generowanie kolorów z tapety (Python/KMeans)
│   ├── glava-colorswitch       # Toggle: tryb auto ↔ tryb czerwony
│   ├── glava-toggle            # Włącz/wyłącz GLava
│   └── glava-gui.py            # Panel GUI (Tkinter)
└── systemd/
    └── glava-color-daemon.service
```

---

## Jak to działa — przepływ danych

```
cron (co godzinę, root)
  └─► bing-downloader.sh
        ├─► ~/Pictures/Bing/bing_today.jpg  (tapeta)
        ├─► /usr/share/backgrounds/login-bing.jpg  (ekran logowania)
        └─► xfconf-query / gsettings  (ustawia tapetę w DE)
                │
                │ (zmiana pliku wyzwala inotifywait)
                ▼
systemd user service: glava-color-daemon
  └─► glava-colors-auto
        ├─► KMeans → 3 kolory dominujące
        └─► ~/.config/glava/graph/1.frag  (zaktualizowany shader)
              └─► restart glava --desktop
```

---

## Flagi stanu

Pliki flag w `~/.config/glava/` sterują zachowaniem daemona i GUI:

| Plik | Znaczenie |
|---|---|
| `red.shift` | Aktywny tryb RED lub ręczny — daemon nie nadpisuje kolorów |
| `manual.shift` | Kolory ustawione przez GUI — daemon nie nadpisuje |
| `.glava_disabled` | GLava wyłączona przez użytkownika — daemon jej nie uruchamia |

Wszystkie flagi są usuwane przez **„Przywróć Bing (auto)"** w GUI lub bezpośrednio przez `glava-colors-auto`.

---

## Szablon shadera `graph_red.frag`

Plik `config/graph_red.frag` jest dołączony do projektu i instalowany automatycznie do `~/.config/glava/graph_red.frag`. Jest to autorski preset shadera GLava — **nie jest to domyślna konfiguracja GLava**.

Różni się od domyślnego `graph/1.frag` tym, że zamiast prostego makra `#define COLOR` używa własnego silnika gradientu z trzema kontrolowanymi wektorami kolorów:

```glsl
vec3 bottom = vec3(0.5, 0.0, 0.0);   // kolor dołu wykresu
vec3 mid    = vec3(0.9, 0.1, 0.1);   // kolor środka
vec3 top    = vec3(0.8, 0.8, 0.8);   // kolor góry
```

`glava-colors-auto` nadpisuje te trzy linie kolorami wygenerowanymi z aktualnej tapety. Domyślny preset to gradient od ciemnego bordowego przez czerwień do jasnoszarego — tryb „red" używany gdy tapeta nie jest załadowana lub użytkownik przełączy się ręcznie.

> **Uwaga:** Instalator nie nadpisuje istniejącego pliku `graph_red.frag` — jeśli masz własny preset, zostanie zachowany.

---

## Ręczna kontrola

### Panel GUI
```bash
glava-gui          # (jeśli ~/.local/bin jest w PATH)
# lub
python3 ~/.local/bin/glava-gui.py
```

### Terminal
```bash
glava-toggle       # włącz/wyłącz GLava
glava-colorswitch  # przełącz tryb auto ↔ czerwony
glava-colors-auto  # wymuś regenerację kolorów z tapety
```

### Usługa systemd
```bash
systemctl --user status glava-color-daemon
systemctl --user restart glava-color-daemon
systemctl --user stop glava-color-daemon
```

### Logi
```bash
tail -f ~/.local/logs/glava-color-daemon.log
tail -f ~/.local/logs/bing-downloader.log
```

---

## Znane ograniczenia

- **GLava wymaga sprzętowego OpenGL** — nie działa w maszynach wirtualnych z software renderingiem (VMware SVGA, VirtualBox SVGA3D bez akceleracji).
- **XFCE:** skrypt używa `xfdesktop` (nie `xfce4-desktop`) i `xfconf-query` przez `su -c` zamiast `sudo -u` ze względu na ograniczenia DBUS przy uruchamianiu przez roota.
- **Tapeta Bing:** pobierana z regionu DE (Niemcy) — można zmienić parametr `mkt=de-DE` w `bing-downloader.sh` na inny region.
- **Pierwsza tapeta po instalacji:** jeśli plik `bing_today.jpg` już istnieje, daemon czeka na jego zmianę. Aby wymusić aktualizację kolorów od razu: `touch ~/Pictures/Bing/bing_today.jpg`

---

## Deinstalacja

```bash
# Wyłącz i usuń usługę
systemctl --user disable --now glava-color-daemon

# Usuń skrypty
rm -f ~/.local/bin/bing-downloader.sh \
       ~/.local/bin/glava-color-daemon \
       ~/.local/bin/glava-colors-auto \
       ~/.local/bin/glava-colorswitch \
       ~/.local/bin/glava-toggle \
       ~/.local/bin/glava-gui \
       ~/.local/bin/glava-gui.py

# Usuń unit systemd
rm -f ~/.config/systemd/user/glava-color-daemon.service
systemctl --user daemon-reload

# Usuń wpis cron (jako root)
sudo crontab -e   # usuń linię z bing-downloader.sh
```

---

## Licencja

**The Unlicense** — domena publiczna. Rób z tym co chcesz.  
Szczegóły w pliku `UNLICENSE`.

---

---

## English Summary

**bing-glava-suite** automatically downloads the Bing daily wallpaper (UHD), sets it as the desktop background (XFCE / Cinnamon) and login screen, then uses KMeans colour analysis to update GLava's audio visualizer shader colours to match the wallpaper — all without user intervention.

**Components:**
- `bing-downloader.sh` — hourly cron job (runs as root), fetches wallpaper
- `glava-color-daemon` — systemd user service, watches wallpaper file via `inotifywait`, triggers colour update
- `glava-colors-auto` — Python script, KMeans → writes colours to GLava shader
- `glava-colorswitch` — toggles between auto (wallpaper) and red preset mode
- `glava-toggle` — enable/disable GLava
- `glava-gui.py` — Tkinter GUI for manual colour picking, presets and mode switching
- `config/graph_red.frag` — custom GLava shader template (required, installed automatically)

**GLava installation:** GLava is not in standard apt repositories and must be compiled from source. See the Polish section above for a tested build recipe for Ubuntu 24.04 / Linux Mint 22.x (includes GCC 13 compatibility patches).

**Install:** `sudo ./install.sh` — prompts for username, installs apt dependencies, copies shader template, sets up cron and systemd service.

**Known limitations:** GLava requires hardware OpenGL acceleration — does not work in virtual machines with software rendering. XFCE support uses `xfdesktop` process name and `su -c` for `xfconf-query` calls due to DBUS restrictions when running as root.

**License:** Public domain (The Unlicense).
