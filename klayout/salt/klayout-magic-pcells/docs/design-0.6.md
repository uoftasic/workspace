# klayout-magic-pcells 0.6 design: Magic's checks from KLayout

Written 2026-11-24 from the code of version 0.6.0, for a maintainer, and
updated for version 0.6.1, which changed the gap tables (3.5), their
lines in the DRC descriptions (3.1) and some cases of the case suite
(5.1), and for version 0.6.2, which changed the menu's messages and
windows (2.4), the report's lines of text and its information items
(2.7), where hierarchical DRC files a box (3.1), the pins that LVS
reports (3.2), the generated-layer check's texts (3.3) and the port
check's reading of comment layers and pin boxes (3.4). A trial of the
plugin for a sky130A layout course found the problems that 0.6.2 fixes,
on the course's layouts, under XFCE on a 1280 × 800 screen.

Version 0.6 adds checks for four PDKs: sky130A, gf180mcuD, ihp-sg13g2 and
ihp-sg13cmos5l. It runs Magic's DRC, Magic's extraction and netgen's LVS
on a cell of a KLayout layout, from a Magic menu in KLayout (section 2.4)
and from the command line. It adds a generated-layer check and a port
check, and it publishes a table per PDK of where Magic's DRC and the
PDK's KLayout decks disagree. The PCell libraries are as `docs/design.md`
describes them; their parity harness (`tests/parity`, `docs/design.md`
section 10) has one more step, for these checks, which section 5.2
describes.

Claims carry a tag, as in `docs/design.md`:

- **[run]**: run with the 0.6 code or its tests in the pinned image
  `hpretl/iic-osic-tools@sha256:3c371645b19c6f6564dc8c7b21e39ad1c1833d274fe5b85639afe1ba9d7987e7`
  (Magic 8.3.681, KLayout 0.30.11, Netgen 1.5.323), either while the 0.6
  code was being written (*the build* below), on 0.6.0, 0.6.1 or 0.6.2,
  as the text says; a quoted command output is from 0.6.0 unless the text
  says otherwise.
- **[src]**: read from the code.
- **UNVERIFIED**: neither. Section 7 collects these.

Version 0.6 was designed, and the design reviewed, before any code was
written. Section 6 calls that version *the design* and says where the
code departs from it, and why. Two pieces of work outside the repository
fed the design. A gap study per PDK measured where Magic's DRC,
extraction and LVS disagree with the PDK's KLayout decks, on small
layouts that each change one thing; the case suite (5.1) redraws those
layouts and cites the studies as `GAPS-<pdk>`. A review of the design,
made before any code, ran its own measurements (section 6). Numbers from
the studies and the review, and from probe scripts run during the build,
are marked "measured in the image": they come from the same image, but
not from the 0.6 code.

A *job* is one Magic process running one Tcl script on one file. The
*export* is the GDS file written from the cell in memory for a job. A
*why-text* is the message Magic's DRC gives an error box (`N-well width <
0.84um (nwell.1)`); its *rule ID* is the text in its last parentheses, or
the whole why-text when there are none. The *RDB* is KLayout's report
database, which the Marker Database Browser shows; every check writes one.
A number in parentheses, such as (2.4), is a section of this document.

## 1. Goal and what parity means for each check

Someone who draws in KLayout gets Magic's results on that layout without
leaving KLayout, and is told where KLayout's own decks and Magic disagree.
The checks run Magic's engines on the user's layout, as the PCells do for
devices, and leave the PDK's KLayout decks as they are.

| Check | Command | Parity means |
|---|---|---|
| DRC | `drc` | the markers are the error boxes Magic lists for the export in the chosen style and mode: same why-text, same box, in the cell Magic checked |
| Extraction | `extract` | the netlist is the one `extract all` and `ext2spice` write for the export, read with its hierarchy |
| LVS | `lvs` | the result is netgen's with the PDK's setup file; each net, device, property or pin netgen reports is a marker where Magic's `.ext` files place it |
| Generated layers | `layers` | correct layouts (the negative controls of 3.3) give no finding; each case drawn to break a generated-layer rule gives one |
| Ports | `ports` | every text and pin box is classified as Magic's reader and the PDK's KLayout LVS deck treat it |
| Gap table | `scripts/gaps.sh` | rebuilt from the installed PDK and decks; `--check` fails when a table would change |

The harness's jobs step (5.2) runs three references beside the plugin's
DRC [src]. The plumbing check compares the plugin with
`tests/parity/mdrc.tcl`, a script that uses no plugin code, on the
plugin's own export. It compares multisets of (cell, why-text, box at
1 nm): in hierarchical mode, the DRC mode that checks every cell (3.1),
each cell's own listing; in flat mode, the TSV. It tests the export, the
job script, the parsing and the units, but both sides read one file. The
export-fidelity check runs `mdrc.tcl` on the user's original GDS, with
every cell as its own top, and compares the result with the plugin's
hierarchical run per cell and rule, as merged error regions whose XOR
must be empty at 1 nm; it finds a flattened tree, a lost cell or a moved
shape. The third reference, `tests/jobs/magic_native.tcl`, gives what a
user of Magic's GUI or of a plain Magic script gets: the top cell of the
original file, checked from the top only, in `drc(fast)` and then
`drc(full)`. Its result is recorded, not asserted equal, because
hierarchical mode checks every cell and can report more (3.1). On
sky130A's `--quick` run of the jobs step (5.2), 66 plumbing and 33
fidelity comparisons passed, and `magic_native.tcl` gave the same errors
as hierarchical mode on all 22 pairs of case and style [run].

## 2. Architecture

```
KLayout process: GUI, klayout -b, or python3 with the klayout module
 ├─ PCell libraries sky130_magic, ... (one MagicServer per PDK)
 └─ the checks: command-line subcommands and the Magic menu (gui.py)
      ├─ pdkchoice.py   which PDK the layout belongs to
      ├─ export.py      cell in memory -> in.gds, and what Magic will change
      ├─ drcjob.py, lvsjob.py, layercheck.py, portcheck.py
      │     prepare() -> Task (start, poll, wait, cancel) -> Outcome
      ├─ jobs.py        MagicJob: one magic -dnull per job, in <cache>/jobs/
      │     tcl/kmp_job_common.tcl, kmp_drc.tcl, kmp_extract.tcl, kmp_rw.tcl
      ├─ netgen.py      netgen -batch lvs ... -json, and its result
      ├─ extfile.py     .ext reader: ports, nodes, devices, use transforms
      ├─ markers.py     the RDB code every check shares
      └─ data/          pdk-, devices-, readback- and gaps-<pdk>.json
