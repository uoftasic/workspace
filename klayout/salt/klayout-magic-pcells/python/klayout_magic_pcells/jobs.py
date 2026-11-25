"""Magic jobs: one ``magic -dnull`` process per DRC, extraction or
read-and-write run, beside the PCell servers.

A job doesn't go through the PDK's ``MagicServer``: that server answers
each request within ``KMP_TIMEOUT`` seconds behind one lock, and a DRC of a
block would hold every PCell of the PDK for its whole run. A job gets its
own process, ``magic -dnull -noconsole -rcfile <rcfile> <job.tcl>``, with
the server's environment, stdin closed, and a directory of its own that it
writes its results into. The Tcl side is ``tcl/kmp_job_common.tcl``; the
lines it prints are parsed here (``KMP_JOB_SCALE``, ``KMP_JOB``,
``KMP_JOB_FAIL``, ``KMP_JOB_DONE``).

The process is started on the calling thread (in the GUI, KLayout's main
thread), because Linux's PR_SET_PDEATHSIG kills the child when the thread
that started it exits. Two reader threads collect stdout and stderr. The
process gets a process group of its own, and a timeout or ``cancel()``
kills the whole group. ``poll()`` serves the GUI's timer; ``wait()`` and
``run_job()`` block.

A Magic process checks at most ``MAX_CELLS`` cells (one process that
checked 98 cells in a row ended without its end marker); ``batches()``
splits a longer list.

Where a job's files end up (``job_dir()``): with the job cache on, in its
key's directory ``<cache>/jobs/<pdk>/<kind>/<key>/``, where a later run
with the same key finds it. With ``KMP_CACHE=0`` or a run's ``no_cache`` option
(``--no-cache``), which mean the same, in a new directory
``<cache>/jobs/<pdk>/<kind>/tmp-<random>/``. ``release()`` removes such a
directory once the outcome's files have been read, and whatever this
process made and has not released goes when it exits; ``KMP_JOB_KEEP=1``
keeps them.

A key's directory is written once, whole. A job given ``job_dir`` runs in a
new ``tmp-<random>`` directory beside it and, when Magic has ended, renames
that directory to ``job_dir``. Nothing ever runs in a key's directory or
empties it, so two jobs with the same key at the same time (the GUI and the
command line on one layout, or two cells that export to the same file) each
read only their own files. The first to end takes the key's directory; a
later one finds it holding a finished job (job.json state "done") and keeps
its own directory, which is a tmp-* one that ``release()`` removes. A key's
directory holding a failed or unfinished job is replaced, and so is one
whose job is done but which lacks a file the feature needs (``required``:
its record, kmp_drc.json or kmp_result.json, or Magic's outputs), once the
process that ran that job has ended: until then that process may still be
writing its record. A feature may also make a folder of its own inside a
key's directory (an LVS run's ``lvs-<random>``) and register it with
``track()``; ``release()`` removes it like a tmp-* directory.
"""

import atexit
import errno
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import types

from . import __version__
from .backend import MagicServer, _make_pdeathsig, read_pdk_commit, sha256_file, sha256_tree
from .cache import JOB_META, _pid_alive, job_running, read_job_meta
from .config import TCL_DIR, DEFAULT_JOB_TIMEOUT

KINDS = ("drc", "extract", "rw")
MAX_CELLS = 15
TMP_PREFIX = "tmp-"   # a job directory outside the job cache
COMMON_TCL = "kmp_job_common.tcl"
# The PCell server's Tcl; every other .tcl file in TCL_DIR belongs to the jobs.
_SERVER_TCL = ("kmp_server.tcl", "kmp_common.tcl", "kmp_manifest.tcl")

_LINE = re.compile(r"^(KMP_JOB_SCALE|KMP_JOB_FAIL|KMP_JOB_DONE|KMP_JOB)(?:\s+(.*))?$")


class JobError(Exception):
    """A job could not be set up or started."""


