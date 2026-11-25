"""MagicJob with a fake Magic (no Magic needed), the job cache key and job
directories, and the job subcommands' argument and cell checks. With the
klayout module, the layers, ports and extract tasks and the extract command
run on the fake Magic too."""

import io
import json
import os
import shutil
import sys
import tempfile
import textwrap
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout

from tests.unit._util import REPO, needs_klayout, db  # noqa: F401
import types

from klayout_magic_pcells import cache, jobs
from klayout_magic_pcells.config import Config

# Stands in for "magic -dnull -noconsole -rcfile RC job.tcl": what it does
# comes from KMP_FAKE. It records what it saw in KMP_DIR/seen.json.
FAKE_MAGIC = textwrap.dedent("""
    import json, os, subprocess, sys, time
    mode = os.environ.get("KMP_FAKE", "done")
    d = os.environ["KMP_DIR"]
    seen = {"argv": sys.argv[1:], "cwd": os.getcwd(), "stdin": sys.stdin.read(),
            "env": {k: os.environ.get(k) for k in ("KMP_DIR", "KMP_TCL_DIR", "KMP_GDS", "KMP_CELL",
                                                   "PDK", "PDK_ROOT", "DISPLAY", "KMP_NS")}}
    with open(os.path.join(d, "seen.json"), "w") as f:
        json.dump(seen, f)
    def say(s):
        print(s, flush=True)
    print("Magic 8.3 revision 681 - fake")
    say("KMP_JOB_SCALE 0.004999999888241291")
    say("KMP_JOB reading 1")
    if mode in ("hang", "cancel"):
        # A grandchild in the same process group, as Magic's exec would make.
        child = subprocess.Popen(["sleep", "100"])
        with open(os.path.join(d, "pids"), "w") as f:
            f.write("%d %d" % (os.getpid(), child.pid))
        say("KMP_JOB checking 3")
        time.sleep(100)
    if mode == "fail":
        say("KMP_JOB_FAIL cell does_not_exist is not among the cells Magic read from the file")
        sys.exit(0)
    if mode == "empty":
        # kmp_job_load on a cell Magic's reader kept nothing of.
        say("KMP_JOB_FAIL cell %s is empty" % os.environ.get("KMP_TOP", "TOP"))
        sys.exit(0)
    if mode == "nodone":
        sys.stderr.write('Error parsing "job.tcl": invalid command name "nosuch"\\n')
        sys.exit(0)
    if mode == "badexit":
        say("KMP_JOB_DONE 1")
        sys.exit(3)
    if mode == "slow":
        time.sleep(float(os.environ.get("KMP_SLOW", "1")))
    with open(os.path.join(d, "result.tsv"), "w") as f:
        f.write(os.environ.get("KMP_TAG", "x") + "\\n")
    # What the feature scripts write, for the feature tasks' tests.
    top = os.environ.get("KMP_TOP", "TOP")
    if "KMP_RW_MODE" in os.environ:
        import shutil
        shutil.copyfile(os.environ["KMP_GDS"], os.path.join(d, "rw.gds"))
        open(os.path.join(d, "kmp__flat.ext"), "w").close()
        with open(os.path.join(d, "rw_times.txt"), "w") as f:
            f.write("scale 0.004999999888241291\\n")
        with open(os.path.join(d, top + ".spice"), "w") as f:
            f.write(".subckt %s A Y\\n.ends\\n" % top)
    if "KMP_OUT" in os.environ:
        with open(os.path.join(d, top + ".ext"), "w") as f:
            f.write("tech sky130A\\nscale 1000 1 5\\n")
        with open(os.path.join(d, os.environ["KMP_OUT"]), "w") as f:
            f.write("* NGSPICE file created from %s.ext - technology: sky130A\\n.subckt %s A Y\\n.ends\\n"
                    % (top, top))
    sys.stderr.write("Warning: Calma reading is not undoable!  I hope that's OK.\\n")
    say("KMP_JOB checking 2")
    say("KMP_JOB_DONE 2")
""")


def alive(pid):
    try:
        with open("/proc/%d/status" % pid) as f:
            return "State:\tZ" not in f.read()
    except OSError:
        return False


class _Fake(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="kmp-jobs-")
        self.magic = os.path.join(self.d, "magic")
        with open(self.magic, "w") as f:
            f.write("#!%s\n" % sys.executable + FAKE_MAGIC)
        os.chmod(self.magic, 0o755)
        self.rc = os.path.join(self.d, "pdks", "sky130A", "libs.tech", "magic", "sky130A.magicrc")
        os.makedirs(os.path.dirname(self.rc))
        with open(self.rc, "w") as f:
            f.write("# rcfile\n")
        self.script = os.path.join(self.d, "job.tcl")
        with open(self.script, "w") as f:
            f.write("# the fake reads KMP_FAKE instead\n")
        self.cfg = Config.load(env={"HOME": self.d, "KMP_MAGIC": self.magic, "PATH": os.environ["PATH"],
                                    "PDK_ROOT": os.path.join(self.d, "pdks"), "KMP_PDK": "sky130A",
                                    "KMP_CACHE_DIR": os.path.join(self.d, "cache"),
                                    "DISPLAY": ":99"},
                               config_path="/nonexistent.ini")

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def job(self, mode, **kw):
        env = dict(kw.pop("env", {}), KMP_FAKE=mode)
        return jobs.MagicJob(self.cfg, "drc", self.script, env=env, **kw)


