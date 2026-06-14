# Testing Guide — bing-glava-suite v1.0.0-RC3 (MULTI-INSTANCE)

---

## Część 0: Testy automatyczne (pytest)

### Wymagania

```bash
sudo apt install python3-pytest python3-pillow python3-tk
```

### Konfiguracja — `pytest.ini`

Upewnij się że `pytest.ini` w katalogu projektu zawiera:

```ini
[pytest]
testpaths = tests
pythonpath = scripts
addopts = -v
```

Opcja `addopts = -v` sprawia że każdy z 405 testów wyświetla się osobno
z wynikiem PASSED / FAILED. Bez niej pytest pokazuje tylko podsumowanie.

### Uruchomienie

```bash
cd ~/bing-glava-suite
pytest
```

Wszystkie 405 testów powinno zakończyć się statusem `passed`. Przykładowy
wynik poprawnej sesji:

```
tests/test_base_widget.py::test_build_creates_widgets PASSED
tests/test_base_widget.py::test_build_populates_vars PASSED
...
405 passed in ~18s
```

Aby uruchomić tylko jeden plik testowy:

```bash
pytest tests/test_base_widget.py
```

Aby uruchomić tylko jeden konkretny test:

```bash
pytest tests/test_base_widget.py::test_frozen_instance_debounce_writes_to_correct_file
```

---

## Część 1: Testy instalacji (Live CD / czyste konto)

### Wymagania
- Linux Mint XFCE ISO na USB (lub konto testowe `su - testuser`)
- Min. 8 GB RAM przy Live CD (dodaj `toram` do linii GRUB)
- Połączenie internetowe

### Przygotowanie Live CD
```bash
sudo sed -i '/cdrom/d' /etc/apt/sources.list
sudo apt install git
git clone -b feature/modular-gui https://github.com/Krzysztofci/bing-glava-suite.git
cd bing-glava-suite
sudo ./install.sh
```

### Scenariusz 1.1 — Instalacja czysta
| Krok | Akcja | Oczekiwany wynik |
|---|---|---|
| 1 | Uruchom `sudo ./install.sh` | Instalator startuje, pokazuje pasek postępu |
| 2 | Przejdź przez wszystkie kroki instalatora | Każdy krok kończy się bez błędów |
| 3 | Sprawdź czy GLava działa: `glava --desktop` | GLava uruchamia się na pulpicie |
| 4 | Uruchom GUI: `glava-gui` | Okno GUI otwiera się |
| 5 | Wykonaj polecenie z końca instalatora lub przeloguj się | Aby daemon wystartował bez restartu systemu uruchom polecenie podane przez instalator; po samym wylogowaniu daemon może być inactive |
| 5a | Po restarcie systemu: `systemctl --user status glava-color-daemon` | Status: active (running) |
| 6 | Sprawdź liczbę procesów: `pgrep -x glava | wc -l` | Liczba == liczba instancji w GUI |

### Scenariusz 1.2 — Reinstalacja (nadpisanie istniejącej)
| Krok | Akcja | Oczekiwany wynik |
|---|---|---|
| 1 | Uruchom `sudo ./install.sh` ponownie | Instalator nie crashuje na istniejących plikach |
| 2 | Sprawdź czy konfiguracja użytkownika zachowana | `~/.config/GlavaMP/` i `~/.config/glava/` niezmienione |
| 3 | Sprawdź procesy po reinstalacji | Brak zdublowanych procesów GLava |

---

## Część 2: Zarządzanie procesami GLava

> **Narzędzie diagnostyczne** — otwórz terminal i monitoruj procesy w czasie rzeczywistym:
> ```bash
> watch -n 1 'pgrep -x glava | wc -l; pgrep -x glava'
> ```

### Scenariusz 2.1 — Toggle on/off (podstawowy)
| Krok | Akcja | Oczekiwany wynik |
|---|---|---|
| 1 | Uruchom GUI z 1 instancją | `pgrep -x glava | wc -l` == 1 |
| 2 | Kliknij toggle GLava → OFF | Liczba procesów == 0 |
| 3 | Kliknij toggle GLava → ON | Liczba procesów == 1 |
| 4 | Sprawdź czy instancja działa poprawnie | GLava widoczny na pulpicie |

