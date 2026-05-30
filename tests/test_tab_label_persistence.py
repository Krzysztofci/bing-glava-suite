# =============================================================================
# tests/test_tab_label_persistence.py
# Testy bug #2 — błędne nazwy zakładek po restarcie GUI.
#
# Problem: etykiety generowane przez add_tab (np. "Bars ✦", "Radial ✦")
# są zapisywane do instances.json przez update_instance(iid, name=actual).
# Przy kolejnym starcie GUI is_auto NIE rozpoznaje tych etykiet jako
# autogenerowanych (wzorzec r'Instance \d+' ich nie łapie), więc są
# przekazywane jako label do add_tab. add_tab mimo to inkrementuje
# _module_counts, co powoduje że kolejna instancja tego samego modułu
# dostaje błędny numer ("Bars ✦2" zamiast "Bars ✦").
#
# Testy operują bezpośrednio na is_auto logic i module_counts —
# bez uruchamiania tkinter.
# =============================================================================
import re
import pytest
# ── Fixture: mock_registry ────────────────────────────────────────────────────
@pytest.fixture
def mock_registry(tmp_path, monkeypatch):
    from gui import instance as inst_mod
    registry_file = str(tmp_path / "instances.json")
    monkeypatch.setattr(inst_mod, "INSTANCES_FILE", registry_file)
    monkeypatch.setattr(inst_mod, "USER_HOME", str(tmp_path))
    return registry_file


# ── Pomocnicza funkcja is_auto (dokładna kopia z glava-gui.py) ───────────────
def _is_auto(name):
    """Kopia logiki is_auto z _build_notebook w glava-gui.py."""
    return (
        name is None
        or name == "Default"
        or bool(re.fullmatch(r'Instance \d+', name))
    )


def _add_tab_label(module, module_counts, label=None):
    """
    Kopia logiki generowania etykiety z InstTabBar.add_tab.
    Zwraca (wygenerowana_etykieta, zaktualizowany_module_counts).
    """
    counts = dict(module_counts)
    cnt = counts.get(module, 0) + 1
    counts[module] = cnt
    if label is None:
        name = module.capitalize()
        generated = f"{name} \u2726" if cnt == 1 else f"{name} \u2726{cnt}"
    else:
        generated = label
    return generated, counts


# ── is_auto nie rozpoznaje etykiet generowanych przez add_tab ─────────────────
def test_is_auto_does_not_match_generated_label_single():
    """'Bars ✦' NIE jest rozpoznane jako autogenerowane — to jest rdzeń buga."""
    assert _is_auto("Bars \u2726") is False


def test_is_auto_does_not_match_generated_label_numbered():
    """'Bars ✦2' NIE jest rozpoznane jako autogenerowane."""
    assert _is_auto("Bars \u2726\u0032") is False


def test_is_auto_does_not_match_any_module():
    """Żaden moduł z sufixem ✦ nie przejdzie przez is_auto."""
    for mod in ("bars", "wave", "circle", "graph", "radial"):
        label = f"{mod.capitalize()} \u2726"
        assert _is_auto(label) is False, f"Błąd dla: {label!r}"


def test_is_auto_matches_legacy_patterns():
    """Wzorce które IS_AUTO powinien łapać — None, 'Default', 'Instance N'."""
    assert _is_auto(None) is True
    assert _is_auto("Default") is True
    assert _is_auto("Instance 0") is True
    assert _is_auto("Instance 42") is True


def test_is_auto_does_not_match_user_rename():
    """Nazwa nadana ręcznie przez użytkownika NIE jest auto."""
    assert _is_auto("Mój wizualizer") is False
    assert _is_auto("lewy panel") is False


# ── Błędna numeracja przy ponownym dodaniu z zapisaną etykietą ───────────────
def test_second_session_bars_gets_wrong_number():
    """
    Symulacja buga: po restarcie GUI instancja bars ma zapisaną etykietę
    "Bars ✦" w instances.json. is_auto zwraca False, więc label_to_pass="Bars ✦".
    add_tab inkrementuje licznik mimo przekazanego label → kolejna instancja
    bars dostaje "Bars ✦2" zamiast "Bars ✦".
    """
    counts = {}
    # Sesja 1: dwie instancje bars — autogenerowane etykiety
    label0, counts = _add_tab_label("bars", counts, label=None)
    label1, counts = _add_tab_label("bars", counts, label=None)
    assert label0 == "Bars \u2726"
    assert label1 == "Bars \u2726\u0032"  # "Bars ✦2"

    # Sesja 2: inst_id=0 ma w rejestrze "Bars ✦" — is_auto False, przekazane
    # jako label. inst_id=1 ma "Bars ✦2" — też is_auto False.
    counts2 = {}
    # inst_id=0 — label przekazany (nie None), ale licznik i tak rośnie
    out0, counts2 = _add_tab_label("bars", counts2, label=label0)
    # inst_id=1 — label przekazany
    out1, counts2 = _add_tab_label("bars", counts2, label=label1)
    # Etykiety zachowane bo label != None — to część poprawna
    assert out0 == "Bars \u2726"
    assert out1 == "Bars \u2726\u0032"
    # ALE licznik jest już 2 — dodanie trzeciej instancji da "Bars ✦3" nie "Bars ✦2"
    assert counts2["bars"] == 2