class MagicJobWithAFakeMagic(_Fake):
    def test_a_job_that_finishes(self):
        r = jobs.run_job(self.cfg, "drc", self.script, env={"KMP_FAKE": "done", "KMP_CELL": "inv$1"},
                         files={"in.gds": b"GDS", "names.txt": self.rc})
        self.assertTrue(r.ok, r.error)
        self.assertIsNone(r.error)
        self.assertEqual(r.returncode, 0)
        self.assertAlmostEqual(r.scale, 0.005, places=6)
        self.assertEqual(r.stages, [("reading", 1), ("checking", 2)])
        self.assertEqual(r.done, 2)
        self.assertIn("Calma reading", r.stderr)
        self.assertIn("KMP_JOB_DONE 2", r.stdout)
        self.assertTrue(os.path.isfile(r.path("result.tsv")))
        # The job directory is under <cache>/jobs/<pdk>/<kind>/ and holds the files.
        self.assertTrue(r.dir.startswith(os.path.join(self.d, "cache", "jobs", "sky130A", "drc") + os.sep))
        with open(r.path("in.gds"), "rb") as f:
            self.assertEqual(f.read(), b"GDS")
        self.assertTrue(os.path.isfile(r.path("names.txt")))
        with open(r.path("seen.json")) as f:
            seen = json.load(f)
        self.assertEqual(seen["argv"], ["-dnull", "-noconsole", "-rcfile", self.rc, self.script])
        self.assertEqual(os.path.realpath(seen["cwd"]), os.path.realpath(r.dir))
        self.assertEqual(seen["stdin"], "")
        env = seen["env"]
        self.assertEqual(env["KMP_DIR"], r.dir)
        self.assertEqual(env["KMP_GDS"], r.path("in.gds"))
        self.assertTrue(env["KMP_TCL_DIR"].endswith(os.path.join("klayout_magic_pcells", "tcl")))
        self.assertEqual(env["KMP_CELL"], "inv$1")
        self.assertEqual((env["PDK"], env["PDK_ROOT"]), ("sky130A", os.path.join(self.d, "pdks")))
        self.assertIsNone(env["DISPLAY"])
        with open(r.path("job.json")) as f:
            meta = json.load(f)
        self.assertEqual((meta["state"], meta["kind"], meta["pdk"]), ("done", "drc", "sky130A"))
        self.assertEqual(meta["fingerprint"], jobs.job_fingerprint(self.cfg))

    def test_a_missing_done_line_fails_the_job(self):
        r = self.job("nodone").start().wait()
        self.assertFalse(r.ok)
        self.assertEqual(r.returncode, 0)
        self.assertIn("without KMP_JOB_DONE", r.error)
        self.assertIn('invalid command name "nosuch"', r.error)

    def test_kmp_job_fail_fails_the_job(self):
        r = self.job("fail").start().wait()
        self.assertFalse(r.ok)
        self.assertEqual(r.error, "cell does_not_exist is not among the cells Magic read from the file")

    def test_a_bad_exit_status_after_the_done_line(self):
        r = self.job("badexit").start().wait()
        self.assertFalse(r.ok)
        self.assertEqual(r.returncode, 3)
        self.assertIn("status 3", r.error)

    def _pids(self, job):
        p = os.path.join(job.dir, "pids")
        for _ in range(100):
            if os.path.isfile(p) and os.path.getsize(p):
                with open(p) as f:
                    return [int(x) for x in f.read().split()]
            time.sleep(0.05)
        self.fail("the fake Magic never wrote its pids")

    def test_a_timeout_kills_the_process_group(self):
        t = time.monotonic()
        job = self.job("hang", timeout=1).start()
        pids = self._pids(job)
        r = job.wait()
        self.assertLess(time.monotonic() - t, 20)
        self.assertFalse(r.ok)
        self.assertEqual(r.error, "timed out after 1 s")
        self.assertEqual(r.stages[-1], ("checking", 3))
        for pid in pids:
            for _ in range(50):
                if not alive(pid):
                    break
                time.sleep(0.05)
            self.assertFalse(alive(pid), "process %d left after the timeout" % pid)

    def test_poll_then_cancel(self):
        job = self.job("cancel").start()
        self.assertIsNone(job.poll())
        pids = self._pids(job)
        for _ in range(100):
            if job.stage == ("checking", 3):
                break
            time.sleep(0.05)
        self.assertEqual(job.stage, ("checking", 3))
        self.assertIsNone(job.poll())
        job.cancel()
        r = job.poll()
        self.assertIs(r, job.wait())
        self.assertFalse(r.ok)
        self.assertEqual(r.error, "cancelled")
        for pid in pids:
            for _ in range(50):
                if not alive(pid):
                    break
                time.sleep(0.05)
            self.assertFalse(alive(pid), "process %d left after cancel" % pid)
        with open(os.path.join(r.dir, "job.json")) as f:
            self.assertEqual(json.load(f)["state"], "failed")

    def test_poll_sees_the_end(self):
        job = self.job("done").start()
        for _ in range(200):
            r = job.poll()
            if r is not None:
                break
            time.sleep(0.05)
        self.assertTrue(r.ok, r.error)

    def test_a_given_job_dir_is_emptied_first(self):
        jd = os.path.join(self.d, "mine")
        os.makedirs(jd)
        with open(os.path.join(jd, "stale.txt"), "w") as f:
            f.write("old")
        r = self.job("done", job_dir=jd).start().wait()
        self.assertTrue(r.ok, r.error)
        self.assertEqual(r.dir, jd)
        self.assertFalse(os.path.exists(os.path.join(jd, "stale.txt")))

    def test_two_jobs_with_one_job_dir_at_once(self):
        # Each job runs in a directory of its own, so neither reads the other's
        # files (design-0.6.md 2.3).
        jd = os.path.join(self.d, "cache", "jobs", "sky130A", "drc", "k" * 64)
        a = self.job("slow", env={"KMP_TAG": "A", "KMP_SLOW": "1"}, job_dir=jd).start()
        time.sleep(0.2)
        b = self.job("done", env={"KMP_TAG": "B"}, job_dir=jd).start()
        rb = b.wait()
        ra = a.wait()
        for tag, r in (("A", ra), ("B", rb)):
            self.assertTrue(r.ok, r.error)
            with open(r.path("result.tsv")) as f:
                self.assertEqual(f.read(), tag + "\n", "job %s read another job's result" % tag)
        # B ended first and took the key's directory; A's result stays in its
        # own tmp-* directory beside it, which release() removes.
        self.assertEqual(rb.dir, jd)
        self.assertNotEqual(ra.dir, jd)
        self.assertEqual(os.path.dirname(ra.dir), os.path.dirname(jd))
        self.assertTrue(os.path.basename(ra.dir).startswith("tmp-"), ra.dir)
        with open(os.path.join(jd, "job.json")) as f:
            self.assertEqual(json.load(f)["state"], "done")
        self.assertEqual(jobs.release(ra.dir), [ra.dir])
        self.assertEqual(jobs.release(rb.dir), [])
        self.assertTrue(os.path.isdir(jd))
        # While a job runs, the key's directory is not touched.
        c = self.job("slow", env={"KMP_TAG": "C", "KMP_SLOW": "0.5"}, job_dir=jd).start()
        self.assertNotEqual(c.dir, jd)
        with open(os.path.join(jd, "result.tsv")) as f:
            self.assertEqual(f.read(), "B\n")
        rc = c.wait()
        self.assertTrue(rc.ok, rc.error)
        self.assertNotEqual(rc.dir, jd)
        jobs.release(rc.dir)

    def test_a_failed_job_in_the_key_dir_is_replaced(self):
        jd = os.path.join(self.d, "cache", "jobs", "sky130A", "drc", "f" * 64)
        r1 = self.job("fail", job_dir=jd).start().wait()
        self.assertFalse(r1.ok)
        self.assertEqual(r1.dir, jd)
        r2 = self.job("done", env={"KMP_TAG": "ok"}, job_dir=jd).start().wait()
        self.assertTrue(r2.ok, r2.error)
        self.assertEqual(r2.dir, jd)
        with open(os.path.join(jd, "job.json")) as f:
            self.assertEqual(json.load(f)["state"], "done")
        with open(os.path.join(jd, "result.tsv")) as f:
            self.assertEqual(f.read(), "ok\n")
        left = [n for n in os.listdir(os.path.dirname(jd)) if n.startswith("tmp-")]
        self.assertEqual(left, [])

    def _done_key_dir(self, jd, owner_pid):
        """A key's directory whose job.json says done, holding no record."""
        os.makedirs(jd)
        with open(os.path.join(jd, "in.gds"), "wb") as f:
            f.write(b"GDS")
        with open(os.path.join(jd, "job.json"), "w") as f:
            json.dump({"kind": "extract", "pdk": "sky130A", "state": "done", "owner_pid": owner_pid,
                       "fingerprint": jobs.job_fingerprint(self.cfg)}, f)

    def test_a_done_key_dir_without_its_record_is_replaced(self):
        # A key's directory marked done but without the job's result file (only
        # in.gds and job.json) is replaced; kept, that key would never be cached again.
        jd = os.path.join(self.d, "cache", "jobs", "sky130A", "drc", "d" * 64)
        self._done_key_dir(jd, _dead_pid())
        r = self.job("done", env={"KMP_TAG": "new"}, job_dir=jd, required=("result.tsv",)).start().wait()
        self.assertTrue(r.ok, r.error)
        self.assertEqual(r.dir, jd)
        with open(os.path.join(jd, "result.tsv")) as f:
            self.assertEqual(f.read(), "new\n")
        with open(os.path.join(jd, "job.json")) as f:
            self.assertEqual(json.load(f)["owner_pid"], os.getpid())
        self.assertEqual([n for n in os.listdir(os.path.dirname(jd)) if n.startswith("tmp-")], [])

    def test_a_done_key_dir_without_its_record_stays_while_its_process_lives(self):
        # That process may be about to write its record.
        jd = os.path.join(self.d, "cache", "jobs", "sky130A", "drc", "e" * 64)
        self._done_key_dir(jd, os.getpid())
        r = self.job("done", job_dir=jd, required=("result.tsv",)).start().wait()
        self.assertTrue(r.ok, r.error)
        self.assertNotEqual(r.dir, jd)
        self.assertFalse(os.path.exists(os.path.join(jd, "result.tsv")))
        jobs.release(r.dir)
        # A done directory that holds the record stays whatever its owner.
        jd2 = os.path.join(self.d, "cache", "jobs", "sky130A", "drc", "c" * 64)
        self._done_key_dir(jd2, None)
        with open(os.path.join(jd2, "result.tsv"), "w") as f:
            f.write("old\n")
        r = self.job("done", job_dir=jd2, required=("result.tsv",)).start().wait()
        self.assertNotEqual(r.dir, jd2)
        jobs.release(r.dir)

    def test_bad_arguments(self):
        for kw in ({"env": {"PATH": "/x"}}, {"env": {"KMP_X": 1}}, {"files": {"../x": b""}},
                   {"files": {"a/b": b""}}, {"timeout": 0}):
            with self.assertRaises(jobs.JobError, msg=str(kw)):
                jobs.MagicJob(self.cfg, "drc", self.script, **kw)
        with self.assertRaises(jobs.JobError):
            jobs.MagicJob(self.cfg, "lint", self.script)
        with self.assertRaises(jobs.JobError):
            jobs.MagicJob(self.cfg, "drc", "no_such_script.tcl")
        job = self.job("done")
        with self.assertRaises(jobs.JobError):
            job.poll()
        job.start().wait()
        with self.assertRaises(jobs.JobError):
            job.start()

    def test_magic_missing(self):
        cfg = Config.load(env={"HOME": self.d, "KMP_MAGIC": os.path.join(self.d, "nope"),
                               "KMP_CACHE_DIR": os.path.join(self.d, "cache")},
                          config_path="/nonexistent.ini")
        with self.assertRaises(jobs.JobError) as cm:
            jobs.run_job(cfg, "drc", self.script)
        self.assertIn("cannot start Magic", str(cm.exception))

    def test_the_timeout_defaults_to_the_setting(self):
        self.assertEqual(self.job("done").timeout, 1800.0)
        cfg = Config.load(env={"HOME": self.d, "KMP_JOB_TIMEOUT": "12"}, config_path="/nonexistent.ini")
        self.assertEqual(jobs.MagicJob(cfg, "rw", self.script).timeout, 12.0)


