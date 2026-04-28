# =============================================================================
# gui/tab_main.py  v3 — przywrócony układ 2-kolumnowy z obrazka
#
# Lewa kolumna:  Motyw GLava + Kolory + Profile kolorów + Ustawienia
# Prawa kolumna: Tryby + Geometria GLava
# =============================================================================

import tkinter as tk
from tkinter import ttk, colorchooser, messagebox, simpledialog
import os, subprocess

from .core import (
    GLAVA_MODULES, BING_REGIONS, BIN_DIR,
    FLAG_RED, FLAG_MANUAL, WALLPAPER_LOCK,
    read_active_module, write_active_module,
    read_bing_config, write_bing_config,
    load_color_presets, save_color_presets,
    get_live_frag, get_template,
)
from .colors import (
    read_colors_from_frag, write_colors_to_frag,
    shader_supports_hsv, set_gradient_mode,
)
from .geometry import get_screen_info, calc_geometry, read_geometry, write_geometry
from .glava import glava_restart, glava_toggle, restore_auto, toggle_wallpaper_lock
from . import core


def build_tab_main(parent, app):
    tab = TabMain(parent, app)
    tab.build()
    app._tab_main_ref = tab


class TabMain:
    def __init__(self, parent, app):
        self.parent = parent
        self.app    = app
        self.T      = app.T
        self.bing_cfg       = read_bing_config()
        self.presets        = load_color_presets()
        self.current_colors = {"top": "#ffffff", "mid": "#888888", "bottom": "#000000"}
        self.gradient_mode  = app.settings.get("gradient_mode", "rgb")
        self._load_colors_from_live()

    def _load_colors_from_live(self):
        colors = read_colors_from_frag(get_live_frag(self.app.active_module))
        if colors:
            self.current_colors = colors
        if "LAST_SESSION" in self.presets:
            self.current_colors = self.presets["LAST_SESSION"]

    def build(self):
        outer = tk.Frame(self.parent, padx=8, pady=6)
        outer.pack(fill="both", expand=True, pady=(0, 8))

        left  = tk.Frame(outer)
        right = tk.Frame(outer)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        right.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        outer.columnconfigure(0, weight=1, uniform="col")
        outer.columnconfigure(1, weight=1, uniform="col")
        outer.rowconfigure(0, weight=1)

        self._build_left(left)
        self._build_right(right)

    # ── LEWA: Motyw + Kolory + Profile kolorów + Ustawienia ──────────────────

    def _build_left(self, col):
        T = self.T

        # Motyw GLava
        lf_mod = ttk.LabelFrame(col, text=T.get("section_module", "GLava theme"), padding=(8, 6))
        lf_mod.pack(fill="x", pady=(0, 8))
        row = tk.Frame(lf_mod)
        row.pack(fill="x")
        ttk.Label(row, text=T.get("label_module", "Active theme") + ":").pack(side="left")
        self.module_var = tk.StringVar(value=self.app.active_module)
        ttk.Combobox(row, textvariable=self.module_var,
                     values=GLAVA_MODULES, width=9, state="readonly").pack(side="left", padx=(4, 8))
        row.children["!combobox"].bind("<<ComboboxSelected>>",
                                       lambda e: None)
        ttk.Button(row, text=T.get("btn_apply_module", "Apply theme"),
                  command=self._apply_module
                  ).pack(side="left", fill="x", expand=True)

        # Kolory
        lf_col = ttk.LabelFrame(col, text=T.get("section_colors", "Colors"), padding=(8, 6))
        lf_col.pack(fill="x", pady=(0, 8))
        srow = ttk.Frame(lf_col)
        srow.pack(fill="x", pady=(0, 5))
        self.color_btns = {}
        for key in ("top", "mid", "bottom"):
            lbl = T.get(f"btn_{key}", key.capitalize())
            btn = tk.Button(srow, text=lbl,
                            bg=self.current_colors[key],
                            command=lambda k=key: self._pick_color(k),
                            height=1)
            btn.pack(side="left", padx=2, expand=True, fill="x")
            self.color_btns[key] = btn
        ttk.Button(lf_col, text=T.get("btn_apply_manual", "Apply colors (manual mode)"),
                  command=self._apply_colors
                  ).pack(fill="x")
        ttk.Button(lf_col, text=T.get("btn_capture", "Capture current from screen"),
                  command=self._capture_colors
                  ).pack(fill="x")
        grad_row = ttk.Frame(lf_col)
        grad_row.pack(fill="x")
        ttk.Label(grad_row, text=T.get("label_gradient", "Gradient:")).pack(side="left")
        self.gradient_var = tk.StringVar(value=self.gradient_mode)
        for val, lbl in (("rgb", "RGB"), ("hsv", "HSV")):
            ttk.Radiobutton(grad_row, text=lbl, variable=self.gradient_var,
                           value=val, command=self._change_gradient).pack(side="left", padx=3)
        self.hsv_warn = tk.Label(grad_row, text="", fg="#e65100")
        self.hsv_warn.pack(side="left")
        self._update_hsv_warn()


        # Profile kolorów
        lf_pre = ttk.LabelFrame(col, text=T.get("section_profiles", "Color profiles"), padding=(8, 6))
        lf_pre.pack(fill="x", pady=(0, 8))
        self.preset_var = tk.StringVar()
        names = sorted(k for k in self.presets if k != "LAST_SESSION")
        self.preset_cb = ttk.Combobox(lf_pre, textvariable=self.preset_var,
                                      values=names, state="readonly")
        self.preset_cb.pack(fill="x", pady=(0, 5))
        if names:
            self.preset_cb.current(0)
        btn_row = ttk.Frame(lf_pre)
        btn_row.pack(fill="x")
        ttk.Button(btn_row, text=T.get("btn_load", "Load"),
                   command=self._load_preset
                   ).pack(side="left", expand=True, fill="x", padx=(0, 2))
        ttk.Button(btn_row, text=T.get("btn_save_new", "Save new"),
                   command=self._save_preset
                   ).pack(side="left", expand=True, fill="x", padx=(0, 2))
        ttk.Button(btn_row, text=T.get("btn_delete", "Delete"),
                   command=self._delete_preset,
                   style="Accent.TButton"
                   ).pack(side="left", expand=True, fill="x", padx=(0, 2))

        # Ustawienia
        lf_set = ttk.LabelFrame(col, text=T.get("section_settings", "Settings"), padding=(8, 6))
        lf_set.pack(fill="x", pady=(0, 8))
        s_row = ttk.Frame(lf_set)
        s_row.pack(fill="x")
        ttk.Label(s_row, text=T.get("label_region", "Bing region") + ":").pack(side="left")
        self.region_var = tk.StringVar(value=self.bing_cfg.get("BING_REGION", "de-DE"))
        ttk.Combobox(s_row, textvariable=self.region_var, values=BING_REGIONS,
                     width=7, state="readonly"
                     ).pack(side="left", padx=(4, 8))
        ttk.Button(s_row, text=T.get("btn_save_settings", "Save settings"),
                  command=self._save_settings).pack(side="left")
        lock_text = (T.get("btn_unlock_wallpaper", "Unlock wallpaper")
                     if os.path.exists(WALLPAPER_LOCK)
                     else T.get("btn_lock_wallpaper", "Lock wallpaper"))
        self.lock_btn = ttk.Button(lf_set, text=lock_text,
                                   command=self._toggle_lock,
                                   style="Accent.TButton")
        self.lock_btn.pack(fill="x")

    # ── PRAWA: Tryby + Geometria ──────────────────────────────────────────────

    def _build_right(self, col):
        T = self.T

        # Tryby
        lf_mode = ttk.LabelFrame(col, text=T.get("section_modes", "Modes"), padding=(8, 6))
        lf_mode.pack(fill="x", pady=(0, 8))
        ttk.Button(lf_mode,
                   text=T.get("btn_fetch_wallpaper", "Fetch Bing wallpaper (desktop only)"),
                   command=self._fetch_wallpaper_user,
                   style="Accent.TButton"
                   ).pack(fill="x", pady=(4, 2))
        ttk.Button(lf_mode,
                   text=T.get("btn_fetch_wallpaper_full", "Fetch Bing wallpaper (desktop + login screen)"),
                   command=self._fetch_wallpaper_full,
                   style="Accent.TButton"
                   ).pack(fill="x")
        ttk.Button(lf_mode,
                   text=T.get("btn_restore_auto", "Restore Bing (auto)"),
                   command=self._restore_auto
                   ).pack(fill="x")
        ttk.Button(lf_mode,
                   text=T.get("btn_toggle_glava", "Enable / Disable GLava"),
                   command=self._toggle_glava
                   ).pack(fill="x", pady=(2, 4))
        # Geometria GLava
        lf_geo = ttk.LabelFrame(col, text=T.get("section_geometry", "GLava geometry"), padding=(8, 6))
        lf_geo.pack(fill="x", pady=(0, 8))
        geo = read_geometry(core.RC_GLSL)
        if geo is None:
            si  = get_screen_info()
            geo = calc_geometry(self.app.active_module, si[0], si[1], si[4], si[3])
        self.geo_vars = {}
        grid = tk.Frame(lf_geo)
        grid.pack(fill="x", pady=(0, 5))
        for i, (key, val, lbl) in enumerate([
            ("x", geo[0], "X"), ("y", geo[1], "Y"),
            ("w", geo[2], "W"), ("h", geo[3], "H"),
        ]):
            r, c = i // 2, (i % 2) * 2
            ttk.Label(grid, text=lbl, width=2, anchor="e"
                     ).grid(row=r, column=c, padx=(0, 2), sticky="e")
            var = tk.StringVar(value=str(val))
            self.geo_vars[key] = var
            ttk.Entry(grid, textvariable=var, width=8
                     ).grid(row=r, column=c+1, padx=(0, 10))
        ttk.Button(lf_geo,
                  text=T.get("btn_auto_geometry", "Auto-detect geometry"),
                  command=self._auto_geometry
                  ).pack(fill="x")
        ttk.Button(lf_geo,
                  text=T.get("btn_apply_geometry", "Apply geometry"),
                  command=self._apply_geometry
                  ).pack(fill="x")

    # ── CALLBACKI ─────────────────────────────────────────────────────────────

    def refresh_geometry(self):
        """Odświeża pola X/Y/W/H aktualną wartością z rc.glsl."""
        geo = read_geometry(core.RC_GLSL)
        if geo and hasattr(self, "geo_vars"):
            for k, v in zip(("x", "y", "w", "h"), geo):
                self.geo_vars[k].set(str(v))

    def _apply_module(self):
        module = self.module_var.get()
        self.app.active_module = module
        write_active_module(module)
        tmpl = get_template(module)
        if not os.path.exists(tmpl):
            messagebox.showerror("", f"Brak szablonu:\n{tmpl}")
            return
        # Przelicz geometrię dla nowego modułu
        self._update_geometry_for_module(module)
        if not os.path.exists(get_live_frag(module)):
            self._apply_colors(); return
        if not os.path.exists(FLAG_RED) and not os.path.exists(FLAG_MANUAL):
            subprocess.Popen(["/bin/bash", os.path.join(BIN_DIR, "glava-colors-auto")])
            self.app.root.after(1500, self.app.update_status)
        else:
            glava_restart(module, after_fn=self.app.update_status)
        self.app.rebuild_module_tab()
        self._update_hsv_warn()

    def _update_geometry_for_module(self, module):
        """Przelicza i zapisuje geometrię dla danego modułu uwzględniając jego flagi."""
        try:
            from .geometry import get_screen_info, calc_geometry, write_geometry
            import re as _re
            si = get_screen_info()
            flipped   = False
            mirror_yx = False
            glava_dir = os.path.join(os.path.expanduser("~"), ".config/glava")
            if module == "bars":
                path = os.path.join(glava_dir, "bars.glsl")
                if os.path.exists(path):
                    txt = open(path).read()
                    m = _re.search(r'^#define\s+FLIP\s+(\S+)', txt, _re.MULTILINE)
                    if m: flipped = bool(int(m.group(1)))
                    m = _re.search(r'^#define\s+MIRROR_YX\s+(\S+)', txt, _re.MULTILINE)
                    if m: mirror_yx = bool(int(m.group(1)))
            elif module == "graph":
                path = os.path.join(glava_dir, "graph.glsl")
                if os.path.exists(path):
                    txt = open(path).read()
                    m = _re.search(r'^#define\s+INVERT\s+(\S+)', txt, _re.MULTILINE)
                    if m: flipped = bool(int(m.group(1)))
            # circle, wave, radial — brak flag flip/mirror, standardowa geometria
            x, y, w, h = calc_geometry(
                module, si[0], si[1], si[4], si[3],
                flipped=flipped, mirror_yx=mirror_yx,
                left_reserved=si[5], right_reserved=si[6]
            )
            write_geometry(core.RC_GLSL, x, y, w, h)
        except Exception:
            pass

    def _pick_color(self, key):
        color = colorchooser.askcolor(color=self.current_colors[key])[1]
        if color:
            self.current_colors[key] = color
            self.color_btns[key].config(bg=color)
            self._save_last_session()

    def _apply_colors(self):
        ok, err = write_colors_to_frag(
            self.app.active_module, self.current_colors, self.gradient_mode)
        if not ok:
            messagebox.showerror("", err); return
        self._save_last_session()
        glava_restart(self.app.active_module, after_fn=self.app.update_status)

    def _capture_colors(self):
        colors = read_colors_from_frag(get_live_frag(self.app.active_module))
        if colors:
            self.current_colors = colors
            for key, btn in self.color_btns.items():
                btn.config(bg=self.current_colors[key])

    def _change_gradient(self):
        mode = self.gradient_var.get()
        self.gradient_mode = mode
        self.app.settings["gradient_mode"] = mode
        from .core import save_settings
        save_settings(self.app.settings)
        set_gradient_mode(self.app.active_module, mode)
        glava_restart(self.app.active_module, after_fn=self.app.update_status)


    def _update_hsv_warn(self):
        if hasattr(self, "hsv_warn"):
            self.hsv_warn.config(text=(
                "⚠ RGB only"
                if not shader_supports_hsv(self.app.active_module) else ""))

    def _load_preset(self):
        name = self.preset_var.get()
        if name and name in self.presets:
            self.current_colors = self.presets[name].copy()
            for key, btn in self.color_btns.items():
                btn.config(bg=self.current_colors[key])
            self._apply_colors()

    def _save_preset(self):
        name = simpledialog.askstring("Nowy profil kolorów", "Podaj nazwę:")
        if name:
            self.presets[name] = self.current_colors.copy()
            save_color_presets(self.presets)
            self._refresh_preset_cb()

    def _delete_preset(self):
        name = self.preset_var.get()
        if name and messagebox.askyesno("", f"Usuń '{name}'?"):
            del self.presets[name]
            save_color_presets(self.presets)
            self._refresh_preset_cb()

    def _refresh_preset_cb(self):
        names = sorted(k for k in self.presets if k != "LAST_SESSION")
        self.preset_cb["values"] = names
        if names: self.preset_cb.current(0)

    def _save_last_session(self):
        self.presets["LAST_SESSION"] = self.current_colors.copy()
        save_color_presets(self.presets)

    def _fetch_wallpaper_user(self):
        subprocess.Popen(["/bin/bash",
                          os.path.join(BIN_DIR, "bing-fetch-user.sh"), "--force"])
        self.app.root.after(4000, self.app.update_status)

    def _fetch_wallpaper_full(self):
        import getpass
        from .glava import _sudo_run
        dl = "/usr/local/bin/bing-downloader.sh"
        if not os.path.exists(dl):
            dl = os.path.join(BIN_DIR, "bing-downloader.sh")
        _sudo_run([dl, getpass.getuser(), "--force"])
        self.app.root.after(4000, self.app.update_status)

    def _restore_auto(self):
        restore_auto(callback=self.app.update_status)

    def _toggle_glava(self):
        glava_toggle()
        self.app.root.after(500, self.app.update_status)

    def _auto_geometry(self):
        T = self.T
        si = get_screen_info()
        x, y, w, h = calc_geometry(self.app.active_module,
                                    si[0], si[1], si[4], si[3])
        parts = []
        if si[3] > 0: parts.append(f"Górny pasek: {si[3]}px")
        if si[4] > 0: parts.append(f"Dolny pasek: {si[4]}px")
        bar_info = ", ".join(parts) if parts else "Brak paska"
        messagebox.showinfo("Auto-konfiguracja geometrii",
                            f"Wykryto: {si[0]}×{si[1]}\n{bar_info}\n"
                            f"X={x}  Y={y}  W={w}  H={h}")
        for k, v in (("x", x), ("y", y), ("w", w), ("h", h)):
            self.geo_vars[k].set(str(v))
        if write_geometry(core.RC_GLSL, x, y, w, h):
            glava_restart(self.app.active_module, after_fn=self.app.update_status)

    def _apply_geometry(self):
        try:
            x, y = int(self.geo_vars["x"].get()), int(self.geo_vars["y"].get())
            w, h = int(self.geo_vars["w"].get()), int(self.geo_vars["h"].get())
        except ValueError:
            messagebox.showerror("", "Wartości muszą być liczbami całkowitymi.")
            return
        if w <= 0 or h <= 0:
            messagebox.showerror("", "Szerokość i wysokość muszą być > 0.")
            return
        if write_geometry(core.RC_GLSL, x, y, w, h):
            messagebox.showinfo("", "Geometria zaktualizowana.")
            glava_restart(self.app.active_module, after_fn=self.app.update_status)

    def _save_settings(self):
        self.bing_cfg["BING_REGION"] = self.region_var.get()
        write_bing_config(self.bing_cfg)
        messagebox.showinfo("", "Zapisano.")

    def _toggle_lock(self):
        locked = toggle_wallpaper_lock(WALLPAPER_LOCK)
        self.lock_btn.config(text=(
            "Odblokuj tapetę" if locked else "Zablokuj tapetę"))
        self.app.update_status()