```

### 2.1 One Magic process per job

A job does not go through the PDK's PCell server (`MagicServer`,
`docs/design.md` 3.3). The server answers one request at a time and
restarts Magic after `KMP_TIMEOUT` (30 s), so a DRC of a block sent
through it would be killed, and every PCell of that PDK would wait for it
meanwhile [src]. A job is `magic -dnull -noconsole -rcfile <rcfile>
<script>`, with the server's environment, stdin closed and the job
directory as its working directory.
`jobs.MagicJob` starts it on the calling thread (KLayout's main thread in
the GUI), because `PR_SET_PDEATHSIG` kills the child when the thread that
started it exits. The child runs in its own process group, which a
timeout (`KMP_JOB_TIMEOUT`, 1800 s) or `cancel()` kills; the backend test
checks that neither leaves a Magic process [run]. One process checks at
most 15 cells (`jobs.batches()`). In a gap study, a process that checked
98 cells in a row in three styles ended without its end marker or an
error, and batches of 15 worked (measured in the image; the cause
is UNVERIFIED).

### 2.2 The job protocol

Every job script sources `kmp_job_common.tcl` and talks to `jobs.py` only
through stdout lines [src]: `KMP_JOB_SCALE <um>` (µm per Magic unit, `[cif
scale out]`), `KMP_JOB <stage> <n>`, and `KMP_JOB_FAIL <message>` or
`KMP_JOB_DONE <n>`, after which Magic quits. A job without its done line
has failed whatever the exit status, because Magic exits 0 after a Tcl
error in its start-up script. A cell name reaches Tcl only as an
environment variable's value. `kmp_job_read` prints the scale from the
same process that reads the file, because Magic rescales its units for a
file with off-grid coordinates ("units rescaled by factor of 5 / 1",
measured in the image); the scale is 0.004999999888241291 on all four
PDKs [run]. `kmp_job_load` fails the job unless the cell is in `cellname
list allcells`, `load` succeeds, `cellname list self` then names that
cell, and the cell's box is not empty. These checks are there because
Magic does not always say when a load went wrong: it creates an empty
cell for an unknown name, loads an empty `y` for `x/y`, keeps the
previous cell for `br[0]` and `café`, and raises an error for `a.b`
(measured in the image). An empty cell has the box `0 0 1 1`, so for a box that small the
script looks inside with `select area` and `what -list` before it fails
the job with "cell X is empty". For a top cell, every check that runs
Magic turns that failure into a finding (3.1 to 3.4).

### 2.3 Job directories and the job cache

A job's files go under `<cache>/jobs/<pdk>/<kind>/`, where `<cache>` is
the plugin's cache directory (`KMP_CACHE_DIR`, `docs/design.md` section
6) [src]:

| Kind | Files besides `in.gds` and `job.json` |
|---|---|
| `drc` | `cells.txt` (Magic's order), `drc_<i>.tsv` per cell, `summary.tsv`, `meta.tsv`, `kmp_drc.json` |
| `extract` | one `.ext` per cell, `netlist.spice`, `kmp_result.json`; per LVS run `lvs.out`, `lvs.json` and `netgen.log`, in `lvs-<random>/` (with `kmp_owner.json`, the LVS process's PID) in a key's directory and in `lvs/` in a tmp-* one |
| `rw` | `rw.gds`, `kmp__flat.ext`, `kmp__flat.spice`, `rw_times.txt`; for `ports --magic`, `<top>.spice` and the `.ext` files |

`job.json` records the kind, PDK, script, state, owning PID, plugin
version and a fingerprint (versions digest, Tcl digest, plugin version).
With the job cache on, a finished job stays in its key's directory,
`<kind>/<key>/`. The key (`jobs.job_cache_key`) is a SHA-256 over the
export's digest, the kind, the options, the PDK, a versions digest (the
Magic executable, the rcfile, every file in its directory, the PDK
commit), the job Tcl files and the plugin version, so a second run on an
unchanged layout starts no Magic. The DRC area is not in the key, so an
area check reuses the whole-cell job; reusing results per cell was left
out of 0.6 (6.7).

A key's directory is written once, whole: the job runs in a new
`tmp-<random>/` beside it, and once Magic has ended and `job.json` is
written, `MagicJob._publish` renames that directory to the key's. Two
runs with one key at once (the GUI and the command line on one layout,
or two cells that export to the same file) therefore read only their own
files; the first to end fills the cache, and a later one keeps its result
in its own tmp-* directory. A key's directory that holds a failed or
unfinished job, or no `job.json`, is moved aside in one rename and
replaced. So is the directory of a finished job that lacks a file its
check needs (`MagicJob`'s `required` files: `kmp_drc.json` for DRC;
`netlist.spice` and `kmp_result.json` for extraction; the rw outputs),
but only once the process that ran the job has ended, because that
process writes the check's record right after the rename [src]. Failed
runs are published too, so the directory that an error message names
still exists after the command ends.

`KMP_CACHE=0` and `--no-cache` mean the same for every check: the job runs
in a new `<cache>/jobs/<pdk>/<kind>/tmp-<random>/`, and no key's directory
is read or written. `jobs.release()` removes that directory once the
outcome's files have been read (after the command line writes its
outputs, or once the GUI shows the result). A directory that a process
has not released is removed when the process exits, and `KMP_JOB_KEEP=1`
keeps them all. An LVS run's `lvs-<random>/` in a key's directory is
registered with `jobs.track()` and is removed the same way [src]. Job
directories are never in the system's temporary directory, so the checks
need a writable `KMP_CACHE_DIR` even with the cache off.

`cache clear` removes every job directory except a running job's; it
also removes the finished tmp-* directories of a session that is still
open. `cache prune` removes, for its PDKs:

- key directories whose fingerprint is not current;
- tmp-* directories whose owning process has ended, and the `run-*`
  directories of development builds;
- directories without a readable `job.json` that are older than a day;
- in the key directories it keeps, the `lvs-*` folders whose
  `kmp_owner.json` names a process that has ended, or that have no such
  file and are older than a day (`cache.lvs_leftovers`).

### 2.4 The task API and the Magic menu

The command line and the GUI share one code path. Each check module
(`drcjob`; `lvsjob` for `extract` and `lvs`; `layercheck`; `portcheck`)
has [src]:

```python
def prepare(layout, cell, cfg, data, options) -> Task  # exports; Magic not started
class Task:
    stage                  # (name, n) of the last progress line
    def start(self): ...   # returns at once
    def poll(self): ...    # Outcome once done, else None
    def wait(self): ...    # blocks
    def cancel(self): ...  # kills Magic; the outcome (status 2) says "cancelled"
class Outcome:
    status   # 0 nothing found, 1 findings, 2 the input or a job failed
    rdb      # markers.Rdb, also on failure, when it says why
    summary  # one paragraph, for a message box or stderr
    headline # the message box's first line, in plain words; None on failure
    files    # name -> path: "job_dir", export, netlist, report, ...