class Protocol(unittest.TestCase):
    def test_lines(self):
        self.assertEqual(jobs.parse_line("KMP_JOB_SCALE 0.004999999888241291\n")[0], "scale")
        self.assertEqual(jobs.parse_line("KMP_JOB check 12"), ("stage", ("check", 12)))
        self.assertEqual(jobs.parse_line("KMP_JOB listing"), ("stage", ("listing", 0)))
        self.assertEqual(jobs.parse_line("KMP_JOB_FAIL load x/y left the cell y loaded"),
                         ("fail", "load x/y left the cell y loaded"))
        self.assertEqual(jobs.parse_line("KMP_JOB_DONE 7"), ("done", 7))
        self.assertEqual(jobs.parse_line("KMP_JOBS 3"), (None, None))
        self.assertEqual(jobs.parse_line("Reading \"TOP\"."), (None, None))

    def test_batches_of_fifteen(self):
        self.assertEqual([len(b) for b in jobs.batches(range(31))], [15, 15, 1])
        self.assertEqual(jobs.batches([]), [])


class JobCache(_Fake):
    def test_the_key_covers_export_kind_options_tcl_and_version(self):
        k = jobs.job_cache_key("a" * 64, "drc", {"style": "drc(full)", "mode": "hierarchical"}, self.cfg)
        self.assertEqual(k, jobs.job_cache_key("a" * 64, "drc", {"mode": "hierarchical",
                                                                  "style": "drc(full)"}, self.cfg))
        self.assertRegex(k, "^[0-9a-f]{64}$")
        others = [jobs.job_cache_key("b" * 64, "drc", {"style": "drc(full)", "mode": "hierarchical"}, self.cfg),
                  jobs.job_cache_key("a" * 64, "rw", {"style": "drc(full)", "mode": "hierarchical"}, self.cfg),
                  jobs.job_cache_key("a" * 64, "drc", {"style": "drc(fast)", "mode": "hierarchical"}, self.cfg)]
        orig_tcl, orig_version = jobs.tcl_digest, jobs.__version__
        try:
            jobs.tcl_digest = lambda: "changed"
            others.append(jobs.job_cache_key("a" * 64, "drc", {"style": "drc(full)", "mode": "hierarchical"},
                                             self.cfg))
            jobs.tcl_digest = orig_tcl
            jobs.__version__ = "9.9.9"
            others.append(jobs.job_cache_key("a" * 64, "drc", {"style": "drc(full)", "mode": "hierarchical"},
                                             self.cfg))
        finally:
            jobs.tcl_digest, jobs.__version__ = orig_tcl, orig_version
        self.assertEqual(len(set(others + [k])), 6)
        # A change in the PDK's tech files changes the key.
        with open(os.path.join(os.path.dirname(self.rc), "sky130A.tech"), "w") as f:
            f.write("tech\n")
        jobs._digest_memo.clear()
        self.assertNotEqual(k, jobs.job_cache_key("a" * 64, "drc", {"style": "drc(full)",
                                                                     "mode": "hierarchical"}, self.cfg))

    def test_the_tcl_digest_covers_the_job_scripts_only(self):
        names = jobs.job_tcl_files()
        self.assertIn("kmp_job_common.tcl", names)
        for server in ("kmp_server.tcl", "kmp_common.tcl", "kmp_manifest.tcl"):
            self.assertNotIn(server, names)
        self.assertRegex(jobs.tcl_digest(), "^[0-9a-f]{64}$")

    def test_job_dir_for(self):
        self.assertEqual(jobs.job_dir_for(self.cfg, "extract", "k" * 64),
                         os.path.join(self.d, "cache", "jobs", "sky130A", "extract", "k" * 64))

    def test_cache_clear_and_prune_cover_the_jobs(self):
        root = self.cfg.cache_dir
        done = jobs.run_job(self.cfg, "drc", self.script, env={"KMP_FAKE": "done"})
        stale = jobs.run_job(self.cfg, "rw", self.script, env={"KMP_FAKE": "done"},
                             job_dir=jobs.job_dir_for(self.cfg, "rw", "k" * 64))
        meta_path = os.path.join(stale.dir, "job.json")
        with open(meta_path) as f:
            meta = json.load(f)
        meta["fingerprint"] = "old"
        with open(meta_path, "w") as f:
            json.dump(meta, f)
        other = os.path.join(root, "jobs", "gf180mcuD", "drc", "run-x")
        os.makedirs(other)
        with open(os.path.join(other, "job.json"), "w") as f:
            json.dump({"pdk": "gf180mcuD", "fingerprint": "old", "state": "done"}, f)
        running = self.job("hang", timeout=30).start()
        try:
            self.assertEqual(len(cache.job_dirs(root)), 4)
            st = cache.GdsCache(root, {"pdk": "sky130A"}, validate=None, server_code="x").stats()
            self.assertEqual(st["jobs"], 4)
            removed = cache.prune_jobs(root, {"sky130A": jobs.job_fingerprint(self.cfg)})
            self.assertEqual(removed, [stale.dir])
            self.assertTrue(os.path.isdir(done.dir) and os.path.isdir(other))
            cache.GdsCache(root, {"pdk": "sky130A"}, validate=None, server_code="x").clear()
            # The running job's directory stays; everything else goes.
            self.assertEqual(cache.job_dirs(root), [running.dir])
        finally:
            running.cancel()
        cache.clear_jobs(root)
        self.assertEqual(cache.job_dirs(root), [])


