# Architektura — bing-glava-suite

Dokument referencyjny do analizy kodu i pisania testów.

> 🇬🇧 [English version](ARCHITECTURE.md)

> ⚠️ **Uwaga na nieaktualne komentarze w kodzie:**
> Kilka miejsc w kodzie zawiera stare założenia które zostały zmienione
> ale komentarze nie zostały zaktualizowane. Lista znanych przypadków
> na końcu tego dokumentu.

---

## 1. Instancje GLava

### Każda instancja jest równorzędna
- Nie ma instancji "chronionej" ani "domyślnej" — każdą można zamknąć i usunąć
- Każda instancja ma własny `inst_id` (int; id=0 przydzielane przy pierwszym starcie
  na świeżej instalacji, kolejne od 1)
- `next_inst_id()` zwraca najmniejszy wolny id ≥ 1

### Katalogi instancji
Każda instancja ma dwa katalogi:

```
~/.config/glava-inst-{inst_id}/glava/   ← XDG_CONFIG_HOME dla GLava (rc.glsl, shadery)
~/.config/GlavaMP/inst-{inst_id}/       ← dane GUI (profiles.json, presets.json)
```

### ~/.config/glava — katalog WZORCOWY
- `~/.config/glava/` jest **tylko szablonem** używanym przy tworzeniu nowych instancji
- **Nie jest** katalogiem żadnej instancji
- **Nie jest** powiązany z inst_id=0
- Instancje są tworzone przez `GlavaInstance.create()` która kopiuje z tego szablonu
- Fallback szablonu: `/etc/xdg/glava/`

### Tworzenie instancji
```
GlavaInstance(inst_id).create(source=None)
  → kopiuje z ~/.config/glava/ (lub /etc/xdg/glava/)
  → tworzy ~/.config/glava-inst-{id}/glava/
  → tworzy ~/.config/GlavaMP/inst-{id}/
```

---

## 2. Rejestr instancji

### instances.json
- Lokalizacja: `~/.config/GlavaMP/instances.json`
- Format: lista dict `[{inst_id, name, module, active}, ...]`
- Przechowuje kolejność zakładek i stan sesji
- **NIE jest** source of truth dla modułu — patrz sekcja 3

### Funkcje rejestru (gui/instance.py)
- `load_instances()` / `save_instances()`
- `register_instance(inst_id, name, module)`
- `unregister_instance(inst_id)` — działa dla każdego inst_id
- `update_instance(inst_id, **kwargs)` — aktualizuje name/module/active
- `next_inst_id()` — zwraca najmniejszy wolny id ≥ 1

---

## 3. Source of truth dla modułu

**`rc.glsl` jest source of truth**, nie `instances.json`.

Linia `#request mod <nazwa>` w `rc.glsl` każdej instancji określa aktywny moduł.
`instances.json` przechowuje moduł jako cache/hint przy ładowaniu — może być nieaktualny.

Przy starcie GUI: `_inst_modules` jest synchronizowany z `rc.glsl` każdej instancji,
a dopiero potem może być uzupełniony z `instances.json` jako fallback.

---

## 4. Zarządzanie procesami

### GUI przechowuje procesy
```python
self.instances  : dict[inst_id, GlavaInstance]
self.processes  : dict[inst_id, Popen | None]
```

### Restart instancji
Poprawna ścieżka: `restart_active_instance()` → `glava_restart_instance()`
- Ustawia `XDG_CONFIG_HOME = instance.xdg_dir`
- Zatrzymuje tylko ten jeden proces (SIGTERM → 2s → SIGKILL)
- Czeka na faktyczne zakończenie procesu przed powrotem
- Zwraca nowy Popen przez `after_fn`
- Przyjmuje opcjonalny parametr `instance=` — gdy podany, operuje na tej
  konkretnej instancji zamiast na aktywnej; używany przez odpięte panele,
  żeby zapisy i restarty zawsze trafiały do właściwej instancji niezależnie
  od tego, która karta jest aktualnie aktywna w oknie głównym

Stara ścieżka (kompatybilność wsteczna): `glava_restart()`
- Robi `pkill -x glava` — zabija **wszystkie** procesy
- Startuje tylko jedną instancję
- Używana tylko jako fallback gdy `app` nie ma `restart_active_instance`

### Toggle on/off
- **OFF**: `pkill -x glava` (celowo zabija wszystkie — w tym procesy poza kontrolą GUI)
- **ON**: startuje wszystkie zarejestrowane instancje równolegle
- Blokada `_toggle_in_progress` zapobiega race condition

