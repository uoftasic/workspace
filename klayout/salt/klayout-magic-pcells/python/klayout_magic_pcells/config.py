"""Configuration: environment variables, then config.ini, then defaults.

``config.ini`` lives at ``$XDG_CONFIG_HOME/klayout-magic-pcells/config.ini``
(else ``~/.config/klayout-magic-pcells/config.ini``). Its keys sit in a
``[kmp]`` section, in lower case and without the ``KMP_`` prefix, for
example ``magic = /opt/magic/bin/magic`` or ``pdks = sky130A, gf180mcuD``.
Settings for one PDK go in a section of their own, ``[kmp:<pdk>]``, with the
keys ``magicrc``, ``manifest`` and ``netgen_setup``; in the environment they
are ``KMP_MAGICRC_<PDK>``, ``KMP_MANIFEST_<PDK>`` and
``KMP_NETGEN_SETUP_<PDK>``, with the PDK name in upper case and ``-``
written as ``_`` (``KMP_MAGICRC_IHP_SG13G2``).

The checks that run Magic as a job (DRC, extraction, netgen LVS, the
generated-layer check) read ``KMP_DRC_STYLE`` (default ``drc(full)``),
``KMP_DRC_MODE`` (``hierarchical``, the default, or ``flat``),
``KMP_JOB_TIMEOUT`` (seconds per job, default 1800), ``KMP_NETGEN`` (default:
``netgen`` on ``PATH``) and ``KMP_MENU`` (``0`` leaves the Magic menu out).

Which PDKs get a library comes from ``KMP_PDKS`` (a comma- or space-separated
list, or ``auto``, the default: every supported PDK whose rcfile exists under
``PDK_ROOT``). ``KMP_PDK`` names the PDK that the command line, the
unqualified ``KMP_MAGICRC`` and ``KMP_MANIFEST``, and ``Config.load()``
without a ``pdk`` argument are about; it defaults to sky130A. When
``KMP_PDKS`` is unset and ``KMP_PDK`` is set, only that PDK is registered,
as in version 0.2.

No setting here comes from ``PDK``, which the iic-osic-tools image sets to
``ihp-sg13g2`` by default: which PDKs get a library, and the PDK that
``KMP_PDK`` defaults to, don't depend on it. The checks' choice of PDK
(``pdkchoice.choose_pdk``) reads it in its last rule, a guess: ``PDK`` is
the guess when the layers give none, and it decides between two PDKs whose
layers fit a layout alike. The Magic server gets ``PDK`` set to its own
PDK (``backend``).
"""

import configparser
import copy
import os
import re
import shutil

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
TCL_DIR = os.path.join(PACKAGE_DIR, "tcl")

# The PDKs this version supports: the KLayout library each one gets, and the
# Tcl namespace of its device generators (each PDK's .tcl sets PDKNAMESPACE
# to it). The library names avoid the PDKs' own KLayout libraries
# (skywater130; gf180mcu, gf180mcu_klayoutapi, gf180mcu_sealring; SG13_dev,
# SG13_native_pcell_lib), since registering a library under a name that
# exists replaces the existing one.
PDKS = {
    "sky130A": {"library": "sky130_magic", "namespace": "sky130"},
    "gf180mcuD": {"library": "gf180mcu_magic", "namespace": "gf180mcu"},
    "ihp-sg13g2": {"library": "sg13g2_magic", "namespace": "sg13g2"},
    "ihp-sg13cmos5l": {"library": "sg13cmos5l_magic", "namespace": "sg13cmos5l"},
}
SUPPORTED_PDKS = tuple(PDKS)
DEFAULT_PDK = "sky130A"
LIBRARY_NAMES = {p: v["library"] for p, v in PDKS.items()}


def shipped_manifest(pdk):
    return os.path.join(PACKAGE_DIR, "data", "manifest-%s.json" % pdk)


SHIPPED_MANIFEST = shipped_manifest(DEFAULT_PDK)

# (environment variable, ini key) of the settings shared by every PDK
_KEYS = [
    ("KMP_MAGIC", "magic"),
    ("PDK_ROOT", "pdk_root"),
    ("KMP_PDK", "pdk"),
    ("KMP_PDKS", "pdks"),
    ("KMP_MAGICRC", "magicrc"),
    ("KMP_CACHE_DIR", "cache_dir"),
    ("KMP_CACHE", "cache"),
    ("KMP_BACKEND", "backend"),
    ("KMP_TIMEOUT", "timeout"),
    ("KMP_LAZY", "lazy"),
    ("KMP_MANIFEST", "manifest"),
    ("KMP_LOG", "log"),
    ("KMP_DRC_STYLE", "drc_style"),
    ("KMP_DRC_MODE", "drc_mode"),
    ("KMP_JOB_TIMEOUT", "job_timeout"),
    ("KMP_NETGEN", "netgen"),
    ("KMP_NETGEN_SETUP", "netgen_setup"),
    ("KMP_MENU", "menu"),
]

