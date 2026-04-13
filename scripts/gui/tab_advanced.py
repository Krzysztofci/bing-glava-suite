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

    # =========================================================================
    # SEKCJA: Flagi uruchamiania GLava
    # =========================================================================

    def _build_glava_flags(self, parent):
        T = self.T
        lf = tk.LabelFrame(parent,
                            text=T.get("section_glava_flags", "Parametry uruchamiania GLava"),
                            font=("Arial", 8, "bold"), padx=4, pady=4)
        lf.pack(fill="x", pady=(0, 4))

        # ── Checkboxy znanych flag ────────────────────────────────────────────
        # Odczytaj aktualne flagi z procesu lub z autostart
        current_flags = self._read_current_flags()

        # Definicja checkboxów: (flaga, klucz_i18n, fallback_label, tooltip_key, tooltip_fallback)
        flag_defs = [
            ("--desktop",
             "flag_desktop",   "--desktop",
             "flag_desktop_tip", "Wbuduj wizualizację w pulpit (wymagane do działania na tle)"),
            ("--requesting",
             "flag_requesting", "--requesting",
             "flag_requesting_tip", "Żądaj kompozycji RGBA — potrzebne dla przezroczystości"),
            ("--verbose",
             "flag_verbose",   "--verbose",
             "flag_verbose_tip", "Szczegółowe logi GLava w terminalu"),
            ("--force-mod=bars",
             "flag_force_bars",  "--force-mod=bars",
             "flag_force_bars_tip",  "Wymuś moduł bars przy starcie (nadpisuje rc.glsl)"),
        ]

        self._flag_vars = {}   # flaga → BooleanVar

        flags_frame = tk.Frame(lf)
        flags_frame.pack(fill="x", pady=(0, 4))

        for flag, i18n_key, fallback, tip_key, tip_fallback in flag_defs:
            var = tk.BooleanVar(value=(flag in current_flags))
            self._flag_vars[flag] = var
            cb = tk.Checkbutton(flags_frame,
                                text=T.get(i18n_key, fallback),
                                variable=var,
                                font=("Arial", 8))
            cb.pack(anchor="w")

        # ── Pole "surowych" flag dodatkowych ─────────────────────────────────
        tk.Label(lf, text=T.get("label_extra_flags_raw", "Dodatkowe flagi (ręcznie):"),
                 font=("Arial", 7), fg="gray50").pack(anchor="w", pady=(4, 0))

        extra_raw = self._flags_to_extra(current_flags)
        self._extra_raw_var = tk.StringVar(value=extra_raw)
        tk.Entry(lf, textvariable=self._extra_raw_var,
                 font=("Arial", 8)).pack(fill="x", pady=(2, 2))
        tk.Label(lf, text=T.get("label_flags_note", "np. --force-mod=circle --verbose"),
                 font=("Arial", 7), fg="gray50").pack(anchor="w")

        # ── Przycisk Zastosuj ─────────────────────────────────────────────────
        btn_row = tk.Frame(lf)
        btn_row.pack(fill="x", pady=(6, 0))
        tk.Button(btn_row,
                  text=T.get("btn_apply_flags", "Zastosuj i restartuj GLava"),
                  command=self._apply_flags,
                  bg="#1b5e20", fg="white", font=("Arial", 8, "bold")
                  ).pack(fill="x")

        # Zapamiętaj labelf do odświeżenia po restarcie
        self._autostart_status = tk.Label(lf, text="", font=("Arial", 7), fg="gray50")
        self._autostart_status.pack(anchor="w")

    def _read_current_flags(self):
        """Zwraca string z aktualnymi flagami — najpierw z ps, potem z autostart."""
        try:
            r = subprocess.run(["ps", "-C", "glava", "-o", "args="],
                               capture_output=True, text=True)
            m = re.search(r'glava\s+(.*)', r.stdout.strip())
            if m:
                flags = m.group(1).strip()
                if flags:
                    return flags
        except Exception:
            pass
        # Fallback: odczytaj z pliku autostart
        from .glava import AUTOSTART_FILE
        if os.path.exists(AUTOSTART_FILE):
            with open(AUTOSTART_FILE) as f:
                for line in f:
                    if line.startswith("Exec="):
                        rest = line.strip()[len("Exec="):]
                        # Usuń "glava" z początku jeśli jest
                        rest = re.sub(r'^glava\s*', '', rest).strip()
                        return rest
        return "--desktop"

    def _build_flags_string(self):
        """Składa finalny string flag z checkboxów + pola ręcznego."""
        known = [f for f, var in self._flag_vars.items() if var.get()]
        raw = self._extra_raw_var.get().strip()

        # Połącz, usuń duplikaty, zachowaj kolejność
        combined = known[:]
        if raw:
            import shlex
            for part in shlex.split(raw):
                if part not in combined:
                    combined.append(part)
        return " ".join(combined) if combined else "--desktop"

    def _flags_to_extra(self, flags_str):
        """Zwraca część flag nieobjętą checkboxami (do pola ręcznego)."""
        import shlex
        known = set(self._flag_vars.keys()) if hasattr(self, "_flag_vars") else set()
        try:
            parts = shlex.split(flags_str)
        except Exception:
            parts = flags_str.split()
        extra = [p for p in parts if p not in known]
        return " ".join(extra)

    def _apply_flags(self):
        """Zastosuj flagi: restart GLava, a po udanym starcie — podmień autostart."""
        T = self.T
        flags = self._build_flags_string()

        # Zapisz do app żeby inne części GUI mogły korzystać
        self.app.extra_flags = flags

        from .glava import glava_restart, update_autostart, glava_is_running
        import time

        def _after_restart():
            # Sprawdź czy GLava faktycznie wstała
            time.sleep(0.3)
            if glava_is_running():
                ok = update_autostart(flags)
                status = T.get("autostart_updated", "✓ Autostart zaktualizowany")
                if not ok:
                    status = T.get("autostart_update_failed", "⚠ Nie udało się zaktualizować autostartu")
            else:
                status = T.get("glava_start_failed", "⚠ GLava nie uruchomiła się — sprawdź flagi")
            self.app.root.after(0, lambda: self._autostart_status.config(text=status))
            self.app.update_status()

        glava_restart(
            self.app.active_module,
            extra_flags=flags,
            after_fn=_after_restart,
        )
        self._autostart_status.config(
            text=T.get("restarting", "Restartowanie…"))

    # =========================================================================
    # SEKCJA: Audio
    # =========================================================================

    def _build_audio(self, parent):
        T = self.T
        lf = tk.LabelFrame(parent,
                            text=T.get("section_audio", "Audio"),
                            font=("Arial", 8, "bold"), padx=4, pady=4)
        lf.pack(fill="x", pady=(0, 4))

        tk.Label(lf, text=T.get("audio_affects_all", "⚠ Wpływa na wszystkie moduły"),
                 font=("Arial", 7), fg="#bf360c").pack(anchor="w", pady=(0, 4))

        # Bufor audio
        buf_cur = self._read_request_int("setbufsize", 4096)
        buf_vals = [512, 1024, 2048, 4096, 8192, 16384] if self._expert() else [512, 1024, 2048, 4096]
        if buf_cur not in buf_vals:
            buf_cur = min(buf_vals, key=lambda x: abs(x - buf_cur))
        self._combo_row(lf,
                        T.get("label_bufsize", "Bufor audio"),
                        "setbufsize", buf_vals, buf_cur,
                        T.get("tooltip_bufsize",
                              "Rozmiar bufora FFT — potęga 2\n"
                              "Większy = więcej 'grawitacji'\n512=szybki, 4096=ciężki"))

        # Rozmiar próbki
        smp_cur = self._read_request_int("setsamplesize", 1024)
        smp_vals = [256, 512, 1024, 2048, 4096] if self._expert() else [256, 512, 1024, 2048]
        smp_vals = [v for v in smp_vals if v <= buf_cur] or [min(smp_vals)]
        if smp_cur not in smp_vals:
            smp_cur = min(smp_vals, key=lambda x: abs(x - smp_cur))
        self._combo_row(lf,
                        T.get("label_samplesize", "Rozmiar próbki"),
                        "setsamplesize", smp_vals, smp_cur,
                        T.get("tooltip_samplesize",
                              "256=172UPS 512=86UPS 1024=43UPS 2048=21UPS\nZawsze <= bufor audio"))

        # Częstotliwość próbkowania
        rate_cur = self._read_request_int("setsamplerate", 22050)
        rate_vals = [8000, 11025, 16000, 22050, 44100, 48000] if self._expert() else [22050, 44100]
        if rate_cur not in rate_vals:
            rate_cur = min(rate_vals, key=lambda x: abs(x - rate_cur))
        self._combo_row(lf,
                        T.get("label_samplerate", "Częst. próbkowania"),
                        "setsamplerate", rate_vals, rate_cur,
                        T.get("tooltip_samplerate",
                              "Częstotliwość próbkowania audio\n"
                              "22050 Hz = standardowa\n44100 Hz = wysoka jakość"))

        # Limit FPS — suwak
        fps_cur = self._read_request_int("setframerate", 0)
        self._fps_var = tk.IntVar(value=fps_cur)
        fps_entry = tk.StringVar(value=str(fps_cur))
        fps_row = tk.Frame(lf)
        fps_row.pack(fill="x", pady=2)
        tk.Label(fps_row,
                 text=T.get("label_fps_limit", "Limit FPS"),
                 font=("Arial", 8), width=16, anchor="w").pack(side="left")
        tk.Scale(fps_row, variable=self._fps_var, from_=0, to=240,
                 orient="horizontal", showvalue=False, sliderlength=12,
                 command=lambda v: (
                     fps_entry.set(str(int(float(v)))),
                     self._debounce_request("setframerate", int(float(v)))
                 )).pack(side="left", fill="x", expand=True, padx=(3, 0))
        fps_e = tk.Entry(fps_row, textvariable=fps_entry,
                         width=4, font=("Arial", 8), justify="right")
        fps_e.pack(side="left", padx=(3, 0))
        tk.Label(fps_row, text=T.get("label_fps_unit", "fps"),
                 font=("Arial", 8), fg="gray50", width=3).pack(side="left")

        def on_fps(event):
            try:
                v = max(0, min(240, int(fps_entry.get())))
                self._fps_var.set(v)
                fps_entry.set(str(v))
                self._debounce_request("setframerate", v)
            except ValueError:
                fps_entry.set(str(self._fps_var.get()))
        fps_e.bind("<Return>",   on_fps)
        fps_e.bind("<FocusOut>", on_fps)

        # Checkboxy bool
        bool_params = [
            ("setmirror",
             T.get("label_mirror", "Lustro L/R (mono)"),
             T.get("tooltip_mirror",
                   "Uśrednia lewy i prawy kanał\nPrzy włączonym INVERT nie działa")),
            ("setinterpolate",
             T.get("label_interpolate", "Interpolacja ramek"),
             T.get("tooltip_interpolate",
                   "Wygładza animację między klatkami audio\n"
                   "Poprawia płynność ale dodaje minimalne opóźnienie")),
        ]
        for key, label, tooltip in bool_params:
            val = self._read_request_bool(key)
            var = tk.BooleanVar(value=val)
            setattr(self, f"_{key}_var", var)
            brow = tk.Frame(lf)
            brow.pack(fill="x", pady=1)
            tk.Checkbutton(brow, text=label, variable=var,
                           font=("Arial", 8),
                           command=lambda k=key, v=var: self._write_bool_rc(k, v)
                           ).pack(side="left")

    # =========================================================================
    # SEKCJA: Rendering / kompozytor
    # =========================================================================

    def _build_rendering(self, parent):
        T = self.T
        lf = tk.LabelFrame(
            parent,
            text=T.get("section_rendering", "Rendering / kompozytor"),
            font=("Arial", 8, "bold"), padx=4, pady=4
        )
        lf.pack(fill="x", pady=(0, 4))

        tk.Label(lf,
                 text=T.get("label_rendering_warn",
                             "⚠ Ustawienia zależne od środowiska.\n"
                             "Mogą nie działać na każdej konfiguracji."),
                 font=("Arial", 7), fg="#bf360c", justify="left").pack(anchor="w", pady=(0, 6))

        # Tryb renderowania — auto / software / hardware
        # auto     → brak nadpisania env
        # software → LIBGL_ALWAYS_SOFTWARE=1
        # hardware → LIBGL_ALWAYS_SOFTWARE=0 (jawne wymuszenie)
        render_cur = getattr(self.app, "_render_mode", "auto")
        row = tk.Frame(lf)
        row.pack(fill="x", pady=(0, 4))
        tk.Label(row, text=T.get("label_render_mode", "Tryb:"),
                 font=("Arial", 8)).pack(side="left")
        self.render_var = tk.StringVar(value=render_cur)
        ttk.Combobox(row, textvariable=self.render_var,
                     values=["auto", "software", "hardware"],
                     width=9, state="readonly",
                     font=("Arial", 8)).pack(side="left", padx=(4, 0))
        tk.Label(row, text=T.get("label_render_note", "(aktywne po restarcie GLava)"),
                 font=("Arial", 7), fg="gray50").pack(side="left", padx=(6, 0))

        # Przezroczystość — #request setopacity w rc.glsl
        opacity_cur = self._read_request_float("setopacity", 1.0)
        alpha_val = int(round(opacity_cur * 100))
        self._alpha_var = tk.IntVar(value=alpha_val)
        self._alpha_entry = tk.StringVar(value=str(alpha_val))

        alpha_row = tk.Frame(lf)
        alpha_row.pack(fill="x", pady=(0, 2))
        tk.Label(alpha_row, text=T.get("label_alpha", "Przeźroczystość:"),
                 font=("Arial", 8), width=14, anchor="w").pack(side="left")
        tk.Scale(alpha_row, variable=self._alpha_var,
                 from_=0, to=100, orient="horizontal",
                 showvalue=False, sliderlength=12,
                 command=self._on_alpha_scale
                 ).pack(side="left", fill="x", expand=True, padx=(3, 0))
        alpha_e = tk.Entry(alpha_row, textvariable=self._alpha_entry,
                           width=4, font=("Arial", 8), justify="right")
        alpha_e.pack(side="left", padx=(3, 0))
        tk.Label(alpha_row, text="%",
                 font=("Arial", 8), fg="gray50", width=2).pack(side="left")

        def on_alpha_entry(event):
            try:
                v = max(0, min(100, int(self._alpha_entry.get())))
                self._alpha_var.set(v)
                self._alpha_entry.set(str(v))
                self._apply_opacity(v)
            except ValueError:
                self._alpha_entry.set(str(self._alpha_var.get()))
        alpha_e.bind("<Return>",   on_alpha_entry)
        alpha_e.bind("<FocusOut>", on_alpha_entry)

        # Przycisk Zastosuj rendering
        tk.Button(lf,
                  text=T.get("btn_apply_rendering", "Zastosuj rendering i restartuj"),
                  command=self._apply_rendering,
                  bg="#1a237e", fg="white", font=("Arial", 8)
                  ).pack(fill="x", pady=(6, 0))

    def _on_alpha_scale(self, val):
        v = int(float(val))
        self._alpha_entry.set(str(v))
        self._debounce_opacity(v)

    def _debounce_opacity(self, value):
        if hasattr(self, "_opacity_job"):
            try:
                self.app.root.after_cancel(self._opacity_job)
            except Exception:
                pass
        self._opacity_job = self.app.root.after(
            400, lambda: self._apply_opacity(value))

    def _apply_opacity(self, percent):
        """Zapisuje #request setopacity do rc.glsl (wartość 0.0–1.0)."""
        val = round(percent / 100.0, 2)
        self._write_request("setopacity", val)

    def _apply_rendering(self):
        """Restart GLava z wybranym trybem renderowania i opacity."""
        T = self.T
        mode = self.render_var.get()
        self.app._render_mode = mode

        env = None
        if mode == "software":
            env = {"LIBGL_ALWAYS_SOFTWARE": "1"}
        elif mode == "hardware":
            env = {"LIBGL_ALWAYS_SOFTWARE": "0"}

        # Zapisz opacity od razu przed restartem
        self._apply_opacity(self._alpha_var.get())

        flags = getattr(self.app, "extra_flags", "--desktop")

        from .glava import glava_restart
        glava_restart(
            self.app.active_module,
            extra_flags=flags,
            env=env,
            after_fn=self.app.update_status,
        )

    # =========================================================================
    # SEKCJA: Diagnostyka
    # =========================================================================

    def _build_diagnostics(self, parent):
        T = self.T
        lf = tk.LabelFrame(parent,
                            text=T.get("section_diagnostics", "Diagnostyka"),
                            font=("Arial", 8, "bold"), padx=4, pady=4)
        lf.pack(fill="x", pady=(0, 0))

        tk.Button(lf,
                  text=T.get("btn_show_logs", "Pokaż logi daemona"),
                  command=self._show_logs,
                  bg="#37474f", fg="white", font=("Arial", 8)
                  ).pack(fill="x", pady=(0, 3))

        tk.Button(lf,
                  text=T.get("btn_test_strut", "Test detekcji pasków"),
                  command=self._test_strut,
                  bg="#37474f", fg="white", font=("Arial", 8)
                  ).pack(fill="x")

    # =========================================================================
    # Helpery rc.glsl
    # =========================================================================

    def _expert(self):
        return hasattr(self.app, "expert_mode") and self.app.expert_mode.get()

    def _combo_row(self, parent, label, key, values, current, tooltip):
        row = tk.Frame(parent)
        row.pack(fill="x", pady=2)
        tk.Label(row, text=label, font=("Arial", 8),
                 width=16, anchor="w").pack(side="left")
        var = tk.StringVar(value=str(current))
        cb = ttk.Combobox(row, textvariable=var,
                          values=[str(v) for v in values],
                          width=7, state="readonly", font=("Arial", 8))
        cb.pack(side="left", padx=(3, 0))
        cb.bind("<<ComboboxSelected>>",
                lambda e, k=key, v=var: self._debounce_request(k, int(v.get())))
        return cb

    def _read_request_bool(self, key):
        if not os.path.exists(RC_GLSL):
            return False
        with open(RC_GLSL) as f:
            src = f.read()
        m = re.search(rf'^#request\s+{key}\s+(\S+)', src, re.MULTILINE)
        if m:
            return m.group(1).lower() == "true"
        return False

    def _read_request_int(self, key, default):
        if not os.path.exists(RC_GLSL):
            return default
        with open(RC_GLSL) as f:
            src = f.read()
        m = re.search(rf'^#request\s+{key}\s+(\d+)', src, re.MULTILINE)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                pass
        return default

    def _read_request_float(self, key, default):
        if not os.path.exists(RC_GLSL):
            return default
        with open(RC_GLSL) as f:
            src = f.read()
        m = re.search(rf'^#request\s+{key}\s+([0-9.]+)', src, re.MULTILINE)
        if m:
            try:
                return float(m.group(1))
            except Exception:
                pass
        return default

    def _write_request(self, key, val):
        if not os.path.exists(RC_GLSL):
            return
        with open(RC_GLSL) as f:
            src = f.read()
        # Jeśli klucz nie istnieje, dopisz go na końcu sekcji #request
        if re.search(rf'^#request\s+{key}\s+', src, re.MULTILINE):
            new = re.sub(rf'^(#request\s+{key}\s+)\S+', rf'\g<1>{val}',
                         src, flags=re.MULTILINE)
        else:
            new = src.rstrip() + f'\n#request {key} {val}\n'
        with open(RC_GLSL, "w") as f:
            f.write(new)

    def _debounce_request(self, key, value):
        self._write_request(key, value)
        if hasattr(self, "_rjob"):
            try:
                self.app.root.after_cancel(self._rjob)
            except Exception:
                pass
        from .glava import glava_restart
        flags = getattr(self.app, "extra_flags", "--desktop")
        self._rjob = self.app.root.after(
            500, lambda: glava_restart(
                self.app.active_module,
                extra_flags=flags,
                after_fn=self.app.update_status))

    def _write_bool_rc(self, key, var):
        val = "true" if var.get() else "false"
        self._write_request(key, val)
        if hasattr(self, "_rjob"):
            try:
                self.app.root.after_cancel(self._rjob)
            except Exception:
                pass
        from .glava import glava_restart
        flags = getattr(self.app, "extra_flags", "--desktop")
        self._rjob = self.app.root.after(
            500, lambda: glava_restart(
                self.app.active_module,
                extra_flags=flags,
                after_fn=self.app.update_status))

    # =========================================================================
    # Callbacki diagnostyczne
    # =========================================================================

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
        lines = [
            f"Ekran:          {screen_w} × {screen_h} px",
            f"Obszar roboczy: {screen_w} × {work_h} px",
            f"Pasek górny:    {top_res} px",
            f"Pasek dolny:    {bot_res} px",
            "",
            "Źródło: _NET_WM_STRUT_PARTIAL (EWMH)",
        ]
        messagebox.showinfo(
            T.get("btn_test_strut", "Test detekcji pasków"),
            "\n".join(lines)
        )
