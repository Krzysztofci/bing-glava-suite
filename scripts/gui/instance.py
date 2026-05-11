# =============================================================================
# gui/instance.py
# Klasa GlavaInstance — reprezentuje jedną instancję GLava z własnym katalogiem
# konfiguracyjnym. Fundament architektury multi-instancji.
# =============================================================================
import os
import glob
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

    DEFAULT_GLAVA_DIR = os.path.join(USER_HOME, ".config/glava")
    DEFAULT_CONF_DIR  = os.path.join(USER_HOME, ".config/GlavaMP")

    def __init__(self, inst_id=0):
        self.inst_id = inst_id
        if inst_id == 0:
            self.xdg_dir   = os.path.join(USER_HOME, ".config")
            self.glava_dir = self.DEFAULT_GLAVA_DIR
            self.conf_dir  = self.DEFAULT_CONF_DIR
        else:
            self.xdg_dir   = os.path.expanduser(f"~/.config/glava-inst-{inst_id}")
            self.glava_dir = os.path.join(self.xdg_dir, "glava")
            self.conf_dir  = os.path.expanduser(f"~/.config/GlavaMP/inst-{inst_id}")

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
        return os.path.isdir(self.glava_dir)

    def create(self, source_inst=None):
        """
        Tworzy strukturę katalogów nowej instancji.
        source_inst — GlavaInstance z której kopiujemy pliki GLSL.
                      Domyślnie instancja 0 (oryginalna).
        Pliki własne (rc.glsl, bars.glsl itp.) — kopiowane.
        Pozostałe (util/, subdirectory fragi) — symlinki do inst-0.
        """
        if source_inst is None:
            source_inst = GlavaInstance(0)

        os.makedirs(self.glava_dir, exist_ok=True)
        os.makedirs(self.conf_dir,  exist_ok=True)

        src = source_inst.glava_dir

        # Kopiuj własne pliki GLSL
        for pattern in ("*.glsl",):
            for f in glob.glob(os.path.join(src, pattern)):
                dst = os.path.join(self.glava_dir, os.path.basename(f))
                if not os.path.exists(dst):
                    shutil.copy2(f, dst)

        # Symlinki do podkatalogów (bars/, circle/ itp.) i util/
        for entry in os.scandir(src):
            dst = os.path.join(self.glava_dir, entry.name)
            if os.path.exists(dst) or os.path.islink(dst):
                continue
            if entry.is_dir(follow_symlinks=False) or entry.is_symlink():
                os.symlink(entry.path, dst)

    def destroy(self):
        """Usuwa katalog instancji (nie dla inst_id=0)."""
        if self.inst_id == 0:
            raise ValueError("Nie można usunąć instancji domyślnej (inst_id=0)")
        if os.path.isdir(self.xdg_dir):
            shutil.rmtree(self.xdg_dir)
        if os.path.isdir(self.conf_dir):
            shutil.rmtree(self.conf_dir)

    def __repr__(self):
        return f"GlavaInstance(inst_id={self.inst_id!r}, glava_dir={self.glava_dir!r})"
