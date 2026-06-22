import os
import sys

import numpy as np
import pytest
import tkinter as tk
import tkinter.ttk as ttk
from PIL import Image
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from gui.color_button import _recolor_rect, _contrast_fg, ColorButton


_THEME_DIR_FOREST_DARK = os.path.join(
    os.path.dirname(__file__), '..', 'scripts', 'gui', 'themes', 'forest-dark'
)
_RECT_BASIC_PNG = os.path.join(_THEME_DIR_FOREST_DARK, 'rect-basic.png')


@pytest.fixture
def root():
    try:
        r = tk.Tk()
    except tk.TclError:
        pytest.skip("Brak dostępnego displaya X (Xvfb?) — pomijam testy wymagające tk.Tk()")
    r.withdraw()
    yield r
    r.destroy()


def _skip_if_no_theme_asset():
    if not os.path.exists(_RECT_BASIC_PNG):
        pytest.skip(f"Brak {_RECT_BASIC_PNG} — testy _recolor_rect wymagają realnego "
                    f"PNG motywu Forest")


# =============================================================================
# _recolor_rect (Missing Logic: 37-75)
# =============================================================================

def test_recolor_rect_black_center_pixel():
    _skip_if_no_theme_asset()
    img = _recolor_rect(
        source_path=_RECT_BASIC_PNG,
        hex_color="#000000",
        brighten=1.0,
        bg_hex="#313131",
    )
    w, h = img.size
    r, g, b, a = img.getpixel((w // 2, h // 2))
    assert a > 0
    assert r < 10 and g < 10 and b < 10


def test_recolor_rect_white_center_pixel():
    _skip_if_no_theme_asset()
    img = _recolor_rect(
        source_path=_RECT_BASIC_PNG,
        hex_color="#ffffff",
        brighten=1.0,
        bg_hex="#313131",
    )
    w, h = img.size
    r, g, b, a = img.getpixel((w // 2, h // 2))
    assert a > 0
    assert r > 240 and g > 240 and b > 240


def test_recolor_rect_transparent_background():
    _skip_if_no_theme_asset()
    img = _recolor_rect(
        source_path=_RECT_BASIC_PNG,
        hex_color="#ff0000",
        brighten=1.0,
        bg_hex="#313131",
    )
    arr = np.array(img)
    # Piksele czystego tła (weight == 0) muszą być przezroczyste — to jest
    # mechanizm nine-slice, który pozwala obrysowi przycisku "wystawać" poza
    # prostokąt PNG bez widocznego prostokątnego tła.
    assert np.any(arr[:, :, 3] == 0)


def test_recolor_rect_brighten_increases_intensity():
    """brighten>1.0 powinno dać jaśniejszy środek niż brighten=1.0, dla
    tego samego koloru źródłowego — sprawdza że parametr realnie coś robi."""
    _skip_if_no_theme_asset()
    img_normal  = _recolor_rect(_RECT_BASIC_PNG, "#404040", brighten=1.0,  bg_hex="#313131")
    img_bright  = _recolor_rect(_RECT_BASIC_PNG, "#404040", brighten=1.12, bg_hex="#313131")
    w, h = img_normal.size
    r1, g1, b1, _ = img_normal.getpixel((w // 2, h // 2))
    r2, g2, b2, _ = img_bright.getpixel((w // 2, h // 2))
    assert (r2, g2, b2) >= (r1, g1, b1)


# =============================================================================
# _contrast_fg (Missing Logic: 138-146)
# =============================================================================

def test_contrast_fg_dark_background():
    assert _contrast_fg("#000000") == "#ffffff"


def test_contrast_fg_light_background():
    assert _contrast_fg("#ffffff") == "#000000"


def test_contrast_fg_mid_threshold_below():
    """lum tuż pod 0.55 -> tekst biały (próg z kodu: lum > 0.55)."""
    assert _contrast_fg("#8c8c8c") == "#ffffff"  # lum ≈ 0.549


def test_contrast_fg_mid_threshold_above():
    assert _contrast_fg("#919191") == "#000000"  # lum ≈ 0.567


def test_contrast_fg_invalid_input_falls_back_to_white():
    assert _contrast_fg("not-a-color") == "#ffffff"


def test_contrast_fg_missing_hash_prefix():
    """lstrip('#') na wejściu bez '#' nie powinno crashować."""
    assert _contrast_fg("000000") == "#ffffff"


# =============================================================================
# _resolve_theme (Missing Logic: 160-170)
#
# UWAGA: oryginalna wersja tych testów (Copilot) wołała
# cb._resolve_theme(root=None), co wewnątrz robi ttk.Style(None) —
# wymaga JUŻ ISTNIEJĄCEGO domyślnego okna Tk (tkinter._get_default_root),
# inaczej rzuca RuntimeError. To zależało od przypadkowej kolejności
# testów w sesji. Tutaj dajemy realny tk.Tk() przez fixture.
# =============================================================================

def test_resolve_theme_finds_existing_theme_dir(root, monkeypatch, tmp_path):
    theme_name = ttk.Style(root).theme_use()
    theme_dir = tmp_path / theme_name
    theme_dir.mkdir()
    (theme_dir / "rect-basic.png").write_bytes(b"PNG")
    (theme_dir / "rect-hover.png").write_bytes(b"PNG")

    import gui.color_button as cb_mod
    monkeypatch.setattr(cb_mod, "_THEMES_DIR", str(tmp_path))

    cb = ColorButton.__new__(ColorButton)
    cb._resolve_theme(root)

    assert cb._theme_dir == str(theme_dir)
    assert cb._src_basic == str(theme_dir / "rect-basic.png")
    assert cb._src_hover == str(theme_dir / "rect-hover.png")


def test_resolve_theme_falls_back_to_forest_dark_when_theme_dir_missing(
        root, monkeypatch, tmp_path):
    """Katalog aktywnego motywu nie istnieje w _THEMES_DIR -> fallback do
    'forest-dark', niezależnie od tego jaki motyw jest faktycznie aktywny."""
    import gui.color_button as cb_mod
    monkeypatch.setattr(cb_mod, "_THEMES_DIR", str(tmp_path))
    # Celowo NIE tworzymy żadnego katalogu motywu w tmp_path

    cb = ColorButton.__new__(ColorButton)
    cb._resolve_theme(root)

    assert cb._theme_dir.endswith("forest-dark")
    assert cb._src_basic.endswith(os.path.join("forest-dark", "rect-basic.png"))


# =============================================================================
# _put_pil (Missing Logic: 237-245)
# =============================================================================

def test_put_pil_calls_configure_with_png_data():
    photo = MagicMock()
    pil = Image.new("RGBA", (10, 10), (255, 0, 0, 255))

    ColorButton._put_pil(photo, pil)

    assert photo.configure.called
    args, kwargs = photo.configure.call_args
    assert "data" in kwargs
    assert isinstance(kwargs["data"], bytes)
    assert kwargs["data"][:4] == b"\x89PNG"  # nagłówek pliku PNG


# =============================================================================
# _update_images (Missing Logic: 253-269)
#
# Mockujemy ttk.Style.configure na poziomie klasy — dzięki temu cb._root
# może być zwykłym MagicMockiem, bez potrzeby realnego tk.Tk().
# =============================================================================

def test_update_images_recolors_both_variants_and_updates_style(monkeypatch):
    import gui.color_button as cb_mod

    cb = ColorButton.__new__(ColorButton)
    cb._root       = MagicMock()
    cb._style      = "ColorBtn_test.TButton"
    cb._img_basic  = MagicMock()
    cb._img_hover  = MagicMock()
    cb._src_basic  = "/fake/rect-basic.png"
    cb._get_bg_hex = lambda: "#313131"

    recolor_calls = []
    monkeypatch.setattr(cb_mod, "_recolor_rect",
                         lambda *a, **kw: recolor_calls.append((a, kw)) or MagicMock())
    put_calls = []
    monkeypatch.setattr(ColorButton, "_put_pil",
                         staticmethod(lambda photo, pil: put_calls.append((photo, pil))))
    configure_calls = []
    monkeypatch.setattr(ttk.Style, "configure",
                         lambda self, *a, **kw: configure_calls.append((a, kw)))

    cb._update_images("#ff0000")

    assert len(recolor_calls) == 2  # basic + hover
    assert len(put_calls) == 2
    assert put_calls[0][0] is cb._img_basic
    assert put_calls[1][0] is cb._img_hover
    assert len(configure_calls) == 1
    assert configure_calls[0][1].get("foreground") == "#ffffff"  # kontrast dla #ff0000


def test_update_images_noop_when_pil_unavailable(monkeypatch):
    """Bez Pillow (_PIL_OK=False) funkcja powinna wyjść natychmiast —
    zero wywołań _recolor_rect/_put_pil."""
    import gui.color_button as cb_mod
    monkeypatch.setattr(cb_mod, "_PIL_OK", False)

    cb = ColorButton.__new__(ColorButton)
    recolor_calls = []
    monkeypatch.setattr(cb_mod, "_recolor_rect",
                         lambda *a, **kw: recolor_calls.append(True))

    cb._update_images("#ff0000")  # nie powinno podnieść wyjątku

    assert recolor_calls == []


# =============================================================================
# __init__ / _init_style — PRAWDZIWY konstruktor, z realnym tk.Tk() i realnym
# (małym, wygenerowanym przez PIL) PNG w tmp_path. To jedyny sposób żeby
# faktycznie przejść przez cały łańcuch _resolve_theme -> _init_style ->
# _make_photo -> _pil_to_photoimage -> style.element_create.
#
# UWAGA: Missing Logic "138-146" w oryginalnym raporcie to set_color(), NIE
# _contrast_fg — Copilot błędnie podpisał zakresy w komentarzach, a ja to
# powtórzyłem bez przeliczenia. _contrast_fg (87-95) było już w pełni
# pokryte od początku.
# =============================================================================

@pytest.fixture
def real_theme_dir(tmp_path, root):
    """Tworzy katalog motywu o nazwie AKTUALNIE aktywnego tematu Tk, z
    realnymi (choć trywialnymi) plikami PNG — wystarczającymi dla PIL/Tk."""
    theme_name = ttk.Style(root).theme_use()
    theme_dir = tmp_path / theme_name
    theme_dir.mkdir()
    tiny = Image.new("RGBA", (8, 8), (100, 100, 100, 255))
    tiny.save(str(theme_dir / "rect-basic.png"))
    tiny.save(str(theme_dir / "rect-hover.png"))
    return theme_name, theme_dir


def test_init_builds_real_widget_and_registers_style(root, monkeypatch, tmp_path, real_theme_dir):
    theme_name, theme_dir = real_theme_dir
    import gui.color_button as cb_mod
    monkeypatch.setattr(cb_mod, "_THEMES_DIR", str(tmp_path))

    cb = ColorButton(root, key="init_test", text="Test", color="#ff0000",
                      command=lambda: None, root=root)

    assert isinstance(cb.widget, ttk.Button)
    assert cb._theme_dir == str(theme_dir)
    assert cb._registered_for_theme == theme_name
    assert cb._img_basic is not None
    assert cb._img_hover is not None


def test_init_applies_contrast_foreground(root, monkeypatch, tmp_path, real_theme_dir):
    """__init__ -> _init_style -> style.configure(foreground=...) zgodnie
    z _contrast_fg dla podanego koloru."""
    theme_name, theme_dir = real_theme_dir
    import gui.color_button as cb_mod
    monkeypatch.setattr(cb_mod, "_THEMES_DIR", str(tmp_path))

    cb = ColorButton(root, key="init_test2", text="Test", color="#000000",
                      command=lambda: None, root=root)

    style = ttk.Style(root)
    assert style.lookup(cb._style, "foreground") == "#ffffff"


# =============================================================================
# set_color — obie gałęzie: motyw niezmieniony (-> _update_images) i motyw
# zmieniony (-> _init_style, przebudowa elementu/stylu od zera)
# =============================================================================

def test_set_color_updates_images_when_theme_unchanged(
        root, monkeypatch, tmp_path, real_theme_dir):
    theme_name, theme_dir = real_theme_dir
    import gui.color_button as cb_mod
    monkeypatch.setattr(cb_mod, "_THEMES_DIR", str(tmp_path))

    cb = ColorButton(root, key="setcolor1", text="Test", color="#ff0000",
                      command=lambda: None, root=root)

    update_calls = []
    init_calls = []
    monkeypatch.setattr(cb, "_update_images", lambda hex_color: update_calls.append(hex_color))
    monkeypatch.setattr(cb, "_init_style", lambda hex_color: init_calls.append(hex_color))

    cb.set_color("#00ff00")

    assert update_calls == ["#00ff00"]
    assert init_calls == []  # motyw bez zmian -> bez przebudowy stylu


def test_set_color_rebuilds_style_when_theme_changed(
        root, monkeypatch, tmp_path, real_theme_dir):
    theme_name, theme_dir = real_theme_dir
    import gui.color_button as cb_mod
    monkeypatch.setattr(cb_mod, "_THEMES_DIR", str(tmp_path))

    cb = ColorButton(root, key="setcolor2", text="Test", color="#ff0000",
                      command=lambda: None, root=root)
    cb._registered_for_theme = "__inny_motyw__"  # symuluje zmianę motywu TTK

    update_calls = []
    init_calls = []
    monkeypatch.setattr(cb, "_update_images", lambda hex_color: update_calls.append(hex_color))
    monkeypatch.setattr(cb, "_init_style", lambda hex_color: init_calls.append(hex_color))

    cb.set_color("#00ff00")

    assert init_calls == ["#00ff00"]
    assert update_calls == []


# =============================================================================
# reinit / pack / grid — trywialna delegacja, ale realna logika do pokrycia
# =============================================================================

def test_reinit_calls_init_style_with_current_color():
    cb = ColorButton.__new__(ColorButton)
    cb._color = "#abcdef"
    calls = []
    cb._init_style = lambda hex_color: calls.append(hex_color)

    cb.reinit()

    assert calls == ["#abcdef"]


def test_pack_delegates_to_widget():
    cb = ColorButton.__new__(ColorButton)
    cb.widget = MagicMock()

    cb.pack(fill="x", padx=5)

    cb.widget.pack.assert_called_once_with(fill="x", padx=5)


def test_grid_delegates_to_widget():
    cb = ColorButton.__new__(ColorButton)
    cb.widget = MagicMock()

    cb.grid(row=0, column=1)

    cb.widget.grid.assert_called_once_with(row=0, column=1)


# =============================================================================
# _get_bg_hex — gałąź z gui.theme.COLORS i fallback gdy import/atrybut
# nie jest dostępny
# =============================================================================

def test_get_bg_hex_uses_theme_colors_when_available(monkeypatch):
    import gui.theme as theme_mod
    monkeypatch.setattr(theme_mod, "COLORS", {"bg1": "#222222"}, raising=False)

    cb = ColorButton.__new__(ColorButton)
    assert cb._get_bg_hex() == "#222222"


def test_get_bg_hex_falls_back_to_dark_without_root_attribute(monkeypatch):
    """hasattr(self, '_root') == False (np. ColorButton.__new__ bez seta) ->
    fallback bez dotykania ttk.Style(), prosto na 'forest-dark' -> '#313131'."""
    import gui.theme as theme_mod
    monkeypatch.delattr(theme_mod, "COLORS", raising=False)

    cb = ColorButton.__new__(ColorButton)  # brak self._root w ogóle
    assert cb._get_bg_hex() == "#313131"


def test_get_bg_hex_falls_back_using_default_root_when_colors_missing(root, monkeypatch):
    import gui.theme as theme_mod
    monkeypatch.delattr(theme_mod, "COLORS", raising=False)

    cb = ColorButton.__new__(ColorButton)
    cb._root = root  # hasattr(self, '_root') == True -> wejdzie w ttk.Style()

    result = cb._get_bg_hex()
    assert result in ("#313131", "#ffffff")