def cli_main(args, ctx) -> int   # prepare, wait, write -o, --tsv, --json; release
```

On the command line, `__main__.job_context` first checks `--cell` against
the file (a missing cell exits 2 with "cell X is not in FILE"), then
chooses the PDK and loads its data. `prepare` does not raise on a bad
input. It returns a Task that ends with status 2 and the reason in its
RDB when the export fails, when the cell is not in the layout, or, in a
check that runs Magic, when the layout holds error-marker cells (2.6)
[src]. A `RuntimeError` from KLayout while the cell is copied or written
counts as a failed export: `extract` and `lvs` say "cannot export cell X:
<its first line>", and `drc` says "did not run: cannot export X: <its
first line>" [src]. The LVS Task runs netgen inside the `poll` call that
sees Magic finish, which takes 0.01 to 0.02 s on an inverter [run]. In
the GUI, a 200 ms `QTimer` polled at intervals of 0.198 to 0.211 s, and
the menu stayed usable (measured in the image).

**The menu.** `gui.install_menu()`, which the autorun macro calls, puts a
"Magic" menu before Help, using only `pya.Action` and `AbstractMenu`
(reading a replaced menu's Qt objects crashed KLayout, measured in the
image). Its entries are Run Magic DRC..., Check the visible area with
Magic DRC, Extract with Magic..., LVS with netgen..., Check generated
layers, Check ports, Rule differences and Settings... [src]. With
`KMP_MENU=0`, or with no main window, there is no menu. An entry takes
the current view's cell as it is in memory and calls `choose_pdk(...,
hint_decides=False)`. Where the command line would guess the PDK (2.5),
a dialog lists the PDKs with the guess preselected and says why, and the
answer holds for that file until KLayout closes. A cached job ends in the
first `poll()` and shows no progress dialog, and so does the port check,
which runs no Magic from the menu. Otherwise a non-modal
`QProgressDialog`, polled every 200 ms, shows "<title>: <stage> (<s>
s)", and its Cancel button calls `Task.cancel()` (without Qt,
`pya.AbsoluteProgress` is used and blocks). A second check in the same
view asks whether to cancel the first. At the end the RDB opens in the
browser and a message box gives the outcome's `headline`, a first line in
plain words that each check builds (`drcjob.headline`,
`layercheck.headline`, `portcheck.headline`, `lvsjob.lvs_headline`), and
below it the summary. After LVS the message gets no line that names
netgen's report, since the report's window title does. Closing the message calls `raise_browser()`,
which raises the visible `MarkerBrowserDialog` windows: KLayout's browser
has no parent window, and under XFCE a maximised main window that gets the
focus back from the message covered it (seen under XFCE on a 1280 × 800
screen, with KLayout 0.30.11 and 0.6.1's code; 0.6.2's raise was checked
there too). The text
windows and Settings open no larger than the screen's free area and have a
maximise button (`fit_size`, `_resizable`). Then the tmp-* job
directories are released. The DRC dialog's choices are kept in `state.json` beside
`config.ini`. Extract writes `<cell>.magic.spice` by the command line's
rule (3.2); where that rule refuses, or for a layout that was never
saved, it says "Not written: ..." and opens a save dialog at the first
free name (`inv.magic-2.spice`). The browser's Rerun button calls the
recipe that `gui.register_recipe()` registers, with the RDB's generator
(2.7), and `gui.rerun` runs that check again and replaces the database.
The screenshot rig (`KMP_SHOT_SESSIONS=magic tools/screenshots/take.sh`)
drives every entry under Xvfb on sky130A. Its runs include a Cancel that
killed Magic, a DRC Rerun, and an extract next to a file that the plugin
did not write, which must leave that file unchanged [run, during the
build].

### 2.5 Which PDK a layout belongs to

`pdkchoice.choose_pdk` takes the first of these rules that decides [src]:

1. `--pdk`;
2. the layout's technology, when its PDK fits the layout's layers;
3. the library of the layout's PCell variants, live or `<defunct>`, else
   the PDK whose manifest has the device of every `<device>__kmp_<8 hex>`
   cell;
4. `KMP_PDKS`, when it selects one PDK;
5. a guess: the best-fitting PDK when rule 2 set the technology aside,
   and the image's `PDK` variable otherwise.

The command line takes the guess with a note on stderr; when there is no
guess, it exits 2 and asks for `--pdk`. The fit (`layer_fit`) counts the
layout's shapes on GDS layers that each PDK's data file knows, except
text, boundary and Magic's mask-style (`*.mask`) layers. The technology
decides unless its PDK counts fewer than 3/4 (`TECH_FIT`) of the best
PDK's shapes (6.8). The two IHP PDKs share layer numbers, so between them
the technology decides, and a guess takes the PDK variable when it names
one of them, else ihp-sg13g2. KLayout reads a GDS file with technology
'', so on the command line rule 2 never applies [run]. Given technology
sg13g2, a sky130A inverter gets "a guess from the layers: the layout's
technology is sg13g2 (ihp-sg13g2), but 0% of its shapes are on
ihp-sg13g2's layers and 89% on sky130A's" [run].

### 2.6 The export and its findings

`export.export_cell` writes the cell's tree from the layout in memory, so
unsaved edits are checked. It writes no `$$$CONTEXT_INFO$$$` structure,
which Magic would read as a cell, and no timestamps, so that equal
layouts give equal bytes for the cache key [src]. It copies the tree
with `Cell.copy_tree`, which turns PCell variants into plain cells; a
round trip through a file would lose names, because KLayout's GDS writer
turns `a b` into `a$b` and `café` into `caf$$` [run]. On the copy, it
flattens instances that are magnified or rotated by other than a
multiple of 90° (Magic rounds a 45° instance to 90°, measured in the
image). It renames cells whose names are not made of `[A-Za-z0-9_$]` and
keeps a map of the renames, and in flat mode it flattens the top cell.
From the layer table in the PDK's data file (4), it lists in every
check's RDB what Magic will change without giving an error:

| `Export/...` category | What it reports |
|---|---|
| `Magic snaps this shape to its 5 nm grid` | vertices off the PDK grid; Magic snaps them, warns, and reports no DRC error |
| `Magic does not read this layer` | shapes on layers Magic's reader ignores; for a layer Magic draws itself on output (sky130A npc 95/20) the item says so |
| `Magic reads this layer as another type` | the IHP PDKs' 16/0, which Magic reads as `digisub` |
| `Magic reads this cell without a layer drawn in another cell` | the cross-cell check below |
| `Magic reads nothing in this cell` | a top cell of which Magic's reader keeps no shape (3.1) |
| `error-marker cells`, `instances flattened for Magic`, `cells renamed for Magic` | cells holding the plugin's 255/0 marker, and the changes above |

The cross-cell check runs in hierarchical mode only. Through every
placement, it finds an implant or marker shape drawn in one cell over
another cell's diffusion or poly, and a well shape drawn over another
cell's diffusion, where the other cell does not draw that layer there
itself; Magic reads that other cell without the layer [src]. The drawing
cell can be a parent, a child or a sibling. Cuts don't count: a contact
takes its type from the diffusion or poly under it in its own cell, and
a via takes none; a well decides what diffusion is, not what poly is
(6.8). Counting every overlap
gave 9,859 findings on a block of 1,280 placed sky130A standard cells,
each over diffusion that the cell covered with the same layer itself;
leaving those out gives 0 (measured in the image). A cell that holds the
error marker is a PCell variant that Magic failed to generate, and Magic
does not read 255/0, so every check that runs Magic returns status 2
with `ExportResult.refusal()`'s reason instead of checking the layout
without the device.

### 2.7 Reports

`markers.Rdb` works in KLayout and with the standalone `klayout.rdb`
module. It makes one RDB cell per checked cell, with items in µm in that
cell's coordinates [src]. `add_parent_references` gives each RDB cell a
reference per placement in its parents (up to 1000), because the
browser draws a child's items through the first reference only
(measured in the image).
Each RDB's generator is the text that `pya.Recipe.generator` gives for
the recipe `klayout_magic_pcells`, such as
`klayout_magic_pcells: cell='inv_pcell',cmd='drc',file='/repo/out/cases/sky130A/inverters/inv_pcell.gds',mode='hierarchical',pdk='sky130A',style='drc(full)'`
[run]. With it, the browser's Rerun button calls the plugin. `klayout
LAYOUT -m FILE.lyrdb` opens a report on its layout; the other order puts
it in an empty first view (measured in the image).

KLayout 0.30's browser shows an item's values in the Info pane as lines of
a block that does not wrap, and cuts each value after 200 characters
(`MarkerBrowserPage::update_info_text` in KLayout's source). `Rdb.item`
therefore stores a text as several string values (`text_lines`): one per
sentence or clause, a longer one broken into lines of at most 80
characters; joined with spaces they give the text back
(`markers.item_text`). The database's description is one line, because
the browser's database list shows a line break there as `\n`. An item
that is information, not a finding of its check, gets KLayout's tag
`waived` and is marked visited (`Rdb.item(..., info=True)`): the browser
still counts it in its category's total, but writes the waived count
after a dash and draws a category of such items in green (seen under
XFCE with 0.6.2's code). Each check names the export findings that
count (`add_export_findings(..., counted=...)`): none for DRC, extraction
and LVS, and the off-grid, read-as-another-type and cross-cell ones for
the layers check.

## 3. The checks

### 3.1 DRC

`kmp_drc.tcl` checks a cell as the edit cell the way `mdrc.tcl` does:
`load`, `select top cell`, `box grow c 10um`, `drc euclidean on`, `drc
style`, `drc check`, `drc catchup`, `drc listall why`, `drc list count
total` [src]. The style is `KMP_DRC_STYLE`, `drc(full)` by default.
Magic's own default, the first style in each tech file, is `drc(fast)`,
and the gap studies found the latch-up and tap rules in `drc(full)` only
(measured in the image).

The DRC has two modes. Hierarchical mode, the default, exports the
hierarchy. Magic reads it with a plain `gds read` and checks every cell
definition as the edit cell, children first and then the top. The top
cell's check is reported whole, in the top cell; a subcell's box that it
does not cover stays in that subcell's coordinates and RDB cell (the
subcell classes below). A child that
Magic reads as empty is skipped, and so is a cell of the export from
which Magic made no cell; both are listed by KLayout name in
`Outcome.empty` and in the RDB description [src]. Flat mode checks a
flattened copy; the plugin calls its result "Magic's verdict on the
flattened mask". Every RDB gives Magic's `drc list count total`, which
differs from the number of boxes, and the RDB of a hierarchical run says
that Magic's check from the top cell alone can report fewer errors.

**Why hierarchical is the default.** Magic's GDS reader decides device
types inside each cell from that cell's own shapes. With an inverter's
implants or well in a parent cell and its transistors in a child, Magic
reports errors and wrong devices. Run with `drc(full)` and the harness's
extraction, the case suite's `hier` set gave the same numbers as the
review [run]:

| PDK, layers in the parent | Magic's check of the two-level top cell | Devices Magic extracts |
|---|---|---|
| sky130A, nsdm and psdm | Can't overlap 2, LU.3 3, diff/tap.8 13, nwell.1 2, nwell.2a 2, nwell.4 2, poly.4 4 | pfet_01v8, pfet_01v8_hvt: the NMOS reads as a pfet |
| sky130A, nwell | Can't overlap 3, diff/tap.11 10, nwell.4 5, poly.5 8 | nfet_01v8 only |
| gf180mcuD, NPLUS and PPLUS | Can't overlap 1, DF.8 5, PL.5a 4 | none |
| gf180mcuD, NWELL | CO.4 8, DF.1a 6, DF.1c 16, DF.3a 2, DF.5 12, DF.8 8, DF.9 3, FIXME 8, PL.4 14 | none |
| ihp-sg13g2, pSD / NWell | LU.b 3, NW.d 11 / Can't overlap 3, NW.d 6, NW.f 17 | lv_nmos only |
| ihp-sg13cmos5l, pSD / NWell | LU.b 3, NW.d 11 / Can't overlap 3, NW.d 5, NW.f 17 | lv_nmos only |

The flat originals gave no error and the drawn devices on every row, and
flat mode gives no error on every two-level cell [run]. A flat default
would call clean a layout that Magic fails, and the DRC job would disagree
with the extraction job, which keeps the hierarchy. On every PDK, the
backend test asserts that the top cell's own listing equals the measured
top-only result, and that the rules of hierarchical mode's errors are
exactly the rules of that result [run]. Both modes on one file, trimmed,
on 0.6.2's code [run]:

```
$ python3 -m klayout_magic_pcells drc out/cases/sky130A/hier/inv_base_all_h.gds --tsv -
cell	rule	why	l	b	r	t
inv_base_all_h	nwell.2a	N-well spacing < 1.27um (nwell.2a)	1.17	3.37	1.68	3.4
...
inv_base_all_h	poly.4	poly spacing to Diffusion < 0.075um (poly.4)	1.5	3.5	1.575	3.575
Magic DRC (drc(full), hierarchical) of inv_base_all_h on sky130A: 36 error boxes, 7 rules, in 1 cell. inv_base_all_h: 36 error boxes; Magic's drc list count total 5 in the top cell, 7 over the 2 cells checked; of the 47 boxes the subcells' own checks list, 7 are in the top cell's check (reported there), 0 only in the flattened layout's check, 40 only when the subcell is checked on its own (information, not counted). The export has 9 findings (category Export).
$ python3 -m klayout_magic_pcells drc out/cases/sky130A/hier/inv_base_all_h.gds --mode flat --tsv -
cell	rule	why	l	b	r	t
Magic DRC (drc(full), flat) of inv_base_all_h on sky130A: no errors. inv_base_all_h: 0 error boxes; Magic's drc list count total 0 in the top cell. The export has 1 finding (category Export).
```

The first exits 1, the second 0; eight of the nine export findings are
the cross-cell check's.

**Subcell boxes.** A subcell checked on its own can list boxes that its
surroundings remove (a met1 area error on a PCell's gate pad that the
parent's metal joins), and boxes that Magic's check from the top cell
misses although the flattened mask has them. So `drcjob.classify` sorts
each box of a cell other than the top, through each placement [src]:

- it is left out if the top cell's own listing has a box of its rule ID
  that overlaps or touches it: the top cell's box, which the report
  keeps, stands for it;
- else it is an error, in the subcell, if Magic's check of the flattened
  layout has one, and the item says so;
- else it is information, under `Magic DRC/<rule>/only when <cell> is
  checked on its own`. Such boxes go in `Outcome.alone` and are left out
  of the error count, the exit status and the TSV.

The test is overlap, not equality, because Magic tiles the same error
region differently from the top and from the cells (sky130A diff/tap.10:
21 boxes from the top, 17 from the cells, measured in the image). The
flattened check is one more job, with flat mode's options, on the export
read back and flattened. It runs only when some subcell box is not in
the top's listing, and it shares flat mode's cache entry when the two
files are equal [run]. On the hier cases, every box that a child's own
check adds beyond the top's listing is information: 40, 20 and 16 on the
three sky130A cases, 11 each on gf180mcuD `C_NMOS_all_h`, `C_NMOS_imp_h`
and `C_PMOS_all_h` (which exits 0) and 4 on `C_PMOS_nw_h`, none on IHP
[run]. On the case suite's PCell inverter (5.1), three met1.6 boxes
inside each FET variant come from the gate-contact pads that
`docs/design.md` expects on a lone device; neither the top cell's check
nor flat mode lists them, so they are information and `drc` exits 0
[run].

**Copies.** A parent's check lists most of its children's errors again,
so hierarchical mode drops a parent's box whose (why-text, box at 1 nm)
equals a subcell's box at any depth through a placement (`drcjob.dedup`).
Until 0.6.2 the top cell's copies were dropped too, and a subcell box that
the top cell's check listed was an error in the subcell. That filed a top
cell's errors under its subcells: on a placement of sky130A standard
cells without a tap cell, 0.6.1 dropped 61 of the top cell's 62 boxes as
copies, and 55 of the 56 latch-up and tap boxes went under three
standard cells, where a reader looks for the fault in the foundry's
cells [run, 0.6.1]. Since 0.6.2 the top cell keeps every box of its own
check (`dedup(..., keep=(top,))`), and a subcell box that it covers is
left out (the first class above); the same placement gives 62 boxes, all
in the top cell, as flat mode does [run]. The case suite's sheets place
each case as a subcell, 40 µm apart. Checked in `drc(full)` without the
cache, the sheets of 0.6.0 (130, 69, 151 and 49 cases; 0.6.1 redrew
eight of these cases and added two, 5.1) gave the following with 0.6.0's
copy drop; the last column is the flattened check's time, against about
8.7 s for the hierarchical batches of the sky130A sheet during the build
[run]:

| PDK | Error boxes, hierarchical / flat | Rules | Copies dropped | Top cell's boxes kept | Subcell boxes: in the top's check / flattened check only / information | Flattened check |
|---|---|---|---|---|---|---|
| sky130A | 348 / 324 | 55 | 207 | 25 | 214 / 109 / 0 | 0.9 s |
| gf180mcuD | 252 / 277 | 33 | 165 | 23 | 173 / 56 / 0 | 0.7 s |
| ihp-sg13g2 | 304 / 243 | 32 | 153 | 86 | 218 / 0 / 0 | not run |
| ihp-sg13cmos5l | 91 / 66 | 18 | 34 | 32 | 59 / 0 / 0 | not run |

On 0.6.2's code, the sheets of 0.6.1 (132, 69, 151 and 49 cases) give,
hierarchical / flat: 351 / 334 boxes on sky130A, 248 / 281 on gf180mcuD,
239 / 243 on ihp-sg13g2 and 66 / 66 on ihp-sg13cmos5l. Each hierarchical
count is the top cell's own check (242, 192, 239 and 66 boxes) plus the
subcell boxes that only the flattened check confirms (109, 56, 0 and 0);
224, 177, 218 and 59 subcell boxes are in the top cell's check [run].

**Categories.** Each why-text gets a category under its rule ID (`Magic
DRC / diff/tap.8 / N-well overlap ...`), made only when it holds errors.
Magic's error list has no layer, so each category's description gives
the styles, each rule statement's tech-file line and value, the Magic
types, the GDS layers that the `gdsii` style writes them on, and a line
for each gap-table row (3.5) that holds one of its statements.
`drcjob.gap_rows` finds the rows by the statements' tech-file lines
rather than by the printed ID, because one printed ID can have
statements in several rows (sky130A's `hvi.5`, IHP's `AFil.i`), and one
statement can check two rules. Where a row's key is not the ID that
Magic prints, the line names the row [src]. Rules name types by alias
(`allm1`) or synonym (`m1`), and the `gdsii` style names them by the
first name on the `types` line (`metal1`); `tech_aliases` and
`tech_types` read both from the tech files [src], so the met1.6 items name 68/20 (met1.drawing), 68/13 (met1.res)
and 68/98 (MET1BLOCK) [run].

**A cell Magic reads nothing in.** When every layer of the top cell is
one that Magic's reader ignores, or reads only to type diffusion or poly
that is not there, Magic loads an empty cell and `kmp_job_load` fails
the job (2.2). drcjob recognises the failure "cell X is empty". It adds
`Export/Magic reads nothing in this cell` over the cell's box, lists the
top cell in `Outcome.empty` and gives status 1 in both modes; the failed
job is not cached [src]. On sky130A `s_npc_alone`, the item reads "Magic
reads nothing in cell s_npc_alone. Its layers: 95/20 (npc.drawing):
Magic's reader ignores it (and draws its own when it writes GDS)
(sky130A.tech:3979)" [run].

**Area checks.** `--box L,B,R,T` keeps the errors of the whole-cell check
that touch the area through any placement, because some rules test a
whole shape. On a 100 × 3 µm sky130A n-well with one tap at its left end,
a check of x = 70 to 100 µm alone gave a false `nwell.4` (measured in the
image), and `--box 85,0,100,3` gives none. On every PDK's long-well case,
the backend test asserts that the area result is the whole-cell rows
that touch the area [run]. The exit status counts the error boxes left
after the copy drop, the subcell classes and the area filter, and it
counts a top cell that Magic reads nothing in; export findings do not
change it.

### 3.2 Extraction and LVS

`kmp_extract.tcl` reads the export with its hierarchy and runs `extract
all` and `ext2spice lvs` with the harness's netlist-only settings [src].
Three options change that: `--caps` adds capacitance and coupling,
`--flatglob` runs `gds flatglob *__kmp_*` first, and
`--ports-from-labels` runs `port makeall`. Magic's own flow does not run
`port makeall`, and the report says so. `lvs` then runs `netgen -batch
lvs "<netlist> <cell>" "<schematic> <subckt>" <setup> lvs.out -json`
with the PDK's setup file, which `KMP_NETGEN_SETUP_<PDK>` can set. netgen
exits 0 whatever the result, so `netgen.py` reads the report instead; it
knows every result form in netgen's library (`test_netgen.py`). A layout
matches only on "Circuits match uniquely." or "Circuits match with N
symmetries.", with no property, port, pin or subcell failure after it.

`extract` writes the netlist, after a header line, to `<cell>.magic.spice`
beside the layout (`<cell>.magic.pex.spice` with `--caps`), or to the
file that `-o` names [src]. At the default name, it replaces only a file
whose first line starts with `* Written by klayout_magic_pcells`. Any
other file there, even an empty one, makes it exit 2 with a message that
suggests `-o`; with `-o`, it writes where it is told. `--rdb OUT.lyrdb`
saves the report, also when the job fails [src]. On sky130A, with a
second run (not shown) that replaced the file the first had written
[run]:

```
$ python3 -m klayout_magic_pcells extract out/cases/sky130A/inverters/inv.gds --rdb out/d2/inv_extract.lyrdb
extract: Magic extracted inv (netlist only, sky130A) into /repo/out/cases/sky130A/inverters/inv.magic.spice. The report has 1 item about the export.
...
$ head -2 out/cases/sky130A/inverters/inv.magic.spice
* Written by klayout_magic_pcells 0.6.0: Magic's netlist of inv (netlist only, sky130A) from /repo/out/cases/sky130A/inverters/inv.gds
* NGSPICE file created from inv.ext - technology: sky130A
$ cp out/cases/sky130A/inverters/inv.spice out/cases/sky130A/inverters/inv.magic.spice
$ python3 -m klayout_magic_pcells extract out/cases/sky130A/inverters/inv.gds
...
error: /repo/out/cases/sky130A/inverters/inv.magic.spice exists and klayout_magic_pcells did not write it (its first line is not "* Written by klayout_magic_pcells ..."); pass -o OUT.spice to write the netlist elsewhere, or -o /repo/out/cases/sky130A/inverters/inv.magic.spice to overwrite it
```

**Markers.** netgen's JSON names, for each circuit pair, what it could
not match. `extfile.py` places each of these from the `.ext` files,
through every `use` transform and array step up to the top cell [run,
`test_extfile.py`]: a net at its `node` point, drawn as the net's shape
under that point (a diffusion piece is cut at the gates) or as a 0.02 µm
box; a device at its `device` point; a pin at its `port` box. netgen's
JSON leaves out one pin: on the layout's "(no pins)" row of a pin table
it gives "(no matching pin)" for the schematic pin that the text report
names ("(no pins) | VPWR **Mismatch**"), so `netgen.report_pins` reads
the report's "Subcircuit pins:" tables and `Circuit.pin_pairs` takes the
name from there [run, `test_netgen.py`]. The unit
is the job's `KMP_JOB_SCALE`, not the `.ext` file's `scale` line: for
the same 0.005 µm on all four PDKs, that line's third number is 500000
on sky130A and 0.5 on the others (measured in the image). A backend test
checks on every PDK that each port box holds its GDS text [run]. netgen
names a net of a flattened subcell `<use id>/<net>` and a device `<use
id>/<model>:<index>`; markers of a subcircuit pair that netgen compared
on its own go into that subcell's RDB cell. An inverter with an open
drain, trimmed [run]:

```
$ python3 -m klayout_magic_pcells lvs out/cases/sky130A/inverters/inv_open_drain.gds --schematic out/cases/sky130A/inverters/inv_open_drain.spice -o out/demo/od.lyrdb
lvs: inv_open_drain against inv_open_drain in out/cases/sky130A/inverters/inv_open_drain.spice (sky130A): netgen: Netlists do not match. The layout does not match. 2 markers in the report.
  netgen/net only in the layout: a_300_260#, Magic type ndif at (1.500, 1.300): layout sky130_fd_pr__nfet_01v8 pin 1|3 x1; netgen found no schematic net to pair it with
  netgen/nets that differ: Y, Magic type li at (2.250, 2.600): layout sky130_fd_pr__pfet_01v8_hvt pin 1|3 x1; schematic sky130_fd_pr__nfet_01v8 pin 1|3 x1, sky130_fd_pr__pfet_01v8_hvt pin 1|3 x1
