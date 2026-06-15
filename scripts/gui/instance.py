# =============================================================================
# gui/instance.py
# Klasa GlavaInstance — reprezentuje jedną instancję GLava z własnym katalogiem
# konfiguracyjnym. Fundament architektury multi-instancji.
# =============================================================================
import json
import os
import shutil

USER_HOME = os.path.expanduser("~")

class GlavaInstance:
    """
    Reprezentuje jedną instancję GLava.

    Atrybuty:
        inst_id   — unikalny identyfikator (int lub str, np. 0, 1, "main")
        xdg_dir   — ~/.config/glava-inst-{inst_id}  (XDG_CONFIG_HOME dla GLava)
        glava_dir — {xdg_dir}/glava                 (pliki rc.glsl, bars.glsl itp.)
        conf_dir  — ~/.config/GlavaMP/inst-{inst_id} (profile, ustawienia GUI)

    Instancja 0 jest domyślna i wskazuje na oryginalny ~/.config/glava/.
    """

    def __init__(self, inst_id=0, home=None):
        self.inst_id = inst_id
        _home = home or USER_HOME
        self.xdg_dir          = os.path.join(_home, f".config/glava-inst-{inst_id}")
        self.glava_dir        = os.path.join(self.xdg_dir, "glava")
        self.conf_dir         = os.path.join(_home, f".config/GlavaMP/inst-{inst_id}")
        self.DEFAULT_GLAVA_DIR = os.path.join(_home, ".config/glava")
        self.DEFAULT_CONF_DIR  = os.path.join(_home, ".config/GlavaMP")

    # ── Ścieżki plików ────────────────────────────────────────────────────────

    @property
    def rc_glsl(self):
        return os.path.join(self.glava_dir, "rc.glsl")

    @property
    def smooth_glsl(self):
        return os.path.join(self.glava_dir, "smooth_parameters.glsl")

    def module_glsl(self, module_name):
        return os.path.join(self.glava_dir, f"{module_name}.glsl")

    def module_frag(self, module_name):
        return os.path.join(self.glava_dir, module_name, "1.frag")

    def module_tmpl(self, module_name):
        return os.path.join(self.glava_dir, f"{module_name}_colors.frag")

    @property
    def profiles_file(self):
        return os.path.join(self.conf_dir, "profiles.json")

    @property
    def presets_file(self):
        return os.path.join(self.conf_dir, "presets.json")

    # ── Zarządzanie katalogiem ────────────────────────────────────────────────

    def exists(self):
        """Zwraca True jeśli katalog instancji istnieje."""
        #        return os.path.isdir(self.glava_dir)
        return os.path.exists(self.glava_dir)

    # Katalogi shaderow zawierajace pliki frag (kolory) — musza byc kopiowane
    # a nie symlinkowane, inaczej wszystkie instancje dzielą te same pliki frag
    SHADER_DIRS = {"bars", "wave", "circle", "graph", "radial"}

    def create(self, source=None):
        """
        Tworzy strukturę katalogów instancji.
        source — GlavaInstance do skopiowania; None = szablon ~/.config/glava.
        Fallback szablonu: /etc/xdg/glava.
        """
        if self.exists():
            return

        os.makedirs(os.path.dirname(self.glava_dir), exist_ok=True)
        os.makedirs(self.conf_dir, exist_ok=True)

        if source is not None and os.path.isdir(source.glava_dir):
            base_src = source.glava_dir
        else:
            base_src = self.DEFAULT_GLAVA_DIR if os.path.exists(self.DEFAULT_GLAVA_DIR) else "/etc/xdg/glava"

        if os.path.exists(base_src):
            shutil.copytree(base_src, self.glava_dir, symlinks=True, dirs_exist_ok=True)
