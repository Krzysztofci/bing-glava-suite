#!/usr/bin/env python3
# =============================================================================
# glava-gui.py
# Graficzny panel sterowania GLava. Pozwala na ręczny dobór kolorów,
# zapis/wczytywanie presetów, przełączanie trybów i toggle GLava.
#
# Flagi ustawiane przez GUI:
#   manual.shift — blokuje daemon przed nadpisaniem kolorów ustawionych ręcznie
#   red.shift    — aktywuje preset czerwony (ustawiany przez glava-colorswitch)
# Obie flagi są usuwane przez "Przywróć Bing (auto)" → glava-colors-auto.
# =============================================================================

import tkinter as tk
from tkinter import colorchooser, messagebox, simpledialog
import os
import subprocess
import re
import json

# --- Ścieżki (oparte na $HOME, bez hardkodowania użytkownika) ---
USER_HOME    = os.path.expanduser("~")
CONFIG_DIR   = os.path.join(USER_HOME, ".config/glava")
BIN_DIR      = os.path.join(USER_HOME, ".local/bin")
LIVEFRAG     = os.path.join(CONFIG_DIR, "graph/1.frag")
REDFRAG      = os.path.join(CONFIG_DIR, "graph_red.frag")
FLAG_RED     = os.path.join(CONFIG_DIR, "red.shift")
FLAG_MANUAL  = os.path.join(CONFIG_DIR, "manual.shift")
PRESETS_FILE = os.path.join(CONFIG_DIR, "presets.json")


