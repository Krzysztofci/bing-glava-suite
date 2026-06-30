# Uwagi do `logic-cov` — zebrane z domknięcia bing-glava-suite do 100%

Kontekst: te uwagi pochodzą z realnej, wielosesyjnej pracy nad podniesieniem
pokrycia całego projektu z ~61% do 100% TOTAL LOGIC. Wszystko poniżej zostało
faktycznie napotkane, nie jest teoretyzowaniem — każdy punkt da się zreplikować
na obecnym stanie narzędzia (`logic-cov` przesłany do analizy, 539 linii).

---

## 1. Błędy / false-positive / false-negative w klasyfikacji

### 1.1 False-positive: `LOGIC_NAME_HINTS` matchuje przez substring, nie przez słowo

**Przypadek:** `gui/theme.py::TCheckbutton` — funkcja identyczna co do treści
z `TFrame`/`TLabel`/`TEntry`/`TSeparator` (cienki wrapper `ttk.X(**_ttk_kw(kw))`,
zero logiki biznesowej), ale jedyna z tej rodziny sklasyfikowana jako `LOGIC`
(`gui=1, logic=2`) zamiast `GUI`.

**Przyczyna (zlokalizowana w kodzie):**
```python
func_name_lower = func_name.lower()  # "tcheckbutton"
if any(hint in func_name_lower for hint in GUI_NAME_HINTS):
    self.gui += 2
if any(hint in func_name_lower for hint in LOGIC_NAME_HINTS):
    self.logic += 2
```
`LOGIC_NAME_HINTS` zawiera `"check"` (myślane jako `check_something`/
`validate`-style). `"tcheckbutton"` zawiera podciąg `"check"` (`T-CHECK-button`)
czysto przypadkowo — `in` na stringu nie rozróżnia granic słowa.

**Sugerowana poprawka:** dopasowanie po granicy słowa/segmentach
`snake_case`/`camelCase`, nie surowy substring `in`. Np. rozbicie nazwy na
tokeny (`re.findall(r'[a-z]+', func_name_lower)` lub split po wielkich
literach) i sprawdzanie `hint in tokens`, a nie `hint in func_name_lower`.
To samo ryzyko dotyczy prawdopodobnie innych krótkich hintów (`"get"`,
`"set"` — te akurat są częste i krótkie, więc szczególnie podatne na
przypadkowe matche w środku dłuższych nazw, np. `"widget"` zawiera `"get"`).

**Wpływ w praktyce:** w tym projekcie skończyło się na ręcznym, trywialnym
teście istniejącym wyłącznie żeby zamknąć liczbę w raporcie — nie testuje
niczego realnego. To kosztuje czas i fałszuje sygnał "ile % to realna praca
do zrobienia".

---

### 1.2 False-negative: ciężka konstrukcja widgetów potrafi "zatopić" realną logikę w tej samej funkcji

**Przypadek:** `glava-gui.py::GlavaGUI._save_workspace` — funkcja o 80 liniach,
~30 z nich to realna logika biznesowa (odczyt kolorów/geometrii/GLSL z dysku,
budowa struktury JSON, zapis z obsługą `OSError`), ~50 to budowa modalnego
dialogu TTK (Label/Entry/Button × kilka). Wynik klasyfikacji: `GUI` z
`gui=18, logic=12` — mimo 12 punktów logiki, przewaga GUI (18) decyduje
binarnie i CAŁA funkcja (wraz z tymi 12 punktami) wypada z raportu "Missing
Logic". Siostrzana funkcja `_load_workspace` (tej samej wielkości, ten sam
wzorzec dialogu + porównywalna ilość realnej logiki) wypadła akurat na `MIXED`
(`gui=17, logic=13`) różnicą jednego punktu w każdą stronę — i DZIĘKI temu
trafiła do raportu, była widoczna, i ostatecznie przetestowana. `_save_workspace`
nie trafiłaby do raportu nigdy, gdybyśmy nie sprawdzili tego ręcznie przez `-vv`.

