# =============================================================================
# gui/tab_advanced.py
# Zakładka Zaawansowane — ustawienia środowiskowe, diagnostyka.
# =============================================================================

import tkinter as tk
from tkinter import ttk, messagebox
import os
import re
import subprocess

from .core import BIN_DIR, RC_GLSL
from .geometry import get_screen_info, get_strut_reserved


def build_tab_advanced(parent, app):
    tab = TabAdvanced(parent, app)
    tab.build()


class TabAdvanced:
    def __init__(self, parent, app):
        self.parent = parent
        self.app    = app
        self.T      = app.T

    def build(self):
        T = self.T
        p = self.parent

        outer = tk.Frame(p, padx=6, pady=6)
        outer.pack(fill="both", expand=True)

        left  = tk.Frame(outer)
        right = tk.Frame(outer)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        right.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        outer.columnconfigure(0, weight=1, uniform="col")
        outer.columnconfigure(1, weight=1, uniform="col")
        outer.rowconfigure(0, weight=1)

        self._build_glava_flags(left)
        self._build_audio(left)
        self._build_rendering(right)
        self._build_diagnostics(right)

    def _build_audio(self, parent):
        lf = tk.LabelFrame(parent, text=self.T.get("section_audio", "Audio"),
                           font=("Arial", 8, "bold"), padx=4, pady=4)
        lf.pack(fill="x", pady=(0, 4))

        tk.Label(lf, text=self.T.get("audio_affects_all", "⚠ Wpływa na wszystkie moduły"),
                 font=("Arial", 7), fg="#bf360c").pack(anchor="w", pady=(0, 4))

        # --- 1. Zmienne stanu ---
        buf_cur = self._read_request_int("setbufsize", 4096)
        self._bufsize_var = tk.StringVar(value=str(buf_cur))

        smp_cur = self._read_request_int("setsamplesize", 1024)
        self._samplesize_var = tk.StringVar(value=str(smp_cur))
        
        rate_cur = self._read_request_int("setsamplerate", 22050)
        self._samplerate_var = tk.StringVar(value=str(rate_cur))

        # --- 2. Działająca blokada (Bezpiecznik) ---
        def on_buffer_change(*args):
            try:
                b_val = int(self._bufsize_var.get())
                # Lista wszystkich możliwych wartości
                all_smp = [256, 512, 1024, 2048, 4096, 8192, 16384] if self._expert() else [256, 512, 1024, 2048]
                valid_smp = [v for v in all_smp if v <= b_val]
                
                # Dynamiczna aktualizacja Comboboxa próbek
                if hasattr(self, "_smp_combo"):
                    self._smp_combo['values'] = [str(v) for v in valid_smp]
                
                # Jeśli wybrana próbka jest teraz "nielegalna", korygujemy ją
                if int(self._samplesize_var.get()) > b_val:
                    self._samplesize_var.set(str(b_val))
                    self._debounce_request("setsamplesize", b_val)
            except: pass

        self._bufsize_var.trace_add("write", on_buffer_change)

        # --- 3. Wywołania z Twoimi kluczami z JSONa ---
        
        # Bufor audio
        self._combo_row(lf, self.T.get("label_bufsize", "Bufor audio"), 
                        "setbufsize", [512, 1024, 2048, 4096, 8192, 16384] if self._expert() else [512, 1024, 2048, 4096], 
                        self._bufsize_var, "tooltip_bufsize")

        # Rozmiar próbki (Inicjalnie przefiltrowana lista)
        smp_start = [v for v in ([256, 512, 1024, 2048, 4096, 8192, 16384] if self._expert() else [256, 512, 1024, 2048]) if v <= buf_cur]
        self._combo_row(lf, self.T.get("label_samplesize", "Rozmiar próbki"), 
                        "setsamplesize", smp_start, self._samplesize_var, "tooltip_samplesize")

        # Częstotliwość próbkowania
        self._combo_row(lf, self.T.get("label_samplerate", "Częst. próbkowania"), 
                        "setsamplerate", [8000, 11025, 16000, 22050, 44100, 48000] if self._expert() else [22050, 44100], 
                        self._samplerate_var, "tooltip_samplerate")

        # ... reszta kodu (samplerate, fps) pozostaje bez zmian ...

        # 4. Limit FPS (klucz: label_fps_limit)
        fps_cur = self._read_request_int("setframerate", 60)
        self._fps_var = tk.IntVar(value=fps_cur)
        fps_entry = tk.StringVar(value=str(fps_cur))
        fps_row = tk.Frame(lf)
        fps_row.pack(fill="x", pady=2)
        
        tk.Label(fps_row, text=self.T.get("label_fps_limit", "Limit FPS"), font=("Arial", 8),
                 width=16, anchor="w").pack(side="left")
        _tip(fps_row, "?", self.T.get("tooltip_fps_limit", "Maksymalna liczba klatek na sekundę"))
        
        tk.Scale(fps_row, variable=self._fps_var, from_=0, to=240,
                 orient="horizontal", showvalue=False, sliderlength=12,
                 command=lambda v: (
                     fps_entry.set(str(int(float(v)))),
                     self._debounce_request("setframerate", int(float(v)))
                 )).pack(side="left", fill="x", expand=True, padx=(3, 0))
        
        fps_e = tk.Entry(fps_row, textvariable=fps_entry, width=4, font=("Arial", 8), justify="right")
        fps_e.pack(side="left", padx=(3, 0))
        
        tk.Label(fps_row, text="fps", font=("Arial", 8), fg="gray50", width=3).pack(side="left")

        def on_fps(event):
            try:
                v = max(0, min(240, int(fps_entry.get())))
                self._fps_var.set(v); fps_entry.set(str(v))
                self._debounce_request("setframerate", v)
            except ValueError:
                fps_entry.set(str(self._fps_var.get()))
        fps_e.bind("<Return>",   on_fps)
        fps_e.bind("<FocusOut>", on_fps)

        # 5. Przełączniki (Lustro, Interpolacja)
        # UWAGA: Tutaj dopasowałem klucze do Twojego JSONa: label_mirror i label_interpolate
        for key, label_key in [("setmirror", "label_mirror"), ("setinterpolate", "label_interpolate")]:
            val = self._read_request_bool(key)
            var = tk.BooleanVar(value=val)
            setattr(self, f"_{key}_var", var)

            brow = tk.Frame(lf)
            brow.pack(fill="x", pady=1)
    
            tk.Checkbutton(brow, text=self.T.get(label_key, label_key), variable=var,
                           font=("Arial", 8),
                           command=lambda k=key, v=var: self._write_bool_rc(k, v)
                           ).pack(side="left")

            tip_key = label_key.replace("label_", "tooltip_")
            t_text = self.T.get(tip_key, "")
            if t_text:
                _tip(brow, "?", t_text)

    def _expert(self):
        return hasattr(self.app, "expert_mode") and self.app.expert_mode.get()

    def _combo_row(self, parent, label, key, values, current_var, tooltip_key):
        row = tk.Frame(parent)
        row.pack(fill="x", pady=2)
        tk.Label(row, text=label, font=("Arial", 8), width=16, anchor="w").pack(side="left")
        
        # Obsługa tooltipów - pobiera tekst z Twojego JSONa
        if tooltip_key:
            t_text = self.T.get(tooltip_key, "")
            if t_text:
                try:
                    _tip(row, "?", t_text)
                except NameError: pass

        # Używamy bezpośrednio przekazanej zmiennej StringVar
        cb = ttk.Combobox(row, textvariable=current_var,
                          values=[str(v) for v in values],
                          width=7, state="readonly", font=("Arial", 8))
        cb.pack(side="left", padx=(3, 0))
        
        # Rejestrujemy referencję dla blokady próbek
        if key == "setsamplesize":
            self._smp_combo = cb
            
        cb.bind("<<ComboboxSelected>>",
                lambda e, k=key, v=current_var: self._debounce_request(k, int(v.get())))
        return cb

    def _read_request_bool(self, key):
        if not os.path.exists(RC_GLSL): return False
        with open(RC_GLSL) as f: src = f.read()
        m = re.search(rf'^#request\s+{key}\s+(\S+)', src, re.MULTILINE)
        if m: return m.group(1).lower() == "true"
        return False

    def _read_request_int(self, key, default):
        if not os.path.exists(RC_GLSL): return default
        with open(RC_GLSL) as f: src = f.read()
        m = re.search(rf'^#request\s+{key}\s+(\d+)', src, re.MULTILINE)
        if m:
            try: return int(m.group(1))
            except: pass
        return default

    def _write_request(self, key, val):
        if not os.path.exists(RC_GLSL): return
    
        with open(RC_GLSL, "r") as f: 
            lines = f.readlines()

        found = False
        new_lines = []
    
        # Przeszukujemy linia po linii (bardziej elastyczne niż re.sub na całości)
        for line in lines:
            # Szukamy linii, która ma w sobie "#request" i nasz "klucz"
            if f"#request" in line and key in line:
                # Tworzymy idealnie sformatowaną linię
                new_lines.append(f"#request {key} {val}\n")
                found = True
            else:
                new_lines.append(line)

        # Jeśli nie znaleźliśmy takiej linii w całym pliku, dopisujemy ją na końcu
        if not found:
            if new_lines and not new_lines[-1].endswith("\n"):
                new_lines.append("\n")
            new_lines.append(f"#request {key} {val}\n")

        with open(RC_GLSL, "w") as f: 
            f.writelines(new_lines)


    def _debounce_request(self, key, value):
        self._write_request(key, value)
        if hasattr(self, "_rjob"):
            try: self.app.root.after_cancel(self._rjob)
            except: pass
        from .glava import glava_restart
        self._rjob = self.app.root.after(
            500, lambda: glava_restart(
                self.app.active_module, after_fn=self.app.update_status))

    def _write_bool_rc(self, key, var):
        val = "true" if var.get() else "false"
        self._write_request(key, val)
        if hasattr(self, "_rjob"):
            try: self.app.root.after_cancel(self._rjob)
            except: pass
        from .glava import glava_restart
        self._rjob = self.app.root.after(
            500, lambda: glava_restart(
                self.app.active_module, after_fn=self.app.update_status))

    def _build_glava_flags(self, parent):
        T = self.T
        lf = tk.LabelFrame(parent,
                            text=T.get("section_glava_flags", "GLava startup parameters"),
                            font=("Arial", 8, "bold"), padx=4, pady=4)
        lf.pack(fill="x", pady=(0, 4))
        tk.Label(lf, text=T.get("label_concept_status", "⚠ Currently in concept phase"),
                 font=("Arial", 7, "italic"), fg="#d32f2f").pack(anchor="w")
        tk.Label(lf, text=T.get("label_extra_flags", "Extra flags:"),
                 font=("Arial", 8)).pack(anchor="w")
        # Wczytaj aktualną flagę z procesu GLava
        import subprocess, re
        extra = "--desktop"
        try:
            r = subprocess.run(["ps", "-C", "glava", "-o", "args="],
                               capture_output=True, text=True)
            m = re.search(r'glava\s+(.*)', r.stdout.strip())
            if m:
                extra = m.group(1).strip()
        except Exception:
            pass
        if not extra:
            extra = "--desktop"
        setattr(self.app, "extra_flags", extra)
        self.flags_var = tk.StringVar(value=extra)
        self.flags_var.trace_add("write", lambda *_: setattr(self.app, "extra_flags", self.flags_var.get()))
        tk.Entry(lf, textvariable=self.flags_var,
                 font=("Arial", 9)).pack(fill="x", pady=(2, 2))
        tk.Label(lf, text=T.get("label_flags_note", "e.g. --desktop --force-mod=bars"),
                 font=("Arial", 7), fg="gray50").pack(anchor="w")

    def _build_rendering(self, parent):
        T = self.T
        lf = tk.LabelFrame(
            parent,
            text=T.get("section_rendering", "Rendering / compositor"),
            font=("Arial", 8, "bold"), padx=4, pady=4
        )
        lf.pack(fill="x", pady=(0, 4))
        tk.Label(lf, text=T.get("label_concept_status", "⚠ Currently in concept phase"),
                 font=("Arial", 7, "italic"), fg="#d32f2f").pack(anchor="w")
        tk.Label(lf,
                 text=T.get("label_rendering_warn",
                             "⚠ Environment-dependent settings.\nMay not work on every configuration."
                             "Mogą nie działać na każdej konfiguracji."),
                 font=("Arial", 7), fg="#bf360c", justify="left").pack(anchor="w", pady=(0, 6))

        row = tk.Frame(lf)
        row.pack(fill="x", pady=(0, 4))
        tk.Label(row, text=T.get("label_render_mode", "Mode:"),
                 font=("Arial", 8)).pack(side="left")
        self.render_var = tk.StringVar(value="auto")
        ttk.Combobox(row, textvariable=self.render_var,
                     values=["auto", "software", "hardware"],
                     width=9, state="readonly",
                     font=("Arial", 8)).pack(side="left", padx=(4, 0))

        alpha_row = tk.Frame(lf)
        alpha_row.pack(fill="x")
        tk.Label(alpha_row, text=T.get("label_alpha", "Transparency:"),
                 font=("Arial", 8)).pack(side="left")
        self.alpha_var = tk.IntVar(value=100)
        tk.Scale(alpha_row, variable=self.alpha_var,
                 from_=0, to=100, orient="horizontal",
                 font=("Arial", 7), showvalue=True,
                 length=80).pack(side="left", padx=(4, 0))
        tk.Label(alpha_row, text="%",
                 font=("Arial", 8), fg="gray50").pack(side="left")

    def _build_diagnostics(self, parent):
        T = self.T
        lf = tk.LabelFrame(parent,
                            text=T.get("section_diagnostics", "Diagnostics"),
                            font=("Arial", 8, "bold"), padx=4, pady=4)
        lf.pack(fill="x", pady=(0, 0))

        tk.Button(lf,
                  text=T.get("btn_show_logs", "Show daemon logs"),
                  command=self._show_logs,
                  bg="#37474f", fg="white", font=("Arial", 8)
                  ).pack(fill="x", pady=(0, 3))

        tk.Button(lf,
                  text=T.get("btn_test_strut", "Test panel detection"),
                  command=self._test_strut,
                  bg="#37474f", fg="white", font=("Arial", 8)
                  ).pack(fill="x")

    # ── CALLBACKI ─────────────────────────────────────────────────────────────

    def _show_logs(self):
        log = os.path.join(os.path.expanduser("~"),
                           ".local/logs/glava-color-daemon.log")
        if not os.path.exists(log):
            messagebox.showinfo("", f"Brak pliku logu:\n{log}")
            return
        try:
            subprocess.Popen(["xterm", "-e", f"tail -f '{log}'"])
        except FileNotFoundError:
            try:
                subprocess.Popen(["x-terminal-emulator", "-e",
                                   f"tail -f '{log}'"])
            except Exception:
                with open(log) as f:
                    last = "".join(f.readlines()[-40:])
                messagebox.showinfo("Log (ostatnie 40 linii)", last)

    def _test_strut(self):
        T = self.T
        screen_w, screen_h, work_h, top_res, bot_res = get_screen_info()
        
        # Pobieramy etykiety z JSONa, a wartości doklejamy dynamicznie
        lines = [
            f"{T.get('label_screen', 'Ekran:')}          {screen_w} × {screen_h} px",
            f"{T.get('label_work_area', 'Obszar roboczy:')} {screen_w} × {work_h} px",
            f"{T.get('label_top_bar', 'Pasek górny:')}    {top_res} px",
            f"{T.get('label_bottom_bar', 'Pasek dolny:')}    {bot_res} px",
            "",
            f"{T.get('label_source', 'Źródło:')} _NET_WM_STRUT_PARTIAL (EWMH)",
        ]
        
        messagebox.showinfo(
            T.get("btn_test_strut", "Test panel detection"),
            "\n".join(lines)
        )

def _tip(parent, label, text):
    import tkinter as tk
    if not text: return
    lbl = tk.Label(parent, text=label, font=("Arial", 8),
                   fg="#1565c0", cursor="question_arrow",
                   relief="groove", padx=2)
    lbl.pack(side="left", padx=(2, 0))
    tip_window = [None]
    def show(e):
        x = lbl.winfo_rootx() + 20
        y = lbl.winfo_rooty() + 20
        tw = tk.Toplevel(lbl)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(tw, text=text, justify="left", bg="#ffffcc", relief="solid", bd=1,
                 font=("Arial", 8), padx=4, pady=2).pack()
        tip_window[0] = tw
    def hide(e):
        if tip_window[0]: tip_window[0].destroy(); tip_window[0] = None
    lbl.bind("<Enter>", show)
    lbl.bind("<Leave>", hide)