def test_module_change_corrupts_saved_name(mock_registry):
    """
    Symulacja buga: instancja zarejestrowana jako radial, GUI zapisuje etykietę
    "Radial ✦". Użytkownik zmienia moduł na bars — update_instance zapisuje
    module="bars" ale name zostaje "Radial ✦". Przy restarcie is_auto=False,
    więc zakładka bars dostaje etykietę "Radial ✦".
    """
    from gui.instance import register_instance, update_instance, load_instances

    register_instance(1, name="Instance 1", module="radial")
    # GUI generuje etykietę i zapisuje
    update_instance(1, name="Radial \u2726")
    # Użytkownik zmienia moduł
    update_instance(1, module="bars")

    entry = load_instances()[0]
    # name i module są niespójne — to jest stan który prowadzi do buga
    assert entry["module"] == "bars"
    assert entry["name"] == "Radial \u2726"  # stara nazwa — błąd


def test_correct_is_auto_would_catch_generated_labels():
    """
    Weryfikacja że rozszerzony wzorzec is_auto naprawiłby buga.
    Poprawna implementacja powinna łapać etykiety w formacie "<Moduł> ✦[N]".
    """
    fixed_pattern = re.compile(
        r'Instance \d+|Default|'
        r'(?:Bars|Wave|Circle|Graph|Radial) \u2726\d*'
    )

    def is_auto_fixed(name):
        return (name is None or bool(fixed_pattern.fullmatch(name)))

    assert is_auto_fixed("Bars \u2726") is True
    assert is_auto_fixed("Bars \u27262") is True
    assert is_auto_fixed("Radial \u2726") is True
    assert is_auto_fixed("Wave \u272610") is True
    assert is_auto_fixed("Instance 3") is True
    assert is_auto_fixed("Default") is True
    # Nazwy użytkownika nadal chronione
    assert is_auto_fixed("Mój wizualizer") is False
    assert is_auto_fixed("lewy panel") is False


# ── Pełny cykl: rejestr → build_notebook → restart → build_notebook ──────────
def test_full_restart_cycle_three_instances(mock_registry):
    """
    Symulacja pełnego cyklu: 3 instancje (radial, bars, graph),
    zamknięcie GUI (zapis do rejestru), ponowne otwarcie.
    Sprawdza czy etykiety po restarcie są spójne z modułami.
    """
    from gui.instance import register_instance, update_instance, load_instances

    # Sesja 1: rejestracja 3 instancji
    register_instance(0, name="Instance 0", module="radial")
    register_instance(1, name="Instance 1", module="bars")
    register_instance(2, name="Instance 2", module="graph")

    # GUI generuje etykiety i zapisuje (symulacja _build_notebook → labels_to_save)
    counts = {}
    for iid, mod in [(0, "radial"), (1, "bars"), (2, "graph")]:
        label, counts = _add_tab_label(mod, counts, label=None)
        update_instance(iid, name=label)

    # Weryfikacja stanu po sesji 1
    entries = {e["inst_id"]: e for e in load_instances()}
    assert entries[0]["name"] == "Radial \u2726"
    assert entries[1]["name"] == "Bars \u2726"
    assert entries[2]["name"] == "Graph \u2726"

    # Sesja 2: reload — czy nazwy są spójne z modułami?
    for entry in load_instances():
        name = entry["name"]
        mod  = entry["module"]
        # Nazwa powinna zaczynać się od nazwy modułu (capitalize)
        assert name.startswith(mod.capitalize()), (
            f"inst_id={entry['inst_id']}: name={name!r} nie pasuje do module={mod!r}"
        )


def test_unregister_does_not_corrupt_remaining_names(mock_registry):
    """
    Zamknięcie jednej zakładki nie psuje nazw pozostałych instancji.
    """
    from gui.instance import (
        register_instance, update_instance,
        unregister_instance, load_instances,
    )

    register_instance(0, name="Instance 0", module="radial")
    register_instance(1, name="Instance 1", module="bars")
    register_instance(2, name="Instance 2", module="graph")

    counts = {}
    for iid, mod in [(0, "radial"), (1, "bars"), (2, "graph")]:
        label, counts = _add_tab_label(mod, counts, label=None)
        update_instance(iid, name=label)

    # Zamknięcie inst_id=1 (bars)
    unregister_instance(1)

    remaining = {e["inst_id"]: e for e in load_instances()}
    assert 1 not in remaining
    assert remaining[0]["name"] == "Radial \u2726"
    assert remaining[2]["name"] == "Graph \u2726"
    # Moduły nie zmienione
    assert remaining[0]["module"] == "radial"
    assert remaining[2]["module"] == "graph"
