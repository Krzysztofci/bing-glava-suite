# gui/widgets.py
# SimpleSlider — ttk.Scale + Entry, bez Shift/drag.
# =============================================================================
import os
import tkinter as tk
from tkinter import ttk

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

class SimpleSlider(tk.Frame):
    """SimpleSlider — ttk.Scale + Entry z walidacją i set_range()."""
    def __init__(self, parent, vmin=0, vmax=100, value=0, step=1,
                 is_float=False, decimals=2, on_change=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.vmin      = float(vmin)
        self.vmax      = float(vmax)
        self._value    = float(value)
        self.step      = float(step)
        self.is_float  = is_float
        self.decimals  = decimals if is_float else 0
        self.on_change = on_change

        self._var = tk.DoubleVar(value=float(value))
        self._scale = ttk.Scale(self, orient="horizontal",
                                from_=vmin, to=vmax,
                                variable=self._var,
                                command=self._on_cmd)
        self._scale.pack(side="left", fill="x", expand=True)
        self._scale.bind("<ButtonRelease-1>", self._on_release)

        self._entry_var = tk.StringVar(value=self._fmt(float(value)))
        self._entry = ttk.Entry(self, textvariable=self._entry_var,
                                width=7, justify="right")
        self._entry.pack(side="right", padx=(4, 0))
        self._entry.bind("<Return>",   self._on_entry)
        self._entry.bind("<FocusOut>", self._on_entry)

    def _fmt(self, v):
        return f"{v:.{self.decimals}f}" if self.is_float else str(int(round(v)))

    def _on_cmd(self, v):
        fv = float(v)
        if self.step > 0:
            fv = round(round(fv / self.step) * self.step, self.decimals)
        fv = max(self.vmin, min(self.vmax, fv))
        self._value = fv
        self._var.set(fv)
        self._entry_var.set(self._fmt(fv))

    def _on_release(self, e):
        if self.on_change:
            self.on_change(self._value)
    def _on_entry(self, e):
        try:
            fv = float(self._entry_var.get())
            fv = max(self.vmin, min(self.vmax, fv))
            self._value = fv
            self._var.set(fv)
            self._entry_var.set(self._fmt(fv))
            if self.on_change:
                self.on_change(fv)
        except ValueError:
            self._entry_var.set(self._fmt(self._value))

    def get(self):
        return self._value

    def set(self, value):
        fv = max(self.vmin, min(self.vmax, float(value)))
        self._value = fv
        self._var.set(fv)
        self._entry_var.set(self._fmt(fv))

    def set_range(self, vmin, vmax):
        self.vmin = float(vmin)
        self.vmax = float(vmax)
        self._scale.configure(from_=vmin, to=vmax)
        self._value = max(self.vmin, min(self.vmax, self._value))
        self._var.set(self._value)
        self._entry_var.set(self._fmt(self._value))
