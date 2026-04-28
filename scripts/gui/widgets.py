# =============================================================================
# gui/widgets.py
# AccelSlider — wrapper wokół ttk.Scale z Forest-ttk-theme.
# =============================================================================
import tkinter as tk
from tkinter import ttk
import math
import os
from .theme import COLORS

_THEMES_DIR = os.path.join(os.path.dirname(__file__), "themes")


def _ensure_shift_style(root):
    """Tworzy styl Shift.Horizontal.TScale z hover-thumbem. Wywołaj po apply_theme()."""
    style = ttk.Style(root)
    theme = style.theme_use()
    theme_dir = os.path.join(_THEMES_DIR, theme)

    # Nie twórz drugi raz dla tego samego motywu
    key = f"_shift_style_created_{theme}"
    if getattr(root, key, False):
        return
    setattr(root, key, True)

    hover_png  = os.path.join(theme_dir, "thumb-hor-hover.png")
    accent_png = os.path.join(theme_dir, "thumb-hor-accent.png")
    png_path   = hover_png if os.path.exists(hover_png) else accent_png

    try:
        img = tk.PhotoImage(file=png_path, master=root)
        if not hasattr(root, "_shift_thumb_imgs"):
            root._shift_thumb_imgs = []
        root._shift_thumb_imgs.append(img)

        style.element_create("ShiftThumb.slider", "image", img,
                              ("pressed", img), ("disabled", img))
        style.layout("Shift.Horizontal.TScale", [
            ("Horizontal.Scale.trough", {
                "sticky": "ew",
                "children": [("ShiftThumb.slider", {"side": "left", "sticky": ""})]
            })
        ])
        style.configure("Shift.Horizontal.TScale")
    except Exception:
        # Fallback — identyczny jak bazowy
        style.configure("Shift.Horizontal.TScale")