### Scenariusz 2.2 — Szybkie toggle (race condition)
| Krok | Akcja | Oczekiwany wynik |
|---|---|---|
| 1 | Uruchom GUI z 2 instancjami | Liczba procesów == 2 |
| 2 | Klikaj toggle ON/OFF szybko 10 razy z rzędu | Liczba procesów zawsze ≤ 2 |
| 3 | Odczekaj 3 sekundy po ostatnim kliknięciu | Liczba procesów == 0 lub 2 (zależnie od ostatniego stanu) |
| 4 | Nie powinno być > 2 procesów w żadnym momencie | Brak procesów zombie/osieroconych |

### Scenariusz 2.3 — Restart po zmianie shadera
| Krok | Akcja | Oczekiwany wynik |
|---|---|---|
| 1 | Uruchom GUI z 1 instancją (bars) | Liczba procesów == 1, PID = X |
| 2 | Zmień shader na circle (zakładka instancji → zmień shader) | GLava restartuje się |
| 3 | Sprawdź PID po restarcie | PID != X (nowy proces) |
| 4 | Sprawdź liczbę procesów | Liczba == 1 (nie 2) |
| 5 | Zmień shader 5 razy szybko | Po ustaniu klikania — tylko 1 restart, liczba == 1 |

### Scenariusz 2.4 — Zamknięcie GUI
| Krok | Akcja | Oczekiwany wynik |
|---|---|---|
| 1 | Uruchom GUI z 3 instancjami | Liczba procesów == 3 |
| 2 | Zamknij GUI (X lub Alt+F4) | GUI zamknięte, procesy GLava **działają dalej** (toggle OFF przed zamknięciem aby zatrzymać) |
| 3 | `pgrep -x glava | wc -l` | Liczba == 3 (procesy nadal żyją) |

### Scenariusz 2.5 — Restart systemu
| Krok | Akcja | Oczekiwany wynik |
|---|---|---|
| 1 | Uruchom GUI z N instancjami | N procesów aktywnych |
| 2 | Zamknij GUI, zrestartuj system | — |
| 3 | Po restarcie uruchom GUI | GUI przywraca ostatnio używane instancje (workspace wczytuje się ręcznie przez przycisk wczytaj) |
| 4 | Sprawdź liczbę procesów | Liczba == N (nie 2N) |

---

## Część 3: Zarządzanie instancjami

### Scenariusz 3.1 — Dodawanie instancji
| Krok | Akcja | Oczekiwany wynik |
|---|---|---|
| 1 | Uruchom GUI | Jeśli brak zapisanych instancji — GUI uruchamia się bez kart i bez procesów |
| 2 | Dodaj instancję: przycisk `+` → wybierz shader | Nowa zakładka pojawia się, liczba procesów == 1 |
| 3 | Dodaj kolejną instancję: przycisk `+` → wybierz **inny** shader | Liczba == 2; każda instancja wymaga ręcznego wyboru shadera |
| 4 | Dodaj jeszcze 2 instancje z różnymi shaderami | Liczba == 4 |
| 5 | Każda instancja ma inny shader | Wizualizacje różnią się |

### Scenariusz 3.2 — Duplikowanie instancji
| Krok | Akcja | Oczekiwany wynik |
|---|---|---|
| 1 | Skonfiguruj instancję 1 (unikalne kolory, parametry) | — |
| 2 | Kliknij prawym → Duplikuj | Nowa instancja z tymi samymi ustawieniami |
| 3 | Sprawdź czy kolory i parametry są skopiowane | Identyczne z oryginałem |
| 4 | Sprawdź procesy | Liczba zwiększona o 1 |
| 5 | Zmodyfikuj zduplikowaną instancję | Oryginał nie zmienia się |