def _env_cfg(fake, **extra):
    env = {"HOME": fake.d, "KMP_MAGIC": fake.magic, "PATH": os.environ["PATH"],
           "PDK_ROOT": os.path.join(fake.d, "pdks"), "KMP_PDK": "sky130A",
           "KMP_CACHE_DIR": os.path.join(fake.d, "cache")}
    env.update(extra)
    return Config.load(env=env, config_path="/nonexistent.ini")


def _set_env(test, **values):
    """Set os.environ for one test (KMP_JOB_KEEP)."""
    old = {k: os.environ.get(k) for k in values}

    def restore():
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    test.addCleanup(restore)
    for k, v in values.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def _dead_pid():
    import subprocess
    p = subprocess.Popen(["true"])
    p.wait()
    return p.pid


class JobDirs(_Fake):
    """Where a job runs: the key's directory with the cache on, a tmp-*
    directory under <cache>/jobs with KMP_CACHE=0 or no_cache (the same),
    removed by release() and at the end of the process."""

    def setUp(self):
        _Fake.setUp(self)
        _set_env(self, KMP_JOB_KEEP=None)
        self.base = os.path.join(self.d, "cache", "jobs", "sky130A", "drc")

    def _system_tmp_jobs(self):
        t = tempfile.gettempdir()
        return set(n for n in os.listdir(t) if n.startswith("kmp-job-"))

    def test_kmp_cache_0_runs_under_the_cache_and_release_removes_it(self):
        before = self._system_tmp_jobs()
        cfg = _env_cfg(self, KMP_CACHE="0")
        r = jobs.run_job(cfg, "drc", self.script, env={"KMP_FAKE": "done"})
        self.assertTrue(r.ok, r.error)
        self.assertEqual(os.path.dirname(r.dir), self.base)
        self.assertTrue(os.path.basename(r.dir).startswith("tmp-"), r.dir)
        self.assertEqual(self._system_tmp_jobs(), before, "a job directory in the system's temp directory")
        self.assertEqual(jobs.release(r.dir), [r.dir])
        self.assertFalse(os.path.exists(r.dir))
        self.assertEqual(jobs.release(r.dir), [])

    def test_no_cache_and_kmp_cache_0_choose_the_same(self):
        on, off = self.cfg, _env_cfg(self, KMP_CACHE="0")
        key = "k" * 64
        self.assertTrue(jobs.use_cache(on, {}))
        self.assertTrue(jobs.use_cache(on, None))
        self.assertFalse(jobs.use_cache(on, {"no_cache": True}))
        self.assertFalse(jobs.use_cache(off, {}))
        self.assertEqual(jobs.job_dir(on, "drc", key, {}), (jobs.job_dir_for(on, "drc", key), True))
        made = []
        for cfg, opts in ((on, {"no_cache": True}), (off, {}), (off, {"no_cache": True})):
            d, cached = jobs.job_dir(cfg, "drc", key, opts)
            self.assertFalse(cached)
            self.assertEqual(os.path.dirname(d), self.base)
            self.assertTrue(os.path.basename(d).startswith("tmp-") and os.path.isdir(d))
            made.append(d)
        self.assertEqual(len(set(made)), 3)
        self.assertEqual(sorted(jobs.release(made)), sorted(made))

    def test_kmp_job_keep_keeps_it(self):
        d, _ = jobs.job_dir(self.cfg, "drc", "k" * 64, {"no_cache": True})
        _set_env(self, KMP_JOB_KEEP="1")
        self.assertEqual(jobs.release(d), [])
        self.assertTrue(os.path.isdir(d))
        _set_env(self, KMP_JOB_KEEP="0")
        self.assertEqual(jobs.release(d), [d])

    def test_release_takes_an_outcome_and_spares_key_dirs(self):
        a, _ = jobs.job_dir(self.cfg, "drc", "k" * 64, {"no_cache": True})
        b, _ = jobs.job_dir(self.cfg, "drc", "k" * 64, {"no_cache": True})
        key = jobs.job_dir_for(self.cfg, "drc", "k" * 64)
        os.makedirs(key)
        alien = os.path.join(self.base, "tmp-notmine")
        os.makedirs(alien)
        out = types.SimpleNamespace(files={"job_dir": a, "job": a, "jobs": [b, key, alien], "netlist": "x"})
        self.assertEqual(sorted(jobs.release(out)), sorted([a, b]))
        self.assertTrue(os.path.isdir(key) and os.path.isdir(alien))
        self.assertEqual(jobs.release({"job_dir": key}), [])

    def test_the_end_of_the_process_removes_what_is_left(self):
        import subprocess
        body = textwrap.dedent("""
            import sys
            sys.path.insert(0, sys.argv[1])
            from klayout_magic_pcells import jobs
            from klayout_magic_pcells.config import Config
            cfg = Config.load(env={"HOME": sys.argv[2], "KMP_MAGIC": sys.argv[3], "PATH": "/usr/bin:/bin",
                                   "PDK_ROOT": sys.argv[2] + "/pdks", "KMP_PDK": "sky130A",
                                   "KMP_CACHE_DIR": sys.argv[2] + "/cache", "KMP_CACHE": "0"},
                              config_path="/nonexistent.ini")
            r = jobs.run_job(cfg, "drc", sys.argv[4], env={"KMP_FAKE": "done"})
            print(r.dir)
        """)
        for keep in ("0", "1"):
            env = dict(os.environ, KMP_JOB_KEEP=keep)
            p = subprocess.run([sys.executable, "-c", body, os.path.join(REPO, "python"), self.d, self.magic,
                                self.script], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               universal_newlines=True, timeout=60)
            self.assertEqual(p.returncode, 0, p.stderr)
            d = p.stdout.strip().splitlines()[-1]
            self.assertTrue(d.startswith(self.base + os.sep), d)
            self.assertEqual(os.path.isdir(d), keep == "1", "KMP_JOB_KEEP=%s: %s" % (keep, d))

    def test_an_unwritable_cache_fails_the_job_instead_of_using_tmp(self):
        before = self._system_tmp_jobs()
        blocker = os.path.join(self.d, "file")
        with open(blocker, "w") as f:
            f.write("not a directory")
        cfg = _env_cfg(self, KMP_CACHE="0", KMP_CACHE_DIR=blocker)
        with self.assertRaises(jobs.JobError) as cm:
            jobs.run_job(cfg, "drc", self.script, env={"KMP_FAKE": "done"})
        self.assertIn("KMP_CACHE_DIR", str(cm.exception))
        self.assertEqual(self._system_tmp_jobs(), before)

    def _meta(self, d, **meta):
        os.makedirs(d, exist_ok=True)
        m = {"pdk": "sky130A", "fingerprint": jobs.job_fingerprint(self.cfg), "state": "done",
             "owner_pid": os.getpid()}
        m.update(meta)
        with open(os.path.join(d, "job.json"), "w") as f:
            json.dump(m, f)
        return d

    def test_prune_and_clear_remove_stale_tmp_dirs(self):
        root = self.cfg.cache_dir
        dead = _dead_pid()
        stale = self._meta(os.path.join(self.base, "tmp-stale"), owner_pid=dead)
        legacy = self._meta(os.path.join(self.base, "run-legacy"), owner_pid=dead)
        live = self._meta(os.path.join(self.base, "tmp-live"), fingerprint="old")
        keyed = self._meta(jobs.job_dir_for(self.cfg, "drc", "k" * 64), owner_pid=dead)
        other = self._meta(os.path.join(root, "jobs", "gf180mcuD", "drc", "tmp-other"), pdk="gf180mcuD",
                           owner_pid=dead)
        removed = cache.prune_jobs(root, {"sky130A": jobs.job_fingerprint(self.cfg)})
        self.assertEqual(sorted(removed), sorted([stale, legacy]))
        # A live session's tmp-* directory is its own; a current key's stays;
        # another PDK's is left to a prune of that PDK.
        self.assertTrue(all(os.path.isdir(d) for d in (live, keyed, other)))
        running = self.job("hang", timeout=30).start()
        try:
            cache.clear_jobs(root)
            self.assertEqual(cache.job_dirs(root), [running.dir])
        finally:
            running.cancel()

    def _lvs_dir(self, key_dir, owner_pid):
        d = tempfile.mkdtemp(prefix="lvs-", dir=key_dir)
        if owner_pid is not False:
            with open(os.path.join(d, cache.OWNER_FILE), "w") as f:
                json.dump({"owner_pid": owner_pid}, f)
        return d

    def test_an_lvs_folder_goes_with_release_and_prune_removes_leftovers(self):
        # Each LVS on a cached extraction gets an lvs-<random>/ folder in the key's
        # directory; release() removes this process's, prune those a finished
        # process left (design-0.6.md 2.3).
        root = self.cfg.cache_dir
        key = self._meta(jobs.job_dir_for(self.cfg, "extract", "k" * 64))
        mine = jobs.track(self._lvs_dir(key, os.getpid()))
        out = types.SimpleNamespace(files={"job_dir": key, "lvs_dir": mine, "report": os.path.join(mine, "lvs.out")})
        _set_env(self, KMP_JOB_KEEP="1")
        self.assertEqual(jobs.release(out), [])
        _set_env(self, KMP_JOB_KEEP=None)
        self.assertEqual(jobs.release(out), [mine])
        self.assertFalse(os.path.exists(mine))
        self.assertTrue(os.path.isdir(key))
        left = self._lvs_dir(key, _dead_pid())
        live = self._lvs_dir(key, os.getpid())
        unowned = self._lvs_dir(key, False)
        self.assertEqual(cache.lvs_leftovers(key), [left])
        removed = cache.prune_jobs(root, {"sky130A": jobs.job_fingerprint(self.cfg)})
        self.assertEqual(removed, [left])
        self.assertTrue(os.path.isdir(live) and os.path.isdir(unowned) and os.path.isdir(key))
        # One without an owner file goes once it is older than the age.
        self.assertEqual(cache.prune_jobs(root, {"sky130A": jobs.job_fingerprint(self.cfg)}, age=-1), [unowned])

    def test_stats_counts_the_jobs_of_the_pdk_asked_for(self):
        root = self.cfg.cache_dir
        self._meta(jobs.job_dir_for(self.cfg, "drc", "k" * 64))
        self._meta(jobs.job_dir_for(self.cfg, "rw", "k" * 64))
        self._meta(os.path.join(root, "jobs", "gf180mcuD", "drc", "k" * 64), pdk="gf180mcuD")
        c = cache.GdsCache(root, {"pdk": "sky130A"}, validate=None, server_code="x")
        self.assertEqual(c.stats()["jobs"], 3)
        self.assertEqual(c.stats(pdks=["sky130A"])["jobs"], 2)
        self.assertEqual(c.stats(pdks=["gf180mcuD"])["jobs"], 1)
        self.assertEqual(c.stats(pdks=["ihp-sg13g2"])["jobs"], 0)


