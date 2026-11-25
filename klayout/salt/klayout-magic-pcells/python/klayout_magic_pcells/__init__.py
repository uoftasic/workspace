"""KLayout PCells for the devices that Magic's PDK generators draw.

One library per PDK: ``sky130_magic`` (sky130A), ``gf180mcu_magic``
(gf180mcuD), ``sg13g2_magic`` (ihp-sg13g2) and ``sg13cmos5l_magic``
(ihp-sg13cmos5l), each backed by its own Magic process.

``register()`` registers every PDK that the configuration selects
(``KMP_PDKS``, by default the supported PDKs installed under ``PDK_ROOT``).
For each one it checks the configuration, starts Magic with that PDK's
rcfile and registers the library. A PDK whose Magic can't start, or whose
setup is incomplete, gets one logged error and no library; the others still
register. Cells of a PDK that isn't registered stay ``<defunct>`` and keep
their stored geometry until a later ``register()`` succeeds.
"""

import logging
import os
import tempfile

__version__ = "0.6.2"
# The sky130A library's name, kept for code written against version 0.2.
LIBRARY_NAME = "sky130_magic"

log = logging.getLogger("klayout_magic_pcells")


class PdkState:
    """Everything one PDK's library needs at run time."""

    def __init__(self, pdk):
        from .config import LIBRARY_NAMES
        self.pdk = pdk
        self.library_name = LIBRARY_NAMES.get(pdk, pdk)
        self.cfg = None
        self.manifest = None
        self.server = None
        self.cache = None
        self.generator = None
        self.versions = None
        self.created_stamp = ""
        self.stamp_dict = {}
        self.library = None
        self.defaults_mismatch = []
        self.last_error = None


states = {}


def state_for(pdk):
    """The PdkState of ``pdk`` (made empty on first use)."""
    st = states.get(pdk)
    if st is None:
        st = states[pdk] = PdkState(pdk)
    return st


def primary_pdk():
    """The PDK that KMP_PDK names (sky130A by default)."""
    try:
        from .config import Config
        return Config.load().pdk
    except Exception:
        from .config import DEFAULT_PDK
        return DEFAULT_PDK


class _PrimaryState:
    """``klayout_magic_pcells.state``: the PdkState of the PDK that KMP_PDK
    names, for code written against version 0.2's single state."""

    def __getattr__(self, name):
        return getattr(state_for(primary_pdk()), name)


state = _PrimaryState()


def _log_error(msg):
    try:
        from ._kl import error
        error(msg)
    except Exception:
        log.error(msg)


def _log_warn(msg):
    try:
        from ._kl import warn
        warn(msg)
    except Exception:
        log.warning(msg)


def _hint_setup(pdk):
    from .config import pdk_env_suffix
    return ("Set KMP_MAGIC to the Magic executable, PDK_ROOT to the directory holding %s "
            "(or KMP_MAGICRC_%s to its rcfile), or put them in "
            "~/.config/klayout-magic-pcells/config.ini; KMP_PDKS selects which PDKs register"
            % (pdk, pdk_env_suffix(pdk)))


def _hint_devices(pdk):
    from .config import pdk_env_suffix
    return ("Check PDK_ROOT and KMP_MAGICRC_%s, or build a manifest for this PDK "
            "(tools/build_manifest.py --pdk %s --out FILE) and set KMP_MANIFEST_%s to it"
            % (pdk_env_suffix(pdk), pdk, pdk_env_suffix(pdk)))


class StartError(RuntimeError):
    """The backend can't serve a library; ``hint`` says what to set."""

    def __init__(self, msg, hint=None):
        super().__init__(msg)
        self.hint = hint


def _cache_dir_problem(path):
    """None if ``path`` exists or can be made and is writable, else why not."""
    try:
        os.makedirs(path, exist_ok=True)
        fd, probe = tempfile.mkstemp(prefix=".kmp-probe-", dir=path)
        os.close(fd)
        os.remove(probe)
        return None
    except OSError as e:
        return str(e)


def missing_devices(manifest, live_defaults, live_boxpaint=None):
    """Manifest PCells whose generator the running Magic doesn't define."""
    out = [d.name for d in manifest.devices if d.kind == "device" and d.name not in live_defaults]
    if live_boxpaint is not None:
        out += [d.name for d in manifest.devices if d.kind == "box" and d.name not in live_boxpaint]
    return out


def _prepare(cfg):
    """Check one PDK's configuration and load its manifest; raises StartError."""
    from .manifest import Manifest
    problems = cfg.problems()
    if problems:
        raise StartError("; ".join(problems), hint="Or leave %s out of KMP_PDKS" % cfg.pdk)
    manifest = Manifest.load(cfg.manifest)
    if manifest.pdk != cfg.pdk:
        raise StartError("manifest %s is for %s, not %s" % (cfg.manifest, manifest.pdk, cfg.pdk),
                         hint="Set KMP_MANIFEST_%s" % cfg.pdk.upper().replace("-", "_"))
    return manifest