### Scenariusz 3.3 — Usuwanie instancji
| Krok | Akcja | Oczekiwany wynik |
|---|---|---|
| 1 | Uruchom GUI z 3 instancjami | Liczba procesów == 3 |
| 2 | Zamknij jedną zakładkę instancji | Liczba == 2 |
| 3 | Sprawdź `~/.config/GlavaMP/instances.json` | Wpis zamkniętej instancji usunięty |
| 4 | Sprawdź `ls ~/.config/glava-inst-*/` | Katalog zamkniętej instancji usunięty |
| 5 | Zamknij kolejną instancję | Liczba == 1 |
| 6 | Zamknij ostatnią pozostałą instancję | Liczba == 0 |

### Scenariusz 3.4 — Zmiana nazwy instancji
| Krok | Akcja | Oczekiwany wynik |
|---|---|---|
| 1 | Kliknij prawym na zakładkę → Zmień nazwę | Dialog z polem tekstowym |
| 2 | Wpisz nową nazwę | Zakładka pokazuje nową nazwę |
| 3 | Zrestartuj GUI | Nazwa zachowana po restarcie |

---

## Część 4: Zakładka Main — kolory i tapeta

### Scenariusz 4.1 — Ręczna zmiana kolorów
| Krok | Akcja | Oczekiwany wynik |
|---|---|---|
| 1 | Otwórz zakładkę Main aktywnej instancji | Widoczne 3 przyciski kolorów (top/mid/bottom) |
| 2 | Kliknij kolor "top" → wybierz czerwony | Przycisk zmienia kolor |
| 3 | Kliknij przycisk "Zastosuj kolory" | GLava restartuje się, wizualizacja zmienia kolory (brak auto-restartu po zmianie koloru) |
| 4 | Sprawdź czy kolory zostały zapisane do `1.frag` | `cat ~/.config/glava-inst-{id}/glava/{shader}/1.frag | grep "vec3 top"` (podmień `{shader}` na aktywny moduł instancji) |

### Scenariusz 4.2 — Gradient RGB vs HSV
| Krok | Akcja | Oczekiwany wynik |
|---|---|---|
| 1 | Ustaw tryb gradient: RGB | GLava używa interpolacji RGB |
| 2 | Przełącz na HSV | GLava używa interpolacji HSV (inne przejścia kolorów) |
| 3 | Przełącz z powrotem na RGB | Wraca do interpolacji RGB |
| 4 | Sprawdź czy tryb zachowany po restarcie GUI | Ustawienie persystuje |

### Scenariusz 4.3 — Presety kolorów
| Krok | Akcja | Oczekiwany wynik |
|---|---|---|
| 1 | Ustaw unikalne kolory | — |
| 2 | Zapisz preset: pole nazwy → "Mój preset" → Zapisz | Preset pojawia się na liście |
| 3 | Zmień kolory na inne | — |
| 4 | Wczytaj "Mój preset" | Kolory wracają do zapisanych |
| 5 | Usuń preset | Znika z listy |
| 6 | Sprawdź `~/.config/GlavaMP/presets.json` | Plik odzwierciedla stan listy |

### Scenariusz 4.4 — Kolory z tapety Bing
| Krok | Akcja | Oczekiwany wynik |
|---|---|---|
| 1 | Upewnij się że `~/Pictures/Bing/bing_today.jpg` istnieje | — |
| 2 | Kliknij "Zastosuj kolory z tapety" z opcją **All** | KMeans ekstrakcja, GLava restartuje się |
| 3 | Kolory instancji zmienione zgodnie z tapetą | Widoczna w podglądzie miniatura |
| 4 | Sprawdź wszystkie instancje | Każda instancja otrzymuje ten sam zestaw kolorów (opcja All) |

### Scenariusz 4.5 — Blokada tapety
| Krok | Akcja | Oczekiwany wynik |
|---|---|---|
| 1 | Włącz blokadę tapety (przełącznik w GUI) | `~/.config/GlavaMP/wallpaper.lock` istnieje |
| 2 | Uruchom `sudo /usr/local/bin/bing-downloader.sh $USER` | Tapeta NIE zmienia się |
| 3 | Miniatury regionów Bing aktualizują się | Mimo blokady tapety |
| 4 | Wyłącz blokadę | Plik `wallpaper.lock` usunięty |
| 5 | Uruchom downloader ponownie | Tapeta zmienia się normalnie |