class JobResult:
    """What one job did.

    ``ok``: the done line came, Magic exited 0 and printed no KMP_JOB_FAIL.
    ``scale``: µm per Magic unit, from the KMP_JOB_SCALE line, as Magic
    printed it (0.004999999888241291 on all four PDKs). ``error``: the
    KMP_JOB_FAIL text, the timeout, the cancel, or the missing done line.
    """

    def __init__(self, ok, returncode, dir, stdout, stderr, scale, stages, elapsed, error,
                 done=None):
        self.ok = ok
        self.returncode = returncode
        self.dir = dir
        self.stdout = stdout
        self.stderr = stderr
        self.scale = scale
        self.stages = stages
        self.elapsed = elapsed
        self.error = error
        self.done = done  # the number on the KMP_JOB_DONE line, or None

    def path(self, name):
        """A file the job wrote into its directory."""
        return os.path.join(self.dir, name)

    def __repr__(self):
        return "JobResult(ok=%s, returncode=%s, error=%r, elapsed=%.2f)" % (
            self.ok, self.returncode, self.error, self.elapsed)


def parse_line(line):
    """('scale' | 'stage' | 'fail' | 'done', value) for a protocol line,
    else (None, None)."""
    m = _LINE.match(line.rstrip("\r\n"))
    if not m:
        return None, None
    word, rest = m.group(1), (m.group(2) or "").strip()
    if word == "KMP_JOB_SCALE":
        try:
            return "scale", float(rest.split()[0])
        except (ValueError, IndexError):
            return None, None
    if word == "KMP_JOB_FAIL":
        return "fail", rest or "the job failed"
    if word == "KMP_JOB_DONE":
        try:
            return "done", int(rest.split()[0]) if rest else 0
        except ValueError:
            return "done", 0
    parts = rest.rsplit(None, 1)
    if len(parts) == 2:
        try:
            return "stage", (parts[0], int(parts[1]))
        except ValueError:
            pass
    return "stage", (rest, 0)


def script_path(script):
    """A job script: a file name in TCL_DIR, or an absolute path."""
    return script if os.path.isabs(script) else os.path.join(TCL_DIR, script)


def batches(items, n=MAX_CELLS):
    """``items`` in lists of at most ``n``, one list per Magic process."""
    items = list(items)
    return [items[i:i + n] for i in range(0, len(items), n)]


def _kill_group(proc):
    """SIGKILL the job's process group (Magic and anything it started)."""
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    except OSError:
        pass
    try:
        proc.kill()
    except OSError:
        pass


def jobs_root(cfg):
    return os.path.join(cfg.cache_dir, "jobs")


# -- where a job runs ------------------------------------------------------------

_made = set()          # tmp-* directories this process made and has not removed
_made_lock = threading.Lock()


def use_cache(cfg, options=None):
    """True when a run may read and write the job cache: the cache is on
    (``KMP_CACHE`` is not 0) and the run's options don't say ``no_cache``
    (``--no-cache``)."""
    return bool(getattr(cfg, "cache_enabled", True)) and not (options or {}).get("no_cache")


def keep_job_dirs(env=None):
    """True with ``KMP_JOB_KEEP=1``: tmp-* job directories are kept."""
    v = (os.environ if env is None else env).get("KMP_JOB_KEEP", "")
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def tmp_job_dir(cfg, kind):
    """A new, empty ``<cache>/jobs/<pdk>/<kind>/tmp-<random>/`` for a run
    outside the job cache. ``release()`` removes it, and so does the end of
    the process."""
    base = os.path.join(jobs_root(cfg), cfg.pdk, kind)
    try:
        os.makedirs(base, exist_ok=True)
        d = tempfile.mkdtemp(prefix=TMP_PREFIX, dir=base)
    except OSError as e:
        raise JobError("cannot make a job directory under %s (%s); set KMP_CACHE_DIR to a writable "
                       "directory" % (base, e))
    with _made_lock:
        _made.add(d)
    return d


def track(path):
    """Register a directory this process made (an LVS run's folder inside a
    key's directory) so that ``release()`` and the end of the process
    remove it, as they do a tmp-* directory."""
    with _made_lock:
        _made.add(path)
    return path


