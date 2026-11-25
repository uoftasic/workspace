"""The Magic menu: Magic's DRC, extraction, netgen LVS and the plugin's
generated-layer and port checks from KLayout's main window.

The autorun macro calls ``install_menu()`` after ``register()``, and
``register_recipe()`` once. ``install_menu()`` inserts a top-level menu
"Magic" before Help, through ``pya.Action`` and the main window's
``AbstractMenu`` only (reading a replaced menu's Qt objects crashed
KLayout; design-0.6.md 2.4). It does nothing without a main window
(``klayout -b``, plain ``python3``) or with ``KMP_MENU=0``, and a second
call leaves one menu.

Each entry takes the current view's layout and cell, chooses the PDK
(``pdkchoice.choose_pdk(..., hint_decides=False)``; when that can't decide,
a dialog lists the candidates with the PDK variable's guess preselected),
and calls the feature's ``prepare(layout, cell, cfg, data, options)``
(the task API, design-0.6.md 2.4). ``Task.start()`` starts Magic; a
non-modal progress dialog polls ``Task.poll()`` from a 200 ms ``QTimer``
(design-0.6.md 2.4) and its Cancel button calls ``Task.cancel()``. When the
task ends, the Marker Database Browser opens on ``Outcome.rdb`` and a
message gives ``Outcome.summary``. Without Qt the call blocks with
``pya.AbsoluteProgress``. One job runs at a time per view; a second request
asks whether to cancel the first. An error in a feature becomes a message
box.

The browser's Rerun button calls the recipe ``klayout_magic_pcells`` with
the RDB's generator (design-0.6.md 2.7), which runs the same check again on the
view's layout and replaces the database; the new one carries the same
generator.

Choices are remembered in ``state.json`` beside ``config.ini``
(``~/.config/klayout-magic-pcells/state.json``): the last DRC style, mode
and area, and the LVS schematic and subcircuit per layout file and cell.

This module imports no Qt and no ``pya`` at import time; the command line
never needs it.
"""

import importlib
import json
import os
import tempfile
import time
import traceback

MENU = "kmp_magic_menu"
RECIPE = "klayout_magic_pcells"
POLL_MS = 200
STATE_SCHEMA = 1
PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
# The repository (or the installed Salt package) holds docs/gaps/ two levels
# above the package: <root>/python/klayout_magic_pcells.
ROOT_DIR = os.path.dirname(os.path.dirname(PACKAGE_DIR))

MODULES = {"drc": "drcjob", "extract": "lvsjob", "lvs": "lvsjob", "layers": "layercheck",
           "ports": "portcheck"}
TITLES = {"drc": "Magic DRC", "extract": "Extraction with Magic", "lvs": "LVS with netgen",
          "layers": "Generated-layer check", "ports": "Port check"}

DRC_MODES = [("hierarchical", "Hierarchical: every cell, then the top cell"),
             ("flat", "Flat: Magic's verdict on the flattened mask")]
DRC_AREAS = [("cell", "Whole cell"), ("visible", "Visible area"), ("selection", "Selection box")]
SCHEMATIC_FILTER = "SPICE or CDL (*.spice *.sp *.cir *.cdl *.net *.ckt);;All files (*)"


def _pya():
    """KLayout's ``pya``, imported on first use (None without KLayout)."""
    try:
        import pya
    except ImportError:
        return None
    return pya


class UserError(Exception):
    """Something the user can fix; shown without a traceback."""


class Cancelled(Exception):
    """The user closed a dialog."""


# -- where we are --------------------------------------------------------------

def main_window():
    """KLayout's main window, or None (batch mode, plain python3)."""
    pya = _pya()
    if pya is None or not hasattr(pya, "Application"):
        return None
    app = pya.Application.instance()
    return app.main_window() if app is not None else None


def has_qt():
    """True in the KLayout GUI: Qt bindings and a main window. ``pya`` in
    plain ``python3`` has no ``QTimer``, and ``klayout -b`` no main window."""
    pya = _pya()
    if pya is None or not hasattr(pya, "QTimer"):
        return False
    return main_window() is not None


def _log_error(text):
    try:
        from ._kl import error
        error(text)
    except Exception:
        import logging
        logging.getLogger("klayout_magic_pcells").error(text)


# -- remembered choices (state.json) -------------------------------------------

def state_path(env=None):
    """``state.json`` in the folder of ``config.ini``."""
    from .config import config_file_path
    return os.path.join(os.path.dirname(config_file_path(env)), "state.json")


class State:
    """The GUI's remembered choices. A missing or unreadable file is empty;
    writes go through a temporary file, so a crash leaves the old file."""

    def __init__(self, path=None):
        self.path = path or state_path()

    def load(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return {"schema": STATE_SCHEMA}
        if not isinstance(data, dict) or data.get("schema") != STATE_SCHEMA:
            return {"schema": STATE_SCHEMA}
        return data

    def save(self, data):
        data = dict(data)
        data["schema"] = STATE_SCHEMA
        d = os.path.dirname(self.path)
        os.makedirs(d, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".state-", suffix=".json", dir=d)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=1, sort_keys=True)
                f.write("\n")
            os.replace(tmp, self.path)
        except BaseException:
            try:
                os.remove(tmp)
            except OSError:
                pass
            raise

    def lvs(self, file, cell):
        """{"schematic": path, "subckt": name} for this layout file (""
        for one never saved) and cell, or None."""
        row = self.load().get("lvs", {}).get(file or "", {}).get(cell)
        return dict(row) if isinstance(row, dict) else None

    def set_lvs(self, file, cell, schematic, subckt):
        data = self.load()
        data.setdefault("lvs", {}).setdefault(file or "", {})[cell] = {"schematic": schematic,
                                                                      "subckt": subckt}
        self.save(data)

    def drc(self):
        """The last DRC dialog's {"style", "mode", "area"} ({} at first)."""
        row = self.load().get("drc", {})
        return dict(row) if isinstance(row, dict) else {}

    def set_drc(self, style, mode, area):
        data = self.load()
        data["drc"] = {"style": style, "mode": mode, "area": area}
        self.save(data)


def _state():
    return State()


# -- Rerun parameters -----------------------------------------------------------

