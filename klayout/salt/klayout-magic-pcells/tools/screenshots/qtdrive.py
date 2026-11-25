"""Helpers for driving KLayout's Qt GUI from a macro: find widgets, send key
and mouse events, wait, and grab parts of the screen. Used by gui.py.

Everything goes through KLayout's own Qt bindings (pya), so the events reach
the same Qt handlers that a keyboard and mouse would. Screen grabs read the
X server's frame buffer (QScreen.grabWindow on the root window), so they
include tooltips, popups and dialogs as they are on screen.
"""

import os

import pya

QE = pya.QEvent


def app():
    return pya.Application.instance()


def mw():
    return app().main_window()


def cls_of(obj):
    return type(obj).__name__.replace("_Native", "")


def find(root, cls=None, name=None, visible=None):
    """All descendants of root, optionally of one Qt class, with one
    objectName, or visible only."""
    out = []

    def rec(o):
        for c in o.children():
            ok = (cls is None or cls_of(c) == cls) and (name is None or c.objectName == name)
            if ok and visible is not None:
                try:
                    ok = c.isVisible() == visible
                except Exception:
                    ok = False
            if ok:
                out.append(c)
            rec(c)

    rec(root)
    return out


def find1(root, **kw):
    res = find(root, **kw)
    if not res:
        raise RuntimeError("no widget %r under %r" % (kw, root))
    return res[0]


def toplevel(name=None, title=None):
    for w in pya.QApplication.topLevelWidgets():
        if not w.isVisible():
            continue
        if name is not None and w.objectName != name:
            continue
        if title is not None and not w.windowTitle.startswith(title):
            continue
        return w
    return None


def dock(name):
    return find1(mw(), cls="QDockWidget", name=name)


def key(w, k, text="", mods=None):
    mods = pya.Qt.NoModifier if mods is None else mods
    for t in (QE.KeyPress, QE.KeyRelease):
        pya.QApplication.sendEvent(w, pya.QKeyEvent(t, k.to_i(), mods, text))


_KEYS = {".": "Key_Period", "-": "Key_Minus", "+": "Key_Plus", " ": "Key_Space"}


def type_text(w, text, finish="Return"):
    """Focus a line edit, select its text, type over it and press Return
    (or Tab, which leaves the field; in a dialog Return presses its default
    button). The last key is sent as a press only: the form can rebuild its
    widgets while it handles it, so a release would go to a deleted
    widget."""
    w.setFocus()
    w.selectAll()
    for ch in text:
        key(w, getattr(pya.Qt, _KEYS.get(ch, "Key_" + ch.upper())), ch)
    if finish:
        k = getattr(pya.Qt, "Key_" + finish)
        pya.QApplication.sendEvent(w, pya.QKeyEvent(QE.KeyPress, k.to_i(), pya.Qt.NoModifier,
                                                    "\r" if finish == "Return" else "\t"))


def hover(x, y):
    """Move the X pointer (a real motion event), via a point next to it."""
    pya.QCursor.setPos(x - 40, y - 40)
    pya.QCursor.setPos(x, y)


def global_rect(w, margin=0):
    p = w.mapToGlobal(pya.QPoint(0, 0))
    return (p.x - margin, p.y - margin, w.width + 2 * margin, w.height + 2 * margin)


def union(*rects):
    x0 = min(r[0] for r in rects)
    y0 = min(r[1] for r in rects)
    x1 = max(r[0] + r[2] for r in rects)
    y1 = max(r[1] + r[3] for r in rects)
    return (x0, y0, x1 - x0, y1 - y0)


def grab(path, rect=None):
    """Save the screen, or the rectangle (x, y, w, h) of it, as a PNG."""
    scr = pya.QGuiApplication.primaryScreen
    if rect is None:
        pm = scr.grabWindow(0)
    else:
        x, y, w, h = [int(v) for v in rect]
        pm = scr.grabWindow(0, max(x, 0), max(y, 0), w, h)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not pm.save(path, "PNG"):
        raise RuntimeError("could not save %s" % path)


class Canvas:
    """The layout canvas of the current view: clicks in micron coordinates."""

    def __init__(self):
        lvw = [c for c in find(mw(), cls="LayoutViewWidget") if c.isVisible()][0]
        self.widget = find1(lvw, name="canvas")
        self.view = mw().current_view()

    def point(self, x, y):
        """The canvas position of (x, y) um, in (fractional) pixels."""
        p = self.view.viewport_trans() * pya.DPoint(x, y)
        return p.x, self.view.viewport_height() - 1 - p.y

    def move(self, x, y):
        px, py = self.point(x, y)
        g = self.widget.mapToGlobal(pya.QPoint(int(px), int(py)))
        hover(g.x, g.y)

    def click(self, x, y):
        px, py = self.point(x, y)
        o = self.widget.mapToGlobal(pya.QPoint(0, 0))
        b = pya.Qt.LeftButton
        for t, bs in ((QE.MouseButtonPress, b), (QE.MouseButtonRelease, pya.Qt.NoButton)):
            ev = pya.QMouseEvent(t, pya.QPointF(px, py), pya.QPointF(o.x + px, o.y + py), b, bs,
                                 pya.Qt.NoModifier)
            pya.QApplication.sendEvent(self.widget, ev)


class Again(Exception):
    """Raised by a step that waits for something: Steps runs it again
    250 ms later, for at most ``Steps.wait_s`` seconds."""


class Steps:
    """Run a list of (pause in ms, function) one after another on timers, so
    that the event loop runs between steps. The next step is scheduled before
    a step runs, so a step that opens a modal dialog doesn't stop the
    sequence: the dialog's own event loop runs the following steps. A step
    that raises Again is run again until it returns."""

    wait_s = 120.0

    def __init__(self, steps, log_path, on_error):
        self.steps = list(steps)
        self.i = 0
        self.log = open(log_path, "a")
        self.on_error = on_error
        self.timers = []
        self.waiting = None

    def note(self, text):
        self.log.write(text + "\n")
        self.log.flush()

    def start(self, delay=500):
        self._schedule(delay)

    def _schedule(self, delay):
        t = pya.QTimer(mw())
        t.singleShot = True
        t.interval = delay
        t.timeout = self._run
        self.timers.append(t)
        t.start()
        return t

    def _run(self):
        import time
        if self.i >= len(self.steps):
            return
        pause, fn = self.steps[self.i]
        self.i += 1
        nxt = self._schedule(self.steps[self.i][0]) if self.i < len(self.steps) else None
        if self.waiting is None or self.waiting[0] != self.i:
            self.note("step %d: %s" % (self.i, fn.__name__))
        try:
            fn()
            self.waiting = None
        except Again:
            if nxt is not None:
                nxt.stop()
            if self.waiting is None or self.waiting[0] != self.i:
                self.waiting = (self.i, time.monotonic())
            if time.monotonic() - self.waiting[1] > self.wait_s:
                self.note("step %d: %s still waiting after %.0f s" % (self.i, fn.__name__, self.wait_s))
                self.on_error()
                return
            self.i -= 1
            self._schedule(250)
        except Exception:
            import traceback
            self.note(traceback.format_exc())
            self.on_error()
