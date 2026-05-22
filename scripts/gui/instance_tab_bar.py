# =============================================================================
# gui/instance_tab_bar.py
# InstanceTabBar — tab bar dla instancji GLava.
#
# Architektura:
#   - ttk.Notebook (height=0) — tylko pasek zakładek, bez klienta
#   - ttk.Menubutton [+] obok Notebooka w tym samym wierszu
#   - _content_frame ponizej — na pelnej szerokosci, pokazuje frame
#     aktywnej zakladki
#   - Kazda zakladka ma: dummy frame w Notebooku + content frame w _content_frame
#
# Callbacki (wszystkie opcjonalne):
#   on_select(inst_id)
#   on_add(module_name)
#   on_load_workspace()
#   on_close(inst_id)
#   on_action(inst_id, action)
# =============================================================================

import tkinter as tk
from tkinter import ttk, simpledialog

_GLAVA_MODULES = ["bars", "wave", "circle", "graph", "radial"]

_CONTEXT_ACTIONS = [
    ("rename",         "Zmien nazwe"),
    None,
    ("change_shader",  "Zmien shader"),
    None,
    ("save_session",   "Zapisz sesje"),
    ("save_workspace", "Zapisz workspace"),
    ("duplicate",      "Duplikuj"),
    None,
    ("close",          "Zamknij"),
]