def _truthy(v):
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def options_from_params(params):
    """What a Rerun runs, from an RDB generator's parameters (the features
    write them with ``markers.recipe_generator``; every value is a string).
    Returns (cmd, cell names, options, pdk or None). Raises ValueError for a
    generator this version doesn't know."""
    p = {k: v for k, v in params.items() if k != "rdb_index"}
    cmd = p.get("cmd")
    if cmd not in MODULES:
        raise ValueError("this report's Rerun names the command %r, which the plugin does not have" % (cmd,))
    cell = p.get("cell") or ""
    if not cell:
        raise ValueError("this report's Rerun names no cell")
    file = p.get("file") or ""
    pdk = p.get("pdk") or None
    if cmd == "drc":
        # drcjob joins several cells with commas.
        cells = [c for c in cell.split(",") if c]
        opts = {"style": p.get("style") or None, "mode": p.get("mode") or None,
                "box": p.get("box") or None, "file": file}
    elif cmd in ("extract", "lvs"):
        cells = [cell]
        opts = {"cmd": cmd, "file": file, "flatglob": _truthy(p.get("flatglob", "")),
                "ports_from_labels": _truthy(p.get("ports_from_labels", ""))}
        if cmd == "extract":
            opts["caps"] = _truthy(p.get("caps", ""))
        else:
            opts["schematic"] = p.get("schematic") or ""
            opts["schematic_cell"] = p.get("schematic_cell") or None
    elif cmd == "layers":
        cells = [cell]
        opts = {"file": file}
    else:
        cells = [cell]
        opts = {"file": file, "magic": _truthy(p.get("magic", ""))}
    return cmd, cells, opts, pdk


def command_text(cmd, file, cell, pdk, options):
    """The command line that runs the same check, for the RDB descriptions
    of the layers and ports checks (drcjob and lvsjob write their own)."""
    parts = ["python3", "-m", "klayout_magic_pcells", cmd, file or "LAYOUT", "--cell", cell, "--pdk", pdk]
    if cmd == "ports" and options.get("magic"):
        parts.append("--magic")
    return " ".join(parts)


def gaps_page(pdk, root=None):
    """The path of docs/gaps/<pdk>.md, or None when it is not installed."""
    path = os.path.join(root or ROOT_DIR, "docs", "gaps", "%s.md" % pdk)
    return path if os.path.isfile(path) else None


def settings_rows(cfg):
    """(setting, where to set it, value, source) for the Settings dialog."""
    from . import config as config_mod
    var = {key: v for v, key in config_mod._KEYS}
    per_pdk = {"magicrc": "KMP_MAGICRC_%s", "manifest": "KMP_MANIFEST_%s",
               "netgen_setup": "KMP_NETGEN_SETUP_%s"}
    ini_key = {"cache_enabled": "cache"}
    rows = []
    for name, value, source in cfg.describe():
        key = ini_key.get(name, name)
        if name in per_pdk:
            where = "%s, or %s in [kmp:%s]" % (per_pdk[name] % config_mod.pdk_env_suffix(cfg.pdk), name, cfg.pdk)
        elif key in var:
            where = "%s, or %s in [kmp]" % (var[key], key)
        else:
            where = ""
        rows.append((name, where, str(value), source or ""))
    return rows


# -- the menu ---------------------------------------------------------------------

_actions = {}


def _menu_wanted(env=None):
    env = os.environ if env is None else env
    v = env.get("KMP_MENU", "")
    if v != "":
        return _truthy(v)
    try:
        from .config import Config
        return bool(Config.load(env=env).menu)
    except Exception:
        # A broken configuration must not hide the menu; its entries say
        # what is wrong.
        return True


def entries():
    """(name, title, callback) of the menu, ("-", None, None) for a separator."""
    return [
        ("run_drc", "Run Magic DRC...", on_drc),
        ("drc_visible", "Check the visible area with Magic DRC", on_drc_visible),
        ("-", None, None),
        ("extract", "Extract with Magic...", on_extract),
        ("lvs", "LVS with netgen...", on_lvs),
        ("-", None, None),
        ("layers", "Check generated layers", on_layers),
        ("ports", "Check ports", on_ports),
        ("-", None, None),
        ("gaps", "Rule differences", on_gaps),
        ("settings", "Settings...", on_settings),
    ]


def _guarded(title, fn):
    def run():
        try:
            fn()
        except Cancelled:
            pass
        except UserError as e:
            message("warning", title, str(e))
        except Exception as e:
            _log_error("klayout_magic_pcells: %s failed:\n%s" % (title, traceback.format_exc()))
            message("critical", title, "%s failed: %s\n\nThe traceback is in KLayout's log "
                    "(File > Log Viewer)." % (title, e))
    return run


def install_menu(env=None):
    """Insert the Magic menu before Help. Returns True when it was inserted;
    False without a main window or with KMP_MENU=0. Calling it again
    replaces the menu."""
    mw = main_window()
    if mw is None or not _menu_wanted(env):
        return False
    pya = _pya()
    menu = mw.menu()
    if menu.is_menu(MENU):
        menu.delete_item(MENU)
    _actions.clear()
    menu.insert_menu("help_menu", MENU, "Magic")
    for i, (name, title, callback) in enumerate(entries()):
        if name == "-":
            menu.insert_separator(MENU + ".end", "sep%d" % i)
            continue
        action = pya.Action()
        action.title = title
        action.on_triggered = _guarded(title.rstrip("."), callback)
        menu.insert_item(MENU + ".end", name, action)
        _actions[name] = action
    return True


def remove_menu():
    mw = main_window()
    if mw is not None and mw.menu().is_menu(MENU):
        mw.menu().delete_item(MENU)
    _actions.clear()


# -- messages and windows -----------------------------------------------------------

_windows = []   # message boxes, text windows and old progress dialogs we made
_rdbs = []      # report databases handed to views (kept, so Python never frees one)


def _prune():
    """Destroy the hidden windows of earlier jobs (never from their own
    signal handlers)."""
    keep = []
    for w in _windows:
        try:
            if w._destroyed():
                continue
            if w.isVisible():
                keep.append(w)
            else:
                w._destroy()
        except Exception:
            pass
    _windows[:] = keep


def message(kind, title, text, details=None, on_close=None):
    """A non-modal message box (info, warning or critical) in the GUI; the
    log elsewhere. ``details`` goes below ``text`` in smaller type;
    ``on_close()`` runs when the box closes."""
    pya = _pya()
    if not has_qt():
        full = text if not details else "%s\n%s" % (text, details)
        if kind == "critical":
            _log_error("%s: %s" % (title, full))
        else:
            try:
                from ._kl import info
                info("%s: %s" % (title, full))
            except Exception:
                pass
        return None
    _prune()
    mb = pya.QMessageBox(main_window())
    mb.objectName = "kmp_message"
    mb.windowTitle = "Magic: %s" % title
    mb.text = text
    if details:
        mb.informativeText = details
    mb.icon = {"info": pya.QMessageBox.Information, "warning": pya.QMessageBox.Warning,
               "critical": pya.QMessageBox.Critical}[kind]
    mb.addButton(pya.QMessageBox.Ok)
    mb.windowModality = pya.Qt.NonModal
    if on_close is not None:
        mb.finished = lambda *_: on_close()
    mb.show()
    _windows.append(mb)
    return mb


BROWSER = "MarkerBrowserDialog"   # the object name of KLayout's Marker Database Browser


