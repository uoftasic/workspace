"""Disk cache of Magic's GDS output, keyed by request and versions.

Layout: ``<root>/v1/<versions digest, 12 hex>/<device>/<key, 24 hex>.gds``
plus a ``.json`` sidecar next to it. A GDS without its sidecar is a miss.
The sidecar records the SHA-256 of the GDS as stored; a GDS whose bytes no
longer match it (truncated, overwritten, another entry's file) is a miss,
and the entry is deleted so that Magic regenerates it. Each versions
directory holds ``versions.json``, which names its PDK (prune works per
PDK). ``<root>/tmp`` holds the files Magic is writing.

``<root>/jobs/<pdk>/<kind>/<dir>/`` holds the jobs' directories (jobs.py):
the job's input, Magic's output files and ``job.json``, which records the
job's PDK, its state, the process that started it and the fingerprint of
the versions it ran with. ``<dir>`` is the job's cache key, or
``tmp-<random>`` for a run outside the job cache (``run-<random>`` in
earlier 0.6 builds). ``clear`` deletes them, except those of a job still
running; ``prune`` deletes those of the PDKs it works on whose fingerprint
is not the current one, their tmp-* directories whose process has
ended, and the ``lvs-<random>`` folders an LVS run leaves in a key's
directory when its process ended before removing them.

Another process may delete any of these while a session runs (``cache
clear``, ``cache prune``, or the whole directory removed by hand): the
session makes the directories again when it next writes, and an entry it
remembered that is gone is generated again.
"""

import atexit
import hashlib
import json
import os
import shutil
import tempfile
import time

from . import protocol

# 2: the sidecar carries gds_sha256. 3: the versions fields cover the PDK
# commit, every file in libs.tech/magic and the fixed devices' vendor GDS.
# 4: the sidecar carries what Magic's dialog shows when it reopens on the
# instance ("opened"), and a request may be an Apply (kmp_apply).
# A new format starts a new versions directory, so older entries are never
# read.
FORMAT = 4

_TCL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tcl")


def server_code_digest():
    """SHA-256 of the server's Tcl (kmp_server.tcl and kmp_common.tcl),
    which holds the plugin's model of Magic's dialog (the binding chain,
    one update_dialog pass, Apply's name). It is part of the dialog cache
    key: a change to that model must not be answered from entries the old
    model wrote."""
    h = hashlib.sha256()
    for name in ("kmp_server.tcl", "kmp_common.tcl"):
        with open(os.path.join(_TCL, name), "rb") as f:
            h.update(name.encode() + b"\0" + f.read() + b"\0")
    return h.hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 16), b""):
            h.update(block)
    return h.hexdigest()


