import os
import sys
import pytest
import tkinter as tk
from tkinter import ttk

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import gui.instance_tab_bar as bar_mod


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def root():
    r = tk.Tk()
    r.withdraw()
    yield r
    r.destroy()


@pytest.fixture
def captured_callbacks():
    """Rejestr wywołań callbacków — przekazywany jako on_select/on_add/etc."""
    calls = {
        "select": [], "add": [], "load_workspace": [], "save_workspace": [],
        "close": [], "action": [],
    }
    return calls


@pytest.fixture
def bar(root, captured_callbacks):
    c = captured_callbacks
    return bar_mod.InstanceTabBar(
        root,
        on_select=lambda iid: c["select"].append(iid),
        on_add=lambda mod: c["add"].append(mod),
        on_load_workspace=lambda: c["load_workspace"].append(True),
        on_save_workspace=lambda: c["save_workspace"].append(True),
        on_close=lambda iid: c["close"].append(iid),
        on_action=lambda *a: c["action"].append(a),
    )


# ── add_tab — guard / duplicate id ──────────────────────────────────────────

def test_add_tab_creates_entry_in_tabs_dict(bar):
    bar.add_tab(inst_id=1, module="bars")
    assert 1 in bar._tabs


def test_add_tab_ignores_duplicate_inst_id(bar):
    bar.add_tab(inst_id=1, module="bars")
    first_dummy = bar._tabs[1]["dummy"]
    bar.add_tab(inst_id=1, module="wave")  # powinno być ignorowane
    assert bar._tabs[1]["dummy"] is first_dummy
    assert bar._tabs[1]["label"].startswith("Bars")


def test_add_tab_default_label_first_instance_no_suffix(bar):
    bar.add_tab(inst_id=1, module="bars")
    assert bar._tabs[1]["label"] == "Bars \u2726"


def test_add_tab_default_label_second_instance_has_numeric_suffix(bar):
    bar.add_tab(inst_id=1, module="bars")
    bar.add_tab(inst_id=2, module="bars")
    assert bar._tabs[2]["label"] == "Bars \u27262"


def test_add_tab_counts_per_module_independently(bar):
    bar.add_tab(inst_id=1, module="bars")
    bar.add_tab(inst_id=2, module="wave")
    bar.add_tab(inst_id=3, module="bars")
    assert bar._tabs[1]["label"] == "Bars \u2726"
    assert bar._tabs[2]["label"] == "Wave \u2726"
    assert bar._tabs[3]["label"] == "Bars \u27262"


def test_add_tab_increments_module_count_even_with_explicit_label(bar):
    """Komentarz w kodzie: licznik modułu rośnie nawet gdy label podany z
    zewnątrz — kolejny duplikat i tak dostanie kolejny numer wewnętrznie."""
    bar.add_tab(inst_id=1, module="bars", label="Custom Name")
    bar.add_tab(inst_id=2, module="bars")
    assert bar._module_counts["bars"] == 2
    assert bar._tabs[2]["label"] == "Bars \u27262"


def test_add_tab_explicit_label_is_used_verbatim(bar):
    bar.add_tab(inst_id=1, module="bars", label="My Custom Tab")
    assert bar._tabs[1]["label"] == "My Custom Tab"


def test_add_tab_refreshes_idx_map(bar):
    bar.add_tab(inst_id=42, module="bars")
    assert 42 in bar._idx_to_id.values()


def test_add_tab_select_true_shows_content(bar):
    """winfo_manager() == 'pack' znaczy, że widget jest podpięty pod pack
    geometry manager — sprawdzamy to a nie winfo_ismapped(), bo root jest
    .withdraw()-nięty w fixturze i nigdy nie domapuje dzieci na serwer X,
    niezależnie czy .pack()/.pack_forget() zostało wywołane przez kod."""
    bar.add_tab(inst_id=1, module="bars", select=True)
    assert bar._tabs[1]["content"].winfo_manager() == "pack"


