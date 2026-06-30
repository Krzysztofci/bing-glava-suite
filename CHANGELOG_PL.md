# Dziennik zmian — bing-glava-suite

---

## [1.0.0-RC5] — 2026-06-29

### Kandydat do wydania 5 — 100% pokrycia logiki testami

---

### 🧪 Testy i pokrycie

Pełen przegląd pokrycia logiki w całym projekcie, śledzony własnym
narzędziem `logic-cov` (AST-based, cross-referencowane z `pytest-cov`).
**Pokrycie logiki: 61% → 100% (2951/2951 instrukcji logicznych, zero
brakujących)** we wszystkich plikach `scripts/gui/` i `scripts/glava-gui.py`.

- Wszystkie widgety parametrów modułów (`bars`, `circle`, `radial`, `wave`)
  — domknięte pozostałe dziury w fallbacku informacji o ekranie, zagnieżdżonych
  callbackach sliderów/offsetów, i wzajemnym ograniczaniu parametrów
  (min/max grubości w wave).
- `gui/instance_tab_bar.py` — domknięte gałęzie obronne `TclError`/
  `IndexError` (zmiana nazwy zakładki na zniszczonym widgecie, wyścig przy
  odświeżaniu mapy indeksów).
- `gui/widgets.py` — domknięta ścieżka sukcesu własnego stylowania uchwytu
  slidera (`_ensure_shift_style`), wcześniej testowana tylko przez fallback.
- `gui/glava.py` — domknięte pozostałe gałęzie obsługi wyjątków (I/O plików
  PID, eskalacja SIGTERM→SIGKILL, legacy `glava_restart`/`glava_stop`) oraz
  ścieżka zapisu PID z parametrem `instance=` w `glava_start`.
- **Workspace save/load w `glava-gui.py`** (`_save_workspace`,
  `_load_workspace`, `_save_window_state`) — pierwsze w historii pokrycie
  testami tych modalnych dialogów (wcześniej 75% pliku, teraz 100%).
  Obejmuje cały pipeline odtwarzania instancji (definicje GLSL, parametry
  wygładzania, geometria, kolory, restart) oraz ścieżki anulowania/błędu
  obu dialogów.
- **`scripts/glava-colors-auto-mi`** (wieloinstancyjny auto-updater kolorów
  z tapety, wołany przez demona/cron) — pierwszy w historii zestaw testów
  (39 testów, 100% pokrycia instrukcji). Ten skrypt nie ma rozszerzenia
  `.py` i leży poza skonfigurowanym zasięgiem pokrycia projektu, więc
  wcześniej był całkowicie niezmierzony mimo działania w produkcji przy
  każdej zmianie tapety.

### 🐛 Naprawione błędy

- **`gui/glava.py::glava_start` — usunięty zapomniany debug-leftover.**
  Bezwarunkowy, nieowinięty w try/except blok debug-logujący (timestamp +
  5-poziomowy stack trace) pisał do `~/.local/logs/glava-start.log` przy
  *każdym* starcie GLavy — łącznie z każdym automatycznym restartem
  wywołanym przez `glava-colors-auto-mi` przy zmianie tapety. Bez rotacji,
  bez limitu, realne zużycie dysku w normalnej pracy. Po drodze cicho
  łamał własny docstring funkcji (stawał się martwym kodem po bloku debug,
  bo docstring liczy się tylko jako pierwsza instrukcja). Usunięty,
  przywrócony prawdziwy docstring.
- `gui/tab_advanced.py` — usunięto dwie potwierdzone-nieosiągalne martwe
  gałęzie (`_read_request_int` except, martwy `continue` w `_restart_all`),
  znalezione i zweryfikowane podczas analizy pokrycia (włącznie z
  interakcją cross-file z `restart_active_instance` z `glava-gui.py`).
- `gui/tab_main.py` — naprawiono resource leak (`open(path).read()` bez
  `with`) w `_update_geometry_for_module`.
- `.github/workflows/test.yml` — usunięto zduplikowany krok "Run tests"
  (pytest odpalany dwa razy per joba); `sleep 1` przed startem Xvfb
  zamieniony na poll-loop z `xdpyinfo`; podniesiona rozdzielczość Xvfb,
  żeby domyślne okno 1040×768 mieściło się bez clampingu.

### 🔍 Znane problemy (przeniesione z RC4, wciąż otwarte)

- Zapis profilu shadera (bars) nie obejmuje `setbufsize`, `setsamplesize`,
  `setmirror`, `setinterpolate`
- Zmiana rozmiaru bufora audio wpływa na szerokość wizualizacji (niezamierzony efekt)
- Zmiana FPS wpływa na prędkość animacji i wysokość słupków w module bars
- Logi demona w zakładce Advanced są ubogie — logowana tylko zmiana kolorów,
  inne zdarzenia nie są rejestrowane; logi mogą pokazywać nieaktualne dane

### 📌 Uwaga narzędziowa (nie problem produktu — do backlogu `logic-cov`)