class AccelSlider(ttk.Frame):
    """
    Suwak z przyspieszeniem kwadratowym i trybem precyzji (Shift).

    Wygląd pochodzi w całości z ttk.Scale Forest-ttk-theme.
    Shift: zmienia styl na Shift.Horizontal.TScale (hover thumb jako wyróżnik).

    Parametry:
        vmin, vmax   — zakres wartości
        value        — wartość początkowa
        step         — krok w trybie precyzji (Shift+przeciąganie)
        is_float     — True = wartości float
        decimals     — miejsca po przecinku
        on_change    — callback(value)
        accel        — wykładnik przyspieszenia (domyślnie 2.0)
        tooltip      — tekst dymku
    """

    def __init__(self, parent, vmin=0, vmax=100, value=0, step=1,
                 is_float=False, decimals=2, on_change=None,
                 accel=2.0, tooltip=None, **kwargs):
        super().__init__(parent, **kwargs)

        self.vmin      = float(vmin)
        self.vmax      = float(vmax)
        self._value    = float(value)
        self.step      = float(step)
        self.is_float  = is_float
        self.decimals  = decimals
        self.on_change = on_change
        self.accel     = accel
        self._shift    = False
        self._drag_x   = None
        self._drag_v   = None
        self._dragging = False

        # ttk.Scale: zakres 0..1 (mapujemy sami)
        self._scale_var = tk.DoubleVar(value=self._to_norm(float(value)))

        self._scale = ttk.Scale(
            self,
            orient="horizontal",
            from_=0.0,
            to=1.0,
            variable=self._scale_var,
            style="Horizontal.TScale",
            command=self._on_scale_cmd,
        )
        self._scale.pack(side="left", fill="x", expand=True)

        self._entry_var = tk.StringVar()
        self._entry = ttk.Entry(self, textvariable=self._entry_var,
                                width=7, justify="right")
        self._entry.pack(side="right", padx=(4, 0))

        # Drag z przyspieszeniem — nadpisuje domyślny ruch Scale
        self._scale.bind("<ButtonPress-1>",   self._on_press)
        self._scale.bind("<B1-Motion>",        self._on_drag)
        self._scale.bind("<ButtonRelease-1>", self._on_release)

        # Shift przez okno
        self.after(100, self._bind_shift_to_root)

        self._entry.bind("<Return>",   self._on_entry)
        self._entry.bind("<FocusOut>", self._on_entry)

        tip = tooltip + "\nShift = tryb precyzji" if tooltip else "Shift = tryb precyzji"
        self._setup_tooltip(tip)

        self.set(value)

    # ── Normalizacja ──────────────────────────────────────────────────────────

    def _to_norm(self, v):
        if self.vmax == self.vmin:
            return 0.0
        return max(0.0, min(1.0, (v - self.vmin) / (self.vmax - self.vmin)))

    def _from_norm(self, t):
        return self.vmin + t * (self.vmax - self.vmin)

    # ── Publiczne API ─────────────────────────────────────────────────────────

    def get(self):
        return self._value

    def set(self, value):
        self._value = self._clamp(float(value))
        self._scale_var.set(self._to_norm(self._value))
        self._update_entry()

    def set_range(self, vmin, vmax):
        self.vmin = float(vmin)
        self.vmax = float(vmax)
        self._value = self._clamp(self._value)
        self._scale_var.set(self._to_norm(self._value))
        self._update_entry()

    # ── Scale callback (kliknięcie bez drag) ──────────────────────────────────

    def _on_scale_cmd(self, val):
        if self._dragging:
            return
        self._value = self._clamp(self._from_norm(float(val)))
        self._update_entry()
        if self.on_change:
            self.on_change(self._value)

    # ── Drag z przyspieszeniem ────────────────────────────────────────────────

    def _on_press(self, e):
        self._scale.focus_set()
        self._drag_x = e.x
        self._drag_v = self._value
        self._dragging = False

    def _on_drag(self, e):
        if self._drag_x is None:
            return
        dx = e.x - self._drag_x
        if abs(dx) > 2:
            self._dragging = True
        if not self._dragging:
            return

        w = max(self._scale.winfo_width(), 1)

        if self._shift:
            new_val = self._drag_v + dx * self.step
        else:
            t = dx / w
            t_acc = math.copysign(abs(t) ** self.accel, t)
            new_val = self._drag_v + t_acc * (self.vmax - self.vmin)

        self._value = self._clamp(new_val)
        self._scale_var.set(self._to_norm(self._value))
        self._update_entry()
        if self.on_change:
            self.on_change(self._value)

    def _on_release(self, e):
        self._drag_x = None
        self._drag_v = None
        self._dragging = False

    # ── Shift ─────────────────────────────────────────────────────────────────

    def _bind_shift_to_root(self):
        try:
            root = self.winfo_toplevel()
            if root:
                root.bind("<KeyPress-Shift_L>",   self._shift_root_on,  add="+")
                root.bind("<KeyPress-Shift_R>",   self._shift_root_on,  add="+")
                root.bind("<KeyRelease-Shift_L>", self._shift_root_off, add="+")
                root.bind("<KeyRelease-Shift_R>", self._shift_root_off, add="+")
        except Exception:
            pass

    def _shift_root_on(self, e):
        if self.focus_get() is self._scale:
            self._set_shift(True)

    def _shift_root_off(self, e):
        if self.focus_get() is self._scale or self._shift:
            self._set_shift(False)

    def _set_shift(self, on):
        if self._shift == on:
            return
        self._shift = on
        style = "Shift.Horizontal.TScale" if on else "Horizontal.TScale"
        self._scale.configure(style=style)

    # ── Entry ─────────────────────────────────────────────────────────────────

    def _on_entry(self, e):
        try:
            v = float(self._entry_var.get())
            self.set(v)
            if self.on_change:
                self.on_change(self._value)
        except ValueError:
            self._update_entry()

    def _update_entry(self):
        self._entry_var.set(self._fmt())

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _fmt(self):
        if self.is_float:
            return f"{self._value:.{self.decimals}f}"
        return str(int(round(self._value)))

    def _clamp(self, v):
        return max(self.vmin, min(self.vmax, v))

    def _setup_tooltip(self, text):
        tip = [None]
        def show(e):
            x = self._scale.winfo_rootx() + 20
            y = self._scale.winfo_rooty() + 20
            tip[0] = tk.Toplevel(self._scale)
            tip[0].wm_overrideredirect(True)
            tip[0].wm_geometry(f"+{x}+{y}")
            tk.Label(tip[0], text=text, justify="left",
                     bg="#ffffcc", fg="#333333",
                     relief="solid", bd=1,
                     font=("TkDefaultFont", 8), padx=4, pady=2).pack()
        def hide(e):
            if tip[0]:
                tip[0].destroy()
                tip[0] = None
        self._scale.bind("<Enter>", show)
        self._scale.bind("<Leave>", hide)
