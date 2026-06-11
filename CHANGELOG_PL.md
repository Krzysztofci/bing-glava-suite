# Dziennik zmian — bing-glava-suite

---

## [1.0.0-RC2] — 2026-06-11

### Poprawki błędów po testach RC1

- **fix:** Zduplikowane procesy GLava przy zmianie FPS lub parametrów audio
  w zakładce Advanced — `_debounce_request` respektuje teraz blokadę
  `_restart_in_progress` używaną przez resztę GUI
- **fix:** Zakleszczenie przełącznika on/off — szybkie klikanie mogło trwale
  zablokować przełącznik, uniemożliwiając ponowne włączenie GLava bez
  restartu GUI; naprawione przez zwolnienie blokady gdy brak zarejestrowanych instancji
- **fix:** Zapis/odczyt workspace nie zachowywał parametrów wygładzania
  (`grawitacja`, `wygładzanie`, `klatek avg`, `skala FFT`, `odcięcie basu`);
  wartości były odczytywane parserem `#define`, podczas gdy `smooth_parameters.glsl`
  używa wyłącznie `#request` — naprawiono obie ścieżki: zapis i odczyt

### Dokumentacja
- ROADMAP i ROADMAP_PL: usunięto wpis Wayland (projekt tylko X11),
  dodano linki do GitHub Issues przy wszystkich planowanych funkcjach
- TESTING.md: poprawiono opisy scenariuszy 2.5, 3.1, 3.3, 4.1, 4.4,
  7.2 (usunięty), 8.1, 8.2 na podstawie wyników testów RC1
- Dodano stronę projektu GitHub Pages z macierzą funkcji i zrzutami ekranu

---

## [1.0.0-RC1] — 2026-06-07

### Release Candidate 1 — Multi-instance GLava Studio

Pierwszy kandydat do wydania przepisanej wersji multi-instancyjnej.
Podstawowa funkcjonalność jest stabilna; znane problemy opisano poniżej.

---

### ✨ Nowości w RC1 (od v0.5.0)

#### Architektura multi-instancyjna
- Uruchamianie wielu wizualizatorów GLava jednocześnie — Bars, Wave, Circle,
  Graph, Radial — każdy we własnej karcie z izolowaną konfiguracją i procesem
- Per-instancja `XDG_CONFIG_HOME` pod `~/.config/glava-inst-{id}/glava/`
- Wszystkie instancje równorzędne — każdą można zamknąć lub usunąć, łącznie z inst-0
- Trwały stan przez `instances.json` — karty przeżywają restarty aplikacji
- Źródło prawdy o module: linia `#request mod` w `rc.glsl`, nie `instances.json`

#### InstanceTabBar
- Własny pasek kart oparty na `ttk.Notebook` (height=0) z Forest-ttk-theme
- Etykiety kart: `Bars ✦`, `Bars ✦2` itp. — automatyczna numeracja per moduł
- Przycisk `[✚]` do dodawania instancji i wczytywania workspace
- Menu kontekstowe prawym przyciskiem: Zmień nazwę / Zmień shader /
  Zapisz workspace / Duplikuj / Zamknij
- Przyciski zapisu (🖫) i wczytywania (🗁) workspace w pasku kart

#### i18n — pełna obsługa polskiego i angielskiego
- Wszystkie ciągi UI, dialogi i menu przechodzą przez `T.get()` — brak hardkodowanego tekstu
- Pomocnik `ask_string()` TTK zastępujący `simpledialog.askstring` dla spójnego
  wyglądu z Forest-ttk-theme
- `tk.Listbox` w dialogu wczytywania workspace dopasowany stylem do Forest-dark
- Nowe klucze w `pl.json` i `en.json`: dialogi workspace, etykiety menu kontekstowego,
  dialogi profili kolorów/shaderów, przeglądarka logów, komunikaty błędów

#### Ulepszenia instalatora
- `~/.local/bin` dodany do `PATH` w `.bashrc` po instalacji skryptów użytkownika
  (chroniony markerem `LOCAL_BIN_PATH`, bezpieczny przy reinstalacji)
- `systemctl --user start` uruchamiany po `enable` z sprawdzeniem `is-active`
- Czystsze podsumowanie — usunięto zbędne instrukcje ręcznego startu

#### Zarządzanie procesami
- `glava_stop_instance()` czeka na śmierć procesu przed powrotem
- Blokada `_toggle_in_progress` zapobiega wyścigom przy szybkim przełączaniu
- `glava-color-daemon` ustawia `DISPLAY`/`DBUS_SESSION_BUS_ADDRESS`/`XAUTHORITY`
  automatycznie gdy brakuje (brak zależności od hardkodowanego `:0`)

---

### 🐛 Znane problemy / Ograniczenia

- **Liczba procesów przy starcie** — w niektórych konfiguracjach autostart i daemon
  mogą razem uruchomić instancje dając 2× oczekiwaną liczbę procesów.
  Rozwiązanie: użyj toggle OFF/ON w GUI po zalogowaniu.
- **Selektor kolorów** — używa systemowego dialogu `colorchooser` (Tk);
  nie pasuje wizualnie do Forest-ttk-theme. Własny selektor TTK planowany
  w przyszłym wydaniu.
- **Auto-wczytywanie workspace** — workspace nie jest automatycznie wczytywany
  przy starcie GUI; należy wczytać ręcznie przyciskiem 🗁.

> Błędy naprawione w RC2: duplikowanie procesów przy zmianie parametrów w zakładce
> Advanced, zakleszczenie przełącznika on/off, parametry wygładzania niezapisywane
> w workspace.

---

### 📂 Struktura katalogów

```
~/.config/
├── glava/                        ← Katalog wzorcowy (nie instancja)
├── glava-inst-1/glava/           ← Instancja 1
├── glava-inst-2/glava/           ← Instancja 2
└── GlavaMP/
    ├── instances.json            ← Rejestr + trwały stan kart
    ├── profiles.json             ← Profile shaderów (globalne, per moduł)
    ├── presets.json              ← Presety kolorów
    ├── gui.conf                  ← Geometria okna
    └── themes/                   ← Pliki Forest-ttk-theme
```

---

### 🧪 Szybki test

```bash
python3 glava-gui.py
# 1. Kliknij [✚] → wybierz Bars → pojawia się karta "Bars ✦", GLava startuje
# 2. Kliknij [✚] → wybierz Wave → "Wave ✦" pojawia się obok
# 3. Prawy przycisk na karcie → Zmień nazwę, Duplikuj lub Zamknij
# 4. Zmień FPS w Advanced → aktywna instancja restartuje się
# 5. Zapisz workspace (🖫) → zamknij i otwórz ponownie → wczytaj workspace (🗁)
```

---

## [0.5.0] — 2026-04-xx

Przepisane modułowe GUI — pięć modułów shaderów z dedykowanymi panelami
sterowania, zunifikowane obliczanie geometrii, debounced restart, framework i18n,
integracja Forest-ttk-theme, prekompilowany `.deb` GLava dla Ubuntu 24.04 / Mint 22.x.

## [0.2.2] — 2026-04-xx

Naprawiony gradient wave/graph, system gradientu HSV/RGB, funkcja blokady tapety.

## [0.2.0] — 2026-03-xx

Krytyczne poprawki shaderów (bars, gradient circle), przeprojektowany system gradientu.

## [0.1.0] — 2026-03-xx

Pierwsze wydanie: pobieracz tapet + kontroler GLava, demon systemd,
ekstrakcja kolorów KMeans, podstawowe GUI Tkinter.