def browser_windows():
    """KLayout's Marker Database Browsers that are on screen. Each is a window
    of its own, without a parent (lay::Browser), so the window manager does not
    keep it above the main window."""
    pya = _pya()
    try:
        widgets = pya.QApplication.topLevelWidgets()
    except Exception:
        return []
    out = []
    for w in widgets:
        try:
            if w.objectName == BROWSER and w.isVisible():
                out.append(w)
        except Exception:
            pass
    return out


def raise_browser():
    """Bring the Marker Database Browser in front of the main window. Under
    XFCE with KLayout maximised, closing the result message gives the focus
    back to the main window, which then covers the browser."""
    for w in browser_windows():
        try:
            w.raise_()
            w.activateWindow()
        except Exception:
            pass


def fit_size(want, available, margin=(40, 70)):
    """(width, height): ``want`` made small enough for the screen area
    ``available`` (width, height), less ``margin`` for the window's frame
    and title bar."""
    w, h = want
    if available:
        w = min(w, max(200, available[0] - margin[0]))
        h = min(h, max(150, available[1] - margin[1]))
    return w, h


def _value(x):
    """A pya attribute that is a property in some bindings and a method in others."""
    return x() if callable(x) else x


def _available():
    """(width, height) of the screen area windows may use (without panels),
    or None."""
    pya = _pya()
    for get in (lambda: _value(_value(pya.QGuiApplication.primaryScreen).availableGeometry),
                lambda: _value(pya.QApplication.desktop).availableGeometry(main_window())):
        try:
            g = get()
            return (int(_value(g.width)), int(_value(g.height)))
        except Exception:
            continue
    return None


def _resizable(dlg, size):
    """Size a window to fit the screen, and ask the window manager for a
    maximise button. It stays a dialog of the main window, which keeps it
    above that window."""
    pya = _pya()
    try:
        dlg.setWindowFlags(pya.Qt.Dialog | pya.Qt.WindowTitleHint | pya.Qt.WindowSystemMenuHint
                           | pya.Qt.WindowMaximizeButtonHint | pya.Qt.WindowCloseButtonHint)
    except Exception:
        pass
    w, h = fit_size(size, _available())
    dlg.resize(w, h)


def ask_yes_no(title, text):
    pya = _pya()
    res = pya.MessageBox.question("Magic: %s" % title, text, pya.MessageBox.Yes + pya.MessageBox.No)
    return res == pya.MessageBox.Yes


def show_text(title, text, name="kmp_text", markdown=False, size=(900, 600), at_end=False):
    """A non-modal window with ``text`` (plain, or Markdown when asked),
    sized to fit the screen; ``at_end`` scrolls to the last line."""
    pya = _pya()
    if not has_qt():
        return None
    _prune()
    dlg = pya.QDialog(main_window())
    dlg.objectName = name
    dlg.windowTitle = title
    _resizable(dlg, size)
    lay = pya.QVBoxLayout(dlg)
    if markdown:
        view = pya.QTextBrowser(dlg)
        view.openExternalLinks = True
        view.setMarkdown(text)
    else:
        view = pya.QPlainTextEdit(dlg)
        view.readOnly = True
        view.lineWrapMode = pya.QPlainTextEdit.NoWrap
        try:
            view.font = pya.QFontDatabase.systemFont(pya.QFontDatabase.FixedFont)
        except Exception:
            pass
        view.plainText = text
    view.objectName = "text"
    lay.addWidget(view)
    bb = pya.QDialogButtonBox(dlg)
    close = bb.addButton(pya.QDialogButtonBox.Close)
    close.objectName = "close"
    bb.rejected = lambda: dlg.hide()
    lay.addWidget(bb)
    dlg.windowModality = pya.Qt.NonModal
    dlg.show()
    if at_end:
        try:
            view.moveCursor(pya.QTextCursor.End)
            view.ensureCursorVisible()
        except Exception:
            pass
    _windows.append(dlg)
    return dlg


def _read(path, limit=2000000):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read(limit)
    except OSError as e:
        return "(cannot read %s: %s)" % (path, e)


# -- dialogs ---------------------------------------------------------------------------

def _buttons(dlg):
    pya = _pya()
    bb = pya.QDialogButtonBox(dlg)
    ok = bb.addButton(pya.QDialogButtonBox.Ok)
    cancel = bb.addButton(pya.QDialogButtonBox.Cancel)
    ok.objectName = "ok"
    cancel.objectName = "cancel"
    bb.accepted = lambda: dlg.accept()
    bb.rejected = lambda: dlg.reject()
    return bb


def _radios(dlg, form, label, choices, current, prefix):
    pya = _pya()
    box = pya.QWidget(dlg)
    lay = pya.QVBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    group = pya.QButtonGroup(dlg)
    radios = {}
    for key, text in choices:
        rb = pya.QRadioButton(text, box)
        rb.objectName = prefix + key
        lay.addWidget(rb)
        group.addButton(rb)
        radios[key] = rb
    radios[current if current in radios else choices[0][0]].checked = True
    form.addRow(label, box)
    return radios


def ask_drc_options(styles, current, pdk):
    """{"style", "mode", "area"} or None on Cancel."""
    pya = _pya()
    dlg = pya.QDialog(main_window())
    dlg.objectName = "kmp_drc_dialog"
    dlg.windowTitle = "Run Magic DRC (%s)" % pdk
    form = pya.QFormLayout(dlg)
    style = pya.QComboBox(dlg)
    style.objectName = "style"
    for s in styles:
        style.addItem(s)
    if current.get("style") in styles:
        style.currentIndex = styles.index(current["style"])
    form.addRow("Style", style)
    radios = _radios(dlg, form, "Mode", DRC_MODES, current.get("mode"), "mode_")
    area = pya.QComboBox(dlg)
    area.objectName = "area"
    keys = [k for k, _ in DRC_AREAS]
    for _, text in DRC_AREAS:
        area.addItem(text)
    area.currentIndex = keys.index(current.get("area")) if current.get("area") in keys else 0
    form.addRow("Area", area)
    note = pya.QLabel("Hierarchical mode checks every cell and then the top cell; Magic's check from "
                      "the top cell alone can report fewer errors. An area check runs Magic on the whole "
                      "cell and keeps the errors that touch the area.", dlg)
    note.wordWrap = True
    form.addRow(note)
    form.addRow(_buttons(dlg))
    try:
        if dlg.exec_() != 1:
            return None
        mode = [k for k, rb in radios.items() if rb.isChecked()][0]
        return {"style": style.currentText, "mode": mode, "area": keys[area.currentIndex]}
    finally:
        dlg._destroy()


def extract_title(pdk):
    """The Extract dialog's title. The cell goes in the dialog, not the
    title, which the window manager cuts at the dialog's width."""
    return "Extract with Magic (%s)" % pdk


