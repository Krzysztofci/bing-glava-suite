# =============================================================================
# gui/color_button.py
#
# ColorButton — ttk.Button z dynamicznie kolorowanym tłem PNG (nine-slice).
#
# Mechanizm:
#   - Kopiuje rect-basic.png / rect-hover.png z motywu Forest
#   - Przekolorowuje piksele proporcjonalnie zachowując strukturę nine-slice
#   - Rejestruje nowy element TTK przez style.element_create("image", ...)
#   - Tworzy nowy styl ColorBtn_<key>.TButton i podpina element
#   - Przy każdej zmianie koloru podmienia PhotoImage in-place (put())
#
# Wymaga: Pillow (PIL)
# =============================================================================

import tkinter as tk
from tkinter import ttk
import os

try:
    from PIL import Image, ImageColor
    import numpy as np
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

_THEMES_DIR = os.path.join(os.path.dirname(__file__), "themes")


def _recolor_rect(source_path, hex_color, brighten=1.0, bg_hex="#313131"):
    """
    Przekolorowuje nine-slice rect PNG na podany kolor hex.

    Mechanizm: alpha-blending per piksel.
    Wykrywa automatycznie który koniec skali to tło a który to przycisk
    przez porównanie z podanym bg_hex — działa zarówno dla dark (jasny=btn)
    jak i light (ciemny=btn).
    """
    img = Image.open(source_path).convert("RGBA")
    a   = np.array(img, dtype=np.float32)

    bgr, bgg, bgb = ImageColor.getrgb(bg_hex)
    tr, tg, tb    = ImageColor.getrgb(hex_color)

    lum_raw   = a[:, :, 0]
    val_min   = float(lum_raw.min())
    val_max   = float(lum_raw.max())
    bg_lum    = 0.299*bgr + 0.587*bgg + 0.114*bgb  # luminancja tła

    # Ustal który koniec to tło: ten bliższy luminancji bg_hex
    dist_min = abs(val_min - bg_lum)
    dist_max = abs(val_max - bg_lum)

    if dist_min < dist_max:
        # val_min ≈ tło (forest-dark: 49≈bg 49)
        bg_val  = val_min
        btn_val = val_max
        span    = btn_val - bg_val
        weight  = np.clip((lum_raw - bg_val) / span, 0.0, 1.0) if span > 0 else np.zeros_like(lum_raw)
    else:
        # val_max ≈ tło (forest-light: 255≈bg 255)
        bg_val  = val_max
        btn_val = val_min
        span    = bg_val - btn_val
        weight  = np.clip((bg_val - lum_raw) / span, 0.0, 1.0) if span > 0 else np.zeros_like(lum_raw)

    bright = float(brighten)
    a[:, :, 0] = np.clip(bgr * (1 - weight) + tr * bright * weight, 0, 255)
    a[:, :, 1] = np.clip(bgg * (1 - weight) + tg * bright * weight, 0, 255)
    a[:, :, 2] = np.clip(bgb * (1 - weight) + tb * bright * weight, 0, 255)

    # Piksele czystego tła → przezroczyste
    a[weight == 0, 3] = 0

    return Image.fromarray(a.astype(np.uint8), "RGBA")


def _pil_to_photoimage(pil_img, master):
    """Konwertuje PIL Image → tk.PhotoImage (przez PPM w pamięci)."""
    import io
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    buf.seek(0)
    return tk.PhotoImage(data=buf.getvalue(), master=master)


def _contrast_fg(hex_color):
    """Zwraca biały lub czarny tekst zależnie od luminancji tła."""
    try:
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        return "#000000" if lum > 0.55 else "#ffffff"
    except Exception:
        return "#ffffff"