```

**PCells through Magic's GDS reader.** Every job reads the plugin's PCells
from GDS, and for some devices that loses the device: Magic's own cell
extracts as the device, but the same cell, written to GDS and read back,
extracts as another device or none. `ReadbackTest`
(`tests/backend/test_lvs_backend.py`) extracts every device default from
Magic's database, and again after `gds write` and a fresh `gds read`.
`data/readback-<pdk>.json` keeps the differences: 7 of 60 sky130A defaults (the four `cap_vpp_*`, two pd2nw
diodes and an npn's area), 10 of 50 on gf180mcuD (the 10 V asymmetric
FETs, `rm1` to `rm5`, `nwell` and two varactors), 0 of 39 on ihp-sg13g2
and 2 of 31 on ihp-sg13cmos5l (`nmoscl_2`, `nmoscl_4`) [run]. The reports
mark every placement of a listed variant ("Magic's GDS reader does not
keep this device; Magic's own cell extracts as ...").

`lvs` exits 0 on a match, 1 otherwise, and 2 when the input, Magic or
netgen fails; `-o` saves the report in every case. `extract` exits 1
when a placed variant holds a device that the read-back file lists;
export findings do not count toward its status, because every sky130A
layout draws npc 95/20, which Magic's reader ignores [run]. On a cell
that Magic reads nothing in, `lvsjob` recognises "cell X is empty" as
drcjob does: it adds `Export/Magic reads nothing in this cell`, writes no
netlist and gives status 1. `extract` says "Magic reads nothing in
s_npc_alone (sky130A), so there is no netlist", and `lvs` gives a
mismatch without running netgen, with the final result "netgen did not
run: Magic reads nothing in s_npc_alone" [run]. An extraction job takes
0.2 to 0.3 s on an inverter [run]. netgen splits its arguments at
spaces, so a schematic path with a space is copied into the job
directory, and a cache path with a space fails.

### 3.3 Generated layers

Magic reads implants and markers only to decide what each piece of
diffusion and poly is, and draws its own when it writes GDS. So a
missing or undersized implant passes Magic's DRC (the gap studies,
measured in the image). `kmp_rw.tcl` reads the hierarchical export and
writes it back as `rw.gds`. It also flattens a copy with Magic's own
`flatten`, which keeps the device types that Magic gave each cell, and
extracts that copy [src]. KLayout then compares the user's layout with
what Magic wrote and extracted, and reports the findings F1 to F5
below. F1 to F4, and the export's off-grid, read-as-another-type and
cross-cell findings (2.6), set the status to 1:

| RDB category | Finding |
|---|---|
| `F1 implant or marker stops short/<layer>` | an implant or marker encloses a device shape by less than Magic's output grows that layer from it |
| `F2 transistor Magic reads as another device or none` | a drawn gate that Magic extracts as another device, two, or none |
| `F3 shape Magic drops/<layer>` | conductor, poly or diffusion Magic does not write back; cuts with no Magic cut over them, and on sky130A a licon on diffusion with li over it but neither nsdm nor psdm under it; the item gives that cause |
| `F4 conductor Magic adds/<layer>` | conductor Magic writes where none was drawn, such as from a pin box |
| `F5 cuts Magic redrew (information)/<layer>` | cut groups Magic redrew; the text says whether Magic's own cuts meet the cut size and spacing |

**The enclosure rule.** Device shapes come from the user's layers through
the reading rules in `data/devices-<pdk>.json` (sky130A n-diffusion is
diff ∩ nsdm − psdm). For each `generated` row of the PDK's data file (4)
that has `enclosure_check` set, F1 asks for a strip `grow_um − 1 nm`
wide outside each edge of the device shape, except edges that abut the
tech file's exception types (`bloat-or ... 0`), and reports what the
user's layer leaves uncovered. Corners are not measured; the NPC shape
is the 0.17 µm square that Magic centres in the user's cut; and gaps
that Magic fills between two implant shapes are not findings. The rows,
parsed from the gdsii style [src]:

| PDK | Layer: device shape and distance in µm (tech-file line) |
|---|---|
| sky130A | nsdm 93/44 and psdm 94/20: diffusion and tap, 0.125 (846, 845; 841, 840); npc 95/20: poly contact cut, 0.10 (1128); hvtp 78/44: hvt pfet gate, 0.18 (917); lvtn 125/44: lvt gate, 0.18 (892). Rules named: `n/psdm.5a` (diffusion), `n/psdm.5b` (tap), `licon.15`, `hvtp.3`, `lvtn.4b`, after SkyWater's periphery rules (google/skywater-pdk 7198cf6), which write the implant rules `n/ psd.5a` and `n/ psd.5b`; the plugin spells them as the PDK's `sky130A.lydrc` deck does |
| gf180mcuD | nplus 32/0 and pplus 31/0: diffusion 0.16, tap 0.02, gate 0.23 (735, 739, 740; 784, 788, 789); dualgate 55/0: 5 V and 6 V diffusion, 0.24 (810, 811) |
| ihp-sg13g2 | psd 14/0: p-diffusion 0.18, PMOS gate 0.30, p-tap 0.03 (cifout.tech:205, 206, 204); thkox 44/0: HV diffusion, 0.27 (390) |
| ihp-sg13cmos5l | psd 14/0: as ihp-sg13g2 (cifout.tech:144, 145, 143); thkox 44/0: 0.27 (315) |

On sky130A `a_nsdm_flush`, whose nsdm equals the NMOS diffusion [run]:

```
$ python3 -m klayout_magic_pcells layers out/cases/sky130A/gaps/a_nsdm_flush.gds
layers on sky130A, cell a_nsdm_flush: F1 1, F2 0, F3 0, F4 0; F5 0 (information); 2 devices in Magic's extraction; export: 0 off grid, 1 on unread layers, 0 read as another type, 0 cross-cell
F1 nsdm: nsdm around the n-diffusion at (0.400, 1.300)-(2.600, 1.950) stops short. Magic draws nsdm over (0.275, 1.175)-(2.725, 2.075) here, 0.125 um past the n-diffusion; your nsdm leaves 0.7750 um2 of that uncovered. The rule is n/psdm.5a (sky130A.tech:846)
```

A missing implant is an F2 case, since a device shape that an implant
defines lies inside that implant; on `a_no_nsdm`, F2 says "Magic reads
every such gate as a pfet, whatever the well (sky130A.tech:2597)" [run].
A cell that Magic reads nothing in gives the reads-nothing finding (3.1)
and no F1 to F5 (`s_npc_alone` exits 1) [run]. A failed export, a
missing cell, a refused layout (2.6) or reading rules that cannot be
read give status 2, with the reason under `Job/failed` [src]. The
negative controls give no F1 to F4 finding, which the backend test and
the jobs step assert in code [run]. Per PDK, they are the review's seven
standard cells copied from `libs.ref`, a row of them placed by KLayout,
the same row written by Magic, and the clean hand-drawn inverter. On
gf180mcuD, `filltie` gives one F5 item. A switch `"f1"` in
`devices-<pdk>.json` would make F1 information only; it is `"check"` on
all four PDKs [src].

### 3.4 Ports

The port check reads the user's layout in KLayout, not Magic's output,
which rewrites pin datatypes. It compares each cell's texts and pin boxes
with the `ports` table of the PDK's data file, which is built from the
tech file's `labels` and `calma` lines and the KLayout LVS deck's
`labels(...)` calls [src]. On sky130A, for example, Magic takes a text on
a `*/16` pin layer, or over a box on one, as a port; KLayout's LVS reads
names from `*/5`; both accept a `*/5` text over a `*/16` box of the same
layer (except 65/5); and a text on li or met1 drawing names a net in
Magic but makes no port. A text layer that Magic reads onto a type of the
tech file's comment plane names no net: the builder lists it under
`comment`, not `text` (sky130A's text.drawing 83/44; the IHP PDKs' 63/0,
152/0 and 160/0), and such a text is no finding. Magic's netlist of
`sky130_fd_sc_hd__inv_1` has no net named by its cell-name text on 83/44
[run]. The findings are:

- P1: a text that neither tool reads.
- P2: a text that names a net in Magic but makes no port, so netgen
  fails pin matching.
- P3: a Magic port that the KLayout deck can't name (gf180mcuD standard
  cells give it for VNW and VPW on 21/10 and 204/10).
- P4: a pin box with no text, looking at texts on the pin's own layer
  number and on the text layer that a `both` row pairs with the pin
  (sky130A's pwell.label 64/59 for pwell.pin 122/16, where the standard
  cells put VNB).
- P5: a pin box with no drawing under it, which Magic turns into
  conductor and KLayout does not.
- P6: a text over no shape of its layer, looking down the hierarchy.
- P7: texts inside device PCells on a layer that KLayout's flat LVS joins
  by name, with the advice `doports 0`.
- P8, which needs `--magic`: a top-level pin text missing from the ports
  of Magic's `.subckt` line.

P1 to P7 start no job. With `--magic`, a cell that Magic reads nothing in
gives P1 to P7 and the reads-nothing item, and the summary says that P8
did not run [src]. On sky130A `inv`, the check with `--magic` finds
nothing, and Magic's ports are A, Y, VPWR and VGND; `inv_pin_only_li`
gives one P5, and `inv_text_on_pin` one P3 [run].

### 3.5 The gap table

`scripts/gaps.sh [--pdk P]... [--check]` runs `tools/build_gaps.py` in one
container per PDK [src]. Each KLayout deck runs once on a one-box layout
with the harness's switches; on sky130A it also runs with the switches of
KLayout's sky130 > Run DRC (Full) menu entry, and `sky130A.lydrc` runs
too. The categories of a deck's report are its rule list, and a text
scan of the deck gives each name's line and switch. The decks' rules are
joined with Magic's (from `data/pdk-<pdk>.json`) on rule ID through
`tests/gaps/aliases-<pdk>.json`, the only part typed by hand. Both
engines also run on the case suite's `gaps` set, where a case counts the
rules that it reports and its control does not. A case tests the rows of
the rule it targets, but not a row that the target's statement names only
as a later operand of a composite: Magic prints `via.5a` for sky130A's
`via.5a - via.4a`, and a case filed under `via.5a` is not a test of
`via.4a` [src]. Besides "both", "Magic only" and "KLayout only", a rule
can be "both, values differ", "folded" (Magic checks it only inside a
composite rule such as `via.1a + 2 * via.4a`), "measured on other
shapes" (gf180mcuD PP.8a), "same name for another check", or "in the
deck, did not fire on its case". The outputs are `docs/gaps/` and
`data/gaps-<pdk>.json`. The second, which the DRC job reads for its
category descriptions (3.1), has an entry per row that holds a Magic
statement other than as a later operand: the row's status and KLayout
names, the IDs that Magic prints, and the statements' tech-file lines
as `file:line` (schema 2). On 0.6.1 the tables count [run]:

| PDK | both | values differ | folded | other shapes | other check | did not fire | Magic only | KLayout only | rows |
|---|---|---|---|---|---|---|---|---|---|
| sky130A | 76 | 1 | 5 | 0 | 3 | 7 | 93 | 205 | 390 |
| gf180mcuD | 105 | 7 | 8 | 2 | 0 | 3 | 14 | 406 | 545 |
| ihp-sg13g2 | 203 | 0 | 12 | 0 | 1 | 4 | 12 | 130 | 362 |
| ihp-sg13cmos5l | 146 | 0 | 10 | 0 | 1 | 3 | 8 | 114 | 282 |

For 0.6.1, the rows on which the two tools disagreed were checked against
the foundries' published rules (`tests/cases/README.md` names the
sources). The check added aliases on all four PDKs, for rules that the
two tools name differently, and the cases that did not break the rule
they target were redrawn (5.1).

Without the cases' results, the statuses from the deck runs of 0.6.1's
tables agree with the gap studies' tables on 212 of 221 sky130A rows, 46
of 54 gf180mcuD rows, 160 of 162 ihp-sg13g2 rows and 79 of 89
ihp-sg13cmos5l rows, counting only the rows that both name. The
comparison is the one made during the build; on 0.6.0's tables it gave
221 of 228, 46 of 54, 161 of 163 and 79 of 89. Fewer rows compare on
0.6.1 because its alias files put some statements and deck outputs in
rows under other IDs (sky130A's
`var.1` in `varac.1`, `denmos/depmos.2` in `denmos.7`, `sky130A.lydrc`'s
`via1.5a` in `via.5a`; ihp-sg13g2's `x.2` in `grid.Angle45`), and a
study row under the old ID has no row here to compare with. Only
names, values, switches and line numbers of the decks reach the outputs,
which ship under Apache-2.0 (the project lead's decision of 2026-11-23).
`--check` rebuilds everything and exits 1 with `GAPS DIFFER <file>` when a
table would change; during the build, on sky130A, it printed
`GAPS OK sky130A` in 114 s [run].

## 4. The per-PDK data files

`tools/build_pdk_data.py`, which uses only Python's standard library,
writes `data/pdk-<pdk>.json` [src]. Its sources are the Magic tech file
with every `include` expanded, the KLayout `.lyp`, the KLayout LVS deck's
`labels(...)` calls, and `tools/pdk_data_overrides.json`, which names the
device-shape types and rule IDs of the `generated` rows and corrects one
layer (ihp-sg13cmos5l 16/0 reads as `digisub`). The data file holds:

- the sources' SHA-256;
- the grid (0.005 µm on all four PDKs);
- every DRC rule statement, with its line, styles, types, value and
  why-text (sky130A 286, gf180mcuD 202, ihp-sg13g2 367, ihp-sg13cmos5l
  262 [run]);
- each GDS layer's role and how Magic reads it (`paint`, `device-only`,
  `pin`, `text`, `ignored`, `reads-as:<type>`);
- the layers that each Magic type is written on;
- the `generated` rows of 3.3 and the port table of 3.4.

`--check` rebuilds the file in memory and fails on any difference. It
also checks that the installed decks read every switch that the
harness's KLayout DRC `PROFILES` set, which it reads from the harness
with `ast`; on sky130A it printed `PDK DATA OK` and `KLAYOUT DRC PROFILE
OK` [run]. `devices-<pdk>.json`, which holds the reading rules of 3.3,
was typed from the tech file, and each row cites its lines.

## 5. Tests

### 5.1 Test suites

`scripts/test.sh` runs the unit tests and the gap generator's tests, then
`tests/backend` once per PDK [src]. On 0.6.1's code the 380 unit tests
and the gap generator's 18 tests passed, and on 0.6.2's code 401 unit
tests and the same 18 [run]. Two of the unit tests
were skipped: they read a folder of saved netgen reports kept outside
the repository, and run only when `KMP_NETGEN_EVIDENCE` names it. In
0.6.1's run the backend tests ran 95 tests on sky130A in 144 s, 3 of them
skipped, and in 0.6.2's run the same 95 in 150 s [run]. The backend files for the 0.6 checks build their cases
with the case suite, in a temporary folder:

| File | Tests | What they check |
|---|---|---|
| `test_jobs_backend.py` | 7 | the scale; the load checks on the names list; timeout and cancel leave no Magic; two jobs on one key at once; a Tcl error ends the job |
| `test_drc_backend.py` | 17 | one-change cases; the hierarchy cases and `mdrc.tcl` on their export; the long well by area; the names; the error marker; 15-cell batches and an empty child; poll and cancel; RDB boxes against the TSV; the subcell classes; cells Magic reads nothing in; layer hints |
| `test_lvs_backend.py` | 15 | the read-back list; the inverter and its broken variants; two LVS runs on one extraction; port boxes against texts; `--caps`; the cache; the extract command |
| `test_layers_backend.py` | 14 | the negative controls; F1 to F5 cases; the hierarchy cases; the RDB, cache and tmp-* directories; cells Magic reads nothing in; port variants; P8; layers read as another type |

`python3 tests/cases/build.py --pdk P --out DIR [--set S]` draws the case
suite with `klayout.db` at run time and writes `cases.json`; no layout file
is committed. Its sets are `gaps` (the gap studies' one-change cases,
drawn with the geometry of the studies' own builders, except the cases
that 0.6.1 redrew), `hier`, `whole_shape` (a long well per PDK), `names`
(twelve awkward cell names and a missing one), `inverters` (with
schematics and a PCell inverter), `controls` and `sheet`; on sky130A it
built 132, 4, 1, 13, 8, 10 and 1 cases [run]. Each case's `expect`
holds what the studies and the review measured, transcribed once; the
suite never fills it from its own runs (`tests/cases/README.md`). There
are two exceptions. The `expect` of sky130A `inv_text_on_pin`, with A's
text on li1.pin (67/16), is P3, what the case was drawn to give. The
gaps cases that 0.6.1 redrew because they did not break the rule they
target (four on sky130A, four on gf180mcuD), and the two it added
(sky130A `s_m1_huge_space` and its control), have an `expect` that was
measured once on the new shapes in the pinned image and written into
`tests/cases/expect-<pdk>.json` [run].

### 5.2 The harness's jobs step

`tests/jobs/run_jobs.py` is the last step of `tests/parity/run_sweep.py`,
so `scripts/parity.sh --pdk P` runs it; `--no-jobs` skips it, and
`--quick`, `--update-baseline`, `--jobs N` and `--keep` pass through
[src]. It also runs on its own in the image, with `KMP_IMAGE_PDK` set to
the PDK when that is not sky130A: `scripts/in_image.sh 'python3
tests/jobs/run_jobs.py --pdk sky130A --out out/jobs/sky130A [--quick]'`.
It builds the case suite with every set, the PCell inverter and the row
that Magic writes, and runs the cases on a pool of worker processes. The
gaps cases run as the sheet's cells: hierarchical mode checks each
`D<case>` cell as its own top, 15 to a process, and flat mode checks the
flattened sheet. The other sets run case by case in every style and both
modes (the names set in `drc(full)` only). `--quick` builds the
inverters, gaps and controls sets, without the row that Magic writes. It
runs the inverters set and, per PDK, a negative control, an F3 case and
a cell that Magic reads nothing in (gf180mcuD and ihp-sg13cmos5l have no
such case), and it skips the read-back and gap-table checks. The step's
checks are these (`tests/jobs/README.md` says why each exists):