### Zamknięcie GUI
- Zamknięcie okna GUI **nie zatrzymuje** procesów GLava
- Procesy działają dalej jako procesy tła
- Aby zatrzymać GLava: użyj toggle OFF przed zamknięciem GUI

---

## 5. Ścieżki plików konfiguracyjnych

### Globalne (współdzielone)
```
~/.config/GlavaMP/
├── instances.json      ← rejestr instancji
├── gui.conf            ← geometria okna GUI
├── gui_settings.json   ← ustawienia GUI (język, tryb expert)
├── profiles.json       ← profile shaderów (GLOBALNE — per moduł, nie per instancja)
├── presets.json        ← presety kolorów (3 kolory: top/mid/bottom)
└── themes/             ← pliki Forest-ttk-theme
```

### Per instancja
```
~/.config/glava-inst-{id}/glava/
├── rc.glsl                     ← konfiguracja główna + source of truth modułu
├── smooth_parameters.glsl      ← parametry wygładzania
├── bars.glsl / wave.glsl / …   ← parametry kształtu per moduł
├── bars/ wave/ circle/ …       ← katalogi z 1.frag (kolory — izolowane per instancja)
└── bars_colors.frag / …        ← szablony kolorów

~/.config/GlavaMP/inst-{id}/
├── profiles.json       ← UWAGA: plik istnieje w GlavaInstance.profiles_file
│                          ale faktycznie nie jest używany — profile są globalne
└── presets.json        ← j.w.
```

---

## 6. Etykiety zakładek

Etykiety generowane automatycznie przez `add_tab`:
- Pierwsza instancja modułu: `"Bars ✦"`, `"Wave ✦"`, `"Radial ✦"` itd.
- Kolejne: `"Bars ✦2"`, `"Bars ✦3"` itd.

Etykiety nadane ręcznie przez użytkownika (rename) są zachowywane między sesjami.

Przy starcie GUI `is_auto` sprawdza czy nazwa jest autogenerowana:
```python
is_auto = (name is None
           or name == "Default"
           or re.fullmatch(r'Instance \d+', name)
           or re.fullmatch(r'(?:Bars|Wave|Circle|Graph|Radial) ✦\d*', name))
```
Jeśli `is_auto=True` — `add_tab` generuje świeżą etykietę.
Jeśli `is_auto=False` — zachowana nazwa użytkownika.

---

## 7. System i18n

Wszystkie teksty UI przechodzą przez `T.get(klucz, fallback)`:
- `T` to instancja translatora wczytana z `lang/pl.json` lub `lang/en.json`
- Język przełączalny w czasie działania — GUI przebudowuje się przez pętlę `while True` w `glava-gui.py`
- `ask_string(parent, T, title, prompt)` — zamiennik TTK dla `simpledialog.askstring`
- `colorchooser.askcolor` — nadal używa systemowego dialogu Tk (zamiennik TTK planowany na RC2)

---

## 8. Zależności między modułami

```
glava-gui.py
├── gui/instance.py         ← GlavaInstance, rejestr
├── gui/instance_tab_bar.py ← pasek zakładek
├── gui/glava.py            ← zarządzanie procesami
├── gui/core.py             ← stałe, ścieżki, ustawienia
├── gui/tab_main.py         ← panel główny (kolory, tapeta, geometria)
├── gui/tab_advanced.py     ← panel zaawansowany (audio, FPS, rendering)
├── gui/tab_module.py       ← panel modułu (parametry shadera)
└── gui/modules/
    ├── base.py             ← boilerplate suwaków, debounce, helper ask_string
    ├── bars.py / wave.py / circle.py / graph.py / radial.py
    └── glsl_io.py          ← odczyt/zapis plików GLSL
```

---

## 9. Znane nieaktualne komentarze w kodzie

| Plik | Linia | Stary komentarz | Aktualny stan |
|------|-------|-----------------|---------------|
| `glava-gui.py` | 13 | `"Instancja 0 jest domyślna i nieusuwalna"` | Każda instancja jest usuwalna |
| `README.md` | struktura katalogów | `"glava/ ← Instance 0 (default, non-deletable)"` | `~/.config/glava/` to katalog wzorcowy, nie instancja |
| `CHANGELOG.md` | sekcja v1.0.0 | `"Instance 0 non-deletable by design"` | Nieaktualne |