class ColorButton:
    """
    Wrapper tworzący ttk.Button z kolorowanym tłem PNG.

    Użycie:
        cb = ColorButton(parent, key="top", text="Top",
                         color="#e53935", command=callback, root=root)
        cb.widget.pack(...)          # dostęp do ttk.Button
        cb.set_color("#1565c0")      # zmień kolor dynamicznie
    """

    # Ścieżki bazowych PNG (forest-dark) — wspólne dla wszystkich instancji
    _theme_dir  = None
    _src_basic  = None
    _src_hover  = None

    def __init__(self, parent, key, text, color, command, root):
        self._key    = key
        self._color  = color
        self._root   = root
        self._style  = f"ColorBtn_{key}.TButton"

        # Znajdź pliki PNG motywu
        self._resolve_theme(root)

        # Stwórz PhotoImage (muszą być przechowywane — GC je usuwa)
        self._img_basic = None
        self._img_hover = None

        # Zarejestruj element TTK przy pierwszym użyciu
        self._registered_for_theme = None  # nazwa motywu dla którego zarejestrowano
        self._init_style(color)

        # Utwórz widget
        self.widget = ttk.Button(parent, text=text,
                                 style=self._style,
                                 command=command)

    # ── Publiczne API ─────────────────────────────────────────────────────────

    def set_color(self, hex_color):
        """Zmień kolor przycisku dynamicznie."""
        self._color = hex_color
        # Sprawdź czy motyw się zmienił — jeśli tak, przebuduj styl
        current_theme = ttk.Style(self._root).theme_use()
        if self._registered_for_theme != current_theme:
            self._init_style(hex_color)
        else:
            self._update_images(hex_color)

    def reinit(self):
        """Wywołaj po zmianie motywu TTK żeby odtworzyć elementy stylu."""
        self._init_style(self._color)

    def pack(self, **kw):
        self.widget.pack(**kw)

    def grid(self, **kw):
        self.widget.grid(**kw)

    # ── Inicjalizacja stylu i elementu TTK ───────────────────────────────────

    def _resolve_theme(self, root):
        """Znajdź katalog motywu na podstawie aktywnego theme."""
        style = ttk.Style(root)
        theme = style.theme_use()
        theme_dir = os.path.join(_THEMES_DIR, theme)
        # Fallback do forest-dark
        if not os.path.isdir(theme_dir):
            theme_dir = os.path.join(_THEMES_DIR, "forest-dark")
        self._theme_dir = theme_dir
        self._src_basic = os.path.join(theme_dir, "rect-basic.png")
        self._src_hover = os.path.join(theme_dir, "rect-hover.png")

    def _init_style(self, hex_color):
        if not _PIL_OK:
            # Fallback bez PIL — zwykły TButton
            return

        style = ttk.Style(self._root)

        # Stwórz PhotoImage dla basic i hover
        self._img_basic = self._make_photo(hex_color, brighten=1.0)
        self._img_hover = self._make_photo(hex_color, brighten=1.12)

        elem_basic = f"ColorBtnBasic_{self._key}.button"
        elem_hover = f"ColorBtnHover_{self._key}.button"

        current_theme = style.theme_use()
        if self._registered_for_theme != current_theme:
            # Zarejestruj element dla aktywnego motywu
            # (po zmianie motywu TTK resetuje elementy — trzeba ponownie)
            self._resolve_theme(self._root)  # odśwież ścieżki PNG
            # Odśwież też obrazki pod nowy motyw
            self._img_basic = self._make_photo(hex_color, brighten=1.0)
            self._img_hover = self._make_photo(hex_color, brighten=1.12)
            try:
                style.element_create(
                    f"ColorBtn_{self._key}.button",
                    "image",
                    self._img_basic,
                    ("active", self._img_hover),
                    ("pressed", self._img_basic),
                    ("disabled", self._img_basic),
                    border=4, sticky="nsew"
                )
            except Exception:
                # Element już istnieje — podmień PhotoImage przez TCL
                # żeby stare (zniszczone) obrazki nie zostały w elementcie
                try:
                    self._root.tk.call(
                        "ttk::style", "element", "configure",
                        f"ColorBtn_{self._key}.button",
                        "-image", self._img_basic
                    )
                except Exception:
                    pass
            self._registered_for_theme = current_theme

        # Layout — używamy gotowych elementów padding i label z TButton
        # żeby wysokość była identyczna z innymi przyciskami
        style.layout(self._style, [
            (f"ColorBtn_{self._key}.button", {
                "children": [(
                    "Button.padding", {
                        "children": [(
                            "Button.label",
                            {"side": "left", "expand": True}
                        )]
                    }
                )]
            })
        ])
        fg = _contrast_fg(hex_color)
        style.configure(self._style,
                        padding=(8, 4, 8, 4),
                        anchor="center",
                        foreground=fg)

    def _get_bg_hex(self):
        """Pobiera kolor tła aktywnego motywu."""
        try:
            from .theme import COLORS, ACTIVE_THEME
            # forest-light ma bg1=#ffffff, forest-dark ma bg1=#313131
            return COLORS.get("bg1", "#313131")
        except Exception:
            theme = ttk.Style().theme_use() if hasattr(self, '_root') else "forest-dark"
            return "#ffffff" if "light" in theme else "#313131"

    def _make_photo(self, hex_color, brighten):
        """Generuje tk.PhotoImage z przekolorowanego PNG."""
        pil = _recolor_rect(self._src_basic, hex_color,
                            brighten=brighten, bg_hex=self._get_bg_hex())
        return _pil_to_photoimage(pil, self._root)

    def _update_images(self, hex_color):
        """Podmień obrazki po zmianie koloru (put() in-place)."""
        if not _PIL_OK:
            return

        bg = self._get_bg_hex()
        # Wygeneruj nowe PIL images
        pil_basic = _recolor_rect(self._src_basic, hex_color, brighten=1.0,  bg_hex=bg)
        pil_hover  = _recolor_rect(self._src_basic, hex_color, brighten=1.12, bg_hex=bg)

        # Zaktualizuj istniejące PhotoImage przez put() (szybsze niż tworzenie nowych)
        self._put_pil(self._img_basic, pil_basic)
        self._put_pil(self._img_hover, pil_hover)

        # Zaktualizuj kolor tekstu
        fg = _contrast_fg(hex_color)
        ttk.Style(self._root).configure(self._style, foreground=fg)

    @staticmethod
    def _put_pil(photo, pil_img):
        """Wgrywa dane PIL Image do istniejącego tk.PhotoImage przez put()."""
        import io
        buf = io.BytesIO()
        pil_img.save(buf, format="PNG")
        buf.seek(0)
        data = buf.getvalue()
        photo.configure(data=data)