**Sugerowana poprawka:** dodać trzeci próg niezależny od porównania
gui-vs-logic — np. "jeśli `logic >= N` (próg absolutny, np. 8-10), licz
funkcję jako MIXED niezależnie od tego jak wysokie jest `gui`". Funkcje z
realną logiką budżetowo "warte" 12-13 punktów to nie przypadkowy odprysk —
to konkretna, ryzykowna logika (utrata danych usera przy buggu w tym
przypadku), niezależnie od tego, że akurat siedzi w funkcji z dużym dialogiem.

**Wpływ w praktyce:** w tym konkretnym projekcie i tak ją przetestowaliśmy
(bo wiedzieliśmy, że jest tam ryzyko, i sprawdziliśmy `-vv` żeby zrozumieć
czemu nie ma jej w `-comp`) — ale to wymagało świadomej, ręcznej decyzji
"nie wierzę że tu nic nie ma, sprawdzę". Kto ufa tylko `-comp` bez `-vv`,
nigdy się o tej funkcji nie dowie.

---

### 1.3 Blind spot: filtr `path.suffix == ".py"` ignoruje pliki Pythonowe bez rozszerzenia

**Przypadek:** `scripts/glava-colors-auto-mi` — 213 linii, prawdziwy shebang
`#!/usr/bin/env python3`, realna logika (PID management, SIGTERM→SIGKILL
escalation, orkiestracja per-instancja) tej samej wagi co `gui/glava.py`.
Plik leży WEWNĄTRZ skanowanego drzewa (`scripts/`), ale `path.rglob("*.py")`
+ `path.suffix == ".py"` go całkowicie ignoruje — nigdy nie pojawi się
w żadnym raporcie, niezależnie od pokrycia.

**Sugerowana poprawka:** rozszerzyć detekcję o pliki z shebangiem
Pythonowym (`#!/usr/bin/env python3`, `#!/usr/bin/python3` itp.) niezależnie
od rozszerzenia — sprawdzenie pierwszej linii pliku jest trywialne i szybkie.
Alternatywnie/dodatkowo: tryb `-v`/`-vv` mógłby wypisywać listę plików
NAPOTKANYCH w drzewie ale POMINIĘTYCH przez filtr rozszerzenia (analogicznie
do ostrzeżeń `coverage.py` typu "module was never imported") — żeby brak
pokrycia był przynajmniej WIDOCZNY jako "nieprzeanalizowane", nie cichy.

**Dodatkowa, niezależna od logic-cov pułapka przy tym samym pliku:** zwykły
`coverage.py` użyty osobno na tym pliku też go nie widział — ale z innego
powodu: `pyproject.toml` ma `[tool.coverage.run] source = ["scripts/gui"]`,
co wycina WSZYSTKO poza `scripts/gui/` (czyli i ten plik, i `tools/`, i
gdyby się znalazł nowy plik w `scripts/` poza `gui/`). To nie jest bug w
`logic-cov`, ale skoro oba narzędzia niezależnie "gubią" ten sam plik z
dwóch różnych przyczyn — łatwo nabrać błędnej pewności "to jest pokryte"
kiedy w rzeczywistości nikt tego nigdy nie zmierzył.

---

## 2. Drobniejsze obserwacje (nie błędy, ale tarcie przy realnym użyciu)

- **Inny licznik statementów niż `coverage.py`.** `logic-cov` liczy swoje
  AST-based "Logic Stmts" (np. `gui/glava.py` → 359), `coverage.py` liczy
  bytecode-line-based "Stmts" dla tego samego pliku (246). Oba są wewnętrznie
  konsystentne, ale nie da się ich bezpośrednio mapować 1:1 przy
  cross-referencingu ręcznym/przez LLM — trzeba pamiętać że to dwie różne
  miary, nie tylko różne %. Warto to gdzieś explicit zanotować w `--help`/README,
  żeby ktoś (czy LLM dostający surowy output) nie próbował np. odjąć jednej
  liczby od drugiej.

