# =============================================================================
# gui/widgets.py
# Współdzielone widgety GUI — używane przez wszystkie moduły.
# =============================================================================
import tkinter as tk
import math
from .theme import COLORS


class AccelSlider(tk.Frame):
    """
    Suwak z przyspieszeniem kwadratowym i trybem precyzji (Shift).

    Shift działa tylko gdy canvas ma focus — brak globalnego bind_all.
    Kolor niebieski = tryb precyzji, zielony = normalny.

    Parametry:
        vmin, vmax   — zakres wartości
        value        — wartość początkowa
        step         — krok w trybie precyzji (Shift+przeciąganie)
        is_float     — True = wartości float
        decimals     — miejsca po przecinku
        on_change    — callback(value)
        accel        — wykładnik przyspieszenia (domyślnie 2.0)
        tooltip      — tekst dymku (bez wzmianki o Shift — dodawana auto)
        label_width  — szerokość etykiety (domyślnie 0 = brak etykiety)
    """

    COLOR_NORMAL   = "#4a7c59"
    COLOR_SHIFT    = "#1565c0"
    COLOR_TRACK    = "#d0d0d0"
    COLOR_TRACK_BD = "#aaaaaa"
    HANDLE_W       = 10   # szerokość uchwytu w px

    def __init__(self, parent, vmin=0, vmax=100, value=0, step=1,
                 is_float=False, decimals=2, on_change=None,
                 accel=2.0, tooltip=None, **kwargs):
        super().__init__(parent, **kwargs)

        self.COLOR_NORMAL   = COLORS["slider_fill"]
        self.COLOR_SHIFT    = COLORS["slider_fill_sh"]
        self.COLOR_TRACK    = COLORS["slider_track"]
        self.COLOR_TRACK_BD = COLORS["slider_border"]

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

        # Ramka focusa wokół canvasa — zamiast highlightthickness
        self._canvas_h = 14
        self._frame = tk.Frame(self, bd=0, relief="flat",
                               bg=self.COLOR_TRACK_BD,
                               highlightthickness=1,
                               highlightbackground=self.COLOR_TRACK_BD)
        self._frame.pack(side="left", fill="x", expand=True)
        self._canvas = tk.Canvas(self._frame, height=self._canvas_h,
                                 width=58,
                                 bg=self.COLOR_TRACK,
                                 highlightthickness=0,
                                 cursor="sb_h_double_arrow")
        self._canvas.pack(fill="both", expand=True)

        # Pole tekstowe — stała szerokość, zawsze widoczne
        self._entry_var = tk.StringVar()
        self._entry = tk.Entry(self, textvariable=self._entry_var,
                               width=6, font=("Arial", 9), justify="right",
                               bg=COLORS["bg2"], fg=COLORS["text"],
                               insertbackground=COLORS["text"],
                               relief="flat", bd=0,
                               highlightthickness=1,
                               highlightbackground=COLORS["border2"],
                               highlightcolor=COLORS["red"])
        self._entry.pack(side="right", padx=(3, 0))

        # Bindowania na canvas — tylko lokalne, bez bind_all
        c = self._canvas
        c.bind("<ButtonPress-1>",   self._on_press)
        c.bind("<B1-Motion>",        self._on_drag)
        c.bind("<ButtonRelease-1>", self._on_release)
        c.bind("<FocusIn>",         self._on_focus_in)
        c.bind("<FocusOut>",        self._on_focus_out)
        # Shift przez root — ale tylko gdy canvas aktywny
        c.bind("<KeyPress-Shift_L>",   self._on_shift_on)
        c.bind("<KeyPress-Shift_R>",   self._on_shift_on)
        c.bind("<KeyRelease-Shift_L>", self._on_shift_off)
        c.bind("<KeyRelease-Shift_R>", self._on_shift_off)

        # Shift przez okno rodzica — ale sprawdzamy focus
        self._root = None
        self._shift_binds = []
        self.after(100, self._bind_shift_to_root)

        self._entry.bind("<Return>",   self._on_entry)
        self._entry.bind("<FocusOut>", self._on_entry)

        # Tooltip
        tip_lines = []
        if tooltip:
            tip_lines.append(tooltip)
        tip_lines.append("Shift+przeciąganie = precyzja (krok 1)")
        self._setup_tooltip("\n".join(tip_lines))

        # Inicjalny rysunek
        self.set(value)

    def _bind_shift_to_root(self):
        """Rejestruje Shift na oknie głównym — tylko raz na widget."""
        try:
            root = self.winfo_toplevel()
            if root:
                self._root = root
                b1 = root.bind("<KeyPress-Shift_L>",
                               self._on_shift_root, add="+")
                b2 = root.bind("<KeyPress-Shift_R>",
                               self._on_shift_root, add="+")
                b3 = root.bind("<KeyRelease-Shift_L>",
                               self._on_shift_root_off, add="+")
                b4 = root.bind("<KeyRelease-Shift_R>",
                               self._on_shift_root_off, add="+")
        except Exception:
            pass

    def _on_shift_root(self, e):
        """Shift na poziomie okna — aktywuje tylko jeśli ten canvas ma focus."""
        focused = self.focus_get()
        if focused is self._canvas:
            self._on_shift_on(e)

    def _on_shift_root_off(self, e):
        focused = self.focus_get()
        if focused is self._canvas or self._shift:
            self._on_shift_off(e)

    # ── Publiczne API ─────────────────────────────────────────────────────────

    def get(self):
        return self._value

    def set(self, value):
        self._value = self._clamp(float(value))
        self._redraw()
        self._update_entry()

    def set_range(self, vmin, vmax):
        self.vmin = float(vmin)
        self.vmax = float(vmax)
        self._value = self._clamp(self._value)
        self._redraw()
        self._update_entry()

    # ── Rysowanie ─────────────────────────────────────────────────────────────

    def _redraw(self):
        c = self._canvas
        c.update_idletasks()
        w = c.winfo_width()
        if w < 2:
            w = 100
        h = self._canvas_h

        c.delete("all")

        # Tło toru
        c.create_rectangle(0, 0, w, h,
                            fill=self.COLOR_TRACK, outline="")

        # Pozycja uchwytu (liniowa)
        t = ((self._value - self.vmin) / (self.vmax - self.vmin)
             if self.vmax != self.vmin else 0.0)
        t = max(0.0, min(1.0, t))
        handle_x = int(t * (w - self.HANDLE_W))

        # Wypełnienie po lewej od uchwytu
        color = self.COLOR_SHIFT if self._shift else self.COLOR_NORMAL
        if handle_x > 0:
            c.create_rectangle(0, 0, handle_x, h,
                                fill=color, outline="")

        # Uchwyt — jaśniejszy odcień koloru wypełnienia
        handle_color = "#ef5350" if not self._shift else "#90caf9"
        c.create_rectangle(handle_x, 1, handle_x + self.HANDLE_W, h - 1,
                            fill=handle_color, outline="", width=0)

        # Wartość tekstowa — wyśrodkowana na torze
        c.create_text(w // 2, h // 2, text=self._fmt(),
                      font=("Arial", 8), fill="#333333")

    def _fmt(self):
        if self.is_float:
            return f"{self._value:.{self.decimals}f}"
        return str(int(round(self._value)))

    # ── Focus ─────────────────────────────────────────────────────────────────

    def _on_focus_in(self, e):
        self._frame.config(bg="#1565c0")

    def _on_focus_out(self, e):
        self._shift = False
        self._frame.config(bg=self.COLOR_TRACK_BD)
        self._redraw()

    # ── Przeciąganie ──────────────────────────────────────────────────────────

    def _on_press(self, e):
        self._canvas.focus_set()
        self._drag_x   = e.x
        self._drag_v   = self._value
        self._dragging = False

    def _on_drag(self, e):
        if self._drag_x is None:
            return
        dx = e.x - self._drag_x
        if abs(dx) > 2:
            self._dragging = True

        if not self._dragging:
            return

        if self._shift:
            # Tryb precyzji: krok per piksel, aktualizuj punkt startowy
            delta = dx * self.step
            new_val = self._drag_v + delta
            # Nie aktualizujemy _drag_x — wartość rośnie liniowo od punktu startu
        else:
            t = dx / max(self._canvas.winfo_width(), 1)
            t_acc = math.copysign(abs(t) ** self.accel, t)
            delta = t_acc * (self.vmax - self.vmin)
            new_val = self._drag_v + delta

        self.set(new_val)
        if self.on_change:
            self.on_change(self._value)

    def _on_release(self, e):
        self._drag_x   = None
        self._drag_v   = None
        self._dragging = False

    def _on_shift_on(self, e):
        if not self._shift:
            self._shift = True
            self._redraw()

    def _on_shift_off(self, e):
        if self._shift:
            self._shift = False
            self._redraw()

    # ── Pole tekstowe ─────────────────────────────────────────────────────────

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

    def _clamp(self, v):
        return max(self.vmin, min(self.vmax, v))

    def _setup_tooltip(self, text):
        tip = [None]
        def show(e):
            x = self._canvas.winfo_rootx() + 20
            y = self._canvas.winfo_rooty() + 20
            tip[0] = tk.Toplevel(self._canvas)
            tip[0].wm_overrideredirect(True)
            tip[0].wm_geometry(f"+{x}+{y}")
            tk.Label(tip[0], text=text, justify="left",
                     bg="#ffffcc", relief="solid", bd=1,
                     font=("Arial", 8), padx=4, pady=2).pack()
        def hide(e):
            if tip[0]:
                tip[0].destroy()
                tip[0] = None
        self._canvas.bind("<Enter>", show)
        self._canvas.bind("<Leave>", hide)
