"""Magic extraction and netgen LVS of a KLayout cell: the ``extract`` and
``lvs`` commands, and the GUI's "Extract with Magic" and "LVS with netgen".

``prepare`` exports the cell (export.py) and returns a Task; the Task runs
one Magic job (``tcl/kmp_extract.tcl``: hierarchical reading, ``extract
all``, ``ext2spice``) and, for LVS, netgen with the PDK's setup file. The
job directory keeps the ``.ext`` files, the netlist and netgen's report; a
second run on the same export with the same options reuses it (the job
cache, keyed by ``jobs.job_cache_key``).

The markers (design-0.6.md 3.2) come from netgen's ``lvs.json`` at the places
the ``.ext`` files give, in µm from the job's ``[cif scale out]``
(design-0.6.md 6.5): a layout net netgen could not match is marked at its
``node`` point, on its shape where one is found; a device with a property
error at its ``device`` point; a layout pin without a partner at its port
box. Nets of subcells that netgen flattened are followed through the
``use`` transforms. With them go the export's findings and the read-back
findings (design-0.6.md 3.2): each placement of a PCell variant whose
device Magic's GDS reader does not keep (``data/readback-<pdk>.json``).

A cell Magic reads nothing in (every layer it draws is one Magic's reader
ignores or reads only to decide device types) is a finding, as in drc,
layers and ports --magic: "Export/Magic reads nothing in this cell",
status 1, and no netlist; for lvs the verdict is a mismatch.

An LVS run on a cached extraction gets a folder of its own in the key's
directory, ``lvs-<random>``, registered with ``jobs.track``: it goes when
the outcome has been read, as a tmp-* job directory does, unless
``KMP_JOB_KEEP=1``; ``cache prune`` removes those a process left behind.

Status: extract 0 when the netlist was written, 1 when a placed PCell
variant holds a device Magic's GDS reader does not keep (the read-back
list) or Magic reads nothing in the cell; lvs 0 only when netgen's final
result is a match with no property, port or pin error, else 1; 2 when the
input, Magic or netgen fails.
"""

import json
import os
import re
import shutil
import tempfile

from . import extfile, jobs, markers, netgen
from .export import ExportError, export_cell

SCRIPT = "kmp_extract.tcl"
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
NETLIST = "netlist.spice"
RESULT = "kmp_result.json"
REPORT = "lvs.out"

CAT_RESULT = "netgen/result"
CAT_LAYOUT_ONLY = "netgen/net only in the layout"
CAT_SCHEM_ONLY = "netgen/net only in the schematic"
CAT_NETS = "netgen/nets that differ"
CAT_DEVICES = "netgen/device mismatch"
CAT_PROPS = "netgen/property mismatch"
CAT_PINS = "netgen/pins"
CAT_READBACK = "Extraction/Magic's GDS reader does not keep this device"
CAT_UNPLACED = "Extraction/nets without a position"
CAT_PORTS_FROM_LABELS = "Extraction/every label made a port"
CAT_JOB = "Job/failed"

_VARIANT = re.compile(r"^(.+)__kmp_[0-9a-f]{8}(?:\$\d+)?$")
_DESCRIPTIONS = {
    CAT_RESULT: "netgen's final result and why the layout fails, as netgen printed it.",
    CAT_LAYOUT_ONLY: "Nets of Magic's netlist that netgen could not pair with a schematic net, "
                     "marked at the point Magic's .ext file gives for them.",
    CAT_SCHEM_ONLY: "Schematic nets that netgen could not pair with a layout net.",
    CAT_NETS: "Nets netgen paired by name whose devices and pins differ (fanout per device class).",
    CAT_DEVICES: "Devices netgen could not match, and device counts that differ.",
    CAT_PROPS: "Devices that match but whose properties (W, L, ...) differ beyond netgen's tolerance.",
    CAT_PINS: "Pins of the layout cell and the schematic subcircuit that netgen could not pair. Magic makes "
              "a port only from a text on the PDK's port layers (a label over a pin box); a text "
              "elsewhere names a net but is no pin. The ports command lists them.",
    CAT_READBACK: "PCell variants whose device Magic's GDS reader does not keep: Magic's own cell, "
                  "placed from its Devices menu, extracts as the device; the same cell read from GDS "
                  "does not (listed in data/readback-<pdk>.json).",
    CAT_UNPLACED: "Nets netgen named whose position the .ext files don't give.",
    CAT_PORTS_FROM_LABELS: "port makeall ran: every label became a port. Magic's own flow would not "
                           "have made these ports; the ports command shows which texts are not ports.",
    CAT_JOB: "The job failed; what Magic or netgen said.",
}

# Magic types in the .ext, to the layer roles their shapes are on.
_DIFF = re.compile(r"(dif|^n?p?sd|^ppd|^npd|tap|^nd|^pd)", re.I)


class Outcome:
    def __init__(self, status, rdb, summary, files=None, verdict=None, findings=None, headline=None):
        self.status = status
        self.rdb = rdb
        self.summary = summary
        self.headline = headline         # the GUI message's plain first line
        self.files = files or {}
        self.verdict = verdict
        self.findings = findings or []   # [{"category", "cell", "text", "box"}]


def lvs_headline(cell, subckt, schematic, matched, findings):
    """The first line of the GUI's LVS message, in plain words: match or
    not, and the report's markers per category."""
    against = "%s in %s" % (subckt, os.path.basename(schematic or ""))
    if matched:
        return "%s matches %s." % (cell, against)
    per = []
    for f in findings:
        cat = f["category"].split("/", 1)[-1]
        for i, (c, n) in enumerate(per):
            if c == cat:
                per[i] = (c, n + 1)
                break
        else:
            per.append((cat, 1))
    s = "%s does not match %s." % (cell, against)
    if per:
        s += " The report marks %s." % ", ".join("%s: %d" % cn for cn in per)
    return s