| Check | Passes when |
|---|---|
| `drc_plumbing`, `drc_fidelity` | the first two references of section 1 agree |
| `drc_cells` | the cells in `Outcome.raw` are the export's tree minus `Outcome.empty` |
| `drc_markers` | the RDB's error boxes equal `Outcome.rows`, cell by cell |
| `drc_coverage` | every case has a plumbing result per style and mode and a fidelity result per style |
| `drc_hier`, `drc_names` | the hier set's top-cell listing and devices equal `expect.magic`; each names case gives its one error under its KLayout name |
| `lvs`, `lvs_badnets`, `lvs_markers` | the verdict equals netgen's, as the step's own parser reads it; every net netgen could not match has a marker, which holds the net's `.ext` node point |
| `layers`, `ports` | the findings equal `tests/jobs/expected-<pdk>.json`, which `--update-baseline` rewrites |
| `controls`, `f1_positives`, `reads_nothing`, `ports_expect` | asserted in code, also under `--update-baseline`: no F1 to F4 on a negative control; F1 on every gap-study F1 case; the reads-nothing finding on exactly the cells that should give it; `expect.ports` |
| `readback`, `gaps` | the read-back differs only where `data/readback-<pdk>.json` says; `tools/build_gaps.py --check` passes |

`magic_native.tcl`, the sheet's boxes per mode and every job's time are
recorded, not checked. The step writes `jobs.json`, which the harness puts
into `report.json` as `jobs` and into the "Jobs step" section of
`report.md`. That section gives pass and fail per check, each failure,
the LVS verdicts, what the child cells' own checks add on the hier set,
the read-back and gap-table lines, the cases where `magic_native.tcl`
differs from the plugin, the sheet's boxes per mode and the jobs' times.
The step exits 0 when every check passes, 1 when one fails or a unit of
work raises an exception, and 2 when the step itself fails. On sky130A,
`--quick` ran 11 units of work on 6 workers in 62.5 s, with the jobs'
own times summing to 325 s, and printed `JOBS PASS sky130A` [run].

