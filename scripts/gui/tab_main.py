# =============================================================================
# gui/tab_main.py
#
# Lewa kolumna:  Motyw GLava + Kolory + Profile kolorów + Ustawienia
# Prawa kolumna: Tryby + Geometria GLava
#
# Wzorzec: bars.py + example.py (Forest-ttk-theme)
# =============================================================================
import os
import subprocess
import tkinter as tk
from tkinter import colorchooser, messagebox, ttk

from . import core
from .color_button import ColorButton
from .colors import (
    read_colors_from_frag,
    set_gradient_mode,
    shader_supports_hsv,
    write_colors_to_frag,
)
from .core import (
    BIN_DIR,
    BING_REGIONS,
    FLAG_MANUAL,
    FLAG_RED,
    WALLPAPER_LOCK,
    get_live_frag,
    get_template,
    load_color_presets,
    read_bing_config,
    save_color_presets,
    write_bing_config,
)
from .geometry import calc_geometry, get_screen_info, read_geometry, write_geometry
from .glava import (
    glava_restart,
    glava_restart_instance,
    glava_toggle,
    toggle_wallpaper_lock,
)
from .modules.base import ask_string


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

    def _inst(self):
        """Zwraca aktywna instancje GlavaInstance."""
        return self.app.active_instance

    def _live_frag(self, module=None):
        """Sciezka live frag aktywnej instancji."""
        m = module or self.app.active_module
        inst = self._inst()
        if inst:
            return inst.module_frag(m)
        return get_live_frag(m)

    def _tmpl_frag(self, module=None):
        """Sciezka szablonu frag aktywnej instancji."""
        m = module or self.app.active_module
        inst = self._inst()
        if inst:
            return inst.module_tmpl(m)
        return get_template(m)

    def _load_colors_from_live(self):
        colors = read_colors_from_frag(self._live_frag())
        if colors:
            self.current_colors = colors
        if "LAST_SESSION" in self.presets:
            self.current_colors = self.presets["LAST_SESSION"]

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
        self._build_left(left)
        self._build_right(right)

    # ── LEWA ─────────────────────────────────────────────────────────────────
    def _build_left(self, col):
        T = self.T
        # Kolory
        lf = ttk.LabelFrame(col, text=T.get("section_colors", "Colors"),
                            padding=(15, 10))
        lf.pack(fill="x", padx=10, pady=10)
        srow = ttk.Frame(lf)
        srow.pack(fill="x", pady=(0, 5))
        self.color_btns = {}
        for key in ("top", "mid", "bottom"):
            lbl_text = T.get(f"btn_{key}", key.capitalize())
            color    = self.current_colors[key]
            cb = ColorButton(srow, key=key, text=lbl_text,
                             color=color,
                             command=lambda k=key: self._pick_color(k),
                             root=self.app.root)
            cb.widget.pack(side="left", padx=2, expand=True, fill="x")
            self.color_btns[key] = cb
        apply_row = ttk.Frame(lf)
        apply_row.pack(fill="x", pady=(0, 3))
        ttk.Button(apply_row, text=T.get("btn_apply_manual", "Apply colors (manual mode)"),
                   command=self._apply_colors,
                   style="Accent.TButton").pack(fill="x")
        restore_row = ttk.Frame(lf)
        restore_row.pack(fill="x", pady=(0, 3))
        ttk.Button(restore_row, text=T.get("btn_sync_wallpaper", "Sync with Wallpaper (auto mode)"),
                   command=self._restore_auto).pack(fill="x")
        ttk.Button(lf, text=T.get("btn_capture", "Capture current from screen"),
                   command=self._capture_colors).pack(fill="x", pady=(0, 3))
        grad_row = ttk.Frame(lf)
        grad_row.pack(fill="x", pady=(0, 3))
        ttk.Label(grad_row, text=T.get("label_gradient", "Gradient:")).pack(side="left")
        self.gradient_var = tk.StringVar(value=self.gradient_mode)
        for val, lbl in (("rgb", "RGB"), ("hsv", "HSV")):
            ttk.Radiobutton(grad_row, text=lbl, variable=self.gradient_var,
                            value=val,
                            command=self._change_gradient).pack(side="left", padx=3)
        self.hsv_warn = tk.Label(grad_row, text="", fg="#e65100")
        self.hsv_warn.pack(side="left")
        self._update_hsv_warn()
        self.all_inst_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(grad_row, text=T.get("chk_all_instances", "Wszystkie"),
                        variable=self.all_inst_var).pack(side="right")
        # Profile kolorów
        lf = ttk.LabelFrame(col, text=T.get("section_profiles", "Color profiles"),
                            padding=(15, 10))
        lf.pack(fill="x", padx=10, pady=10)
        self.preset_var = tk.StringVar()
        names = sorted(k for k in self.presets if k != "LAST_SESSION")
        self.preset_cb = ttk.Combobox(lf, textvariable=self.preset_var,
                                      values=names, state="readonly")
        self.preset_cb.pack(fill="x", pady=(0, 5))
        if names:
            self.preset_cb.current(0)
        btn_row = ttk.Frame(lf)
        btn_row.pack(fill="x")
        ttk.Button(btn_row, text=T.get("btn_load", "Load"),
                   command=self._load_preset,
                   style="Accent.TButton").pack(side="left", expand=True,
                                                   fill="x", padx=(0, 2))
        ttk.Button(btn_row, text=T.get("btn_save_new", "Save new"),
                   command=self._save_preset).pack(side="left", expand=True,
                                                   fill="x", padx=(0, 2))
        ttk.Button(btn_row, text=T.get("btn_delete", "Delete"),
                   command=self._delete_preset,
                   style="Danger.TButton").pack(side="left", expand=True, fill="x")

    # ── GLava Geometry ────────────────────────────────────────────────────
        lf = ttk.LabelFrame(col, text=T.get("section_geometry", "GLava geometry"),
                            padding=(15, 10))
        lf.pack(fill="x", padx=10, pady=10)
        rc_path = (self.app.get_active_rc_glsl()
                   if hasattr(self.app, 'get_active_rc_glsl') else None) or core.RC_GLSL
        geo = read_geometry(rc_path)
        if geo is None:
            si  = get_screen_info()
            geo = calc_geometry(self.app.active_module, si[0], si[1], si[4], si[3])
        self.geo_vars = {}
        grid_f = ttk.Frame(lf)
        grid_f.pack(fill="x", pady=(0, 5))
        for i, (key, val, lbl) in enumerate([
            ("x", geo[0], "X"), ("y", geo[1], "Y"),
            ("w", geo[2], "W"), ("h", geo[3], "H"),
        ]):
            r, c = i // 2, (i % 2) * 2
            ttk.Label(grid_f, text=lbl, width=2,
                      anchor="e").grid(row=r, column=c, padx=(0, 2), pady=2, sticky="e")
            var = tk.StringVar(value=str(val))
            self.geo_vars[key] = var
            ttk.Entry(grid_f, textvariable=var,
                      width=8).grid(row=r, column=c + 1, padx=(0, 10), pady=2)
        ttk.Button(lf, text=T.get("btn_auto_geometry", "Auto-detect geometry"),
                   command=self._auto_geometry).pack(fill="x", pady=(0, 3))
        ttk.Button(lf, text=T.get("btn_apply_geometry", "Apply geometry"),
                   command=self._apply_geometry,
                   style="Accent.TButton").pack(fill="x")

    # ── PRAWA ─────────────────────────────────────────────────────────────────
    def _build_right(self, col):
        T = self.T

        # ── Wallpaper ──────────────────────────────────────────────────────────
        lf = ttk.LabelFrame(col, text=T.get("section_wallpaper", "Wallpaper"),
                            padding=(15, 10))
        lf.pack(fill="x", padx=10, pady=10)

        # --- wiersz: strzałka | miniatura w Card | strzałka ---
        nav_row = ttk.Frame(lf)
        nav_row.pack(fill="x", pady=(0, 4))

        self._wp_regions   = list(BING_REGIONS)          # lista regionów
        self._wp_region_idx = 0                           # aktywny indeks
        try:
            self._wp_region_idx = self._wp_regions.index(
                self.bing_cfg.get("BING_REGION", "de-DE"))
        except ValueError:
            pass

        self._btn_prev = ttk.Button(nav_row, text="‹", width=2,
                                    command=self._wp_prev)
        self._btn_prev.pack(side="left", padx=(0, 4))

        # Ramka Card wokół miniatury
        card = ttk.Frame(nav_row, style="Card", padding=4)
        card.pack(side="left", expand=True)

        self._thumb_placeholder = tk.PhotoImage(width=249, height=140)
        self._thumb_label = tk.Label(card, image=self._thumb_placeholder,
                                     bg="#2a2a2a", relief="flat")
        self._thumb_label.pack()

        self._btn_next = ttk.Button(nav_row, text="›", width=2,
                                    command=self._wp_next)
        self._btn_next.pack(side="left", padx=(4, 0))

        # --- wskaźnik regionu ---
        self._region_indicator_var = tk.StringVar()
        ttk.Label(lf, textvariable=self._region_indicator_var,
                  font=(None, 10)).pack()
        self._update_region_indicator()

        # --- lock wallpaper jako Switch ---
        self._lock_var = tk.BooleanVar(value=os.path.exists(WALLPAPER_LOCK))
        self.lock_btn = ttk.Checkbutton(
            lf,
            text=T.get("btn_lock_wallpaper", "Lock wallpaper"),
            style="Switch",
            variable=self._lock_var,
            command=self._toggle_lock,
        )
        self.lock_btn.pack(anchor="w", pady=(6, 0))

        # --- tytuł ---
        ttk.Label(lf, text=T.get("label_wp_title", "Tytuł:"),
                  font=(None, 10)).pack(anchor="w", pady=(6, 0))
        self._wp_title_var = tk.StringVar(value="—")
        ttk.Label(lf, textvariable=self._wp_title_var,
                  wraplength=400, justify="left",
                  font=(None, 10)).pack(anchor="w")

        # --- copyright ---
        ttk.Label(lf, text=T.get("label_wp_copyright", "Copyright:"),
                  font=(None, 10)).pack(anchor="w", pady=(4, 0))
        self._wp_copy_var = tk.StringVar(value="—")
        ttk.Label(lf, textvariable=self._wp_copy_var,
                  wraplength=400, justify="left",
                  font=(None, 10)).pack(anchor="w")

        ttk.Separator(lf, orient="horizontal").pack(fill="x", pady=8)

        # --- fetch ---
        fetch_row = ttk.Frame(lf)
        fetch_row.pack(fill="x", pady=(0, 6))
        ttk.Button(fetch_row,
                   text=T.get("btn_fetch_wallpaper", "Fetch user"),
                   command=self._fetch_wallpaper_user,
                   style="Accent.TButton").pack(side="left", expand=True,
                                                fill="x", padx=(0, 4))
        ttk.Button(fetch_row,
                   text=T.get("btn_fetch_wallpaper_full", "Fetch with loginscreen"),
                   command=self._fetch_wallpaper_full).pack(side="left", expand=True,
                                                            fill="x")


        # ── GLava Geometry przeniesiona do lewej kolumny──────────────────────


        self._load_wp_thumbnail()
        self._start_meta_watch()
        # ── CALLBACKI ─────────────────────────────────────────────────────────────
    def _start_meta_watch(self):
        if not os.path.exists(core.BING_METADATA):
            return
        self._meta_watch_active = True
        import threading
        t = threading.Thread(target=self._meta_watch_thread, daemon=True)
        t.start()

    def _meta_watch_thread(self):
        while getattr(self, "_meta_watch_active", False):
            proc = subprocess.Popen(
                ["inotifywait", "-e", "close_write", core.BING_METADATA],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            proc.wait()
            if getattr(self, "_meta_watch_active", False):
                self.app.root.after(0, self._load_wp_thumbnail)

    def refresh_geometry(self):
        rc_path = (self.app.get_active_rc_glsl() if hasattr(self.app, 'get_active_rc_glsl') else None) or core.RC_GLSL
        geo = read_geometry(rc_path)
        if geo and hasattr(self, "geo_vars"):
            for k, v in zip(("x", "y", "w", "h"), geo):
                self.geo_vars[k].set(str(v))

    def destroy(self):
        self._meta_watch_active = False

    def _wp_prev(self):
        self._wp_region_idx = (self._wp_region_idx - 1) % len(self._wp_regions)
        self._update_region_indicator()
        self._load_wp_thumbnail()
        self._save_region()

    def _wp_next(self):
        self._wp_region_idx = (self._wp_region_idx + 1) % len(self._wp_regions)
        self._update_region_indicator()
        self._load_wp_thumbnail()
        self._save_region()

    def _update_region_indicator(self):
        region = self._wp_regions[self._wp_region_idx]
        total  = len(self._wp_regions)
        self._region_indicator_var.set(
            f"{region}  ·  {self._wp_region_idx + 1} / {total}")

    def _load_wp_thumbnail(self):
        if not hasattr(self, "_thumb_label"):
            return
        region = self._wp_regions[self._wp_region_idx]
        # Wczytaj metadane
        meta = {}
        if os.path.exists(core.BING_METADATA):
            try:
                import json
                with open(core.BING_METADATA, encoding="utf-8") as f:
                    meta = json.load(f)
            except Exception:
                pass
        region_meta = meta.get(region, {})
        # Tytuł i copyright
        title = region_meta.get("title", "—")
        if title in ("Info", "", "—"):
            copyright = region_meta.get("copyright", "")
            idx = copyright.find(" (©")
            title = copyright[:idx] if idx > 0 else copyright
        self._wp_title_var.set(title)
        self._wp_copy_var.set(region_meta.get("copyright", "—"))
        # Miniatura
        thumb_file = region_meta.get("thumb_file", "")
        if thumb_file and os.path.exists(thumb_file):
            try:
                from PIL import Image, ImageTk
                img = Image.open(thumb_file).resize((249, 140), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self._thumb_label.config(image=photo)
                self._thumb_label._photo = photo  # zapobiegamy GC
            except Exception:
                self._thumb_label.config(image=self._thumb_placeholder)
        else:
            self._thumb_label.config(image=self._thumb_placeholder)
    def _update_geometry_for_module(self, module):
        try:
            import re as _re

            from .geometry import calc_geometry, get_screen_info, write_geometry
            si = get_screen_info()
            flipped = False
            mirror_yx = False
            glava_dir = self.app.get_active_glava_dir() if hasattr(self.app, 'get_active_glava_dir') else os.path.join(os.path.expanduser("~"), ".config/glava")
            rc_path   = self.app.get_active_rc_glsl()   if hasattr(self.app, 'get_active_rc_glsl')   else core.RC_GLSL
            if module == "bars":
                path = os.path.join(glava_dir, "bars.glsl")
                if os.path.exists(path):
                    with open(path) as f:
                        txt = f.read()
                    m = _re.search(r'^#define\s+FLIP\s+(\S+)', txt, _re.MULTILINE)
                    if m: flipped = bool(int(m.group(1)))
                    m = _re.search(r'^#define\s+MIRROR_YX\s+(\S+)', txt, _re.MULTILINE)
                    if m: mirror_yx = bool(int(m.group(1)))
            elif module == "graph":
                path = os.path.join(glava_dir, "graph.glsl")
                if os.path.exists(path):
                    with open(path) as f:
                        txt = f.read()
                    m = _re.search(r'^#define\s+INVERT\s+(\S+)', txt, _re.MULTILINE)
                    if m: flipped = bool(int(m.group(1)))
            x, y, w, h = calc_geometry(
                module, si[0], si[1], si[4], si[3],
                flipped=flipped, mirror_yx=mirror_yx,
                left_reserved=si[5], right_reserved=si[6]
            )
            write_geometry(rc_path, x, y, w, h)
        except Exception:
            pass

    def _contrast_fg(self, hex_color):
        try:
            h = hex_color.lstrip("#")
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
            return "#000000" if luminance > 0.5 else "#ffffff"
        except Exception:
            return "#ffffff"

    def _update_color_btn(self, key, color):
        if key in self.color_btns:
            self.color_btns[key].set_color(color)

    def _pick_color(self, key):
        color = colorchooser.askcolor(
            color=self.current_colors[key],
            title=self.T.get("dialog_color_pick_title", "Pick color"))[1]
        if color:
            self.current_colors[key] = color
            self._update_color_btn(key, color)
            self._save_last_session()

    def _apply_colors(self):
        all_inst = self.all_inst_var.get() if hasattr(self, "all_inst_var") else False

        if all_inst and hasattr(self.app, "instances"):
            any_err = False
            # Odśwież PID-y z plików — daemon mógł zmienić procesy
            from gui.glava import adopt_instance
            for _iid in list(self.app.instances.keys()):
                if self.app.processes.get(_iid) is None:
                    _pid, _proc = adopt_instance(_iid)
                    if _proc is not None:
                        self.app.processes[_iid] = _proc

            for iid, inst in self.app.instances.items():
                module = self.app._inst_modules.get(iid, self.app.active_module)
                ok, err = write_colors_to_frag(
                    module,
                    self.current_colors,
                    self.gradient_mode,
                    tmpl_path=inst.module_tmpl(module),
                    live_path=inst.module_frag(module),
                )
                if not ok:
                    any_err = True
            if any_err:
                messagebox.showerror("", self.T.get("error_some_instances",
                                                    "Błąd przy niektórych instancjach."))
            self._save_last_session()
            for iid, inst in self.app.instances.items():
                proc = self.app.processes.get(iid)
                module = self.app._inst_modules.get(iid, self.app.active_module)
                self.app.processes[iid] = None

                def _after(new_proc, _iid=iid):
                    self.app.processes[_iid] = new_proc
                    self.app.root.after(0, self.app.update_status)

                glava_restart_instance(instance=inst, module=module,
                                       proc=proc, after_fn=_after)

        else:
            ok, err = write_colors_to_frag(
                self.app.active_module,
                self.current_colors,
                self.gradient_mode,
                tmpl_path=self._tmpl_frag(),
                live_path=self._live_frag(),
            )
            if not ok:
                messagebox.showerror("", err)
                return
            self._save_last_session()
            if hasattr(self.app, 'restart_active_instance'):
                self.app.restart_active_instance(after_fn=self.app.update_status)
            else:
                glava_restart(self.app.active_module, after_fn=self.app.update_status)

    def _capture_colors(self):
        colors = read_colors_from_frag(self._live_frag())
        if colors:
            self.current_colors = colors
            for key in self.color_btns:
                self._update_color_btn(key, self.current_colors[key])

    def _change_gradient(self):
        mode = self.gradient_var.get()
        self.gradient_mode = mode
        self.app.settings["gradient_mode"] = mode
        from .core import save_settings
        save_settings(self.app.settings)
        all_inst = self.all_inst_var.get() if hasattr(self, "all_inst_var") else False
        targets = (list(self.app.instances.items())
                   if all_inst and hasattr(self.app, "instances")
                   else [(self.app._active_inst_id, self.app.active_instance)])
        for iid, inst in targets:
            if inst is None:
                continue
            set_gradient_mode(
                self.app._inst_modules.get(iid, self.app.active_module), mode,
                live_path=inst.module_frag(self.app._inst_modules.get(iid, self.app.active_module)),
                tmpl_path=inst.module_tmpl(self.app._inst_modules.get(iid, self.app.active_module)),
            )
        if all_inst and hasattr(self.app, 'instances'):
            prev_iid  = self.app._active_inst_id
            prev_inst = self.app.active_instance
            for iid, inst in list(self.app.instances.items()):
                if inst is None:
                    continue
                self.app._active_inst_id  = iid
                self.app.active_instance  = inst
                self.app.restart_active_instance(
                    module=self.app._inst_modules.get(iid, self.app.active_module),
                    after_fn=None)
            self.app._active_inst_id = prev_iid
            self.app.active_instance = prev_inst
            self.app.update_status()
        elif hasattr(self.app, 'restart_active_instance'):
            self.app.restart_active_instance(after_fn=self.app.update_status)
        else:
            glava_restart(self.app.active_module, after_fn=self.app.update_status)

    def _update_hsv_warn(self):
        if hasattr(self, "hsv_warn"):
            self.hsv_warn.config(text=(
                "⚠ RGB only"
                if not shader_supports_hsv(
                    self.app.active_module,
                    live_path=self._live_frag(),
                    tmpl_path=self._tmpl_frag(),
                ) else ""))

    def refresh_gradient_mode(self):
        """Odczytuje tryb gradientu z aktywnego shadera i aktualizuje przełącznik."""
        import re as _re
        live = self._live_frag()
        if not os.path.exists(live):
            return
        try:
            with open(live) as f:
                src = f.read()
            m = _re.search(r'#define HSV_MODE ([01])', src)
            if m:
                mode = "hsv" if m.group(1) == "1" else "rgb"
                self.gradient_mode = mode
                self.gradient_var.set(mode)
        except Exception:
            pass
        self._update_hsv_warn()

    def refresh_active_instance(self):
        """Odświeża UI tab_main po zmianie aktywnej instancji."""
        self._load_colors_from_live()
        for key in self.color_btns:
            self._update_color_btn(key, self.current_colors[key])
        self.refresh_gradient_mode()
        self.refresh_geometry()

    def _load_preset(self):
        name = self.preset_var.get()
        if name and name in self.presets:
            self.current_colors = self.presets[name].copy()
            for key in self.color_btns:
                self._update_color_btn(key, self.current_colors[key])
            self._apply_colors()

    def _save_preset(self):
        name = ask_string(
            self.parent, self.T,
            self.T.get("dialog_color_preset_title", "New color preset"),
            self.T.get("dialog_color_preset_prompt", "Enter name:"))
        if name:
            self.presets[name] = self.current_colors.copy()
            save_color_presets(self.presets)
            self._refresh_preset_cb()

    def _delete_preset(self):
        name = self.preset_var.get()
        if name and messagebox.askyesno("", self.T.get("dialog_delete_preset_confirm", "Delete") + f" '{name}'?"):
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
        from .colors import extract_colors_from_wallpaper

        wallpaper = os.path.expanduser("~/Pictures/Bing/bing_today.jpg")
        if not os.path.exists(wallpaper):
            messagebox.showerror("", self.T.get("error_no_wallpaper",
                                                "Brak tapety: " + wallpaper))
            return

        colors = extract_colors_from_wallpaper(wallpaper)
        if colors is None:
            messagebox.showerror("", self.T.get("error_kmeans",
                                                "Błąd analizy tapety."))
            return

        all_inst = self.all_inst_var.get() if hasattr(self, "all_inst_var") else False


        targets = (list(self.app.instances.items())
                   if all_inst and hasattr(self.app, "instances")
                   else [(self.app._active_inst_id, self.app.active_instance)])

        if hasattr(self.app, 'instances'):
            from gui.glava import adopt_instance
            for _iid in list(self.app.instances.keys()):
                if self.app.processes.get(_iid) is None:
                    _pid, _proc = adopt_instance(_iid)
                    if _proc is not None:
                        self.app.processes[_iid] = _proc

        for iid, inst in targets:
            if inst is None:
                continue
            module = self.app._inst_modules.get(iid, self.app.active_module)
            write_colors_to_frag(
                module, colors, self.gradient_mode,
                tmpl_path=inst.module_tmpl(module),
                live_path=inst.module_frag(module),
            )
            proc = self.app.processes.get(iid)
            self.app.processes[iid] = None

            def _after(new_proc, _iid=iid):
                self.app.processes[_iid] = new_proc
                self.app.root.after(0, self.app.update_status)

            glava_restart_instance(instance=inst, module=module,
                                   proc=proc, after_fn=_after)

        for flag in (FLAG_RED, FLAG_MANUAL):
            if os.path.exists(flag):
                os.remove(flag)

        self.app.root.after(0, self.app.update_status)

    def _toggle_glava(self):
        glava_toggle()
        self.app.root.after(500, self.app.update_status)

    def _auto_geometry(self):
        T = self.T
        si = get_screen_info()
        x, y, w, h = calc_geometry(self.app.active_module,
                                    si[0], si[1], si[4], si[3])
        parts = []
        if si[3] > 0:
            parts.append(f"{T.get('label_top_bar', 'Top panel')}: {si[3]}px")
        if si[4] > 0:
            parts.append(f"{T.get('label_bottom_bar', 'Bottom panel')}: {si[4]}px")
        bar_info = ", ".join(parts) if parts else T.get("label_no_bar", "Brak paska")
        messagebox.showinfo(self.T.get("auto_geo_title", "Auto-konfiguracja geometrii"),
                            f"{T.get('auto_geo_info', 'Wykryto')}: {si[0]}×{si[1]}\n{bar_info}\n"
                            f"X={x}  Y={y}  W={w}  H={h}")
        for k, v in (("x", x), ("y", y), ("w", w), ("h", h)):
            self.geo_vars[k].set(str(v))
        rc_path = self.app.get_active_rc_glsl() if hasattr(self.app, 'get_active_rc_glsl') else core.RC_GLSL
        if write_geometry(rc_path, x, y, w, h):
            if hasattr(self.app, 'restart_active_instance'):
                self.app.restart_active_instance(after_fn=self.app.update_status)
            else:
                glava_restart(self.app.active_module, after_fn=self.app.update_status)

    def _apply_geometry(self):
        try:
            x, y = int(self.geo_vars["x"].get()), int(self.geo_vars["y"].get())
            w, h = int(self.geo_vars["w"].get()), int(self.geo_vars["h"].get())
        except ValueError:
            messagebox.showerror("", self.T.get("error_int_only", "Wartości muszą być liczbami całkowitymi."))
            return
        if w <= 0 or h <= 0:
            messagebox.showerror("", self.T.get("error_positive_only", "Szerokość i wysokość muszą być > 0."))
            return
        rc_path = self.app.get_active_rc_glsl() if hasattr(self.app, 'get_active_rc_glsl') else core.RC_GLSL
        if write_geometry(rc_path, x, y, w, h):
            messagebox.showinfo("", self.T.get("geometry_applied", "Geometria zaktualizowana."))
            if hasattr(self.app, 'restart_active_instance'):
                self.app.restart_active_instance(after_fn=self.app.update_status)
            else:
                glava_restart(self.app.active_module, after_fn=self.app.update_status)

    def _save_region(self):
        region = self._wp_regions[self._wp_region_idx]
        self.bing_cfg["BING_REGION"] = region
        write_bing_config(self.bing_cfg)
    def _save_settings(self):
        self.bing_cfg["BING_REGION"] = self._wp_regions[self._wp_region_idx]
        write_bing_config(self.bing_cfg)
        messagebox.showinfo("", self.T.get("settings_saved", "Settings saved."))

    def _toggle_lock(self):
        toggle_wallpaper_lock(WALLPAPER_LOCK)
        self.app.update_status()