class InstanceTabBar(ttk.Frame):
    """
    Tab bar dla instancji GLava.

    Uzycie:
        bar = InstanceTabBar(parent, on_select=..., on_add=..., ...)
        bar.pack(fill="both", expand=True)
        bar.add_tab(inst_id=1, module="bars")
        frame = bar.get_frame(1)   # wsadz tu zawartosc instancji
    """

    def __init__(self, parent,
                 on_select=None,
                 on_add=None,
                 on_load_workspace=None,
                 on_save_workspace=None,
                 on_close=None,
                 on_action=None,
                 modules=None,
                 content_parent=None,
                 **kw):
        super().__init__(parent, **kw)

        self._on_select         = on_select
        self._on_add            = on_add
        self._on_load_workspace = on_load_workspace
        self._on_save_workspace = on_save_workspace
        self._on_close          = on_close
        self._on_action         = on_action
        self._modules           = modules or _GLAVA_MODULES
        self._content_parent    = content_parent  # None = uzyj self

        # inst_id -> {"label", "dummy", "content"}
        self._tabs:          dict = {}
        self._module_counts: dict = {}
        self._idx_to_id:     dict = {}

        self._build()

    # -------------------------------------------------------------------------
    # Budowa
    # -------------------------------------------------------------------------

    def _build(self):
        # Główny kontener
        self.nav_container = ttk.Frame(self)
        self.nav_container.pack(side="top", fill="x")

        # Używamy grid zamiast pack dla tab_row
        tab_row = ttk.Frame(self.nav_container)
        tab_row.grid(row=0, column=0, sticky="ew")
        self.nav_container.grid_columnconfigure(0, weight=1)

        style = ttk.Style()

        # POBIERANIE KOLORÓW Z MOTYWU
        # Pobieramy kolor tła i akcentu, aby nie wpisywać ich ręcznie
        bg_color = style.lookup("TFrame", "background")
        fg_color = style.lookup("TLabel", "foreground")
        # Kolor separatora pobrany z obramowania przycisków lub ramki
        border_color = style.lookup("TButton", "bordercolor") or "#454545"

        # 1. LAYOUT Notebooka
        style.layout("Borderless.TNotebook", [
            ('Notebook.tab', {'sticky': 'nswe'})
        ])

        # 2. KONFIGURACJA STYLU (używamy zmiennych bg_color)
        style.configure("Borderless.TNotebook",
                        borderwidth=0,
                        highlightthickness=0,
                        padding=0,
                        tabmargins=[2, 5, 2, 0])

        style.configure("Borderless.TNotebook.Tab",
                        focusthickness=0,
                        focuscolor="",
                        borderwidth=0,
                        padding=[0, 0])

        # Mapowanie kolorów - teraz pobieranych dynamicznie
        style.map("Borderless.TNotebook.Tab",
                  background=[("selected", bg_color), ("active", bg_color)],
                  lightcolor=[("selected", bg_color)],
                  bordercolor=[("selected", bg_color)],
                  darkcolor=[("selected", bg_color)])

        # 3. NOTEBOOK i PRZYCISK w GRIDzie
        self._nb = ttk.Notebook(tab_row, style="Borderless.TNotebook")
        self._nb.grid(row=0, column=0, sticky="sw")

        style.configure("TabAdd.Toolbutton",
                        padding=[4, 0],
                        relief="flat",
                        borderwidth=0)

        self._btn_add = ttk.Menubutton(
            tab_row,
            text="\u271a",
            style="TabAdd.Toolbutton",
            width=2
        )
        # sticky="s" trzyma przycisk przy dolnej krawędzi wiersza
        self._btn_add.grid(row=0, column=1, sticky="s", padx=2, pady=(0, 2))
        style.configure("TabWS.Toolbutton", padding=[4, 0], relief="flat", borderwidth=0, font=("TkDefaultFont", 10, "bold"))
        self._btn_save_ws = ttk.Button(
            tab_row, text="🖫",
            style="TabWS.Toolbutton", width=2,
            command=lambda: self._call("on_save_workspace")
        )
        self._btn_save_ws.grid(row=0, column=2, sticky="s", padx=2, pady=(0, 2))
        self._btn_load_ws = ttk.Button(
            tab_row, text="🗁",
            style="TabWS.Toolbutton", width=2,
            command=lambda: self._call("on_load_workspace")
        )
        self._btn_load_ws.grid(row=0, column=3, sticky="s", padx=2, pady=(0, 2))

        # 4. SEPARATOR w GRIDzie (row 1)
        self._line = tk.Frame(self.nav_container, height=1, bg=border_color)
        self._line.grid(row=1, column=0, sticky="ew")

        # 5. CONTENT FRAME — jesli podano content_parent, uzyj go jako rodzica
        cp = self._content_parent if self._content_parent is not None else self
        self._content_frame = ttk.Frame(cp)
        self._content_frame.pack(side="top", fill="both", expand=True)

        # Menu i bindy bez zmian
        self._add_menu = tk.Menu(self._btn_add, tearoff=False)
        self._btn_add.configure(menu=self._add_menu)
        self._rebuild_add_menu()

        self._nb.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        self._nb.bind("<Button-3>",             self._on_right_click)
        self._nb.bind("<Button-1>", self._on_tab_click_force)
    # -------------------------------------------------------------------------
    # Menu [+]
    # -------------------------------------------------------------------------

    def _rebuild_add_menu(self):
        style = ttk.Style()
        bg = style.lookup("TFrame", "background") or "#313131"
        fg = style.lookup("TLabel", "foreground") or "#eeeeee"
        
        # Odświeżamy wygląd istniejącego menu przed jego wypełnieniem
        self._add_menu.configure(
            bg=bg,
            fg=fg,
            activebackground="#217346",
            activeforeground="#ffffff",
            bd=1,
            relief="flat"
        )
        
        self._add_menu.delete(0, "end")
        for mod in self._modules:
            self._add_menu.add_command(
                label=mod,
                command=lambda m=mod: self._call("on_add", m))
        self._add_menu.add_separator(background=bg)
        self._add_menu.add_command(
            label="Wczytaj zestaw...",
            command=lambda: self._call("on_load_workspace"))

    # -------------------------------------------------------------------------
    # Menu kontekstowe (prawy klik)
    # -------------------------------------------------------------------------

    def _on_right_click(self, event):
        try:
            idx = self._nb.index(f"@{event.x},{event.y}")
        except tk.TclError:
            return
        inst_id = self._idx_to_id.get(idx)
        if inst_id is None:
            return

        style = ttk.Style()
        # Pobieramy kolory z motywu z bezpiecznymi zamiennikami (fallback)
        bg = style.lookup("TFrame", "background") or "#313131"
        fg = style.lookup("TLabel", "foreground") or "#eeeeee"
        
        # Wybór koloru akcentu (zielony dla dark, niebieski/szary dla innych)
        curr_theme = style.theme_use().lower()
        select_bg = "#217346" if "dark" in curr_theme else "#0078d4"
        active_fg = "#ffffff"

        # TWORZENIE MENU - Kluczowe: usunięcie starych ramek i cieni
        menu = tk.Menu(self._nb, 
                       tearoff=False,
                       bg=bg,
                       fg=fg,
                       activebackground=select_bg,
                       activeforeground=active_fg,
                       bd=1,
                       relief="flat",
                       activeborderwidth=0) # Dodatkowe wyłączenie ramek przy wyborze

        for item in _CONTEXT_ACTIONS:
            if item is None:
                menu.add_separator(background=bg)
            else:
                key, lbl = item
                if key == "close":
                    menu.add_command(label=lbl, command=lambda i=inst_id: self._call("on_close", i))
                elif key == "rename":
                    menu.add_command(label=lbl, command=lambda i=inst_id: self._nb.after(1, lambda: self._do_rename(i)))
                elif key == "change_shader":
                    submenu = tk.Menu(menu, tearoff=False,
                                      bg=bg, fg=fg,
                                      activebackground=select_bg,
                                      activeforeground=active_fg,
                                      bd=1, relief="flat")
                    for mod in _GLAVA_MODULES:
                        submenu.add_command(
                            label=mod,
                            command=lambda i=inst_id, m=mod: self._call("on_action", i, "change_shader", m))
                    menu.add_cascade(label=lbl, menu=submenu)
                else:
                    menu.add_command(label=lbl, command=lambda i=inst_id, k=key: self._call("on_action", i, k))
        
        menu.tk_popup(event.x_root, event.y_root)
    def _do_rename(self, inst_id):
        if inst_id not in self._tabs:
            return
        current = self._tabs[inst_id]["label"]
        new_name = simpledialog.askstring(
            "Zmien nazwe", "Nowa nazwa zakladki:",
            initialvalue=current, parent=self._nb)
        if new_name and new_name.strip():
            name = new_name.strip()
            self._tabs[inst_id]["label"] = name
            try:
                self._nb.tab(self._tabs[inst_id]["dummy"], text=name)
            except tk.TclError:
                pass
            self._call("on_action", inst_id, "rename")

    # -------------------------------------------------------------------------
    # Zmiana aktywnej zakladki
    # -------------------------------------------------------------------------

    def _on_tab_changed(self, event=None):
        try:
            idx = self._nb.index("current")
        except tk.TclError:
            return
        inst_id = self._idx_to_id.get(idx)
        if inst_id is not None:
            self._show_content(inst_id)
            self._call("on_select", inst_id)

    def _show_content(self, inst_id):
        """Pokazuje content frame aktywnej zakladki, chowa pozostale."""
        for iid, data in self._tabs.items():
            if iid == inst_id:
                data["content"].pack(fill="both", expand=True)
            else:
                data["content"].pack_forget()

    # -------------------------------------------------------------------------
    # Publiczne API
    # -------------------------------------------------------------------------

    def add_tab(self, inst_id, module: str, label: str = None,
                select: bool = True):
        if inst_id in self._tabs:
            return

        # Zawsze inkrementuj licznik modulu — nawet gdy label jest przekazany z zewnatrz.
        # Dzieki temu duplikat zawsze dostanie kolejny numer.
        cnt = self._module_counts.get(module, 0) + 1
        self._module_counts[module] = cnt

        if label is None:
            name  = module.capitalize()
            label = f"{name} \u2726" if cnt == 1 else f"{name} \u2726{cnt}"

        # Pusty dummy w Notebooku (tylko zakładka)
        dummy = ttk.Frame(self._nb)
        self._nb.add(dummy, text=label)

        # Content frame w _content_frame (pelna szerokosc)
        content = ttk.Frame(self._content_frame)

        self._tabs[inst_id] = {
            "label":   label,
            "dummy":   dummy,
            "content": content,
        }
        self._refresh_idx_map()

        if select:
            try:
                self._nb.select(dummy)
            except tk.TclError:
                pass
            self._show_content(inst_id)

    def remove_tab(self, inst_id):
        if inst_id not in self._tabs:
            return
        data = self._tabs[inst_id]
        try:
            self._nb.forget(data["dummy"])
        except tk.TclError:
            pass
        data["dummy"].destroy()
        data["content"].destroy()
        del self._tabs[inst_id]
        self._refresh_idx_map()
        # Pokaz content nowej aktywnej zakladki
        try:
            idx     = self._nb.index("current")
            new_id  = self._idx_to_id.get(idx)
            if new_id:
                self._show_content(new_id)
        except tk.TclError:
            pass

    def set_label(self, inst_id, label: str):
        if inst_id not in self._tabs:
            return
        self._tabs[inst_id]["label"] = label
        try:
            self._nb.tab(self._tabs[inst_id]["dummy"], text=label)
        except tk.TclError:
            pass

    def get_frame(self, inst_id) -> ttk.Frame:
        """Zwraca content Frame — wsadz tu zawartosc instancji."""
        if inst_id in self._tabs:
            return self._tabs[inst_id]["content"]
        return None

    @property
    def active_id(self):
        try:
            idx = self._nb.index("current")
            return self._idx_to_id.get(idx)
        except tk.TclError:
            return None

    @property
    def notebook(self) -> ttk.Notebook:
        return self._nb

    @property
    def content_frame(self) -> ttk.Frame:
        """Ramka na zawartosc aktywnej zakladki (pelna szerokosc)."""
        return self._content_frame

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _refresh_idx_map(self):
        self._idx_to_id = {}
        dummies = {data["dummy"]: iid for iid, data in self._tabs.items()}
        for idx in range(self._nb.index("end")):
            try:
                tab_id = self._nb.tabs()[idx]
                for dummy, iid in dummies.items():
                    if str(dummy) == tab_id:
                        self._idx_to_id[idx] = iid
                        break
            except (tk.TclError, IndexError):
                pass

    def _call(self, cb_name: str, *args):
        cb = getattr(self, f"_{cb_name}", None)
        if cb is not None:
            cb(*args)

    def _on_tab_click_force(self, event):
    #"""Wymusza reakcję nawet na zieloną zakładkę."""
        try:
            idx = self._nb.index(f"@{event.x},{event.y}")
            inst_id = self._idx_to_id.get(idx)
        
            if inst_id is not None:
            # Nawet jeśli to ta sama zakładka, wywołujemy callback select
            # co pozwoli Ci wrócić z Main do widoku modułu
                self._show_content(inst_id)
                if self._on_select:
                    self._on_select(inst_id)
        except tk.TclError:
            pass