# -- the job subcommands (argument parsing, the --cell check) -------------------

def run_cli(argv, data=None):
    from klayout_magic_pcells import __main__ as cli
    out, err = io.StringIO(), io.StringIO()
    old = cli._load_pdk_data
    seen = {}

    def fake_data(pdk):
        seen["pdk"] = pdk
        return data
    cli._load_pdk_data = fake_data
    try:
        with redirect_stdout(out), redirect_stderr(err):
            try:
                rc = cli.main(argv)
            except SystemExit as e:
                rc = e.code
    finally:
        cli._load_pdk_data = old
    return rc, out.getvalue() + err.getvalue(), seen


@needs_klayout
class JobCommands(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="kmp-cli-")
        for name, tops in (("two.gds", ("A", "B")), ("one.gds", ())):
            ly = db.Layout()
            ly.dbu = 0.001
            cells = []
            for n in ("A", "B"):
                c = ly.create_cell(n)
                c.shapes(ly.layer(68, 20)).insert(db.DBox(0, 0, 1, 1))
                cells.append(c)
            if not tops:
                top = ly.create_cell("TOP")
                for i, c in enumerate(cells):
                    top.insert(db.DCellInstArray(c.cell_index(), db.DTrans(db.DVector(5 * i, 0))))
            ly.write(os.path.join(self.d, name))
        self.two_tops = os.path.join(self.d, "two.gds")
        self.one_top = os.path.join(self.d, "one.gds")
        self.env = dict(os.environ)
        os.environ["KMP_PDKS"] = "sky130A"
        os.environ["KMP_PDK"] = "sky130A"

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.env)
        shutil.rmtree(self.d, ignore_errors=True)

    def test_a_missing_cell_exits_2(self):
        rc, text, _ = run_cli(["drc", self.one_top, "--cell", "TOP", "--cell", "nope"])
        self.assertEqual(rc, 2)
        self.assertIn("cell nope is not in %s" % self.one_top, text)
        rc, text, _ = run_cli(["ports", self.one_top, "--cell", "a.b"])
        self.assertEqual(rc, 2)
        self.assertIn("cell a.b is not in", text)

    def test_several_top_cells_need_cell(self):
        rc, text, _ = run_cli(["layers", self.two_tops])
        self.assertEqual(rc, 2)
        self.assertIn("A, B", text)
        self.assertIn("--cell", text)

    def test_a_missing_file_exits_2(self):
        rc, text, _ = run_cli(["extract", os.path.join(self.d, "none.gds")])
        self.assertEqual(rc, 2)
        self.assertIn("none.gds", text)

    def test_commands_not_built_yet(self):
        from klayout_magic_pcells import __main__ as cli
        import importlib.util
        for cmd, extra in (("drc", []), ("extract", []), ("lvs", ["--schematic", "x.spice"]),
                           ("layers", []), ("ports", [])):
            if importlib.util.find_spec("klayout_magic_pcells." + cli.FEATURES[cmd]) is not None:
                continue  # built by now
            rc, text, seen = run_cli([cmd, self.one_top] + extra)
            self.assertEqual(rc, 2, text)
            self.assertIn("%s: not built yet" % cmd, text)
            self.assertEqual(seen["pdk"], "sky130A")

    def test_the_context_a_feature_gets(self):
        from klayout_magic_pcells import __main__ as cli
        got = {}

        def fake_feature(args, ctx):
            got["args"], got["ctx"] = args, ctx
            return 1
        old = cli._feature_main
        cli._feature_main = lambda cmd: fake_feature
        try:
            rc, text, _ = run_cli(["drc", self.one_top, "--cell", "A", "--cell", "TOP", "--box", "0,0,2,1.5",
                                   "--mode", "flat"], data="DATA")
        finally:
            cli._feature_main = old
        self.assertEqual(rc, 1, text)
        ctx, args = got["ctx"], got["args"]
        self.assertEqual([c.name for c in ctx.cells], ["A", "TOP"])
        self.assertEqual((ctx.pdk, ctx.file, ctx.data, ctx.cfg.pdk), ("sky130A", self.one_top, "DATA", "sky130A"))
        self.assertIn("KMP_PDKS", ctx.pdk_reason)
        self.assertEqual(args.box, (0.0, 0.0, 2.0, 1.5))
        self.assertEqual((args.mode, args.style), ("flat", "drc(full)"))
        rc, text, _ = run_cli(["drc", self.one_top, "--box", "2,0,1,1"])
        self.assertEqual(rc, 2)
        # A negative first number gets past argparse in both spellings
        # ("--box -0.592,..." and "--box=-0.592,...").
        cli._feature_main = lambda cmd: fake_feature
        try:
            for argv, want in ((["--box", "-0.592,0,1.592,1.5"], (-0.592, 0.0, 1.592, 1.5)),
                               (["--box=-0.592,0,1.592,1.5"], (-0.592, 0.0, 1.592, 1.5)),
                               (["--box", "-1,-2,-0.5,-0.25", "--cell", "TOP"], (-1.0, -2.0, -0.5, -0.25))):
                rc, text, _ = run_cli(["drc", self.one_top] + argv)
                self.assertEqual(rc, 1, text)
                self.assertEqual(got["args"].box, want)
        finally:
            cli._feature_main = old
        rc, text, _ = run_cli(["drc", self.one_top, "--mode", "per-cell"])
        self.assertEqual(rc, 2)