#    def create(self, source_inst=None):
#        """
#        Tworzy strukturę katalogów nowej instancji.
#        source_inst — GlavaInstance z której kopiujemy pliki GLSL.
#                      Domyślnie instancja 0 (oryginalna).
#
#        Strategia kopiowania:
#          - *.glsl (rc.glsl, bars.glsl itp.)   — kopiowane
#          - bars/, wave/, circle/, graph/, radial/ — kopiowane w całości
#            (zawierają 1.frag z kolorami — muszą być izolowane per instancja)
#          - util/ i inne katalogi               — symlinki do inst-0
#            (współdzielone shadery pomocnicze, nie zawierają danych per inst)
#        """
#        if source_inst is None:
#            source_inst = GlavaInstance(0)
#
#        os.makedirs(self.glava_dir, exist_ok=True)
#        os.makedirs(self.conf_dir,  exist_ok=True)
#
#        src = source_inst.glava_dir
#
#        # Kopiuj pliki konfiguracyjne z poziomu glava_dir
#        # *.glsl  — rc.glsl, bars.glsl itp.
#        # *_colors.frag — szablony kolorow (bars_colors.frag itp.)
#        for pattern in ("*.glsl", "*_colors.frag"):
#            for f in glob.glob(os.path.join(src, pattern)):
#                dst = os.path.join(self.glava_dir, os.path.basename(f))
#                if not os.path.exists(dst):
#                    shutil.copy2(f, dst)
#
#        # Katalogi shaderow — kopiuj w calosci (izolacja plikow frag)
#        # Pozostale katalogi — symlinkuj (util/, backup/ itp.)
#        for entry in os.scandir(src):
#            dst = os.path.join(self.glava_dir, entry.name)
#            if os.path.exists(dst) or os.path.islink(dst):
#                continue
#            if entry.is_dir(follow_symlinks=False):
#                if entry.name in self.SHADER_DIRS:
#                    # Kopiuj caly katalog shadera
#                    shutil.copytree(entry.path, dst, symlinks=True)
#                else:
#                    # Symlinkuj pozostale katalogi (util/ itp.)
#                    os.symlink(entry.path, dst)
#            elif entry.is_symlink():
#                # Zachowaj istniejace symlinki (np. z poprzedniej instalacji)
#                os.symlink(os.readlink(entry.path), dst)

    def destroy(self):
        """Usuwa katalog instancji."""
        if os.path.isdir(self.xdg_dir):
            shutil.rmtree(self.xdg_dir)
        if os.path.isdir(self.conf_dir):
            shutil.rmtree(self.conf_dir)

    def __repr__(self):
        return f"GlavaInstance(inst_id={self.inst_id!r}, glava_dir={self.glava_dir!r})"

# =============================================================================
# Rejestr instancji — instances.json
# =============================================================================


INSTANCES_FILE = os.path.join(USER_HOME, ".config/GlavaMP/instances.json")

def load_instances():
    """
    Wczytuje rejestr instancji z instances.json.
    Zwraca listę dict: [{inst_id, name, module, active}, ...]
    Pusta lista jest poprawnym stanem (brak instancji).
    """
    if not os.path.exists(INSTANCES_FILE):
        return []
    try:
        with open(INSTANCES_FILE) as f:
            data = json.load(f)
        if not isinstance(data, list):
            return []
        return data
    except Exception:
        return []

def save_instances(instances):
    """Zapisuje rejestr instancji do instances.json."""
    os.makedirs(os.path.dirname(INSTANCES_FILE), exist_ok=True)
    with open(INSTANCES_FILE, "w") as f:
        json.dump(instances, f, indent=2)

def register_instance(inst_id, name=None, module="bars"):
    """Dodaje instancję do rejestru jeśli nie istnieje."""
    instances = load_instances()
    ids = [i["inst_id"] for i in instances]
    if inst_id in ids:
        return
    instances.append({
        "inst_id": inst_id,
        "name": name or f"Instance {inst_id}",
        "module": module,
        "active": False,
    })
    save_instances(instances)

def unregister_instance(inst_id):
    """Usuwa instancję z rejestru."""
    instances = load_instances()
    instances = [i for i in instances if i["inst_id"] != inst_id]
    save_instances(instances)


def update_instance(inst_id, **kwargs):
    """
    Aktualizuje pola istniejącego wpisu w rejestrze.
    Obsługiwane pola: name, module, active.
    Przykład: update_instance(2, name="Bars lewy", module="bars")
    """
    instances = load_instances()
    for entry in instances:
        if entry["inst_id"] == inst_id:
            for k, v in kwargs.items():
                entry[k] = v
            break
    save_instances(instances)

def next_inst_id():
    """Zwraca następny wolny inst_id."""
    instances = load_instances()
    ids = {i["inst_id"] for i in instances}
    n = 1
    while n in ids:
        n += 1
    return n