def readback(pdk):
    """{device: row} of ``data/readback-<pdk>.json``, or {}."""
    path = os.path.join(DATA_DIR, "readback-%s.json" % pdk)
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return {r["device"]: r for r in json.load(f).get("devices", [])}


def readback_text(row):
    if row.get("kind") == "values":
        return ("Magic's GDS reader changes this device's values; Magic's own cell extracts as %s, "
                "the cell read from GDS as %s" % (row["database"], row["gds"]))
    if row.get("gds", "none") == "none":
        return "Magic's GDS reader does not keep this device; Magic's own cell extracts as %s" % row["database"]
    return ("Magic's GDS reader does not keep this device; Magic's own cell extracts as %s, the cell "
            "read from GDS as %s" % (row["database"], row["gds"]))


def _generator(params):
    fn = getattr(markers, "recipe_generator", None)
    if fn is None:
        return ""
    try:
        return fn(params)
    except Exception:
        return ""


def command_line(options, file=None, cell=None, pdk=None):
    cmd = options.get("cmd", "lvs")
    parts = ["python3", "-m", "klayout_magic_pcells", cmd, file or "LAYOUT"]
    if pdk:
        parts += ["--pdk", pdk]
    if cell:
        parts += ["--cell", cell]
    if cmd == "lvs":
        parts += ["--schematic", options.get("schematic") or "SCH"]
        if options.get("schematic_cell"):
            parts += ["--schematic-cell", options["schematic_cell"]]
    elif options.get("caps"):
        parts.append("--caps")
    if options.get("flatglob"):
        parts.append("--flatglob")
    if options.get("ports_from_labels"):
        parts.append("--ports-from-labels")
    return " ".join(parts)


class _Cached:
    """A JobResult rebuilt from a finished job directory."""

    def __init__(self, jd, saved):
        self.ok = True
        self.returncode = 0
        self.dir = jd
        self.stdout = saved.get("stdout", [])
        self.stderr = saved.get("stderr", "")
        self.scale = saved.get("scale")
        self.stages = []
        self.elapsed = 0.0
        self.error = None
        self.cached = True


def _cached_result(jd):
    try:
        with open(os.path.join(jd, jobs.JOB_META if hasattr(jobs, "JOB_META") else "job.json")) as f:
            meta = json.load(f)
        with open(os.path.join(jd, RESULT)) as f:
            saved = json.load(f)
    except (OSError, ValueError):
        return None
    if meta.get("state") != "done" or not os.path.isfile(os.path.join(jd, NETLIST)) or not saved.get("scale"):
        return None
    return _Cached(jd, saved)


