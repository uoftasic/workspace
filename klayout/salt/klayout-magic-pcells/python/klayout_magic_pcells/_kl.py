"""KLayout modules: ``klayout.db``/``klayout.tl`` (pip module, and inside the
KLayout binary), else ``pya``."""

try:
    import klayout.db as db
    import klayout.tl as tl
except ImportError:  # pragma: no cover - older embedded builds
    import pya as db
    tl = db


def info(msg):
    tl.Logger.info(msg)


def warn(msg):
    tl.Logger.warn(msg)


def error(msg):
    tl.Logger.error(msg)
