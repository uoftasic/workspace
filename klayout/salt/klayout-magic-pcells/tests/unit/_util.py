import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "python"))
sys.path.insert(0, os.path.join(REPO, "tests", "parity"))

try:
    import klayout.db as db  # noqa: F401
    HAVE_KLAYOUT = True
except ImportError:
    db = None
    HAVE_KLAYOUT = False

needs_klayout = unittest.skipUnless(HAVE_KLAYOUT, "the klayout Python module is not installed")