class GlavaControlCenter:
    def __init__(self, root):
        self.root = root
        self.root.title("GLava Master Panel")
        self.root.geometry("400x820")

        self.current_colors = {"top": "#ffffff", "mid": "#888888", "bottom": "#000000"}
        self.presets = {}
        self.load_presets()

        container = tk.Frame(root, padx=20, pady=10)
        container.pack(fill="both", expand=True)

        # --- SEKCJA: KOLORY ---
        tk.Label(container, text="KOLORYSTYKA",
                 font=("Arial", 11, "bold")).pack(pady=(0, 5))

        c_frame = tk.Frame(container)
        c_frame.pack(pady=5)
        for key in ["top", "mid", "bottom"]:
            lbl = "Góra" if key == "top" else "Środek" if key == "mid" else "Dół"
            btn = tk.Button(c_frame, text=lbl,
                            command=lambda k=key: self.pick_color(k),
                            bg=self.current_colors[key], width=10, height=2)
            btn.pack(side="left", padx=3)
            setattr(self, f"btn_{key}", btn)

        tk.Button(container, text="ZASTOSUJ KOLORY (TRYB RĘCZNY)",
                  command=self.apply_manual,
                  bg="#2e7d32", fg="white",
                  font=("Arial", 10, "bold"), height=2).pack(fill="x", pady=5)

        tk.Button(container, text="POBIERZ AKTUALNE Z EKRANU",
                  command=self.capture_current,
                  bg="#f39c12", fg="white").pack(fill="x", pady=2)

        # --- SEKCJA: PROFILE (PRESETY) ---
        tk.Frame(container, height=2, bd=1,
                 relief="sunken").pack(fill="x", pady=15)
        tk.Label(container, text="TWOJE PROFILE KOLORÓW",
                 font=("Arial", 11, "bold")).pack(pady=(0, 5))

        self.listbox = tk.Listbox(container, height=6, font=("Arial", 10))
        self.listbox.pack(fill="x", pady=5)
        self.refresh_listbox()

        btn_p_frame = tk.Frame(container)
        btn_p_frame.pack(fill="x")
        tk.Button(btn_p_frame, text="WCZYTAJ",
                  command=self.load_selected_preset,
                  bg="#546e7a", fg="white", width=12).pack(side="left", padx=5, expand=True)
        tk.Button(btn_p_frame, text="ZAPISZ NOWY",
                  command=self.save_new_preset,
                  bg="#546e7a", fg="white", width=12).pack(side="left", padx=5, expand=True)
        tk.Button(btn_p_frame, text="USUŃ",
                  command=self.delete_preset,
                  bg="#b71c1c", fg="white", width=8).pack(side="left", padx=5)

        # --- SEKCJA: STEROWANIE TRYBAMI ---
        tk.Frame(container, height=2, bd=1,
                 relief="sunken").pack(fill="x", pady=15)
        tk.Label(container, text="TRYBY I SKRYPTY",
                 font=("Arial", 11, "bold")).pack(pady=(0, 5))

        tk.Button(container, text="TRYB RED / BING (SWITCH)",
                  command=self.run_colorswitch,
                  bg="#c62828", fg="white", height=2).pack(fill="x", pady=3)

        tk.Button(container, text="PRZYWRÓĆ BING (AUTO)",
                  command=self.restore_auto,
                  bg="#1565c0", fg="white", height=2).pack(fill="x", pady=3)

        tk.Button(container, text="WŁĄCZ / WYŁĄCZ GLAVA",
                  command=self.run_toggle,
                  bg="#424242", fg="white").pack(fill="x", pady=(15, 0))

        # --- STATUS ---
        self.status_label = tk.Label(container, text="Status: ...",
                                     font=("Arial", 9, "italic"))
        self.status_label.pack(side="bottom", pady=5)
        self.update_status()

    # -------------------------------------------------------------------------
    # PRESETY
    # -------------------------------------------------------------------------
    def load_presets(self):
        if os.path.exists(PRESETS_FILE):
            try:
                with open(PRESETS_FILE, 'r') as f:
                    self.presets = json.load(f)
                if "LAST_SESSION" in self.presets:
                    self.current_colors = self.presets["LAST_SESSION"]
            except Exception:
                self.presets = {}

    def save_presets_to_file(self):
        self.presets["LAST_SESSION"] = self.current_colors
        with open(PRESETS_FILE, 'w') as f:
            json.dump(self.presets, f, indent=4)

    def refresh_listbox(self):
        self.listbox.delete(0, tk.END)
        for name in sorted(self.presets.keys()):
            if name != "LAST_SESSION":
                self.listbox.insert(tk.END, name)

    def save_new_preset(self):
        name = simpledialog.askstring("Nowy Profil", "Podaj nazwę profilu:")
        if name:
            self.presets[name] = self.current_colors.copy()
            self.save_presets_to_file()
            self.refresh_listbox()

    def load_selected_preset(self):
        selection = self.listbox.curselection()
        if selection:
            name = self.listbox.get(selection[0])
            self.current_colors = self.presets[name].copy()
            for key in ["top", "mid", "bottom"]:
                getattr(self, f"btn_{key}").config(bg=self.current_colors[key])
            self.apply_manual()

    def delete_preset(self):
        selection = self.listbox.curselection()
        if selection:
            name = self.listbox.get(selection[0])
            if messagebox.askyesno("Usuń", f"Czy na pewno usunąć profil '{name}'?"):
                del self.presets[name]
                self.save_presets_to_file()
                self.refresh_listbox()

    # -------------------------------------------------------------------------
    # AKCJE
    # -------------------------------------------------------------------------
    def run_colorswitch(self):
        subprocess.Popen(["/bin/bash", os.path.join(BIN_DIR, "glava-colorswitch")])
        self.root.after(1000, self.update_status)

    def restore_auto(self):
        # Usuń obie flagi ręczne — glava-colors-auto też je usuwa, ale dla pewności
        for flag in (FLAG_RED, FLAG_MANUAL):
            if os.path.exists(flag):
                os.remove(flag)
        subprocess.Popen(["/bin/bash", os.path.join(BIN_DIR, "glava-colors-auto")])
        self.root.after(1000, self.update_status)

    def run_toggle(self):
        subprocess.run(["/bin/bash", os.path.join(BIN_DIR, "glava-toggle")])
        self.root.after(500, self.update_status)

    def pick_color(self, key):
        color = colorchooser.askcolor(color=self.current_colors[key])[1]
        if color:
            self.current_colors[key] = color
            getattr(self, f"btn_{key}").config(bg=color)
            self.save_presets_to_file()

    def apply_manual(self):
        """Zapisuje wybrane kolory do aktywnego shadera i blokuje daemon."""
        # Ustaw obie flagi — daemon nie będzie nadpisywał
        open(FLAG_RED, 'a').close()
        open(FLAG_MANUAL, 'a').close()

        if not os.path.exists(REDFRAG):
            messagebox.showerror("Błąd", f"Brak pliku szablonu:\n{REDFRAG}")
            return

        with open(REDFRAG, 'r') as f:
            lines = f.readlines()

        os.makedirs(os.path.dirname(LIVEFRAG), exist_ok=True)

        with open(LIVEFRAG, 'w') as f:
            for line in lines:
                written = False
                for k in ["bottom", "mid", "top"]:
                    if f'vec3 {k}' in line:
                        rgb = tuple(
                            int(self.current_colors[k].lstrip('#')[i:i+2], 16)
                            for i in (0, 2, 4))
                        vec = "vec3({:.2f}, {:.2f}, {:.2f})".format(
                            rgb[0] / 255, rgb[1] / 255, rgb[2] / 255)
                        f.write(f"vec3 {k} = {vec};\n")
                        written = True
                        break
                if not written:
                    f.write(line)

        self.save_presets_to_file()
        self.restart_glava()

    def capture_current(self):
        """Odczytuje kolory z aktywnego shadera i wyświetla je w GUI."""
        if not os.path.exists(LIVEFRAG):
            return
        with open(LIVEFRAG, 'r') as f:
            content = f.read()
        for key in ["bottom", "mid", "top"]:
            pattern = rf'vec3\s+{key}\s*=\s*vec3\s*\((.*?)\)\s*;'
            match = re.search(pattern, content)
            if match:
                vals = [float(v.strip()) for v in match.group(1).split(',')]
                hex_c = '#%02x%02x%02x' % (
                    int(vals[0] * 255), int(vals[1] * 255), int(vals[2] * 255))
                self.current_colors[key] = hex_c
                getattr(self, f"btn_{key}").config(bg=hex_c)

    def restart_glava(self):
        subprocess.run(["pkill", "-x", "glava"])
        self.root.after(500, lambda: subprocess.Popen(
            ["glava", "--desktop"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL))

    def update_status(self):
        res = subprocess.run(["pgrep", "-x", "glava"], capture_output=True)
        running = res.returncode == 0
        mode = ""
        if running:
            if os.path.exists(FLAG_MANUAL):
                mode = " [tryb ręczny]"
            elif os.path.exists(FLAG_RED):
                mode = " [tryb RED]"
            else:
                mode = " [tryb AUTO]"
        status = ("● GLAVA AKTYWNA" + mode) if running else "○ GLAVA WYŁĄCZONA"
        self.status_label.config(
            text=status, fg="green" if running else "red")
        self.root.after(3000, self.update_status)


if __name__ == "__main__":
    root = tk.Tk()
    GlavaControlCenter(root)
    root.mainloop()