# =============================================================================
# Standalone smoke-test:   python3 gui/instance_tab_bar.py
# =============================================================================

if __name__ == "__main__":
    import os

    root = tk.Tk()
    root.title("InstanceTabBar smoke test v9")
    root.geometry("750x440")

    style = ttk.Style()
    _base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "themes")
    _dark_tcl = os.path.join(_base, "forest-dark.tcl")
    if os.path.exists(_dark_tcl):
        root.tk.call("source", _dark_tcl)
        style.theme_use("forest-dark")
        print("[info] forest-dark zaladowany")

    log = tk.Text(root, height=7, bg="#1a1a1a", fg="#aaffaa",
                  font=("Monospace", 9))
    log.pack(fill="x", side="bottom", padx=4, pady=4)

    def _log(msg):
        log.insert("end", msg + "\n")
        log.see("end")

    _next_id = [4]

    def on_add(module):
        iid = _next_id[0]
        _next_id[0] += 1
        bar.add_tab(iid, module=module)
        f = bar.get_frame(iid)
        ttk.Label(f, text=f"inst_id={iid}  module={module}",
                  font=("TkDefaultFont", 14)).pack(expand=True)
        _log(f"[+] inst_id={iid}  module={module}")

    def on_select(iid):
        _log(f"select  inst_id={iid}")

    def on_close(iid):
        bar.remove_tab(iid)
        _log(f"[x] zamknieto inst_id={iid}")

    def on_action(iid, action):
        _log(f"action='{action}'  inst_id={iid}")

    bar = InstanceTabBar(
        root,
        on_select=on_select,
        on_add=on_add,
        on_load_workspace=lambda: _log("[+] Wczytaj zestaw..."),
        on_close=on_close,
        on_action=on_action,
    )
    bar.pack(fill="both", expand=True, padx=4, pady=(4, 0))

    for iid, mod in [(1, "bars"), (2, "bars"), (3, "wave")]:
        bar.add_tab(iid, module=mod, select=(iid == 3))
        f = bar.get_frame(iid)
        ttk.Label(f, text=f"inst_id={iid}  module={mod}",
                  font=("TkDefaultFont", 14)).pack(expand=True)

    root.mainloop()