def canonical_json(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def versions_fields(versions, pdk):
    """Every key field except device, form and request."""
    return {
        "format": FORMAT,
        "protocol": protocol.PROTOCOL,
        "pdk": pdk,
        "magic": versions.magic,
        "open_pdks": versions.open_pdks,
        "tech": versions.tech,
        "code": versions.code,
        "techfile": versions.techfile,
        "pdk_commit": getattr(versions, "pdk_commit", ""),
        "techdir": getattr(versions, "techdir", ""),
        "vendor": getattr(versions, "vendor", ""),
    }


def versions_digest(fields):
    return hashlib.sha256(canonical_json(fields).encode("utf-8")).hexdigest()


def cache_key(fields, device, form, request):
    obj = dict(fields)
    obj["device"] = device
    obj["form"] = form
    obj["request"] = {str(k): str(v) for k, v in request.items()}
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def _atomic_write_text(path, text):
    d = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", suffix=".json", dir=d)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


class CacheError(Exception):
    pass


def count_top_cells(gds_path):
    """Read the file with KLayout and return its top cell names."""
    from ._kl import db
    ly = db.Layout()
    ly.read(gds_path)
    return [c.name for c in ly.top_cells()]


class GdsCache:
    """``enabled=False`` keeps nothing on disk between sessions (KMP_CACHE=0)."""

    def __init__(self, root, fields, enabled=True, validate=count_top_cells, server_code=None):
        self.root = root
        self.fields = dict(fields)
        self.enabled = enabled
        self.validate = validate
        self.server_code = server_code if server_code is not None else server_code_digest()
        self.vdigest = versions_digest(self.fields)[:12]
        self.stats_counts = {"evicted": 0}
        self._own_dir = None
        if enabled:
            self.base = os.path.join(root, "v1", self.vdigest)
            self.tmp_dir = os.path.join(root, "tmp")
        else:
            # The session's entries live here and are deleted with it.
            self.base = self._own_dir = tempfile.mkdtemp(prefix="kmp-nocache-")
            self.tmp_dir = os.path.join(self.base, "tmp")
            atexit.register(self.close)
        os.makedirs(self.tmp_dir, exist_ok=True)

    def close(self):
        """Delete the session directory of a disabled cache (KMP_CACHE=0)."""
        if self._own_dir:
            shutil.rmtree(self._own_dir, ignore_errors=True)
            self._own_dir = None

    def key(self, device, form, request):
        return cache_key(self.fields, device, form, request)

    def paths(self, key, device):
        d = os.path.join(self.base, device)
        return os.path.join(d, key[:24] + ".gds"), os.path.join(d, key[:24] + ".json")

    def tmp_path(self, key):
        # Made again here: cache clear or prune in another process, or the
        # cache directory removed by hand, may have deleted it.
        os.makedirs(self.tmp_dir, exist_ok=True)
        return os.path.join(self.tmp_dir, "%s.%d.gds" % (key[:24], os.getpid()))

    def lookup(self, key, device):
        """Return (gds_path, sidecar) or None.

        A sidecar that can't be read or names another key is a miss. A
        sidecar for another device, or a GDS whose SHA-256 differs from the
        one recorded at store time, is a miss and the entry is deleted.
        """
        if not self.enabled:
            return None
        gds, side = self.paths(key, device)
        if not (os.path.isfile(gds) and os.path.isfile(side)):
            return None
        try:
            with open(side, encoding="utf-8") as f:
                sidecar = json.load(f)
        except (OSError, ValueError):
            return None
        if not isinstance(sidecar, dict) or sidecar.get("key") != key:
            return None
        try:
            good = sidecar.get("device") == device and sha256_file(gds) == sidecar.get("gds_sha256")
        except OSError:
            good = False
        if not good:
            self.evict(key, device)
            return None
        return gds, sidecar

    def evict(self, key, device):
        """Delete one entry (both files); a missing file is no error."""
        for p in self.paths(key, device):
            try:
                os.remove(p)
            except OSError:
                pass
        self.stats_counts["evicted"] += 1

    def store(self, key, device, tmp_gds, sidecar):
        """Validate ``tmp_gds``, move it into place, then write the sidecar.

        Sets ``device`` and ``gds_sha256`` in ``sidecar``.
        """
        if not os.path.isfile(tmp_gds) or os.path.getsize(tmp_gds) == 0:
            raise CacheError("Magic wrote no GDS at %s" % tmp_gds)
        if self.validate is not None:
            tops = self.validate(tmp_gds)
            if len(tops) != 1:
                raise CacheError("%s: expected one top cell, found %d (%s)"
                                 % (tmp_gds, len(tops), ", ".join(tops)))
        sidecar["device"] = device
        sidecar["gds_sha256"] = sha256_file(tmp_gds)
        gds, side = self.paths(key, device)
        os.makedirs(os.path.dirname(gds), exist_ok=True)
        marker = os.path.join(self.base, "versions.json")
        if self.enabled and not os.path.isfile(marker):
            _atomic_write_text(marker, json.dumps(self.fields, indent=1, sort_keys=True) + "\n")
        os.replace(tmp_gds, gds)
        _atomic_write_text(side, json.dumps(sidecar, indent=1, sort_keys=True) + "\n")
        return gds

    # -- Magic's dialog forms ------------------------------------------------
    #
    # What Magic's parameter dialog made of a form and a list of edits (the
    # dialog op), kept as <versions dir>/_dialog/<key, 24 hex>.json. No
    # device is called "_dialog".

    def dialog_key(self, device, request):
        """The key of one dialog op: the versions fields, the device, the
        whole request (the form, the edits, the dialog's widget order and
        dependencies from the manifest, what else was asked) and the
        server's code. Which edits the plugin types where (dialog.plan) is
        in the request itself."""
        obj = dict(self.fields)
        obj.update({"op": "dialog", "device": device, "request": request,
                    "server_code": self.server_code})
        return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()

    def dialog_path(self, key):
        return os.path.join(self.base, "_dialog", key[:24] + ".json")

    def dialog_lookup(self, key, device):
        """The stored dialog result, or None (also for one written for
        another key or device, or without a form)."""
        if not self.enabled:
            return None
        try:
            with open(self.dialog_path(key), encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return None
        if (not isinstance(data, dict) or data.get("key") != key or data.get("device") != device
                or not isinstance(data.get("form"), dict)):
            return None
        return data

    def dialog_store(self, key, device, data):
        if not self.enabled:
            return
        path = self.dialog_path(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        marker = os.path.join(self.base, "versions.json")
        if not os.path.isfile(marker):
            _atomic_write_text(marker, json.dumps(self.fields, indent=1, sort_keys=True) + "\n")
        _atomic_write_text(path, json.dumps(dict(data, key=key, device=device), indent=1,
                                            sort_keys=True) + "\n")

    # -- maintenance ----------------------------------------------------------

    def version_dirs(self):
        top = os.path.join(self.root, "v1")
        if not os.path.isdir(top):
            return []
        return sorted(os.path.join(top, d) for d in os.listdir(top))

    @staticmethod
    def pdk_of(version_dir):
        """The PDK a versions directory belongs to: from its versions.json,
        else (a directory written before version 0.4) from the first sidecar
        found in it; None for a directory with neither."""
        try:
            with open(os.path.join(version_dir, "versions.json"), encoding="utf-8") as f:
                pdk = json.load(f).get("pdk")
            if pdk:
                return pdk
        except (OSError, ValueError, AttributeError):
            pass
        try:
            devices = sorted(os.listdir(version_dir))
        except OSError:
            return None
        for dev in devices:
            d = os.path.join(version_dir, dev)
            if not os.path.isdir(d):
                continue
            for fn in sorted(os.listdir(d)):
                if not fn.endswith(".json"):
                    continue
                try:
                    with open(os.path.join(d, fn), encoding="utf-8") as f:
                        side = json.load(f)
                    pdk = (side.get("versions") or {}).get("pdk")
                    if pdk:
                        return pdk
                except (OSError, ValueError, AttributeError):
                    continue
        return None

    def prune(self, current=None, tmp_age=86400):
        """Delete the versions directories of the PDKs in ``current`` ({pdk:
        current versions digest}, default: this cache's own) except each
        one's current directory, and directories that hold no entry.
        Directories of other PDKs are left alone: their current digest isn't
        known here. Files in tmp older than ``tmp_age`` seconds go too (a
        session that died while Magic wrote); the directory itself stays.

        Returns (removed directories, {kept directory: its PDK})."""
        if current is None:
            current = {self.fields.get("pdk"): self.vdigest}
        removed, other = [], {}
        for d in self.version_dirs():
            name = os.path.basename(d)
            pdk = self.pdk_of(d)
            if pdk is None or (pdk in current and current[pdk] != name):
                shutil.rmtree(d, ignore_errors=True)
                removed.append(d)
            elif pdk not in current:
                other[d] = pdk
        self._clean_tmp(tmp_age)
        return removed, other

    def _clean_tmp(self, age):
        tmp = os.path.join(self.root, "tmp")
        try:
            names = os.listdir(tmp)
        except OSError:
            return
        now = time.time()
        for fn in names:
            p = os.path.join(tmp, fn)
            try:
                if now - os.path.getmtime(p) > age:
                    os.remove(p)
            except OSError:
                pass

    def clear(self, tmp_age=86400):
        """Delete every entry of every PDK, and every job directory. A
        running session's files in tmp (and Magic's run directories) and a
        running job's directory are left; they go with it."""
        shutil.rmtree(os.path.join(self.root, "v1"), ignore_errors=True)
        self._clean_tmp(tmp_age)
        clear_jobs(self.root)

    def stats(self, pdks=None):
        """Entries and versions directories of every PDK; job directories of
        the PDKs in ``pdks`` (default: every PDK)."""
        n = size = 0
        for d in self.version_dirs():
            for dirpath, _, files in os.walk(d):
                for fn in files:
                    if fn.endswith(".gds"):
                        n += 1
                    size += os.path.getsize(os.path.join(dirpath, fn))
        jobs = job_dirs(self.root, pdks)
        return {"entries": n, "bytes": size, "versions": len(self.version_dirs()),
                "current": self.vdigest,
                "pdk_of": {os.path.basename(d): self.pdk_of(d) for d in self.version_dirs()},
                "jobs": len(jobs), "jobs_bytes": sum(_tree_size(d) for d in jobs)}


# -- job directories ------------------------------------------------------------

JOBS = "jobs"
JOB_META = "job.json"  # the same name as jobs.JOB_META (jobs.py imports this module)


def _tree_size(path):
    size = 0
    for dirpath, _, files in os.walk(path):
        for fn in files:
            try:
                size += os.path.getsize(os.path.join(dirpath, fn))
            except OSError:
                pass
    return size


TMP_PREFIXES = ("tmp-", "run-")  # jobs.TMP_PREFIX, and the run-* of earlier 0.6 builds
LVS_PREFIX = "lvs-"              # an LVS run's folder inside a key's directory (lvsjob)
OWNER_FILE = "kmp_owner.json"    # {"owner_pid": N} in such a folder


def job_dirs(root, pdks=None):
    """Every job directory, ``<root>/jobs/<pdk>/<kind>/<dir>``; with
    ``pdks``, only those of these PDKs."""
    out = []
    top = os.path.join(root, JOBS)
    for level1 in (sorted(os.listdir(top)) if os.path.isdir(top) else []):
        p1 = os.path.join(top, level1)
        if not os.path.isdir(p1) or (pdks is not None and level1 not in pdks):
            continue
        for level2 in sorted(os.listdir(p1)):
            p2 = os.path.join(p1, level2)
            if not os.path.isdir(p2):
                continue
            out += [os.path.join(p2, d) for d in sorted(os.listdir(p2))
                    if os.path.isdir(os.path.join(p2, d))]
    return out


def read_job_meta(job_dir):
    try:
        with open(os.path.join(job_dir, JOB_META), encoding="utf-8") as f:
            meta = json.load(f)
        return meta if isinstance(meta, dict) else None
    except (OSError, ValueError):
        return None


def _pid_alive(pid):
    try:
        with open("/proc/%d/status" % int(pid)) as f:
            return "State:\tZ" not in f.read()
    except (OSError, ValueError, TypeError):
        return False


def job_running(job_dir):
    """True while the process that started the job still runs it."""
    meta = read_job_meta(job_dir)
    return bool(meta and meta.get("state") == "running" and _pid_alive(meta.get("owner_pid")))


def clear_jobs(root):
    """Delete every job directory except a running job's. Returns the
    directories removed."""
    removed = []
    for d in job_dirs(root):
        if job_running(d):
            continue
        shutil.rmtree(d, ignore_errors=True)
        removed.append(d)
    return removed


def is_tmp_job_dir(job_dir):
    """A job directory outside the job cache (tmp-*, or run-* of earlier
    0.6 builds)."""
    return os.path.basename(os.path.normpath(job_dir)).startswith(TMP_PREFIXES)


def _old(path, age, now):
    try:
        return now - os.path.getmtime(path) > age
    except OSError:
        return False


def lvs_leftovers(job_dir, age=86400, now=None):
    """The ``lvs-*`` folders in a key's directory whose LVS process has
    ended (``kmp_owner.json``), or that have no readable owner file and are
    older than ``age`` seconds."""
    now = time.time() if now is None else now
    out = []
    try:
        names = sorted(os.listdir(job_dir))
    except OSError:
        return out
    for n in names:
        p = os.path.join(job_dir, n)
        if not (n.startswith(LVS_PREFIX) and os.path.isdir(p)):
            continue
        try:
            with open(os.path.join(p, OWNER_FILE), encoding="utf-8") as f:
                pid = json.load(f).get("owner_pid")
        except (OSError, ValueError, AttributeError):
            if _old(p, age, now):
                out.append(p)
            continue
        if not _pid_alive(pid):
            out.append(p)
    return out


def prune_jobs(root, current, age=86400):
    """Delete the job directories of the PDKs in ``current`` ({pdk: the
    current fingerprint, jobs.job_fingerprint}) that ran with another
    fingerprint, their tmp-* directories whose process has ended (one whose
    process still runs is that session's, which removes it), and any job
    directory without a readable job.json older than ``age`` seconds. In
    the key directories it keeps, it deletes the LVS runs' leftover
    ``lvs-*`` folders (``lvs_leftovers``). A running job's directory and
    other PDKs' are left. Returns the directories removed."""
    removed = []
    now = time.time()
    for d in job_dirs(root):
        if job_running(d):
            continue
        meta = read_job_meta(d)
        if meta is None:
            if not _old(d, age, now):
                continue
        else:
            pdk = meta.get("pdk")
            if pdk not in current:
                continue
            if is_tmp_job_dir(d):
                if _pid_alive(meta.get("owner_pid")):
                    continue
            elif meta.get("fingerprint") == current[pdk]:
                for left in lvs_leftovers(d, age, now):
                    shutil.rmtree(left, ignore_errors=True)
                    removed.append(left)
                continue
        shutil.rmtree(d, ignore_errors=True)
        removed.append(d)
    return removed