In the full run of 2026-11-24, on version 0.6.0's code before the changes
that the README's "Last full run" lists, each PDK ran
`scripts/parity.sh --pdk P --jobs 2` in its own container. The four
containers ran at the same time on 6 CPUs, so the times below overlap.
The full jobs step passed on every PDK, and no check failed [run]. The
gap table column gives that run's tables; section 3.5 gives 0.6.1's
counts.

| PDK | Units of work | Checks passed | On 2 workers | Jobs' own times summed | Read-back: measured, differ | Gap table |
|---|---|---|---|---|---|---|
| sky130A | 181 | 1,816 | 454.6 s | 902.9 s | 60, 7 | 398 rules, 130 cases |
| gf180mcuD | 117 | 1,279 | 306.2 s | 608.1 s | 50, 10 | 568 rules, 69 cases |
| ihp-sg13g2 | 201 | 1,944 | 249.8 s | 496.4 s | 39, 0 | 383 rules, 151 cases |
| ihp-sg13cmos5l | 92 | 1,006 | 172.1 s | 340.5 s | 31, 2 | 297 rules, 49 cases |

The summed times leave out the case suite's build, which the figure in
`report.md` adds (about 1 s). Every device that differs on read-back is
one that `data/readback-<pdk>.json` lists. On 0.6.1's code the full
step ran again on each PDK, one PDK at a time on 6 workers, and no check
failed: sky130A ran 183 units of work and passed 1,834 checks, the two
cases that 0.6.1 added accounting for the difference, and the other PDKs
ran the same units of work and passed the same numbers of checks as in
the full run [run]. On 0.6.2's code, after `--update-baseline` on sky130A
and ihp-sg13g2 for the port check's changes (3.4), the full step passed
the same numbers of checks on all four PDKs [run].