---

## Część 5: Zakładka Main — geometria

### Scenariusz 5.1 — Auto-detekcja geometrii
| Krok | Akcja | Oczekiwany wynik |
|---|---|---|
| 1 | Kliknij "Wykryj geometrię" | GUI odczytuje rozmiar ekranu i pasek zadań |
| 2 | Sprawdź wartości X, Y, W, H | W == szerokość ekranu, H == wysokość ekranu |
| 3 | Y < 0 przy pasku na dole | Y == -(wysokość paska) |
| 4 | Zastosuj geometrię | GLava restartuje się z nową geometrią |
| 5 | GLava wyrównany do krawędzi ekranu | Brak przerw między GLava a paskiem |

### Scenariusz 5.2 — Pionowy pasek (Mirror YX)
| Krok | Akcja | Oczekiwany wynik |
|---|---|---|
| 1 | Włącz "Pionowy pasek" (Mirror YX) dla bars | GLava obraca się o 90° |
| 2 | Wykryj geometrię | X uwzględnia lewy panel (jeśli istnieje) |
| 3 | Włącz "Odbicie" + "Pionowy pasek" | GLava po prawej stronie ekranu |

### Scenariusz 5.3 — Ręczna edycja geometrii
| Krok | Akcja | Oczekiwany wynik |
|---|---|---|
| 1 | Wpisz ręcznie X=0, Y=-40, W=1600, H=900 | — |
| 2 | Kliknij "Zastosuj" | GLava przesuwa się do podanych współrzędnych |
| 3 | Zrestartuj GUI | Geometria zachowana |

---

## Część 6: Zakładka Module — parametry shadera

### Scenariusz 6.1 — Suwaki parametrów kształtu
| Krok | Akcja | Oczekiwany wynik |
|---|---|---|
| 1 | Otwórz zakładkę Module dla instancji bars | Widoczne suwaki: szerokość, odstęp, wzmocnienie itp. |
| 2 | Przesuń suwak "Szerokość słupka" do maksimum | GLava restartuje się po 300ms, słupki szersze |
| 3 | Przesuń do minimum | Słupki węższe |
| 4 | Wpisz wartość ręcznie w pole obok suwaka | Suwak przesuwa się do wpisanej wartości |
| 5 | Wpisz wartość spoza zakresu | Wartość jest przycinana do min/max |

### Scenariusz 6.2 — Flagi (przełączniki)
| Krok | Akcja | Oczekiwany wynik |
|---|---|---|
| 1 | Włącz "Odbicie pionowe" | Wizualizacja odwraca się |
| 2 | Włącz "Odwróć spektrum" | Bas po prawej zamiast lewej |
| 3 | Włącz oba jednocześnie | Oba efekty aktywne |
| 4 | Zrestartuj GUI | Flagi zachowane |

### Scenariusz 6.3 — Profile szaderów
| Krok | Akcja | Oczekiwany wynik |
|---|---|---|
| 1 | Ustaw unikalne parametry kształtu | — |
| 2 | Wpisz nazwę "Bass heavy" → Zapisz profil | Profil pojawia się na liście |
| 3 | Zmień parametry na inne | — |
| 4 | Wybierz "Bass heavy" z listy → Zastosuj | Parametry wracają do zapisanych |
| 5 | Usuń profil | Znika z listy |
| 6 | Sprawdź `~/.config/GlavaMP/profiles.json` | Plik odzwierciedla stan |

### Scenariusz 6.4 — Wygładzanie audio (zakładka Audio)
| Krok | Akcja | Oczekiwany wynik |
|---|---|---|
| 1 | Zmień "Grawitacja" na maksimum | Słupki opadają szybciej |
| 2 | Zmień "Wygładzanie" na minimum | Wizualizacja bardziej responsywna |
| 3 | Zmień "Klatek avg" | Płynniejsza ale wolniejsza wizualizacja |
| 4 | Parametry wygładzania działają per instancja (nie globalnie) | Zmiana na inst-1 nie wpływa na inst-2 |

