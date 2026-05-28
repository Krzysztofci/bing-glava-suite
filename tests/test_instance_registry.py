import pytest
import os
import json

@pytest.fixture
def mock_registry(tmp_path, monkeypatch):
    from gui import instance as inst_mod
    registry_file = str(tmp_path / "instances.json")
    monkeypatch.setattr(inst_mod, "INSTANCES_FILE", registry_file)
    monkeypatch.setattr(inst_mod, "USER_HOME", str(tmp_path))
    return registry_file

# ── load_instances ────────────────────────────────────────────────────────────

def test_load_instances_empty_when_missing(mock_registry):
    """load_instances zwraca [] gdy plik nie istnieje."""
    from gui.instance import load_instances
    assert load_instances() == []

def test_load_instances_reads_file(mock_registry):
    from gui.instance import load_instances, save_instances
    data = [
        {"inst_id": 0, "name": "Default", "module": "bars",   "active": True},
        {"inst_id": 1, "name": "Second",  "module": "circle", "active": False},
    ]
    save_instances(data)
    result = load_instances()
    assert len(result) == 2
    assert result[1]["inst_id"] == 1
    assert result[1]["name"] == "Second"

def test_load_instances_handles_corrupt(mock_registry):
    """load_instances zwraca [] gdy plik jest uszkodzony."""
    from gui.instance import load_instances
    with open(mock_registry, "w") as f:
        f.write("{ invalid json }")
    assert load_instances() == []

def test_load_instances_handles_non_list(mock_registry):
    """load_instances zwraca [] gdy plik zawiera dict zamiast listy."""
    from gui.instance import load_instances
    with open(mock_registry, "w") as f:
        json.dump({"inst_id": 0}, f)
    assert load_instances() == []

# ── save_instances ────────────────────────────────────────────────────────────

def test_save_instances_creates_file(mock_registry):
    from gui.instance import save_instances, load_instances
    save_instances([{"inst_id": 0, "name": "A", "module": "bars", "active": False}])
    assert os.path.exists(mock_registry)
    assert len(load_instances()) == 1

def test_save_instances_roundtrip(mock_registry):
    from gui.instance import save_instances, load_instances
    data = [
        {"inst_id": 0, "name": "Foo", "module": "wave",   "active": True},
        {"inst_id": 2, "name": "Bar", "module": "radial", "active": False},
    ]
    save_instances(data)
    result = load_instances()
    assert result[0]["name"] == "Foo"
    assert result[1]["inst_id"] == 2

# ── register_instance ─────────────────────────────────────────────────────────

def test_register_adds_instance(mock_registry):
    from gui.instance import register_instance, load_instances
    register_instance(1, name="Test", module="wave")
    instances = load_instances()
    assert len(instances) == 1
    assert instances[0]["inst_id"] == 1
    assert instances[0]["name"] == "Test"
    assert instances[0]["module"] == "wave"

def test_register_default_name(mock_registry):
    from gui.instance import register_instance, load_instances
    register_instance(3)
    instances = load_instances()
    assert instances[0]["name"] == "Instance 3"

def test_register_default_module(mock_registry):
    from gui.instance import register_instance, load_instances
    register_instance(1)
    assert load_instances()[0]["module"] == "bars"

def test_register_active_false_by_default(mock_registry):
    from gui.instance import register_instance, load_instances
    register_instance(1)
    assert load_instances()[0]["active"] == False

def test_register_idempotent(mock_registry):
    """Dwukrotna rejestracja tej samej instancji nie duplikuje wpisu."""
    from gui.instance import register_instance, load_instances
    register_instance(1)
    register_instance(1)
    assert len(load_instances()) == 1

def test_register_multiple(mock_registry):
    from gui.instance import register_instance, load_instances
    register_instance(1, name="A")
    register_instance(2, name="B")
    register_instance(3, name="C")
    ids = [i["inst_id"] for i in load_instances()]
    assert ids == [1, 2, 3]

# ── unregister_instance ───────────────────────────────────────────────────────

def test_unregister_removes_instance(mock_registry):
    from gui.instance import register_instance, unregister_instance, load_instances
    register_instance(1)
    register_instance(2)
    unregister_instance(1)
    ids = [i["inst_id"] for i in load_instances()]
    assert 1 not in ids
    assert 2 in ids

def test_unregister_nonexistent_does_not_raise(mock_registry):
    """Usunięcie nieistniejącej instancji nie crashuje."""
    from gui.instance import unregister_instance
    unregister_instance(99)

def test_unregister_inst0_allowed(mock_registry):
    """inst-0 nie ma specjalnej ochrony — można wyrejestrować."""
    from gui.instance import register_instance, unregister_instance, load_instances
    register_instance(0, name="Zero")
    unregister_instance(0)
    ids = [i["inst_id"] for i in load_instances()]
    assert 0 not in ids

# ── update_instance ───────────────────────────────────────────────────────────

def test_update_instance_name(mock_registry):
    from gui.instance import register_instance, update_instance, load_instances
    register_instance(1, name="Stara")
    update_instance(1, name="Nowa")
    assert load_instances()[0]["name"] == "Nowa"

def test_update_instance_module(mock_registry):
    from gui.instance import register_instance, update_instance, load_instances
    register_instance(1, module="bars")
    update_instance(1, module="circle")
    assert load_instances()[0]["module"] == "circle"

def test_update_instance_active(mock_registry):
    from gui.instance import register_instance, update_instance, load_instances
    register_instance(1)
    update_instance(1, active=True)
    assert load_instances()[0]["active"] == True

def test_update_nonexistent_does_not_raise(mock_registry):
    from gui.instance import update_instance
    update_instance(99, name="Ghost")

# ── next_inst_id ──────────────────────────────────────────────────────────────

def test_next_inst_id_starts_at_1(mock_registry):
    from gui.instance import next_inst_id
    assert next_inst_id() == 1

def test_next_inst_id_skips_existing(mock_registry):
    from gui.instance import register_instance, next_inst_id
    register_instance(1)
    register_instance(2)
    assert next_inst_id() == 3

def test_next_inst_id_fills_gap(mock_registry):
    from gui.instance import register_instance, next_inst_id
    register_instance(1)
    register_instance(3)
    assert next_inst_id() == 2

def test_next_inst_id_with_inst0(mock_registry):
    """inst-0 jest zwykłą instancją — next_inst_id() liczy normalnie."""
    from gui.instance import register_instance, next_inst_id
    register_instance(0)
    register_instance(1)
    assert next_inst_id() == 2