def ask_extract_options(cell, pdk):
    """{"caps": bool} or None on Cancel."""
    pya = _pya()
    dlg = pya.QDialog(main_window())
    dlg.objectName = "kmp_extract_dialog"
    dlg.windowTitle = extract_title(pdk)
    dlg.resize(420, dlg.height)
    form = pya.QFormLayout(dlg)
    cell_label = pya.QLabel(cell, dlg)
    cell_label.objectName = "cell"
    form.addRow("Cell", cell_label)
    radios = _radios(dlg, form, "Netlist", [("plain", "Netlist only"),
                                           ("caps", "With parasitic capacitance")], "plain", "kind_")
    form.addRow(_buttons(dlg))
    try:
        if dlg.exec_() != 1:
            return None
        return {"caps": radios["caps"].isChecked()}
    finally:
        dlg._destroy()


def _subckts(path):
    from . import netgen
    try:
        return netgen.subcircuits(path) if path and os.path.isfile(path) else []
    except OSError:
        return []


def ask_lvs_options(cell, current, pdk):
    """{"schematic": path, "subckt": name} or None on Cancel. The
    subcircuit list comes from the file's .subckt lines; the one named like
    the cell is chosen unless ``current`` names another."""
    pya = _pya()
    current = current or {}
    dlg = pya.QDialog(main_window())
    dlg.objectName = "kmp_lvs_dialog"
    dlg.windowTitle = "LVS of %s with netgen (%s)" % (cell, pdk)
    dlg.resize(620, 130)
    form = pya.QFormLayout(dlg)
    row = pya.QWidget(dlg)
    hl = pya.QHBoxLayout(row)
    hl.setContentsMargins(0, 0, 0, 0)
    path = pya.QLineEdit(row)
    path.objectName = "schematic"
    path.text = current.get("schematic", "")
    browse = pya.QPushButton("Browse...", row)
    browse.objectName = "browse"
    hl.addWidget(path)
    hl.addWidget(browse)
    form.addRow("Schematic", row)
    sub = pya.QComboBox(dlg)
    sub.objectName = "subckt"
    form.addRow("Subcircuit", sub)
    shown = [None]

    def fill(*_):
        if shown[0] == path.text:
            return
        shown[0] = path.text
        names = _subckts(path.text)
        sub.clear()
        for n in names:
            sub.addItem(n)
        want = current.get("subckt") if current.get("schematic") == path.text else None
        for cand in (want, cell):
            if cand in names:
                sub.currentIndex = names.index(cand)
                break

    def pick(*_):
        start = os.path.dirname(path.text) if path.text else os.getcwd()
        f = pya.FileDialog.ask_open_file_name("Schematic for LVS", start, SCHEMATIC_FILTER)
        if f:
            path.text = f
            fill()

    browse.clicked = pick
    path.editingFinished = fill
    path.textChanged = fill
    fill()
    form.addRow(_buttons(dlg))
    try:
        while True:
            if dlg.exec_() != 1:
                return None
            fill()
            if not path.text or not os.path.isfile(path.text):
                pya.MessageBox.warning("Magic: LVS", "Choose a schematic file (SPICE or CDL).", pya.MessageBox.Ok)
                continue
            if sub.count == 0:
                pya.MessageBox.warning("Magic: LVS", "%s has no .subckt line." % path.text, pya.MessageBox.Ok)
                continue
            if plugin_netlist(path.text) and not ask_yes_no(
                    "LVS", "%s is a netlist that Extract with Magic wrote from a layout, not a schematic. "
                    "LVS against it compares Magic's netlist with Magic's netlist.\n\nUse it anyway?"
                    % path.text):
                continue
            return {"schematic": os.path.abspath(path.text), "subckt": sub.currentText}
    finally:
        dlg._destroy()


def plugin_netlist(path):
    """True for a netlist file that Extract with Magic wrote (its first line
    is the plugin's header), which the LVS dialog's file list offers beside
    the schematics."""
    from .lvsjob import written_by_plugin
    return bool(path) and written_by_plugin(path)


def ask_pdk(candidates, preselect, why):
    """One of ``candidates``, or None on Cancel."""
    pya = _pya()
    dlg = pya.QDialog(main_window())
    dlg.objectName = "kmp_pdk_dialog"
    dlg.windowTitle = "Which PDK?"
    form = pya.QFormLayout(dlg)
    label = pya.QLabel("%s.\nChoose the PDK whose Magic checks this layout. The choice holds for this "
                       "layout until KLayout closes." % why.rstrip("."), dlg)
    label.wordWrap = True
    form.addRow(label)
    combo = pya.QComboBox(dlg)
    combo.objectName = "pdk"
    for p in candidates:
        combo.addItem(p)
    if preselect in candidates:
        combo.currentIndex = candidates.index(preselect)
    form.addRow("PDK", combo)
    form.addRow(_buttons(dlg))
    try:
        if dlg.exec_() != 1:
            return None
        return combo.currentText
    finally:
        dlg._destroy()


# -- the context of a run ------------------------------------------------------------

class Context:
    """The view, cellview, layout, cell, file and PDK a check runs on."""

    def __init__(self, view, cv, layout, cell, file, cfg, pdk, reason, data):
        self.view = view
        self.cv = cv
        self.cv_index = cv.index()
        self.layout = layout
        self.cell = cell
        self.file = file
        self.cfg = cfg
        self.pdk = pdk
        self.reason = reason
        self.data = data


_pdk_answers = {}   # layout file (or id of an unsaved layout) -> the PDK the user chose


def _layout_key(layout, file):
    return file or "layout:%d" % id(layout)


def choose_pdk(layout, file, base, explicit=None):
    """(pdk, reason) for the layout; asks when pdkchoice can't decide."""
    from .pdkchoice import PdkChoiceError, choose_pdk as choose
    key = _layout_key(layout, file)
    if not explicit and key in _pdk_answers:
        return _pdk_answers[key], "chosen in the dialog"
    try:
        return choose(layout, explicit=explicit, cfg=base, hint_decides=False)
    except PdkChoiceError as e:
        if explicit or not has_qt():
            if e.hint and not explicit:
                return e.hint, getattr(e, "hint_reason", None) or "a guess from the PDK variable (PDK=%s)" % e.hint
            raise UserError(str(e))
        pdk = ask_pdk(list(e.candidates), e.hint, pdk_question(e))
        if pdk is None:
            raise Cancelled()
        _pdk_answers[key] = pdk
        return pdk, "chosen in the dialog"


def pdk_question(e):
    """The PDK dialog's first sentence for a PdkChoiceError: the technology
    that the layout's layers contradict, or that it names none."""
    why = getattr(e, "why", None)
    if why:
        return why[0].upper() + why[1:]
    if e.candidates:
        return "The layout names no technology and no PCell library of the plugin"
    return str(e)


