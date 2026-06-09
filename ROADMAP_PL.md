# Plan rozwoju — GLava Master Panel / bing-glava-suite

Ten dokument gromadzi planowane funkcje, poprawki i pomysły na przyszłe wydania.
Priorytety i harmonogram mogą ulec zmianie w zależności od wyników testów i opinii społeczności.

> 🇬🇧 [English version](ROADMAP.md)

---

## 🚀 Krótki termin

### Poprawki i ulepszenia

- **Wykrywanie źródła tapety** — demon kolorów aktualnie obserwuje `bing-today.jpg`
  bezpośrednio przez `inotifywait`. Plan: wykrywanie środowiska graficznego przy starcie
  (XFCE przez `xfconf-query`, Cinnamon/GNOME przez `gsettings`) i wyciąganie kolorów
  z aktualnie ustawionej tapety pulpitu.
  → [issue #TBD](../../issues)

- **Własny selektor kolorów TTK** — zastąpienie systemowego dialogu `colorchooser.askcolor`
  natywnym widgetem TTK zgodnym z Forest-ttk-theme.
  → [issue #TBD](../../issues)

### Nowe funkcje

- **Kroplomierz / pobieranie koloru z tapety** — możliwość kliknięcia w dowolne miejsce
  miniatury tapety w celu próbkowania koloru, zamiast korzystania wyłącznie
  z automatycznej ekstrakcji KMeans.
  → [issue #TBD](../../issues)

- **Ikona w zasobniku** — lekki wskaźnik w zasobniku systemowym (przez `pystray` lub
  `AppIndicator3`) do szybkiego przełączania Włącz/Wyłącz i podglądu statusu instancji
  bez otwierania pełnego GUI.
  → [issue #TBD](../../issues)

---

## 📦 Średni termin

### Ulepszenia przestrzeni roboczej

- **Menedżer workspace** — dedykowany dialog do zarządzania, zmiany nazw i usuwania
  zapisanych przestrzeni roboczych.
  → [issue #TBD](../../issues)

### Instalator

- **Wykrywanie zależności** — automatyczne wykrywanie brakujących pakietów systemowych
  i informowanie użytkownika o konieczności ich instalacji zamiast cichego niepowodzenia.
  → [issue #TBD](../../issues)

- **Szersze wsparcie dla dystrybucji opartych na Debianie** — testowanie i naprawianie
  kompatybilności instalatora na Debianie 12, Ubuntu 22.04, Pop!_OS i innych pochodnych
  Debiana poza Linux Mint 22 / Ubuntu 24.04.
  → [issue #TBD](../../issues)

---

## 🎬 Przyszłość / Bez harmonogramu

- **Paczka GLava z obsługą wtyczki OBS** — osobna skompilowana paczka z wtyczką
  wirtualnej kamery OBS.
  → [issue #TBD](../../issues)

- **Kompatybilność z menedżerami okien** — testowanie i naprawianie kompatybilności
  z GNOME, KDE Plasma, MATE, LXQt, Openbox, i3/sway (tylko X11). Każde środowisko
  może wymagać innych mechanizmów autostartu, wykrywania geometrii i zapytań o tapetę.
  → [issue #TBD](../../issues)

- **Opcjonalne moduły / shadery społecznościowe** — przeglądarka w aplikacji do
  instalowania społecznościowych shaderów GLava (np. NCS Spectrum). Wymaga sprzętu
  z OpenGL 4.2+ i zewnętrznych testerów.
  → [issue #TBD](../../issues)

- **AppImage / przenośna paczka** — samodzielna paczka niewymagająca instalacji,
  dla użytkowników preferujących unikanie `sudo ./install.sh`.

---

## 💡 Pomysły pod rozwagą

- **Historia kolorów** — dziennik ostatnio wyekstrahowanych palet z możliwością
  ponownego zastosowania dowolnej z nich.
  → [issue #TBD](../../issues)

- **Wsparcie wielu monitorów** — presety geometrii instancji per monitor.
  → [issue #TBD](../../issues)

- **Interfejs CLI** — polecenie `glava-ctl` do skryptowego zarządzania instancjami bez GUI.
  → [issue #TBD](../../issues)

---

> **Wayland:** GLava wymaga X11. Użytkownicy Waylanda — zobacz [WayVes](https://github.com/Roonil/WayVes).

---

*Ostatnia aktualizacja: 2026-06*
