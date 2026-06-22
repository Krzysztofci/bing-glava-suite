import importlib.util
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), '..', 'scripts', 'glava-gui.py')


def _load_glava_gui_module():
    """glava-gui.py ma myślnik w nazwie -> nie da się go zaimportować
    zwykłym 'import'. Ładujemy po ścieżce przez importlib, co pozwala
    testować PRAWDZIWE metody/funkcje (nie kopie-w-teście jak wcześniej
    w test_toggle_race.py)."""
    spec = importlib.util.spec_from_file_location("glava_gui_under_test", _SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def gg():
    """Moduł glava-gui.py załadowany raz na cały plik testowy."""
    return _load_glava_gui_module()


# ── load_gui_conf / save_gui_conf ────────────────────────────────────────────

def test_load_gui_conf_returns_defaults_when_file_missing(gg, tmp_path, monkeypatch):
    conf_path = str(tmp_path / "gui.conf")
    monkeypatch.setattr(gg, "GUI_CONF", conf_path)

    conf = gg.load_gui_conf()

    assert conf["width"]  == gg.WIN_W_DEFAULT
    assert conf["height"] == gg.WIN_H_DEFAULT
    assert conf["theme"]  == "forest-dark"
    assert conf["x"] is None
    assert conf["y"] is None


def test_load_gui_conf_creates_file_when_missing(gg, tmp_path, monkeypatch):
    """Gdy gui.conf nie istnieje, load_gui_conf() wywołuje save_gui_conf()
    z domyślnymi wartościami."""
    conf_path = str(tmp_path / "gui.conf")
    monkeypatch.setattr(gg, "GUI_CONF", conf_path)
    monkeypatch.setattr(gg, "CONFIG_DIR", str(tmp_path))

    assert not os.path.exists(conf_path)
    gg.load_gui_conf()
    assert os.path.exists(conf_path)


def test_load_gui_conf_reads_existing_values(gg, tmp_path, monkeypatch):
    conf_path = str(tmp_path / "gui.conf")
    with open(conf_path, "w") as f:
        json.dump({"width": 1280, "height": 800, "x": 10, "y": 20,
                   "theme": "forest-light"}, f)
    monkeypatch.setattr(gg, "GUI_CONF", conf_path)

    conf = gg.load_gui_conf()

    assert conf == {"width": 1280, "height": 800, "x": 10, "y": 20,
                     "theme": "forest-light"}


def test_load_gui_conf_ignores_unknown_keys(gg, tmp_path, monkeypatch):
    conf_path = str(tmp_path / "gui.conf")
    with open(conf_path, "w") as f:
        json.dump({"width": 999, "totally_unknown_key": "ignored"}, f)
    monkeypatch.setattr(gg, "GUI_CONF", conf_path)

    conf = gg.load_gui_conf()

    assert conf["width"] == 999
    assert "totally_unknown_key" not in conf


def test_load_gui_conf_falls_back_to_defaults_on_corrupt_json(gg, tmp_path, monkeypatch):
    conf_path = str(tmp_path / "gui.conf")
    with open(conf_path, "w") as f:
        f.write("{not valid json!!!")
    monkeypatch.setattr(gg, "GUI_CONF", conf_path)

    conf = gg.load_gui_conf()

    assert conf["width"] == gg.WIN_W_DEFAULT


def test_save_gui_conf_writes_json(gg, tmp_path, monkeypatch):
    conf_path = str(tmp_path / "nested" / "gui.conf")
    monkeypatch.setattr(gg, "GUI_CONF", conf_path)
    monkeypatch.setattr(gg, "CONFIG_DIR", str(tmp_path / "nested"))

    gg.save_gui_conf({"width": 1024, "height": 768, "x": None, "y": None,
                       "theme": "forest-dark"})

    with open(conf_path) as f:
        data = json.load(f)
    assert data["width"] == 1024


def test_save_gui_conf_creates_parent_dir(gg, tmp_path, monkeypatch):
    conf_path = str(tmp_path / "does" / "not" / "exist" / "gui.conf")
    monkeypatch.setattr(gg, "GUI_CONF", conf_path)
    monkeypatch.setattr(gg, "CONFIG_DIR", str(tmp_path / "does" / "not" / "exist"))

    gg.save_gui_conf({"width": 1, "height": 1, "x": None, "y": None, "theme": "x"})

    assert os.path.exists(conf_path)