def _magic_problems(cfg):
    """What stops a Magic job: the executable and the PDK's rcfile (the
    manifest only matters to the PCells)."""
    return [p for p in cfg.problems() if not p.startswith("manifest ")]


def context(needs_magic=True, needs_netgen=False, view=None, cv=None, pdk=None):
    """The current view's Context; raises UserError with what is missing."""
    from . import _hint_setup, pdkdata
    from .config import Config, ConfigError
    mw = main_window()
    if view is None:
        view = mw.current_view() if mw is not None else None
    if view is None:
        raise UserError("Open a layout first.")
    if cv is None:
        cv = view.active_cellview()
    if cv is None or not cv.is_valid() or cv.cell is None:
        raise UserError("The current view shows no cell.")
    layout = cv.layout()
    cell = cv.cell
    file = os.path.abspath(cv.filename()) if cv.filename() else ""
    try:
        base = Config.load()
    except ConfigError as e:
        raise UserError("The plugin's configuration has an error: %s" % e)
    pdk, reason = choose_pdk(layout, file, base, explicit=pdk)
    cfg = base.for_pdk(pdk)
    if needs_magic:
        problems = _magic_problems(cfg)
        if problems:
            raise UserError("%s. %s." % ("; ".join(problems), _hint_setup(pdk)))
    if needs_netgen:
        problems = cfg.job_problems()
        if problems:
            raise UserError("; ".join(problems) + ".")
    try:
        data = pdkdata.load(pdk)
    except Exception as e:
        raise UserError("The plugin has no PDK data for %s: %s" % (pdk, e))
    return Context(view, cv, layout, cell, file, cfg, pdk, reason, data)


def _cell_box(ctx, box):
    """A DBox of the view (the context cell's coordinates) in the coordinates
    of the cell the check runs on."""
    try:
        t = ctx.cv.context_dtrans()
        box = t.inverted() * box
    except Exception:
        pass
    return (box.left, box.bottom, box.right, box.top)


# -- running a task --------------------------------------------------------------------

_runs = []   # the running jobs, one per view at most
_old = []    # finished runs' progress dialogs and timers, destroyed when the next one opens


def _dispose_old():
    while _old:
        o = _old.pop()
        try:
            if not o._destroyed():
                o._destroy()
        except Exception:
            pass


def running(view=None):
    """The running jobs (of ``view``)."""
    return [r for r in _runs if view is None or r.view is view]


class Run:
    """One task with its progress display: a non-modal QProgressDialog
    polled by a QTimer (u2_progress.ProgressDialog over u1_poll.TimerPoll),
    or, without Qt, a blocking pya.AbsoluteProgress loop."""

    def __init__(self, title, task, view, on_done):
        self.title = title
        self.task = task
        self.view = view
        self.on_done = on_done
        self.done = False
        self.cancelled = False
        self.outcome = None
        self.error = None
        self.dialog = None
        self.timer = None
        self.t0 = None
        self.ticks = 0
        self.job_label = None

    def start(self):
        self.t0 = time.monotonic()
        _runs.append(self)
        try:
            self.task.start()
            out = self.task.poll()
        except Exception:
            self._finish(None, traceback.format_exc())
            return self
        if out is not None:
            # A cached job, or a check without Magic: no dialog.
            self._finish(out)
            return self
        if has_qt():
            self._show()
        else:
            self._block()
        return self

    def stage_text(self):
        """"<title>: <stage> (<s> s)". A task's own stage ("starting
        flattened inv", "cached inv") names the job; Magic's stage lines
        while it runs ("checking inv") follow it, so the flattened layout's
        check reads "flattened inv: checking inv"."""
        st = getattr(self.task, "stage", None)
        if not st:
            text = "starting Magic"
        elif isinstance(st, (tuple, list)):
            text = " ".join(str(x) for x in st if x not in (None, "", 0))
        else:
            text = str(st)
        for word in ("starting ", "cached "):
            if text.startswith(word):
                self.job_label = text[len(word):]
                break
        else:
            label = getattr(self, "job_label", None)
            if label and label.startswith("flattened ") and text != "starting Magic":
                text = "%s: %s" % (label, text)
        return "%s: %s (%.0f s)" % (self.title, text, time.monotonic() - self.t0)

    def _show(self):
        pya = _pya()
        _prune()
        _dispose_old()
        mw = main_window()
        dlg = self.dialog = pya.QProgressDialog(mw)
        dlg.objectName = "kmp_progress"
        dlg.windowTitle = "Magic: %s" % self.title
        dlg.labelText = self.stage_text()
        dlg.cancelButtonText = "Cancel"
        dlg.minimum = 0
        dlg.maximum = 0          # a busy bar: a job has no known length
        dlg.minimumDuration = 0  # Qt's default (4 s) would hide a short job's dialog
        dlg.autoReset = False
        dlg.autoClose = False
        dlg.windowModality = pya.Qt.NonModal
        dlg.canceled = self.cancel
        dlg.resize(460, dlg.height)
        self.timer = pya.QTimer(mw)
        self.timer.interval = POLL_MS
        self.timer.timeout = self._tick
        dlg.show()
        self.timer.start()

    def _tick(self):
        if self.done:
            return
        self.ticks += 1
        try:
            out = self.task.poll()
        except Exception:
            self._finish(None, traceback.format_exc())
            return
        if out is not None:
            self._finish(out)
        elif self.dialog is not None:
            self.dialog.labelText = self.stage_text()

    def _block(self):
        pya = _pya()
        prog = pya.AbsoluteProgress(self.title)
        prog.format = "%.0f s"
        prog.unit = 1
        try:
            while not self.done:
                out = self.task.poll()
                if out is not None:
                    self._finish(out)
                    break
                prog.desc = self.stage_text()
                try:
                    prog.set(int(time.monotonic() - self.t0), True)
                except Exception:   # KLayout's Cancel: "Operation cancelled"
                    self.cancel()
                    break
                time.sleep(0.05)
        except Exception:
            self._finish(None, traceback.format_exc())
        finally:
            prog._destroy()

    def cancel(self):
        """Kill the job (the progress dialog's Cancel)."""
        if self.done:
            return
        self.cancelled = True
        out = None
        try:
            self.task.cancel()
            out = self.task.poll()
        except Exception:
            pass
        self._finish(out)

    def _finish(self, out, error=None):
        if self.done:
            return
        self.done = True
        self.outcome = out
        self.error = error
        # Hidden, not destroyed: this may run inside the dialog's own
        # canceled signal or the timer's timeout.
        if self.timer is not None:
            self.timer.stop()
            _old.append(self.timer)
        if self.dialog is not None:
            self.dialog.hide()
            _old.append(self.dialog)
        if self in _runs:
            _runs.remove(self)
        try:
            self.on_done(self)
        except Exception:
            _log_error("klayout_magic_pcells: %s: showing the result failed:\n%s"
                       % (self.title, traceback.format_exc()))
            message("critical", self.title, "Showing the result failed: %s" % traceback.format_exc(limit=1))


