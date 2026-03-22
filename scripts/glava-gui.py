#!/usr/bin/env python3
# =============================================================================
# glava-gui.py
# Graficzny panel sterowania GLava + Bing wallpaper suite.
#
# Funkcje:
#   - Ręczny dobór kolorów i zapis presetów
#   - Przywracanie trybu auto (kolory z tapety Bing)
#   - Toggle GLava (włącz/wyłącz)
#   - Konfiguracja geometrii GLava (X/Y/W/H → rc.glsl)
#   - Wybór regionu Bing
#   - Wielojęzyczność (pliki lang/*.json)
# =============================================================================

import tkinter as tk
from tkinter import colorchooser, messagebox, simpledialog, ttk
import os
import subprocess
import re
import json
import glob
import datetime

def sudo_run(cmd):
    """Uruchamia komendę jako root z graficznym pytaniem o hasło przez zenity."""
    import shutil
    if shutil.which("zenity"):
        passwd = subprocess.run(
            ["zenity", "--password", "--title=Autoryzacja"],
            capture_output=True, text=True
        ).stdout.strip()
        if not passwd:
            return False
        full_cmd = ["sudo", "-S"] + cmd
        result = subprocess.run(
            full_cmd,
            input=passwd + "\n",
            capture_output=True, text=True
        )
        return result.returncode == 0
    else:
        result = subprocess.run(["sudo"] + cmd)
        return result.returncode == 0

USER_HOME    = os.path.expanduser("~")
CONFIG_DIR   = os.path.join(USER_HOME, ".config/glava")
BIN_DIR      = os.path.join(USER_HOME, ".local/bin")
LIVEFRAG     = os.path.join(CONFIG_DIR, "graph/1.frag")
REDFRAG      = os.path.join(CONFIG_DIR, "graph_red.frag")
RC_GLSL      = os.path.join(CONFIG_DIR, "rc.glsl")
FLAG_RED     = os.path.join(CONFIG_DIR, "red.shift")
FLAG_MANUAL  = os.path.join(CONFIG_DIR, "manual.shift")
PRESETS_FILE = os.path.join(CONFIG_DIR, "presets.json")
WALLPAPER    = os.path.join(USER_HOME, "Pictures/Bing/bing_today.jpg")
SETTINGS_FILE = os.path.join(CONFIG_DIR, "gui_settings.json")

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
LANG_DIR   = os.path.join(SCRIPT_DIR, "..", "lang")
if not os.path.isdir(LANG_DIR):
    LANG_DIR = os.path.join(SCRIPT_DIR, "lang")

BING_REGIONS = [
    "de-DE", "en-US", "en-GB", "fr-FR", "es-ES",
    "it-IT", "pt-BR", "ja-JP", "zh-CN", "pl-PL",
]


def load_lang(lang_code):
    path = os.path.join(LANG_DIR, f"{lang_code}.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    fallback = os.path.join(LANG_DIR, "en.json")
    if os.path.exists(fallback):
        with open(fallback) as f:
            return json.load(f)
    return {}


def available_langs():
    langs = {}
    for f in sorted(glob.glob(os.path.join(LANG_DIR, "*.json"))):
        code = os.path.splitext(os.path.basename(f))[0]
        try:
            with open(f) as fp:
                data = json.load(fp)
            langs[code] = data.get("lang_name", code)
        except Exception:
            langs[code] = code
    return langs


def load_settings():
    defaults = {"lang": "pl", "bing_region": "de-DE"}
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE) as f:
                data = json.load(f)
            defaults.update(data)
        except Exception:
            pass
    return defaults


def save_settings(settings):
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=4)


def read_geometry():
    if not os.path.exists(RC_GLSL):
        return 0, 660, 1600, 200
    with open(RC_GLSL) as f:
        content = f.read()
    m = re.search(r'#request\s+setgeometry\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)', content)
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
    return 0, 660, 1600, 200


def write_geometry(x, y, w, h):
    if not os.path.exists(RC_GLSL):
        return False
    with open(RC_GLSL) as f:
        content = f.read()
    new = re.sub(
        r'(#request\s+setgeometry\s+)\d+\s+\d+\s+\d+\s+\d+',
        f'\\g<1>{x} {y} {w} {h}',
        content
    )
    with open(RC_GLSL, "w") as f:
        f.write(new)
    return True

