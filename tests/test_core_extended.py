import pytest
import os
import json
from gui import core

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_core(tmp_path, monkeypatch):
    """Patchuje wszystkie ścieżki plików core.py na tmp_path."""
    monkeypatch.setattr(core, "CONFIG_DIR",        str(tmp_path / "GlavaMP"))
    monkeypatch.setattr(core, "GLAVA_DIR",         str(tmp_path / "glava"))
    monkeypatch.setattr(core, "SETTINGS_FILE",     str(tmp_path / "GlavaMP" / "gui_settings.json"))
    monkeypatch.setattr(core, "PRESETS_FILE",      str(tmp_path / "GlavaMP" / "presets.json"))
    monkeypatch.setattr(core, "PROFILES_FILE",     str(tmp_path / "GlavaMP" / "profiles.json"))
    monkeypatch.setattr(core, "ACTIVE_MODULE_FILE",str(tmp_path / "glava" / "active_module"))
    monkeypatch.setattr(core, "BINGCONF_DIR",      str(tmp_path / "bing-glava"))
    monkeypatch.setattr(core, "BINGCONF_FILE",     str(tmp_path / "bing-glava" / "config"))
    os.makedirs(str(tmp_path / "GlavaMP"), exist_ok=True)
    os.makedirs(str(tmp_path / "glava"),   exist_ok=True)
    os.makedirs(str(tmp_path / "bing-glava"), exist_ok=True)
    return tmp_path

# ── read_active_module / write_active_module ──────────────────────────────────

def test_write_read_active_module(mock_core):
    for mod in core.GLAVA_MODULES:
        core.write_active_module(mod)
        assert core.read_active_module() == mod

def test_read_active_module_default(mock_core):
    """Brak pliku zwraca domyślny moduł 'graph'."""
    assert core.read_active_module() == "graph"

def test_read_active_module_unknown(mock_core):
    """Nieznany moduł w pliku zwraca 'graph'."""
    with open(core.ACTIVE_MODULE_FILE, "w") as f:
        f.write("nonexistent_module")
    assert core.read_active_module() == "graph"

def test_write_active_module_creates_dir(tmp_path, monkeypatch):
    """write_active_module tworzy katalog jeśli nie istnieje."""
    nested = str(tmp_path / "new" / "glava" / "active_module")
    monkeypatch.setattr(core, "ACTIVE_MODULE_FILE", nested)
    monkeypatch.setattr(core, "CONFIG_DIR", str(tmp_path / "new" / "GlavaMP"))
    core.write_active_module("bars")
    assert open(nested).read().strip() == "bars"

# ── get_live_frag / get_template ──────────────────────────────────────────────

def test_get_live_frag_default(mock_core):
    """get_live_frag() bez argumentu używa aktywnego modułu."""
    core.write_active_module("bars")
    frag = core.get_live_frag()
    assert frag.endswith("bars/1.frag")

def test_get_live_frag_explicit(mock_core):
    for mod in core.GLAVA_MODULES:
        frag = core.get_live_frag(mod)
        assert frag.endswith(f"{mod}/1.frag")

def test_get_template_default(mock_core):
    core.write_active_module("circle")
    tmpl = core.get_template()
    assert tmpl.endswith("circle_colors.frag")

def test_get_template_explicit(mock_core):
    for mod in core.GLAVA_MODULES:
        tmpl = core.get_template(mod)
        assert tmpl.endswith(f"{mod}_colors.frag")

# ── save_settings ─────────────────────────────────────────────────────────────

def test_save_and_load_settings(mock_core):
    settings = {"lang": "pl", "theme": "dark", "gradient_mode": "hsv"}
    core.save_settings(settings)
    result = core.load_settings()
    assert result["lang"] == "pl"
    assert result["theme"] == "dark"
    assert result["gradient_mode"] == "hsv"

def test_save_settings_overwrites(mock_core):
    core.save_settings({"lang": "en"})
    core.save_settings({"lang": "pl"})
    assert core.load_settings()["lang"] == "pl"

# ── read_bing_config / write_bing_config ──────────────────────────────────────

def test_read_bing_config_default(mock_core):
    """Brak pliku zwraca domyślny region de-DE."""
    cfg = core.read_bing_config()
    assert cfg["BING_REGION"] == "de-DE"

def test_write_read_bing_config(mock_core):
    core.write_bing_config({"BING_REGION": "pl-PL"})
    cfg = core.read_bing_config()
    assert cfg["BING_REGION"] == "pl-PL"

def test_write_bing_config_multiple_keys(mock_core):
    core.write_bing_config({"BING_REGION": "en-US", "CUSTOM_KEY": "value"})
    cfg = core.read_bing_config()
    assert cfg["BING_REGION"] == "en-US"
    assert cfg["CUSTOM_KEY"] == "value"

def test_read_bing_config_ignores_comments(mock_core):
    """Linie komentarzy (# ...) są ignorowane."""
    with open(core.BINGCONF_FILE, "w") as f:
        f.write("# komentarz\nBING_REGION=fr-FR\n")
    cfg = core.read_bing_config()
    assert cfg["BING_REGION"] == "fr-FR"
    assert "# komentarz" not in cfg

