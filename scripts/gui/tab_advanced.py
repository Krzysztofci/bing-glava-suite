# =============================================================================
# gui/tab_advanced.py
# Zakładka Zaawansowane — ustawienia środowiskowe, diagnostyka.
#
# Wzorzec GUI: bars.py v5 (grid w LabelFrame, ttk.*, Forest-ttk-theme)
# =============================================================================

import tkinter as tk
from tkinter import ttk, messagebox, colorchooser
import os, re, subprocess

from .core import BIN_DIR, RC_GLSL
from .geometry import get_screen_info
from .modules import glsl_io


def build_tab_advanced(parent, app):
    tab = TabAdvanced(parent, app)
    tab.build()


class TabAdvanced:
    def __init__(self, parent, app):
        self.parent = parent
        self.app    = app
        self.T      = app.T

    def build(self):
        outer = ttk.Frame(self.parent)
        outer.pack(fill="both", expand=True)

        left  = ttk.Frame(outer)
        right = ttk.Frame(outer)
        left.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)
        right.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)
        outer.columnconfigure(0, weight=1, uniform="col")
        outer.columnconfigure(1, weight=1, uniform="col")
        outer.rowconfigure(0, weight=1)

        self._build_theme(left)
        #self._build_glava_flags(left)
        self._build_audio(right)
        #self._build_rendering(right)
        self._build_diagnostics(left)
        self._build_footer(outer)

    # ── Motyw GUI ────────────────────────────────────────────────────────────────

    def _build_theme(self, parent):
        T = self.T
        lf = ttk.LabelFrame(parent, text=T.get("section_theme", "Motyw GUI"),
                            padding=(15, 10))
        lf.pack(fill="x", padx=10, pady=10)

        row = ttk.Frame(lf)
        row.pack(fill="x")
        ttk.Label(row, text=T.get("label_theme", "Motyw:"),
                  width=8, anchor="w").pack(side="left")

        THEMES = ["forest-dark", "forest-light"]
        self._theme_var = tk.StringVar(
            value=self.app.gui_conf.get("theme", "forest-dark"))
        ttk.Combobox(row, textvariable=self._theme_var,
                     values=THEMES, state="readonly",
                     width=14).pack(side="left", padx=(4, 8))
        ttk.Button(row, text=T.get("btn_apply_theme", "Apply"),
                   command=self._apply_theme,
                   style="Accent.TButton").pack(side="left")

    def _apply_theme(self):
        theme = self._theme_var.get()
        self.app.gui_conf["theme"] = theme
        # Anuluj debounced zapis i zapisz pozycję przed zniszczeniem okna
        if self.app._resize_after:
            self.app.root.after_cancel(self.app._resize_after)
            self.app._resize_after = None
        self.app._save_window_state()
        self.app._save_gui_conf()
        self.app._restart = True
        self.app.root.destroy()

    
    # ── GLava startup parameters ──────────────────────────────────────────────

    def _build_glava_flags(self, parent):
        T = self.T
        lf = ttk.LabelFrame(parent,
                            text=T.get("section_glava_flags", "GLava startup parameters"),
                            padding=(15, 10))
        lf.pack(fill="x", padx=10, pady=10)

        ttk.Label(lf, text=T.get("label_concept_status",
                                   "⚠ Currently in concept phase")).pack(anchor="w")
        ttk.Label(lf, text=T.get("label_extra_flags", "Extra flags:")).pack(anchor="w", pady=(4, 0))

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
        self.flags_var.trace_add("write",
                                  lambda *_: setattr(self.app, "extra_flags",
                                                     self.flags_var.get()))
        ttk.Entry(lf, textvariable=self.flags_var).pack(fill="x", pady=(2, 2))
        ttk.Label(lf, text=T.get("label_flags_note",
                                   "e.g. --desktop --force-mod=bars")).pack(anchor="w")

    # ── Audio ─────────────────────────────────────────────────────────────────

    def _build_audio(self, parent):
        T = self.T
        lf = ttk.LabelFrame(parent, text=T.get("section_audio", "Audio"),
                            padding=(15, 10))
        lf.pack(fill="x", padx=10, pady=10)

        ttk.Label(lf, text=T.get("audio_affects_all",
                                   "⚠ Wpływa na wszystkie moduły")).pack(anchor="w", pady=(0, 4))

        # Zmienne
        buf_cur  = self._read_request_int("setbufsize",    4096)
        smp_cur  = self._read_request_int("setsamplesize", 1024)
        rate_cur = self._read_request_int("setsamplerate", 22050)

        self._bufsize_var    = tk.StringVar(value=str(buf_cur))
        self._samplesize_var = tk.StringVar(value=str(smp_cur))
        self._samplerate_var = tk.StringVar(value=str(rate_cur))

        def on_buffer_change(*args):
            try:
                b_val = int(self._bufsize_var.get())
                all_smp = ([256, 512, 1024, 2048, 4096, 8192, 16384]
                           if self._expert() else [256, 512, 1024, 2048])
                valid = [v for v in all_smp if v <= b_val]
                if hasattr(self, "_smp_combo"):
                    self._smp_combo["values"] = [str(v) for v in valid]
                if int(self._samplesize_var.get()) > b_val:
                    self._samplesize_var.set(str(b_val))
                    self._debounce_request("setsamplesize", b_val)
            except Exception:
                pass

        self._bufsize_var.trace_add("write", on_buffer_change)

        # Combo — bufor
        self._combo_row(lf, T.get("label_bufsize", "Bufor audio"),
                        "setbufsize",
                        [512, 1024, 2048, 4096, 8192, 16384] if self._expert()
                        else [512, 1024, 2048, 4096],
                        self._bufsize_var, "tooltip_bufsize")

        # Combo — próbka
        smp_start = [v for v in
                     ([256, 512, 1024, 2048, 4096, 8192, 16384] if self._expert()
                      else [256, 512, 1024, 2048])
                     if v <= buf_cur]
        self._combo_row(lf, T.get("label_samplesize", "Rozmiar próbki"),
                        "setsamplesize", smp_start,
                        self._samplesize_var, "tooltip_samplesize")

        # Combo — częstotliwość
        self._combo_row(lf, T.get("label_samplerate", "Częst. próbkowania"),
                        "setsamplerate",
                        [8000, 11025, 16000, 22050, 44100, 48000] if self._expert()
                        else [22050, 44100],
                        self._samplerate_var, "tooltip_samplerate")

        # Limit FPS — ttk.Scale
        fps_cur  = self._read_request_int("setframerate", 0)
        self._fps_var = tk.IntVar(value=fps_cur)
        fps_entry = tk.StringVar(value=str(fps_cur))

        fps_row = ttk.Frame(lf)
        fps_row.pack(fill="x", pady=2)
        ttk.Label(fps_row, text=T.get("label_fps_limit", "Limit FPS"),
                  width=16, anchor="w").pack(side="left")
        t = glsl_io.tip(fps_row, "?", T.get("tooltip_fps_limit",
                 "Maksymalna liczba klatek na sekundę"))
        if t: t.pack(side="left", padx=(2, 0))

        ttk.Scale(fps_row, variable=self._fps_var, from_=0, to=240,
                  orient="horizontal",
                  command=lambda v: (
                      fps_entry.set(str(int(float(v)))),
                      self._debounce_request("setframerate", int(float(v)))
                  )).pack(side="left", fill="x", expand=True, padx=(3, 0))

        fps_e = ttk.Entry(fps_row, textvariable=fps_entry, width=4, justify="right")
        fps_e.pack(side="left", padx=(3, 0))
        ttk.Label(fps_row, text="fps", width=3).pack(side="left")

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

        # Przełączniki
        for key, label_key in [("setmirror",      "label_mirror"),
                                ("setinterpolate", "label_interpolate")]:
            val = self._read_request_bool(key)
            var = tk.BooleanVar(value=val)
            setattr(self, f"_{key}_var", var)

            brow = ttk.Frame(lf)
            brow.pack(fill="x", pady=1)
            ttk.Checkbutton(
                brow,
                text=T.get(label_key, label_key),
                variable=var,
                command=lambda k=key, v=var: self._write_bool_rc(k, v)
            ).pack(side="left")

            tip_key = label_key.replace("label_", "tooltip_")
            t_text = T.get(tip_key, "")
            if t_text:
                t = glsl_io.tip(brow, "?", t_text)
                if t: t.pack(side="left", padx=(2, 0))

    # ── Rendering / compositor ────────────────────────────────────────────────

    def _build_rendering(self, parent):
        T = self.T
        lf = ttk.LabelFrame(parent,
                            text=T.get("section_rendering", "Rendering / compositor"),
                            padding=(15, 10))
        lf.pack(fill="x", padx=10, pady=10)

        ttk.Label(lf, text=T.get("label_concept_status",
                                   "⚠ Currently in concept phase")).pack(anchor="w")
        ttk.Label(lf, text=T.get("label_rendering_warn",
                                   "⚠ Environment-dependent settings.\n"
                                   "May not work on every configuration."),
                  justify="left").pack(anchor="w", pady=(0, 6))

        row = ttk.Frame(lf)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=T.get("label_render_mode", "Mode:")).pack(side="left")
        self.render_var = tk.StringVar(value="auto")
        ttk.Combobox(row, textvariable=self.render_var,
                     values=["auto", "software", "hardware"],
                     width=9, state="readonly").pack(side="left", padx=(4, 0))

        alpha_row = ttk.Frame(lf)
        alpha_row.pack(fill="x", pady=2)
        ttk.Label(alpha_row, text=T.get("label_alpha", "Transparency:")).pack(side="left")
        self.alpha_var = tk.IntVar(value=100)
        ttk.Scale(alpha_row, variable=self.alpha_var,
                  from_=0, to=100, orient="horizontal").pack(
            side="left", fill="x", expand=True, padx=(4, 0))
        ttk.Label(alpha_row, text="100", width=4).pack(side="left")
        ttk.Label(alpha_row, text="%").pack(side="left")

    # ── Diagnostics ───────────────────────────────────────────────────────────

    def _build_diagnostics(self, parent):
        T = self.T
        lf = ttk.LabelFrame(parent, text=T.get("section_diagnostics", "Diagnostics"),
                            padding=(15, 10))
        lf.pack(fill="x", padx=10, pady=10)

        ttk.Button(lf, text=T.get("btn_show_logs", "Show daemon logs"),
                   command=self._show_logs,
                   style="Accent.TButton").pack(fill="x", pady=(0, 3))
        ttk.Button(lf, text=T.get("btn_test_strut", "Test panel detection"),
                   command=self._test_strut).pack(fill="x")

    def _build_footer(self, parent):
        import webbrowser
        T = self.T
        
        # Ramka dolna
        footer = ttk.Frame(parent)
        footer.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(20, 10))

        # Separator dla oddzielenia od reszty opcji
        ttk.Separator(footer, orient="horizontal").pack(fill="x", pady=(0, 15))

        # Tekst pobierany z JSONa
        promo_text = T.get("label_star_me", "Podoba Ci się to co robię? Zajrzyj na GitHub i daj mi gwiazdkę ★")
        promo_label = ttk.Label(footer, text=promo_text, font=("", 10, "bold"))
        promo_label.pack(pady=(0, 5))

        motivation_text = T.get("label_motivation", "Zmotywuje mnie to do dalszego rozwoju programu!")
        ttk.Label(footer, text=motivation_text).pack(pady=(0, 10))

        # Kontener na przyciski
        btn_box = ttk.Frame(footer)
        btn_box.pack()

        # Przycisk GitHub z Twoim zielonym stylem Accent
        github_url = "https://github.com/Krzysztofci/bing-glava-suite"
        ttk.Button(btn_box, 
                   text=T.get("btn_github", "GitHub Repository ⭐"), 
                   style="Accent.TButton",
                   command=lambda: webbrowser.open(github_url)).pack(side="left", padx=5)

        # Licencje
        ttk.Button(btn_box, 
                   text=T.get("btn_license", "License"), 
                   width=10,
                   command=lambda: self._show_license_text("LICENSE")).pack(side="left", padx=2)
        
        ttk.Button(btn_box, 
                   text=T.get("btn_3rd_party", "Third-party Licenses"),
                   command=lambda: self._show_license_text("CREDITS")).pack(side="left", padx=2)

    def _show_license_text(self, filename):
        # Proste okno z tekstem (możesz potem zamienić na czytanie z pliku)
        if filename == "LICENSE":
            msg = "\nLicensed under MIT License\n\nCopyright (c) 2026 Krzysztofci\n"
        else:
            msg = "\n- GLava (GPLv3) - Copyright (c) 2015 Karl Stavestrand <karl@stavestrand.no>\n\n- Forest-ttk-theme (MIT)- Copyright (c) 2021 rdbende\n"
        
        messagebox.showinfo(filename, msg)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _expert(self):
        return hasattr(self.app, "expert_mode") and self.app.expert_mode.get()

    def _combo_row(self, parent, label, key, values, current_var, tooltip_key):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=label, width=16, anchor="w").pack(side="left")

        if tooltip_key:
            t_text = self.T.get(tooltip_key, "")
            if t_text:
                t = glsl_io.tip(row, "?", t_text)
                if t: t.pack(side="left", padx=(2, 0))

        cb = ttk.Combobox(row, textvariable=current_var,
                          values=[str(v) for v in values],
                          width=7, state="readonly")
        cb.pack(side="left", padx=(3, 0))

        if key == "setsamplesize":
            self._smp_combo = cb

        cb.bind("<<ComboboxSelected>>",
                lambda e, k=key, v=current_var: self._debounce_request(k, int(v.get())))
        return cb

    def _rc_glsl(self):
        """Ścieżka rc.glsl aktywnej instancji."""
        if hasattr(self.app, 'get_active_rc_glsl'):
            return self.app.get_active_rc_glsl()
        return RC_GLSL

    def _read_request_bool(self, key):
        rc = self._rc_glsl()
        if not os.path.exists(rc): return False
        with open(rc) as f: src = f.read()
        m = re.search(rf'^#request\s+{key}\s+(\S+)', src, re.MULTILINE)
        if m: return m.group(1).lower() == "true"
        return False

    def _read_request_int(self, key, default):
        rc = self._rc_glsl()
        if not os.path.exists(rc): return default
        with open(rc) as f: src = f.read()
        m = re.search(rf'^#request\s+{key}\s+(\d+)', src, re.MULTILINE)
        if m:
            try: return int(m.group(1))
            except Exception: pass
        return default

    def _write_request_to(self, rc, key, val):
        """Zapisuje #request key val do podanego pliku rc.glsl."""
        if not os.path.exists(rc):
            return
        with open(rc) as f:
            lines = f.readlines()
        found = False
        new_lines = []
        for line in lines:
            if "#request" in line and key in line:
                new_lines.append(f"#request {key} {val}\n")
                found = True
            else:
                new_lines.append(line)
        if not found:
            if new_lines and not new_lines[-1].endswith("\n"):
                new_lines.append("\n")
            new_lines.append(f"#request {key} {val}\n")
        with open(rc, "w") as f:
            f.writelines(new_lines)

    def _write_request(self, key, val):
        """Zapisuje parametr do rc.glsl WSZYSTKICH instancji (audio/fps = globalne)."""
        if hasattr(self.app, 'instances'):
            for inst in self.app.instances.values():
                self._write_request_to(inst.rc_glsl, key, val)
        else:
            self._write_request_to(self._rc_glsl(), key, val)

    def _debounce_request(self, key, value):
        self._write_request(key, value)
        if hasattr(self, "_rjob"):
            try:
                self.app.root.after_cancel(self._rjob)
            except Exception:
                pass
        # Restartuj wszystkie instancje rownoleggle
        if hasattr(self.app, 'instances') and hasattr(self.app, 'processes'):
            def _restart_all():
                from .glava import glava_restart_instance
                import threading
                threads = []
                for iid, inst in self.app.instances.items():
                    mod = self.app._inst_modules.get(iid, self.app.active_module)
                    proc = self.app.processes.get(iid)
                    def _do(i=iid, ins=inst, m=mod, p=proc):
                        from .glava import glava_stop_instance, glava_start
                        import time
                        glava_stop_instance(p)
                        time.sleep(0.5)
                        new_proc = glava_start(instance=ins)
                        self.app.processes[i] = new_proc
                    t = threading.Thread(target=_do, daemon=True)
                    threads.append(t)
                for t in threads:
                    t.start()
                self.app.root.after(0, self.app.update_status)
            self._rjob = self.app.root.after(500, _restart_all)
        elif hasattr(self.app, 'restart_active_instance'):
            self._rjob = self.app.root.after(
                500, lambda: self.app.restart_active_instance(
                    after_fn=self.app.update_status))
        else:
            from .glava import glava_restart
            self._rjob = self.app.root.after(
                500, lambda: glava_restart(
                    self.app.active_module, after_fn=self.app.update_status))

    def _write_bool_rc(self, key, var):
        # _write_request juz zapisuje do wszystkich instancji
        self._debounce_request(key, "true" if var.get() else "false")

    # ── Callbacki ─────────────────────────────────────────────────────────────

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
        screen_w, screen_h, work_h, top_res, bot_res, left_res, right_res = get_screen_info()
        lines = [
            f"{T.get('label_screen',     'Ekran:')}           {screen_w} × {screen_h} px",
            f"{T.get('label_work_area',  'Obszar roboczy:')}  {screen_w} × {work_h} px",
            f"{T.get('label_top_bar',    'Pasek górny:')}     {top_res} px",
            f"{T.get('label_bottom_bar', 'Pasek dolny:')}     {bot_res} px",
            f"{T.get('label_left_bar',   'Pasek lewy:')}      {left_res} px",
            f"{T.get('label_right_bar',  'Pasek prawy:')}     {right_res} px",
            "",
            f"{T.get('label_source', 'Źródło:')} _NET_WM_STRUT_PARTIAL (EWMH)",
        ]
        messagebox.showinfo(T.get("btn_test_strut", "Test panel detection"),
                            "\n".join(lines))