### Scenariusz 6.5 — Tryb Expert
| Krok | Akcja | Oczekiwany wynik |
|---|---|---|
| 1 | Włącz tryb Expert (przełącznik w zakładce Advanced, sekcja Audio) | Dodatkowe opcje konfiguracyjne bufora audio, rozmiaru i częstotliwości próbkowania |
| 2 | Wyłącz tryb Expert | Dodatkowe elementy znikają |
| 3 | Parametry Expert działają per instancja; po zamknięciu instancji są resetowane do wartości z katalogu wzorcowego | Znane ograniczenie — do poprawy w przyszłości |

---

## Część 7: Zakładka Advanced

### Scenariusz 7.1 — Ustawienia renderowania
| Krok | Akcja | Oczekiwany wynik |
|---|---|---|
| 1 | Zmień framerate z 60 na 30 | GLava aktywnej instancji restartuje się z niższym FPS (ustawienie per instancja, nie globalne) |
| 2 | Włącz/wyłącz VSync | Zmiana zachowana w rc.glsl |
| 3 | Zmień wersję shadera | rc.glsl zaktualizowany |
| 4 | Sprawdź `~/.config/glava-inst-0/glava/rc.glsl` | Wartości zgodne z GUI |

### Scenariusz 7.2 — Diagnostyka
| Krok | Akcja | Oczekiwany wynik |
|---|---|---|
| 1 | Kliknij "Test geometrii" | Messagebox z 7 wartościami (screen_w, screen_h, work_h, top, bottom, left, right) |
| 2 | Wartości sensowne dla systemu | W i H zgodne z rozdzielczością ekranu |
| 3 | Kliknij "Pokaż logi" | Otwiera terminal z `tail -f` na logu daemona |
| 4 | Logi zawierają wpisy z aktualnej sesji | Brak błędów krytycznych |

### Scenariusz 7.3 — Motyw GUI
| Krok | Akcja | Oczekiwany wynik |
|---|---|---|
| 1 | Zmień motyw forest-dark → forest-light | GUI zmienia wygląd natychmiastowo |
| 2 | Zmień z powrotem | Powrót do ciemnego motywu |
| 3 | Zrestartuj GUI | Motyw zachowany |

---

## Część 8: Workspace

### Scenariusz 8.1 — Zapis i odczyt workspace
| Krok | Akcja | Oczekiwany wynik |
|---|---|---|
| 1 | Utwórz 3 instancje: bars, circle, wave | 3 procesy aktywne |
| 2 | Każda instancja z unikalnymi kolorami i parametrami | — |
| 3 | Zapisz workspace (akcja w zakładce instancji) | Plik workspace zapisany |
| 4 | Zamknij GUI | Procesy GLava **działają dalej** — aby zatrzymać użyj toggle OFF przed zamknięciem GUI |
| 5 | Uruchom GUI ponownie | — |
| 6 | Wczytaj workspace | Dokładnie 3 instancje przywrócone (nie mniej) |
| 7 | Sprawdź procesy | Liczba == 3 |
| 8 | Sprawdź kolory i parametry każdej instancji | Identyczne z zapisanymi, włącznie z wartościami wygładzania |

### Scenariusz 8.2 — Workspace po restarcie systemu
| Krok | Akcja | Oczekiwany wynik |
|---|---|---|
| 1 | Zapisz workspace z N instancjami | — |
| 2 | Zrestartuj system | — |
| 3 | Uruchom GUI | GUI przywraca ostatnio używane instancje; workspace wczytaj ręcznie |
| 4 | Liczba procesów == N | Brak zdublowania |

---

## Część 9: Język i ustawienia globalne

### Scenariusz 9.1 — Zmiana języka
| Krok | Akcja | Oczekiwany wynik |
|---|---|---|
| 1 | Zmień język PL → EN (combobox w nagłówku) | GUI przeładowuje się po angielsku |
| 2 | Zmień EN → PL | GUI przeładowuje się po polsku |
| 3 | Sprawdź czy GLava nie restartuje się niepotrzebnie przy zmianie języka | Procesy niezmienione |
| 4 | Zrestartuj GUI | Język zachowany |