class Task:
    """One extraction (and netgen run). See the module's docstring."""

    def __init__(self, layout, cell, cfg, data, options):
        self.layout = layout
        self.cell = cell
        self.cfg = cfg
        self.data = data
        self.options = dict(options)
        self.cmd = self.options.get("cmd", "lvs")
        self.stage = None
        self.export = None
        self.job = None
        self.job_dir = None      # set by start(): the key's directory, or a tmp-* one
        self._key = None
        self._tmp = None
        self._result = None
        self._outcome = None
        self._failed = None      # (summary, detail) before any job
        self._lvsdir = None      # this run's netgen folder
        self.schematic_cell = None

    # -- set-up (prepare) --

    def _fail_early(self, summary):
        self._failed = summary

    def _prepare(self):
        o = self.options
        if self.cmd == "lvs":
            sch = o.get("schematic")
            if not sch or not os.path.isfile(sch):
                return self._fail_early("the schematic %s does not exist" % (sch or "(none given)"))
            if not os.path.isfile(self.cfg.netgen_setup):
                return self._fail_early("netgen's setup file for %s is missing: %s (set KMP_NETGEN_SETUP_<PDK>)"
                                        % (self.cfg.pdk, self.cfg.netgen_setup))
            try:
                names = netgen.subcircuits(sch)
            except OSError as e:
                return self._fail_early("cannot read the schematic %s: %s" % (sch, e))
            self._subckts = names
        self._tmp = tempfile.mkdtemp(prefix="kmp-extract-")
        gds = os.path.join(self._tmp, "in.gds")
        try:
            self.export = export_cell(self.layout, self.cell, gds, self.data)
        except ExportError as e:
            return self._fail_early(str(e))
        except RuntimeError as e:  # KLayout could not copy or write the cell
            name = getattr(self.cell, "name", self.cell)
            return self._fail_early("cannot export cell %s: %s" % (name, str(e).splitlines()[0] if str(e) else e))
        why = self.export.refusal()
        if why:
            return self._fail_early(why)
        if self.cmd == "lvs":
            want = o.get("schematic_cell")
            if want:
                if want not in self._subckts:
                    return self._fail_early("the schematic %s has no subcircuit %s (it has %s)"
                                            % (o["schematic"], want, ", ".join(self._subckts) or "none"))
                self.schematic_cell = want
            else:
                # By default the subcircuit named like the layout cell.
                for cand in (self.export.klayout_top, self.export.top):
                    if cand in self._subckts:
                        self.schematic_cell = cand
                        break
                if self.schematic_cell is None:
                    return self._fail_early(
                        "the schematic %s has no subcircuit %s; choose one with --schematic-cell (it has %s)"
                        % (o["schematic"], self.export.klayout_top, ", ".join(self._subckts) or "none"))
        opts = {"top": self.export.top, "caps": bool(o.get("caps")) and self.cmd == "extract",
                "flatglob": bool(o.get("flatglob")), "makeall": bool(o.get("ports_from_labels"))}
        self.job_options = opts
        self._key = jobs.job_cache_key(self.export.sha256, "extract", opts, self.cfg)
        return None

    # -- running --

    def start(self):
        if self._outcome is not None or self.job is not None or self._result is not None:
            return self
        if self._failed:
            self._finish_failed(self._failed)
            return self
        try:
            if self.options.get("job_dir"):
                self.job_dir = self.options["job_dir"]
                caching = jobs.use_cache(self.cfg, self.options)
            else:
                # The key's directory, or with KMP_CACHE=0 or no_cache a new tmp-* one.
                self.job_dir, caching = jobs.job_dir(self.cfg, "extract", self._key, self.options)
        except jobs.JobError as e:
            self._finish_failed("the extraction job could not start: %s" % e)
            return self
        hit = _cached_result(self.job_dir) if caching else None
        if hit is not None:
            self._result = hit
            self.stage = ("cached", 0)
            self._cleanup_tmp()
            return self
        env = {"KMP_TOP": self.export.top, "KMP_OUT": NETLIST,
               "KMP_CAPS": "1" if self.job_options["caps"] else "0",
               "KMP_FLATGLOB": "1" if self.job_options["flatglob"] else "0",
               "KMP_MAKEALL": "1" if self.job_options["makeall"] else "0"}
        try:
            self.job = jobs.MagicJob(self.cfg, "extract", SCRIPT, env=env,
                                     files={"in.gds": self.export.path}, job_dir=self.job_dir,
                                     required=(NETLIST, RESULT))
            self.job.start()
        except jobs.JobError as e:
            self._finish_failed("the extraction job could not start: %s" % e)
        self._cleanup_tmp()
        return self

    def _cleanup_tmp(self):
        if self._tmp:
            shutil.rmtree(self._tmp, ignore_errors=True)
            self._tmp = None

    def poll(self):
        if self._outcome is not None:
            return self._outcome
        if self._result is None:
            if self.job is None:
                self.start()
                if self._outcome is not None:
                    return self._outcome
            if self._result is None:
                r = self.job.poll()
                self.stage = self.job.stage
                if r is None:
                    return None
                self._took(r)
        return self._finish()

    def wait(self):
        if self._outcome is not None:
            return self._outcome
        if self._result is None:
            if self.job is None:
                self.start()
                if self._outcome is not None:
                    return self._outcome
            if self._result is None:
                self._took(self.job.wait())
        return self._finish()

    def _took(self, r):
        self._result = r
        # The job's files are where it ended up: the key's directory, or its
        # own tmp-* one when another job with the same key ended first.
        self.job_dir = r.dir

    def cancel(self):
        """Kill Magic; the outcome (status 2) says "cancelled", as drcjob's
        and layercheck's do."""
        if self._outcome is not None:
            return
        r = None
        if self.job is not None and self._result is None:
            self.job.cancel()
            r = self.job.poll()
            if r is not None:
                self._took(r)
        self._finish_failed("cancelled", r)

    # -- results --

    def _rdb(self):
        o = self.options
        cell = self.export.klayout_top if self.export else getattr(self.cell, "name", str(self.cell))
        what = "LVS with netgen" if self.cmd == "lvs" else (
            "Extraction with parasitic capacitance" if o.get("caps") else "Extraction (netlist only)")
        desc = "%s of %s, PDK %s. Magic reads the exported layout with its hierarchy (gds read; extract all " \
               "per cell; ext2spice%s)." % (what, cell, self.cfg.pdk, "" if self.cmd == "lvs" else
                                            (" with cthresh 0" if o.get("caps") else " lvs"))
        if self.cmd == "lvs":
            desc += " netgen with %s against %s (subcircuit %s)." % (
                self.cfg.netgen_setup, o.get("schematic"), self.schematic_cell)
        desc += " Command: " + command_line(o, o.get("file"), cell, self.cfg.pdk)
        params = {"cmd": self.cmd, "file": o.get("file") or "", "cell": cell, "pdk": self.cfg.pdk}
        for k in ("schematic", "schematic_cell", "caps", "flatglob", "ports_from_labels"):
            if o.get(k):
                params[k] = o[k]
        name = "Magic LVS" if self.cmd == "lvs" else "Magic extraction"
        return markers.Rdb(name, desc, _generator(params), cell)

    def _finish_failed(self, summary, result=None, rdb=None):
        rdb = rdb or self._rdb()
        rdb.info(rdb.category(CAT_JOB, _DESCRIPTIONS[CAT_JOB]), summary)
        if result is not None:
            markers.add_magic_said(rdb, _magic_lines(result))
        files = {"job_dir": self.job_dir} if self.job_dir else {}
        if self._lvsdir:
            files["lvs_dir"] = self._lvsdir
        self._outcome = Outcome(2, rdb, "%s: %s" % (self.cmd, summary), files)
        self._cleanup_tmp()
        return self._outcome

    def _finish(self):
        if self._outcome is not None:
            return self._outcome
        r = self._result
        rdb = self._rdb()
        findings = []
        n_export = markers.add_export_findings(rdb, self.export) if self.export is not None else 0
        if not r.ok and markers.empty_cell_error(r.error, self.export.top):
            return self._reads_nothing(r, rdb, findings)
        if not r.ok:
            return self._finish_failed("Magic's extraction failed: %s" % r.error, r, rdb)
        if not getattr(r, "cached", False):
            try:
                with open(os.path.join(r.dir, RESULT), "w") as f:
                    json.dump({"scale": r.scale, "stdout": r.stdout, "stderr": r.stderr}, f)
            except OSError:
                pass
        markers.add_magic_said(rdb, _magic_lines(r))
        try:
            ext = extfile.Extraction.from_dir(r.dir, self.export.top, r.scale)
        except (extfile.ExtError, OSError) as e:
            return self._finish_failed("cannot read Magic's .ext files: %s" % e, r, rdb)
        netlist = os.path.join(r.dir, NETLIST)
        files = {"job_dir": r.dir, "netlist": netlist, "export": os.path.join(r.dir, "in.gds")}
        n_readback = self._mark_readback(rdb, findings)
        if self.job_options.get("makeall"):
            rdb.info(rdb.category(CAT_PORTS_FROM_LABELS, _DESCRIPTIONS[CAT_PORTS_FROM_LABELS]),
                     "port makeall made %d ports in %s" % (len(ext.ports()), self.export.top), info=True)
        self.ext = ext
        if self.cmd == "extract":
            # Only devices the netlist misses count as findings of the
            # extraction; the export's items (npc 95/20, which Magic reads
            # nowhere, is on every sky130A layout) are information beside it.
            status = 1 if n_readback else 0
            kind = "with parasitic capacitance" if self.job_options["caps"] else "netlist only"
            summary = "extract: Magic extracted %s (%s, %s) into %s." % (
                self.export.klayout_top, kind, self.cfg.pdk, netlist)
            # name_netlist() puts the file the netlist is written to here.
            if n_readback:
                summary += (" %d placed PCell variant%s hold a device Magic's GDS reader does not keep."
                            % (n_readback, "" if n_readback == 1 else "s"))
            if n_export:
                summary += " The report has %d item%s about the export." % (n_export, "" if n_export == 1 else "s")
            head = "Magic extracted %s (%s)." % (self.export.klayout_top, kind)
            if n_readback:
                head += (" %d placed PCell variant%s hold a device that Magic's GDS reader does not keep."
                         % (n_readback, "" if n_readback == 1 else "s"))
            self._outcome = Outcome(status, rdb, summary, files, findings=findings, headline=head)
            return self._outcome
        return self._run_netgen(r, ext, rdb, files, findings)

    def _reads_nothing(self, r, rdb, findings):
        """Magic's reader kept none of the cell's shapes: the finding under
        "Export/Magic reads nothing in this cell", status 1, no netlist; for
        lvs a mismatch. The failed job is not cached."""
        name = self.export.klayout_top
        text = markers.add_reads_nothing(rdb, self.export, cell_name=name, data=self.data)
        markers.add_magic_said(rdb, _magic_lines(r))
        b = getattr(self.export, "bbox", None)
        box = None
        if b is not None and not b.empty():
            box = [round(b.left, 4), round(b.bottom, 4), round(b.right, 4), round(b.top, 4)]
        findings.append({"category": markers.CAT_READS_NOTHING, "cell": name, "text": text, "box": box})
        files = {"job_dir": r.dir, "export": os.path.join(r.dir, "in.gds")}
        if self.cmd == "extract":
            summary = "extract: Magic reads nothing in %s (%s), so there is no netlist." % (name, self.cfg.pdk)
            self._outcome = Outcome(1, rdb, summary, files, findings=findings,
                                    headline="Magic reads nothing in %s, so there is no netlist." % name)
            return self._outcome
        v = netgen.Verdict()
        v.complete = True
        v.final = "netgen did not run: Magic reads nothing in %s" % name
        rdb.info(rdb.category(CAT_RESULT, _DESCRIPTIONS[CAT_RESULT]), v.final)
        summary = ("lvs: Magic reads nothing in %s (%s), so there is no netlist to compare with %s in %s. "
                   "The layout does not match." % (name, self.cfg.pdk, self.schematic_cell,
                                                   self.options["schematic"]))
        self._outcome = Outcome(1, rdb, summary, files, verdict=v, findings=findings,
                                headline="Magic reads nothing in %s, so there is no netlist to compare; "
                                         "the layout does not match." % name)
        return self._outcome

    def _run_netgen(self, r, ext, rdb, files, findings):
        if os.path.basename(r.dir).startswith(jobs.TMP_PREFIX):
            # This run's own directory.
            lvsdir = os.path.join(r.dir, "lvs")
            shutil.rmtree(lvsdir, ignore_errors=True)
            os.makedirs(lvsdir, exist_ok=True)
        else:
            # A key's directory is shared and written once: each netgen run gets a folder of its
            # own in it, so that two LVS runs on one extraction (another schematic, or the GUI and
            # the command line at once) never remove or overwrite each other's report. The folder
            # goes with jobs.release(), and cache prune finds it by its owner file if this
            # process ends first.
            try:
                lvsdir = jobs.track(tempfile.mkdtemp(prefix="lvs-", dir=r.dir))
                with open(os.path.join(lvsdir, "kmp_owner.json"), "w", encoding="utf-8") as f:
                    json.dump({"owner_pid": os.getpid()}, f)
            except OSError as e:
                return self._finish_failed("cannot make a folder for netgen in %s: %s" % (r.dir, e), r, rdb)
            self._lvsdir = lvsdir
            files["lvs_dir"] = lvsdir
        report = os.path.join(lvsdir, REPORT)
        sch = os.path.abspath(self.options["schematic"])
        if " " in sch:
            copy = os.path.join(lvsdir, "schematic.spice")
            shutil.copyfile(sch, copy)
            sch = copy
        netlist = files["netlist"]
        self.stage = ("netgen", 0)
        try:
            res = netgen.run(self.cfg, netlist, self.export.top, sch, self.schematic_cell, report, cwd=lvsdir)
        except netgen.NetgenError as e:
            return self._finish_failed("netgen failed: %s" % e, r, rdb)
        files.update({"report": report, "json": res.json, "netgen_log": os.path.join(lvsdir, "netgen.log")})
        try:
            with open(files["netgen_log"], "w", encoding="utf-8") as f:
                f.write(res.output)
        except OSError:
            pass
        v = res.verdict
        if not v.complete:
            return self._finish_failed("netgen gave no final result; see %s" % report, r, rdb)
        cat = rdb.category(CAT_RESULT, _DESCRIPTIONS[CAT_RESULT])
        # On a match the result items are information: nothing in the report is to be fixed.
        ok = bool(v.matched)
        rdb.info(cat, "Final result: %s" % v.final, info=ok)
        for reason in v.reasons:
            rdb.info(cat, reason, info=ok)
        if v.symmetries:
            rdb.info(cat, "netgen matched with %d symmetries: a match" % v.symmetries, info=ok)
        if self.job_options.get("makeall"):
            rdb.info(cat, "--ports-from-labels: every label was made a port, which Magic's own flow "
                          "would not do; see the ports check", info=ok)
        spice = extfile.spice_devices(netlist)
        for c in res.circuits:
            self._mark_circuit(rdb, ext, spice, c, findings)
        if v.pin_errors and not any(f["category"] == CAT_PINS for f in findings):
            self._add(rdb, findings, CAT_PINS, None, None, "netgen: %s" % v.final)
        status = 0 if v.matched else 1
        sch_label = "%s in %s" % (self.schematic_cell, self.options["schematic"])
        summary = "lvs: %s against %s (%s): netgen: %s" % (self.export.klayout_top, sch_label, self.cfg.pdk, v.final)
        extra = [x for x in v.reasons if not x.endswith(v.final)]
        if extra:
            summary += " " + " ".join(x if x.endswith(".") else x + "." for x in extra)
        summary += " " + ("The layout matches." if v.matched else "The layout does not match.")
        n_marks = sum(1 for f in findings if f["category"].startswith("netgen/"))
        if n_marks:
            summary += " %d marker%s in the report." % (n_marks, "" if n_marks == 1 else "s")
        head = lvs_headline(self.export.klayout_top, self.schematic_cell, self.options["schematic"], v.matched,
                            findings)
        self._outcome = Outcome(status, rdb, summary, files, verdict=v, findings=findings, headline=head)
        return self._outcome

    # -- markers --

    def _kl_name(self, file_name):
        return self.export.klayout_name(file_name) if self.export else file_name

    def _add(self, rdb, findings, cat, cell, shape, text):
        cell = cell or self.export.klayout_top
        c = rdb.category(cat, _DESCRIPTIONS.get(cat, ""))
        rdb.item(c, cell, shape, text)
        box = None
        if shape is not None:
            b = shape.bbox() if hasattr(shape, "bbox") else shape
            box = [round(b.left, 4), round(b.bottom, 4), round(b.right, 4), round(b.top, 4)]
        findings.append({"category": cat, "cell": cell, "text": text, "box": box})

    def _net_shape(self, cell_name, point, mtype):
        """The polygon of the net's shape under ``point`` (µm, in that cell),
        on the layers Magic's type ``mtype`` is drawn on; else a small box."""
        from ._kl import db
        x, y = point
        small = db.DBox(x - 0.01, y - 0.01, x + 0.01, y + 0.01)
        cell = self.layout.cell(cell_name) if isinstance(cell_name, str) else None
        if cell is None or self.data is None:
            return small
        dbu = self.layout.dbu
        probe = db.Box(int(round(x / dbu)) - 1, int(round(y / dbu)) - 1, int(round(x / dbu)) + 1,
                       int(round(y / dbu)) + 1)
        for li, role in self._layers_for(mtype):
            reg = db.Region(cell.begin_shapes_rec_touching(li, probe))
            if reg.is_empty():
                continue
            reg.merge()
            if role == "diffusion":
                # Magic splits diffusion at the gates: keep the piece of this net.
                for pl, _r in self._layers_for("poly"):
                    reg -= db.Region(cell.begin_shapes_rec(pl))
            hit = reg.interacting(db.Region(probe))
            for poly in hit.each():
                return poly.to_dtype(dbu)
        return small

    def _layers_for(self, mtype):
        t = (mtype or "").lower()
        rows = [r for r in getattr(self.data, "layers", []) if r.get("read") == "paint"
                and r.get("role") in ("diffusion", "poly", "conductor")]
        if _DIFF.search(t):
            pick = [r for r in rows if r["role"] == "diffusion"]
        elif t in ("p", "pc", "poly") or t.startswith("poly"):
            pick = [r for r in rows if r["role"] == "poly"]
        elif t in ("li", "locali", "li1"):
            pick = [r for r in rows if r["name"].lower().startswith("li")]
        else:
            m = re.match(r"^(?:m|metal|met)(\d+)$", t)
            if m:
                k = m.group(1)
                pick = [r for r in rows if re.match(r"^(met|metal)%s\b" % k, r["name"].lower())
                        or r["name"].lower().startswith(("met%s." % k, "metal%s." % k))
                        or r["name"].lower() in ("met%s" % k, "metal%s" % k)]
            else:
                pick = []
        out = []
        for r in pick:
            li = self.layout.find_layer(r["gds"][0], r["gds"][1])
            if li is not None:
                out.append((li, r["role"]))
        return out

    def _mark_net(self, rdb, findings, ext, cat, circuit_cell, name, text):
        loc = ext.locate_net(name, circuit_cell)
        if loc is None:
            self._add(rdb, findings, CAT_UNPLACED, self._kl_name(circuit_cell), None,
                      "%s (no position in the .ext files): %s" % (name, text))
            return
        cell = self._kl_name(circuit_cell)
        shape = self._net_shape(cell, loc.point, loc.type)
        self._add(rdb, findings, cat, cell, shape,
                  "%s, Magic type %s at (%.3f, %.3f): %s" % (name, loc.type, loc.point[0], loc.point[1], text))

    def _mark_circuit(self, rdb, ext, spice, c, findings):
        from ._kl import db
        lay_cell, sch_cell = c.name
        if lay_cell not in ext.cells:
            lay_cell = self.export.top
        for lay, sch in c.badnets:
            sch_names = {n for n, _f in sch if n != netgen.NO_NET}
            lay_names = {n for n, _f in lay if n != netgen.NO_NET}
            pad = any(n == netgen.NO_NET for n, _f in sch)
            fan = {n: f for n, f in sch}
            for n, f in lay:
                if n == netgen.NO_NET:
                    continue
                if n in sch_names:
                    self._mark_net(rdb, findings, ext, CAT_NETS, lay_cell, n,
                                   "layout %s; schematic %s" % (_fanout(f), _fanout(fan[n])))
                else:
                    cat = CAT_LAYOUT_ONLY if pad else CAT_NETS
                    self._mark_net(rdb, findings, ext, cat, lay_cell, n,
                                   "layout %s; netgen found no schematic net to pair it with" % _fanout(f))
            lay_pad = any(n == netgen.NO_NET for n, _f in lay)
            for n, f in sch:
                if n != netgen.NO_NET and n not in lay_names and lay_pad:
                    self._add(rdb, findings, CAT_SCHEM_ONLY, self._kl_name(lay_cell), None,
                              "schematic net %s of %s (%s) has no layout net" % (n, sch_cell, _fanout(f)))
        for lay, sch in c.badelements:
            for n, f in lay:
                if n in (netgen.NO_NET, "(no matching element)", "(no matching instance)"):
                    continue
                inst, model = device_ref(n)
                loc = ext.locate_device(inst, model, lay_cell, spice)
                text = "layout device %s (%s) has no schematic partner" % (n, _fanout(f))
                if loc is None:
                    self._add(rdb, findings, CAT_DEVICES, self._kl_name(lay_cell), None, text)
                else:
                    x, y = loc.point
                    self._add(rdb, findings, CAT_DEVICES, self._kl_name(lay_cell),
                              db.DBox(x - 0.05, y - 0.05, x + 0.05, y + 0.05), text)
        lay_dev, sch_dev = c.devices
        for model in sorted(set(lay_dev) | set(sch_dev)):
            a, b = lay_dev.get(model, 0), sch_dev.get(model, 0)
            if a != b:
                self._add(rdb, findings, CAT_DEVICES, self._kl_name(lay_cell), None,
                          "%s: %d in the layout, %d in the schematic %s" % (model, a, b, sch_cell))
        for (ldev, lprops), (sdev, sprops) in c.properties:
            inst, model = device_ref(ldev)
            diffs = ", ".join("%s: layout %s, schematic %s" % (k, lprops.get(k, "-"), sprops.get(k, "-"))
                              for k in sorted(set(lprops) | set(sprops)))
            text = "%s against %s: %s" % (ldev, sdev, diffs)
            loc = ext.locate_device(inst, model, lay_cell, spice)
            if loc is None:
                self._add(rdb, findings, CAT_PROPS, self._kl_name(lay_cell), None, text)
            else:
                x, y = loc.point
                self._add(rdb, findings, CAT_PROPS, self._kl_name(lay_cell),
                          db.DBox(x - 0.05, y - 0.05, x + 0.05, y + 0.05), text)
        top_ext = ext.cells.get(lay_cell)
        said_no_pins = False
        for lp, sp in c.pin_pairs():
            if lp == netgen.NO_PINS:
                if not said_no_pins:
                    kl_cell = self.layout.cell(self._kl_name(lay_cell)) if self.layout is not None else None
                    why = ("the layout has no texts" if kl_cell is not None and not has_texts(kl_cell)
                           else "Magic made no port from its texts")
                    self._add(rdb, findings, CAT_PINS, self._kl_name(lay_cell), None,
                              "the layout cell %s has no pins: %s" % (lay_cell, why))
                    said_no_pins = True
                if sp in (netgen.NO_PIN, netgen.NO_PINS):
                    continue
                # netgen's first row, "(no pins) | VPWR" (the schematic pin from its
                # report, netgen.Circuit.pin_pairs): that pin has no layout pin either,
                # as each row after it says of its own pin.
                lp = netgen.NO_PIN
            if sp in (netgen.NO_PIN, netgen.NO_PINS) and lp not in (netgen.NO_PIN, netgen.NO_PINS):
                port = top_ext.port(lp) if top_ext else None
                text = "layout pin %s has no partner among the pins of %s" % (lp, sch_cell)
                if port is not None:
                    l, b, rr, t = ext.box_um(port.box)
                    shape = db.DBox(l, b, max(rr, l + 0.01), max(t, b + 0.01))
                    self._add(rdb, findings, CAT_PINS, self._kl_name(lay_cell), shape, text)
                else:
                    self._add(rdb, findings, CAT_PINS, self._kl_name(lay_cell), None, text)
            elif lp == netgen.NO_PIN and sp not in (netgen.NO_PIN, netgen.NO_PINS):
                node = top_ext.nodes.get(sp) if top_ext else None
                text = "schematic pin %s has no pin in the layout" % sp
                if node is not None and node.point is not None:
                    text += ("; the layout has a net %s, but Magic made no port of it (a text on a "
                             "port layer, over a pin box, makes one)" % sp)
                    x, y = ext.um(node.x), ext.um(node.y)
                    self._add(rdb, findings, CAT_PINS, self._kl_name(lay_cell),
                              self._net_shape(self._kl_name(lay_cell), (x, y), node.type), text)
                else:
                    self._add(rdb, findings, CAT_PINS, self._kl_name(lay_cell), None, text)

    def _mark_readback(self, rdb, findings):
        """Every placement of a PCell variant whose device the read-back list holds."""
        from ._kl import db
        rows = readback(self.cfg.pdk)
        if not rows:
            return 0
        n = 0
        top = self.cell if not isinstance(self.cell, str) else self.layout.cell(self.cell)
        cat = None

        def listed(name):
            m = _VARIANT.match(name)
            return rows.get(m.group(1)) if m else None

        hits = []
        row = listed(top.name)
        if row:
            hits.append((top.name, top.dbbox(), row))
        it = top.begin_instances_rec()
        while not it.at_end():
            child = it.inst_cell()
            row = listed(child.name)
            if row:
                t = it.dtrans() * it.inst_dtrans()
                hits.append((child.name, child.dbbox().transformed(t), row))
            it.next()
        for name, box, row in hits:
            if cat is None:
                cat = rdb.category(CAT_READBACK, _DESCRIPTIONS[CAT_READBACK])
            self._add(rdb, findings, CAT_READBACK, self.export.klayout_top, box,
                      "%s: %s" % (name, readback_text(row)))
            n += 1
        return n