# -- the feature tasks and the extract command on the fake Magic ------------------

def _inverter_file(d, name="inv", text=True):
    """A one-cell sky130A layout: a met1 box with a text "A" over it."""
    ly = db.Layout()
    ly.dbu = 0.001
    top = ly.create_cell(name)
    top.shapes(ly.layer(68, 20)).insert(db.DBox(0, 0, 2, 0.5))
    if text:
        top.shapes(ly.layer(68, 5)).insert(db.DText("A", db.DTrans(db.DVector(1, 0.25))))
    path = os.path.join(d, name + ".gds")
    ly.write(path)
    return path


def _load(path):
    from klayout_magic_pcells import export
    ly = export.load_layout(path)
    return ly, ly.top_cells()[0]


@needs_klayout
class FeatureJobDirs(_Fake):
    """layers, ports --magic and extract: the key's directory with the cache
    on, a tmp-* one with no_cache or KMP_CACHE=0; "job_dir" in
    Outcome.files ("job" too, for one version); "Job/failed" on failure."""

    def setUp(self):
        _Fake.setUp(self)
        from klayout_magic_pcells import pdkdata
        _set_env(self, KMP_JOB_KEEP=None, KMP_FAKE=None)
        self.data = pdkdata.load("sky130A")
        self.ly, self.top = _load(_inverter_file(self.d))
        self.rw = os.path.join(self.d, "cache", "jobs", "sky130A", "rw")

    def _is_tmp(self, d, base):
        return os.path.dirname(d) == base and os.path.basename(d).startswith("tmp-") and os.path.isdir(d)

    def test_layers(self):
        from klayout_magic_pcells import layercheck
        t1 = layercheck.prepare(self.ly, self.top, self.cfg, self.data, {})
        o1 = t1.wait()
        self.assertNotEqual(o1.status, 2, o1.summary)
        self.assertFalse(t1.cached)
        jd = o1.files["job_dir"]
        self.assertEqual(o1.files["job"], jd)
        self.assertEqual(os.path.dirname(jd), self.rw)
        self.assertFalse(os.path.basename(jd).startswith("tmp-"))
        t2 = layercheck.prepare(self.ly, self.top, self.cfg, self.data, {})
        o2 = t2.wait()
        self.assertTrue(t2.cached)
        self.assertEqual(o2.files["job_dir"], jd)
        self.assertEqual(jobs.release(o2), [])
        self.assertTrue(os.path.isdir(jd))
        for cfg, opts in ((self.cfg, {"no_cache": True}), (_env_cfg(self, KMP_CACHE="0"), {})):
            t = layercheck.prepare(self.ly, self.top, cfg, self.data, opts)
            o = t.wait()
            self.assertNotEqual(o.status, 2, o.summary)
            self.assertFalse(t.cached)
            self.assertTrue(self._is_tmp(o.files["job_dir"], self.rw), o.files)
            self.assertEqual(o.files["job"], o.files["job_dir"])
            self.assertEqual(o.summary, o1.summary)
            self.assertEqual(jobs.release(o), [o.files["job_dir"]])
            self.assertFalse(os.path.exists(o.files["job_dir"]))
        self.assertTrue(os.path.isdir(jd), "a run without the cache touched the key's directory")

    def test_layers_and_ports_failures(self):
        from klayout_magic_pcells import layercheck, portcheck
        _set_env(self, KMP_FAKE="fail")
        for name, task in (("layers", layercheck.prepare(self.ly, self.top, self.cfg, self.data, {"no_cache": True})),
                           ("ports", portcheck.prepare(self.ly, self.top, self.cfg, self.data,
                                                       {"magic": True, "no_cache": True}))):
            with self.subTest(check=name):
                o = task.wait()
                self.assertEqual(o.status, 2, o.summary)
                self.assertTrue(o.summary.startswith(name + ": "), o.summary)
                self.assertEqual(o.rdb.count("Job/failed"), 1)
                self.assertEqual(o.rdb.count(("Job failed",)), 0)
                self.assertTrue(self._is_tmp(o.files["job_dir"], self.rw), o.files)
                self.assertEqual(o.files["job"], o.files["job_dir"])
                self.assertEqual(jobs.release(o), [o.files["job_dir"]])

    def test_ports_magic(self):
        from klayout_magic_pcells import portcheck
        o = portcheck.prepare(self.ly, self.top, self.cfg, self.data, {"magic": True, "no_cache": True}).wait()
        self.assertNotEqual(o.status, 2, o.summary)
        self.assertEqual(o.magic_ports, ["A", "Y"])
        self.assertTrue(self._is_tmp(o.files["job_dir"], self.rw), o.files)
        self.assertEqual(o.files["job"], o.files["job_dir"])
        self.assertTrue(os.path.isfile(o.files["spice"]))

    def test_extract(self):
        from klayout_magic_pcells import lvsjob
        base = os.path.join(self.d, "cache", "jobs", "sky130A", "extract")
        o1 = lvsjob.prepare(self.ly, self.top, self.cfg, self.data, {"cmd": "extract"}).start().wait()
        self.assertEqual(o1.status, 0, o1.summary)
        # Magic prints "Calma reading is not undoable" on every run: not an item.
        self.assertEqual(o1.rdb.count("Magic said"), 0)
        self.assertEqual(o1.headline, "Magic extracted inv (netlist only).")
        key_dir = o1.files["job_dir"]
        self.assertEqual(os.path.dirname(key_dir), base)
        self.assertFalse(os.path.basename(key_dir).startswith("tmp-"))
        mtime = os.path.getmtime(os.path.join(key_dir, "job.json"))
        for cfg, opts in ((self.cfg, {"cmd": "extract", "no_cache": True}),
                          (_env_cfg(self, KMP_CACHE="0"), {"cmd": "extract"})):
            t = lvsjob.prepare(self.ly, self.top, cfg, self.data, opts)
            o = t.start().wait()
            self.assertEqual(o.status, 0, o.summary)
            self.assertNotEqual(t.stage, ("cached", 0))
            self.assertTrue(self._is_tmp(o.files["job_dir"], base), o.files)
            self.assertTrue(os.path.isfile(o.files["netlist"]))
            self.assertEqual(jobs.release(o), [o.files["job_dir"]])
        # --no-cache no longer empties the key's directory and runs there.
        self.assertEqual(os.path.getmtime(os.path.join(key_dir, "job.json")), mtime)
        t = lvsjob.prepare(self.ly, self.top, self.cfg, self.data, {"cmd": "extract"})
        t.start().wait()
        self.assertEqual(t.stage, ("cached", 0))