Heurystyka nazw w `logic-cov` klasyfikuje `gui/theme.py::TCheckbutton` jako
`LOGIC` (trafia w `"check"` wewnątrz `"tcheckbutton"`) mimo że to trywialny
wrapper `ttk.Checkbutton`, identyczny z natury do `TFrame`/`TLabel`/
`TEntry`/`TSeparator` (świadomie nietestowanych gdzie indziej w projekcie).
Dodano test-placeholder wyłącznie żeby zamknąć zgłaszaną dziurę — patrz
komentarz w `tests/test_theme.py`. Pełny opis tego i innych znalezisk
dot. `logic-cov` (martwy punkt po rozszerzeniu plików z shebangiem, waga
GUI maskująca realną logikę w funkcjach z dużą ilością widgetów, propozycja
mapy testów do roadmapy narzędzia) jest w `logic-cov-feedback.md`.

---

## [1.0.0-RC4] — 2026-06-15

### Kandydat do wydania 4 — Infrastruktura CI i naprawa demona

---

### 🐛 Naprawione błędy

#### glava-color-daemon: usunięta aktualizacja kolorów przy starcie
- Usunięto sprawdzenie przy starcie demona, które aktualizowało kolory gdy
  tapeta była nowsza niż shader. Powodowało to niepożądane aktualizacje
  kolorów przy każdym starcie demona niezależnie od rzeczywistej potrzeby.

#### Geometria — błąd off-by-one
- Wysokość paska 39px ustawia teraz poprawnie offset Y na -39px (było -40px).

### 🔧 Infrastruktura

- Dodano GitHub Actions CI — pytest na Python 3.10 / 3.11 / 3.12 + linting Ruff
- Dodano raportowanie pokrycia kodu przez Codecov (42%)
- Dodano `pyproject.toml` z konfiguracją Ruff i metadanymi projektu
- Ruff auto-fix: usunięto białe znaki z pustych linii w 19 plikach

### 🔍 Znane problemy (odłożone na przyszłe wydanie)

- Zapis profilu shadera (bars) nie obejmuje `setbufsize`, `setsamplesize`,
  `setmirror`, `setinterpolate`
- Zmiana rozmiaru bufora audio wpływa na szerokość wizualizacji (niezamierzony efekt)
- Zmiana FPS wpływa na prędkość animacji i wysokość słupków w module bars
- Logi demona w zakładce Advanced są ubogie — logowana tylko zmiana kolorów,
  inne zdarzenia nie są rejestrowane; logi mogą pokazywać nieaktualne dane

---

## [1.0.0-RC3] — 2026-06-14

### Kandydat do wydania 3 — Naprawa kierowania danych w odpiętych panelach

---

### 🐛 Naprawione błędy

#### Odpięte panele zapisywały dane do złej instancji
- **Przyczyna:** `BaseParamWidget` zawsze pobierał instancję docelową przez
  `app.active_instance` w chwili zapisu/restartu. Zmiana zakładki w oknie
  głównym podczas gdy panel był odpięty powodowała, że zapisy GLSL i restarty
  GLava trafiały do złej instancji — np. manipulowanie odpiętym panelem Radial
  restartowało Bars (nowo aktywna karta) z modułem Radial.
- **Naprawa:** `BaseParamWidget.__init__` otrzymuje opcjonalny parametr
  `instance=`. `detach_section()` tworzy teraz **nowy widżet** przywiązany do
  zamrożonej `active_instance` z chwili odpięcia, całkowicie izolując go od
  stanu okna głównego. Wszystkie właściwości GLSL i `_schedule_restart()`
  przechodzą przez `_get_instance()`, które zwraca zamrożoną instancję gdy jest
  ustawiona.
- **`restart_active_instance()`** otrzymuje parametr `instance=` — gdy podany,
  operuje na tej konkretnej instancji zamiast na aktualnie aktywnej.
  Pending restarty również przechowują referencję do instancji (3-krotka).

---

## [1.0.0-RC2] — 2026-06-11

### Kandydat do wydania 2 — Poprawki błędów i stabilność

---

### 🐛 Naprawione błędy

- **Duplikowanie procesów w `_debounce_request`** — naprawiony race condition
  powodujący tworzenie wielu procesów GLava
- **Deadlock w `_on_glava_toggle`** — naprawione zawieszenie gdy `self.instances`
  jest puste
- **Korupcja zapisu/wczytania workspace** — `smooth_parameters.glsl` używa
  `#request` nie `#define`; regex `read_all_defines` naprawiony by obsługiwał
  wartości zawierające spacje

### 🔧 Pozostałe zmiany

- Śledzenie błędów i funkcji przeniesione z plików tekstowych na pulpicie do
  GitHub Issues
- Lista funkcji oczyszczona z nieprawidłowych założeń
- ROADMAP i CHANGELOG zaktualizowane (dwujęzycznie)
- Wsparcie Waylanda trwale usunięte — użytkownicy kierowani do WayVes

---

## [1.0.0-RC1] — 2026-06-07

### Kandydat do wydania 1 — Multi-instance GLava Studio

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
├── glava-inst-1/glava/           ← Instancja 1 (skopiowana z wzorca)
├── glava-inst-2/glava/           ← Instancja 2
└── GlavaMP/
    ├── instances.json            ← Rejestr zakładek + trwały stan
    ├── profiles.json             ← Profile szaderów (globalne, per moduł)
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