def _busy(view, title):
    """Ask before a second job in one view; cancel the first on Yes. False
    when the user keeps the first."""
    for r in running(view):
        if not has_qt():
            return False
        if not ask_yes_no(title, "%s is still running in this view.\n\nCancel it and start %s?"
                          % (r.title, title)):
            return False
        r.cancel()
    return True


def prepare(ctx, cmd, cells, options):
    """The feature's Task (the task API, design-0.6.md 2.4)."""
    mod = importlib.import_module("klayout_magic_pcells." + MODULES[cmd])
    if cmd == "drc":
        return mod.prepare(ctx.layout, cells, ctx.cfg, ctx.data, options)
    return mod.prepare(ctx.layout, cells[0], ctx.cfg, ctx.data, options)


def release(out):
    """``jobs.release`` for an outcome whose files have been read: its tmp-*
    job directories (DRC's flattened checks too) go; a key's stays."""
    if out is None:
        return []
    from . import jobs
    files = getattr(out, "files", None) or {}
    return jobs.release([out, files.get("flat_checks") or []])


def drc_classes_text(out):
    """The DRC message's lines about hierarchical mode's subcell boxes, from
    ``Outcome.classes`` and ``Outcome.alone``, or ""."""
    try:
        from .drcjob import ALONE, FLAT_ONLY, IN_TOP, alone_category
    except ImportError:
        return ""
    lines = []
    # drcjob's summary carries the classes' sentence already (since fix-drc).
    said = "the subcells' own checks list" in (getattr(out, "summary", "") or "")
    for name, c in sorted((getattr(out, "classes", None) or {}).items()):
        sub = c.get(IN_TOP, 0) + c.get(FLAT_ONLY, 0) + c.get(ALONE, 0)
        if sub and not said:
            lines.append("%s: of the %d box%s the subcells' own checks list, %d %s in the top cell's check "
                         "(errors), %d only in the flattened layout's check (errors), %d only when the subcell "
                         "is checked on its own (information)."
                         % (name, sub, "" if sub == 1 else "es", c.get(IN_TOP, 0),
                            "is" if c.get(IN_TOP, 0) == 1 else "are", c.get(FLAT_ONLY, 0), c.get(ALONE, 0)))
    by_cell = {}
    for cell, why, _box in getattr(out, "alone", None) or []:
        try:
            rule = alone_category(why, cell)[1]
        except Exception:
            rule = why
        by_cell.setdefault(cell, []).append(rule)
    for cell, rules in sorted(by_cell.items()):
        counts = {}
        for r in rules:
            counts[r] = counts.get(r, 0) + 1
        lines.append("%d box%s only when %s is checked on its own (information, not counted as errors): %s."
                     % (len(rules), "" if len(rules) == 1 else "es", cell,
                        ", ".join("%s %d" % (r, n) for r, n in sorted(counts.items()))))
    return "\n".join(lines)


def show_outcome(ctx, run, rdb_index=None, after=None):
    """Put the outcome's RDB into the view and open the browser, then the
    summary. ``rdb_index``: replace that database (Rerun). The outcome's
    tmp-* job directories are released once its files are read, unless
    ``after`` set ``out.kmp_hold`` (it releases them itself)."""
    out = run.outcome
    try:
        _show_outcome(ctx, run, rdb_index, after)
    finally:
        if out is not None and not getattr(out, "kmp_hold", False):
            release(out)


def _show_outcome(ctx, run, rdb_index, after):
    title = run.title
    if run.error:
        _log_error("klayout_magic_pcells: %s failed:\n%s" % (title, run.error))
        message("critical", title, "%s failed: %s\n\nThe traceback is in KLayout's log (File > Log Viewer)."
                % (title, run.error.strip().splitlines()[-1]))
        return
    out = run.outcome
    if run.cancelled:
        message("info", title, "%s was cancelled; Magic was stopped." % title)
        return
    if out is None:
        message("critical", title, "%s ended without a result." % title)
        return
    view = ctx.view
    if view is not None and not view._destroyed():
        db = out.rdb.db
        _rdbs.append(db)
        if rdb_index is not None and 0 <= rdb_index < view.num_rdbs():
            view.replace_rdb(rdb_index, db)
            idx = rdb_index
        else:
            idx = view.add_rdb(db)
        view.show_rdb(idx, ctx.cv_index)
    # after() first: extract's names the file written in the summary.
    extra = after(out) if after is not None else None
    head, details = message_texts(out, extra)
    kind = {0: "info", 1: "warning"}.get(out.status, "critical")
    message(kind, title, head, details, on_close=raise_browser)


def message_texts(out, extra=None):
    """(text, details) of a check's result message: the outcome's plain
    headline, then the summary the command line prints, the DRC classes'
    lines and ``extra``. An outcome without a headline (a failed check) puts
    its summary first."""
    parts = []
    head = getattr(out, "headline", None)
    if not head:
        head, summary = out.summary, ""
    else:
        summary = out.summary
    if summary:
        parts.append(summary)
    classes = drc_classes_text(out) if hasattr(out, "alone") else ""
    if classes:
        parts.append(classes)
    if extra:
        parts.append(extra)
    return head, "\n\n".join(parts)


def start(ctx, cmd, cells, options, title=None, rdb_index=None, after=None):
    """Prepare and start one check in ``ctx``'s view; the browser opens when
    it ends. Returns the Run, or None when the user kept a running job."""
    title = title or TITLES[cmd]
    if not _busy(ctx.view, title):
        return None
    # Every feature's prepare() returns a Task, a failed one when the export
    # fails or is refused; the outcome then says why.
    task = prepare(ctx, cmd, cells, options)
    run = Run(title, task, ctx.view, lambda r: show_outcome(ctx, r, rdb_index, after))
    return run.start()


# -- the entries ---------------------------------------------------------------------

def _drc_defaults(cfg, data):
    from .drcjob import drc_styles
    styles = drc_styles(data) or [cfg.drc_style]
    cur = _state().drc()
    style = cur.get("style") if cur.get("style") in styles else cfg.drc_style
    mode = cur.get("mode") if cur.get("mode") in ("hierarchical", "flat") else cfg.drc_mode
    return styles, {"style": style, "mode": mode, "area": cur.get("area") or "cell"}


def _drc_box(ctx, area):
    if area == "visible":
        return _cell_box(ctx, ctx.view.box())
    if area == "selection":
        b = ctx.view.selection_bbox()
        if b.empty():
            raise UserError("Nothing is selected: select shapes or instances for an area check, or choose "
                            "another area.")
        return _cell_box(ctx, b)
    return None