@needs_klayout
class ExtractCommand(_Fake):
    """The extract command's netlist file: <cell>.magic.spice beside the
    layout, never over a file the plugin did not write; -o writes where it
    is told; --rdb saves the report."""

    def setUp(self):
        _Fake.setUp(self)
        from klayout_magic_pcells import pdkdata
        self.data = pdkdata.load("sky130A")
        _set_env(self, HOME=self.d, KMP_MAGIC=self.magic, PDK_ROOT=os.path.join(self.d, "pdks"),
                 KMP_PDK="sky130A", KMP_PDKS="sky130A", KMP_CACHE_DIR=os.path.join(self.d, "cache"),
                 KMP_CACHE=None, KMP_JOB_KEEP=None, KMP_FAKE=None)
        self.work = os.path.join(self.d, "work")
        os.makedirs(self.work)
        self.gds = _inverter_file(self.work)
        self.schematic = os.path.join(self.work, "inv.spice")
        with open(self.schematic, "w") as f:
            f.write("* the user's schematic\n.subckt inv A Y\n.ends\n")

    def cli(self, *args):
        return run_cli(["extract", self.gds, "--pdk", "sky130A"] + list(args), data=self.data)

    def read(self, path):
        with open(path) as f:
            return f.read()

    def test_the_default_name_spares_the_schematic(self):
        from klayout_magic_pcells import lvsjob
        rc, text, _ = self.cli()
        self.assertEqual(rc, 0, text)
        self.assertEqual(self.read(self.schematic), "* the user's schematic\n.subckt inv A Y\n.ends\n")
        out = os.path.join(self.work, "inv.magic.spice")
        self.assertIn("netlist: %s" % out, text)
        body = self.read(out)
        self.assertTrue(body.startswith(lvsjob.NETLIST_HEADER), body)
        self.assertIn(".subckt inv", body)
        self.assertTrue(lvsjob.written_by_plugin(out))
        # A second run replaces the file the plugin wrote.
        rc, text, _ = self.cli()
        self.assertEqual(rc, 0, text)
        rc, text, _ = self.cli("--caps")
        self.assertEqual(rc, 0, text)
        self.assertTrue(lvsjob.written_by_plugin(os.path.join(self.work, "inv.magic.pex.spice")))

    def test_a_file_the_plugin_did_not_write_is_refused(self):
        out = os.path.join(self.work, "inv.magic.spice")
        for mine in ("* my own notes\n", ""):
            with open(out, "w") as f:
                f.write(mine)
            for extra in ((), ("--no-cache",)):
                rc, text, _ = self.cli(*extra)
                self.assertEqual(rc, 2, text)
                self.assertIn("%s exists and klayout_magic_pcells did not write it" % out, text)
                self.assertIn("-o", text)
                self.assertEqual(self.read(out), mine)
                # The summary names no file the user doesn't get, such as the job
                # directory's netlist.spice.
                first = text.splitlines()[0]
                self.assertEqual(first, "extract: Magic extracted inv (netlist only, sky130A).", text)
                self.assertNotIn("netlist.spice", text)

    def test_o_writes_where_it_is_told(self):
        from klayout_magic_pcells import lvsjob
        rc, text, _ = self.cli("-o", self.schematic)
        self.assertEqual(rc, 0, text)
        self.assertTrue(lvsjob.written_by_plugin(self.schematic))
        self.assertFalse(os.path.exists(os.path.join(self.work, "inv.magic.spice")))

    def test_rdb(self):
        from klayout_magic_pcells import markers
        path = os.path.join(self.work, "x.lyrdb")
        rc, text, _ = self.cli("--rdb", path, "--no-cache")
        self.assertEqual(rc, 0, text)
        self.assertTrue(os.path.isfile(path))
        os.remove(path)
        _set_env(self, KMP_FAKE="fail")
        rc, text, _ = self.cli("--rdb", path, "--no-cache")
        self.assertEqual(rc, 2, text)
        r = markers.load(path)
        names = [c.name() for c in r.each_category()]
        self.assertIn("Job", names)
        # The job directory was a tmp-* one, removed after the run.
        self.assertIn("is removed; KMP_JOB_KEEP=1 keeps it", text)
        base = os.path.join(self.d, "cache", "jobs", "sky130A", "extract")
        self.assertEqual([n for n in os.listdir(base) if n.startswith("tmp-")], [])


    def test_the_summary_names_the_file_written(self):
        # fix-misc: it named the job directory's netlist.spice, which a
        # --no-cache run removes.
        out = os.path.join(self.work, "inv.magic.spice")
        for extra in ((), ("--no-cache",)):
            rc, text, _ = self.cli(*extra)
            self.assertEqual(rc, 0, text)
            first = text.splitlines()[0]
            self.assertTrue(first.startswith("extract: Magic extracted inv"), text)
            self.assertIn(" into %s." % out, first)
            self.assertNotIn("netlist.spice", first)
        rc, text, _ = self.cli("-o", os.path.join(self.work, "x.spice"))
        self.assertIn(" into %s." % os.path.join(self.work, "x.spice"), text.splitlines()[0])

    def test_a_cell_magic_reads_nothing_in_is_a_finding(self):
        # extract gives the reads-nothing finding with status 1, as drc, layers
        # and ports --magic do, not a failed job with status 2.
        from klayout_magic_pcells import markers
        _set_env(self, KMP_FAKE="empty")
        rdb = os.path.join(self.work, "x.lyrdb")
        rc, text, _ = self.cli("--rdb", rdb)
        self.assertEqual(rc, 1, text)
        self.assertTrue(text.startswith("extract: Magic reads nothing in inv (sky130A), so there is no netlist."),
                        text)
        self.assertIn("Export/Magic reads nothing in this cell: Magic reads nothing in cell inv", text)
        self.assertNotIn("failed", text)
        self.assertFalse(os.path.exists(os.path.join(self.work, "inv.magic.spice")))
        cats = {c.name(): c for c in markers.load(rdb).each_category()}
        self.assertIn("Export", cats)
        self.assertNotIn("Job", cats)
        setup = os.path.join(self.d, "setup.tcl")
        with open(setup, "w") as f:
            f.write("# netgen setup\n")
        _set_env(self, KMP_NETGEN_SETUP_SKY130A=setup)
        js = os.path.join(self.work, "lvs.json")
        rc, text, _ = run_cli(["lvs", self.gds, "--pdk", "sky130A", "--schematic", self.schematic,
                               "--json", js, "--report", os.path.join(self.work, "lvs.txt")], data=self.data)
        self.assertEqual(rc, 1, text)
        self.assertIn("lvs: Magic reads nothing in inv (sky130A)", text)
        self.assertIn("The layout does not match.", text)
        with open(js) as f:
            doc = json.load(f)
        self.assertEqual(doc["status"], 1)
        self.assertFalse(doc["verdict"]["matched"])
        self.assertEqual([x["category"] for x in doc["findings"]], [markers.CAT_READS_NOTHING])
        self.assertFalse(os.path.exists(os.path.join(self.work, "lvs.txt")))

    def test_an_export_klayout_cannot_write_fails_the_task(self):
        from klayout_magic_pcells import lvsjob
        ly, top = _load(self.gds)
        old = lvsjob.export_cell

        def broken(*a, **k):
            raise RuntimeError("Cannot open file for writing: /x/in.gds\nmore")
        lvsjob.export_cell = broken
        try:
            out = lvsjob.prepare(ly, top, self.cfg, self.data, {"cmd": "extract"}).start().wait()
        finally:
            lvsjob.export_cell = old
        self.assertEqual(out.status, 2, out.summary)
        self.assertEqual(out.summary, "extract: cannot export cell inv: Cannot open file for writing: /x/in.gds")

    def test_lvs_o_saves_the_report_when_the_job_fails(self):
        from klayout_magic_pcells import markers
        setup = os.path.join(self.d, "setup.tcl")
        with open(setup, "w") as f:
            f.write("# netgen setup\n")
        _set_env(self, KMP_FAKE="fail", KMP_NETGEN_SETUP_SKY130A=setup)
        path = os.path.join(self.work, "lvs.lyrdb")
        rc, text, _ = run_cli(["lvs", self.gds, "--pdk", "sky130A", "--schematic", self.schematic,
                               "-o", path], data=self.data)
        self.assertEqual(rc, 2, text)
        self.assertTrue(os.path.isfile(path), text)
        r = markers.load(path)
        self.assertIn("Job", [c.name() for c in r.each_category()])