### Scenariusz 9.2 — Zapis rozmiaru i pozycji okna
| Krok | Akcja | Oczekiwany wynik |
|---|---|---|
| 1 | Przesuń i zmień rozmiar okna GUI | — |
| 2 | Zamknij i uruchom ponownie | Okno w tej samej pozycji i rozmiarze |
| 3 | Sprawdź `~/.config/GlavaMP/gui.conf` | Zawiera zapisaną geometrię okna |

---

## Część 10: Bing wallpaper i miniatury

### Scenariusz 10.1 — Pobieranie tapety
| Krok | Akcja | Oczekiwany wynik |
|---|---|---|
| 1 | Uruchom `sudo /usr/local/bin/bing-downloader.sh $USER` | Tapeta pobrana do `~/Pictures/Bing/bing_today.jpg` |
| 2 | Miniatury regionów pobrane | `~/Pictures/Bing/thumbs/` zawiera pliki .jpg |
| 3 | Metadane zapisane | `~/Pictures/Bing/metadata.json` istnieje |
| 4 | Ekran logowania zaktualizowany | `/usr/share/backgrounds/login-bing.jpg` |

### Scenariusz 10.2 — Miniatury offline
| Krok | Akcja | Oczekiwany wynik |
|---|---|---|
| 1 | Wyłącz sieć: `sudo nmcli networking off` | — |
| 2 | Uruchom `sudo /usr/local/bin/bing-downloader.sh $USER` | Skrypt kończy się bez błędu |
| 3 | Istniejące miniatury niezmienione | Pliki w `thumbs/` zachowane |
| 4 | `metadata.json` niezmieniony | Stare metadane zachowane |
| 5 | Włącz sieć: `sudo nmcli networking on` | — |

### Scenariusz 10.3 — Miniatura w GUI
| Krok | Akcja | Oczekiwany wynik |
|---|---|---|
| 1 | Otwórz zakładkę Main | Miniatura aktualnej tapety Bing widoczna |
| 2 | Zmień region Bing w ustawieniach | Miniatura odpowiadającego regionu |

---

## Część 11: Stabilność długoterminowa

### Scenariusz 11.1 — Sesja 30 minut
| Krok | Akcja | Oczekiwany wynik |
|---|---|---|
| 1 | Uruchom GUI z 2 instancjami | — |
| 2 | Uruchom audio: `bash tools/radio.sh` | GLava animuje się |
| 3 | Co 10 minut sprawdź: `pgrep -x glava | wc -l` | Zawsze == 2 |
| 4 | Po 30 minutach sprawdź użycie RAM | Brak memory leak (RSS nie rośnie) |
| 5 | Wyłącz GLava toggle OFF, następnie zamknij GUI | Liczba procesów == 0 |

### Scenariusz 11.2 — Cron i daemon
| Krok | Akcja | Oczekiwany wynik |
|---|---|---|
| 1 | Sprawdź cron root: `sudo crontab -l` | Wpis dla `bing-downloader.sh` |
| 2 | Poczekaj do pełnej godziny lub uruchom ręcznie | Tapeta pobrana, miniatury zaktualizowane |
| 3 | Sprawdź log daemona: `journalctl --user -u glava-color-daemon -n 50` | Brak błędów krytycznych |

---

## Tabela konfiguracji testowych

| Desktop | Środowisko | Status |
|---|---|---|
| Linux Mint 22.x XFCE | Live (toram) + normalna instalacja | ✅ Testowane |
| Linux Mint Cinnamon | Normalna instalacja | ✅ Działa |
| Linux Mint Cinnamon | Live (toram) | ⏳ Nie testowane |
| Linux Mint XFCE | Konto testowe (`su - testuser`) | ⏳ Do weryfikacji |

---

---

## Część 12: Odpięte panele — kierowanie danych do właściwej instancji (RC3)