def get_bing_region():
    downloader = os.path.join(BIN_DIR, "bing-downloader.sh")
    if not os.path.exists(downloader):
        return "de-DE"
    with open(downloader) as f:
        content = f.read()
    m = re.search(r'mkt=([a-z]{2}-[A-Z]{2})', content)
    return m.group(1) if m else "de-DE"


def set_bing_region(region):
    downloader = os.path.join(BIN_DIR, "bing-downloader.sh")
    if not os.path.exists(downloader):
        return False
    with open(downloader) as f:
        content = f.read()
    new = re.sub(r'mkt=[a-z]{2}-[A-Z]{2}', f'mkt={region}', content)
    with open(downloader, "w") as f:
        f.write(new)
    return True


class GlavaControlCenter:
    def __init__(self, root):
        self.root = root
        self.settings = load_settings()
        self.T = load_lang(self.settings.get("lang", "pl"))
        self.langs = available_langs()
        self.current_colors = {"top": "#ffffff", "mid": "#888888", "bottom": "#000000"}
        self.presets = {}
        self.load_presets()
        self.root.title(self.T.get("title", "GLava Master Panel"))
        self.root.resizable(True, True)
        self.build_ui()
        self.update_status()

    def build_ui(self):
        for w in self.root.winfo_children():
            w.destroy()
        T = self.T

        # --- Pasek górny ---
        top_bar = tk.Frame(self.root)
        top_bar.pack(fill="x", padx=10, pady=(8, 2))
        tk.Label(top_bar, text=T.get("title", "GLava Master Panel"),
                 font=("Arial", 11, "bold")).pack(side="left")
        lang_frame = tk.Frame(top_bar)
        lang_frame.pack(side="right")
        tk.Label(lang_frame, text=T.get("section_language", "Język") + ":",
                 font=("Arial", 9)).pack(side="left", padx=(0, 4))
        self.lang_var = tk.StringVar(value=self.settings.get("lang", "pl"))
        lang_cb = ttk.Combobox(lang_frame, textvariable=self.lang_var,
                                values=list(self.langs.keys()), width=5, state="readonly")
        lang_cb.pack(side="left")
        lang_cb.bind("<<ComboboxSelected>>", self.change_language)

        # --- WIERSZ 1: Kolorystyka + Tryby ---
        row1 = tk.Frame(self.root)
        row1.pack(fill="x", padx=10, pady=4)

        # Kolorystyka
        cf = tk.LabelFrame(row1, text=T.get("section_colors", "Kolorystyka"),
                            font=("Arial", 9, "bold"), padx=6, pady=6)
        cf.pack(side="left", fill="both", expand=True, padx=(0, 4))

        btn_row = tk.Frame(cf)
        btn_row.pack(fill="x", pady=(0, 6))
        for key in ["top", "mid", "bottom"]:
            lbl = T.get(f"btn_{key}", key)
            btn = tk.Button(btn_row, text=lbl, command=lambda k=key: self.pick_color(k),
                            bg=self.current_colors[key], width=8, height=2)
            btn.pack(side="left", padx=2)
            setattr(self, f"btn_{key}", btn)

        tk.Button(cf, text=T.get("btn_apply_manual", "Zastosuj (ręczny)"),
                  command=self.apply_manual, bg="#2e7d32", fg="white",
                  font=("Arial", 9, "bold")).pack(fill="x", pady=(0, 3))
        tk.Button(cf, text=T.get("btn_capture", "Pobierz z ekranu"),
                  command=self.capture_current, bg="#f39c12", fg="white").pack(fill="x")

        # Tryby
        mf = tk.LabelFrame(row1, text=T.get("section_modes", "Tryby"),
                            font=("Arial", 9, "bold"), padx=6, pady=6)
        mf.pack(side="left", fill="both", expand=True, padx=(4, 0))
        tk.Button(mf, text=T.get("btn_fetch_wallpaper", "Pobierz tapetę Bing (pulpit)"),
                  command=self.fetch_wallpaper_no_lightdm, bg="#1565c0", fg="white"
                  ).pack(fill="x", pady=(0, 3))
        tk.Button(mf, text=T.get("btn_fetch_wallpaper_full", "Pobierz tapetę Bing (pulpit + logowanie)"),
                  command=self.fetch_wallpaper_full, bg="#0d47a1", fg="white"
                  ).pack(fill="x", pady=(0, 6))
        tk.Button(mf, text=T.get("btn_restore_auto", "Przywróć Bing (auto)"),
                  command=self.restore_auto, bg="#37474f", fg="white").pack(fill="x", pady=(0, 3))
        tk.Button(mf, text=T.get("btn_toggle_glava", "Włącz / Wyłącz GLava"),
                  command=self.run_toggle, bg="#424242", fg="white").pack(fill="x")

        # --- WIERSZ 2: Profile + Geometria ---
        row2 = tk.Frame(self.root)
        row2.pack(fill="x", padx=10, pady=4)

        # Profile
        pf = tk.LabelFrame(row2, text=T.get("section_profiles", "Profile kolorów"),
                            font=("Arial", 9, "bold"), padx=6, pady=6)
        pf.pack(side="left", fill="both", expand=True, padx=(0, 4))
        self.listbox = tk.Listbox(pf, height=5, font=("Arial", 9))
        self.listbox.pack(fill="x", pady=(0, 6))
        self.refresh_listbox()
        bp = tk.Frame(pf)
        bp.pack(fill="x")
        tk.Button(bp, text=T.get("btn_load", "Wczytaj"),
                  command=self.load_selected_preset, bg="#546e7a", fg="white",
                  width=9).pack(side="left", padx=(0, 3), expand=True)
        tk.Button(bp, text=T.get("btn_save_new", "Zapisz nowy"),
                  command=self.save_new_preset, bg="#546e7a", fg="white",
                  width=9).pack(side="left", padx=(0, 3), expand=True)
        tk.Button(bp, text=T.get("btn_delete", "Usuń"),
                  command=self.delete_preset, bg="#b71c1c", fg="white",
                  width=6).pack(side="left")

        # Geometria
        gf = tk.LabelFrame(row2, text=T.get("section_geometry", "Geometria GLava"),
                            font=("Arial", 9, "bold"), padx=6, pady=6)
        gf.pack(side="left", fill="both", expand=True, padx=(4, 0))
        gx, gy, gw, gh = read_geometry()
        self.geo_vars = {}
        geo_grid = tk.Frame(gf)
        geo_grid.pack(fill="x", pady=(0, 6))
        for i, (key, val, lbl) in enumerate([
            ("x", gx, T.get("label_x", "X")),
            ("y", gy, T.get("label_y", "Y")),
            ("w", gw, T.get("label_w", "Szer.")),
            ("h", gh, T.get("label_h", "Wys.")),
        ]):
            tk.Label(geo_grid, text=lbl, font=("Arial", 9), width=4
                     ).grid(row=i//2, column=(i%2)*2, sticky="e", padx=(0, 2), pady=2)
            var = tk.StringVar(value=str(val))
            self.geo_vars[key] = var
            tk.Entry(geo_grid, textvariable=var, width=7, font=("Arial", 9)
                     ).grid(row=i//2, column=(i%2)*2+1, padx=(0, 8), pady=2)
        tk.Button(gf, text=T.get("btn_detect_resolution", "Wykryj rozdzielczość"),
                  command=self.detect_resolution, font=("Arial", 9)
                  ).pack(fill="x", pady=(0, 4))
        tk.Button(gf, text=T.get("btn_apply_geometry", "Zastosuj geometrię"),
                  command=self.apply_geometry, bg="#1565c0", fg="white",
                  font=("Arial", 9)).pack(fill="x")

        # --- WIERSZ 3: Ustawienia ---
        sf = tk.LabelFrame(self.root, text=T.get("section_settings", "Ustawienia"),
                           font=("Arial", 9, "bold"), padx=8, pady=6)
        sf.pack(fill="x", padx=10, pady=4)
        s_row = tk.Frame(sf)
        s_row.pack(fill="x")
        tk.Label(s_row, text=T.get("label_region", "Region Bing") + ":",
                 font=("Arial", 9)).pack(side="left")
        self.region_var = tk.StringVar(value=get_bing_region())
        ttk.Combobox(s_row, textvariable=self.region_var, values=BING_REGIONS,
                     width=8, state="readonly").pack(side="left", padx=(4, 16))
        tk.Button(s_row, text=T.get("btn_save_settings", "Zapisz ustawienia"),
                  command=self.save_settings_action, font=("Arial", 9)).pack(side="left")

        # --- STATUS ---
        self.status_label = tk.Label(self.root, text="...",
                                      font=("Arial", 9, "italic"), anchor="w")
        self.status_label.pack(fill="x", padx=12, pady=(2, 8))

    # -------------------------------------------------------------------------
    def change_language(self, event=None):
        lang = self.lang_var.get()
        self.settings["lang"] = lang
        save_settings(self.settings)
        self.T = load_lang(lang)
        self.root.title(self.T.get("title", "GLava Master Panel"))
        self.build_ui()

    def load_presets(self):
        if os.path.exists(PRESETS_FILE):
            try:
                with open(PRESETS_FILE) as f:
                    self.presets = json.load(f)
                if "LAST_SESSION" in self.presets:
                    self.current_colors = self.presets["LAST_SESSION"]
            except Exception:
                self.presets = {}

    def save_presets_to_file(self):
        self.presets["LAST_SESSION"] = self.current_colors
        with open(PRESETS_FILE, "w") as f:
            json.dump(self.presets, f, indent=4)

    def refresh_listbox(self):
        self.listbox.delete(0, tk.END)
        for name in sorted(self.presets.keys()):
            if name != "LAST_SESSION":
                self.listbox.insert(tk.END, name)

    def save_new_preset(self):
        name = simpledialog.askstring(
            self.T.get("dialog_profile_title", "Nowy profil"),
            self.T.get("dialog_profile_name", "Podaj nazwę:"))
        if name:
            self.presets[name] = self.current_colors.copy()
            self.save_presets_to_file()
            self.refresh_listbox()

    def load_selected_preset(self):
        sel = self.listbox.curselection()
        if sel:
            name = self.listbox.get(sel[0])
            self.current_colors = self.presets[name].copy()
            for key in ["top", "mid", "bottom"]:
                getattr(self, f"btn_{key}").config(bg=self.current_colors[key])
            self.apply_manual()

    def delete_preset(self):
        sel = self.listbox.curselection()
        if sel:
            name = self.listbox.get(sel[0])
            if messagebox.askyesno("", f"{self.T.get('dialog_delete_confirm', 'Usuń')} '{name}'?"):
                del self.presets[name]
                self.save_presets_to_file()
                self.refresh_listbox()

    def pick_color(self, key):
        color = colorchooser.askcolor(color=self.current_colors[key])[1]
        if color:
            self.current_colors[key] = color
            getattr(self, f"btn_{key}").config(bg=color)
            self.save_presets_to_file()

    def apply_manual(self):
        open(FLAG_RED, "a").close()
        open(FLAG_MANUAL, "a").close()
        if not os.path.exists(REDFRAG):
            messagebox.showerror("", f"{self.T.get('error_no_template', 'Brak szablonu')}:\n{REDFRAG}")
            return
        with open(REDFRAG) as f:
            lines = f.readlines()
        os.makedirs(os.path.dirname(LIVEFRAG), exist_ok=True)
        with open(LIVEFRAG, "w") as f:
            for line in lines:
                written = False
                for k in ["bottom", "mid", "top"]:
                    if f"vec3 {k}" in line:
                        rgb = tuple(int(self.current_colors[k].lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
                        vec = "vec3({:.2f}, {:.2f}, {:.2f})".format(rgb[0]/255, rgb[1]/255, rgb[2]/255)
                        f.write(f"vec3 {k} = {vec};\n")
                        written = True
                        break
                if not written:
                    f.write(line)
        self.save_presets_to_file()
        self.restart_glava()

    def capture_current(self):
        if not os.path.exists(LIVEFRAG):
            return
        with open(LIVEFRAG) as f:
            content = f.read()
        for key in ["bottom", "mid", "top"]:
            m = re.search(rf"vec3\s+{key}\s*=\s*vec3\s*\((.*?)\)\s*;", content)
            if m:
                vals = [float(v.strip()) for v in m.group(1).split(",")]
                hex_c = "#%02x%02x%02x" % (int(vals[0]*255), int(vals[1]*255), int(vals[2]*255))
                self.current_colors[key] = hex_c
                getattr(self, f"btn_{key}").config(bg=hex_c)

    def fetch_wallpaper_no_lightdm(self):
        """Pobiera tapetę Bing — tylko pulpit, bez sudo (bing-fetch-user.sh)"""
        self.root.focus()
        fetcher = os.path.join(BIN_DIR, "bing-fetch-user.sh")
        subprocess.Popen(["/bin/bash", fetcher, "--force"])
        self.root.after(4000, self.update_status)

    def fetch_wallpaper_full(self):
        """Pobiera tapetę Bing — pulpit + ekran logowania LightDM (--force)"""
        self.root.focus()
        downloader = os.path.join(BIN_DIR, "bing-downloader.sh")
        sudo_run([downloader, "--force"])
        self.root.after(3000, self.update_status)

    def fetch_wallpaper(self):
        """Alias dla save_settings_action — pobiera z pulpitem tylko"""
        self.fetch_wallpaper_no_lightdm()

    def restore_auto(self):
        for flag in (FLAG_RED, FLAG_MANUAL):
            if os.path.exists(flag):
                os.remove(flag)
        subprocess.Popen(["/bin/bash", os.path.join(BIN_DIR, "glava-colors-auto")])
        self.root.after(1000, self.update_status)

    def run_toggle(self):
        subprocess.run(["/bin/bash", os.path.join(BIN_DIR, "glava-toggle")])
        self.root.after(500, self.update_status)

    def detect_resolution(self):
        try:
            result = subprocess.run(["xrandr", "--current"], capture_output=True, text=True)
            m = re.search(r'current (\d+) x (\d+)', result.stdout)
            if m:
                self.geo_vars["x"].set("0")
                self.geo_vars["w"].set(m.group(1))
        except Exception:
            pass

    def apply_geometry(self):
        try:
            x = int(self.geo_vars["x"].get())
            y = int(self.geo_vars["y"].get())
            w = int(self.geo_vars["w"].get())
            h = int(self.geo_vars["h"].get())
        except ValueError:
            return
        if write_geometry(x, y, w, h):
            messagebox.showinfo("", self.T.get("geometry_applied", "Geometria zaktualizowana."))
            self.restart_glava()

    def save_settings_action(self):
        region = self.region_var.get()
        set_bing_region(region)
        self.settings["bing_region"] = region
        save_settings(self.settings)
        self.root.focus()
        messagebox.showinfo("", self.T.get("settings_saved", "Zapisano."))

    def restart_glava(self):
        subprocess.run(["pkill", "-x", "glava"])
        self.root.after(500, lambda: subprocess.Popen(
            ["glava", "--desktop"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))

    def update_status(self):
        T = self.T
        res = subprocess.run(["pgrep", "-x", "glava"], capture_output=True)
        running = res.returncode == 0
        if running:
            if os.path.exists(FLAG_MANUAL):
                mode = T.get("mode_manual", "tryb ręczny")
            elif os.path.exists(FLAG_RED):
                mode = T.get("mode_red", "tryb RED")
            else:
                mode = T.get("mode_auto", "tryb AUTO")
            status = f"● {T.get('status_active', 'GLava aktywna')} [{mode}]"
            color = "green"
        else:
            status = f"○ {T.get('status_inactive', 'GLava wyłączona')}"
            color = "red"
        if os.path.exists(WALLPAPER):
            dt = datetime.datetime.fromtimestamp(os.path.getmtime(WALLPAPER)).strftime("%d %b %Y %H:%M")
            status += f"   |   {T.get('label_wallpaper', 'Tapeta')}: {dt}"
        else:
            status += f"   |   {T.get('label_no_wallpaper', 'brak tapety')}"
        self.status_label.config(text=status, fg=color)
        self.root.after(3000, self.update_status)


if __name__ == "__main__":
    root = tk.Tk()
    GlavaControlCenter(root)
    root.mainloop()