def start_backend(cfg=None, pdk=None, server=None, manifest=None):
    """Resolve one PDK's configuration, start its Magic and build its generator.

    Returns that PDK's state; raises on failure. Does not register anything.
    Refuses (StartError) when the running Magic lacks any device or box-paint
    generator of the manifest: every such PCell could only draw the error
    marker, and saving a file opened that way replaces the stored geometry
    with markers (K2).
    """
    from .backend import Generator, make_server
    from .cache import GdsCache, versions_fields
    from .config import Config
    from .manifest import diff_defaults
    from .stamp import make_stamp, parse_stamp

    if cfg is None:
        cfg = Config.load(pdk=pdk)
    elif pdk is not None and cfg.pdk != pdk:
        cfg = cfg.for_pdk(pdk)
    st = state_for(cfg.pdk)
    if st.generator is not None:
        return st
    lib = st.library_name
    if manifest is None:
        manifest = _prepare(cfg)
    if cfg.cache_enabled:
        why = _cache_dir_problem(cfg.cache_dir)
        if why:
            _log_warn("%s: the cache directory %s can't be used (%s); continuing without "
                      "the disk cache. Set KMP_CACHE_DIR to a writable directory, or KMP_CACHE=0."
                      % (lib, cfg.cache_dir, why))
            cfg.cache_enabled = False
            cfg.sources["cache_enabled"] = "off: KMP_CACHE_DIR not writable"
    if server is None:
        server = make_server(cfg, vendor_cells=manifest.vendor_cells())
    try:
        versions = server.start()
        said = ""
        if hasattr(server, "startup_messages"):
            lines = server.startup_messages()
            said = ("; Magic said: " + " | ".join(lines)) if lines else ""
        if not versions.namespace:
            raise StartError(
                "the rcfile %s loaded no PDK: after reading it, Magic has no PDKNAMESPACE and none "
                "of the manifest's %d generators (namespace %s)%s"
                % (cfg.magicrc, len(manifest.devices), manifest.namespace or cfg.namespace, said),
                hint=_hint_devices(cfg.pdk))
        if manifest.namespace and versions.namespace != manifest.namespace:
            raise StartError(
                "the rcfile %s loaded the generator namespace %s, but the manifest %s is for %s"
                % (cfg.magicrc, versions.namespace, cfg.manifest, manifest.namespace),
                hint=_hint_devices(cfg.pdk))
        # The namespace doesn't tell the variants of one PDK apart: sky130A
        # and sky130B both load ::sky130, and gf180mcu A to F ::gf180mcu.
        # Magic's technology name does (sky130A, gf180mcuD, ...).
        want_tech = (manifest.data.get("built_with") or {}).get("tech_name") or cfg.pdk
        if versions.tech_name != want_tech:
            raise StartError(
                "the rcfile %s loaded the Magic technology %s, not %s: the manifest %s is for %s"
                % (cfg.magicrc, versions.tech_name or "(none)", want_tech, cfg.manifest, cfg.pdk),
                hint=_hint_devices(cfg.pdk))
        missing = missing_devices(manifest, versions.defaults, versions.boxpaint)
        if missing:
            n = len(manifest.devices)
            raise StartError(
                "the running Magic defines %d of the manifest's %d generators (missing: %s%s): "
                "the PDK's device generators (namespace %s) did not load, or Magic loaded "
                "another PDK%s"
                % (n - len(missing), n, ", ".join(missing[:4]), ", ..." if len(missing) > 4 else "",
                   manifest.namespace or cfg.namespace, said),
                hint=_hint_devices(cfg.pdk))
    except Exception:
        server.close()
        raise
    mismatch = diff_defaults(manifest.defaults_by_device(), versions.defaults)
    if versions.defaults_digest != manifest.defaults_digest:
        _log_warn("%s: the defaults of %d device(s) in the running Magic differ from "
                  "the manifest %s (run 'python3 -m klayout_magic_pcells doctor --pdk %s')"
                  % (lib, len(mismatch), cfg.manifest, cfg.pdk))
    cache = GdsCache(cfg.cache_dir, versions_fields(versions, cfg.pdk), enabled=cfg.cache_enabled)
    st.cfg, st.manifest, st.server, st.cache = cfg, manifest, server, cache
    st.versions = versions
    st.generator = Generator(server, cache, versions)
    # audit --regen: every get() goes to Magic (Config.fresh is set there).
    st.generator.fresh = bool(getattr(cfg, "fresh", False))
    st.created_stamp = make_stamp(versions)
    st.stamp_dict = parse_stamp(st.created_stamp)
    st.defaults_mismatch = mismatch
    return st


def _fail(pdk, e):
    st = state_for(pdk)
    st.last_error = str(e)
    hint = getattr(e, "hint", None)
    if hint is None:
        hint = _hint_setup(pdk)
    _log_error("%s: not registered: %s. %s"
               % (st.library_name, str(e).rstrip(". "),
                  (hint + ", then call" if hint else "Then call")
                  + " klayout_magic_pcells.register()."))
    shutdown(pdk)


def _register_library(pdk):
    st = state_for(pdk)
    try:
        from .library import MagicLibrary
        st.library = MagicLibrary(st.manifest, st)
    except Exception as e:  # e.g. a rebuilt manifest whose names collide (PCellNameError)
        st.library = None
        _fail(pdk, e)
    return st.library