### 5.3 Mutations

During the build, each change below was put into the plugin, the jobs
step was run, and the change was reverted. The runs were on sky130A
unless noted [run]:

| Change to the plugin | Caught by |
|---|---|
| DRC boxes shifted 5 nm when Magic's listing is parsed | `--quick`: `drc_plumbing`, `drc_fidelity` |
| DRC markers shifted in the RDB only | `--quick`: `drc_markers` |
| hierarchical mode checks the top cell only | `--quick`: `drc_cells`, `drc_plumbing`, `drc_fidelity` (the last two also on gf180mcuD) |
| the export flattens in hierarchical mode | full step: `drc_coverage` (all 130 gaps cases the suite had then), `drc_fidelity`, `drc_hier` (then called `drc_b1`); plumbing can't see it, as `mdrc.tcl` reads the same flat file |
| `kmp_job_load` without its checks | `--quick`: `reads_nothing`, `layers`; `test_jobs_backend` |
| netgen's verdict from the final line only | `--quick`: `lvs` (`inv_w036`, a property error) |
| the `.ext` unit from its `scale` line | gf180mcuD `--quick`: `lvs_markers`; `test_lvs_backend` |
| the layer check without its Magic-minus-user (F4) or user-minus-Magic (F3) direction | `--quick`: `layers` |
| F1 as Magic's layer minus the user's | `--quick`: `controls`, `layers` |
| `*/16` pin layers, or texts on them, taken as `*/5` | `--quick`: `ports`; for the texts also `ports_expect` |
| F1 with no findings, or as a subtraction, with `--update-baseline` | full step: `f1_positives` or `controls`, exit 1 |

A first round of the same changes, at commit 2610ebf, missed three of
them: the DRC markers shifted in the RDB only, the `.ext` unit from its
`scale` line, and the `*/16` texts. It caught the removed load checks,
the missing F3 direction and the F1 subtraction only in the full step;
under `--update-baseline` it absorbed the loss of the F1 positives; and
the export that flattens in hierarchical mode only lowered the pass
count. After that round, `drc_markers`, `lvs_markers`, `drc_coverage`,
`drc_cells`, `reads_nothing`, `f1_positives`, `ports_expect`, the case
`inv_text_on_pin` and the extra cases of `--quick` were added, and those
changes were run again at e1e4893.

## 6. Decisions and their evidence

The review of the design found two problems that would have given wrong
results, and eight others. Its runs used 1 CPU and 2.5 GB. A test named
below repeats the review's measurement with the 0.6 code.

**6.1 Default DRC mode.** The design made flat mode the default. The
two-level cases of 3.1 showed, on all four PDKs, that flat mode would
call clean a layout that Magic fails, and would disagree with extraction
on the same file. So hierarchical mode is the default, and the export
names the layer that each cell lacks (the cross-cell check of 2.6). The
design called hierarchical mode `per-cell`; `KMP_DRC_MODE=per-cell` is an
error whose message gives the name `hierarchical`.

**6.2 The generated-layer rule.** The design's F1 was "Magic's implant
minus yours". After Magic's read and write-back, that rule left npc
uncovered on the sky130A standard cells `dfxtp_1` (0.0455 µm²) and
`mux2_1` (0.0642 µm²), on a layout that Magic wrote itself, and in
hundreds of pieces on a block of 1,280 placed cells (measured in the
image). Magic's DRC has no rule for the layers that Magic regenerates, so
F1 instead measures the user's enclosure against the distance by which
Magic's gdsii style grows the layer (3.3).

**6.3 The DRC reference.** Comparing the plugin with `mdrc.tcl` on the
same export can't fail on any choice that the two scripts share, so it
serves only as the plumbing check (section 1). Comparing multisets of
boxes is too strict between routes that should agree. On a 126-cell
sheet, KLayout's flat copy gave 349 boxes and Magic's `flatten` gave 348,
and `drc list count total` said 167 where `drc listall why` listed 261
(measured in the image). So the export-fidelity check compares merged
regions per rule, and every RDB gives the count total.