> Weryfikacja naprawki błędu z RC3: odpięty panel musi zawsze wysyłać zmiany
> do instancji której dotyczy, niezależnie od aktywnej zakładki w oknie głównym.

### Scenariusz 12.1 — Podstawowy: odpięty panel nie reaguje na zmianę aktywnej zakładki

| Krok | Akcja | Oczekiwany wynik |
|---|---|---|
| 1 | Uruchom GUI z 2 instancjami: **Bars** i **Radial** | 2 procesy aktywne |
| 2 | Przejdź na zakładkę **Radial** | Radial jest aktywny |
| 3 | Odepnij panel "Kształt" dla Radial (przycisk ⊞ przy sekcji) | Okno główne minimalizuje się, panel odpina się |
| 4 | Przywróć okno główne (kliknij na pasku zadań) | Oba okna widoczne |
| 5 | Kliknij zakładkę **Bars** w oknie głównym | Bars staje się aktywny |
| 6 | Zmień dowolny parametr w odpiętym panelu **Radial** | GLava Radial restartuje się z nową wartością |
| 7 | Sprawdź liczbę procesów: `pgrep -x glava | wc -l` | Nadal == 2 (nie 3) |
| 8 | Sprawdź że **Bars** nadal wyświetla shader bars | Bars NIE zmienił się na radial |
| 9 | Sprawdź wartość w pliku Radial: `grep "PARAM" ~/.config/glava-inst-{id}/glava/radial.glsl` | Wartość zgodna ze zmianą |

### Scenariusz 12.2 — Dwa odpięte panele jednocześnie

| Krok | Akcja | Oczekiwany wynik |
|---|---|---|
| 1 | Uruchom GUI z instancjami **Bars** (inst-1) i **Radial** (inst-2) | 2 procesy aktywne |
| 2 | Odepnij panel "Kształt" dla **Bars** | Okno panelu Bars |
| 3 | Wróć do GUI, przejdź na **Radial**, odepnij panel "Kształt" dla **Radial** | Dwa odpięte panele na pulpicie |
| 4 | Zmień parametr w panelu **Bars** | Tylko Bars restartuje się |
| 5 | Zmień parametr w panelu **Radial** | Tylko Radial restartuje się |
| 6 | Sprawdź `pgrep -x glava | wc -l` | Zawsze == 2 |
| 7 | Sprawdź że każda instancja wyświetla swój shader | Bars = bars, Radial = radial |

### Scenariusz 12.3 — Zmiana parametru po przełączeniu wszystkich zakładek

| Krok | Akcja | Oczekiwany wynik |
|---|---|---|
| 1 | Uruchom GUI z 3 instancjami: Bars, Wave, Radial | 3 procesy |
| 2 | Odepnij panel "Wygładzanie" dla **Wave** | Panel Wave odpięty |
| 3 | Przełącz kolejno przez wszystkie zakładki w oknie głównym | active_instance zmienia się 3 razy |
| 4 | Zmień parametr "Grawitacja" w odpiętym panelu **Wave** | Tylko Wave restartuje się |
| 5 | Sprawdź `~/.config/glava-inst-{wave_id}/glava/smooth_parameters.glsl` | Wartość grawitacji zmieniona tylko w Wave |
| 6 | Sprawdź pozostałe instancje | Bars i Radial niezmienione |

## Narzędzia diagnostyczne

```bash
# Liczba procesów GLava
pgrep -x glava | wc -l

# PID-y procesów GLava
pgrep -x glava

# Monitor w czasie rzeczywistym
watch -n 1 'pgrep -x glava | wc -l; pgrep -x glava'

# Logi daemona
journalctl --user -u glava-color-daemon -n 50 -f

# Sprawdź rejestr instancji
cat ~/.config/GlavaMP/instances.json

# Sprawdź pliki PID
ls ~/.config/GlavaMP/*.pid 2>/dev/null

# Sprawdź aktywny moduł instancji 0
grep "#request mod" ~/.config/glava-inst-0/glava/rc.glsl

# Sprawdź geometrię instancji 0
grep "setgeometry" ~/.config/glava-inst-0/glava/rc.glsl
```