@needs_klayout
class LvsTaskCancel(_Fake):
    """lvsjob.Task.cancel() sets the outcome, as drcjob's and layercheck's do
    (design-0.6.md 2.4)."""

    def setUp(self):
        _Fake.setUp(self)
        from klayout_magic_pcells import pdkdata
        _set_env(self, KMP_JOB_KEEP=None, KMP_FAKE="cancel")
        self.data = pdkdata.load("sky130A")
        self.ly, self.top = _load(_inverter_file(self.d))

    def test_cancel(self):
        from klayout_magic_pcells import lvsjob
        t = lvsjob.prepare(self.ly, self.top, self.cfg, self.data, {"cmd": "extract", "no_cache": True})
        t.start()
        for _ in range(100):
            if t.job.stage == ("checking", 3):
                break
            self.assertIsNone(t.poll())
            time.sleep(0.05)
        pid = t.job.pid
        t.cancel()
        # Set by cancel() itself, before any poll().
        self.assertIsNotNone(t._outcome, "cancel() set no outcome")
        out = t.poll()
        self.assertIs(out, t._outcome)
        self.assertEqual(out.status, 2)
        self.assertIn("cancelled", out.summary)
        self.assertEqual(out.rdb.count("Job/failed"), 1)
        self.assertIs(t.wait(), out)
        self.assertEqual(out.files["job_dir"], t.job_dir)
        for _ in range(50):
            if not alive(pid):
                break
            time.sleep(0.05)
        self.assertFalse(alive(pid))
        self.assertEqual(jobs.release(out), [out.files["job_dir"]])
        # Before start(), too.
        t2 = lvsjob.prepare(self.ly, self.top, self.cfg, self.data, {"cmd": "extract", "no_cache": True})
        t2.cancel()
        self.assertEqual(t2.poll().status, 2)


@needs_klayout
class Texts(unittest.TestCase):
    def test_has_texts_looks_down_the_hierarchy(self):
        from klayout_magic_pcells import lvsjob
        ly = db.Layout()
        ly.dbu = 0.001
        child = ly.create_cell("CHILD")
        child.shapes(ly.layer(68, 5)).insert(db.DText("A", db.DTrans()))
        parent = ly.create_cell("PARENT")
        parent.insert(db.DCellInstArray(child.cell_index(), db.DTrans()))
        bare = ly.create_cell("BARE")
        bare.shapes(ly.layer(68, 20)).insert(db.DBox(0, 0, 1, 1))
        self.assertTrue(lvsjob.has_texts(child))
        self.assertTrue(lvsjob.has_texts(parent))
        self.assertFalse(lvsjob.has_texts(bare))


if __name__ == "__main__":
    unittest.main()