def job_dir(cfg, kind, key, options=None):
    """``(directory, cached)``: where a job whose cache key is ``key`` runs.
    With the cache on (``use_cache(cfg, options)``), the key's directory
    (``job_dir_for``) and True: a finished job there is the result, without
    running Magic. With ``KMP_CACHE=0`` or ``options["no_cache"]``, a new
    ``tmp_job_dir`` and False."""
    if use_cache(cfg, options):
        return job_dir_for(cfg, kind, key), True
    return tmp_job_dir(cfg, kind), False


def _named_dirs(what):
    if not what:
        return []
    if isinstance(what, str):
        return [what]
    if isinstance(what, (list, tuple, set)):
        return [d for w in what for d in _named_dirs(w)]
    files = what if isinstance(what, dict) else getattr(what, "files", None) or {}
    return _named_dirs([files.get("job_dir"), files.get("job"), files.get("jobs"), files.get("lvs_dir")])


def release(what):
    """Remove the tmp-* job directories that ``what`` names, once its files
    have been read: an Outcome (its ``files``' "job_dir", "job", "jobs" and
    "lvs_dir"), a files dict, a path, or a list of these. Only directories
    this process made (``tmp_job_dir``, ``track``) go; a key's directory
    stays. Nothing goes with ``KMP_JOB_KEEP=1``. Returns the directories
    removed."""
    if keep_job_dirs():
        return []
    removed = []
    for d in _named_dirs(what):
        with _made_lock:
            if d not in _made:
                continue
            _made.discard(d)
        shutil.rmtree(d, ignore_errors=True)
        removed.append(d)
    return removed


def _release_all():
    with _made_lock:
        left = sorted(_made)
    release(left)


atexit.register(_release_all)