# ── available_langs ───────────────────────────────────────────────────────────

def test_available_langs_returns_dict():
    result = core.available_langs()
    assert isinstance(result, dict)
    assert len(result) >= 1

def test_available_langs_contains_pl_en():
    result = core.available_langs()
    assert "pl" in result
    assert "en" in result

def test_available_langs_values_are_strings():
    for code, name in core.available_langs().items():
        assert isinstance(code, str)
        assert isinstance(name, str)

# ── load/save_color_presets ───────────────────────────────────────────────────

def test_load_color_presets_empty(mock_core):
    assert core.load_color_presets() == {}

def test_save_and_load_color_presets(mock_core):
    presets = {
        "Czerwony": {"top": "#ff0000", "mid": "#880000", "bottom": "#440000"},
        "Zielony":  {"top": "#00ff00", "mid": "#008800", "bottom": "#004400"},
    }
    core.save_color_presets(presets)
    result = core.load_color_presets()
    assert result["Czerwony"]["top"] == "#ff0000"
    assert result["Zielony"]["mid"] == "#008800"

def test_save_color_presets_overwrites(mock_core):
    core.save_color_presets({"A": {"top": "#111111"}})
    core.save_color_presets({"B": {"top": "#222222"}})
    result = core.load_color_presets()
    assert "A" not in result
    assert result["B"]["top"] == "#222222"

def test_load_color_presets_handles_corrupt(mock_core):
    with open(core.PRESETS_FILE, "w") as f:
        f.write("{ invalid json }")
    assert core.load_color_presets() == {}

# ── load/save_shader_profiles ─────────────────────────────────────────────────

def test_load_shader_profiles_empty(mock_core):
    assert core.load_shader_profiles() == {}

def test_save_and_load_shader_profiles(mock_core):
    profiles = {
        "bars": {
            "Gruby bass": {"BAR_WIDTH": 8, "BAR_GAP": 3},
        },
        "circle": {
            "Duże koło": {"RADIUS": 220},
        }
    }
    core.save_shader_profiles(profiles)
    result = core.load_shader_profiles()
    assert result["bars"]["Gruby bass"]["BAR_WIDTH"] == 8
    assert result["circle"]["Duże koło"]["RADIUS"] == 220

def test_load_shader_profiles_handles_corrupt(mock_core):
    with open(core.PROFILES_FILE, "w") as f:
        f.write("{ invalid json }")
    assert core.load_shader_profiles() == {}

def test_load_shader_profiles_handles_non_dict(mock_core):
    with open(core.PROFILES_FILE, "w") as f:
        json.dump([1, 2, 3], f)
    assert core.load_shader_profiles() == {}

# ── get/save/delete_shader_profile_for_module ─────────────────────────────────

def test_get_profiles_empty_module(mock_core):
    assert core.get_shader_profiles_for_module("bars") == {}

def test_save_and_get_profile_for_module(mock_core):
    core.save_shader_profile_for_module("bars", "Test", {"BAR_WIDTH": 5})
    result = core.get_shader_profiles_for_module("bars")
    assert "Test" in result
    assert result["Test"]["BAR_WIDTH"] == 5

def test_save_profile_does_not_affect_other_module(mock_core):
    core.save_shader_profile_for_module("bars", "Test", {"BAR_WIDTH": 5})
    assert core.get_shader_profiles_for_module("circle") == {}

def test_save_multiple_profiles_same_module(mock_core):
    core.save_shader_profile_for_module("bars", "A", {"BAR_WIDTH": 2})
    core.save_shader_profile_for_module("bars", "B", {"BAR_WIDTH": 8})
    result = core.get_shader_profiles_for_module("bars")
    assert "A" in result
    assert "B" in result

def test_save_profile_overwrites_existing(mock_core):
    core.save_shader_profile_for_module("bars", "Test", {"BAR_WIDTH": 2})
    core.save_shader_profile_for_module("bars", "Test", {"BAR_WIDTH": 9})
    assert core.get_shader_profiles_for_module("bars")["Test"]["BAR_WIDTH"] == 9

def test_delete_profile_for_module(mock_core):
    core.save_shader_profile_for_module("bars", "Test", {"BAR_WIDTH": 5})
    result = core.delete_shader_profile_for_module("bars", "Test")
    assert result == True
    assert "Test" not in core.get_shader_profiles_for_module("bars")

def test_delete_profile_removes_empty_module(mock_core):
    """Usunięcie ostatniego profilu modułu usuwa też klucz modułu."""
    core.save_shader_profile_for_module("bars", "Test", {})
    core.delete_shader_profile_for_module("bars", "Test")
    assert "bars" not in core.load_shader_profiles()

def test_delete_nonexistent_profile_returns_false(mock_core):
    assert core.delete_shader_profile_for_module("bars", "Nonexistent") == False

def test_delete_profile_does_not_affect_other_module(mock_core):
    core.save_shader_profile_for_module("bars",   "Test", {"BAR_WIDTH": 5})
    core.save_shader_profile_for_module("circle", "Test", {"RADIUS": 200})
    core.delete_shader_profile_for_module("bars", "Test")
    assert "Test" in core.get_shader_profiles_for_module("circle")