- **`-vv` (dump klasyfikacji per-funkcja) jest najcenniejszym narzędziem
  do zrozumienia DLACZEGO coś (nie) jest w raporcie `-comp`** — ale to
  osobne wywołanie. W praktyce za każdym razem kiedy wynik z `-comp` był
  zaskakujący (więcej padding niż się wydawało, funkcja nieobecna mimo
  realnej logiki w środku) — sięgaliśmy po `-vv` żeby zweryfikować. Warto
  rozważyć flagę łączącą oba widoki naraz (np. `-comp -vv` razem, albo
  `-comp --explain` dorzucające klasyfikację per-funkcja TYLKO dla funkcji
  które aktualnie mają missing logic — to ograniczyłoby output do tego co
  faktycznie potrzebne).

- **Padding zakresu (`if`/`for`/`try` rodzica) jest świadomy i pomocny dla
  LLM-a wklejającego prompt** — to działa dobrze i NIE proszę o zmianę
  default. Warto tylko mieć na uwadze (i może wspomnieć w dokumentacji), że
  surowe `coverage.py --cov-report=term-missing` daje WĘŻSZY, bardziej
  precyzyjny zakres tej samej dziury — i że to oczekiwana, zamierzona różnica,
  nie niespójność między narzędziami.

---

## 3. Mapa testów — konkretna propozycja na podstawie realnego tarcia

Poniżej nie teoria, a lista konkretnych sytuacji z tej sesji, które mapa
testów rozwiązałaby od razu, bez ręcznego grepowania/zgadywania:

### 3.1 Powtarzający się, najkosztowniejszy problem: import lokalny przesłania top-level

W KAŻDYM bez wyjątku pliku w tym projekcie, gdzie metoda robi lokalny
`from X import Y` wewnątrz swojego ciała, podczas gdy moduł TEŻ ma
`from X import Y` na górze pliku — patchowanie top-level importu (intuicyjne,
pierwsze podejście) **nie ma żadnego efektu** na to co faktycznie się wykona,
bo lokalny import w środku funkcji zawsze pobiera świeżą referencję z X w
momencie wywołania. Historia tego projektu ma już co najmniej jeden
udokumentowany incydent realnego, niezamierzonego odpalenia procesu `glava`
w testach właśnie przez tę pułapkę (`test_bars.py`, patrz komentarze w
`test_glava_gui_toggle.py`). W tej sesji trafiłem na to ponownie przy
`_save_workspace`/`_load_workspace` (świeży `GlavaInstance(iid)` per pętla,
nie `self.instances[iid]`).

**Co mapa powinna rejestrować per funkcja/metoda źródłowa:**
- lista nazw importowanych lokalnie (wewnątrz ciała), z dokładną linią
- dla każdej: czy ten SAM symbol jest też importowany na poziomie modułu
  (top-level) — czyli czy istnieje ryzyko "patchowania złego miejsca"
- moduł-źródło każdego importu (`gui.glava`, `gui.instance`, ...)

Z tym, narzędzie (albo nawet sam `logic-cov` jako dodatkowy raport) mogłoby
PROAKTYWNIE ostrzegać: "funkcja X ma top-level import Y z modułu Z, ale
WEWNĄTRZ robi też lokalny `from Z import Y` — jeśli piszesz test patchujący
`Y` na poziomie modułu (top-level reference), prawdopodobnie nie zadziała,
patchuj `Z.Y` na źródle". To by zaoszczędziło realny czas debugowania (w tej
sesji: kilka razy, w tym jeden zakończony realnym, zaszkodzącym efektem na
żywym systemie Krzysztofa).

### 3.2 "Czy test dla X już istnieje" — odwrotny indeks

