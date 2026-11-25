"""The Magic backend: one persistent ``magic -dnull`` child on pipes.

``MagicServer`` owns the child process and speaks the protocol in
protocol.py. ``Generator`` puts an in-memory memo and the disk cache in front
of it. Nothing in this module imports KLayout.
"""

import atexit
import collections
import hashlib
import json
import logging
import os
import queue
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time

from . import protocol
from .cache import CacheError
from .config import TCL_DIR

log = logging.getLogger("klayout_magic_pcells")

SERVER_TCL = os.path.join(TCL_DIR, "kmp_server.tcl")


class BackendError(Exception):
    """Magic could not answer a request."""


class _Transient(Exception):
    """Timeout, EOF or framing error: restart Magic and retry once."""


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 16), b""):
            h.update(block)
    return h.hexdigest()


def parse_magic_version(banner):
    """'Version 8.3 revision 681.  Compiled ...' -> '8.3.681'."""
    m = re.search(r"Version\s+(\d+\.\d+)\s+revision\s+(\d+)", banner or "")
    return "%s.%s" % (m.group(1), m.group(2)) if m else ""


def read_open_pdks(pdk_path):
    """The open_pdks commit from $PDK_ROOT/<pdk>/SOURCES, or ''."""
    path = os.path.join(pdk_path, "SOURCES")
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2 and parts[0] == "open_pdks":
                    return parts[1]
    except OSError:
        pass
    return ""


def read_pdk_commit(pdk_path):
    """The commit the PDK was built from: open_pdks' from SOURCES (sky130A,
    gf180mcuD), else the first word of COMMIT (the IHP PDKs), else ''."""
    c = read_open_pdks(pdk_path)
    if c:
        return c
    try:
        with open(os.path.join(pdk_path, "COMMIT"), encoding="utf-8", errors="replace") as f:
            words = f.read().split()
            return words[0] if words else ""
    except OSError:
        return ""


def sha256_tree(root):
    """SHA-256 over every regular file under ``root`` (relative path and
    contents, in sorted order), or '' if ``root`` isn't a directory.

    Used on the directory that holds the PDK's tech file (libs.tech/magic):
    the IHP tech files include four more tech files, and the IHP fixed
    devices source layout scripts from there, none of which the proc text
    or the top tech file shows."""
    if not root or not os.path.isdir(root):
        return ""
    h = hashlib.sha256()
    for dirpath, dirnames, files in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d != "__pycache__")
        for fn in sorted(files):
            p = os.path.join(dirpath, fn)
            if not os.path.isfile(p):
                continue
            h.update(os.path.relpath(p, root).encode("utf-8") + b"\0")
            try:
                h.update(sha256_file(p).encode("ascii"))
            except OSError:
                h.update(b"unreadable")
            h.update(b"\n")
    return h.hexdigest()