def has_texts(cell):
    """True when ``cell`` or a cell under it holds a text on any layer."""
    from ._kl import db
    ly = cell.layout()
    for li in ly.layer_indexes():
        it = cell.begin_shapes_rec(li)
        it.shape_flags = db.Shapes.STexts
        if not it.at_end():
            return True
    return False


def device_ref(name):
    """netgen's device name -> (instance path for extfile, model or None).
    netgen writes a device as "<model>:<index>", and one inside a subcell it
    flattened as "<use id>/<model>:<index>" (measured on all four PDKs)."""
    path, _, leaf = name.rpartition("/")
    model, sep, inst = leaf.partition(":")
    if not sep:
        model, inst = "", leaf
    return ("%s/%s" % (path, inst) if path else inst), (model or None)


def _fanout(f):
    if not f:
        return "no devices"
    return ", ".join("%s pin %s x%d" % (d, p, c) for d, p, c in f if d)


_SAID = re.compile(r"(warning|error|cannot|can't|couldn't|not found|unknown|failed|rescaled)", re.I)


def _magic_lines(result):
    """Magic's warnings and errors, without what it prints on every run
    (``drcjob.is_noise``: "Warning: Calma reading is not undoable!")."""
    from .drcjob import is_noise
    lines = list(getattr(result, "stdout", []) or []) + (getattr(result, "stderr", "") or "").splitlines()
    return [ln for ln in lines if _SAID.search(ln) and not ln.startswith("KMP_") and not is_noise(ln)]