def test_add_tab_select_false_does_not_show_content(bar):
    bar.add_tab(inst_id=1, module="bars", select=False)
    assert bar._tabs[1]["content"].winfo_manager() == ""


# ── remove_tab — guard / cleanup ────────────────────────────────────────────

def test_remove_tab_nonexistent_id_is_noop(bar):
    bar.remove_tab(999)  # nie powinno crashować


def test_remove_tab_deletes_entry_from_tabs_dict(bar):
    bar.add_tab(inst_id=1, module="bars")
    bar.remove_tab(1)
    assert 1 not in bar._tabs


def test_remove_tab_refreshes_idx_map(bar):
    bar.add_tab(inst_id=1, module="bars")
    bar.add_tab(inst_id=2, module="wave")
    bar.remove_tab(1)
    assert 1 not in bar._idx_to_id.values()
    assert 2 in bar._idx_to_id.values()


def test_remove_tab_shows_content_of_new_active_tab(bar):
    bar.add_tab(inst_id=1, module="bars", select=True)
    bar.add_tab(inst_id=2, module="wave", select=True)
    bar.remove_tab(2)
    # Po usunięciu aktywnej zakładki (2), Notebook przełącza się na 1.
    assert bar._tabs[1]["content"].winfo_manager() == "pack"


# ── set_label ────────────────────────────────────────────────────────────────

def test_set_label_updates_existing_tab(bar):
    bar.add_tab(inst_id=1, module="bars")
    bar.set_label(1, "Renamed")
    assert bar._tabs[1]["label"] == "Renamed"


def test_set_label_nonexistent_id_is_noop(bar):
    bar.set_label(999, "Whatever")  # nie powinno crashować ani tworzyć wpisu
    assert 999 not in bar._tabs


# ── get_frame ─────────────────────────────────────────────────────────────────

def test_get_frame_returns_content_frame_for_existing_tab(bar):
    bar.add_tab(inst_id=1, module="bars")
    frame = bar.get_frame(1)
    assert frame is bar._tabs[1]["content"]


def test_get_frame_returns_none_for_nonexistent_tab(bar):
    assert bar.get_frame(999) is None


# ── active_id / notebook / content_frame properties ─────────────────────────

def test_active_id_returns_none_when_no_tabs(bar):
    assert bar.active_id is None


def test_active_id_returns_selected_inst_id(bar):
    bar.add_tab(inst_id=1, module="bars", select=True)
    bar.add_tab(inst_id=2, module="wave", select=True)
    assert bar.active_id == 2


def test_notebook_property_returns_ttk_notebook(bar):
    assert isinstance(bar.notebook, ttk.Notebook)


def test_content_frame_property_returns_ttk_frame(bar):
    assert isinstance(bar.content_frame, ttk.Frame)


# ── _refresh_idx_map ──────────────────────────────────────────────────────────

def test_refresh_idx_map_matches_notebook_order(bar):
    bar.add_tab(inst_id=10, module="bars")
    bar.add_tab(inst_id=20, module="wave")
    bar.add_tab(inst_id=30, module="circle")
    # Indeksy w Notebooku powinny odpowiadać porządkowi dodania.
    assert bar._idx_to_id[0] == 10
    assert bar._idx_to_id[1] == 20
    assert bar._idx_to_id[2] == 30


def test_refresh_idx_map_after_removal_reindexes_correctly(bar):
    bar.add_tab(inst_id=10, module="bars")
    bar.add_tab(inst_id=20, module="wave")
    bar.add_tab(inst_id=30, module="circle")
    bar.remove_tab(20)
    assert bar._idx_to_id[0] == 10
    assert bar._idx_to_id[1] == 30
    assert 20 not in bar._idx_to_id.values()


# ── _call — dispatch logiki callbacków ──────────────────────────────────────

def test_call_invokes_matching_callback(bar, captured_callbacks):
    bar._call("on_select", 7)
    assert captured_callbacks["select"] == [7]