def on_drc():
    mw = main_window()
    view = mw.current_view() if mw else None
    if view is not None and not _busy(view, TITLES["drc"]):
        return
    ctx = context()
    styles, cur = _drc_defaults(ctx.cfg, ctx.data)
    if has_qt():
        opts = ask_drc_options(styles, cur, ctx.pdk)
        if opts is None:
            return
        try:
            _state().set_drc(opts["style"], opts["mode"], opts["area"])
        except OSError:
            pass
    else:
        opts = cur
    start(ctx, "drc", [ctx.cell], {"style": opts["style"], "mode": opts["mode"],
                                   "box": _drc_box(ctx, opts["area"]), "file": ctx.file})


def on_drc_visible():
    ctx = context()
    _, cur = _drc_defaults(ctx.cfg, ctx.data)
    start(ctx, "drc", [ctx.cell], {"style": cur["style"], "mode": cur["mode"],
                                   "box": _drc_box(ctx, "visible"), "file": ctx.file},
          title="Magic DRC of the visible area")


def _free_name(path):
    """``path``, or ``<stem>-2<ext>``, ``-3``, ... the first that does not exist."""
    if not os.path.lexists(path):
        return path
    stem, ext = path[:-len(".spice")], ".spice"
    if not path.endswith(ext):
        stem, ext = os.path.splitext(path)
    n = 2
    while os.path.lexists("%s-%d%s" % (stem, n, ext)):
        n += 1
    return "%s-%d%s" % (stem, n, ext)


def save_netlist_as(ctx, out, caps, start, done=None):
    """A non-modal save dialog for the netlist (objectName
    "kmp_netlist_save"), opened at ``start``. Writes the file chosen there,
    with the plugin's header; ``done()`` runs when it closes."""
    from . import lvsjob
    pya = _pya()
    dlg = pya.QFileDialog(main_window())
    dlg.objectName = "kmp_netlist_save"
    dlg.windowTitle = "Save Magic's netlist of %s" % ctx.cell.name
    dlg.acceptMode = pya.QFileDialog.AcceptSave
    dlg.setNameFilter("SPICE (*.spice *.sp);;All files (*)")
    dlg.setDirectory(os.path.dirname(start))
    dlg.selectFile(os.path.basename(start))
    dlg.windowModality = pya.Qt.NonModal
    state = {"saved": None}

    def chosen(path):
        if not path:
            return
        header = lvsjob.netlist_header(ctx.cell.name, ctx.pdk, ctx.file or None, caps)
        try:
            # The user chose the file, and Qt asked before replacing one: as -o.
            lvsjob.save_netlist(out.files["netlist"], path, header, overwrite=True)
            state["saved"] = path
            message("info", "Extract", "Netlist: %s" % path)
        except OSError as e:
            message("critical", "Extract", "Cannot write %s: %s" % (path, e))

    def finished(*_):
        if done is not None:
            done(state["saved"])

    dlg.fileSelected = chosen
    dlg.finished = finished
    dlg.show()
    _windows.append(dlg)
    return dlg


def on_extract():
    mw = main_window()
    view = mw.current_view() if mw else None
    if view is not None and not _busy(view, TITLES["extract"]):
        return
    ctx = context()
    opts = ask_extract_options(ctx.cell.name, ctx.pdk) if has_qt() else {"caps": False}
    if opts is None:
        return
    caps = bool(opts["caps"])
    start(ctx, "extract", [ctx.cell], {"cmd": "extract", "caps": caps, "file": ctx.file},
          after=extract_after(ctx, caps))


def extract_after(ctx, caps):
    """What Extract does with its outcome: write the netlist to
    ``lvsjob.default_netlist_path`` (<cell>.magic.spice beside the layout)
    through ``lvsjob.save_netlist``, which refuses a file the plugin did not
    write; on a refusal, or for a layout never saved, a save dialog. Shows
    the netlist. Returns the line for the message."""

    def after(out):
        from . import lvsjob
        netlist = out.files.get("netlist")
        if out.status == 2 or not netlist:
            return None
        text = _read(netlist)
        if ctx.file:
            target = lvsjob.default_netlist_path(ctx.file, ctx.cell.name, caps)
            header = lvsjob.netlist_header(ctx.cell.name, ctx.pdk, ctx.file, caps)
            try:
                lvsjob.save_netlist(netlist, target, header)
            except lvsjob.NetlistRefused as e:
                refused = str(e)
            except OSError as e:
                refused = "cannot write %s: %s" % (target, e)
            else:
                lvsjob.name_netlist(out, target)
                show_text("Magic's netlist of %s: %s" % (ctx.cell.name, target), text, name="kmp_netlist")
                return "Netlist: %s" % target
            start_at = _free_name(target)
            note = "Not written: %s." % refused
            ask = " Choose another file in the dialog, or Cancel; the plugin never replaces a file it did not write."
        else:
            start_at = os.path.join(os.getcwd(), "%s.magic.%s" % (ctx.cell.name, "pex.spice" if caps else "spice"))
            note = "Not written: the layout has no file, so the netlist has no place beside it."
            ask = " Choose a file in the dialog."
        # The summary names no file: the netlist was not written.
        lvsjob.unname_netlist(out)
        show_text("Magic's netlist of %s (not saved)" % ctx.cell.name, text, name="kmp_netlist")
        if not has_qt():
            return note
        # The dialog reads the job directory's netlist: release it when the dialog closes.
        out.kmp_hold = True
        save_netlist_as(ctx, out, caps, start_at, done=lambda _saved: release(out))
        return note + ask

    return after


def on_lvs():
    mw = main_window()
    view = mw.current_view() if mw else None
    if view is not None and not _busy(view, TITLES["lvs"]):
        return
    ctx = context(needs_netgen=True)
    st = _state()
    cur = st.lvs(ctx.file, ctx.cell.name)
    if has_qt():
        opts = ask_lvs_options(ctx.cell.name, cur, ctx.pdk)
        if opts is None:
            return
        try:
            st.set_lvs(ctx.file, ctx.cell.name, opts["schematic"], opts["subckt"])
        except OSError:
            pass
    elif cur:
        opts = cur
    else:
        raise UserError("LVS needs a schematic; choose it in the GUI first.")

    start(ctx, "lvs", [ctx.cell], {"cmd": "lvs", "schematic": opts["schematic"],
                                   "schematic_cell": opts["subckt"], "file": ctx.file}, after=lvs_after)


def lvs_after(out):
    """What LVS does with its outcome: netgen's report in a window, scrolled
    to its end, where netgen's final result is. The window's title names the
    file, which goes with the job directory (jobs.release) unless
    KMP_JOB_KEEP=1; the message gets no line, so it names no cache path."""
    report = out.files.get("report")
    if report:
        show_text("netgen's report: %s" % report, _read(report), name="kmp_lvs_report", at_end=True)
    return None


