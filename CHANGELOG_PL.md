# Dziennik zmian — bing-glava-suite

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