class MagicJob:
    """One Magic process running one job script.

    ``kind``: "drc", "extract" or "rw". ``script``: a file name in TCL_DIR
    (or an absolute path). ``env``: extra ``KMP_*`` variables, all strings.
    ``files``: {name: path or bytes}, copied into the job directory before
    Magic starts. ``timeout``: seconds (default ``cfg.job_timeout``).
    ``job_dir``: the directory the finished job ends up in (a key's
    directory). The job runs in a new tmp-* directory beside it and renames
    it to ``job_dir`` when Magic has ended, unless ``job_dir`` already holds
    a finished job: then the result stays in the tmp-* directory, which
    ``release()`` removes. ``JobResult.dir`` says which. Without
    ``job_dir`` the job runs in a new ``tmp_job_dir`` (``release()`` removes
    it). ``required``: the file names a finished job's directory must hold
    to count as a result; a key's directory that is done but lacks one is
    replaced once the process that ran its job has ended.

    Magic also gets KMP_TCL_DIR, KMP_DIR (the job directory) and KMP_GDS
    (``env``'s KMP_GDS, else the first ``.gds`` in ``files``, "in.gds"
    first).
    """

    def __init__(self, cfg, kind, script, env=None, files=None, timeout=None, job_dir=None, required=()):
        if kind not in KINDS:
            raise JobError("unknown job kind %r (one of %s)" % (kind, ", ".join(KINDS)))
        self.cfg = cfg
        self.kind = kind
        self.script = script_path(script)
        if not os.path.isfile(self.script):
            raise JobError("job script %s not found" % self.script)
        self.extra_env = {}
        for k, v in (env or {}).items():
            if not (isinstance(k, str) and k.startswith("KMP_")):
                raise JobError("job variables must be named KMP_*, not %r" % (k,))
            if not isinstance(v, str):
                raise JobError("job variable %s must be a string, not %r" % (k, v))
            self.extra_env[k] = v
        self.files = {}
        for name, src in (files or {}).items():
            if (not isinstance(name, str) or not name or os.path.basename(name) != name
                    or name in (".", "..")):
                raise JobError("a job file needs a plain file name, not %r" % (name,))
            if not isinstance(src, (bytes, bytearray, str)):
                raise JobError("job file %s must be a path or bytes" % name)
            self.files[name] = src
        t = getattr(cfg, "job_timeout", DEFAULT_JOB_TIMEOUT) if timeout is None else timeout
        if not t > 0:
            raise JobError("a job timeout must be positive, not %r" % (t,))
        self.timeout = float(t)
        self.target = os.path.normpath(job_dir) if job_dir else None
        self.required = tuple(required or ())
        self.dir = None          # where the job runs; after it, where its files are
        self.stage = None
        self._proc = None
        self._result = None
        self._why_killed = None
        self._lock = threading.Lock()
        self._stdout = []
        self._stderr = []
        self._stages = []
        self._scale = None
        self._fail = None
        self._done = None
        self._threads = []

    # -- setting up ----------------------------------------------------------

    def _make_dir(self):
        if self.target:
            # A new directory beside the key's, on the same file system, so
            # that _publish can rename it into place.
            base = os.path.dirname(self.target)
            try:
                os.makedirs(base, exist_ok=True)
                d = tempfile.mkdtemp(prefix=TMP_PREFIX, dir=base)
            except OSError as e:
                raise JobError("cannot make a job directory beside %s: %s" % (self.target, e))
            with _made_lock:
                _made.add(d)
            return d
        return tmp_job_dir(self.cfg, self.kind)

    def _publish(self):
        """Rename the ended job's directory to its key's directory, unless
        that holds a finished job (or one whose process still runs): then
        ours stays where it is. Returns where the job's files are."""
        run, target = self.dir, self.target
        if not target or run == target:
            return run
        for _ in range(5):
            try:
                os.rename(run, target)   # replaces an empty directory
            except OSError as e:
                if e.errno not in (errno.EEXIST, errno.ENOTEMPTY):
                    return run
            else:
                with _made_lock:
                    _made.discard(run)
                return target
            if self._keeps(target):
                return run
            # A failed or unfinished job, a done one without its result
            # files, or a directory without job.json: move it aside in one
            # step, then remove it.
            try:
                aside = tempfile.mkdtemp(prefix=TMP_PREFIX, dir=os.path.dirname(target))
                os.rename(target, aside)
            except OSError:
                continue   # another job moved it first
            shutil.rmtree(aside, ignore_errors=True)
        return run

    def _keeps(self, target):
        """True when the key's directory ``target`` must stay: a job runs
        in it, or its job is done and the directory holds the ``required``
        files. A done job without them stays while the process that ran it
        lives, since that process writes the feature's record right after
        the job ends."""
        meta = read_job_meta(target)
        if meta is None:
            return False
        if job_running(target):
            return True
        if meta.get("state") != "done":
            return False
        if all(os.path.exists(os.path.join(target, n)) for n in self.required):
            return True
        return _pid_alive(meta.get("owner_pid"))

    def _copy_files(self):
        for name, src in self.files.items():
            dst = os.path.join(self.dir, name)
            if isinstance(src, (bytes, bytearray)):
                with open(dst, "wb") as f:
                    f.write(src)
            else:
                try:
                    shutil.copyfile(src, dst)
                except OSError as e:
                    raise JobError("cannot copy %s into the job directory: %s" % (src, e))

    def _gds(self):
        if "KMP_GDS" in self.extra_env:
            return self.extra_env["KMP_GDS"]
        names = sorted(n for n in self.files if n.lower().endswith(".gds"))
        if "in.gds" in self.files:
            names.insert(0, "in.gds")
        return os.path.join(self.dir, names[0]) if names else ""

    def environment(self):
        # The server's environment (PDK_ROOT and PDK set, DISPLAY and KMP_NS
        # removed); _env reads only cfg.
        env = MagicServer._env(types.SimpleNamespace(cfg=self.cfg))
        env.update(self.extra_env)
        env["KMP_TCL_DIR"] = TCL_DIR
        env["KMP_DIR"] = self.dir
        env["KMP_GDS"] = self._gds()
        return env

    def _write_meta(self, state, extra=None):
        meta = {"kind": self.kind, "pdk": self.cfg.pdk, "script": os.path.basename(self.script),
                "state": state, "owner_pid": os.getpid(), "plugin": __version__,
                "fingerprint": job_fingerprint(self.cfg)}
        meta.update(extra or {})
        try:
            with open(os.path.join(self.dir, JOB_META), "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=1, sort_keys=True)
        except OSError:
            pass

    # -- running -------------------------------------------------------------

    def start(self):
        """Start Magic and return at once. Call it on the thread that owns
        the job: the process dies with that thread (PR_SET_PDEATHSIG)."""
        if self._proc is not None or self._result is not None:
            raise JobError("this job was started already")
        self.dir = self._make_dir()
        self._copy_files()
        self._write_meta("running")
        cmd = [self.cfg.magic, "-dnull", "-noconsole", "-rcfile", self.cfg.magicrc, self.script]
        self._t0 = time.monotonic()
        self._deadline = self._t0 + self.timeout
        try:
            proc = subprocess.Popen(
                cmd, cwd=self.dir, env=self.environment(), stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0,
                preexec_fn=_make_pdeathsig(), start_new_session=True, close_fds=True)
        except OSError as e:
            self._write_meta("failed")
            raise JobError("cannot start Magic (%s): %s" % (self.cfg.magic, e))
        self._proc = proc

        def read_stdout(stream):
            try:
                for raw in iter(stream.readline, b""):
                    self._on_stdout(raw.decode("utf-8", errors="replace").rstrip("\r\n"))
            except (OSError, ValueError):
                pass

        def read_stderr(stream):
            try:
                for raw in iter(stream.readline, b""):
                    with self._lock:
                        self._stderr.append(raw.decode("utf-8", errors="replace"))
            except (OSError, ValueError):
                pass

        self._threads = [
            threading.Thread(target=read_stdout, args=(proc.stdout,), daemon=True,
                             name="kmp-job-stdout"),
            threading.Thread(target=read_stderr, args=(proc.stderr,), daemon=True,
                             name="kmp-job-stderr")]
        for t in self._threads:
            t.start()
        return self

    def _on_stdout(self, line):
        kind, val = parse_line(line)
        with self._lock:
            self._stdout.append(line)
            if kind == "scale":
                self._scale = val
            elif kind == "stage":
                self._stages.append(val)
                self.stage = val
            elif kind == "fail" and self._fail is None:
                self._fail = val
            elif kind == "done":
                self._done = val

    @property
    def pid(self):
        return self._proc.pid if self._proc else None

    def poll(self):
        """The result once the job has ended, else None. A job past its
        timeout is killed here."""
        if self._result is not None:
            return self._result
        if self._proc is None:
            raise JobError("the job was not started")
        if self._proc.poll() is None:
            if time.monotonic() < self._deadline:
                return None
            self._kill("timed out after %g s" % self.timeout)
        return self._finish()

    def wait(self):
        """Block until the job ends (or its timeout kills it)."""
        if self._result is not None:
            return self._result
        if self._proc is None:
            raise JobError("the job was not started")
        try:
            while True:
                left = self._deadline - time.monotonic()
                if left <= 0:
                    if self._proc.poll() is None:
                        self._kill("timed out after %g s" % self.timeout)
                    break
                try:
                    self._proc.wait(timeout=min(left, 0.5))
                    break
                except subprocess.TimeoutExpired:
                    continue
        except BaseException:
            # Ctrl-C in the command line: take Magic down with us.
            self.cancel()
            raise
        return self._finish()

    def cancel(self):
        """Kill the job's process group. The result says "cancelled"."""
        if self._proc is None or self._result is not None:
            return
        if self._proc.poll() is None:
            self._kill("cancelled")
        self._finish()

    def _kill(self, why):
        if self._why_killed is None:
            self._why_killed = why
        _kill_group(self._proc)

    def _finish(self):
        if self._result is not None:
            return self._result
        proc = self._proc
        try:
            rc = proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _kill_group(proc)
            rc = proc.wait()
        # Anything Magic started and left behind in its group goes too.
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            pass
        for t in self._threads:
            t.join(timeout=2)
        for s in (proc.stdout, proc.stderr):
            try:
                s.close()
            except Exception:
                pass
        elapsed = time.monotonic() - self._t0
        with self._lock:
            stdout = list(self._stdout)
            stderr = "".join(self._stderr)
            stages = list(self._stages)
            scale, fail, done = self._scale, self._fail, self._done
        if self._why_killed:
            error = self._why_killed
        elif fail is not None:
            error = fail
        elif done is None:
            error = "Magic ended without KMP_JOB_DONE (exit status %s)%s" % (rc, _said(stdout, stderr))
        elif rc != 0:
            error = "Magic exited with status %s after KMP_JOB_DONE" % rc
        else:
            error = None
        ok = error is None
        self._write_meta("done" if ok else "failed", {"error": error, "elapsed": round(elapsed, 3)})
        self.dir = self._publish()
        self._result = JobResult(ok, rc, self.dir, stdout, stderr, scale, stages, elapsed, error,
                                 done=done)
        return self._result


_ERRORISH = re.compile(r"(error|couldn't|can't|cannot|invalid|unknown|not found)", re.I)


def _said(stdout, stderr, n=3):
    """'; Magic said: ...' with the last lines that look like errors."""
    lines = [ln.strip() for ln in stdout + stderr.splitlines() if ln.strip()]
    picked = [ln for ln in lines if _ERRORISH.search(ln) and not ln.startswith("KMP_")]
    return ("; Magic said: " + " | ".join(picked[-n:])) if picked else ""


def run_job(cfg, kind, script, env=None, files=None, timeout=None, job_dir=None, required=()):
    """Run one job to its end and return its ``JobResult``."""
    return MagicJob(cfg, kind, script, env=env, files=files, timeout=timeout,
                    job_dir=job_dir, required=required).start().wait()


# -- the job cache -------------------------------------------------------------

_digest_memo = {}


def _memo(key, fn):
    if key not in _digest_memo:
        _digest_memo[key] = fn()
    return _digest_memo[key]


def _file_digest(path):
    try:
        st = os.stat(path)
    except OSError:
        return "missing"
    return _memo(("file", path, st.st_size, st.st_mtime_ns), lambda: sha256_file(path))


def job_tcl_files():
    """The job Tcl files: every .tcl file in TCL_DIR but the PCell server's."""
    return sorted(n for n in os.listdir(TCL_DIR) if n.endswith(".tcl") and n not in _SERVER_TCL)


def tcl_digest():
    """SHA-256 over every job Tcl file, names and contents."""
    h = hashlib.sha256()
    for name in job_tcl_files():
        with open(os.path.join(TCL_DIR, name), "rb") as f:
            h.update(name.encode("utf-8") + b"\0" + f.read() + b"\0")
    return h.hexdigest()


def pdk_versions_digest(cfg):
    """What the PDK and Magic are, without starting Magic: the Magic
    executable's and the rcfile's SHA-256, every file in the rcfile's
    directory (libs.tech/magic: the tech file and what it includes), and the
    PDK's commit."""
    techdir = os.path.dirname(cfg.magicrc)
    fields = {
        "pdk": cfg.pdk,
        "magic": cfg.magic,
        "magic_sha256": _file_digest(cfg.magic),
        "magicrc_sha256": _file_digest(cfg.magicrc),
        "techdir": _memo(("tree", techdir), lambda: sha256_tree(techdir)),
        "pdk_commit": _memo(("commit", cfg.pdk_path), lambda: read_pdk_commit(cfg.pdk_path)),
    }
    return hashlib.sha256(json.dumps(fields, sort_keys=True).encode("utf-8")).hexdigest()


def job_fingerprint(cfg):
    """The parts of every job key that don't depend on the job: the PDK's
    versions digest, the job Tcl and the plugin version. A job directory
    records it, so that ``cache prune`` can tell stale ones."""
    obj = {"versions": pdk_versions_digest(cfg), "tcl": tcl_digest(), "plugin": __version__}
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode("utf-8")).hexdigest()


def job_cache_key(export_sha256, kind, options, cfg):
    """The cache key of one job: SHA-256 over the export's digest, the kind,
    the options, the PDK versions digest, the digest of every job Tcl file
    and the plugin version."""
    obj = {"export": export_sha256, "kind": kind, "options": options, "pdk": cfg.pdk,
           "versions": pdk_versions_digest(cfg), "tcl": tcl_digest(), "plugin": __version__}
    text = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def job_dir_for(cfg, kind, key):
    """``<cache>/jobs/<pdk>/<kind>/<key>/``."""
    return os.path.join(jobs_root(cfg), cfg.pdk, kind, key)