def on_layers():
    ctx = context()
    opts = {"file": ctx.file}
    opts["command"] = command_text("layers", ctx.file, ctx.cell.name, ctx.pdk, opts)
    start(ctx, "layers", [ctx.cell], opts)


def on_ports():
    ctx = context(needs_magic=False)
    opts = {"file": ctx.file, "magic": False}
    opts["command"] = command_text("ports", ctx.file, ctx.cell.name, ctx.pdk, opts)
    start(ctx, "ports", [ctx.cell], opts)


def _gaps_pdk():
    """The current layout's PDK, else the one KMP_PDK names."""
    mw = main_window()
    view = mw.current_view() if mw else None
    if view is not None:
        return context(needs_magic=False).pdk
    from .config import Config
    return Config.load().pdk


def on_gaps():
    pdk = _gaps_pdk()
    path = gaps_page(pdk)
    if path is None:
        raise UserError("The rule differences of %s (docs/gaps/%s.md) are not installed with this copy of "
                        "the plugin: looked in %s. They are in the plugin's repository under docs/gaps/."
                        % (pdk, pdk, os.path.join(ROOT_DIR, "docs", "gaps")))
    text = _read(path)
    if show_text("Rule differences between Magic and KLayout: %s (%s)" % (pdk, path), text,
                 name="kmp_gaps", markdown=True, size=(1100, 760)) is None:
        message("info", "Rule differences", path)


def on_settings():
    from .config import Config, ConfigError, config_file_path
    try:
        cfg = Config.load()
    except ConfigError as e:
        raise UserError("The plugin's configuration has an error: %s. Settings come from the environment "
                        "(KMP_...) and %s." % (e, config_file_path()))
    mw = main_window()
    view = mw.current_view() if mw else None
    if view is not None:
        try:
            cfg = cfg.for_pdk(context(needs_magic=False).pdk)
        except (UserError, Cancelled):
            pass
    show_settings(cfg)


def show_settings(cfg):
    from .config import config_file_path
    pya = _pya()
    rows = settings_rows(cfg)
    ini = config_file_path()
    head = ("Settings for %s. A setting comes from the environment variable first, then from %s "
            "(%s), then from the default. Keys in [kmp] are the variable names in lower case without KMP_; "
            "the per-PDK keys go in [kmp:<pdk>]. The Magic menu reads them at each run; the PCell "
            "libraries read them when KLayout starts. state.json beside config.ini keeps the dialogs' "
            "last choices." % (cfg.pdk, ini, "present" if os.path.isfile(ini) else "not there yet"))
    problems = cfg.job_problems()
    if not has_qt():
        message("info", "Settings", head + "\n" + "\n".join("%s = %s (%s)" % (r[0], r[2], r[3]) for r in rows))
        return None
    _prune()
    dlg = pya.QDialog(main_window())
    dlg.objectName = "kmp_settings"
    dlg.windowTitle = "Magic: Settings"
    _resizable(dlg, (1150, 640))
    lay = pya.QVBoxLayout(dlg)
    label = pya.QLabel(head, dlg)
    label.wordWrap = True
    lay.addWidget(label)
    table = pya.QTableWidget(len(rows), 4, dlg)
    table.objectName = "settings"
    table.setHorizontalHeaderLabels(["Setting", "Where to set it", "Value", "Source"])
    for i, row in enumerate(rows):
        for j, text in enumerate(row):
            item = pya.QTableWidgetItem(text)
            item.setToolTip(text)
            table.setItem(i, j, item)
    table.resizeColumnsToContents()
    for col, most in ((1, 360), (2, 420)):
        if table.columnWidth(col) > most:
            table.setColumnWidth(col, most)
    try:
        table.horizontalHeader().stretchLastSection = True
    except Exception:
        pass
    try:
        table.editTriggers = pya.QAbstractItemView.NoEditTriggers
    except Exception:
        pass
    lay.addWidget(table)
    if problems:
        warn = pya.QLabel("Problems: " + "; ".join(problems), dlg)
        warn.wordWrap = True
        lay.addWidget(warn)
    bb = pya.QDialogButtonBox(dlg)
    close = bb.addButton(pya.QDialogButtonBox.Close)
    close.objectName = "close"
    bb.rejected = lambda: dlg.hide()
    lay.addWidget(bb)
    dlg.windowModality = pya.Qt.NonModal
    dlg.show()
    _windows.append(dlg)
    return dlg


# -- Rerun (design-0.6.md 2.7) --------------------------------------------------------

_recipe = None


def _find_cellview(view, file):
    """The cellview of ``view`` that shows ``file``, else the active one."""
    if file:
        for i in range(view.cellviews()):
            cv = view.cellview(i)
            if cv.is_valid() and cv.filename() and os.path.abspath(cv.filename()) == os.path.abspath(file):
                return cv
    return view.active_cellview()


def rerun(params):
    """Run the check an RDB's generator describes again, on the current
    view's layout, and replace that database (``params["rdb_index"]``)."""
    idx = params.get("rdb_index")
    idx = int(idx) if idx not in (None, "") else None
    cmd, cells, opts, pdk = options_from_params(params)
    mw = main_window()
    view = mw.current_view() if mw else None
    if view is None:
        raise UserError("Rerun needs the layout's view.")
    cv = _find_cellview(view, opts.get("file"))
    ctx = context(needs_magic=cmd != "ports" or opts.get("magic"), needs_netgen=cmd == "lvs",
                  view=view, cv=cv, pdk=pdk)
    found = []
    for name in cells:
        c = ctx.layout.cell(name)
        if c is None:
            raise UserError("Rerun: the layout has no cell %s." % name)
        found.append(c)
    if cmd in ("layers", "ports"):
        opts["command"] = command_text(cmd, ctx.file, found[0].name, ctx.pdk, opts)
    return start(ctx, cmd, found, opts, title=TITLES[cmd] + " (rerun)", rdb_index=idx)


def register_recipe():
    """Register the Recipe ``klayout_magic_pcells`` once. Returns True when
    it is registered."""
    global _recipe
    if _recipe is not None:
        return True
    pya = _pya()
    if pya is None or not hasattr(pya, "Recipe"):
        return False

    class _Rerun(pya.Executable):
        def __init__(self, params):
            self.params = dict(params)

        def execute(self):
            _guarded("Rerun", lambda: rerun(self.params))()
            return None

    class MagicRecipe(pya.Recipe):
        def __init__(self):
            super().__init__(RECIPE, "Re-run a klayout-magic-pcells check")

        def executable(self, params):
            return _Rerun(params)

    _recipe = MagicRecipe()
    return True
