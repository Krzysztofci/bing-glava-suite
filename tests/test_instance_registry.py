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

def test_load_instances_default_when_missing(mock_registry):
    from gui.instance import load_instances
    result = load_instances()
    assert len(result) == 1
    assert result[0]["inst_id"] == 0
    assert result[0]["name"] == "Default"

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
    from gui.instance import load_instances
    with open(mock_registry, "w") as f:
        f.write("{ invalid json }")
    result = load_instances()
    assert result[0]["inst_id"] == 0

# ── register_instance ─────────────────────────────────────────────────────────

def test_register_adds_instance(mock_registry):
    from gui.instance import register_instance, load_instances
    register_instance(1, name="Test", module="wave")
    instances = load_instances()
    assert len(instances) == 2
    assert instances[1]["inst_id"] == 1
    assert instances[1]["name"] == "Test"
    assert instances[1]["module"] == "wave"

def test_register_idempotent(mock_registry):
    from gui.instance import register_instance, load_instances
    register_instance(1)
    register_instance(1)
    assert len(load_instances()) == 2

# ── unregister_instance ───────────────────────────────────────────────────────

def test_unregister_removes_instance(mock_registry):
    from gui.instance import register_instance, unregister_instance, load_instances
    register_instance(1)
    unregister_instance(1)
    ids = [i["inst_id"] for i in load_instances()]
    assert 1 not in ids

def test_unregister_inst0_raises(mock_registry):
    from gui.instance import unregister_instance
    with pytest.raises(ValueError):
        unregister_instance(0)

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