def vendor_digest(lines, cache=None):
    """SHA-256 over the vendor cells that fixed devices copy.

    ``lines`` holds "<cell>\\t<.mag path>\\t<GDS file>" as the server's
    versions op resolves them through Magic's search path. Each .mag and
    each GDS file it names is hashed whole (sky130_fd_pr.gds, 10.5 MB, takes
    about 25 ms). Returns (digest, rows) where rows describe each cell."""
    cache = {} if cache is None else cache

    def fh(p):
        if not p:
            return "none"
        if p not in cache:
            try:
                cache[p] = sha256_file(p)
            except OSError:
                cache[p] = "missing"
        return cache[p]
    rows = []
    for line in sorted(l for l in (lines or "").splitlines() if l.strip()):
        parts = (line.split("\t") + ["", "", ""])[:3]
        cell, mag, gds = parts
        rows.append({"cell": cell, "mag": mag, "mag_sha256": fh(mag), "gds": gds,
                     "gds_sha256": fh(gds)})
    if not rows:
        return "", rows
    text = json.dumps(rows, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest(), rows


# What Magic's gencell_create raises after the generator's _draw failed: it
# prints the _draw error and then reads the instance name _draw never set.
_DRAW_FAILED = 'can\'t read "instname": no such variable'
# Lines of a Tcl error trace or return-options dump that gencell_create
# prints with the error; the message itself is kept.
_TRACE_LINE = re.compile(r'^(while executing|invoked from within|\(procedure |\(file |\("|"|.*\} -errorline \d+$)')


def failure_text(device, error, log_text):
    """The reason a request failed, Magic's cause first.

    Magic's own messages come from ``log_text`` (what the generators printed
    on stderr), without Tcl trace lines, and with a return-options dump
    ("-code 1 -level 0 -errorstack {...} -errorinfo {couldn't read file
    ...") cut down to its message. When ``error`` is only gencell_create
    failing after a _draw error, the _draw error comes first."""
    lines = []
    for ln in (log_text or "").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        if ln.startswith("-code ") or " -errorstack " in ln:
            m = re.search(r"-errorinfo \{(.*)$", ln)
            if not m:
                continue
            ln = m.group(1).strip()
        elif _TRACE_LINE.match(ln):
            continue
        if ln not in lines:
            lines.append(ln)
    err = (error or "").strip() or "generation failed"
    if err.startswith(_DRAW_FAILED) and lines:
        return "%s: %s (then gencell_create: %s)" % (device, " | ".join(lines), err)
    return "%s: %s" % (device, err) + (("\n" + "\n".join(lines)) if lines else "")


def defaults_digest(defaults):
    """SHA-256 over the canonical JSON of {device: [[key, value], ...]}."""
    items = [[dev, [[str(k), str(v)] for k, v in defaults[dev]]] for dev in sorted(defaults)]
    text = json.dumps(items, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# Lines every Magic prints while it starts, whatever its rcfile did.
_STARTUP_NOISE = re.compile(r"^(Switching to \w+ tool\.|Processing system \.magicrc file|"
                            r"Magic \d+\.\d+ revision|Starting magic under Tcl|Using the terminal|"
                            r"Root cell box:|Using NULL graphics)")


class Versions:
    """What the running Magic and PDK are; feeds the cache key and stamps."""

    FIELDS = ("magic", "magic_banner", "tech", "tech_name", "tech_file", "tcl", "pdk",
              "namespace", "open_pdks", "pdk_commit", "code", "techfile", "techdir", "vendor",
              "defaults_digest", "protocol")

    def __init__(self, **kw):
        for f in self.FIELDS:
            setattr(self, f, kw.get(f, ""))
        self.defaults = kw.get("defaults", {})
        self.boxpaint = kw.get("boxpaint", [])
        self.vendor_files = kw.get("vendor_files", [])

    def as_dict(self):
        return {f: getattr(self, f) for f in self.FIELDS}

    def __repr__(self):
        return "Versions(magic=%s, tech=%s, open_pdks=%s)" % (self.magic, self.tech, self.open_pdks)


class GenReply:
    def __init__(self, cell, checked, log_text, us, restart=False, kv=None):
        self.cell = cell
        self.checked = checked
        self.log = log_text
        self.us = us
        self.restart = restart
        self.kv = kv or {}


class CheckReply:
    def __init__(self, checked, log_text, kv=None):
        self.checked = checked
        self.log = log_text
        self.kv = kv or {}


def _make_pdeathsig():
    """A preexec_fn that asks Linux to kill the child when its parent dies.

    The libc function is resolved here, in the parent, so the child only makes
    one C call between fork and exec. PR_SET_PDEATHSIG fires when the thread
    that forked exits; KLayout calls produce on its main thread.
    """
    if not sys.platform.startswith("linux"):
        return None
    try:
        import ctypes
        prctl = ctypes.CDLL("libc.so.6", use_errno=True).prctl
    except Exception:
        return None
    sig = int(signal.SIGKILL)

    def _pre():
        prctl(1, sig, 0, 0, 0)  # PR_SET_PDEATHSIG = 1
    return _pre


def _private_run_dir(cfg):
    """A fresh directory for one Magic process: under <cache>/run when the
    disk cache is on and writable, else in the system temp directory."""
    if cfg.cache_enabled:
        base = os.path.join(cfg.cache_dir, "run")
        try:
            os.makedirs(base, exist_ok=True)
            return tempfile.mkdtemp(prefix="kmp-run-", dir=base)
        except OSError:
            pass
    return tempfile.mkdtemp(prefix="kmp-run-")


class MagicServer:
    """One ``magic -dnull -noconsole`` child serving requests over pipes.

    Without ``run_dir`` the server makes a private working directory for
    Magic and deletes it in close(), so two sessions sharing a cache never
    share one, and the CLI leaves nothing behind.
    """

    def __init__(self, cfg, run_dir=None, server_tcl=SERVER_TCL, vendor_cells=None):
        self.cfg = cfg
        # Cells whose .mag and vendor GDS the versions op resolves and hashes
        # (the fixed devices' vendor cells). None: read them from the manifest.
        self.vendor_cells = vendor_cells
        self._own_run_dir = run_dir is None
        self.run_dir = run_dir or _private_run_dir(cfg)
        self.server_tcl = server_tcl
        self.versions = None
        self.stats = {"spawns": 0, "restarts": 0, "requests": 0, "generate": 0, "check": 0,
                      "dialog": 0}
        self._lock = threading.RLock()
        self._proc = None
        self._lines = None
        self._next_id = 0
        self._needs_restart = False
        self._threads = []
        self._stderr = collections.deque(maxlen=40)  # (sequence number, line)
        self._stderr_seq = 0
        self._trace = None
        if cfg.log:
            try:
                self._trace = open(cfg.log, "a", encoding="utf-8")
            except OSError as e:
                log.warning("cannot open KMP_LOG %s: %s", cfg.log, e)

    # -- process management -------------------------------------------------

    def _trace_line(self, direction, text):
        if self._trace:
            try:
                self._trace.write("%.3f %s %s\n" % (time.time(), direction, text.rstrip("\n")))
                self._trace.flush()
            except OSError:
                pass

    def _env(self):
        env = dict(os.environ)
        env["PDK_ROOT"] = self.cfg.pdk_root
        # The rcfiles read PDK_ROOT; PDK is set so that nothing the rcfile
        # sources picks up the image's IHP default from the environment.
        env["PDK"] = self.cfg.pdk
        # kmp_server.tcl takes the generator namespace from the PDKNAMESPACE
        # that the PDK's Tcl sets; a KMP_NS meant for another tool must not
        # override it for every PDK's server.
        env.pop("KMP_NS", None)
        env.pop("DISPLAY", None)
        return env

    def stderr_mark(self):
        """A position in Magic's stderr, for stderr_since()."""
        return self._stderr_seq

    def stderr_since(self, mark, wait=0.05):
        """Lines Magic wrote on stderr after ``mark`` (most recent 40 kept).

        Magic's C code writes its messages there directly, not through Tcl's
        puts; ``wait`` gives the reader thread a moment to catch up.
        """
        if wait:
            time.sleep(wait)
        return [t for n, t in list(self._stderr) if n > mark and t.strip()]

    def _said(self, mark=0):
        lines = self.stderr_since(mark, wait=0)
        return ("; Magic said: " + " | ".join(lines[-4:])) if lines else ""

    def launch(self):
        """Start the Magic process without waiting for it. register() calls
        this for every PDK first, so the Magics load their PDKs in parallel;
        start() then waits. The process is spawned on the calling thread,
        which matters: PR_SET_PDEATHSIG kills the child when that thread
        exits."""
        with self._lock:
            if self._proc is None:
                try:
                    self._launch()
                except BackendError:
                    raise
            return self._proc is not None

    def _spawn(self):
        self._launch()
        self._await_ready()

    def _launch(self):
        if os.path.isdir(self.run_dir):
            shutil.rmtree(self.run_dir, ignore_errors=True)
        os.makedirs(self.run_dir, exist_ok=True)
        cmd = [self.cfg.magic, "-dnull", "-noconsole", "-rcfile", self.cfg.magicrc]
        try:
            proc = subprocess.Popen(
                cmd, cwd=self.run_dir, env=self._env(), stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0,
                preexec_fn=_make_pdeathsig(), close_fds=True)
        except OSError as e:
            raise BackendError("cannot start Magic (%s): %s" % (self.cfg.magic, e))
        lines = queue.Queue()

        # The pipes may be closed under these threads by _kill(); a reader
        # that finds its pipe closed just stops.
        def read_stdout(stream, q):
            try:
                for raw in iter(stream.readline, b""):
                    q.put(raw.decode("utf-8", errors="replace"))
            except (OSError, ValueError):
                pass
            finally:
                q.put(None)

        def read_stderr(stream):
            try:
                for raw in iter(stream.readline, b""):
                    text = raw.decode("utf-8", errors="replace").rstrip("\n")
                    self._stderr_seq += 1
                    self._stderr.append((self._stderr_seq, text))
                    log.debug("magic stderr: %s", text)
                    self._trace_line("ERR", text)
            except (OSError, ValueError):
                pass

        self._stderr.clear()
        self._threads = [
            threading.Thread(target=read_stdout, args=(proc.stdout, lines), daemon=True,
                             name="kmp-magic-stdout"),
            threading.Thread(target=read_stderr, args=(proc.stderr,), daemon=True,
                             name="kmp-magic-stderr")]
        for t in self._threads:
            t.start()
        self._proc, self._lines = proc, lines
        self._parser = protocol.ReplyParser()
        self.stats["spawns"] += 1
        self._launched_at = time.monotonic()
        self._ready = False

    def _await_ready(self):
        if self._ready:
            return
        budget = max(self.cfg.timeout, 10.0)
        deadline = time.monotonic() + budget
        printed = []
        try:
            self._send("source %s\n" % protocol.tcl_word(self.server_tcl))
            while True:
                line = self._get_line(deadline, budget, waiting_for="Magic to load kmp_server.tcl")
                kind, val = self._parser.feed(line)
                if kind == "ready":
                    if val != str(protocol.PROTOCOL):
                        self._kill()
                        raise BackendError("kmp_server.tcl speaks protocol %s, expected %d"
                                           % (val, protocol.PROTOCOL))
                    break
                if kind == "other":
                    log.debug("magic: %s", line.rstrip())
                    if line.strip():
                        printed.append(line.strip())
        except _Transient as e:
            # Say why: Magic's exit status and its last stderr lines (for
            # example "Could not find file .../sky130A.tech"), or what the
            # executable printed if it never answered.
            text = str(e)
            if text.startswith("cannot write"):
                text = self._exit_text() or text
            elif text.startswith("timed out") and printed:
                text += " (it printed %r; is %s Magic?)" % (printed[-1][:80], self.cfg.magic)
            raise _Transient(text + self._said())
        self._needs_restart = False
        self._ready = True
        self._startup_stdout = printed

    def startup_messages(self, n=6):
        """What Magic printed while it read its rcfile (stdout and stderr,
        the last ``n`` lines), for errors about what the rcfile loaded."""
        lines = list(getattr(self, "_startup_stdout", []) or [])
        lines += self.stderr_since(0, wait=0.05)
        out = []
        for ln in lines:
            ln = ln.strip()
            if (ln and ln not in out and not ln.startswith("KMP_")
                    and not _STARTUP_NOISE.match(ln)):
                out.append(ln)
        return out[-n:]

    def _exit_text(self):
        """'Magic exited (status N)' once the child has exited, else ''."""
        proc = self._proc
        if proc is None:
            return ""
        try:
            code = proc.wait(timeout=2)
        except Exception:
            return ""
        # let the stderr reader drain what the process wrote before it died
        for t in self._threads[1:]:
            t.join(timeout=1)
        return "Magic exited (status %s)" % code

    def _send(self, text):
        self._trace_line(">>", text)
        try:
            self._proc.stdin.write(text.encode("utf-8"))
            self._proc.stdin.flush()
        except (OSError, ValueError) as e:
            raise _Transient("cannot write to Magic: %s" % e)

    def _get_line(self, deadline, budget, waiting_for="Magic"):
        remaining = deadline - time.monotonic()
        try:
            if remaining <= 0:
                raise queue.Empty
            line = self._lines.get(timeout=remaining)
        except queue.Empty:
            raise _Transient("timed out after %g s waiting for %s" % (budget, waiting_for))
        if line is None:
            raise _Transient(self._exit_text() or "Magic closed its output")
        self._trace_line("<<", line)
        return line

    def _kill(self):
        proc, self._proc = self._proc, None
        if proc is None:
            return
        try:
            proc.kill()
        except OSError:
            pass
        try:
            proc.wait(timeout=5)
        except Exception:
            pass
        # The readers see EOF once the process is gone; wait for them before
        # closing the pipes, so that no thread reads a closed file.
        for t in self._threads:
            t.join(timeout=1)
        for s in (proc.stdin, proc.stdout, proc.stderr):
            try:
                s.close()
            except Exception:
                pass

    @property
    def pid(self):
        return self._proc.pid if self._proc else None

    def alive(self):
        return self._proc is not None and self._proc.poll() is None

    def start(self):
        """Start Magic (or wait for a launched one) and read its versions.
        Returns a ``Versions``."""
        with self._lock:
            try:
                if self._proc is not None and not self._ready:
                    self._await_ready()
                elif not self.alive():
                    self._spawn()
            except _Transient as e:
                self._kill()
                raise BackendError("Magic did not start: %s" % e)
            if self.versions is None:
                self.versions = self._read_versions()
            return self.versions

    def close(self):
        """Ask Magic to quit, close its stdin, kill it after 2 s, and delete
        the private run directory."""
        with self._lock:
            proc = self._proc
            if proc is not None:
                try:
                    self._send("quit -noprompt\n")
                    proc.stdin.close()
                except Exception:
                    pass
                try:
                    proc.wait(timeout=2)
                except Exception:
                    pass
                self._kill()
            if self._own_run_dir:
                shutil.rmtree(self.run_dir, ignore_errors=True)

    # -- requests -----------------------------------------------------------

    def _roundtrip(self, obj):
        self._next_id += 1
        rid = self._next_id
        self._send(protocol.encode_request(rid, obj))
        deadline = time.monotonic() + self.cfg.timeout
        while True:
            line = self._get_line(deadline, self.cfg.timeout)
            try:
                kind, val = self._parser.feed(line)
            except protocol.ProtocolError as e:
                raise _Transient(str(e))
            if kind == "reply":
                if val.id == rid:
                    return val
                log.debug("dropping stale reply %d", val.id)
            elif kind == "other":
                log.debug("magic: %s", line.rstrip())

    def request(self, obj):
        """Send one request; restart Magic and retry once on a transient error."""
        with self._lock:
            self.stats["requests"] += 1
            last = None
            for attempt in (1, 2):
                mark = self.stderr_mark()
                try:
                    if not self.alive() or self._needs_restart:
                        if self._proc is not None or self.stats["spawns"]:
                            self.stats["restarts"] += 1
                        self._kill()
                        self._spawn()
                        mark = self.stderr_mark()
                    return self._roundtrip(obj)
                except _Transient as e:
                    text = str(e)
                    if "Magic said:" not in text:
                        text += self._said(mark)
                    last = text
                    log.warning("Magic request failed (%s); restarting Magic", text)
                    self._kill()
            raise BackendError("Magic failed twice: %s" % last)

    def _vendor_cells(self):
        if self.vendor_cells is not None:
            return list(self.vendor_cells)
        try:
            from .manifest import Manifest
            return Manifest.load(self.cfg.manifest).vendor_cells()
        except Exception as e:
            log.debug("vendor cells: %s", e)
            return []

    def _read_versions(self):
        procs_out = os.path.join(self.run_dir, "procs.txt")
        defaults_out = os.path.join(self.run_dir, "defaults.json")
        rep = self.request({"op": "versions", "procs_out": procs_out, "defaults_out": defaults_out,
                            "vendor_cells": self._vendor_cells()})
        if not rep.ok:
            raise BackendError("versions request failed: %s" % rep.error)
        kv = rep.kv
        try:
            with open(defaults_out, encoding="utf-8") as f:
                defaults = json.load(f)
            code = sha256_file(procs_out)
        except (OSError, ValueError) as e:
            raise BackendError("cannot read Magic's version dump: %s" % e)
        for p in (procs_out, defaults_out):  # about 300 KB, needed only for the digest
            try:
                os.remove(p)
            except OSError:
                pass
        tech_file = kv.get("tech_file", "")
        techfile_digest = sha256_file(tech_file) if tech_file and os.path.isfile(tech_file) else ""
        vdig, vrows = vendor_digest(kv.get("vendor", ""))
        return Versions(
            magic=parse_magic_version(kv.get("magic_banner", "")),
            magic_banner=kv.get("magic_banner", ""),
            tech=kv.get("tech", ""), tech_name=kv.get("tech_name", ""),
            tech_file=tech_file, tcl=kv.get("tcl", ""), pdk=self.cfg.pdk,
            namespace=kv.get("ns", ""),
            open_pdks=read_open_pdks(self.cfg.pdk_path),
            pdk_commit=read_pdk_commit(self.cfg.pdk_path), code=code,
            techfile=techfile_digest,
            techdir=sha256_tree(os.path.dirname(tech_file)) if tech_file else "",
            vendor=vdig, vendor_files=vrows,
            defaults_digest=defaults_digest(defaults),
            defaults=defaults, boxpaint=kv.get("boxpaint", "").split(),
            protocol=kv.get("protocol", ""))

    def ping(self):
        rep = self.request({"op": "ping"})
        return rep.ok

    def generate(self, device, params, form, out_path, apply=False):
        """Generate one device into ``out_path``: what the dialog's Create
        makes of the form ``params``, or with ``apply`` what its Apply makes
        on an existing instance. Raises BackendError."""
        self.stats["generate"] += 1
        req = {"op": "generate", "device": device, "params": dict(params), "form": form,
               "out": out_path}
        if apply:
            req["apply"] = "1"
        rep = self.request(req)
        if not rep.ok:
            raise BackendError(failure_text(device, rep.error, rep.log))
        restart = rep.kv.get("restart") == "1"
        if restart:
            log.warning("Magic kept cells after a request (%s); restarting it",
                        rep.kv.get("leftover", ""))
            self._needs_restart = True
        if rep.kv.get("kept"):
            log.debug("Magic keeps the cells %s below %s for later requests",
                      rep.kv["kept"], device)
        if rep.kv.get("restored"):
            log.debug("after %s, the server put back: %s", device, rep.kv["restored"])
        try:
            us = int(rep.kv.get("us", "0"))
        except ValueError:
            us = 0
        return GenReply(rep.kv.get("cell", ""), rep.params, rep.log, us, restart, kv=rep.kv)

    def check(self, device, params, form=None):
        """Run ``_check`` once on the merged defaults; nothing is drawn. For
        a box-paint generator (form "box"), report the box Magic would use
        and what the generator prints."""
        self.stats["check"] += 1
        req = {"op": "check", "device": device, "params": dict(params)}
        if form:
            req["form"] = form
        rep = self.request(req)
        if not rep.ok:
            raise BackendError("%s: %s" % (device, rep.error.strip() or "check failed"))
        return CheckReply(rep.params, rep.log, kv=rep.kv)

    def dialog(self, spec, form, edits, want_chains=False, want_apply_name=False):
        """Type ``edits`` ([(name, text)]) into Magic's dialog form ``form``
        ({name: text}), each widget's binding run as Return or a click runs
        it. With ``want_apply_name``, also the cell name the dialog's Apply
        compares with the instance's. Raises BackendError."""
        self.stats["dialog"] = self.stats.get("dialog", 0) + 1
        rep = self.request(dialog_request(spec, form, edits, want_chains, want_apply_name))
        if not rep.ok:
            raise BackendError(failure_text(spec.name, rep.error, rep.log))
        return DialogReply(dict(rep.params), _json_kv(rep.kv, "numbers", {}),
                           _json_kv(rep.kv, "steps", []), _json_kv(rep.kv, "chains", {}), rep.log,
                           rep.kv.get("apply_name", ""))


class DialogReply:
    def __init__(self, form, numbers, steps, chains, log_text, apply_name=""):
        self.form = form
        self.numbers = numbers
        self.steps = steps
        self.chains = chains
        self.log = log_text
        self.apply_name = apply_name


def _json_kv(kv, name, empty):
    text = kv.get(name, "")
    if not text:
        return empty
    try:
        return json.loads(text)
    except ValueError as e:
        raise BackendError("bad %s in Magic's dialog reply: %s" % (name, e))


def dialog_request(spec, form, edits, want_chains=False, want_apply_name=False):
    """The server request that types ``edits`` into ``form``. Everything the
    op's result depends on besides the server's code and the PDK is in it,
    so it is also what the dialog cache key covers."""
    widgets = [n for _k, n in spec.raw.get("dialog_widgets") or []]
    deps = [{"callback": d["callback"], "params": list(d["params"]), "after": int(d.get("after", 0))}
            for d in spec.raw.get("dialog_dependencies") or []]
    return {"op": "dialog", "device": spec.name, "form": dict(form),
            "edits": [[n, t] for n, t in edits], "order": widgets, "deps": deps,
            "want_chains": 1 if want_chains else 0,
            "want_apply_name": 1 if want_apply_name else 0}


class MagicOneShot:
    """The same interface with one Magic process per request (debugging)."""

    def __init__(self, cfg, run_dir=None, vendor_cells=None):
        self.cfg = cfg
        self.run_dir = run_dir
        self.vendor_cells = vendor_cells
        self.versions = None
        self.stats = {"spawns": 0, "restarts": 0, "requests": 0, "generate": 0, "check": 0,
                      "dialog": 0}

    def _once(self, fn):
        s = MagicServer(self.cfg, run_dir=self.run_dir, vendor_cells=self.vendor_cells)
        try:
            s.start()
            if self.versions is None:
                self.versions = s.versions
            return fn(s)
        finally:
            s.close()
            for k in self.stats:
                self.stats[k] += s.stats.get(k, 0)

    def start(self):
        if self.versions is None:
            self._once(lambda s: None)
        return self.versions

    def generate(self, device, params, form, out_path, apply=False):
        return self._once(lambda s: s.generate(device, params, form, out_path, apply))

    def check(self, device, params, form=None):
        return self._once(lambda s: s.check(device, params, form))

    def dialog(self, spec, form, edits, want_chains=False, want_apply_name=False):
        return self._once(lambda s: s.dialog(spec, form, edits, want_chains, want_apply_name))

    def launch(self):
        return False

    def ping(self):
        return self._once(lambda s: s.ping())

    def close(self):
        pass

    def alive(self):
        return False

    pid = None


# A request whose cell is made by the dialog's Apply on an existing instance
# carries this key with "1" (see dialog.py); the server gets it as a flag.
APPLY_KEY = "kmp_apply"


def split_apply(request):
    """(the parameters for Magic, whether the request is an Apply)."""
    if APPLY_KEY not in request:
        return dict(request), False
    if request[APPLY_KEY] != "1":
        raise BackendError("%s=%r in a request: only \"1\" is allowed" % (APPLY_KEY, request[APPLY_KEY]))
    return {k: v for k, v in request.items() if k != APPLY_KEY}, True


class Result:
    """A generated device: Magic's GDS on disk plus what Magic said about it."""

    def __init__(self, key, gds_path, sidecar, source):
        self.key = key
        self.gds_path = gds_path
        self.sidecar = sidecar
        self.source = source  # "memo", "disk" or "magic"

    @property
    def checked(self):
        return self.sidecar.get("checked", {})

    @property
    def messages(self):
        return self.sidecar.get("messages", "")

    @property
    def magic_cell(self):
        return self.sidecar.get("magic_cell", "")

    @property
    def stamp(self):
        return self.sidecar.get("stamp", "")

    @property
    def opened(self):
        """What Magic's dialog shows when it reopens on the instance this
        made (the "Edit device" dialog), {name: text}; {} if unknown."""
        return self.sidecar.get("opened") or {}


class Generator:
    """memo, then the disk cache, then Magic."""

    def __init__(self, server, cache, versions):
        from .stamp import make_stamp
        self.server = server
        self.cache = cache
        self.versions = versions
        self._make_stamp = make_stamp
        self._memo = {}
        self._dialog_memo = {}
        self._lock = threading.RLock()
        self.stats = {"memo": 0, "disk": 0, "magic": 0, "evicted": 0,
                      "dialog_memo": 0, "dialog_disk": 0, "dialog_magic": 0}
        # fresh: every get() asks Magic and replaces what the disk cache
        # held (audit --regen). replaced[key] is a copy of the replaced GDS.
        self.fresh = False
        self.replaced = {}

    def key(self, spec, request):
        return self.cache.key(spec.name, spec.form, request)

    def peek(self, spec, request):
        """The memo entry for this request, or None. Never calls Magic."""
        return self._memo.get(self.key(spec, request))

    def get(self, spec, request):
        key = self.key(spec, request)
        with self._lock:
            hit = self._memo.get(key)
            if hit is not None and not os.path.isfile(hit.gds_path):
                # Deleted under this session (cache clear, prune, or the
                # cache directory removed by hand): generate it again.
                del self._memo[key]
                hit = None
            if hit is not None and (not self.fresh or hit.source == "magic"):
                self.stats["memo"] += 1
                return Result(hit.key, hit.gds_path, hit.sidecar, "memo")
            entry = self.cache.lookup(key, spec.name)
            if entry is not None and not self.fresh:
                self.stats["disk"] += 1
                res = Result(key, entry[0], entry[1], "disk")
                self._memo[key] = res
                return res
            if entry is not None and key not in self.replaced:
                old = self.cache.tmp_path(key) + ".old"
                try:
                    shutil.copyfile(entry[0], old)
                    self.replaced[key] = old
                except OSError:
                    pass
            tmp = self.cache.tmp_path(key)
            mark = self.server.stderr_mark() if hasattr(self.server, "stderr_mark") else None
            params, apply = split_apply(request)
            try:
                if apply:
                    rep = self.server.generate(spec.name, params, spec.form, tmp, apply=True)
                else:
                    rep = self.server.generate(spec.name, params, spec.form, tmp)
                stamp = self._make_stamp(self.versions, key)
                sidecar = {
                    "key": key, "device": spec.name, "form": spec.form,
                    "request": dict(request), "checked": rep.checked,
                    "messages": rep.log, "magic_cell": rep.cell,
                    "versions": self.versions.as_dict(), "stamp": stamp,
                    "gen_us": rep.us,
                    "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }
                if "opened" in rep.kv:
                    sidecar.update({"opened": _json_kv(rep.kv, "opened", {}),
                                    "opened_numbers": _json_kv(rep.kv, "opened_numbers", {}),
                                    "checked_numbers": _json_kv(rep.kv, "checked_numbers", {}),
                                    "opened_type": rep.kv.get("opened_type", ""),
                                    "opened_note": rep.kv.get("opened_note", "")})
                try:
                    gds_path = self.cache.store(key, spec.name, tmp, sidecar)
                except CacheError as e:
                    said = [ln for ln in rep.log.strip().splitlines() if ln.strip()]
                    if mark is not None:
                        said += self.server.stderr_since(mark)
                    if said:
                        raise CacheError("%s; Magic said: %s" % (e, " | ".join(said[-5:])))
                    raise
            finally:
                if os.path.exists(tmp):
                    try:
                        os.remove(tmp)
                    except OSError:
                        pass
            self.stats["magic"] += 1
            res = Result(key, gds_path, sidecar, "magic")
            self._memo[key] = res
            return res

    def check(self, spec, request):
        params, _apply = split_apply(request)
        return self.server.check(spec.name, params, spec.form if spec.form == "box" else None)

    def dialog(self, spec, form, edits, want_apply_name=False):
        """Magic's dialog form after typing ``edits`` into ``form``: a dict
        with "form", "numbers", "log", "apply_name" (with want_apply_name)
        and "source" (memo, disk or magic). The memo and the disk cache
        (keyed by the whole dialog request and the server's code) come
        first, so a file whose instances hold typed values reopens without
        Magic when its variants are cached."""
        key = self.cache.dialog_key(spec.name, dialog_request(spec, form, edits,
                                                              want_apply_name=want_apply_name))
        with self._lock:
            hit = self._dialog_memo.get(key)
            if hit is not None:
                self.stats["dialog_memo"] += 1
                return dict(hit, source="memo")
            got = self.cache.dialog_lookup(key, spec.name)
            if got is not None and not self.fresh:
                self.stats["dialog_disk"] += 1
                self._dialog_memo[key] = got
                return dict(got, source="disk")
            if want_apply_name:
                rep = self.server.dialog(spec, form, edits, want_apply_name=True)
            else:
                rep = self.server.dialog(spec, form, edits)
            self.stats["dialog_magic"] += 1
            data = {"key": key, "device": spec.name, "start": dict(form),
                    "edits": [list(e) for e in edits], "form": rep.form, "numbers": rep.numbers,
                    "log": rep.log}
            if want_apply_name:
                data["apply_name"] = rep.apply_name
            try:
                self.cache.dialog_store(key, spec.name, data)
            except OSError as e:
                log.debug("dialog cache: %s", e)
            self._dialog_memo[key] = data
            return dict(data, source="magic")

    def evict(self, spec, request):
        """Forget one variant in the memo and on disk, so the next get()
        asks Magic."""
        key = self.key(spec, request)
        with self._lock:
            self._memo.pop(key, None)
            self.cache.evict(key, spec.name)
            self.stats["evicted"] += 1

    def clear_memo(self):
        with self._lock:
            self._memo.clear()
            self._dialog_memo.clear()


_to_close = []


def _close_all():
    for s in list(_to_close):
        try:
            s.close()
        except Exception:
            pass


atexit.register(_close_all)


def make_server(cfg, vendor_cells=None):
    cls = MagicOneShot if cfg.backend == "oneshot" else MagicServer
    s = cls(cfg, vendor_cells=vendor_cells)
    _to_close.append(s)
    return s
