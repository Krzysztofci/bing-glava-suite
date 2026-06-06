# Historia zmian — bing-glava-suite

---

## [1.0.0-RC1] — 2026-06-xx

### Kandydat do wydania 1 — Wieloinstancyjne Studio GLava

Pierwszy kandydat do wydania wieloinstancyjnej wersji programu. Podstawowa
funkcjonalność jest stabilna; znane problemy udokumentowane poniżej.

---

### ✨ Co nowego w RC1 (od v0.5.0)

#### Architektura wieloinstancyjna
- Wiele wizualizatorów GLava jednocześnie — Bars, Wave, Circle, Graph, Radial
  — każdy w osobnej zakładce z izolowaną konfiguracją i procesem
- Osobny `XDG_CONFIG_HOME` per instancja: `~/.config/glava-inst-{id}/glava/`
- Wszystkie instancje równorzędne — każdą można zamknąć i usunąć, w tym inst-0
- Trwały stan przez `instances.json` — zakładki przeżywają restart aplikacji
- Source of truth modułu: linia `#request mod` w `rc.glsl`, nie `instances.json`

#### InstanceTabBar
- Własny pasek zakładek oparty na `ttk.Notebook` (height=0) z Forest-ttk-theme
- Etykiety zakładek: `Bars ✦`, `Bars ✦2` itd. — automatyczna numeracja per moduł
- Przycisk `[✚]` do dodawania instancji i wczytywania workspace
- Menu kontekstowe (prawy klik): Zmień nazwę / Zmień shader / Zapisz workspace /
  Duplikuj / Zamknij
- Przyciski zapisu (🖫) i wczytywania (🗁) workspace w pasku zakładek

#### i18n — pełna obsługa polskiego i angielskiego
- Wszystkie teksty UI, dialogi i menu przez `T.get()` — brak hardkodowanych napisów
- Helper `ask_string()` w TTK zastępujący `simpledialog.askstring`
- `tk.Listbox` w dialogu wczytywania workspace ostylowany pod Forest-dark
- Nowe klucze w `pl.json` i `en.json`: dialogi workspace, menu kontekstowe,
  dialogi profili kolorów i szaderów, przeglądarka logów, komunikaty błędów

#### Ulepszenia instalatora
- `~/.local/bin` dodany do `PATH` w `.bashrc` po instalacji skryptów użytkownika
  (marker `LOCAL_BIN_PATH` zapobiega duplikatom przy reinstalacji)
- `systemctl --user start` uruchamiany po `enable` ze sprawdzeniem `is-active`
- Czystsze podsumowanie instalacji — usunięto zbędne instrukcje ręcznego startu

#### Zarządzanie procesami
- `glava_stop_instance()` czeka na faktyczne zakończenie procesu przed powrotem
- Blokada `_toggle_in_progress` zapobiega race condition przy szybkim toggle
- `glava-color-daemon` sam ustawia `DISPLAY`/`DBUS_SESSION_BUS_ADDRESS`/`XAUTHORITY`
  gdy brakuje tych zmiennych (brak hardkodowanego `:0`)

---

### 🐛 Znane problemy / Ograniczenia

- **Liczba procesów po rozruchu** — w niektórych konfiguracjach autostart +
  daemon mogą podwoić liczbę procesów. Obejście: toggle OFF/ON w GUI po zalogowaniu.
- **Color picker** — używa systemowego dialogu Tk `colorchooser`; nie pasuje
  wizualnie do Forest-ttk-theme. Własny picker TTK planowany na RC2.
- **Profile szaderów** — aktualnie globalne per moduł, nie per instancja.
  Profile per instancja planowane na przyszłe wydanie.
- **Automatyczne wczytywanie workspace** — workspace nie wczytuje się automatycznie
  przy starcie GUI; należy wczytać ręcznie przez przycisk 🗁.

---

### 📂 Struktura katalogów

```
~/.config/
├── glava/                        ← Katalog wzorcowy (nie instancja)
├── glava-inst-1/glava/           ← Instancja 1
├── glava-inst-2/glava/           ← Instancja 2
└── GlavaMP/
    ├── instances.json            ← Rejestr + trwały stan zakładek
    ├── profiles.json             ← Profile szaderów (globalne, per moduł)
    ├── presets.json              ← Presety kolorów
    ├── gui.conf                  ← Geometria okna
    └── themes/                   ← Pliki Forest-ttk-theme
```

---

## [0.5.0] — 2026-04-xx

Modułowy przepisany GUI — pięć modułów shaderów z dedykowanymi panelami,
ujednolicone obliczanie geometrii, logika debounced restart, framework i18n,
integracja Forest-ttk-theme, gotowy pakiet `.deb` GLava dla Ubuntu 24.04 / Mint 22.x.

## [0.2.2] — 2026-04-xx

Poprawki gradient wave/graph, system gradientu HSV/RGB, funkcja blokady tapety.

## [0.2.0] — 2026-03-xx

Krytyczne poprawki shaderów (gradient bars, circle), przeprojektowany system gradientu.

## [0.1.0] — 2026-03-xx

Pierwsze wydanie: pobieranie tapet Bing + kontroler GLava, daemon systemd,
ekstrakcja kolorów KMeans, podstawowy GUI Tkinter.