Wielokrotnie w tej sesji pierwszym krokiem przy nowym pliku było pytanie
"jaki plik testowy to pokrywa i czy już coś tam jest". W praktyce zawsze
kończyło się to albo zgadywaniem nazwy (`test_glava_lifecycle.py` testuje
`gui/glava.py`, NIE `glava-gui.py` — myląca nazwa, osobno odnotowana jako
pułapka w notatkach projektu), albo grepowaniem po katalogu `tests/`.

**Co mapa powinna rejestrować:** dla każdej funkcji/metody źródłowej —
lista (plik_testowy, nazwa_testu) które ją faktycznie wykonują (to jest do
wyciągnięcia z `coverage.py --dynamic-context=test-function` + bazy danych
SQLite, którą `coverage.py` już potrafi generować — `logic-cov` mógłby to
po prostu skonsumować jako dodatkowe wejście, nie musi reimplementować
śledzenia wykonania od zera).

### 3.3 Refaktoryzacja: "co się złamie jeśli zmienię nazwę/sygnaturę"

Przy zmianie nazwy funkcji/metody źródłowej, zwykłe `grep -rn "stara_nazwa"
tests/` znajdzie WYWOŁANIA, ale nie odróżni automatycznie:
- wywołania testujące REALNĄ funkcję (`widget._debounce_int(...)`)
- mocków PODSTAWIAJĄCYCH tę funkcję (`monkeypatch.setattr(mod,
  "_debounce_int", fake)`) — te wymagają zmiany STRINGA z nazwą, grep je
  złapie, ale nie ma jak automatycznie zweryfikować że zmiana jest kompletna
  bez odpalenia testów

**Co mapa powinna rejestrować:** rozróżnienie tych dwóch kategorii per
wystąpienie (wywołanie-jako-SUT vs `monkeypatch.setattr`-jako-cel), żeby
przy refaktoryzacji dało się odpytać "pokaż mi WSZYSTKIE miejsca w testach
odwołujące się do `gui.glava.glava_restart`, z rozróżnieniem czy to call
czy mock-target" jedną komendą, zamiast ręcznego review każdego grep-hita.

### 3.4 Sugerowany format (szkic)

Coś w stylu jednego JSON/SQLite per projekt, generowanego jako dodatkowy
tryb `logic-cov --build-test-map`, z grubsza:

```json
{
  "scripts/gui/glava.py": {
    "glava_restart": {
      "covered_by": ["tests/test_glava.py::test_x", "..."],
      "local_imports_of_this_name_elsewhere": [
        {"in_function": "GlavaGUI._on_glava_toggle",
         "in_file": "scripts/glava-gui.py", "line": 1056,
         "shadows_top_level_import_at_line": 48}
      ]
    }
  }
}
```

Nawet bez pełnej automatyzacji tego ostatniego punktu — sama część 3.1
(detekcja "ten import jest jednocześnie top-level i lokalny gdzie indziej
w tym samym pliku") to relatywnie prosty AST-walk (już masz cały potrzebny
AST-tooling w `logic-cov`) i daje od razu wymierną wartość ostrzegawczą.

---

## Podsumowanie priorytetów (subiektywnie, z perspektywy kogoś kto właśnie
przeszedł cały projekt)

1. **3.1 (mapa lokalnych-vs-top-level importów + ostrzeżenie)** — największa
   realna wartość, bo to jedyny punkt z tej listy, który już raz kosztował
   realny incydent (odpalenie procesu produkcyjnego z testu), nie tylko czas.
2. **1.3 (blind spot rozszerzenia)** — krótkie do naprawienia (sprawdzenie
   shebangu), zero ryzyka regresji, czysty zysk widoczności.
3. **1.1/1.2 (heurystyka nazw / próg absolutny)** — wartościowe, ale niskiego
   ryzyka (kosmetyka raportu, nie utrata danych), można odłożyć.
4. **3.2/3.3 (pełna mapa testów)** — najcenniejsze długoterminowo, ale
   największy nakład pracy; sensowne jako osobny epik, niekoniecznie
   wszystko na raz.
