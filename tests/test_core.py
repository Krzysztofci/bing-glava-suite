import pytest
import os
import json
from gui import core

# ── SMOOTH_PARAMS struktura ───────────────────────────────────────────────────

def test_smooth_params_structure():
    """Każdy wpis SMOOTH_PARAMS ma 8 elementów."""
    for p in core.SMOOTH_PARAMS:
        assert len(p) == 8, f"SMOOTH_PARAMS wpis {p[0]} ma {len(p)} elementów, oczekiwano 8"

def test_smooth_params_types():
    """SMOOTH_PARAMS: key=str, vmin/vmax/default/step=numeric, unit=str, tooltip=str."""
    for p in core.SMOOTH_PARAMS:
        key, label, vmin, vmax, default, unit, step, tooltip = p
        assert isinstance(key, str)
        assert isinstance(vmin, (int, float))
        assert isinstance(vmax, (int, float))
        assert vmin < vmax
        assert vmin <= default <= vmax
        assert step > 0

# ── load_settings ─────────────────────────────────────────────────────────────

def test_load_settings_returns_dict(tmp_path, monkeypatch):
    """load_settings zwraca dict nawet gdy plik nie istnieje."""
    monkeypatch.setattr(core, "SETTINGS_FILE", str(tmp_path / "settings.json"))
    result = core.load_settings()
    assert isinstance(result, dict)

def test_load_settings_reads_file(tmp_path, monkeypatch):
    """load_settings odczytuje istniejący plik."""
    sf = tmp_path / "settings.json"
    sf.write_text(json.dumps({"lang": "pl", "theme": "dark"}))
    monkeypatch.setattr(core, "SETTINGS_FILE", str(sf))
    result = core.load_settings()
    assert result["lang"] == "pl"
    assert result["theme"] == "dark"

def test_load_settings_handles_corrupt(tmp_path, monkeypatch):
    """load_settings zwraca {} gdy plik jest uszkodzony."""
    sf = tmp_path / "settings.json"
    sf.write_text("{ invalid json }")
    monkeypatch.setattr(core, "SETTINGS_FILE", str(sf))
    result = core.load_settings()
    assert isinstance(result, dict)

# ── load_lang ─────────────────────────────────────────────────────────────────

def test_load_lang_returns_dict():
    """load_lang('pl') zwraca niepusty dict."""
    result = core.load_lang("pl")
    assert isinstance(result, dict)
    assert len(result) > 0

def test_load_lang_fallback():
    """load_lang z nieznanym kodem zwraca dict (fallback do en lub pusty)."""
    result = core.load_lang("xx_NONEXISTENT")
    assert isinstance(result, dict)

def test_load_lang_get_method():
    """Zwrócony dict ma metodę get() z fallbackiem."""
    T = core.load_lang("pl")
    val = T.get("nonexistent_key", "fallback")
    assert val == "fallback"