**6.4 Area checks without tiles.** The design checked large cells in tiles
and grew an area check by a halo, which gave the false `nwell.4` of 3.1.
The largest flat check measured took 23.6 s and 317 MB: `drc(full)` of a
250 × 250 µm block of 8,022 placed cells (measured in the image). No
measurement showed a need for tiles.

**6.5 The `.ext` unit, the read-back and cell names.** Taking the unit
from the `scale` line would have misplaced every netgen marker on three
PDKs (3.2). The design tested the read-back on a MOSFET inverter only; the
review found 19 device defaults that extract differently after a GDS round
trip, and `ReadbackTest` found the same 19 [run]. For `--cell
does_not_exist`, Magic printed "Creating new cell" and `mdrc.tcl` finished
normally (measured in the image). So in 0.6 the export renames cells
(2.6), every job checks the cell it loaded (2.2), and the command line
checks `--cell` first (2.4).

**6.6 The rest of the review.** With the design's five gap-table statuses,
each of these would have been "both" (`test_build_gaps.py`): rules with
different values on the two sides (gf180mcuD DF.6), rules that never
fired on their case (sky130A `licon.16`), and rules measured on other
shapes. The review's minor findings gave these parts of 0.6: netgen's
symmetry forms counted as matches (3.2); the flattening of instances that
Magic rounds to 90° (2.6); the port table per layer and datatype (3.4);
the copy drop (3.1; since 0.6.2 below the top cell only), since 225 of
the top cell's 261 sheet boxes equalled boxes of the flat listing; one category per why-text (3.1); F5's check of
Magic's own cuts (3.3); and the job cache key and commands (2.3).

**6.7 Left out of 0.6:** tiling and the halo; reusing DRC results per
cell; a view in KLayout's Netlist Database Browser
(`NetlistComparer.same_nets` could impose netgen's pairing later); a
supplementary KLayout deck; resistance extraction and kpex; a DRC job with ihp-sg13g2's GDS tech file, which
checks drawn implants; replacing PCell variants with Magic's own cells
before extraction.

**6.8 Changes during the build.** Runs of the built code changed five
parts of the design [run]:

- *Subcell boxes.* Counting every box of a subcell's own check as an
  error made the sky130A PCell inverter exit 1 on six met1.6 boxes that
  neither the top cell's check nor flat mode lists. Dropping all boxes
  that the top lacks would lose real ones: on the sheets, the top misses
  109 subcell boxes on sky130A and 56 on gf180mcuD, and the flattened
  check confirms all of them. Hence the three classes of 3.1. On a
  100 µm block of placed standard cells, the flattened check took 8.8 s
  of an 18.1 s run; the block kept its 17,360 errors, and 5 `nwell.4`
  boxes became information.
- *Job directories.* In the first built code, with `KMP_CACHE=0`, `drc`
  and `layers` left a directory per run in the system's temporary
  directory, and `--no-cache` left `run-*` directories that `cache
  prune` kept. A cached job emptied its key's directory and ran there.
  Two workers of the jobs step once ran one DRC job at the same time
  (`a.b` and `a-b` both export to `a_b`): the second removed the first's
  directory, and flat mode reported no error where `mdrc.tcl` found M1.a
  (ihp-sg13cmos5l). The job directories of 2.3 replace that scheme;
  before them, a job in `test_two_jobs_on_one_key_at_once` read the
  other job's `in.gds`.
- *The layer-fit PDK rule.* In one GUI run under Xvfb, a sky130A GDS
  opened with File > Open got the technology sg13g2 (a later run gave
  none; section 7), and the menu checked it as ihp-sg13g2 without
  asking. Rule 2 of 2.5, which lets the technology decide only when the
  layout's shapes fit its PDK, handles that case. The unit test
  `TechnologyAgainstTheLayers` gives the case suite's inverters and hier
  cases each of the other technologies. In
  the closest wrong pair (gf180mcuD's `C_NMOS_flat` labelled sg13g2),
  ihp-sg13g2 counts 0.57 of gf180mcuD's shapes, so a `TECH_FIT` of 1/2
  would have been too low. When mask layers were counted, sky130A got 25
  of gf180mcuD's 35 on gf180mcuD's inverter, because sky130A knows
  gf180mcuD's Metal1, 34/0, as `cmm3.mask`; the fit of 2.5 leaves mask
  layers out.
- *Empty cells as findings.* Failing the job on an empty cell (2.2)
  catches misread names (6.5). But 8 sky130A gaps cases (`s_*_alone`) and
  22 ihp-sg13g2 ones hold only implants or markers, and for those `layers`
  then gave status 2, for what was a correct reading of the file. In 0.6
  they give a finding and status 1 (3.1, 3.3). The jobs step's cell-list
  check (`drc_cells`, 5.2) then found four ihp-sg13g2 sheet cells
  (`DTGO_e`, `DTGO_f` and their `_ok` twins) that `drc` neither checked
  nor listed, because Magic made no cell from them; 0.6 lists them in
  `Outcome.empty`.
- *The cross-cell finder.* When the finder counted cuts, it gave three
  findings on the sky130A PCell inverter, each an mcon over a PCell's tap
  under an implant or well that the PCell draws itself, while Magic read
  the layout as drawn (extraction gave the flattened cell's devices,
  `lvs` matched, and the top's DRC count was 0). With cuts left out, both
  IHP PCell inverters still gave one finding: the top cell's NWell over
  0.3 × 0.06 µm of the pmos PCell's gate poly, although hierarchical
  extraction gave the flattened copy's devices and `lvs` matched. So a
  well counts over diffusion only. On sky130A `inv_base_all_h`, the
  cross-cell boxes went from 10 to 8. The category, which said "drawn in
  its parent" during the build, says "in another cell" in 0.6.

## 7. Open points

All UNVERIFIED:

- **DRC.** Which subcell errors Magic's top-cell check lists, and why it
  misses others; whether a subcell's error that is left out because it
  touches another error of its rule in the top cell's list hides an error
  (3.1).
  Whether the subcell classes of 3.1 hold beyond the case suite and one
  block. Whether Magic's GUI shows met1.6 inside the FET cells of a
  Magic-made inverter. Why Magic makes no cell from the ihp-sg13g2
  `TGO_e` and `TGO_f` cases, and why it gives no DV.9 on gf180mcuD
  `dv9_long` but one DV.9 error when the case's two pfets are 3 µm apart.
  What `drc style` does with an unknown name when no data file checks it.
  How much memory a flat check of a whole chip takes; why a process
  stopped after 98 cells (2.1).
- **Jobs.** A key's directory that is marked done but lacks
  `kmp_drc.json` or `kmp_result.json`, because the process died between
  the rename and that write, is replaced only once that process has
  ended (2.3). So a directory left by a KLayout session that is still
  running keeps its key out of the cache until the session exits; and in
  a container, where a live process can take the dead owner's PID, the
  directory can stay. What left such a directory during the build is not
  known.
- **Extraction and LVS.** The shape of netgen's `badelements`; netgen's
  names for array elements inside flattened paths; which of two devices
  with the same model and nets a marker means. `--caps` values are not
  compared.
- **Generated layers and ports.** On gf180mcuD `C_PMOS_all_h`, Magic's
  `flatten` keeps a `pfet_03v3` that its hierarchical extraction lacks,
  so F2 reports nothing there. F1 on implants that are not rectangles. P1
  covers only texts on layer numbers that the data file knows. The
  ihp-sg13g2 nmos and pmos reading rules cite cifin lines 415 and 442,
  which were not found in the image. KLayout DRC on the negative
  controls. That a well over another cell's poly never changes what
  Magic reads (checked on two IHP inverters).
- **Data and gap table.** Layer roles come from name patterns and planes;
  only the layers that the gap studies named were reviewed. The tap and
  gate distances on gf180mcuD and IHP, and sky130A LVTN, have no case
  except gf180mcuD PP5_ov0. Collecting the `labels(...)` calls ignores
  Ruby conditionals. The data file's `whole_shape` flag, which marks the
  rules that test a whole shape (3.1), is a heuristic. The gap studies
  disagree on some ihp-sg13cmos5l aliases and on gf180mcuD `NAT.6`.
- **Export and PDK choice.** The off-grid finder misses a child vertex
  that an off-grid placement puts back on the grid. The empty-cell test
  relies on Magic's box `0 0 1 1` (2.2). Whether File > Open in the image
  gives a plain GDS a technology (one GUI run gave sg13g2, a later one
  none).
- **GUI.** The GUI was tested on sky130A only, in a KLayout with Qt, so
  these were not tested: the `AbsoluteProgress` path, a browser context
  mode other than `database-top`, and child items drawn in place through
  the parent references (2.7). The screenshot rig (2.4), which drives the
  real GUI under Xvfb, did not drive these: the Yes answer when a second
  check asks whether to cancel the first; Rerun of extraction,
  LVS, layers and ports reports, and of a `.lyrdb` written by the command
  line; the selection-box area and a cell entered with descend. For
  0.6.2 the menu also ran under XFCE on a 1280 × 800 screen, driven with
  xdotool; that run tried the LVS dialog's Browse... button. How long
  `prepare()` blocks KLayout's main thread while it exports a large
  layout.