DRC_MODES = ("hierarchical", "flat")
DEFAULT_DRC_STYLE = "drc(full)"
DEFAULT_JOB_TIMEOUT = 1800.0


class ConfigError(Exception):
    pass


def _truthy(text, name):
    t = str(text).strip().lower()
    if t in ("1", "true", "yes", "on"):
        return True
    if t in ("0", "false", "no", "off", ""):
        return False
    raise ConfigError("%s must be 0 or 1, not %r" % (name, text))


def _home(env):
    return env.get("HOME") or os.path.expanduser("~")


def pdk_env_suffix(pdk):
    """'ihp-sg13g2' -> 'IHP_SG13G2', for KMP_MAGICRC_<PDK> and KMP_MANIFEST_<PDK>."""
    return re.sub(r"[^A-Za-z0-9]", "_", pdk).upper()


def config_file_path(env=None):
    env = os.environ if env is None else env
    base = env.get("XDG_CONFIG_HOME") or os.path.join(_home(env), ".config")
    return os.path.join(base, "klayout-magic-pcells", "config.ini")


def default_cache_dir(env=None):
    env = os.environ if env is None else env
    base = env.get("XDG_CACHE_HOME") or os.path.join(_home(env), ".cache")
    return os.path.join(base, "klayout-magic-pcells")


def default_magicrc(pdk_root, pdk):
    return os.path.join(pdk_root, pdk, "libs.tech", "magic", pdk + ".magicrc")


def default_netgen_setup(pdk_root, pdk):
    return os.path.join(pdk_root, pdk, "libs.tech", "netgen", pdk + "_setup.tcl")