def register(pdk=None, cfg=None):
    """Register libraries.

    ``register("gf180mcuD")`` registers that PDK's library and returns it,
    or None (with one logged error) if it can't. ``register()`` registers
    every PDK the configuration selects and returns {pdk: library or None}.

    Idempotent: a registered library is returned as it is, with no second
    Magic (registering again would replace the library).
    """
    from .config import Config, ConfigError
    if cfg is None:
        try:
            cfg = Config.load(pdk=pdk)
        except ConfigError as e:
            if pdk is not None:
                _fail(pdk, e)
                return None
            _log_error("klayout_magic_pcells: nothing registered: %s" % e)
            return {}
    if pdk is not None:
        return register_all([pdk], cfg)[pdk]
    return register_all(list(cfg.pdks) + list(cfg.pdk_errors), cfg)


def register_all(pdks, cfg):
    """Register ``pdks``; returns {pdk: library or None}. The Magics of all
    of them start first and load their PDKs in parallel."""
    from .backend import make_server
    out = {}
    pending = []
    for p in pdks:
        st = state_for(p)
        if st.library is not None:
            out[p] = st.library
            continue
        if p in cfg.pdk_errors:
            _fail(p, StartError(cfg.pdk_errors[p], hint="Correct KMP_PDKS"))
            out[p] = None
            continue
        try:
            pc = cfg if cfg.pdk == p else cfg.for_pdk(p)
            man = _prepare(pc)
            server = None
            if st.generator is None:
                server = make_server(pc, vendor_cells=man.vendor_cells())
                server.launch()
            pending.append((p, pc, man, server))
        except Exception as e:
            _fail(p, e)
            out[p] = None
    for p, pc, man, server in pending:
        try:
            start_backend(pc, server=server, manifest=man)
        except Exception as e:
            _fail(p, e)
            out[p] = None
            continue
        out[p] = _register_library(p)
    return out


def registered():
    """{pdk: library} of the libraries registered now."""
    return {p: st.library for p, st in states.items() if st.library is not None}


def unregister(pdk=None):
    """Unregister one PDK's library (or every one) and stop its Magic."""
    for p in ([pdk] if pdk else list(states)):
        st = state_for(p)
        lib, st.library = st.library, None
        if lib is not None:
            try:
                lib.unregister()
            except Exception as e:
                log.debug("unregister: %s", e)
        shutdown(p)


def shutdown(pdk=None):
    for p in ([pdk] if pdk else list(states)):
        st = state_for(p)
        if st.server is not None:
            try:
                st.server.close()
            except Exception:
                pass
        if st.cache is not None:
            st.cache.close()
        st.server = st.generator = st.cache = None


def generator(pdk=None):
    return state_for(pdk or primary_pdk()).generator


def dialog_values(device, params=None, pdk=None):
    """The parameters the GUI would store for ``params`` typed into the
    device's PCell form: what Magic's dialog shows after those edits and
    Create, plus the hidden ``kmp_dialog`` state, as a dict for
    ``Layout.create_cell``. Given such a dict with some values changed, the
    edit is one in Magic's "Edit device" dialog followed by Apply.

    ``Layout.create_cell(device, library, params)`` stores ``params`` as
    given (KLayout keeps a PCell's coerced values only in the GUI form and
    on a library refresh) and draws the corrected ones; passing
    ``dialog_values(device, params)`` instead stores the corrected values
    too. ``pdk`` picks the PDK when several registered libraries have the
    device (``rm1``, ``via1``). Raises KeyError for a device no registered
    library has, ValueError for a name several have, and the error that
    stopped Magic's dialog (a refused value, a backend failure) otherwise.
    """
    from .dialog import DIALOG_PARAM, correct
    cands = [pdk] if pdk else [p for p, st in states.items()
                               if st.library is not None and st.manifest is not None
                               and device in st.manifest]
    if not cands:
        raise KeyError("no registered library has a device %r" % device)
    if len(cands) > 1:
        raise ValueError("%s is a device of %s; pass pdk=" % (device, ", ".join(sorted(cands))))
    st = state_for(cands[0])
    if st.library is None or st.manifest is None or device not in st.manifest:
        raise KeyError("the %s library is not registered or has no device %r" % (cands[0], device))
    spec = st.manifest[device]
    lib_layout = st.library.layout()
    decl = lib_layout.pcell_declaration(device)
    given = dict(params or {})
    plist = [given.get(pd.name, pd.default) for pd in decl.get_parameters()]
    names = [pd.name for pd in decl.get_parameters()]
    if spec.kind != "box":
        # coerce_parameters swallows failures (produce reports them); here
        # the caller gets the reason.
        vals = {p.name: plist[names.index(p.name)] for p in spec.params}
        dtext = plist[names.index(DIALOG_PARAM)] if DIALOG_PARAM in names else ""
        correct(spec, vals, dtext or "", st.generator)
    out = decl.coerce_parameters(lib_layout, plist)
    if out is None:  # PCellDeclarationHelper returns the list; be safe
        out = plist
    return dict(zip(names, out))