def test_call_with_no_callback_registered_is_noop():
    """Gdy on_close=None (callback nie podany), _call nie powinno crashować."""
    root_local = tk.Tk()
    root_local.withdraw()
    try:
        b = bar_mod.InstanceTabBar(root_local)  # wszystkie callbacki None
        b._call("on_close", 1)  # nie powinno podnieść wyjątku
    finally:
        root_local.destroy()


def test_call_passes_through_multiple_args(bar, captured_callbacks):
    bar._call("on_action", 5, "rename")
    assert captured_callbacks["action"] == [(5, "rename")]


# ── _do_rename ────────────────────────────────────────────────────────────────

def test_do_rename_nonexistent_id_is_noop(bar, monkeypatch):
    called = []
    monkeypatch.setattr(bar_mod, "ask_string", lambda *a, **kw: called.append(True))
    bar._do_rename(999)
    assert called == []


def test_do_rename_updates_label_on_confirm(bar, monkeypatch, captured_callbacks):
    bar.add_tab(inst_id=1, module="bars")
    monkeypatch.setattr(bar_mod, "ask_string", lambda *a, **kw: "New Name")
    bar._do_rename(1)
    assert bar._tabs[1]["label"] == "New Name"
    assert captured_callbacks["action"] == [(1, "rename")]


def test_do_rename_strips_whitespace(bar, monkeypatch):
    bar.add_tab(inst_id=1, module="bars")
    monkeypatch.setattr(bar_mod, "ask_string", lambda *a, **kw: "  Padded  ")
    bar._do_rename(1)
    assert bar._tabs[1]["label"] == "Padded"


def test_do_rename_cancelled_dialog_returns_none_does_not_change_label(
        bar, monkeypatch, captured_callbacks):
    bar.add_tab(inst_id=1, module="bars")
    original_label = bar._tabs[1]["label"]
    monkeypatch.setattr(bar_mod, "ask_string", lambda *a, **kw: None)
    bar._do_rename(1)
    assert bar._tabs[1]["label"] == original_label
    assert captured_callbacks["action"] == []


def test_do_rename_blank_whitespace_only_does_not_change_label(
        bar, monkeypatch, captured_callbacks):
    """new_name='   ' jest truthy ale .strip() daje '' -> guard 'and
    new_name.strip()' powinien zablokować aktualizację."""
    bar.add_tab(inst_id=1, module="bars")
    original_label = bar._tabs[1]["label"]
    monkeypatch.setattr(bar_mod, "ask_string", lambda *a, **kw: "   ")
    bar._do_rename(1)
    assert bar._tabs[1]["label"] == original_label
    assert captured_callbacks["action"] == []


# ── _on_tab_changed / _show_content ─────────────────────────────────────────

def test_show_content_packs_only_target_tab(bar):
    bar.add_tab(inst_id=1, module="bars", select=False)
    bar.add_tab(inst_id=2, module="wave", select=False)
    bar._show_content(1)
    assert bar._tabs[1]["content"].winfo_manager() == "pack"
    assert bar._tabs[2]["content"].winfo_manager() == ""
    bar._show_content(2)
    assert bar._tabs[1]["content"].winfo_manager() == ""
    assert bar._tabs[2]["content"].winfo_manager() == "pack"


def test_on_tab_changed_calls_on_select_for_current_tab(
        bar, captured_callbacks):
    bar.add_tab(inst_id=1, module="bars", select=True)
    bar.add_tab(inst_id=2, module="wave", select=True)
    captured_callbacks["select"].clear()  # add_tab nie woła on_select samo
    bar._on_tab_changed()
    assert captured_callbacks["select"] == [2]


# ── _on_tab_click_force ──────────────────────────────────────────────────────

def test_on_tab_click_force_invalid_coords_does_not_crash(bar):
    """Klik poza obszarem zakładek -> tk.TclError złapany wewnętrznie."""
    class FakeEvent:
        x, y = -100, -100
    bar._on_tab_click_force(FakeEvent())  # nie powinno podnieść wyjątku
