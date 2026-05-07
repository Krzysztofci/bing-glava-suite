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

        self._scale = ttk.Style() # (jeśli potrzebujesz stylu)
        self._scale = ttk.Scale(
        
            self,
            orient="horizontal",
            from_=self.vmin, # Ustawiamy realne wartości zamiast 0..1
            to=self.vmax,
            variable=self._scale_var,
            style="Horizontal.TScale",
            command=self._on_scale_cmd
        )
        self._scale.pack(side="left", fill="x", expand=True)

        self._entry_var = tk.StringVar()
        self._entry = ttk.Entry(self, textvariable=self._entry_var,
                                width=7, justify="right")
        self._entry.pack(side="right", padx=(4, 0))

        # Drag z przyspieszeniem — nadpisuje domyślny ruch Scale
        #self._scale.bind("<ButtonPress-1>",   self._on_press)
        #self._scale.bind("<B1-Motion>",        self._on_drag)
        #self._scale.bind("<ButtonRelease-1>", self._on_release)
        #self._scale.bind("<KeyPress-Shift_L>", lambda e: self._set_shift(True))
        #self._scale.bind("<KeyRelease-Shift_L>", lambda e: self._set_shift(False))
        self._scale.bind("<Button-1>", self._smart_click)

        # Shift przez okno
        self.after(100, self._bind_shift_to_root)

        self._entry.bind("<Return>",   self._on_entry)
        self._entry.bind("<FocusOut>", self._on_entry)

        self._setup_tooltip()

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
        # ZMIANA: Wysyłamy realną wartość, a nie wynik _to_norm
        self._scale_var.set(self._value) 
        self._update_entry()

    def set_range(self, vmin, vmax):
        self.vmin = float(vmin)
        self.vmax = float(vmax)
        self._value = self._clamp(self._value)
        # ZMIANA: Tutaj też realna wartość
        self._scale_var.set(self._value) 
        self._update_entry()

    # ── Scale callback (kliknięcie bez drag) ──────────────────────────────────

    def _on_scale_cmd(self, val):
        # Pobieramy surową wartość z suwaka
        v = float(val)
        
        # Wymuszamy zaokrąglenie do Twojego kroku (np. 0.001)
        # To sprawi, że nawet jeśli suwak "chce" skoczyć o 1, 
        # my natychmiast korygujemy to do wielokrotności stepu.
        if self.step > 0:
            v = round(v / self.step) * self.step
            
        # Ograniczamy do zakresu i zaokrąglamy dla floatów
        self._value = max(self.vmin, min(self.vmax, v))
        if self.is_float:
            self._value = round(self._value, self.decimals)

        # Klucz: Wymuszamy na suwaku, by wrócił na "dobrą" drogę
        self._scale_var.set(self._value)
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
            # TRYB PRECYZYJNY: Ruch myszy o całą szerokość suwaka 
            # zmienia wartość tylko o 5% zakresu (bardzo wolno)
            span = self.vmax - self.vmin
            new_val = self._drag_v + (dx / w) * (span * 0.05) 
        else:
            # TRYB NORMALNY: Liniowy 1:1
            ratio = dx / w
            new_val = self._drag_v + ratio * (self.vmax - self.vmin)

        self._value = self._clamp(new_val)
        self._scale_var.set(self._to_norm(self._value))
        self._update_entry()
        if self.on_change:
            self.on_change(self._value)

    def _on_release(self, e):
        self._drag_x = None
        self._drag_v = None
        self._dragging = False

    # ── Zakres chwytu i kroki──────────────────────────────────────────────────

    def _smart_click(self, event):
        # coords() zwraca [x, y] lewego górnego rogu uchwytu
        slider_coords = self._scale.coords()
        handle_x_left = slider_coords[0]
        
        # Przyjmujemy standardową szerokość uchwytu dla motywu (ok. 16-20px)
        # Możesz to dostosować, ale 8-10px przesunięcia zazwyczaj trafia w środek
        handle_center_x = handle_x_left + 10 
        
        click_x = event.x
        
        # Margines musi być teraz mierzony od środka
        margin = 16 
        dist = abs(click_x - handle_center_x)

        # Jeśli klik w obrębie uchwytu (środek +/- margines) — pozwól na standardowy drag
        if dist <= margin:
            return

        # Klik w tor → wymuszamy Twój krokowy ruch z bars.py
        direction = 1 if click_x > handle_center_x else -1
        new_val = self._value + (direction * self.step)

        # Clamp + zaokrąglenie (zgodnie z Twoją logiką)
        new_val = max(self.vmin, min(self.vmax, new_val))
        if self.is_float:
            new_val = round(new_val, self.decimals)
        else:
            new_val = int(round(new_val))

        self.set(new_val)

        if self.on_change:
            self.on_change(new_val)

        return "break"

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
        # Usuwamy sprawdzanie focusu - jeśli okno widzi Shift, suwak też ma go widzieć
        self._set_shift(True)

    def _shift_root_off(self, e):
        # Wyłączamy tryb precyzji po puszczeniu klawisza
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

    def _setup_tooltip(self, text=None):
        tip_window = [None]
        label_ref = [None]  # Referencja do etykiety, by zmieniać jej tekst

        def update_tip(e):
            current_val = self._fmt()
            
            if not tip_window[0]:
                tip_window[0] = tw = tk.Toplevel(self._scale)
                tw.wm_overrideredirect(True)
                tw.attributes("-topmost", True)
                
                # Używamy ttk.Label - pobierze styl domyślny programu
                label_ref[0] = ttk.Label(tw, text=str(current_val), padding=(8, 4))
                label_ref[0].pack()
            
            x = e.x_root + 15
            y = e.y_root + 15
            tip_window[0].wm_geometry(f"+{x}+{y}")
            
            if label_ref[0]:
                label_ref[0].config(text=str(current_val))
            
            # 2. Aktualizuj pozycję (podążanie za kursorem)
            # e.x_root i e.y_root to aktualna pozycja myszy na ekranie
            x = e.x_root + 15
            y = e.y_root + 15
            tip_window[0].wm_geometry(f"+{x}+{y}")
            
            # 3. Aktualizuj wartość "na żywo"
            if label_ref[0]:
                label_ref[0].config(text=str(current_val))

        def hide(e):
            if tip_window[0]:
                tip_window[0].destroy()
                tip_window[0] = None
                label_ref[0] = None

        # Bindujemy pod ruch myszy, żeby dymek "żył" podczas przesuwania
        self._scale.bind("<Motion>", update_tip)
        self._scale.bind("<Leave>", hide)