# -- the netlist file the extract command writes ----------------------------------

# The first line of every netlist file the plugin writes. A file whose first
# line does not start with it is never overwritten without -o.
NETLIST_HEADER = "* Written by klayout_magic_pcells"


class NetlistRefused(Exception):
    """The target exists and the plugin did not write it."""


def unname_netlist(out):
    """Take the job directory's netlist.spice out of an extract Outcome's
    summary, for a run whose netlist was not written: the summary then
    names no file. ``files["netlist"]`` is unchanged."""
    src = out.files.get("netlist")
    if src:
        out.summary = out.summary.replace(" into %s." % src, ".", 1)
    return out


def name_netlist(out, target):
    """Make an extract Outcome's summary name ``target``, the file the
    netlist was written to, instead of the job directory's netlist.spice
    (which goes with the job directory). ``files["netlist"]`` keeps the job
    directory's copy; ``files["netlist_file"]`` is ``target``."""
    src = out.files.get("netlist")
    if not (src and target):
        return out
    out.summary = out.summary.replace(" into %s." % src, " into %s." % target, 1)
    out.files["netlist_file"] = target
    return out


def default_netlist_path(layout_file, cell_name, caps=False):
    """``<cell>.magic.spice`` (``<cell>.magic.pex.spice`` with caps) beside
    the layout file."""
    base = os.path.dirname(os.path.abspath(layout_file))
    return os.path.join(base, "%s.magic.%s" % (cell_name, "pex.spice" if caps else "spice"))