class Config:
    """Resolved settings for one PDK (``pdk``), plus the shared ones.

    ``sources[name]`` says where each value came from. ``pdks`` is the list
    of PDKs to register; ``pdk_errors`` maps a name in ``KMP_PDKS`` that this
    version doesn't support to the reason, so that registration can fail for
    that PDK alone. ``for_pdk(name)`` gives the settings for another PDK.
    """

    def __init__(self):
        self.magic = None
        self.pdk_root = None
        self.pdk = None
        self.pdks = []
        self.pdk_errors = {}
        self.magicrc = None
        self.cache_dir = None
        self.cache_enabled = True
        self.backend = "server"
        self.timeout = 30.0
        self.lazy = False
        self.manifest = SHIPPED_MANIFEST
        self.log = None
        self.drc_style = DEFAULT_DRC_STYLE
        self.drc_mode = "hierarchical"
        self.job_timeout = DEFAULT_JOB_TIMEOUT
        self.netgen = None
        self.netgen_setup = None
        self.menu = True
        self.config_file = None
        self.sources = {}
        self._env = {}
        self._ini = {}
        self._ini_pdk = {}

    @classmethod
    def load(cls, env=None, config_path=None, pdk=None):
        env = dict(os.environ) if env is None else dict(env)
        cfg = cls()
        cfg._env = env
        path = config_path or config_file_path(env)
        ini = {}
        ini_pdk = {}
        if os.path.isfile(path):
            cp = configparser.ConfigParser()
            try:
                cp.read(path, encoding="utf-8")
            except configparser.Error as e:
                raise ConfigError("cannot read %s: %s" % (path, e))
            if cp.has_section("kmp"):
                ini = {k.lower(): v for k, v in cp.items("kmp")}
            for sec in cp.sections():
                if sec.lower().startswith("kmp:"):
                    ini_pdk[sec[4:].strip()] = {k.lower(): v for k, v in cp.items(sec)}
            cfg.config_file = path
        cfg._ini, cfg._ini_pdk, cfg._ini_path = ini, ini_pdk, path

        def get(var, key):
            if env.get(var, "") != "":
                return env[var], "env %s" % var
            if key in ini and ini[key] != "":
                return ini[key], "%s [kmp] %s" % (path, key)
            return None, None

        raw = {}
        for var, key in _KEYS:
            raw[key] = get(var, key)
        cfg._raw = raw

        def setv(name, value, source):
            setattr(cfg, name, value)
            cfg.sources[name] = source

        v, s = raw["magic"]
        if v is None:
            v = shutil.which("magic", path=env.get("PATH")) or "/foss/tools/bin/magic"
            s = "default (PATH, then /foss/tools/bin/magic)"
        setv("magic", os.path.expanduser(v), s)

        v, s = raw["pdk_root"]
        setv("pdk_root", os.path.expanduser(v) if v else "/foss/pdks", s or "default")

        v, s = raw["pdk"]
        primary = (v or DEFAULT_PDK).strip()
        cfg._primary = primary
        cfg._primary_source = s or "default"

        # The PDKs to register.
        v, s = raw["pdks"]
        if v is None and raw["pdk"][0] is not None:
            names, s = [primary], "%s (KMP_PDKS unset)" % raw["pdk"][1]
        elif v is None or v.strip().lower() in ("auto", ""):
            names = [p for p in SUPPORTED_PDKS
                     if os.path.isfile(default_magicrc(cfg.pdk_root, p))
                     or cfg._pdk_value(p, "magicrc")[0] is not None]
            s = (s or "default") + " (auto: the supported PDKs installed under PDK_ROOT)"
        elif v.strip().lower() == "all":
            names = list(SUPPORTED_PDKS)
        else:
            names = []
            for n in re.split(r"[,\s]+", v.strip()):
                if n and n not in names:
                    names.append(n)
        cfg.pdks = [n for n in names if n in PDKS]
        cfg.pdk_errors = {n: "KMP_PDKS names %s, which this version doesn't support (supported: %s)"
                          % (n, ", ".join(SUPPORTED_PDKS)) for n in names if n not in PDKS}
        cfg.sources["pdks"] = s

        v, s = raw["cache_dir"]
        setv("cache_dir", os.path.expanduser(v) if v else default_cache_dir(env),
             s or "default ($XDG_CACHE_HOME or ~/.cache)/klayout-magic-pcells")

        v, s = raw["cache"]
        setv("cache_enabled", _truthy(v, "KMP_CACHE") if v is not None else True, s or "default")

        v, s = raw["backend"]
        v = (v or "server").strip().lower()
        if v not in ("server", "oneshot"):
            raise ConfigError("KMP_BACKEND must be 'server' or 'oneshot', not %r" % v)
        setv("backend", v, s or "default")

        v, s = raw["timeout"]
        try:
            t = float(v) if v is not None else 30.0
        except ValueError:
            raise ConfigError("KMP_TIMEOUT must be a number of seconds, not %r" % v)
        if t <= 0:
            raise ConfigError("KMP_TIMEOUT must be positive")
        setv("timeout", t, s or "default")

        v, s = raw["lazy"]
        if v is None:
            setv("lazy", cfg.backend == "oneshot", "default (1 with oneshot, 0 with server)")
        else:
            setv("lazy", _truthy(v, "KMP_LAZY"), s)

        v, s = raw["log"]
        setv("log", os.path.expanduser(v) if v else None, s or "default (off)")

        v, s = raw["drc_style"]
        setv("drc_style", v.strip() if v is not None else DEFAULT_DRC_STYLE, s or "default")

        v, s = raw["drc_mode"]
        mode = (v or "hierarchical").strip().lower()
        if mode not in DRC_MODES:
            hint = " (per-cell is now called hierarchical)" if mode in ("per-cell", "per_cell") else ""
            raise ConfigError("KMP_DRC_MODE must be 'hierarchical' or 'flat', not %r%s" % (v, hint))
        setv("drc_mode", mode, s or "default")

        v, s = raw["job_timeout"]
        try:
            t = float(v) if v is not None else DEFAULT_JOB_TIMEOUT
        except ValueError:
            raise ConfigError("KMP_JOB_TIMEOUT must be a number of seconds, not %r" % v)
        if not t > 0:
            raise ConfigError("KMP_JOB_TIMEOUT must be positive")
        setv("job_timeout", t, s or "default")

        v, s = raw["netgen"]
        if v is None:
            v = shutil.which("netgen", path=env.get("PATH")) or "netgen"
            s = "default (netgen on PATH)"
        setv("netgen", os.path.expanduser(v), s)

        v, s = raw["menu"]
        setv("menu", _truthy(v, "KMP_MENU") if v is not None else True, s or "default")

        cfg._set_pdk(pdk or primary, pdk_source="argument" if pdk else cfg._primary_source)
        return cfg

    # -- per-PDK settings -------------------------------------------------------

    def _pdk_value(self, pdk, key):
        """(value, source) of a per-PDK key (magicrc, manifest, netgen_setup)
        for ``pdk``:
        KMP_<KEY>_<PDK>, then [kmp:<pdk>], then the unqualified KMP_<KEY> or
        [kmp] <key> when ``pdk`` is the one KMP_PDK names."""
        var = "KMP_%s_%s" % (key.upper(), pdk_env_suffix(pdk))
        if self._env.get(var, "") != "":
            return self._env[var], "env %s" % var
        sec = self._ini_pdk.get(pdk, {})
        if sec.get(key, "") != "":
            return sec[key], "%s [kmp:%s] %s" % (self._ini_path, pdk, key)
        if pdk == self._primary and self._raw[key][0] is not None:
            return self._raw[key]
        return None, None

    def _set_pdk(self, pdk, pdk_source):
        if pdk not in PDKS:
            raise ConfigError("KMP_PDK=%s is not supported; this version supports %s"
                              % (pdk, ", ".join(SUPPORTED_PDKS)))
        self.pdk = pdk
        self.sources["pdk"] = pdk_source
        v, s = self._pdk_value(pdk, "magicrc")
        if v is None:
            v = default_magicrc(self.pdk_root, pdk)
            s = "default ($PDK_ROOT/<pdk>/libs.tech/magic/<pdk>.magicrc)"
        self.magicrc = os.path.expanduser(v)
        self.sources["magicrc"] = s
        v, s = self._pdk_value(pdk, "manifest")
        self.manifest = os.path.expanduser(v) if v else shipped_manifest(pdk)
        self.sources["manifest"] = s or "default (shipped)"
        v, s = self._pdk_value(pdk, "netgen_setup")
        if v is None:
            v = default_netgen_setup(self.pdk_root, pdk)
            s = "default ($PDK_ROOT/<pdk>/libs.tech/netgen/<pdk>_setup.tcl)"
        self.netgen_setup = os.path.expanduser(v)
        self.sources["netgen_setup"] = s

    def for_pdk(self, pdk):
        """A copy of these settings for another PDK."""
        c = copy.copy(self)
        c.sources = dict(self.sources)
        c._set_pdk(pdk, "argument")
        return c

    @property
    def library_name(self):
        return LIBRARY_NAMES[self.pdk]

    @property
    def namespace(self):
        return PDKS[self.pdk]["namespace"]

    @property
    def pdk_path(self):
        return os.path.join(self.pdk_root, self.pdk)

    def problems(self):
        """Missing pieces, as messages naming the variable to set."""
        out = []
        if not (os.path.isfile(self.magic) and os.access(self.magic, os.X_OK)):
            out.append("Magic executable not found at %s (set KMP_MAGIC, or put magic on PATH)"
                       % self.magic)
        if not os.path.isfile(self.magicrc):
            out.append("Magic rcfile for %s not found at %s (is %s installed? set PDK_ROOT, or "
                       "KMP_MAGICRC_%s)" % (self.pdk, self.magicrc, self.pdk, pdk_env_suffix(self.pdk)))
        if not os.path.isfile(self.manifest):
            out.append("manifest for %s not found at %s (check KMP_MANIFEST_%s)"
                       % (self.pdk, self.manifest, pdk_env_suffix(self.pdk)))
        return out

    def job_problems(self):
        """What the jobs need beyond the PCells: netgen and the PDK's netgen
        setup file (LVS only). Kept out of problems(), which decides whether
        a PDK's library registers."""
        out = []
        exe = self.netgen if os.sep in self.netgen else shutil.which(
            self.netgen, path=self._env.get("PATH"))
        if not (exe and os.path.isfile(exe) and os.access(exe, os.X_OK)):
            out.append("netgen not found at %s (set KMP_NETGEN, or put netgen on PATH); "
                       "LVS needs it" % self.netgen)
        if not os.path.isfile(self.netgen_setup):
            out.append("netgen setup file for %s not found at %s (set KMP_NETGEN_SETUP_%s); "
                       "LVS needs it" % (self.pdk, self.netgen_setup, pdk_env_suffix(self.pdk)))
        return out

    def describe(self):
        rows = []
        for name in ("magic", "pdk_root", "pdks", "pdk", "magicrc", "cache_dir", "cache_enabled",
                     "backend", "timeout", "lazy", "manifest", "log", "drc_style", "drc_mode",
                     "job_timeout", "netgen", "netgen_setup", "menu"):
            val = getattr(self, name)
            if name == "pdks":
                val = ", ".join(val) or "(none)"
            rows.append((name, val, self.sources.get(name, "")))
        return rows