def written_by_plugin(path):
    """True when the file's first line is the plugin's header."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            first = f.readline()
    except OSError:
        return False
    return first.startswith(NETLIST_HEADER)


def netlist_header(cell, pdk, layout_file=None, caps=False):
    from . import __version__
    text = "%s %s: Magic's netlist of %s (%s, %s)%s" % (
        NETLIST_HEADER, __version__, cell, "with parasitic capacitance" if caps else "netlist only", pdk,
        " from %s" % layout_file if layout_file else "")
    return " ".join(text.split()) + "\n"


def save_netlist(src, target, header, overwrite=False):
    """Write the header line, then Magic's netlist ``src``, to ``target``.
    Without ``overwrite``, a target that exists and whose first line is not
    the plugin's header raises NetlistRefused (the user's schematic, say);
    one the plugin wrote is replaced."""
    if not overwrite and os.path.lexists(target) and not written_by_plugin(target):
        raise NetlistRefused("%s exists and klayout_magic_pcells did not write it (its first line is not "
                             "\"%s ...\")" % (target, NETLIST_HEADER))
    with open(src, "rb") as f:
        body = f.read()
    with open(target, "wb") as f:
        f.write(header.encode("utf-8"))
        f.write(body)
    return target


def prepare(layout, cell, cfg, data, options):
    """A Task for ``options["cmd"]`` ("extract" or "lvs") on ``cell`` of
    ``layout``. Options: caps, flatglob, ports_from_labels, schematic,
    schematic_cell, no_cache, file (for the report's command line), job_dir.
    The cell is exported here; Magic starts with ``Task.start()``."""
    t = Task(layout, cell, cfg, data, options)
    t._prepare()
    return t


def cli_main(args, ctx):
    import sys
    cell = ctx.cells[0]
    options = {"cmd": args.cmd, "file": args.file, "flatglob": bool(getattr(args, "flatglob", False)),
               "ports_from_labels": bool(getattr(args, "ports_from_labels", False)),
               "no_cache": bool(getattr(args, "no_cache", False))}
    if args.cmd == "extract":
        options["caps"] = bool(getattr(args, "caps", False))
    else:
        options["schematic"] = args.schematic
        options["schematic_cell"] = getattr(args, "schematic_cell", None)
    task = prepare(ctx.layout, cell, ctx.cfg, ctx.data, options)
    out = task.start().wait()
    status = 2
    try:
        status = _write_outputs(args, ctx, cell, options, task, out)
    finally:
        gone = jobs.release(out)
        if gone and status == 2:
            sys.stderr.write("note: the job directory %s is removed; KMP_JOB_KEEP=1 keeps it\n" % gone[0])
    return status


def _write_outputs(args, ctx, cell, options, task, out):
    import sys
    # The report is saved also when the job failed: it says why.
    if args.cmd == "extract" and getattr(args, "rdb", None):
        out.rdb.save(args.rdb)
    if args.cmd == "lvs" and args.output:
        out.rdb.save(args.output)
    if out.status == 2:
        sys.stderr.write(out.summary + "\n")
        for f in out.findings:
            sys.stderr.write("  %s\n" % f["text"])
        return 2
    if args.cmd == "extract" and out.files.get("netlist"):
        target = args.output or default_netlist_path(args.file, cell.name, options["caps"])
        header = netlist_header(cell.name, ctx.pdk, args.file, options["caps"])
        # The summary is printed after the write: it names the file written,
        # or no file at all (the job directory's copy goes with it).
        try:
            save_netlist(out.files["netlist"], target, header, overwrite=bool(args.output))
        except NetlistRefused as e:
            sys.stderr.write(unname_netlist(out).summary + "\n")
            sys.stderr.write("error: %s; pass -o OUT.spice to write the netlist elsewhere, or -o %s to "
                             "overwrite it\n" % (e, target))
            return 2
        except OSError as e:
            sys.stderr.write(unname_netlist(out).summary + "\n")
            sys.stderr.write("cannot write %s (%s)\n" % (target, e))
            return 2
        sys.stderr.write(name_netlist(out, target).summary + "\n")
        sys.stderr.write("netlist: %s\n" % target)
    else:
        sys.stderr.write(out.summary + "\n")
        if getattr(args, "report", None) and out.files.get("report"):
            shutil.copyfile(out.files["report"], args.report)
        if getattr(args, "json", None):
            v = out.verdict
            doc = {"cmd": "lvs", "pdk": ctx.pdk, "file": args.file, "cell": cell.name,
                   "schematic": args.schematic, "schematic_cell": task.schematic_cell, "status": out.status,
                   "verdict": {"matched": v.matched, "final": v.final, "reasons": v.reasons,
                               "symmetries": v.symmetries},
                   "findings": out.findings, "files": out.files}
            with open(args.json, "w", encoding="utf-8") as f:
                json.dump(doc, f, indent=1)
    for f in out.findings:
        if f["category"].startswith(("netgen/", "Extraction/", "Export/")):
            sys.stderr.write("  %s: %s\n" % (f["category"], f["text"]))
    for name, n in _export_counts(task.export):
        sys.stderr.write("  %s: %d item%s\n" % (name, n, "" if n == 1 else "s"))
    return out.status


def _export_counts(er):
    """[(category, items)] of an ExportResult's findings."""
    if er is None:
        return []
    rows = [(markers.CAT_OFFGRID, len(er.offgrid)), (markers.CAT_UNREAD, len(er.unread)),
            (markers.CAT_READS_AS, len(er.reads_as)), (markers.CAT_CROSS_CELL, len(er.cross_cell)),
            (markers.CAT_FLATTENED, len(er.flattened)), (markers.CAT_RENAMED, len(er.renamed))]
    return [(c, n) for c, n in rows if n]
