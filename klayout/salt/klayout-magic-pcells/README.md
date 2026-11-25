# klayout-magic-pcells

KLayout PCell libraries whose cells are drawn by Magic's own device
generators, one library per PDK:

| PDK | KLayout library | PCells | Magic's generator code |
|---|---|---|---|
| sky130A | `sky130_magic` | 73: 60 devices, 13 box-paint generators | `sky130A.tcl`, namespace `sky130` |
| gf180mcuD | `gf180mcu_magic` | 59: 53 devices, 6 box-paint generators | `gf180mcuD.tcl`, namespace `gf180mcu` |
| ihp-sg13g2 | `sg13g2_magic` | 53: 39 devices, 14 box-paint generators | `ihp-sg13g2.tcl` and the `ihp-sg13g2-*.tcl` files it sources, namespace `sg13g2` |
| ihp-sg13cmos5l | `sg13cmos5l_magic` | 41: 31 devices, 10 box-paint generators | `ihp-sg13cmos5l.tcl` and its `ihp-sg13cmos5l-*.tcl` files, namespace `sg13cmos5l` |

Each PCell asks the PDK's generator in Magic to draw the device, then copies
the GDS that Magic writes into the PCell cell. A device placed in KLayout
therefore has the same polygons and labels as the same device generated in
Magic. The values a device PCell stores are the ones Magic's own parameter
dialog shows after you type yours and press its Create button, and the cell
is the one Create makes. When you edit the instance later, the PCell does
what Magic's "Edit device" dialog does with the change, and the cell is the
one its Apply button makes (see [Values as Magic's dialog shows
them](#values-as-magics-dialog-shows-them)). The box-paint generators are
the via, contact, substrate-contact, guard-ring and well commands of
Magic's "Devices" menus; their PCells take the box size (see [Box-paint
generators](#box-paint-generators)).

The package also runs Magic's own checks on any layout open in KLayout, on
all four PDKs: Magic's DRC, Magic's extraction, and LVS against a
schematic with netgen. Two more checks compare a layout with what Magic
makes of it. One reports implants and markers that Magic draws differently
from the layout, and transistors, shapes and cuts that Magic reads
differently from KLayout; the other reports texts and pin boxes that
Magic, or the PDK's KLayout LVS deck, doesn't read as pins. In KLayout
each check runs from a menu named Magic and shows its results in the
Marker Database Browser, and each also runs from the command line (see
[Checking a layout with Magic](#checking-a-layout-with-magic)). For each
PDK, a generated table lists the DRC rules on which Magic and the PDK's
KLayout decks differ (see [Where KLayout and Magic
disagree](#where-klayout-and-magic-disagree)).

Status: version 0.6.2. The repository is on GitHub as
uoftasic/klayout-magic-pcells. It moved there from vproHacks at 0.6.0, and
GitHub redirects the old URL. The last full run of the parity harness, on
2026-11-24 on version 0.6.0's code, passed all 10,399 points on the four
PDKs. Version 0.6.1 fixed the gap tables and their test cases: rules
that Magic and the KLayout decks name differently share a row, and
test cases that didn't break the rule they target were redrawn. Version
0.6.2 fixes what a trial of the Magic menu for a sky130A layout course
found: findings that the Marker Database Browser cut off, result messages
that used the plugin's internal terms, a browser hidden behind the main
window, DRC
errors of a top cell filed under the standard cells placed in it, false
port findings on the foundry's standard cells, and some wrong or missing
texts. [Last full run](#last-full-run) lists the changes of both versions
and the checks that passed on their code.
The libraries load under `klayout -b -rm`, from the Salt autorun under
`klayout -zz`, and in the full KLayout GUI under Xvfb, where the Magic
menu's entries have also run, on sky130A. [guide.md](guide.md) walks
through installing and using the libraries, with screenshots of that GUI,
including the warning icons that the parameter form shows when Magic
corrects a value.

The design is in [docs/design.md](docs/design.md). It was written for
sky130A alone. The checks, which version 0.6 added, have a design of their
own, [docs/design-0.6.md](docs/design-0.6.md). Where this README and a design
disagree, the README describes the code as it is; the differences are
listed under [Changes from the design](#changes-from-the-design).

## Why Magic is the backend

The PDKs' own KLayout PCells (sky130A's `skywater130`, gf180mcuD's
`gf180mcu`, IHP's `SG13_dev`) draw each device with their own Python code,
so their geometry is independent of Magic's. Several steps that decide
Magic's final geometry happen only when Magic writes GDS, through the
`gdsii` output style of the PDK's Magic tech file:

- contact cuts: the `.mag` of an nfet holds contact areas, and the GDS gets
  the individual cut squares (0.17 µm licon and mcon on sky130A, 0.22 µm
  contacts on gf180mcuD);
- resistor slots on the sky130A high-poly resistors, and the via cut arrays
  of the MIM capacitors;
- label moves from the drawn layer to the contact layer (the sky130A MIM
  cap's C2 is drawn on metal3 and written on 71/5);
- the boundary box made from the `FIXED_BBOX` property (235/4 on sky130A,
  0/0 on gf180mcuD, 189/4 on the IHP PDKs);
- the fixed-layout devices, whose bytes Magic copies from the vendor GDS in
  `libs.ref` (sky130A, gf180mcuD) or draws from layout scripts in
  `libs.tech/magic` (the IHP PDKs).

This library doesn't reproduce those steps in Python. It takes the GDS that
Magic writes as the device, except for its GDS NODE elements: KLayout's GDS
reader drops them, and the vendor GDS of five sky130A fixed devices holds
them (18 to 156 each, on 67/20, 68/20, 69/20 and 70/20). They carry no mask
geometry, and the PCells don't have them. The harness counts them (see
[Tests](#tests)).

## Parity definition

Parity here means: for a given set of typed values, the PCell stores the
values that Magic's own parameter dialog shows after those values are typed
into it (with Return) and its Create button is pressed, and the PCell cell,
flattened, has the same polygons on every GDS layer/datatype, the same
number of shapes on each layer, and the same label texts (string, position,
rotation, mirror, size, justification and font) as the GDS of the cell that
Create makes. For an edit of an existing instance, the same holds for the
values typed into the "Edit device" dialog that Magic reopens on it and the
cell its Apply button makes. For a box-paint
generator, which has no dialog, the reference is the GDS that Magic writes
when the generator is called with no arguments on a box of that size, the
way Magic's menu entries call these generators. The comparison is
an XOR per layer at a common database unit, with no tolerance and no
alignment. KLayout's GDS reader doesn't keep a text's font, so the harness
reads the fonts from the raw GDS records of both files. Cell names,
hierarchy, GDS properties and timestamps are not compared. Versions 0.4 and
earlier compared a device with `magic::gencell` given the typed values; the
harness keeps that as a second reference where it applies (see
[Tests](#tests)).

## Requirements

- KLayout 0.30.5 or later, with Python. Only 0.30.11 has been tested.
- Magic with Tcl. Tested with 8.3.681.
- At least one of the PDKs, as the iic-osic-tools image installs them under
  `/foss/pdks`. Tested: sky130A and gf180mcuD from open_pdks 026824c7,
  ihp-sg13g2 at commit 7e53c777 (tech version 1.0.1), ihp-sg13cmos5l at
  commit ff32f48c (tech version 1.0.0). Other gf180mcu variants (A, B, C, E,
  F) and sky130B are not supported.
- Linux. Windows and macOS are out of scope.
- For use from plain `python3`, the `klayout` pip module (0.30.11 tested).
  The command line's checks (`drc`, `extract`, `lvs`, `layers`, `ports`)
  read the layout with it, so they need it too; the image has it.
- For LVS, netgen with the PDK's netgen setup file
  (`$PDK_ROOT/<pdk>/libs.tech/netgen/<pdk>_setup.tcl`). Tested with netgen
  1.5.323. The other checks don't use netgen.

The image `hpretl/iic-osic-tools@sha256:3c371645b19c6f6564dc8c7b21e39ad1c1833d274fe5b85639afe1ba9d7987e7`
has all of these. The IHP rcfiles in that image end with
`source /foss/tools/osic-multitool/iic-magic-bindkeys`, a file of the image.
In a test of version 0.3 with that line pointing at a file that doesn't
exist, as it would with the IHP PDKs installed elsewhere, the library
registered and generated devices as usual. The stamp digest changed,
because the rcfile is one of the `libs.tech/magic` files it covers (see
[Stamps and audit](#stamps-and-audit)).

## Installing

The repository is a KLayout Salt package (it has a `grain.xml`). Clone it
and link it into the `salt` folder of your KLayout home:

```sh
git clone https://github.com/uoftasic/klayout-magic-pcells.git /path/to/klayout-magic-pcells
mkdir -p ~/.klayout/salt
ln -s /path/to/klayout-magic-pcells ~/.klayout/salt/klayout-magic-pcells
```

In the iic-osic-tools image the folder is `/headless/.klayout/salt/`. The
next time KLayout starts, it runs `pymacros/klayout_magic_pcells.lym`, which
registers a library for every installed PDK. Installing through the Salt
manager or `klayout -y` has not been tried.

Check the setup:

```sh
PYTHONPATH=/path/to/klayout-magic-pcells/python python3 -m klayout_magic_pcells doctor
```

`doctor` prints every setting and where it came from, then, for each
selected PDK, starts Magic, compares the running Magic's device defaults and
box-paint generators with the shipped manifest (the generator list built from
Magic, see [Devices](#devices)), and times one generation (about 20 ms on
sky130A in the image). A line starting `PROBLEM:` names what is missing.
Outside the image, Magic has to be on `PATH` and the PDKs under `PDK_ROOT`
(default `/foss/pdks`), or [Configuration](#configuration) has to say where
they are.

## Usage

**In the GUI**, the libraries are `sky130_magic`, `gf180mcu_magic`,
`sg13g2_magic` and `sg13cmos5l_magic`, and the PCells carry Magic's device
names, such as `sky130_fd_pr__nfet_01v8`, `nfet_03v3` or `sg13_lv_nmos`, and
the box-paint generators' names, such as `via1` or `subconn_guard`. The
libraries aren't bound to a technology, so each is listed under every
technology. [guide.md](guide.md) shows placing and editing devices step by
step.

**In batch**, `klayout -b` skips autorun macros, so name the macro:

```sh
klayout -b -rm /path/to/klayout-magic-pcells/pymacros/klayout_magic_pcells.lym -r my_script.py
```

**From plain Python** with the `klayout` pip module:

```python
import sys
sys.path.insert(0, "/path/to/klayout-magic-pcells/python")
import klayout.db as db
import klayout_magic_pcells as kmp

libs = kmp.register()         # {"sky130A": <library>, "gf180mcuD": <library>, ...}
lib = kmp.register("sky130A") # one PDK: its library, or None with one logged error
ly = db.Layout()
top = ly.create_cell("TOP")
m1 = ly.create_cell("sky130_fd_pr__nfet_01v8", "sky130_magic", {"w": 1.5, "l": 0.5, "nf": 3})
v1 = ly.create_cell("via1", "sky130_magic", {"w": 1.0, "h": 0.5})
top.insert(db.CellInstArray(m1.cell_index(), db.Trans()))
top.insert(db.CellInstArray(v1.cell_index(), db.Trans(db.Vector(3000, 0))))
ly.write("out.gds")
```

`register()` without an argument registers every PDK the configuration
selects (see [Configuration](#configuration)) and returns a dict from PDK to
library, with None for a PDK that couldn't register. Version 0.2's
`register()` returned the sky130A library itself; code that tested it
against None should call `register("sky130A")`.

`create_cell` stores the values it is given and draws what Magic's dialog
makes of them (see [Values as Magic's dialog shows
them](#values-as-magics-dialog-shows-them)). To store the corrected values
too, as the GUI does, pass them through `dialog_values`. To edit that
instance as Magic's "Edit device" dialog and Apply would, change some
values in the result and pass it through `dialog_values` again:

```python
v = kmp.dialog_values("sky130_fd_pr__res_high_po_0p69", {"w": 1.0})  # {"w": 0.69, "val": 1028.0, ..., "kmp_dialog": "..."}
r1 = ly.create_cell("sky130_fd_pr__res_high_po_0p69", "sky130_magic", v)
v2 = kmp.dialog_values("sky130_fd_pr__res_high_po_0p69", dict(v, l=2.0))  # Edit device, then Apply
r2 = ly.create_cell("sky130_fd_pr__res_high_po_0p69", "sky130_magic", v2)
```

`dialog_values(device, values, pdk=None)` needs `pdk` when several
registered libraries have the device.

The package also has a command line, run with `PYTHONPATH` set as for
`doctor` above:

```sh
python3 -m klayout_magic_pcells devices -v            # PCells and their parameters, per PDK
python3 -m klayout_magic_pcells check sky130_fd_pr__nfet_01v8 w=0.1 l=0.1
python3 -m klayout_magic_pcells generate sky130_fd_pr__cap_mim_m3_1 w=5 l=10 -o cap.gds
python3 -m klayout_magic_pcells check --pdk gf180mcuD rm1 w=0
```

A device is looked up in the selected PDKs' manifests; a name that more than
one PDK has (`rm1` to `rm5`, `via1`, `nwell`, ...) needs `--pdk`.

`check` types the values into the device's New device dialog, as the
PCell form does for a new instance, presses Create (see [Values as Magic's
dialog shows them](#values-as-magics-dialog-shows-them)), and shows what
the dialog then shows that differs from what you typed, in Magic's own
text:

```
$ python3 -m klayout_magic_pcells check sky130_fd_pr__nfet_01v8 w=0.1 l=0.1
sky130_fd_pr__nfet_01v8: Magic's dialog shows w=0.42 (entered 0.1)
sky130_fd_pr__nfet_01v8: Magic's dialog shows l=0.15 (entered 0.1)
  message: Mos width must be >= 0.42 um
  message: Mos length must be >= 0.15 um
$ python3 -m klayout_magic_pcells check sky130_fd_pr__res_high_po_0p69 w=1.0
sky130_fd_pr__res_high_po_0p69: Magic's dialog shows w=0.69 (entered 1.0)
sky130_fd_pr__res_high_po_0p69: Magic's dialog sets val=1.028k
  message: Resistor width must be <= 0.690 um
```

For a device with no `_check` proc (ihp-sg13g2's `rm6` and `rm7`) or whose
`_check` raises an error, `check` says so. Magic's `gencell_create` catches
the error and draws with the unchecked values, and so does the PCell. The
manifest probes found `_check` procs that raise "integer value too large to
represent" at `w = 0` on 17 sky130A resistors, on gf180mcuD's `npolyf_s`,
`ppolyf_s` and `rm1` to `rm5`, and on the IHP PDKs' `rsil`, `rppd`, `rhigh`
and `rm1` to `rm5`; IHP's `inductor3` raises at `turns 2.5`.

The dialog can hand `_draw` a value that `_draw` fails on. When Create
writes an empty cell, `check` says so, prints Magic's messages and exits
1:

```
$ python3 -m klayout_magic_pcells check sky130_fd_pr__res_high_po_0p35 val=10000 l=0
sky130_fd_pr__res_high_po_0p35: Magic's dialog shows val=1113.259 (entered 10000.0)
sky130_fd_pr__res_high_po_0p35: Magic's dialog shows l=1.218u (entered 0.0)
sky130_fd_pr__res_high_po_0p35: Magic draws nothing for these values
  message: can't use non-numeric string as operand of "+"
```

For a box-paint generator, `check` reports the box Magic uses after rounding
to its grid (`Magic paints a 0.265 x 1.0 um box (entered 0.263 x 1.0)`), or
`Magic paints nothing` with the generator's message when the box is below
its minimum. `check` exits 0 when Magic draws something, 1 when it draws
nothing or fails, and 2 for a value it refuses or can't parse (`turns=2.5`
for an int, `w=abc`).

Each time KLayout asks a PCell to draw a variant (the cell KLayout makes for
one set of parameter values), the PCell's `produce` call builds the request
for Magic, looks in an in-memory memo and then in the disk cache, and only
then asks Magic. One Magic process (`magic -dnull -noconsole`) runs per PDK
in each KLayout process, started when the library registers. `register()`
starts the processes of all PDKs before it waits for any; with all four PDKs
it took 0.63 s in the image, and one generation takes 15 to 20 ms. Each
Magic process is about 72 MB (measured on sky130A in version 0.2).

## Checking a layout with Magic

The plugin runs Magic's own checks on a layout, from the KLayout GUI or
from the command line. A check writes the cell to a GDS file (the
export), has Magic read that file in a process of its own (`magic -dnull`
with the PDK's rcfile, separate from the PCell libraries' Magic
processes), and puts what it finds into a report database for KLayout's
Marker Database Browser:

| Check | Command | What it reports |
|---|---|---|
| [Magic DRC](#magic-drc) | `drc` | Magic's DRC errors, per rule |
| [Extraction](#extraction) | `extract` | Magic's netlist of the cell |
| [LVS with netgen](#lvs-with-netgen) | `lvs` | netgen's comparison of that netlist with a schematic, with markers on what differs |
| [Generated layers](#generated-layers) | `layers` | implants and markers that Magic draws differently from the layout, and transistors, shapes and cuts that Magic reads differently from KLayout |
| [Ports](#ports) | `ports` | texts and pin boxes that Magic, or the PDK's KLayout LVS deck, doesn't read as pins |

**In the GUI** they are in a menu named Magic, which the autorun macro
inserts before Help: Run Magic DRC..., Check the visible area with Magic
DRC, Extract with Magic..., LVS with netgen..., Check generated layers,
Check ports, Rule differences (the [gap
table](#where-klayout-and-magic-disagree) of the layout's PDK) and
Settings... (each setting, its value and where it comes from; read-only).
An entry checks the current cell of the current view as it is in memory,
unsaved edits included, on the PDK that the command line would choose (see
the rules below). Where those rules end in a guess, the menu doesn't take
it: a dialog asks for the PDK, with the guess preselected, and the answer
holds for that layout until KLayout closes. While Magic runs, a progress
dialog shows the stage and the seconds elapsed, KLayout stays usable, and
the dialog's Cancel button stops Magic. One check runs at a time in a
view; starting another asks whether to cancel the first. When a check
ends, the Marker Database Browser opens on its report and a message gives
the result: a first line in plain words, such as "In a_no_nsdm: 1
transistor that Magic reads as another device or none; 2 shapes or cuts
that Magic drops (licon1.drawing).", then the summary that the command
line prints. When the message is closed, the plugin brings the browser in
front of the main window. The browser is a window of its own, not a
dialog of the main window, and under XFCE a maximised main window that
gets the focus back from the message would otherwise cover it. Each
check's section below says what its entry asks. The windows that show text (Magic's
netlist, netgen's report, Rule differences, Settings...) open no larger
than the screen and can be maximised. There is no menu without a main
window (`klayout -b`, plain `python3`), and `KMP_MENU=0` leaves it out.

**On the command line**, with `PYTHONPATH` set as for `doctor`:

```sh
python3 -m klayout_magic_pcells drc     FILE [--cell C]... [--style S] [--mode hierarchical|flat] [--box L,B,R,T] [-o OUT.lyrdb] [--tsv OUT.tsv] [--no-cache]
python3 -m klayout_magic_pcells extract FILE [--cell C] [--caps] [--flatglob] [--ports-from-labels] [-o OUT.spice] [--rdb OUT.lyrdb] [--no-cache]
python3 -m klayout_magic_pcells lvs     FILE --schematic SCH [--schematic-cell C] [--cell C] [--flatglob] [--ports-from-labels] [-o OUT.lyrdb] [--report OUT.txt] [--json OUT.json] [--no-cache]
python3 -m klayout_magic_pcells layers  FILE [--cell C] [-o OUT.lyrdb] [--json OUT.json] [--no-cache]
python3 -m klayout_magic_pcells ports   FILE [--cell C] [--magic] [-o OUT.lyrdb] [--json OUT.json]
```

`--cell` defaults to the file's top cell. A file with several top cells
needs it, and a cell the file doesn't have exits 2 before Magic starts
(`error: cell nosuch is not in /repo/out/cases/sky130A/hier/inv_base_all_h.gds`).
Every command takes `--pdk`. Without it, the command takes the PDK from
the first of these that names one: the layout's technology, its PCell
libraries (live or `<defunct>`), the names of its PCell variant cells
(`<device>__kmp_<8 hex>`), `KMP_PDKS` when that selects one PDK, and the
`PDK` variable. The technology counts only when the layout's shapes fit
its PDK. For each PDK, the plugin counts the shapes on the layers that the
PDK's data file (`python/klayout_magic_pcells/data/pdk-<pdk>.json`)
knows, leaving out text, boundary and `*.mask` layers. When the
technology's PDK gets less than 3/4 of the count of the PDK that fits
best, the technology is set aside, and the best-fitting PDK takes the place
of the `PDK` variable at the end of the list. The two IHP PDKs share their
layer numbers, so between them the technology still decides. The last
entry of the list, the `PDK` variable or the best-fitting PDK in its
place, is a guess, and the command says so on stderr:

```
note: PDK sky130A, a guess from the PDK variable (PDK=sky130A): the layout names no technology and no PCell library; give --pdk to choose another
```

The [case suite](#the-case-suite) is the set of test layouts that
`tests/cases/build.py` draws. Its files carry no technology, so its
sky130A inverter was given the technology `sg13g2` and run through the PDK
choice in Python. It came out as sky130A, with the reason "a guess from
the layers: the layout's technology is sg13g2 (ihp-sg13g2), but 0% of its
shapes are on ihp-sg13g2's layers and 89% on sky130A's". In the GUI, the
PDK dialog then opens with that sentence and sky130A preselected. A
script, or a course checker, should give `--pdk`.

Every command exits 0 when the check finds nothing, 1 when it finds
something, and 2 when the input or a job fails; each check's section says
what counts. A `.lyrdb` file opens next to its layout with
`klayout LAYOUT -m FILE.lyrdb`; with `-m` before the layout, KLayout puts
the database in an empty view of its own. The database's rerun record (its "generator") is a KLayout Recipe
named `klayout_magic_pcells`, and its description gives the command line
that reproduces the run. The autorun macro registers that Recipe, and in
the GUI the browser's Rerun button (F5) runs the same check again on the
layout in the view and replaces the report. This was tried on a DRC report
made from the menu; Rerun of the other checks' reports, and of a `.lyrdb`
written on the command line and then opened in KLayout, hasn't been tried.

In the browser, an item's text is split into lines: one per sentence or
clause, and a sentence longer than 80 characters into lines of about
equal length. KLayout's Info pane shows each line of an item as it is,
without wrapping, and cuts a line after 200 characters, which would cut
off the last sentence of a long finding, such as "To fix it, draw nsdm
(93/44) over the n-diffusion, 0.125 um past it." In a browser maximised
on a 1280 × 800 screen the Info pane starts about 270 pixels wide;
dragging the splitter between Directory and Markers to the left widens
it, and with the pane about 890 pixels wide every line of that finding
showed whole. The command line and `--json` give each text on one
line. An item that is
information rather than a finding of its check is marked waived and
visited. KLayout's browser counts every item, so a category's total
still includes them, but it writes how many are waived after a dash, draws
a category that holds only such items in green, and leaves them out of
the number in parentheses, the items not yet looked at. On a cell with
two `li.5` error boxes and an npc shape, the total reads "3 (2) - 1". The information items are the export's findings that don't change
the check's exit status, everything under "Magic said", and what each
check's section below calls information.

The examples below ran in the image listed under
[Requirements](#requirements), on the layouts of the [case
suite](#the-case-suite), built with `python3 tests/cases/build.py --pdk
sky130A --out out/cases/sky130A` and run in the folder of each file, with
`KMP_CACHE_DIR` set to a folder under `out/docs2`.

### The exported file and its findings

The exported file has no KLayout context information and no timestamps.
Cells whose names Magic can't load (anything but letters, digits, `_` and
`$`) are renamed in it, and instances with a rotation that isn't a
multiple of 90° or with a magnification are flattened, since Magic can't
place them. Before Magic starts, the export also looks for what Magic will
read differently from KLayout. `drc`, `extract`, `lvs` and `layers` put
these findings into their database (`ports` reports only its own, and with
`--magic` "Magic reads nothing in this cell"):

| Category | What it holds |
|---|---|
| Export/Magic snaps this shape to its 5 nm grid | vertices off the PDK's 5 nm grid, which Magic moves when it reads the file |
| Export/Magic does not read this layer | shapes on layers that Magic's GDS reader ignores, such as sky130A's npc (95/20), which Magic draws itself when it writes GDS |
| Export/Magic reads this layer as another type | for example 16/0 on the IHP PDKs, which Magic reads as `digisub` |
| Export/Magic reads this cell without a layer drawn in another cell | an implant or marker shape of one cell (a parent, a child or a sibling) over the diffusion or poly of another cell that doesn't draw that layer there itself, or a well shape over the other cell's diffusion. Magic decides device types inside each cell from that cell's shapes alone, so it reads the other cell without the layer (see [Magic DRC](#magic-drc)). Cuts don't count: a contact takes its type from the diffusion or poly under it in its own cell |
| Export/instances flattened for Magic | the flattened instances |
| Export/cells renamed for Magic | each renamed cell and its name in the file |
| Export/error-marker cells | PCell variants that failed (the 255/0 error marker, see [If Magic is missing or fails](#if-magic-is-missing-or-fails)); every check that runs Magic refuses such a layout and exits 2, since Magic would check it without those devices |
| Export/Magic reads nothing in this cell | a top cell of which Magic's GDS reader keeps no shape: every layer it draws is one the reader ignores, or one it uses only to decide what the diffusion or poly under it is, and there is none. The item names each layer, what the reader does with it and the tech-file line. `drc` (both modes), `extract`, `lvs`, `layers` and `ports --magic` report it after Magic has loaded the cell (below) |
| Magic said | Magic's messages from the job, without the warning that it gives on every GDS read ("Calma reading is not undoable") |

Each Magic process then checks that the cell it loaded is the one it was
given (the name is in Magic's cell list before `load`, the loaded cell has
that name, and its bounding box isn't empty) and fails the job otherwise,
so a cell that Magic can't find or loads empty never gives a clean result.
When the top cell loads empty because Magic's reader keeps none of its
shapes, `drc`, `extract`, `lvs`, `layers` and `ports --magic` turn that
failed job into the finding "Magic reads nothing in this cell", check
nothing, and exit 1. `extract` then writes no netlist, and `lvs` says that
the layout does not match, without running netgen, and writes no
`--report`. On the case suite's sky130A `s_npc_alone`, which holds only
npc, with a schematic `npc.spice` that holds `.subckt s_npc_alone A` and
no device:

```
$ python3 -m klayout_magic_pcells extract s_npc_alone.gds --pdk sky130A
extract: Magic reads nothing in s_npc_alone (sky130A), so there is no netlist.
  Export/Magic reads nothing in this cell: Magic reads nothing in cell s_npc_alone. Its layers: 95/20 (npc.drawing): Magic's reader ignores it (and draws its own when it writes GDS) (sky130A.tech:3979)
  Export/Magic does not read this layer: 1 item
$ python3 -m klayout_magic_pcells lvs s_npc_alone.gds --pdk sky130A --schematic npc.spice --json npc.lvs.json
lvs: Magic reads nothing in s_npc_alone (sky130A), so there is no netlist to compare with s_npc_alone in npc.spice. The layout does not match.
  Export/Magic reads nothing in this cell: Magic reads nothing in cell s_npc_alone. Its layers: 95/20 (npc.drawing): Magic's reader ignores it (and draws its own when it writes GDS) (sky130A.tech:3979)
  Export/Magic does not read this layer: 1 item
```

Both exit 1. In `npc.lvs.json` the verdict has `matched` false and the
final result "netgen did not run: Magic reads nothing in s_npc_alone".

Each check runs Magic in a job directory under the cache (see [Job
directories](#job-directories)), and a second run of an unchanged cell with
the same options reads the results from there: on version 0.6.0's code,
the first DRC example below took 1.6 s the first time, its check of the
flattened layout included, and 0.2 s the second, while other containers
ran on the same machine.

### Magic DRC

`drc` checks the cell with Magic's DRC in the style `KMP_DRC_STYLE`
(default `drc(full)`; `--style` chooses another), each cell with a 10 µm
margin around it as the parity harness's DRC step does. There are two
modes:

- **Hierarchical**, the default, is Magic's own reading of the file: a
  plain `gds read`, then every cell under the top cell is loaded and checked
  as Magic's edit cell, children first, and the top cell last. The top
  cell keeps every box of its own check, the list that Magic's `drc check`
  gives on the loaded top cell. A box from a subcell's own check is left
  out when the top cell's list has a box of the same rule that overlaps or
  touches it through some placement, since the top cell's box reports it.
  The other boxes of a subcell go into that cell in the database, in its
  own coordinates, with references to its placements: as errors when
  Magic's check of the flattened layout has a box of their rule there, and
  the item then says that the check from the top cell misses it, and
  otherwise as information only, in the category "Magic DRC/<rule>/only
  when <cell> is checked on its own", which doesn't count in the error
  total, the exit status or the TSV. Below the top cell, a box in a
  parent's list that is exactly a box of one of its subcells, seen through
  the instance, is left out of the parent. The check of the flattened
  layout is one more Magic job, run only when some subcell box isn't in the
  top cell's list. So when the top cell has no tap, its latch-up and tap
  errors are in the top cell, even where each standard cell placed in it,
  checked on its own, lists the same errors.
- **Flat** (`--mode flat`) is Magic's verdict on the flattened mask:
  KLayout flattens a copy of the cell and Magic checks that one cell.

Hierarchical is the default because Magic's GDS reader decides what each
piece of diffusion and poly is inside each cell, from that cell's own
implants and wells. A layout whose implants or well sit in a parent cell
over transistors in a child reads differently to Magic than its flattened
mask does. The case suite's `hier` set has such layouts on every PDK: a
clean inverter (the flat original) with some layers moved into a parent
cell and the rest in a child cell placed at the origin. Flat mode found
nothing on any of them. Magic's own reading of the cells with moved layers
gave other transistors and errors, except on three gf180mcuD cases:
`C_NMOS_nw_h` and `C_PMOS_imp_h` read as drawn, and on `C_PMOS_all_h`,
which extracts no transistor, only the child's own check lists boxes, all
of them information. `drc` in both modes and `extract` gave, with the
boxes that are information only after the semicolon (the DRC columns
measured on 0.6.2's code):

| PDK | Case | Layers in the parent | Hierarchical | Flat | Transistors Magic extracts |
|---|---|---|---|---|---|
| sky130A | `inv_base` | none (the flat original) | no errors | no errors | `nfet_01v8`, `pfet_01v8_hvt` |
| | `inv_base_imp_h` | nsdm, psdm | 28 boxes, 7 rules; 20 | no errors | `pfet_01v8`, `pfet_01v8_hvt` |
| | `inv_base_nw_h` | nwell | 26 boxes, 4 rules; 16 | no errors | `nfet_01v8` |
| | `inv_base_all_h` | nsdm, psdm, nwell, hvtp, npc | 36 boxes, 7 rules; 40 | no errors | two `pfet_01v8` |
| gf180mcuD | `C_NMOS`, `C_PMOS` | none | no errors | no errors | `nfet_03v3`; `pfet_03v3` |
| | `C_NMOS_imp_h` | NPLUS, PPLUS | 10 boxes, 3 rules; 11 | no errors | none |
| | `C_NMOS_all_h` | NPLUS, PPLUS, NWELL, DUALGATE | 10 boxes, 3 rules; 11 | no errors | none |
| | `C_PMOS_nw_h` | NWELL | 77 boxes, 9 rules; 4 | no errors | none |
| | `C_PMOS_all_h` | NPLUS, PPLUS, NWELL, DUALGATE | no errors; 11 | no errors | none |
| | `C_NMOS_nw_h` | NWELL | no errors | no errors | `nfet_03v3` |
| | `C_PMOS_imp_h` | NPLUS, PPLUS | no errors | no errors | `pfet_03v3` |
| ihp-sg13g2 | `inv` | none | no errors | no errors | `sg13_lv_nmos`, `sg13_lv_pmos` |
| | `inv_psd_h` | pSD | 14 boxes, 2 rules | no errors | `sg13_lv_nmos` |
| | `inv_nw_h` | NWell | 26 boxes, 3 rules | no errors | `sg13_lv_nmos` |
| | `inv_all_h` | pSD, NWell, ThickGateOx | 23 boxes, 3 rules | no errors | two `sg13_lv_nmos` |
| ihp-sg13cmos5l | `base` | none | no errors | no errors | `sg13_lv_nmos`, `sg13_lv_pmos` |
| | `base_psd_h` | pSD | 14 boxes, 2 rules | no errors | `sg13_lv_nmos` |
| | `base_nw_h` | NWell | 25 boxes, 3 rules | no errors | `sg13_lv_nmos` |
| | `base_all_h` | pSD, NWell, ThickGateOx | 21 boxes, 3 rules | no errors | two `sg13_lv_nmos` |

In hierarchical mode the export also reports each place where Magic reads
a cell without a layer drawn in another cell (8 on `inv_base_all_h`), and
the [generated-layer check](#generated-layers) names the transistors that
change.

Hierarchical mode also lists more than Magic's check of the top cell alone,
which is what `drc check` gives on the loaded top cell in Magic, and every
DRC database says so in its description: "this mode checks every cell and
then the top cell; Magic's check from the top cell alone can report fewer
errors". On the case suite's DRC sheets (132, 69, 151 and 49 cases, each
a subcell, 40 µm apart), in `drc(full)`, 0.6.2's code gave:

| PDK | Hierarchical | Subcell boxes in the top cell's list | Subcell boxes only in the flattened layout's check | The top cell's own check | Flat |
|---|---|---|---|---|---|
| sky130A | 351 boxes, 57 rules | 224 | 109 | 242 boxes, 53 rules | 334 boxes, 57 rules |
| gf180mcuD | 248 boxes, 34 rules | 177 | 56 | 192 boxes, 34 rules | 281 boxes, 34 rules |
| ihp-sg13g2 | 239 boxes, 32 rules | 218 | 0 (not run) | 239 boxes, 32 rules | 243 boxes, 32 rules |
| ihp-sg13cmos5l | 66 boxes, 18 rules | 59 | 0 (not run) | 66 boxes, 18 rules | 66 boxes, 18 rules |

Each hierarchical count is the top cell's own check plus the subcell boxes
that only the check of the flattened layout confirms. On sky130A and
gf180mcuD the subcells' own checks list such boxes, which the check from
the top cell misses. On the IHP sheets every subcell box overlaps or
touches a box of its rule in the top cell's list, so that check didn't run
there. No sheet box is information only. On every PDK the hierarchical and
flat modes listed the same rules.

```
$ python3 -m klayout_magic_pcells drc inv_base_all_h.gds --tsv -
note: PDK sky130A, a guess from the PDK variable (PDK=sky130A): the layout names no technology and no PCell library; give --pdk to choose another
cell	rule	why	l	b	r	t
inv_base_all_h	nwell.2a	N-well spacing < 1.27um (nwell.2a)	1.17	3.37	1.68	3.4
inv_base_all_h	nwell.2a	N-well spacing < 1.27um (nwell.2a)	0	3	1.68	3.37
...
inv_base_all_h	poly.4	poly spacing to Diffusion < 0.075um (poly.4)	1.5	3.5	1.575	3.575
Magic DRC (drc(full), hierarchical) of inv_base_all_h on sky130A: 36 error boxes, 7 rules, in 1 cell. inv_base_all_h: 36 error boxes; Magic's drc list count total 5 in the top cell, 7 over the 2 cells checked; of the 47 boxes the subcells' own checks list, 7 are in the top cell's check (reported there), 0 only in the flattened layout's check, 40 only when the subcell is checked on its own (information, not counted). The export has 9 findings (category Export).
$ python3 -m klayout_magic_pcells drc inv_base_all_h.gds --mode flat
note: PDK sky130A, a guess from the PDK variable (PDK=sky130A): the layout names no technology and no PCell library; give --pdk to choose another
Magic DRC (drc(full), flat) of inv_base_all_h on sky130A: no errors. inv_base_all_h: 0 error boxes; Magic's drc list count total 0 in the top cell. The export has 1 finding (category Export).
```

The first exits 1, the second 0. In the first, the 7 boxes of the child
cell's own check that the top cell's check also lists are left out, and
the 40 boxes that only the child cell's own check lists (`diff/tap.8` 36,
`nwell.1` 2, `LU.3` 2) are information under "only when inv_base_all_dev
is checked on its own". The last line goes to stderr; `-o OUT.lyrdb` writes the database and
`--tsv OUT.tsv` the error boxes (`-` for stdout): a header row, then the
cell, the rule ID, Magic's message and the box in µm, tab-separated,
children first. `--cell` can be given more than
once; each cell is checked as a top cell of its own, into one database.

**Menu:** Magic > Run Magic DRC... asks for the style (the PDK's
`drc(fast)`, `drc(full)` and `drc(routing)`), the mode and the area (the
whole cell, the area the view shows, or the bounding box of the
selection), and keeps the choices for the next run; until it has been used,
`KMP_DRC_STYLE` and `KMP_DRC_MODE` give them. Magic > Check the visible
area with Magic DRC checks the area the view shows with the last style and
mode, without asking. The message at the end lists, per subcell, the boxes
that are information only, by rule. During the check of the flattened
layout the progress dialog reads `flattened <cell>:` and Magic's stage.

**Area checks.** `--box L,B,R,T` (µm, in the top cell's coordinates) keeps
the errors of a whole-cell check that touch the area. Magic still checks
the whole cell, and since the job directory doesn't depend on the area,
the next area check of an unchanged cell doesn't start Magic. Checking only
the area would give wrong results for rules about a whole shape. sky130A's
`nwell.4` requires a tap somewhere in each n-well; the case suite's
100 × 3 µm n-well has one tap, at its left end, and an area check at its
right end reports no error:

```
$ python3 -m klayout_magic_pcells drc nwtap.gds --pdk sky130A --box 85,0,100,3
Magic DRC (drc(full), hierarchical) of nwtap on sky130A in the area 85,0,100,3 um: no errors. nwtap: 0 error boxes; Magic's drc list count total 0 in the top cell.
```

**Categories.** "Magic DRC", then the rule ID, then Magic's message (its
"why-text"). The rule ID is the text in the message's last parentheses
(`diff/tap.8`, `licon.9 + psdm.5a`, `Grid Rules`); a message with no ID,
such as `Can't overlap those layers`, is a category of its own under
"Magic DRC". A rule's description names its styles, each tech-file
statement (file, line, keyword, types and value), and the Magic types and
GDS layers it checks. Then comes one `Gap table:` line for each row of the
[gap table](#where-klayout-and-magic-disagree) that holds one of its
statements, with the row's status and KLayout names:

```
Magic: All nwells must contain metal-connected N+ taps (nwell.4)
In the styles: drc(full) (drc(full) only)
Tech file sky130A.tech:4199: cifmaxwidth nwell_missing_tap 0 um
Magic types: nwell_missing_tap
Gap table: Magic only
```

The check finds a row by the tech-file line of the statement, not by the
ID that Magic prints, because one printed ID can stand for more than one
rule. sky130A's Magic prints `hvi.5` both for the spacing between two HVI
areas, which SkyWater's rules call `hvi.2a`, and for HVI to an LV
n-well, their `hvi.5`, and the gap table has a row for each. Where a
row's rule ID isn't the one that Magic prints, the line names the row:

```
Magic: HVI to HVI spacing < 0.7um (hvi.5)
In the styles: drc(full) (drc(full) only)
Tech file sky130A.tech:4266: cifspacing drawn_hvi drawn_hvi 0.7 um
Magic types: drawn_hvi
Gap table: both (row hvi.2a); KLayout: sky130A_mr.drc: hvi.2a (0.7); sky130A.lydrc: hvi.2 (0.7)
```

`HVI to LV nwell spacing < 0.7um (hvi.5)` gets `Gap table: Magic only`.
A statement that checks two rules gives a line for each of their rows:
sky130A's message that ends in `(nwell.5a, 7)` is about the rules
`nwell.5a` and `nwell.7`. A composite rule such as
`via.1a + 2 * via.4a` gives a line for the first rule's row only. A
message with no statement in the PDK's data file (`data/pdk-<pdk>.json`)
gets the row named by its rule ID.

Magic's error list has no layer, so an item's text names the types and
layers instead. The layers are those the tech file's GDS output style
writes for the rule's types, found through the type names and synonyms
of the tech file's `types` and `aliases` sections: `nwell.2a` checks
`allnwell`, which gives 64/20 (nwell.drawing) and 82/44 (pnp.drawing). The
boxes that are information only sit under "Magic DRC/<rule>/only when
<cell> is checked on its own". A job that fails puts its reason under
"Magic DRC did not run". "Magic said" holds Magic's messages; those of the
check of the flattened layout start with "on the flattened layout:". The
database's description, on one line, names the PDK, the Magic, tech and
PDK versions, the style and the mode, and for each cell checked the boxes
kept and dropped, how the subcells' boxes were sorted, Magic's
`drc list count total`, the cells Magic read as empty, and where the
exported file and the flattened check's files are, with "(removed when
the check ends; KMP_JOB_KEEP=1 keeps it)" after a path in a `tmp-*`
directory. It ends with the command line that runs the check again,
`--pdk` included.

**Exit status.** 0 when no error box is left after the copies, the
subcell boxes that the top cell's check covers, the information boxes
and the area are taken out, 1 when some are or when
Magic reads nothing in the top cell, 2 for a failed input or job: a missing
`--cell`, a style the PDK doesn't have (`sky130A has no DRC style drc(nope)
(it has drc(fast), drc(full), drc(routing))`), error-marker cells, a job
that fails or is cancelled. The export's findings don't change it.

**Limits.**

- Magic lists one violation as one or more boxes, and the two modes cut
  them differently, so compare rules rather than box counts.
- A subcell checked alone can list boxes that its placement removes: in
  the case suite's sky130A inverter built from this package's PCells
  (`inverters/inv_pcell.gds`), the two transistor cells checked alone have
  6 `met1.6` (metal1 minimum area) boxes, which neither the top cell's
  check nor the flattened layout's has. They are information, and `drc`
  exits 0 on that file.
- A subcell's box counts as listed by the top cell's check when a box of
  its rule there overlaps or touches it, and is then left out of the
  report. A box of another error of the same rule that touches it is
  enough, so when a subcell's error touches a different error of the same
  rule in the top cell's list, the report shows only the top cell's box.
  Whether that hides an error on the case suite's layouts is UNVERIFIED.
- A subcell that Magic reads as empty isn't checked, and the description
  lists it, as it lists a cell of the export that Magic's reading of the
  file has no cell for. On the ihp-sg13g2 sheet, the 22 cases that Magic
  reads nothing in are listed that way, four of them (`TGO_e`, `TGO_f` and
  their controls) because Magic's reading has no cell for them.
- One Magic process checks at most 15 cells; a larger tree takes several
  processes, one after another (9 for the sky130A sheet, which held 130
  cases, in a run during version 0.6's development), and the check of
  the flattened layout, when it runs, costs about as much as
  `--mode flat`. Measured during version 0.6's development on a 100 µm
  block of sky130A standard cells, that check took 8.8 s of an 18.1 s
  run, as long as `--mode flat`
  alone; it ran there because a standard cell checked on its own has no
  tap. There is no tiling: Magic checks the whole cell.
- The Marker Database Browser shows a subcell's errors at one placement of
  that cell (see [Known limitations](#known-limitations)).

### Extraction

`extract` has Magic read the export with its hierarchy (`gds read`,
`load`), run `extract all`, and write a SPICE netlist with `ext2spice lvs`:
devices and nets, no capacitance, resistance or length, as in the parity
harness's extraction check. `--caps` adds parasitic capacitance (`extract
do capacitance`, `extract do coupling`, `ext2spice cthresh 0`).
`--flatglob` runs `gds flatglob *__kmp_*` before the read, which flattens
the PCell variants into their parents. `--ports-from-labels` runs `port
makeall` after the load, which makes every label a port, something Magic's
own flow doesn't do (see [Ports](#ports)).

`-o OUT.spice` names the netlist file. Without it, `extract` writes
`<cell>.magic.spice` (`<cell>.magic.pex.spice` with `--caps`) next to the
layout file. Every netlist file it writes starts with a header line that
names the plugin's version, the cell, the kind of netlist, the PDK and the
layout. At the default name, `extract` replaces a file that starts with
that header and refuses any other file, an empty one included, with exit
2; `-o` writes where it is told. In the case suite's `inverters` folder,
next to the schematic `inv.spice`:

```
$ python3 -m klayout_magic_pcells extract inv.gds --pdk sky130A
extract: Magic extracted inv (netlist only, sky130A) into /repo/out/cases/sky130A/inverters/inv.magic.spice. The report has 1 item about the export.
netlist: /repo/out/cases/sky130A/inverters/inv.magic.spice
  Export/Magic does not read this layer: 1 item
$ head -3 inv.magic.spice
* Written by klayout_magic_pcells 0.6.0: Magic's netlist of inv (netlist only, sky130A) from /repo/out/cases/sky130A/inverters/inv.gds
* NGSPICE file created from inv.ext - technology: sky130A

$ python3 -m klayout_magic_pcells extract inv.gds --pdk sky130A -o inv_extracted.spice
extract: Magic extracted inv (netlist only, sky130A) into inv_extracted.spice. The report has 1 item about the export.
netlist: inv_extracted.spice
  Export/Magic does not read this layer: 1 item
$ cat inv_extracted.spice
* Written by klayout_magic_pcells 0.6.0: Magic's netlist of inv (netlist only, sky130A) from /repo/out/cases/sky130A/inverters/inv.gds
* NGSPICE file created from inv.ext - technology: sky130A

.subckt inv A Y VPWR VGND
X0 Y A VGND VGND sky130_fd_pr__nfet_01v8 ad=0.715 pd=3.5 as=0.6175 ps=3.2 w=0.65 l=0.15
X1 Y A VPWR VPWR sky130_fd_pr__pfet_01v8_hvt ad=1.1 pd=4.2 as=0.95 ps=3.9 w=1 l=0.15
.ends
```

With a file that the plugin didn't write at the default name, here a
one-line `inv.magic.pex.spice`, the netlist isn't written:

```
$ python3 -m klayout_magic_pcells extract inv.gds --pdk sky130A --caps
extract: Magic extracted inv (with parasitic capacitance, sky130A). The report has 1 item about the export.
error: /repo/out/cases/sky130A/inverters/inv.magic.pex.spice exists and klayout_magic_pcells did not write it (its first line is not "* Written by klayout_magic_pcells ..."); pass -o OUT.spice to write the netlist elsewhere, or -o /repo/out/cases/sky130A/inverters/inv.magic.pex.spice to overwrite it
```

The schematic `inv.spice` kept its MD5 sum through these runs. With `--caps` the same
cell's netlist has 5 capacitors. In the image, the first `extract` of such
an inverter took 0.6 s, Python's start included.

**Devices Magic's GDS reader doesn't keep.** Every check reads the PCells
through Magic's GDS reader, and some devices don't survive it: Magic's own
cell, placed from its Devices menu, extracts as the device, and the same
cell read from GDS doesn't. Measured on every device's defaults, listed in
`python/klayout_magic_pcells/data/readback-<pdk>.json`:

| PDK | Devices | Read from GDS, Magic extracts |
|---|---|---|
| sky130A | the four `cap_vpp_*` | no device |
| | `diode_pd2nw_05v5_hvt`, `diode_pd2nw_05v5_lvt` | two diodes, a standard `diode_pd2nw_05v5` and the hvt or lvt one |
| | `npn_11v0_W1p00L1p00` | the device, with area 1.97242 instead of 1.97245 |
| gf180mcuD | `nfet_10v0_asym`, `pfet_10v0_asym` | `nfet_05v0` and `pfet_05v0` with l = 0.44u |
| | `rm1` to `rm5`, `nwell`, `pvaractor_3p3`, `pvaractor_6p0` | no device |
| ihp-sg13cmos5l | `nmoscl_2`, `nmoscl_4` | no device |
| ihp-sg13g2 | none | |

gf180mcuD's `eFuse`, `npn_00p54x08p00` and `npn_00p54x10p00` aren't
measured: Magic writes no netlist for its own cell of them. Each placement
of a listed variant gets an item in the category "Extraction/Magic's GDS
reader does not keep this device". `KMP_PDK=P KMP_PDKS=P
KMP_READBACK_WRITE=1 python3 -m unittest
tests.backend.test_lvs_backend.ReadbackTest` measures it again and
rewrites the file.

**Menu:** Magic > Extract with Magic... asks for a netlist only or one with
parasitic capacitance; `--flatglob` and `--ports-from-labels` are on the
command line only. It writes the netlist where `extract` without `-o`
does, under the same rule, and shows it in a window. When that file isn't
the plugin's, or the layout has never been saved, the message says "Not
written: ..." and a save dialog opens, in the first case at the first free
name, such as `inv.magic-2.spice`.

**Categories:** "Extraction/Magic's GDS reader does not keep this device",
"Extraction/every label made a port" (with `--ports-from-labels`),
"Job/failed", and the export's. On the command line `extract` prints these
findings on stderr, and `--rdb OUT.lyrdb` saves the database, also when the
job fails.

**Exit status.** 0 when the netlist is written, 1 when a placed PCell
variant holds a device from the table above or when Magic reads nothing
in the cell (no netlist is written then), 2 when the input or Magic
fails or the netlist file is refused. The export's findings don't change
it (each sky130A layout here has npc, which Magic doesn't read).

**Limits.** No resistance extraction. The capacitances of `--caps` aren't
compared with anything. Positions in the `.ext` files are read with the
unit Magic prints for `[cif scale out]` in the same process (0.005 µm on
all four PDKs), not the `.ext` file's `scale` line, which says 500000 on
sky130A and 0.5 on the others.

### LVS with netgen

`lvs` extracts the cell as `extract` does, then runs netgen with the PDK's
setup file:

```
netgen -batch lvs "<netlist> <cell>" "<schematic> <subcircuit>" <setup file> <report> -json
```

`--schematic` is the SPICE netlist to compare against, and the subcircuit
is the one named like the layout cell unless `--schematic-cell` names
another. The result is netgen's: a match is netgen's final result
"Circuits match uniquely." or "Circuits match with N symmetries." with no
property, port, pin or subcell failure after it. In particular, "Circuits
match uniquely." followed by "Property errors were found." is not a match.

netgen's findings are put on the layout through Magic's `.ext` files. A
layout net that netgen couldn't pair, or that it paired with a net whose
devices differ, is marked by its shape at the point the `.ext` file gives
for it (a piece of diffusion is cut at the gates), or by a 0.02 µm box
there when no shape is found. A device with a property error is marked at
the device, and a layout pin with no partner at its port box. Nets of
subcells that netgen flattened are followed into the subcell through the
placements, so they get markers too. A subcircuit that netgen compared on
its own gets its markers in that subcell, in its own coordinates.

```
$ python3 -m klayout_magic_pcells lvs inv.gds --pdk sky130A --schematic inv.spice
lvs: inv against inv in inv.spice (sky130A): netgen: Circuits match uniquely. The layout matches.
  Export/Magic does not read this layer: 1 item
$ python3 -m klayout_magic_pcells lvs inv_open_drain.gds --pdk sky130A --schematic inv_open_drain.spice -o od.lyrdb --report od.txt --json od.json
lvs: inv_open_drain against inv_open_drain in inv_open_drain.spice (sky130A): netgen: Netlists do not match. The layout does not match. 2 markers in the report.
  netgen/net only in the layout: a_300_260#, Magic type ndif at (1.500, 1.300): layout sky130_fd_pr__nfet_01v8 pin 1|3 x1; netgen found no schematic net to pair it with
  netgen/nets that differ: Y, Magic type li at (2.250, 2.600): layout sky130_fd_pr__pfet_01v8_hvt pin 1|3 x1; schematic sky130_fd_pr__nfet_01v8 pin 1|3 x1, sky130_fd_pr__pfet_01v8_hvt pin 1|3 x1
  Export/Magic does not read this layer: 1 item
$ python3 -m klayout_magic_pcells lvs inv_w036.gds --pdk sky130A --schematic inv_w036.spice
lvs: inv_w036 against inv_w036 in inv_w036.spice (sky130A): netgen: Circuits match uniquely. netgen: Property errors were found. The layout does not match. 1 marker in the report.
  netgen/property mismatch: sky130_fd_pr__nfet_01v8:0 against sky130_fd_pr__nfet_01v8:M1: w: layout 0.36, schematic 0.65
  Export/Magic does not read this layer: 1 item
```

The first exits 0, the other two 1. In the open drain, the marker on
`a_300_260#` is the NMOS drain's diffusion, to the right of the gate;
`klayout inv_open_drain.gds -m od.lyrdb` shows it. `--report`
copies netgen's text report and `--json` writes the verdict, netgen's
reasons, the findings with their boxes in µm, and the paths of the files;
`-o` saves the report also when the job fails. The job directory keeps the
export, the `.ext` files and `netlist.spice`, and netgen's `lvs.out`,
`lvs.json` and `netgen.log` in a directory of their own: in a cached
extraction's directory each LVS run gets a new `lvs-<random>/`, so two
runs on one extraction never write over each other's report, and in a
`tmp-*` run (see [Job directories](#job-directories)) they go in `lvs/`.
Either way that directory is removed when the command ends, unless
`KMP_JOB_KEEP=1`, so the paths that `--json` gives for netgen's files
point at nothing afterwards; `--report` keeps a copy of netgen's report.
On a layout with no texts, the pins item says so, and every schematic
pin gets an item of its own. For the pin on the first row of netgen's pin
table, netgen's JSON gives "(no matching pin)", and the plugin takes the
pin's name from netgen's report ("(no pins) | VPWR **Mismatch**"):

```
$ python3 -m klayout_magic_pcells lvs inv_no_text.gds --pdk sky130A --schematic inv_no_text.spice
lvs: inv_no_text against inv_no_text in inv_no_text.spice (sky130A): netgen: Top level cell failed pin matching. The layout does not match. 5 markers in the report.
  netgen/pins: the layout cell inv_no_text has no pins: the layout has no texts
  netgen/pins: schematic pin VPWR has no pin in the layout
  netgen/pins: schematic pin A has no pin in the layout
  netgen/pins: schematic pin Y has no pin in the layout
  netgen/pins: schematic pin VGND has no pin in the layout
  Export/Magic does not read this layer: 1 item
```

**Menu:** Magic > LVS with netgen... asks for a SPICE or CDL schematic (its
path, or Browse...) and one of its `.subckt` names, with the one named like
the cell preselected, and keeps the choice per layout file and cell. The
file dialog of Browse... lists the netlists that Extract with Magic writes
(`<cell>.magic.spice`) beside the schematics; for such a file, whose first
line is the plugin's header, the dialog asks whether to use it anyway,
since LVS against it compares Magic's netlist with Magic's netlist.
netgen's report opens in a window beside the browser, scrolled to its end,
where netgen's final result is.

**Categories:** "netgen/result" (netgen's final result and its reasons),
"netgen/net only in the layout", "netgen/net only in the schematic",
"netgen/nets that differ", "netgen/device mismatch", "netgen/property
mismatch", "netgen/pins", "Extraction/Magic's GDS reader does not keep
this device", "Extraction/nets without a position", "Extraction/every label
made a port", "Job/failed", and the export's. On a match, the items under
"netgen/result" are information.

**Exit status.** 0 for a match as above, 1 for anything else netgen
reports and for a cell Magic reads nothing in, 2 when the input, Magic
or netgen fails (no schematic, no such subcircuit, a missing netgen
setup file).

**Limits.**

- The result is netgen's report and the markers; there is no view in
  KLayout's Netlist Database Browser.
- A text that isn't a Magic port doesn't make a pin, so netgen fails pin
  matching ("Top level cell failed pin matching.") on a layout whose pins
  are texts alone; the [port check](#ports) says which texts.
  `--ports-from-labels` makes every label a port, which Magic's own flow
  doesn't do, and the report says so.
- netgen splits its arguments at spaces: a schematic path with a space is
  copied into the job directory first, and a cache directory whose path has
  a space fails.

### Generated layers

Magic reads implants and marker layers only to decide what each piece of
diffusion and poly is, and draws its own implants when it writes GDS. In a
hand-drawn layout these layers can be wrong without any Magic DRC error, and
the GDS that Magic writes back is then not the layout that was drawn.
`layers` has one Magic process read the export with its hierarchy, write it
back as GDS, and extract a copy that Magic flattened itself. KLayout then
compares the user's layout with what Magic wrote and extracted. The
findings, under the labels that the output and the categories use:

- **F1, stops short.** An implant or marker encloses a device shape (a
  diffusion, a gate, a poly contact) by less than the distance by which
  Magic's GDS output grows that layer from the shape. The distance comes
  from the PDK's Magic tech file, and the finding cites the line and names
  the foundry rule where the data file has one (on sky130A, every layer
  in the table below). Magic's own shape is used
  only in the finding's advice on what to draw. Gaps that Magic fills between two implant
  shapes aren't findings.
- **F2, read as another device.** A gate the user drew that Magic's
  extraction makes into another device, two devices or none, such as an
  NMOS without nsdm on sky130A, which Magic reads as a pfet.
- **F3, dropped.** Conductor, poly or diffusion that Magic doesn't write
  back, and cuts with no Magic cut over them, such as a licon with no li
  over it. On sky130A, a licon on diffusion or tap that has li over it but
  neither nsdm nor psdm under it is dropped too, since Magic makes a
  contact on diffusion only where one of the two implants is; the item
  says so, and the F2 or F1 item on the same diffusion says which implant
  to draw.
- **F4, added.** Conductor that Magic writes where none was drawn.
- **F5, redrawn** (information). Cuts that Magic replaced with its own; the
  user's file keeps the drawn cuts, and those are what KLayout's DRC
  checks.
- **The export's findings**, as for every check.
- Every device that Magic extracted, with its model, W and L (information).

F1 measures these layers:

| PDK | Layer and the shape it grows from, with the distance |
|---|---|
| sky130A | nsdm and psdm: diffusion 0.125 µm (`n/psdm.5a`) and tap 0.125 µm (`n/psdm.5b`); hvtp and lvtn: the hvt or lvt gate 0.18 µm (`hvtp.3`, `lvtn.4b`); npc: the poly contact cut 0.10 µm (`licon.15`) |
| gf180mcuD | NPLUS and PPLUS: diffusion 0.16 µm, tap 0.02 µm, gate 0.23 µm; DUALGATE: 5 V and 6 V diffusion 0.24 µm |
| ihp-sg13g2, ihp-sg13cmos5l | pSD: p-diffusion 0.18 µm, PMOS gate 0.30 µm, p-tap 0.03 µm; ThickGateOx: HV diffusion 0.27 µm |

```
$ python3 -m klayout_magic_pcells layers a_nsdm_flush.gds --pdk sky130A -o a_nsdm_flush.lyrdb
layers on sky130A, cell a_nsdm_flush: F1 1, F2 0, F3 0, F4 0; F5 0 (information); 2 devices in Magic's extraction; export: 0 off grid, 1 on unread layers, 0 read as another type, 0 cross-cell
F1 nsdm: nsdm around the n-diffusion at (0.400, 1.300)-(2.600, 1.950) stops short. Magic draws nsdm over (0.275, 1.175)-(2.725, 2.075) here, 0.125 um past the n-diffusion; your nsdm leaves 0.7750 um2 of that uncovered. The rule is n/psdm.5a (sky130A.tech:846)
$ python3 -m klayout_magic_pcells layers a_no_nsdm.gds --pdk sky130A
layers on sky130A, cell a_no_nsdm: F1 0, F2 1, F3 2, F4 0; F5 0 (information); 2 devices in Magic's extraction; export: 0 off grid, 1 on unread layers, 0 read as another type, 0 cross-cell
F2 gate: The gate at (1.350, 1.300): it is outside nwell, but Magic reads it as sky130_fd_pr__pfet_01v8 W 0.650 L 0.150. The gate has no nsdm over its diffusion, and Magic reads every such gate as a pfet, whatever the well (sky130A.tech:2597). To fix it, draw nsdm (93/44) over the n-diffusion, 0.125 um past it.
...
```

Both exit 1. `drc` finds no error on `a_nsdm_flush`, and on `a_no_nsdm` 25
boxes of 5 rules (`nwell.2a`, `diff/tap.8`, `nwell.1`, `nwell.4`, `LU.3`),
none of which names nsdm.

On correct layouts the check finds nothing. The backend tests assert, on
all four PDKs, that it reports no F1 to F4 finding on the foundry standard
cells that the case suite copies (seven per PDK, such as sky130A's
`sky130_fd_sc_hd__inv_1`, `__dfxtp_1` and `__mux2_1`), on a row of them
placed by KLayout, on the same row placed and written by Magic itself, and
on each PDK's clean hand-drawn inverter. A run of `layers` for this README
on each PDK's seven cells and the row that KLayout placed gave no F1 to F4
finding on any of them. On
gf180mcuD, the `filltie` cell and both rows get one F5 item, where Magic
moves two contact cuts.

**Menu:** Magic > Check generated layers, with no dialog.

**Categories:** "F1 implant or marker stops short/<layer>", "F1 Magic draws
more of this layer here (information)/<layer>" (for a PDK where F1 can only
be information; on all four it is a check), "F2 transistor Magic reads as
another device or none", "F3 shape Magic drops/<layer>", "F4 conductor
Magic adds/<layer>", "F5 cuts Magic redrew (information)/<layer>",
"Devices Magic extracted (information)", "Job/failed", and the export's.
`--json` writes the same findings.

**Exit status.** 1 when there is an F1 to F4 finding, an export finding
that is off the grid, read as another type or a layer drawn in another
cell, or when Magic reads nothing in the cell; else 0. F5, layers Magic
doesn't read and the device list don't count. 2 when the input or the job
fails; the report then gives the reason under "Job/failed", with the
export's findings, and `-o` and `--json` are written as on any other run.

**Limits.**

- F1 checks enclosure only, along the edges of a shape: it doesn't measure
  corners, and implants that aren't rectangles haven't been tried.
- F2 uses the copy that Magic flattens from its hierarchical reading. On
  gf180mcuD's `C_PMOS_all_h` that copy has one `pfet_03v3`, where Magic's
  hierarchical extraction has none, so F2 doesn't fire there; the export's
  "reads this cell without a layer drawn in another cell" does. Why the two
  differ is UNVERIFIED.
- Wells aren't compared, and the GDS that Magic writes back isn't checked
  with KLayout's DRC.

### Ports

Magic and the PDK's KLayout LVS deck read pins from different layers.
`ports` checks every cell's texts and pin boxes against the PDK's
conventions: which text layers name a net in Magic, which make a Magic port
alone or over a pin box, which the KLayout LVS deck reads, and the forms
that both accept:

| PDK | The form both accept |
|---|---|
| sky130A | a text on a `*/5` label layer over a `*/16` pin box, such as `li1.label` (67/5) over `li1.pin` (67/16) |
| gf180mcuD | a text on the `*/10` label layer of 34, 36, 42, 46 or 81 (Metal1 to Metal5), with no pin box |
| ihp-sg13g2 | a text on `*/25` over a box on `*/2`, on 8, 10, 30, 50, 67, 126 or 134 |
| ihp-sg13cmos5l | the same, on 8, 10, 30, 50 or 126 |

The check reads the user's layout in KLayout and, without `--magic`,
doesn't start Magic. Its findings:

- **P1:** a text that neither Magic nor the KLayout LVS deck reads;
- **P2:** a text that names a net in Magic but makes no port, so netgen
  fails pin matching;
- **P3:** a Magic port that the KLayout LVS deck can't name;
- **P4:** a pin box with no text over it, on its own layer number or on
  the text layer that the form both accept pairs with it (sky130A's
  `pwell.pin`, 122/16, takes its text on `pwell.label`, 64/59);
- **P5:** a pin box with no drawing under it, or reaching past it, which
  Magic turns into conductor and KLayout doesn't;
- **P6:** a text over no shape of its layer, looking down the hierarchy;
- **P7:** texts inside device PCells on a layer the KLayout LVS deck reads,
  whose flat LVS then joins every net with that name;
- **P8** (`--magic`): a top-level text in a pin form that is missing from
  the ports of the subcircuit Magic extracts.

A text on a layer that Magic reads onto a type of its comment plane names
no net in Magic and gives no finding. These are sky130A's `text.drawing`
(83/44) and the IHP PDKs' `TEXT.drawing` (63/0), `DeepVia` (152/0;
`THRUVIA` on ihp-sg13cmos5l) and `NoMetFiller` (160/0), listed as `comment` in the ports table of
`data/pdk-<pdk>.json`. The foundry's standard cells carry their own name
on 83/44, such as `inv_1` at the origin of `sky130_fd_sc_hd__inv_1`, and
Magic's netlist of that cell has no net of that name.

```
$ python3 -m klayout_magic_pcells ports port_txt.gds --pdk ihp-sg13cmos5l --magic
ports on ihp-sg13cmos5l, cell port_txt: P1 0, P2 4, P3 0, P4 0, P5 0, P6 0, P7 0, P8 0; Magic's ports: none
P2 port_txt: text 'A' at (0.000, 1.200) on 8/25 (Metal1.text) names a net in Magic but makes no port, so netgen fails pin matching. The form both accept is a text on 8/25 over a box on 8/2.
...
```

That case's file is in the ihp-sg13cmos5l case suite's `gaps` folder. It
and its variants there, and four sky130A inverters, gave:

| Case | Its texts | Findings |
|---|---|---|
| ihp-sg13cmos5l `port_txt_pin` | on 8/25 over 8/2 boxes | none |
| ihp-sg13cmos5l `port_txt` | on 8/25 | P2 4 |
| ihp-sg13cmos5l `port_m1` | on Metal1 (8/0) | P2 4 |
| ihp-sg13cmos5l `port_pin`, `port_pin_box` | on 8/2 | P3 4 |
| ihp-sg13cmos5l `port_lbl` | on Metal1.label (8/1) | P1 4 |
| sky130A `inv` | on `*/5` over `*/16` boxes | none |
| sky130A `inv_no_text` | none, the pin boxes stay | P4 4 |
| sky130A `inv_pin_only_li` | the A pin box with no li under it | P5 1 |
| sky130A `inv_text_on_pin` | A's text on li1.pin (67/16) instead of li1.label | P3 1 |

On the sky130A inverter built from this package's PCells, P7 reports the
D, G, S and B texts on 67/5 inside the two transistor cells (8 items), and
its message says to turn the PCell's `doports` off. gf180mcuD's standard
cells get P3 for their VNW and VPW labels on 21/10 and 204/10, which Magic
makes ports and the KLayout LVS deck doesn't read. The case suite's seven
sky130A standard cells and the row of them give no finding.

**Menu:** Magic > Check ports runs P1 to P7, with no dialog and without
starting Magic; P8 needs `ports --magic` on the command line.

**Categories:** "P1 text neither Magic nor KLayout's LVS reads", "P2 text
names a net in Magic but makes no port", "P3 Magic port KLayout's LVS
can't name", "P4 pin box with no text", "P5 pin box with no drawing under
it", "P6 text over no shape of its layer", "P7 texts inside device cells",
"P8 pin missing from Magic's subcircuit ports", "Job/failed" (with
`--magic`).

**Exit status.** 1 when there is any finding, 0 when there is none, 2 when
the input or, with `--magic`, the job fails. With `--magic`, a cell Magic
reads nothing in gives P1 to P7 and the export's "Magic reads nothing in
this cell", and no P8.

**Limits.** P1 is reported only for texts on layer numbers that the PDK's
data file knows; texts on other layer numbers are skipped. P8 needs Magic.

## Where KLayout and Magic disagree

`docs/gaps/` has a table per PDK of where Magic's DRC and the PDK's KLayout
DRC decks disagree, one row per rule: [sky130A](docs/gaps/sky130A.md),
[gf180mcuD](docs/gaps/gf180mcuD.md), [ihp-sg13g2](docs/gaps/ihp-sg13g2.md)
and [ihp-sg13cmos5l](docs/gaps/ihp-sg13cmos5l.md), each also as a `.json`
file. A row is a rule ID: the one Magic's message names; where the two
tools name a rule differently, a name from the PDK's alias file,
`tests/gaps/aliases-<pdk>.json` (Magic prints `hvi.5` for sky130A's
HVI-to-HVI spacing, and the row is SkyWater's `hvi.2a`); or the KLayout
name where Magic has no such rule. It holds Magic's statements, with
value, styles and tech-file line; each KLayout deck's outputs, with name,
value, the switch that enables it and the deck line; and what both tools
reported on the cases of the [case suite](#the-case-suite) that target
the rule. Magic's rules come from the PDK's data file
(`python/klayout_magic_pcells/data/pdk-<pdk>.json`). The KLayout side
comes from running each deck on a one-box layout, whose report lists every
rule the deck runs under its switches, and from a scan of the deck for each
output's line and switch; no deck text is stored. The two are joined on the
rule ID, with the alias file's mappings, the only part typed by hand.
Magic checks each case cell alone in all three styles, and KLayout checks
them on one sheet; a case's result is what was reported on it and not on
its control case. For version 0.6.1, the rows on which the two tools
disagreed, and their cases, were checked against the foundries' published
rules ([tests/cases/README.md](tests/cases/README.md#sources) names the
sources, and [Last full run](#last-full-run) lists what changed), and
the notes beside some rows' statuses cite those rules. This check found
problems in the PDKs' Magic tech files, in their KLayout decks and in Magic
itself; [docs/upstream-issues.md](docs/upstream-issues.md) lists them, with
the upstream file and line of each, and none of the 18 issues it
describes has been filed yet.

The status compares Magic with `sky130A_mr.drc` on sky130A (with the parity
harness's switches; the page has columns for the switches of Efabless
sky130 > Run DRC (Full) and for `sky130A.lydrc`), with `gf180mcu.drc` on
gf180mcuD, and with `run_drc.py`'s main and maximal decks on the IHP PDKs:

| Status | Meaning |
|---|---|
| both | both tools check the rule |
| both, values differ | both check it, with different values (both in the row) |
| folded | Magic checks the ID only inside a composite rule, such as `V1.a + 2 * M2.c` |
| measured on other shapes | both check it, on different shapes |
| same name for another check | the name means a different rule on each side |
| in the deck, did not fire on its case | a tool has the rule but reported nothing on the cases that break it; the row names the tool |
| Magic only | that deck doesn't have the rule; the row says when another deck does |
| KLayout only | Magic has no such rule |

The counts, from `docs/gaps/README.md`:

| PDK | both | both, values differ | folded | measured on other shapes | same name for another check | in the deck, did not fire on its case | Magic only | KLayout only | rules | cases |
|---|---|---|---|---|---|---|---|---|---|---|
| sky130A | 76 | 1 | 5 | 0 | 3 | 7 | 93 | 205 | 390 | 132 |
| gf180mcuD | 105 | 7 | 8 | 2 | 0 | 3 | 14 | 406 | 545 | 69 |
| ihp-sg13g2 | 203 | 0 | 12 | 0 | 1 | 4 | 12 | 130 | 362 | 151 |
| ihp-sg13cmos5l | 146 | 0 | 10 | 0 | 1 | 3 | 8 | 114 | 282 | 49 |

`scripts/gaps.sh` rebuilds all four in the image, one container per PDK,
and writes `docs/gaps/` and
`python/klayout_magic_pcells/data/gaps-<pdk>.json`, which the DRC check
reads for its category descriptions. `--pdk P` rebuilds one. `--check`
rebuilds the tables without writing them, and exits 1 with
`GAPS DIFFER <file>` and a diff when one would change, for example after
a PDK or Magic update. On 0.6.1's code, `scripts/gaps.sh --check` took
249 s for the four PDKs; its output, without the `[INFO]` lines that the
image prints when a container starts:

```
$ scripts/gaps.sh --check
sky130A: 390 rules (both 76, both, values differ 1, folded 5, same name for another check 3, in the deck, did not fire on its case 7, Magic only 93, KLayout only 205), 132 cases, 75 s
GAPS OK sky130A
gf180mcuD: 545 rules (both 105, both, values differ 7, folded 8, measured on other shapes 2, in the deck, did not fire on its case 3, Magic only 14, KLayout only 406), 69 cases, 42 s
GAPS OK gf180mcuD
ihp-sg13g2: 362 rules (both 203, folded 12, same name for another check 1, in the deck, did not fire on its case 4, Magic only 12, KLayout only 130), 151 cases, 98 s
GAPS OK ihp-sg13g2
ihp-sg13cmos5l: 282 rules (both 146, folded 10, same name for another check 1, in the deck, did not fire on its case 3, Magic only 8, KLayout only 114), 49 cases, 32 s
GAPS OK ihp-sg13cmos5l
```

The rule list is what the decks run under the switches used; rules that
are switched off are absent. A KLayout value comes from the rule's
description in the deck's report, and a rule whose description has no
number has none.

Magic > Rule differences shows the page of the current layout's PDK
(`docs/gaps/<pdk>.md`) in a KLayout window, or with no layout open the page
of `KMP_PDK`'s PDK. When the `docs` folder isn't installed with the plugin,
it says where it looked.

Some of the rows that matter for a cell drawn by hand in KLayout and
checked by Magic:

- **sky130A** ([front end](docs/gaps/sky130A.md#front-end-li-mcon-met1-via1)):
  - `nwell.4`, `LU.2` and `LU.3`, a missing tap, are Magic only and in
    `drc(full)` alone: Magic reported them on the cases without a tap and
    KLayout didn't. Magic starts in `drc(fast)`, which doesn't have them.
  - `poly.8` (gate endcap) is Magic only; `sky130A.lydrc` has it with
    FEOL on.
  - `psd.10b` and `nsd.10b` are Magic only, and they aren't SkyWater's
    area rules: Magic checks the area of a tap, 0.07011 µm², where
    SkyWater's `n/psd.10a` and `n/psd.10b` are the minimum areas of the
    drawn nsdm and psdm (0.265 and 0.255 µm²). Magic reported the taps of
    `d_tap_area` and `e_ntap_area`, which SkyWater's rules allow.
  - `x.2`: Magic reported the 45° diffusion corners of `d_diff_45` and
    `d_diff_45b` and the 45° li edge of `s_li_45deg` (li outside the SRAM
    core takes 90° only), and KLayout's angle checks reported nothing.
  - `licon.1` and `via.1a`: KLayout flags a 0.20 µm licon and a 0.16 µm
    via1 that Magic accepts, since Magic draws its own cuts.
  - `difftap.2` and `poly.3` are the same names for other checks in
    `sky130A_mr.drc` (core diffusion width and core poly spacing; Magic's
    are the transistor width and the poly resistor width).
- **gf180mcuD** ([wells to via1](docs/gaps/gf180mcuD.md#wells-to-via1)):
  - `DF.6`, the source and drain length past the gate: Magic 0.23 µm for
    every device, KLayout 0.24 µm for 3.3 V and 0.40 µm for 5 V and 6 V
    devices, so `DF6_mv_030` and `DF6_lv_0235` pass Magic and fail KLayout.
  - `NP.5a` is KLayout only: Magic reports nothing on `NP_flush` and
    `NP5a_ov010`, where [the generated-layer check](#generated-layers)
    reports NPLUS that stops short.
  - `CO.2a` and `V1.2a`: Magic reported nothing on contacts or vias that
    are too close (`CO2a_s022`, `CO2b_4x4_s010`, `V1_2a_s022`); `CO.10` (a
    contact on a gate) and `CO.11` (a contact on field oxide) are KLayout
    only.
  - `DF.13` and `DF.14`, tap distance, are KLayout only.
- **ihp-sg13g2** ([front end](docs/gaps/ihp-sg13g2.md#front-end-metal1-via1-grid-pins)):
  - pSD: `pSD.c` is folded into a resistor rule on Magic's side and
    `pSD.k` is KLayout only; Magic reported nothing on `pSD_c`, `pSD_i_psd`
    or `pSD_k`.
  - `V1.a` and `V1.b`: Magic reported nothing on `V1_a`, `V1_big` and
    `V1_b`, and `V1.b1`, `Cnt.g` and `Cnt.h` are KLayout only.
  - `LU.b` is in both, but in Magic only in `drc(full)`.
  - `Pin.e`, a pin box past its metal, is KLayout only.
- **ihp-sg13cmos5l** ([front end](docs/gaps/ihp-sg13cmos5l.md#front-end-metal1-via1-grid-pins)):
  - `pSD.i` and `pSD.j`: Magic reported nothing on `u_pSD.i` and
    `u_pSD.j`, and `pSD.c` is folded; the generated-layer check reports
    the pSD of `u_pSD.c` and `u_pSD.i` as stopping short.
  - `V1.a`: Magic reported nothing on `m_V1.a`; `V1.b1` and `Cnt.b1` are
    KLayout only.
  - `TGO.f` and `NW.b1` are KLayout only.
  - `LU.b` is in Magic only in `drc(full)`.

## Parameters

Every entry, checkbox and selectlist of Magic's dialogs is a PCell
parameter, with two exceptions: the device-type switch (below) and the "Add
top gate contact" and "Add bottom gate contact" checkboxes (`topc`, `botc`)
of the IHP PDKs' four RF FETs, whose names the devices' defaults lack (see
[Known limitations](#known-limitations)). The types come from the manifest,
a JSON file per PDK built from Magic (see [Devices](#devices)). A value you
change is typed into Magic's dialog as the text in the last column (for a
box-paint generator, given to its menu call as that text); what the PCell
then stores and draws is what the dialog makes of it (see [Values as Magic's
dialog shows them](#values-as-magics-dialog-shows-them)):

| In Magic's dialog | PCell type | Typed into Magic's dialog as |
|---|---|---|
| number entry | double | the 15 significant digits that KLayout saves, rounded to 12, written like a Python float (`0.35`, `31.0`); any zero as `0.0`; a value equal to Magic's default as Magic's default text (`0.420`) |
| `nf`, `ng`, `m`, `nx`, `ny`, `turns` | int | `3` |
| checkbox | boolean | `1` or `0` |
| the "\[+/-\](%)" coverage entries (`viasrc`, `viadrn`, `viagate`, `viagb`, `viagr`, `viagl`, `viagt`, `ccov`) | string | the text as typed, whitespace included, if it is a number; anything else is refused (see below) |
| a selectlist other than the device switch (gf180mcuD `guard_type`; IHP `via` `metalbot`, `metaltop`, `orient`, `pattern`; IHP `bondpad` `shape`; sg13cmos5l `cap_cmomf` `mmin`, `mmax`) | string with Magic's choices | the choice; anything else is refused |
| IHP `via` `nxcuts` and `nycuts` | string | the text as typed if every word is a number (`2`, or `1 2` for one value per via layer); anything else is refused |

The IHP `_check` procs test counts with `string is int`, so `2.0` fingers
draw one finger with the message `NG must be an integer!`; `ng` and `turns`
are therefore ints. The selectlists change geometry: on gf180mcuD,
`ppolyf_u` with `guard_type nwell` replaces its 204/0 (LVPWELL) ring with
21/0 and 32/0. The device-type selectlist `gencell`, which switches Magic's
dialog to another device, is not a parameter; each device is its own PCell.

The coverage entries are strings because Magic reads their first character as
an anchor: `+50`, `-50` and `50` are three different layouts, and a KLayout
double has no way to hold `+50`. Whitespace counts too: ` -50` starts with a
space, so it has no anchor and draws like `50`. Keys that Magic's dialog
doesn't show (`lmin`, `wmin`, `class`, `rho` and so on) are not PCell
parameters; Magic uses its own values for them.

The generator code evaluates the coverage strings with an unbraced
`expr abs($viagb)` (sky130A.tcl and the IHP FET code), and IHP's `via_check`
does the same to each word of `nxcuts`. Tcl substitutes any `[command]` or
`$variable` inside such a value, so a file whose instance held
`viagb = [exec ...]` would run that command as soon as it was opened. The
PCell therefore sends a coverage string only if it is a decimal number with
an optional `+` or `-` in front and optional spaces or tabs around it, such
as `+50`, `-50`, `50.5`, ` -50` or `1e2`, a number list only if every word is
a decimal number, and a choice only if it is one of Magic's. For anything
else (`abc`, an empty string, `0x32`, `[exec ...]`) it draws the error marker
described under [If Magic is missing or fails](#if-magic-is-missing-or-fails),
and Magic never sees the value. In the GUI form that parameter should get an
error icon (written from KLayout's source, not seen on screen), and the CLI
`check` exits 2. Magic itself would have reset some of these values (on a
MOSFET `abc` becomes 0, with a message) and drawn nothing for others, so for
text that is not a number the PCell differs from Magic on purpose. The Magic
server also answers with an error for any value that contains `[`, `]`, `$`
or a backslash, whoever sends it.

Floats are rounded because KLayout 0.30.11 doesn't keep doubles exactly in a
saved file. It writes a double parameter with 15 significant digits and
parses that text back up to one ULP off: in a new process `0.35` reopens as
`0.35000000000000003`, and `4.257627156815` as `4.2576271568149995`. Without
rounding, the request, and with it the cache key, would change every time a
file is reopened; for a device, the reopened values would no longer match
the stored dialog form, and the dialog would run again. The PCell rounds the
15-digit text that KLayout saves, not the double, to 12 digits, so the value
and its reopened double give the same text. Version 0.3 rounded the double:
`4.257627156815` was sent as `4.25762715682`, and after a save and reopen as
`4.25762715681`. In a test of version 0.3, 22 of 300 values at or one ULP
from a 12-digit tie changed their request that way; none of the same 300
does with this version. KLayout saves -0.0 as 0, so any zero is sent as
`0.0`.

A value with 13 or more significant digits is therefore not the text Magic
gets: `0.4244999999999` is sent as `0.4245`. Magic's cell name and checked
values can then differ from Magic given the longer text, because Magic
rounds to three decimals for the name. Where this was tried, the geometry
was the same: sky130A `nfet_01v8` with `w` at 0.4225, 0.4275, 1.0045 and
5.005, each against the same value 1e-14 lower, drew the same polygons in
Magic. Floats always carry a decimal point because the generator code does
arithmetic with Tcl's `expr` and `/`, which divide two integer strings as
integers.

Apart from refusing values that the generator code would evaluate, the PCells
add no limits, no snapping and no choices of their own.

### Values as Magic's dialog shows them

A device PCell stores the values that Magic's own parameter dialog shows
after you type yours and press Create, and draws what Create makes. Every
later change to the instance is an edit in the dialog that Magic reopens on
the instance after Create ("Edit device"), followed by its Apply button.
Version 0.4 stored the values as typed and drew what `magic::gencell` made
of them. Box-paint generators have no dialog in Magic (their menu entry
paints into the box as it is), so their PCells keep the box as typed.

Magic's dialog (`toolkit.tcl`) works like this:

- When you press Return in an entry, leave it, click a checkbox or pick a
  choice, the widget's binding runs the device's `_check` and its
  dependency callback (`res_recalc` on a resistor's `val`, `l`, `w` and
  `nx`; `diode_recalc`; `cap_recalc`) on the whole form, two or three
  times, and writes the corrected values back into the form.
- Create runs `_check` once more, draws, stores that checked dict on the new
  cell, and reopens the dialog as "Edit device" on the new instance, which
  shows the checked values. A fixed device keeps no values on its cell: its
  dialog reopens with `nx` and `ny` from the array and `deltax` and
  `deltay` computed from the array's pitch, so a single copy shows
  `deltax 0.0` whatever was typed.
- Apply runs `_check` once and compares the device name plus Magic's hash
  of the result with the instance's cell name. When they are equal it
  leaves the instance as it is; otherwise `gencell_create` checks the
  values a second time and draws a new cell.

The PCell does the same through its Magic server. The values that differ
from what the dialog shows are typed into it one after another, in the
order of the dialog's rows, and each widget's binding runs once, as
pressing Return runs it. An instance's first edit then presses Create, and
every later one Apply. The PCell stores what the dialog shows when it
reopens on the instance. Magic computes every correction, check and cell
name; the plugin's Python code doesn't correct a value itself.
[docs/design.md](docs/design.md) section 4.5 has the details.

Some results on sky130A, which the parity harness also gets from the real
dialog:

| Typed | Stored: what Magic's dialog shows after Create |
|---|---|
| `nfet_01v8` `w 0.1 l 0.1` | `w 0.42`, `l 0.15` |
| `res_high_po_0p69`, nothing typed | `val 1028.0` (Magic's text `1.028k`); the New device dialog opens with `val 463.480` |
| `res_high_po_0p69` `w 1.0` | `w 0.69`, `val 1028.0` |
| `res_high_po_0p35` `val 10000` | `val 1570.0` (`1.57k`); the length stays 0.5 µm |
| `res_high_po_0p35` `l 0 val 10000` | `val 1113.259`, `l 1.218e-06` (`1.218u`): Magic draws nothing, because `_draw` fails on `1.218u` |
| `res_generic_po` `l 0` | `l 1.65`, with "Resistor length must be >= 1.650 um" |
| `diode_pd2nw_05v5` `w 0.225` | `w 0.45`, `area 0.2025` (`202.5m`) |
| `cap_mim_m3_1` `l 0 val 50` | `val 9.52`, `l 2.0`: `val` is the dialog's first row, so it is typed first; `magic::gencell` gives `l 11.242` |
| `npn_05v5_W1p00L1p00` `deltax 1.0` | `deltax 0.0`: one copy, so the reopened dialog computes 0 from the pitch; Create drew with 1.0, which a single copy doesn't use |

The state goes with the instance as the hidden parameter `kmp_dialog`: the
form that Create or Apply was pressed with, which is what the PCell sends
Magic, and the text of every widget of the dialog that reopens on the
instance. Both include widgets whose name the device's defaults lack: the
dialogs of the IHP PDKs' four RF FETs have "Add top gate contact" and "Add
bottom gate contact" checkboxes (`topc`, `botc`) that their defaults don't
have, so the dialog opens them empty and its Create gets `topc ""` and
`botc ""`. The PCell sends them too; they aren't PCell parameters (see
[Parameters](#parameters)). Compared with `magic::gencell` (and with
version 0.4), that changes Magic's cell name, and at the minimum width the
geometry. The state names its device. Two devices of a PDK often have
dialogs with the same widget names, and a state another device made is not
used: the values are typed into the device's own New device dialog, as
Magic's "Device type" switch does (on sky130A, `nfet_01v8`'s values given
to `nfet_g5v0d10v5` show `l 0.50`).

A value that the dialog shows in Magic's SPICE notation (`1.028k`,
`202.5m`, `1.218u`) shows in its field as the number `magic::spice2float`
gives for it. Every PDK's `magic::spice2float` maps the suffix `n` to
`* 1.0 e-9`, which isn't a number, so Magic reads none from `170.0n` (and
its `_draw` fails on it): `res_generic_l1` with `l 0` shows `170.0n` after
Create, gf180mcuD's `rm1` to `rm5` show `99.999n`, and the PCell field
keeps `0.0`, with a warning that names Magic's text.

**In the GUI** ([guide.md](guide.md) has the screenshots). "Seen" marks
what KLayout 0.30.11 showed under Xvfb; the rest comes from KLayout's
source and from the form's callback, driven in a backend test.

- When you change a field in the Instance tool's PCell tab and press Return
  (or leave the field), the field changes to what Magic's dialog shows after
  Create, with a warning icon and a tooltip (seen: `Magic's dialog shows
  0.15 (entered 0.1): Mos length must be >= 0.15 um`).
- A field that Magic's dialog shows in SPICE notation shows Magic's number,
  with a warning icon (seen: `res_high_po_0p69`'s `val` shows 1028, with
  `Magic's dialog shows 1.028k here, which this field can only show as
  1028.0`).
- The PCell tab doesn't give the PCell its stored dialog state, so each
  change there is typed into a New device dialog together with every value
  that differs from the defaults (seen: on `cap_mim_m3_1`, `l 5` and then
  `w 3` put a warning on `val`, `Magic's dialog shows 33.04 (entered
  22.66)`, though `val` wasn't typed).
- In the Properties dialog of a placed instance, a change is made when you
  leave the field, as Magic's Edit device dialog and Apply make it (seen;
  Return there presses the dialog's Ok button). That dialog showed no icon
  for a correction: `w 0.3` on an `nfet_01v8` came back as 0.42, and the
  warning was only in the Log Viewer.
- A field that the dialog changed as a consequence of another edit gets an
  information icon (`Magic's dialog sets this to ... (was ...)`), unless
  Magic shows it in SPICE notation. This icon hasn't been seen on screen.
- An edit that Apply doesn't take, because the values give the instance's
  own cell name (`w 0.1` on an `nfet_01v8` that Create made with the
  defaults), puts the fields back, with a warning that says so.
- When Magic draws nothing for the values, the fields the dialog corrected
  (or, if it corrected none, the first field) get a warning that says so,
  with Magic's message. On a box-paint generator, which has no dialog, the
  warning goes on the side that Magic's message names (seen:
  `Magic draws nothing: Via1 width must be at least 0.26um` on `w`).
- A refused value gets an error icon.

The callback makes the variant (Magic's Create or Apply), so the form asks
Magic on every edit, also with `KMP_LAZY=1`. The dialog's corrections and
Magic's messages also go to KLayout's log as warnings, in the GUI and
outside it.

**Reopening a file and refreshing a library** keep the values and the
drawing. Values that the stored dialog shows aren't typed into the dialog
again, although KLayout runs the PCell's coerce on every instance (when it
opens a file, before every produce, and in `Library.refresh()`, which keeps
what coerce returns). Typing them again would change some devices, because
`_check` isn't idempotent: on sky130A, `res_xhigh_po_5p73` with a typed
`val` shows `l 5.997`, and typing that `val` again would make it `l 5.994`,
another cell. The request,
the cache key and the cell name come from the stored state, so a reopened
variant is the one that was saved. A backend test saves such devices to GDS
and OASIS, reopens them in fresh processes with the disk cache off,
refreshes the library and saves and reopens again, and requires the same
parameters and geometry each time with no dialog run. The parity harness's
round trips check the same on part of each PDK's sweep.

**In batch**, `Layout.create_cell(device, library, values)` stores `values`
as given and draws what the dialog makes of them: KLayout keeps a PCell's
coerced values only in the GUI form and on a library refresh. The result is
the same after a reopen, because the correction depends on the stored values
alone; the disk cache keeps the dialog's results as well as the GDS, so a
reopened file needs no Magic call for variants that are cached.
`dialog_values()` returns the values the GUI would store (see
[Usage](#usage)), and given those values with some changed, it makes the
edit Magic's Edit device dialog and Apply make. `Library.refresh()` stores
the corrected values of every instance (run on `res_high_po_0p69` made
with `w 1.0`: `w 1.0` became `0.69`, `val 1028.0`, with the state in
`kmp_dialog`). The CLI's `generate` stores the corrected values.

**Where the PCell differs from Magic's dialog.** The model is "type each
changed value and press Return, then Create for an instance's first edit and
Apply for every later one". Magic's dialog can be used in other ways, and
where `_check` isn't idempotent or the order of the edits matters, they give
other values:

- A value typed and followed by Create (or Apply) with no Return or Tab
  runs no binding. Create then checks the form once, which is what
  `magic::gencell` does with the typed values. On the sweep's points with
  one typed value, on devices whose dialog has no widget beyond their
  parameters, the harness's path A (see [Tests](#tests)) is therefore this
  interaction. In the last full run it got other checked values than
  Return on 738 of those 4,293 points and other shapes on 22 (counts per
  PDK under [Last full run](#last-full-run)). For example,
  `res_generic_po` with `l 0` comes out as an empty cell, where Return
  shows `l 1.65` and Create draws it.
- Leaving a field (Tab, or a click into the next one) runs its binding
  again, and so do Return in an unchanged entry and Apply with no field
  changed. Review 3, a review of version 0.5's dialog model on
  2026-11-23, ran path D (see [Tests](#tests)) on the points with several
  typed values, with each entry's leave binding run before the next entry
  was typed;
  over the four PDKs, two points then drew another width, both on sky130A:
  `res_high_po_5p73` random:1 (`w 1.87`, where the PCell draws `5.730`)
  and `res_xhigh_po_5p73` random:5 (`w 5.325` against `5.730`). Both were
  reproduced on version 0.5.0 with the review's driver.
- A Magic user can type the values in any order.
- In KLayout's form each confirmed field is one edit, so two fields changed
  one after the other are Create and then Apply, where a Magic user may type
  both before Create. `dialog_values()` with several values types them into
  one dialog.
- Apply places a cell of the Magic session whose name the edit gives, when
  one exists (another instance with those values), instead of drawing one;
  the PCell always has Magic draw it.
- An instance with no stored state (made with `create_cell` and typed
  values, or saved by an earlier version) counts as not created yet: its
  next edit goes into the New device dialog.
- On sky130A's `res_high_po_5p73` and `res_xhigh_po_5p73` with `snake 1`
  and `l` below 5.73 µm, every one of these choices can decide the width:
  `res_check` sets `w` to 5.73 on one pass and back to `l` on the next (its
  `wmin` clamp and its "Snake resistor width must be < length" test each
  read the other's result), so `l 1.87` gives `w` 1.87, 5.730, 1.87, 5.730
  on four passes. This is a bug in the PDK's code; a backend test checks
  that Magic's `_check` still does this.

**Files saved by version 0.4 or earlier** hold the values as typed and no
`kmp_dialog`, and files saved by version 0.5 before review 3's fixes (never
released) hold another form of it (the form from before Create, `"v": 1`).
This version treats both like values given to `create_cell`: it types them
into the New device dialog and draws what Create makes. Where that differs
from what `magic::gencell` made of them, the device comes out differently
from how it was saved; `audit --regen` lists those cells. The harness's
comparison with `magic::gencell` shows how often that happens per PDK (see
[Last full run](#last-full-run)).

### Magic behaviour the PCells reproduce

Parity means these come out of the PCells exactly as Magic has them:

- MOSFET `w` is the width of one finger. `w 1.5 nf 3` is 4.5 µm of total
  width. The PCell form calls it "Finger width".
- Off-grid values are not snapped. The sky130A drawing rounds W and L to
  0.01 µm, so a requested `w 0.425` is drawn 0.43 µm wide, and two inputs
  that draw the same geometry are two different variants. Box-paint sizes
  are rounded to Magic's 5 nm internal grid (0.263 becomes 0.265).
- A negative box-paint size puts the box left of or below the origin, as
  Magic's `box values 0um 0um -1um 1um` does: sky130A `via1` with `w -1 h 1`
  is painted from x = -1 to 0 µm, with its metal reaching to x = -1.05 and
  0.05. A size of zero, `inf` or `nan`, or one too large for Magic's integer
  coordinates, comes out below the generator's minimum (Magic reads `inf`
  and `nan` as -2147483648 internal units), and Magic paints nothing.
- `_check` recalculates `val`, `area` and `peri`, from the size before its
  own clamp; the dialog's later passes compute them again from the clamped
  size. sky130A `diode_pd2nw_05v5` with `w 0.225` is drawn 0.45 × 0.45 µm;
  its dialog shows `area 202.5m`, where `magic::gencell`, with one
  `_check`, reports `area=101.25m peri=1.35`.
- Zero sizes give an empty cell on some devices, where the dialog leaves a
  SPICE string in the form (sky130A's diodes with `w 0` or `l 0` show
  `451.111m`) and `_draw` then fails on it, or the size stays 0 (the metal
  resistors), or `_check` itself fails. Magic writes a cell with no shapes; the PCell
  writes the same empty cell and logs a warning rather than drawing the
  error marker; `generate` and `check` exit 1 and `audit` reports
  `empty cell`. A `_draw` that fails for another reason, such as a PDK file
  edited so that it raises (a backend test does this on every PDK), ends the
  same way: `gencell_create` catches the Tcl error, prints it and leaves the cell
  empty, so the PCell can't tell the two apart. Whether an empty device
  should get the error marker instead is an open question for the project
  lead. The sweeps list every empty output per PDK.
- Some fixed devices are always empty: gf180mcuD's `eFuse` places the stub
  `eFuse_0.mag` (the real cell is `efuse_cell`), `npn_00p54x08p00` asks for
  `npn_npn_00p54x08p00_0` (a stub; the real `npn_00p54x08p00_0.mag` exists
  and isn't used), and `npn_00p54x10p00` places a stub, with no 10p00 GDS in
  `libs.ref`.
- gf180mcuD's two substrate-contact generators paint layer names that its
  tech file doesn't define (`subdiffc`, `mvsubdiffc`), so Magic prints
  "Unrecognized layer" and writes only a 204/0 (LVPWELL) box.
- Fixed devices (`nocell` in Magic) place the vendor or script-drawn cell
  with `nx` × `ny` copies at a pitch of `xstep + deltax` by
  `ystep + deltay`. `fixed_check` prints `NY must be >= 1` for `ny 0` but
  resets `nx` instead of `ny` (sky130A.tcl line 8070; the same code is in
  gf180mcuD and the IHP PDKs), so `ny 0` draws one device. The sky130A
  photodiode's own drawing loop runs zero times for `ny 0`: it draws a
  21.36 × 13.36 µm guard ring with no photodiode in it.
- Labels: sky130A writes texts on the `*/5` layers and no `*/16` pin shapes;
  `cap_var*` and the photodiode have no labels, the `g5v0d16v0` FETs have no
  D label, and the MIM cap's C2 is on 71/5. gf180mcuD's drawn devices carry
  no labels at all (its Tcl has no `label` command); its fixed devices carry
  vendor texts on 34/0. The IHP PDKs write texts on datatype 25, pin shapes
  on datatype 2 for some devices, and device-name texts on 63/0.
  `npn13g2l` and `npn13g2v` call `label E c +m2`, which Magic 8.3.681
  rejects (`Unknown layer: +m2`), so they have no emitter label; `npn13g2`
  loses its `+comment` text the same way.
- Coordinates finer than 5 nm: four sky130A fixed devices
  (`pnp_05v5_W0p68L0p68`, `rf_test_coil1` to `3`) have shapes on 83/44 off
  the 5 nm grid in the vendor GDS, and ihp-sg13g2 `npn13g2` has its E label
  at y = 0.007 µm. They are exact in a host layout with a database unit of
  1 nm or 0.5 nm and get rounded at 5 nm; `audit` reports it.
- `cap_cmomf` (sg13cmos5l) has its lower-left corner at the origin; every
  other drawn device is centred.
- A generator that places a child cell it creates once and reuses
  (ihp-sg13g2 `npn13g2` places `npn13g2_base`) gets the same child in later
  requests, as in one Magic session. The server keeps such cells instead of
  restarting Magic.

The library avoids these Magic behaviours instead of reproducing them:

- `mos_check` loops forever on sky130A and the IHP PDKs when a MOSFET or
  varactor has both `w` and `l` above 28 µm, whatever `nf` (`ng`) and `m`
  are: its tap-spacing loop sets `w` to 29 and then tests the same condition
  again, printing `Transistor width must be < 29 um` on every pass. Magic's
  own dialog hangs on these values too. The server counts the messages each
  request prints, and once one message has been printed 10,000 times it stops
  the request, which ends before anything is drawn. The PCell then draws the
  error marker, in about 0.1 s and without restarting Magic. gf180mcuD's
  loop ends (at `w` 37).
- Magic's cell name is the device name plus a hash of the values, rounded to
  three decimals and with a leading `+` dropped. `viasrc 50` and
  `viasrc +50` get the same Magic cell name and different geometry. In one
  Magic session, the second request paints into the cell that the first one
  made, so the cell ends up with both layouts painted over each other. The
  backend deletes each cell after writing it, and its cache key uses the text
  you entered.
- Generators that change Magic's session and don't change it back: a failed
  IHP `_draw` (at a zero size) leaves 122 layers locked instead of 36,
  because it runs its device code under `tech lock *`; in the same session
  IHP's `via` then draws different geometry on 8/0, 10/0 and 19/0, and the
  inductors lose their top-metal layers. The sky130A guard-ring
  and well commands run `tech revert`, which unlocks `fence`, `magnet` and
  `rotate`; `deep_nwell_draw` leaves an entry on Magic's box stack; the IHP
  substrate-contact and well commands set `units microns`, under which the
  IHP and sky130A via commands paint nothing. The server records the layer
  locks, units and box stack at start-up and puts back whatever a request
  changed of them, so the next request sees what a fresh Magic has there.
  Path A of the harness does the same after every point. A backend test
  checks per PDK that requests after such a change draw what a second, fresh
  Magic draws. Other session state that a generator might change is not
  tracked.
- `gencell_create` called with an empty parameter dict takes the dialog
  branch and fails in batch; the backend always passes the merged defaults.

## Box-paint generators

Magic's "Devices" menus have commands that paint into the cursor box instead
of opening a dialog: vias and contacts, substrate contacts, substrate guard
rings, n-wells with a guard ring, and deep n-wells. Their `_draw` procs have
no `_defaults` proc and take no arguments (sky130A's `mcon_draw` and IHP's
`via1_draw` have optional ones, which the menu doesn't pass); each reads the
box size and paints into the current cell. The manifest calls every such proc
a box-paint generator, and each gets a PCell with two parameters:

| Parameter | Magic's call |
|---|---|
| `w` (µm) | the box's width: `box values 0um 0um ${w}um ${h}um`, then `<ns>::<proc>_draw` with no arguments |
| `h` (µm) | the box's height |

The PCell's origin is the box's lower-left corner, or, for a negative width
or height, its right or top edge (see [Magic behaviour the PCells
reproduce](#magic-behaviour-the-pcells-reproduce)). The cut rules are
`squares-grid` without a grid argument, so a box drawn at the origin and
placed at any offset on the 5 nm grid equals Magic painting the box at that
offset; research for version 0.3 checked 17 offsets on sky130A, and a test
of that version 11 offsets of 4 sizes on each gf180mcuD box-paint generator
(264 cases). The
defaults are the smallest square box the generator paints into, found by the
manifest tool by bisection on the 5 nm grid. Below the minimum Magic prints
a message (`Via1 width must be at least 0.26um`) and paints nothing; the
PCell then writes the same empty cell, as for the zero-size devices. The
guard-ring and well generators treat the box as the centre lines of their
contact strips, so their shapes extend outside it.

Each PCell's GDS is one cell, as Magic would write it for a cell holding only
that paint. Magic's menu paints into the user's own cell instead, where a
via1 painted next to existing via1 paint merges with it and gets one cut
array over the merged area; two via1 PCells side by side are two cells with
an array each, as two Magic subcells would be (read in the source; not run).

| PDK | Generator | In Magic's menu as | Minimum box (µm) | GDS layers at the minimum |
|---|---|---|---|---|
| sky130A | `mcon` | Devices 1 / mcon | 0.17 | 67/20, 67/44, 68/20 |
| | `via1` | Devices 1 / via1 | 0.26 | 68/20, 68/44, 69/20 |
| | `via2` | Devices 1 / via2 | 0.28 | 69/20, 69/44, 70/20 |
| | `via3` | Devices 1 / via3 | 0.32 | 70/20, 70/44, 71/20 |
| | `via4` | Devices 1 / via4 | 1.18 | 71/20, 71/44, 72/20 |
| | `subconn` | Devices 1 / substrate contact (1.8V) | 0.17 | 65/44, 66/44, 67/20, 94/20 |
| | `mvsubconn` | Devices 1 / substrate contact (5.0V) | 0.17 | 65/44, 66/44, 67/20, 75/20, 94/20 |
| | `subconn_guard` | Devices 1 / substrate guard ring (1.8V) | 0.6 | 65/44, 66/44, 67/20, 94/20 |
| | `mvsubconn_guard` | Devices 1 / substrate guard ring (5.0V) | 0.6 | 65/44, 66/44, 67/20, 75/20, 94/20 |
| | `nwell` | Devices 1 / n-well region with guard ring (1.8V) | 0.6 | 64/20, 65/44, 66/44, 67/20, 93/44 |
| | `mvnwell` | Devices 1 / n-well region with guard ring (5.0V) | 0.6 | 64/20, 65/44, 66/44, 67/20, 75/20, 93/44 |
| | `deep_nwell` | Devices 1 / deep n-well region (1.8V) | 3.0 | 64/18, 64/20, 65/44, 66/44, 67/20, 93/44 |
| | `mvdeep_nwell` | Devices 1 / deep n-well region (5.0V) | 3.0 | 64/18, 64/20, 65/44, 66/44, 67/20, 75/20, 93/44 |
| gf180mcuD | `via1` | Devices 2 / via1 | 0.28 | 34/0, 35/0, 36/0 |
| | `via2` | Devices 2 / via2 | 0.28 | 36/0, 38/0, 42/0 |
| | `via3` | Devices 2 / via3 | 0.28 | 40/0, 42/0, 46/0 |
| | `via4` | Devices 2 / via4 | 0.28 | 41/0, 46/0, 81/0 |
| | `subcon_3p3` | Devices 2 / substrate contact (3.3V) | 0.23 | 204/0 only (see above) |
| | `subcon_06v0` | none: the "substrate contact (6.0V)" entry calls `subcon_6p0_draw`, which doesn't exist | 0.23 | 204/0 only |
| ihp-sg13g2 | `via1` to `via4` | none (commented out of the PDK's menu) | 0.2 | metal n, via n, metal n+1 (8/0, 10/0, 19/0 for via1) |
| | `via5` | none | 0.62 | 67/0, 125/0, 126/0 |
| | `via6` | none | 1.9 | 126/0, 133/0, 134/0 |
| | `subconn`, `hvsubconn` | Devices / substrate contact (1.8V), (5.0V) | 0.16 | 1/0, 6/0, 8/0, 14/0 (+ 44/0 for hv) |
| | `subconn_guard`, `hvsubconn_guard` | Devices / substrate guard ring (1.8V), (5.0V) | 0.6 | 1/0, 6/0, 8/0, 14/0 (+ 44/0) |
| | `nwell`, `hvnwell` | Devices / n-well region with guard ring (1.8V), (5.0V) | 0.62 | 1/0, 6/0, 8/0, 31/0 (+ 44/0) |
| | `deep_nwell`, `hvdeep_nwell` | Devices / deep n-well region (1.8V), (5.0V) | 3.0 | 1/0, 6/0, 8/0, 31/0, 32/0 (+ 44/0) |
| ihp-sg13cmos5l | `via1` to `via3` | none | 0.2 | as on ihp-sg13g2 |
| | `via4` | none | 0.62 | 50/0, 125/0, 126/0; its messages say "Via5" (the proc is a copy of sg13g2's `via5_draw`) |
| | `subconn`, `hvsubconn`, `subconn_guard`, `hvsubconn_guard`, `nwell`, `hvnwell` | Devices / as on ihp-sg13g2 | as on ihp-sg13g2 | as on ihp-sg13g2 |

Magic's own messages have mistakes the PCells copy: sky130A's `via4_draw`
prints `Via3 width must be at least 1.18um` for its own minimum, and IHP's
`hvnwell_draw` prints a 0.26 µm height minimum while it tests 0.62 (read in
the source).

## Configuration

A value comes from the environment if set, then from
`$XDG_CONFIG_HOME/klayout-magic-pcells/config.ini` (else
`~/.config/klayout-magic-pcells/config.ini`, section `[kmp]`, keys in lower
case without the `KMP_` prefix, for example `magic = /opt/magic/bin/magic`),
then from the default. The settings of one PDK go in a section `[kmp:<pdk>]`
(for example `[kmp:ihp-sg13g2]` with `magicrc = /opt/ihp/ihp-sg13g2.magicrc`;
the keys are `magicrc`, `manifest` and `netgen_setup`), or in the
environment as `KMP_MAGICRC_<PDK>`, `KMP_MANIFEST_<PDK>` and
`KMP_NETGEN_SETUP_<PDK>`, with the PDK name in upper case and `-` written
as `_` (`KMP_MAGICRC_IHP_SG13G2`).
`klayoutrc` isn't used because KLayout doesn't save it under `-b`.

| Variable | Default | Meaning |
|---|---|---|
| `KMP_PDKS` | `auto`: every supported PDK whose rcfile exists under `PDK_ROOT` (or whose `KMP_MAGICRC_<PDK>` is set) | the PDKs to register, separated by commas or spaces, or `all` |
| `KMP_PDK` | `sky130A` | the PDK that the unqualified `KMP_MAGICRC`, `KMP_MANIFEST` and `KMP_NETGEN_SETUP` apply to, and the default PDK of `tools/build_manifest.py` and `run_sweep.py`; when `KMP_PDKS` is unset and `KMP_PDK` is set, only that PDK registers, as in version 0.2 |
| `KMP_MAGIC` | `magic` on `PATH`, then `/foss/tools/bin/magic` | Magic executable |
| `PDK_ROOT` | `/foss/pdks` | directory that holds the PDKs; the rcfiles read it too |
| `KMP_MAGICRC_<PDK>` | `$PDK_ROOT/<pdk>/libs.tech/magic/<pdk>.magicrc` | that PDK's Magic rcfile |
| `KMP_MANIFEST_<PDK>` | the shipped `manifest-<pdk>.json` | path to a rebuilt manifest |
| `KMP_CACHE_DIR` | `$XDG_CACHE_HOME/klayout-magic-pcells`, else `~/.cache/klayout-magic-pcells` | cache root, shared by all PDKs |
| `KMP_CACHE` | `1` | `0` keeps nothing on disk between sessions; the checks then run in `tmp-*` job directories, which are removed once their results have been read (see [Job directories](#job-directories)) |
| `KMP_BACKEND` | `server` | `server`, or `oneshot` (one Magic process per request, for debugging) |
| `KMP_TIMEOUT` | `30` | seconds per request |
| `KMP_LAZY` | `0` with `server`, `1` with `oneshot` | when 1, the GUI form shows an Update button instead of regenerating on every edit; a device's form still asks Magic on every edit, because the values it shows come from Create |
| `KMP_LOG` | unset | file that receives every request and reply line |
| `KMP_DRC_STYLE` | `drc(full)` | Magic's DRC style for the DRC check: `drc(fast)`, `drc(full)` or `drc(routing)`, the styles all four PDKs have; another name is refused. Magic itself starts in `drc(fast)` |
| `KMP_DRC_MODE` | `hierarchical` | `hierarchical` or `flat` (see [Magic DRC](#magic-drc)); any other value is an error |
| `KMP_JOB_TIMEOUT` | `1800` | seconds for each Magic process of a check, and for each netgen run |
| `KMP_NETGEN` | `netgen` on `PATH` | netgen executable, for LVS |
| `KMP_NETGEN_SETUP_<PDK>` | `$PDK_ROOT/<pdk>/libs.tech/netgen/<pdk>_setup.tcl` | that PDK's netgen setup file |
| `KMP_MENU` | `1` | `0` leaves the Magic menu out of the GUI; the libraries still register |
| `KMP_JOB_KEEP` | unset | `1` keeps the checks' `tmp-*` job directories and the `lvs-*` folders of LVS runs (see [Job directories](#job-directories)); read from the environment only, not from `config.ini` |

`doctor` and the Magic menu's Settings... entry list the settings that
`config.ini` can hold, each with its value and where that comes from, and
`doctor` names a missing netgen or netgen setup file in a `PROBLEM:` line;
the PCell libraries register without them. The menu's dialogs keep their
last choices in `state.json`, beside `config.ini`.

A PDK named in `KMP_PDKS` that isn't installed, or that this version doesn't
support, gets one logged error that names the variable to set, and no
library; the other PDKs still register. With the default `auto`, a PDK that
isn't installed is skipped without a message. Every registered PDK costs a
Magic process for the whole KLayout session, so a user of one PDK can set
`KMP_PDKS` to it.

The PCell libraries read `KMP_PDK` and `KMP_PDKS` and ignore `PDK`, because
the iic-osic-tools image sets `PDK=ihp-sg13g2` by default. The checks use
`PDK` only as the last guess of their PDK choice (see [Checking a layout
with Magic](#checking-a-layout-with-magic)), and say so when they do. A GUI started from a
desktop launcher may not get the login shell's `PATH`; set `magic` in
`config.ini` then.

## The cache

KLayout regenerates every PCell variant when it opens a file. The cache saves
a Magic call per variant on each later open, and if Magic fails during a
session, variants that are already in the cache still come from disk. An
entry is Magic's GDS exactly as Magic wrote it plus a JSON sidecar with the
request, Magic's checked values, its messages, its cell name and the SHA-256
of the GDS, under `<cache>/v1/<versions digest>/<device>/<key>.gds` and
`.json`.

A GDS whose bytes no longer match the digest in its sidecar (truncated,
overwritten, or another entry's file copied over it), or a sidecar written
for another device, counts as a miss: the entry is deleted and Magic
generates it again. If a GDS from the in-memory memo or the disk can't be
read anyway, produce logs a warning, drops the entry and asks Magic once.
`KMP_CACHE=0` keeps the session's entries in a temporary directory that is
deleted when the process exits. If the cache directory can't be written, the
library registers without the disk cache and logs a warning that names
`KMP_CACHE_DIR`. Each Magic process of the PCell libraries runs in its own
empty directory under `<cache>/run` (or the system temp directory without a usable cache), which
is deleted when Magic stops; Magic looks for cells in its working directory
first, so a stray `.mag` file there can't stand in for a vendor cell. Magic
writes into `<cache>/tmp`, and each versions directory names its PDK in a
`versions.json`.

If `cache clear` or `cache prune` runs in another shell, or the cache
directory is deleted, while KLayout has the libraries open, the session
makes its directories again when it next writes, and generates again any
variant it remembered whose file is gone. A backend test does each of
these under a running session.

The key is a SHA-256 over the PDK, the device, the request text, the Magic
version, the PDK's commit (open_pdks' from `SOURCES` for sky130A and
gf180mcuD, the `COMMIT` file for the IHP PDKs), the tech file version, a
digest of the text of every proc loaded in the PDK's generator namespace and
in `::magic`, a digest of the tech file, a digest of every file in the
directory that holds it (`libs.tech/magic`: the IHP tech files include four
more tech files and the IHP fixed devices source layout scripts from there),
a digest of the vendor files that fixed devices copy (each vendor cell's
`.mag`, found on Magic's search path as `getcell` finds it, and the whole GDS
file it names, such as the 10.5 MB `sky130_fd_pr.gds`), and the cache format
(4 in this version: the sidecar also records what Magic's dialog shows when
it reopens on the instance, and a request may be an Apply). Editing a
generator file or a vendor GDS locally therefore starts new entries, and so
does a new Magic, PDK or cache format. For a device the request text is the
form of Magic's dialog that the instance's state stores (see [Values as
Magic's dialog shows them](#values-as-magics-dialog-shows-them)), with
`kmp_apply` set to `1` when Apply made the cell; for the defaults that is the
same text version 0.4 sent. What the dialog made of a form and a set of
edits is kept as well, as `<cache>/v1/<versions digest>/_dialog/<key>.json`,
under a key over the same versions fields, the device, the whole dialog
request (the form, the edits, and the widget order and dependencies the
manifest gives) and a digest of the server's Tcl files, which hold the
plugin's model of the dialog's bindings, so after a change to that model
the cache doesn't return entries that the old model wrote. To manage the
cache:

```sh
python3 -m klayout_magic_pcells cache prune    # delete the selected PDKs' old versions directories
python3 -m klayout_magic_pcells cache clear    # delete every entry of every PDK
python3 -m klayout_magic_pcells cache stats
```

`prune` works on the PDKs that `--pdk` or `KMP_PDKS` selects: it starts each
one's Magic to learn its current versions digest, deletes that PDK's other
versions directories and any directory with no entries, and keeps the
directories of every other PDK; it prints the name of each one it keeps.
A user who sets `KMP_PDKS` to one PDK therefore keeps the other PDKs'
entries; `KMP_PDKS=all` prunes every
installed PDK. Both commands leave Magic's files in `<cache>/tmp` unless they
are more than a day old.

### Job directories

The checks of [Checking a layout with Magic](#checking-a-layout-with-magic)
run each Magic process in a directory of its own under
`<cache>/jobs/<pdk>/<kind>/`, where `<kind>` is `drc`, `extract`
(extraction and LVS) or `rw` (the generated-layer check and `ports
--magic`). The directory keeps the exported GDS (`in.gds`), what Magic
wrote (error lists, `.ext` files, the netlist, netgen's report) and
`job.json`, which records the job's PDK, its state (running, done or
failed), the process that started it and a fingerprint of the versions it
ran with.

With the cache on, a job's directory ends up as `<key>/`. The key is a
SHA-256 over the exported file's SHA-256, the kind, the check's options,
the PDK, a digest of the PDK and Magic (the SHA-256 of the Magic executable
and of the rcfile, every file in the rcfile's directory, and the PDK's
commit), a digest of the jobs' Tcl scripts, and the plugin version. A
second check of an unchanged cell with the same options finds a finished
directory and reads it without starting Magic. For DRC the options are the
style, the mode and the cells of each Magic process, not the area, so an
area check reuses the whole-cell job (see [Magic DRC](#magic-drc)).

Magic doesn't run in a key's directory. A job runs in a new
`tmp-<random>/` beside it, and when Magic has ended, that directory is
renamed to `<key>/` in one step. When two runs with the same key overlap (the GUI and the
command line on one layout, or two cells that export to the same file),
the first to end fills the cache, and the other reads its own results from
its `tmp-*` directory, which is then removed as described below. The next
run with the same key replaces a key's directory that holds a failed or
unfinished job. It also replaces one whose job is done but that lacks a
file the check reads, once the process that ran that job has ended.

`--no-cache` and `KMP_CACHE=0` mean the same for every check: the job runs
in a new `tmp-<random>/` directory and neither reads nor fills the cache. A
`tmp-*` directory is removed once its results have been read (on the
command line when the command ends, in the GUI once the result is shown),
and at the latest when the process exits, and so is the `lvs-<random>/`
folder that an LVS run makes in a cached extraction's directory;
`KMP_JOB_KEEP=1` keeps them. The checks need a writable cache directory
even with `KMP_CACHE=0`; without one a job fails, exit 2, with a message
that names `KMP_CACHE_DIR`.

The cache commands cover these directories too. `cache clear` deletes every
job directory except that of a job that is still running, so it also takes
a live session's finished `tmp-*` directories. `cache prune` deletes, for
the PDKs it works on, the job directories whose fingerprint isn't the
current one and the `tmp-*` directories whose process has ended, and any
job directory without a readable `job.json` that is more than a day old.
In the key directories it keeps, it deletes the `lvs-*` folders whose LVS
process has ended (each folder's `kmp_owner.json` names it), and those
more than a day old that have no such file. `cache stats` prints their
number and total size as `jobs` and `jobs_bytes`, over every PDK, or with
`--pdk P` over P's alone. In the case suite's `inverters` folder:

```
$ env KMP_JOB_KEEP=1 python3 -m klayout_magic_pcells lvs inv.gds --pdk sky130A --schematic inv.spice --no-cache
lvs: inv against inv in inv.spice (sky130A): netgen: Circuits match uniquely. The layout matches.
  Export/Magic does not read this layer: 1 item
$ find /repo/out/docs2/cache-ex/jobs -maxdepth 3 -name 'tmp-*'
/repo/out/docs2/cache-ex/jobs/sky130A/extract/tmp-2n7hg3t5
$ python3 -m klayout_magic_pcells cache prune --pdk sky130A
removed /repo/out/docs2/cache-ex/jobs/sky130A/extract/tmp-2n7hg3t5
...
```

The kept directory held `in.gds`, `inv.ext`, `job.json`, `kmp_result.json`,
`lvs/` and `netlist.spice`. Without `KMP_JOB_KEEP` the same command left
no `tmp-*` directory.

## Stamps and audit

Every variant carries two stamps of the form
`kmp1;magic=8.3.681;tech=1.0.588-56-g026824c;pdk=sky130A;digest=<12 hex>`.
The digest is a SHA-256 over the PDK name, the Magic version, the PDK's
commit, the tech version, the proc text, the tech file, the files of
`libs.tech/magic` and the vendor files, the same inputs as the cache key, so
a locally edited generator file or vendor GDS gives a different stamp even
when the version strings are the same.

- *generated by*: a GDS property (attribute 100) on one shape, the boundary
  box where the device has one on 235/4 (sky130A), otherwise the shape on the
  lowest layer with the smallest corner (on gf180mcuD that is the 0/0
  boundary), with the first 16 hex digits of the cache key and the grid of
  this variant's Magic output added (`;key=<16 hex>;grid=5`: the coarsest
  grid, in nm, that all its coordinates lie on). It survives GDS and OASIS
  with or without the library.
- *created with*: the hidden PCell parameter `kmp_created`, stored in the
  file with the other parameters. When a file is reopened under a different
  Magic or PDK, or with edited generator code, produce logs a warning,
  because the regenerated geometry may differ from what the file was made
  with.

Version 0.3's digest covers more inputs than 0.2's, so a file made with
version 0.2 logs that warning once when it is reopened. Versions 0.4 to 0.6
have the same digest as 0.3, so they reopen 0.3's files without the warning
(for what 0.5 and later draw for an older file, see [Values as Magic's
dialog shows them](#values-as-magics-dialog-shows-them)). Since version 0.5
the cache format is 4, so the versions directory (`3341d4166cfc` for
sky130A in the image, with 0.5 and 0.6 alike) is not 0.3's and 0.4's
(`24feca9ae925`), and these versions don't read the older cache;
`cache prune` deletes the old directories. Stamps written by version 0.1.0
have no digest; they are compared on Magic, tech and PDK alone.

`audit` reads a file without registering any library and reports the cells
of all four libraries: cells with an error marker, without a stamp, with no
shapes, or stamped by a different Magic, PDK or generator code than the
installed one, and a file database unit that doesn't divide 5 nm. A cell
belongs to a PDK by its library name, since several PDKs have a device
called `rm1`. It also reports a cell whose Magic output lies on a finer
grid than the file's database unit, from the grid in the cell's stamp: a
sky130A `mcon` with a 1.175 µm box lies on 5 nm, so a file at dbu 0.002 µm
rounds it, while the default `mcon` lies on 10 nm. A stamp written by
version 0.3 or earlier has no grid; audit then uses the grid of the device's
default output, which the manifest records, and says so in its message, and
a cell that a non-default size puts on a finer grid can go unreported.
`--regen` also registers the libraries the file uses, with every variant
generated by Magic as if the memo and the disk cache were empty, and compares
each cell's stored geometry with what the installed Magic generates now; a
difference, or a cell that regenerates as the error marker, is a problem. A disk-cache entry
that differs from what Magic generates now is reported too, and replaced.
`audit` exits 1 when any cell or the file has a problem.

```sh
python3 -m klayout_magic_pcells audit design.gds --regen
```

## If Magic is missing or fails

`register()` starts Magic before it registers a library. If Magic, a PDK's
rcfile or its manifest is missing, if Magic doesn't start, or if the running
Magic doesn't define every generator in the manifest (an rcfile that loads
no PDK or another PDK, or a generator file that fails to load), it logs one
error for that PDK, naming the variable to set, and registers no library for
it. The error carries Magic's exit status and its last messages on stderr,
such as
`Could not find file '/nonexistent/sky130A/libs.tech/magic/sky130A.tech'`
for a wrong `PDK_ROOT`. For an rcfile that loads no PDK, empty or broken, it
says the rcfile loaded no PDK and quotes Magic, for example
`Error parsing "/tmp/x.magicrc": missing close-brace`. Registering the devices that are present and leaving
out the missing ones is not supported. Cells in files opened while a library
isn't registered show as `<defunct>sky130_magic.…` (or the other library
names) and keep the geometry stored in the file; saving keeps that geometry.
Call `klayout_magic_pcells.register()` from the macro console once the
setting is fixed, and the open cells come back as live PCells.

If a generation fails while the library is registered (Magic failed twice in
a row, timed out, stopped in the endless `mos_check` loop, or wrote a GDS that
KLayout can't read), or a value is refused, produce doesn't raise. It draws a
1 × 1 µm box and a `KMP_ERROR <device>: <reason>` text on layer 255/0, which
none of the four PDKs' layer files lists. The reason includes what Magic
printed, for example
`Can't find GDS file "$PDKPATH/libs.ref/sky130_fd_pr/gds/sky130_fd_pr.gds"`
when the vendor GDS of a fixed device is missing. When a generator's error
is followed by `gencell_create`'s own (an IHP fixed device whose layout
script is missing), Magic's message comes first:
`KMP_ERROR diodevdd_2kv: diodevdd_2kv: couldn't read file ".../diodevdd_2kv.tcl": no such file or directory (then gencell_create: can't read "instname": no such variable)`.
KLayout saves that marker, `audit` reports it, and `generate` exits 1.

## Devices

Each library has a PCell for every `_draw` proc of its PDK that also has a
`_defaults` proc (a device Magic's `gencell` code can build) and for every
`_draw` proc that can be called with no arguments (a box-paint generator,
listed above). sky130A names below drop the `sky130_fd_pr__` prefix (and
`sky130_fd_bs_flash__` for the SONOS FET).

**sky130A** (`sky130_magic`):

| Family | Count | Devices |
|---|---|---|
| MOSFET | 12 | `special_sonosfet_star`, `nfet_01v8`, `nfet_01v8_lvt`, `nfet_03v3_nvt`, `nfet_05v0_nvt`, `nfet_g5v0d10v5`, `nfet_g5v0d16v0`, `pfet_01v8`, `pfet_01v8_hvt`, `pfet_01v8_lvt`, `pfet_g5v0d10v5`, `pfet_g5v0d16v0` |
| Varactor | 3 | `cap_var`, `cap_var_hvt`, `cap_var_lvt` |
| Resistor | 22 | `res_generic_l1`, `res_generic_m1` to `m5`, `res_generic_nd`, `res_generic_nd__hv`, `res_generic_pd`, `res_generic_pd__hv`, `res_generic_po`, `res_high_po_0p35`, `_0p69`, `_1p41`, `_2p85`, `_5p73`, `res_iso_pw`, `res_xhigh_po_0p35`, `_0p69`, `_1p41`, `_2p85`, `_5p73` |
| MIM capacitor | 2 | `cap_mim_m3_1`, `cap_mim_m3_2` |
| Diode | 8 | `diode_pd2nw_05v5`, `_05v5_hvt`, `_05v5_lvt`, `_11v0`, `diode_pw2nd_05v5`, `_05v5_lvt`, `_05v5_nvt`, `_11v0` |
| Photodiode | 1 | `photodiode` |
| Fixed layout | 12 | `cap_vpp_04p4x04p6_m1m2_shieldl1`, `cap_vpp_08p6x07p8_m1m2_shieldl1`, `cap_vpp_11p5x11p7_m1m2_noshield`, `cap_vpp_11p5x11p7_m1m2m3m4_shieldl1m5`, `npn_05v5_W1p00L1p00`, `npn_05v5_W1p00L2p00`, `npn_11v0_W1p00L1p00`, `pnp_05v5_W0p68L0p68`, `pnp_05v5_W3p40L3p40`, `rf_test_coil1`, `rf_test_coil2`, `rf_test_coil3` |
| Box paint | 13 | `mcon`, `via1` to `via4`, `subconn`, `mvsubconn`, `subconn_guard`, `mvsubconn_guard`, `nwell`, `mvnwell`, `deep_nwell`, `mvdeep_nwell` |

**gf180mcuD** (`gf180mcu_magic`):

| Family | Count | Devices |
|---|---|---|
| MOSFET | 13 | `nfet_03v3`, `nfet_03v3_dss`, `nfet_05v0`, `nfet_06v0`, `nfet_06v0_dss`, `nfet_06v0_nvt`, `nfet_10v0_asym`, `pfet_03v3`, `pfet_03v3_dss`, `pfet_05v0`, `pfet_06v0`, `pfet_06v0_dss`, `pfet_10v0_asym` |
| MOS capacitor | 4 | `nmoscap_3p3`, `nmoscap_6p0`, `pmoscap_3p3`, `pmoscap_6p0` |
| Varactor | 4 | `nvaractor_3p3`, `nvaractor_6p0`, `pvaractor_3p3`, `pvaractor_6p0` |
| Resistor | 16 | `nplus_u`, `nplus_u_6p0`, `pplus_u`, `pplus_u_6p0`, `npolyf_s`, `npolyf_u`, `ppolyf_s`, `ppolyf_u`, `ppolyf_u_1k`, `ppolyf_u_1k_6p0`, `nwell` (the n-well resistor), `rm1` to `rm5` |
| MIM capacitor | 1 | `cap_mim_2p0fF` |
| Diode | 4 | `diode_nd2ps_03v3`, `diode_nd2ps_06v0`, `diode_pd2nw_03v3`, `diode_pd2nw_06v0` |
| Fixed layout | 11 | `eFuse`, `npn_00p54x02p00`, `npn_00p54x04p00`, `npn_00p54x08p00`, `npn_00p54x10p00`, `npn_05p00x05p00`, `npn_10p00x10p00`, `pnp_05p00x00p42`, `pnp_05p00x05p00`, `pnp_10p00x00p42`, `pnp_10p00x10p00` |
| Box paint | 6 | `via1` to `via4`, `subcon_3p3`, `subcon_06v0` |

**ihp-sg13g2** (`sg13g2_magic`):

| Family | Count | Devices |
|---|---|---|
| MOSFET | 8 | `sg13_lv_nmos`, `sg13_lv_pmos`, `sg13_hv_nmos`, `sg13_hv_pmos`, `sg13_lv_rfnmos`, `sg13_lv_rfpmos`, `sg13_hv_rfnmos`, `sg13_hv_rfpmos` |
| Varactor | 1 | `SVaricap` |
| Resistor | 10 | `rsil`, `rppd`, `rhigh`, `rm1` to `rm7` |
| MIM capacitor | 2 | `cap_cmim`, `cap_rfcmim` |
| Diode | 2 | `dantenna`, `dpantenna` |
| Bipolar transistor | 4 | `npn13g2`, `npn13g2l`, `npn13g2v`, `pnpMPA` |
| Inductor | 2 | `inductor2`, `inductor3` |
| Bond pad | 1 | `bondpad` |
| Via stack | 1 | `via` |
| Fixed layout | 8 | `diodevdd_2kv`, `diodevdd_4kv`, `diodevss_2kv`, `diodevss_4kv`, `nmoscl_2`, `nmoscl_4`, `schottky`, `scr1` |
| Box paint | 14 | `via1` to `via6`, `subconn`, `hvsubconn`, `subconn_guard`, `hvsubconn_guard`, `nwell`, `hvnwell`, `deep_nwell`, `hvdeep_nwell` |

**ihp-sg13cmos5l** (`sg13cmos5l_magic`):

| Family | Count | Devices |
|---|---|---|
| MOSFET | 8 | as on ihp-sg13g2 |
| Varactor | 1 | `SVaricap` |
| Resistor | 8 | `rsil`, `rppd`, `rhigh`, `rm1` to `rm5` |
| Capacitor | 1 | `cap_cmomf` (finger MOM capacitor; no MIM) |
| Diode | 2 | `dantenna`, `dpantenna` |
| Bipolar transistor | 1 | `pnpMPA` |
| Inductor | 2 | `inductor2`, `inductor3` |
| Bond pad | 1 | `bondpad` |
| Via stack | 1 | `via` |
| Fixed layout | 6 | `diodevdd_2kv`, `diodevdd_4kv`, `diodevss_2kv`, `diodevss_4kv`, `nmoscl_2`, `nmoscl_4` |
| Box paint | 10 | `via1` to `via4`, `subconn`, `hvsubconn`, `subconn_guard`, `hvsubconn_guard`, `nwell`, `hvnwell` |

The fixed-layout devices and the sky130A photodiode take only `nx`, `ny`,
`deltax` and `deltay`.

### Exclusions

The other `_draw` procs need arguments: they are internal helpers that the
device `_draw` procs call, and Magic's menus don't offer them. They get no
PCell, and the manifest lists each with that reason:

| PDK | Helpers |
|---|---|
| sky130A | `cap`, `diode`, `fixed`, `guard_ring`, `mos`, `photodiode`, `res` |
| gf180mcuD | `cap`, `diode`, `fixed`, `mos`, `res` |
| ihp-sg13g2 | `cap`, `diode`, `fixed`, `guard_ring`, `mos`, `res`, `var` |
| ihp-sg13cmos5l | `diode`, `fixed`, `guard_ring`, `mos`, `res`, `var` |

`sky130A.tcl` defines `res_xhigh_po_0p35_draw` twice with the same body, which
is why it has 81 `_draw` definitions for 80 procs. The IHP files `sealring_*.tcl`
and `read_sram_gds.tcl`, and the isolbox and seal ring that `ihp-sg13g2.tcl`'s
header lists, have no `_draw` proc.

### Menu entries that call undefined generators

The manifest records menu entries whose command names a generator the PDK
doesn't define. In the image's PDKs there are two, both on gf180mcuD: "nwell
(3.3V) -1680 Ohm/sq" calls `gf180mcu::nwell_3p3` (the device is `nwell`), and
"substrate contact (6.0V)" calls `gf180mcu::subcon_6p0_draw` (the generator is
`subcon_06v0_draw`). Research for version 0.3 also found, by reading
`gf180mcuD.tcl`, that the "npolyf_s" entry calls `ppolyf_s`, that one npn
label appears twice so that the second makes `npn_00p54x04p00`, and that
`nfet_10v0_asym`, `pfet_10v0_asym`, `npolyf_s` and `nwell` can't be reached
from a working menu entry. The PCells offer all of them.

### The manifests

The PCell declarations come from
`python/klayout_magic_pcells/data/manifest-<pdk>.json`, built by querying
Magic in the pinned image. For each device the tool records its defaults,
its dialog widgets (by running `_dialog` against stub widget procs), what
`_check` does on the defaults and at 0, 10000 and 2.5 for each number, and
Magic's output for the defaults; for each box-paint generator, its minimum
box, its message one step below it and its output at the minimum.

```sh
scripts/manifest.sh                       # rebuild all four (python3 tools/build_manifest.py --all, in the image)
scripts/manifest.sh --check               # exit 1 if a committed manifest differs from the installed Magic
scripts/manifest.sh --pdk gf180mcuD       # one PDK
```

## Tests

Everything runs inside the pinned image, through `scripts/in_image.sh`, which
mounts the repository at `/repo` and uses a login shell (the image puts Magic
and KLayout on `PATH` only there).

```sh
scripts/test.sh                                       # unit tests and the gap table's, then the backend tests once per PDK
scripts/parity.sh                                     # every PDK in turn, full sweep
scripts/parity.sh --pdk gf180mcuD                     # one PDK
scripts/parity.sh --pdk all --quick                   # each generator's defaults and the jobs step's quick set, every PDK
scripts/parity.sh --pdk sky130A --devices 'sky130_fd_pr__res_*' --keep
scripts/parity.sh --pdk ihp-sg13g2 --update-baseline  # rewrite that PDK's baselines
```

Each PDK runs in its own container, with the image's `PDK` variable set to
it, and writes `out/parity/<pdk>/report.json` and `report.md`; without
`--pdk` (or with `--pdk all`) the four run one after another and
`out/parity/summary.json` and `summary.md` collect them. The script exits 0
when every check of every PDK passes, 1 when any check fails, and 2 when the
harness itself fails. For each PDK it runs the steps below in one
container. This list numbers them 1 to 12; `run_sweep.py` and its log
number the same steps from 0 and join some of them, so the extraction
check (item 11) is its step 8 and the jobs step (item 12) its step 9:

1. the unit tests (`tests/unit`, 401 tests) and the backend tests for that
   PDK (`tests/backend`, 95 tests, each run with the PDK's own devices).
   The unit tests cover:
   - configuration, including the PDK selection and per-PDK settings;
   - the wire format;
   - the cache key and the cache files, including damaged and swapped
     entries, prune per PDK and a cache deleted under a session;
   - value formatting (including 6,000 doubles saved by KLayout and read
     back in a second process), and the checks of coverage strings, choices
     and number lists;
   - the GDS import, the coordinate grid of Magic's output and audit's use
     of it, and stamps and their digest;
   - the PCell declarations of all four manifests, and the manifests'
     counts, box-paint entries, exclusions and coordinate grids;
   - Magic's error text, the raw GDS font reader and `compare.py`'s command
     line;
   - the path A watchdog, driven by a fake Magic that crashes on one point
     and hangs on another and by one that dies with an X error at start-up;
   - the stored dialog state, against a fake Magic: when it is used and when
     the values are typed into the dialog again, the defaults shown as
     Create shows them, edits in the dialog's row order, a later edit typed
     into what the dialog shows and drawn by Apply, an Apply that keeps the
     instance, a fixed device's Apply drawn as Create, a value that Magic
     reads no number from kept in its field, another device's state with
     the same widget names not used, the widgets that the defaults lack sent
     with the form and no other widget that isn't a parameter, refused and
     damaged states never sent, every device's dialog order in the
     manifests, and the dialog cache key over the whole request and the
     server's code;
   - the checks of [Checking a layout with
     Magic](#checking-a-layout-with-magic), without Magic (the number of
     tests in brackets): the job runner against a fake Magic that finishes,
     fails, never prints its done line, hangs past the timeout or is
     cancelled, with no process left, the job cache key, where jobs run
     (`tmp-*` directories, their removal and `KMP_JOB_KEEP`, two jobs on
     one key at once), the cache commands on job directories, `extract`'s
     netlist file and its refusal, `extract` and `lvs` on a cell Magic
     reads nothing in (the finding, status 1 and no netlist), an export
     that KLayout can't write (status 2), and a cancelled LVS task
     (`test_jobs.py`, 49); the export's renamed cells, flattened instances,
     off-grid vertices, unread layers and layers drawn in another cell
     (`test_export.py`, 19); the report database, its lines of text and
     its information items (`test_markers.py`, 9);
     the choice of PDK, also with a technology that the layers contradict
     (`test_pdk_choice.py`, 11); the reader of the PDKs' Magic tech files
     behind the data files, its label layers of the comment plane, and
     the foundry rules that sky130A's F1 items name (`test_pdk_data.py`,
     45); DRC's rule IDs, units, area filter, dropped copies, the sorting
     of subcell boxes, a box that the top cell's check lists filed in the
     top cell, the result message's first line, the layer names from the
     tech file's type synonyms, a message's gap-table rows, found by its
     statements' tech-file lines, the one-line description and its
     command, and that each shipped gap file holds every statement of the
     PDK's data file (`test_drcjob.py`, 38); the `.ext` reader, its unit
     and the instance transforms in all eight orientations and in arrays
     (`test_extfile.py`, 12); netgen's verdicts and JSON, from saved
     reports, and the pin that the JSON leaves out and the report names
     (`test_netgen.py`, 26, two of which read a folder of saved netgen
     reports outside the repository and are skipped unless
     `KMP_NETGEN_EVIDENCE` names that folder); F1 to F5 on small layouts,
     the F3 item of a contact on diffusion without an implant, the
     message's first line, and failed exports (`test_layercheck.py`, 30);
     P1 to P8, a standard cell's own texts and pin boxes, and the message's
     first line (`test_portcheck.py`, 17); the case suite's builder, with
     its sheet's 5 nm steps (`test_cases.py`, 15); and the Magic menu
     against a stand-in for KLayout: no menu with `KMP_MENU=0` or without
     a main window, one menu after two installs, `state.json`, the options
     a Rerun gets, the progress text, the PDK dialog's sentence, job
     directories released once a result is shown, Extract never replacing
     a file the plugin didn't write, the result message's text, the
     browser brought to the front when it closes, windows sized to the
     screen, netgen's report shown at its end, the Extract dialog's title,
     and the question about a netlist of the plugin in the LVS dialog
     (`test_gui.py`, 28).

   The backend tests cover:
   - every generator generated twice in one Magic session with no restart;
   - the session state put back after requests that change it, compared
     with a fresh Magic;
   - the box that a box-paint check reports, and negative, zero, `inf` and
     `nan` boxes on every box-paint generator;
   - a brace in a value, a killed Magic restarted and the request retried,
     a timeout, an unknown device, `_check` messages, and the endless
     `mos_check` loop stopped (on gf180mcuD, whose loop ends, the device
     drawn);
   - a value holding a Tcl command, refused by the server and, after saving
     and reopening a file with an empty cache, never run;
   - damaged cache entries regenerated, the cache cleared, pruned and
     deleted under a running session, and a prune that leaves another PDK's
     entries;
   - start-up failures that name their cause, an empty and a broken rcfile
     refused with Magic's words, and an rcfile that loads another technology
     than the PDK's (a copy of its tech file under another name);
   - a missing vendor GDS or IHP layout script named in the error marker,
     and an unwritable cache directory;
   - `audit` after a local edit of the PDK's `via1_draw`, with a stale cache
     entry, and on files at dbu 0.002, 0.0025 and 0.001;
   - a generator edited to raise, reopened;
   - the values Magic's dialog shows, saved to GDS and OASIS and kept
     through three reopens in fresh processes, a library refresh and a
     second save, with the disk cache off and no dialog run on reopen (on
     sky130A, `res_high_po_0p69`, `cap_mim_m3_1`, `res_high_po_0p35` and
     `res_xhigh_po_5p73`, on which typing a stored value again would change
     the form);
   - a Tcl command put into a saved dialog form or into the saved dialog it
     shows, never run;
   - the form callback's icons, the CLI's exit codes and temporary
     directories, a manifest whose names collide, no Magic left running
     after the client exits normally or is killed, and registration from
     plain Python;
   - the checks of [Checking a layout with
     Magic](#checking-a-layout-with-magic), with Magic and netgen: the
     unit Magic prints for `[cif scale out]`, cell names that Magic
     mishandles refused, every such name loaded once the export has
     renamed it, a timeout and a cancel that leave no Magic, a Tcl error
     in the job's script that fails the job instead of hanging it, and
     two jobs on one key at once
     (`test_jobs_backend.py`, 7); DRC on a clean cell and one-change cases
     against Magic's counts per rule, the case suite's `hier` cases in both
     modes, the export against the harness's `mdrc.tcl` on the same file,
     the long n-well's area check, the cell names, the error-marker
     refusal, batches of 15 cells, the cache, poll and cancel, the command
     line with its report database read back against its TSV, the PCell
     inverter's information boxes, cells Magic reads nothing in, and the
     GDS layers named for three rules per PDK (`test_drc_backend.py`, 17);
     the hand inverter against its schematic, the open-drain, texts-only
     (with an item for every schematic pin) and swapped-texts variants and on sky130A the W 0.36 variant with
     their markers, every `.ext` port box holding its GDS text, `--caps`,
     the cache, two LVS runs on one extraction, a property error inside a
     PCell variant, and every device's defaults read back from GDS against
     `readback-<pdk>.json` (`test_lvs_backend.py`, 15); and the
     generated-layer check on the negative controls, its positive cases,
     the `hier` set and cells Magic reads nothing in, and the port check on
     the port variants (`test_layers_backend.py`, 14).

   Only these backend tests are PDK-specific: a device without `_check` or
   with one that raises (ihp-sg13g2, gf180mcuD), `audit` after an edit of
   sky130A's vendor GDS, Magic behaviour that the dialog model leaves out
   on sky130A (the snake resistor's `w` flipping on every `_check`, and
   `res_generic_po` at `l 0` drawing nothing with one `_check` and drawing
   with the dialog's), in the sky130A pass, all four libraries registered
   under `klayout -b -rm` and from the Salt autorun under `klayout -zz`,
   and, of the checks' tests, the W 0.36 inverter and the PCell inverter's
   information boxes (sky130A), P8 on a text that Magic makes no port of
   (ihp-sg13cmos5l), a
   layer Magic reads as another type (the IHP PDKs) and the case suite's
   cells Magic reads nothing in (sky130A and ihp-sg13g2);
2. `tools/build_manifest.py --pdk <pdk> --check`;
3. the sweep (`tests/parity/gen_sweep.py`): for each device the defaults,
   the minimum and maximum of each number, a value below each minimum that
   Magic enforces, each checkbox flipped, counts of 1 and 4, each other
   choice of a selectlist, `2` and `1 2` for a number list, `+50` and `-50`
   for each coverage string, ` -50` and a tab before `+30` on the first and
   last coverage string, W and L off the 0.01 µm grid, `w = 0` and `l = 0`
   on resistors and diodes, a MOSFET more than 30 µm wide, and 5 seeded
   random combinations; for each box-paint generator its minimum on each
   side, 5 nm below it on each side, squares, wide and tall boxes, an
   off-grid width, 20 × 20 µm, negative widths and heights, a negative zero
   and 5 random sizes. The numbers of those points have at most 6 decimals,
   so every generator also gets every float at 12 and at 15 significant
   digits, at a 12-digit rounding tie (13 digits ending in 5), and one ULP
   from such a tie. At most 64 points per device. Each device also gets
   edit points: the default device created and then edited to the values
   of up to 12 of its other points (random, zero, minimum, maximum and
   below-minimum points first), and each of its random points 1 to 4
   created and then edited to the next one's values.
   The text for Magic and the typed values for the PCell come from
   `tests/parity/magic_text.py`, which restates this README's formatting
   contract and imports nothing from the plugin; coverage strings are used
   exactly as typed;
4. path A, Magic alone: `tests/parity/magic_ref.tcl` calls `magic::gencell`
   for every device point but the edit points, and for a box-paint point
   sets the box and calls
   the generator with no arguments, all in one Magic process run in an empty
   directory, using none of this package's code. It takes the generator
   namespace from the PDK's own `PDKNAMESPACE`, puts back the layer locks,
   units and box stack after every point as the server does, and has its own
   copy of the endless-loop guard; `run_sweep.py` watches it: a point on
   which Magic crashes or makes no progress for 300 s is recorded as a Magic
   error, and Magic starts again on the next point;
5. path D, Magic's own dialog: `tests/parity/dialog_ref.tcl` under
   `xvfb-run magic -d XR`, using none of this package's code, does for every
   device point what a user of the "Devices" menu does: it opens the "New
   device" dialog with `magic::gencell <ns>::<device>`, types the point's
   values into their widgets in the dialog's row order (an entry gets the
   text and its `<Return>` binding runs, a checkbox is clicked, a choice is
   picked), reads the form back, presses Create, reads the dialog that
   Create reopens on the new instance ("Edit device"), and writes the cell
   Create made. On an edit point it then types the point's values into
   that dialog, each where the field shows another value (a number compared
   as the number `magic::spice2float` reads), presses Apply, reads the
   dialog reopened on the instance Apply left, and writes that instance's
   cell; where the dialog didn't reopen on the instance (gf180mcuD's three
   stub devices) it deletes the instance and presses Create again. It
   records each widget's binding on the device's first point. It
   restores the session state as path A does, except that it leaves fence,
   magnet and rotate unlocked as each Create leaves them and doesn't use
   `tech revert` (under the GUI each lock change takes longer than the one
   before); it starts a new Magic every 50 points, and has the same
   watchdog as path A, which also starts Magic again on the same point when
   it dies with an X error before its first point (up to 8 times in a row;
   see [CI](#ci));
6. path B, the PCell: `tests/parity/pcell_path.py` under `klayout -b -rm`
   with only that PDK's library registered, first with an empty cache and
   then again from the cache. For a device it passes the point's typed
   values through the PCell's coerce as the GUI form does
   (`dialog_values`), so the variant stores what the GUI stores, and it
   makes a second variant from the typed values as they are, which must
   draw the same shapes. An edit point's first values go through
   `dialog_values`, and then its stored values with the point's values
   changed in them;
7. per point, against path D for a device and against path A for a
   box-paint generator:
   - the request path B actually sent (read back through the stamp's key),
     which for a device must be the form Magic's Create or Apply got
     (marked `kmp_apply` for an Apply, and Create's form where Apply kept
     the instance);
   - for a device, the stored values against what Magic's dialog shows when
     it reopens on the instance (a value in SPICE notation against the
     number that path D's Magic reads from it, and where it reads none, the
     typed value), the stored `kmp_dialog` against that form's and that
     dialog's exact text, and the New device dialog as it opened against the
     manifest's defaults;
   - on an edit point, also the state after its first step against Create's
     form and the Edit device dialog that the edit started from;
   - XOR of every layer, the number of unmerged shapes on every layer, and
     every label with all its attributes, the font read from the raw GDS
     records of both files;
   - a census of the raw GDS records of the reference's file against
     `baseline/<pdk>/census.json`, for elements that KLayout has no shape
     for (the NODE elements above);
   - the bounding box (and, for each generator's defaults, the box in the
     manifest);
   - Magic's cell name, and Magic's checked values (for a box-paint point,
     the box Magic used);
   - the cached run against the first run, no error marker, and the stamp.

   Path A is the second reference for a device point that isn't an edit
   point: where its checked values equal those of the dialog's Create,
   `_draw` got the same values, and its geometry and cell name must be the
   same too; elsewhere the report counts the points where the two draw the
   same shapes. Each widget's binding in path D must run the same chain of
   passes as the server's `dialog` op;
8. for box-paint generators in the PDK's menu, the menu entry itself:
   `tests/parity/menu_ref.tcl` under `xvfb-run magic -d XR` invokes the entry
   on the box of each generator's default, wide and 20 × 20 µm points, and
   the result must equal path A's;
9. round trips on the default, minimum, maximum, below-minimum and zero
   points, the many-digit and tie points, the negative boxes and the
   random-to-random edit points, plus a 20 % sample of the other edit
   points and a 10 % sample of the rest:
   - reopen the GDS and OASIS files with the library and check for a live
     PCell, the stored values that path B saved and the request their state
     gives, the request that the reopened variant was drawn from (read back
     from the generator through its stamp's key), that Magic's dialog didn't
     run again, and geometry regenerated by Magic with the disk cache off
     and compared with the reference (the step fails if a variant comes from
     disk);
   - reopen them without the library: a `<defunct>` cell that keeps the
     stored geometry, and its stamp;
   - save again without the library and reopen with it;
   - refresh the library (`Library.refresh()`, which keeps what coerce
     returns) and check every reopened cell's parameters and geometry again;
   - place each default in host layouts with database units of 0.5 nm and
     5 nm;
10. DRC with both tools on both sides (the reference and the PCell), with
   each device's points on one sheet and each device's defaults also run
   alone, compared as sets of rule IDs, and the defaults compared with
   `baseline/<pdk>/drc-defaults.json`. KLayout
   runs the PDK's own deck: `sky130A_mr.drc` (feol, beol and offgrid on,
   floating_met and seal off), `gf180mcu.drc` (`decks=all,-density`,
   variant D) and the IHP PDKs' `run_drc.py` (`--no_density`, one process,
   one thread; with one thread per CPU, KLayout 0.30.11 crashed once with
   signal 11 on an `npn13g2v` sheet, which passed when run again; a DRC run
   that fails is tried once more). A point whose cell is longer than
   10 mm on a side gets no DRC and is listed in the report: Magic's dialog
   makes ihp-sg13g2's `rm6` and `rm7`, which have no `_check`, 0.9 m and
   1.8 m long at the sweep's largest `val`, and Magic's DRC crashed
   (signal 11) on a sheet that held the `rm7` one, on both sides. The density
   decks are left out: sky130A's divides by zero on a cell without a
   prBoundary, and the others weren't tried on lone devices. Magic runs
   `drc(full)` with the PDK's rcfile, on the cell and
   a 10 µm margin around it (without the margin Magic clips an error area
   that lies outside a lone device's bounding box: sky130A `via4` at its
   minimum loses `met5.1`);
11. Magic extraction of every MOSFET point but the edit points on both
    sides (edit points get no DRC either): the same devices on
    both sides, and the model, W, L and count (`nf × m`, or `ng × m`) matching
    Magic's checked values, except for the patterns recorded in
    `baseline/<pdk>/extract-known.json` (see [Known
    differences](#known-differences)).

12. the jobs step (`tests/jobs/run_jobs.py`; `--no-jobs` skips it): the
    checks of [Checking a layout with Magic](#checking-a-layout-with-magic)
    on the [case suite](#the-case-suite), built for the run, against
    references that use none of the plugin's code, and its outputs against
    each other:
    - DRC in every style and both modes against `tests/parity/mdrc.tcl`
      run on the plugin's own export, as multisets of boxes
      (`drc_plumbing`), and against Magic reading the original file with
      every cell checked as its own top, as merged error regions per cell
      and rule whose XOR must be empty at 1 nm (`drc_fidelity`). Also: the
      plugin checked every cell of the export but those Magic reads as
      empty (`drc_cells`), the report database's error boxes are the TSV's
      (`drc_markers`), every case has a result in every style and mode
      (`drc_coverage`), the `hier` cases' top-cell lists and extracted
      devices are the case suite's expected ones (`drc_hier`), and each
      `names` case gives its one error under its KLayout name
      (`drc_names`);
    - LVS on the inverters against netgen run by the step itself on the
      same netlist and schematic, with its own reading of netgen's report
      (`lvs`); every net netgen couldn't match is named by a marker
      (`lvs_badnets`), and each such marker holds the net's point from the
      `.ext` file (`lvs_markers`);
    - the generated-layer and port checks against
      `tests/jobs/expected-<pdk>.json` (`layers`, `ports`), which
      `--update-baseline` rewrites. Four results are asserted in the code,
      so that a rewritten baseline can't hide a wrong one of them: no F1
      to F4 finding on the negative controls (`controls`), an F1 item on
      each F1 positive case (`f1_positives`), the "Magic reads nothing" finding on the cells
      that should give it (`reads_nothing`), and P3 on sky130A's
      `inv_text_on_pin` (`ports_expect`);
    - every device default extracted from Magic's database and again after
      a GDS write and read, against `readback-<pdk>.json` (`readback`);
    - `tools/build_gaps.py --check` (`gaps`; see [Where KLayout and Magic
      disagree](#where-klayout-and-magic-disagree)).

    The step also records, without checking it, what a Magic user gets
    (`tests/jobs/magic_native.tcl`: the top cell checked from the top only,
    in `drc(fast)` and then `drc(full)`), with the rules per case where that
    differs from hierarchical mode, and the time of every job.
    [tests/jobs/README.md](tests/jobs/README.md) lists every check and why
    it is there. With `--quick` the step runs the inverters set, the PCell
    inverter included, and per PDK a negative control, a case with an F3
    finding and, on sky130A and ihp-sg13g2, a cell Magic reads nothing in;
    it skips the read-back and gap-table checks. The step runs alone too:
    `scripts/in_image.sh 'python3 tests/jobs/run_jobs.py --pdk sky130A
    --out out/jobs/sky130A [--quick]'`, with `KMP_IMAGE_PDK` set to the
    PDK (`scripts/in_image.sh` sets the image's `PDK` variable from it).
    In the last full run the full step took 454.6 s on sky130A,
    306.2 s on gf180mcuD, 249.8 s on ihp-sg13g2 and 172.1 s on
    ihp-sg13cmos5l, on 2 workers each, with the four PDKs running at the
    same time (see [Last full run](#last-full-run)).

Every generator of every PDK is in the sweep; the excluded helpers are listed
in each report with the reason.

A run of `scripts/test.sh` on 0.6.2's code, on 2026-11-24 in the
image, ran the 401 unit tests, all of which passed but the two of
`test_netgen.py` that need `KMP_NETGEN_EVIDENCE`, which were skipped; the
gap table builder's 18 tests passed.
The 95 backend tests passed on each PDK, with the tests written for
another PDK skipped: 3 on sky130A, 11 on gf180mcuD, 8 on ihp-sg13g2 and 10
on ihp-sg13cmos5l. The harness's first step runs the unit
and backend tests but not the gap table builder's;
`scripts/in_image.sh 'python3 -m unittest tests.gaps.test_build_gaps'`
runs those alone.

### The case suite

`tests/cases/build.py --pdk P --out DIR [--set S]...` draws the layouts that
the checks of [Checking a layout with Magic](#checking-a-layout-with-magic)
are tested on, with `klayout.db` at run time (the
repository holds no layout files), and writes them with a `cases.json`
that says what each one targets and what Magic and KLayout reported on it
when it was measured. [tests/cases/README.md](tests/cases/README.md)
describes the sets and the file. Per PDK:

| Set | What it holds | sky130A | gf180mcuD | ihp-sg13g2 | ihp-sg13cmos5l |
|---|---|---|---|---|---|
| `gaps` | a clean control and one-change cases, each with the rule it breaks; two sky130A cases, `d_tap_area` and `e_ntap_area`, break no rule of SkyWater's and target none, and Magic's `psd.10b` and `nsd.10b` report them | 132 | 69 | 151 | 49 |
| `hier` | the flat original and copies with some layers moved into a parent cell (see [Magic DRC](#magic-drc)) | 4 | 8 | 4 | 4 |
| `whole_shape` | a 100 µm well for a rule about a whole shape: with its tap at one end (sky130A, IHP), or with a 3.3 V and a 6 V pfet at its two ends (gf180mcuD) | 1 | 1 | 1 | 1 |
| `names` | twelve cells with awkward names (`a b`, `x/y`, `br[0]`, `café`, ...) under one top cell, each holding one error, and as a 13th case a name the file doesn't have | 13 | 13 | 13 | 13 |
| `inverters` | the hand-drawn inverter, broken variants and the inverter built from the PCells, each with a schematic | 8 | 5 | 5 | 5 |
| `controls` | seven of the PDK's standard cells, a row of them, the same row written by Magic, and the hand inverter | 10 | 10 | 10 | 10 |
| `sheet` | the `gaps` cases as subcells 40 µm apart | 1 | 1 | 1 | 1 |

The PCell inverter needs Magic (`--no-pcell` leaves it out), the controls
need the PDK's `libs.ref`, and `--magic-row` has Magic write the row. The
builds for this README printed, for example,
`CASES sky130A controls=10 gaps=132 hier=4 inverters=8 names=13 sheet=1 whole_shape=1`.

### Last full run

The last full run was on 2026-11-24, on version 0.6.0's code before the
changes listed below, with Magic 8.3.681 and KLayout 0.30.11 in the image
listed under [Requirements](#requirements). Each PDK ran in its own
container as
`scripts/parity.sh --pdk <pdk> --jobs 2`, and the four containers ran at
the same time on a machine with 6 CPUs, started within one minute of each
other; `run_sweep.py --summary` then wrote the summary. It printed
`PARITY PASS over 4 PDKs`: 10,399 of 10,399 points passed, the jobs step
passed on every PDK, and every PDK's run exited 0. The whole run took 66
minutes of wall time. The time given for each PDK below is that PDK's own
run, measured while the other three ran beside it, so it can't be
compared with version 0.5.0's full run, which ran the four PDKs one after
another and took 79 minutes. Each PDK's run included the unit and backend
tests, the manifest check and the jobs step, and checked DRC and the GDS
census against the committed baselines.

After that run, the code changed in these ways. Before the 0.6.0
release:

- `extract` and `lvs` on a cell Magic reads nothing in give the finding
  "Magic reads nothing in this cell" with status 1, and `drc`'s summary
  says that nothing was checked in such cells;
- every sentence of a `drc` summary ends with a period, and the summary of
  a refused `extract` names no path;
- in the [job directories](#job-directories), an LVS run's `lvs-*` folder
  is removed when the check ends, a key's directory that holds a done job
  but lacks a file the check reads is replaced once the process that ran
  the job has ended, `cache prune` removes leftover `lvs-*` folders, and
  the DRC report's description and the GUI's LVS message say which
  directories are removed;
- `drc --box` takes a box whose first number is negative;
- a KLayout error while the export is written fails the check;
- the jobs step's check `drc_b1` was renamed `drc_hier`, and code comments
  cite [docs/design-0.6.md](docs/design-0.6.md) in place of notes outside
  the repository.

Their tests changed with them, and so did the documentation, including
the text that `tools/build_gaps.py` writes into the gap pages. None of
these changes is on the path that the sweep's points measure. Of the
modules that the PCell libraries load, only `cache.py` changed in its
code, and only in the job cache's prune; `config.py` changed in its
docstring alone. In the command line (`__main__.py`), only the handling
of `--box` changed. On the released 0.6.0 code, `scripts/test.sh`,
`scripts/parity.sh --pdk all --quick` and the full jobs step on each PDK
passed, the jobs step with the full run's numbers of checks.

Version 0.6.1 came out of a check of the gap tables against the
foundries' published rules: the rows on which the two tools disagreed,
and their cases (see
[tests/cases/README.md](tests/cases/README.md#sources)). It made these
changes:

- the alias files of all four gap tables join rules that the two tools
  name differently, and the tables went from 398 rules to 390 on
  sky130A, 568 to 545 on gf180mcuD, 383 to 362 on ihp-sg13g2 and 297 to
  282 on ihp-sg13cmos5l. Among the joins:
  - sky130A: `hvi.2a` (Magic's HVI-to-HVI `hvi.5` and `sky130A.lydrc`'s
    `hvi.2`), `via.5a` (`sky130A.lydrc`'s `via1.5a`) and `varac.1`, `.2`
    and `.4` (Magic's `var.1`, `.2` and `.4`);
  - gf180mcuD: Magic's via rules (`V2.3` to `V4.4i`, `VT.*`), its
    `HRES.2` and `HRES.3`, which are the deck's `HRES.3` and `HRES.2`,
    and its SRAM rules, under the deck's names. `MIMTM.5` stays
    "both, values differ" (Magic 0.39 µm, KLayout 0.4 µm), with a note
    that Magic measures to its via4 area, and that if that area is the
    cut plus 0.01 µm per side, Magic's 0.39 µm is 0.4 µm from the cut;
    that area wasn't measured;
  - both IHP PDKs: Magic's `x.2` with the main deck's output
    `gatpoly_drw_Angle45` (row `grid.Angle45`), and the seal-ring rules
    with the maximal deck's outputs per layer. Magic's second `AFil.i`, a rule that allows only
    90° angles on Activ fill, has a row of its own, `AFil.i.angle`;
  - ihp-sg13g2: Magic's `Padc.e`, a 40 µm pad spacing, is filed as
    `Padc.b`, IHP's name for that rule;
- the gaps cases that didn't break the rule they target were redrawn:
  sky130A `s_m1_adj_mcon`, `s_via_m1_adj`, `s_m1_wide_space` and
  `e_butt_short`, and gf180mcuD `NW2a_s050`, `NP3_s006`, `V1_3_m1ov0`
  and `V1_3_m1ov002`. sky130A `s_m1_huge_space` and its control were
  added for `met1.3b`, which brings sky130A's gaps set to 132 cases.
  sky130A `s_li_45deg` now targets `x.2` and `c_pc_to_pdiff` `licon.9`,
  ihp-sg13cmos5l `u_angle.poly` targets `grid.Angle45`, and sky130A
  `d_tap_area` and `e_ntap_area` target no rule. The `expect` entries
  of the redrawn and added cases were measured on the new shapes, and
  the jobs step's baselines changed with them: `e_butt_short` lost its
  F1 item and `NP3_s006` its F3 item (see [Generated
  layers](#generated-layers)), and `s_m1_huge_space` and its control
  were added;
- `tools/build_gaps.py` no longer counts a case as a test of a rule that
  is only a later operand of its target's composite rule: Magic checks
  `via.5a` as `via.5a - via.4a`, and a case filed under `via.5a` is not a
  test of `via.4a`. Four sky130A cases left the `via.4a` row:
  `s_via_014` and `s_via_016` (which target `via.1a`, checked by Magic
  as `via.1a + 2 * via.4a`), `s_via_space` (`via.2 - 2 * via.4a`) and
  `s_via_m1_adj` (`via.5a - via.4a`);
- `data/gaps-<pdk>.json` is in schema 2, with an entry per row and the
  tech-file lines of its statements (schema 1 had an entry per ID that
  Magic prints), and the DRC check finds a message's rows by those
  lines, with a `Gap table:` line per row (see [Magic DRC](#magic-drc));
- `tests/parity/sheet.py` moves each cell of a DRC sheet by a multiple of
  5 nm. In 0.6.0, a case whose bounding box is off the grid on purpose
  (sky130A `s_m1_offgrid`, ihp-sg13g2's `Offgrid` test, ihp-sg13cmos5l
  `u_offgrid`) moved every later cell of its row 1 nm off the grid, and
  KLayout's grid checks reported every layer of those cells;
- `grain.xml` and `__version__` say 0.6.1.

Of these, only the change to `tests/parity/sheet.py` is on the path that
the sweep's points measure: the sweep's DRC step (item 10 under
[Tests](#tests)) builds its sheets with it. It places a cell elsewhere
than 0.6.0's code only when that cell's bounding box, or the box of a
cell placed before it on the sheet, is off the 5 nm grid. Every
bounding box that the full run's reports record (from the shapes, texts
left out) is on that grid: 20,040 boxes, the reference's and the PCell's
of every point whose cell isn't empty. The quick run below put each of
its 226 points on three sheets of one cell each (the reference, the
PCell, and the PCell again as a default run alone; see item 10), 678
sheets in all; the boxes that they record for the
669 cells that aren't empty are on the grid too, and every cell is where
0.6.0's code places it. The other changes touch no module that the PCell
libraries load but `__init__.py`, whose version string neither the
PCells' cache key nor their stamps hold. The changes to the DRC check
and the gap tables are on the jobs step's path, which ran again in full.

On 0.6.1's code these ran on 2026-11-24, one container at a time, and
passed:

- `scripts/test.sh`: 380 unit tests (2 skipped), which are the 372 that
  each PDK's results below give, six added before the 0.6.0 release and
  two in 0.6.1; the gap table builder's 18 tests; and the 95 backend
  tests on each PDK;
- `scripts/gaps.sh --check`: `GAPS OK` on all four PDKs, with the counts
  under [Where KLayout and Magic disagree](#where-klayout-and-magic-disagree);
- the full jobs step on each PDK (`tests/jobs/run_jobs.py --pdk <pdk>`,
  on 6 workers): 1,834 checks passed on sky130A, the full run's 1,816
  and 18 on the two added cases, and 1,279 on gf180mcuD, 1,944 on
  ihp-sg13g2 and 1,006 on ihp-sg13cmos5l, as in the full run; none
  failed;
- `scripts/parity.sh --pdk all --quick`: 73 points on sky130A, 59 on
  gf180mcuD, 53 on ihp-sg13g2 and 41 on ihp-sg13cmos5l, and the jobs
  step's quick set on each, with the summary `PARITY PASS over 4 PDKs`,
  in 26 minutes.

Version 0.6.2 fixes what a trial of the Magic menu for a sky130A layout
course found, on the course's layouts, in KLayout under XFCE on a
1280 × 800 screen. It made these changes:

- the report database stores an item's text as one value per sentence or
  clause, a longer one in lines of at most 80 characters, because
  KLayout's Info pane shows a value in a block that doesn't wrap and cuts
  it after 200 characters: the end of the generated-layer check's F2
  item, "To fix it, draw nsdm (93/44) over the n-diffusion, 0.125 um past
  it.", never showed. The DRC report's description is one line, since
  the browser's database list showed its line breaks as `\n`, and the
  command line in it names `--pdk`;
- items that are information, not findings (the export's findings that
  don't change a check's exit status, "Magic said", the information boxes
  of hierarchical DRC, F5 and the device list of the generated-layer
  check, LVS's result items on a match), are marked waived and visited,
  so KLayout's browser draws their categories in green and counts them
  after a dash: "3 (2) - 1" for a cell with two `li.5` boxes and an npc
  note, where 0.6.1 gave "3 (3)". Extraction and LVS no longer list
  under "Magic said" the warning that Magic gives on every GDS read;
- the GUI's result message starts with a line in plain words, such as
  "36 DRC error markers in inv_base_all_h, 7 rules: diff/tap.8 13,
  nwell.4 6, ...", with the command line's summary below it, and the LVS
  message no longer names netgen's report in the job cache. Closing the message brings the Marker Database
  Browser in front of the main window, which covered it under XFCE when
  KLayout was maximised. The text windows and Settings fit the screen and
  can be maximised; Rule differences asked for 1100 × 760, and its Close
  button was below a 1280 × 800 screen. netgen's report opens at its end.
  The Extract dialog's title is "Extract with Magic (<pdk>)", with the
  cell in a row of its own, since the window manager cut the old title.
  The LVS dialog asks before it takes a netlist that Extract wrote, which
  its file dialog lists beside the schematics;
- hierarchical DRC reports the top cell's own check in the top cell and
  leaves out a subcell's box that the top cell's check also lists. On
  the trial's placement of sky130A standard cells without a tap cell,
  0.6.1 filed 55 of the 56 latch-up and tap boxes under three standard
  cells, having dropped 61 of the top cell's 62 boxes as copies of
  theirs; 0.6.2 reports the 62 boxes, all in the top cell, as flat mode
  does.
  The tables under [Magic DRC](#magic-drc) give the new counts;
- the generated-layer check: on sky130A, a licon that Magic drops because
  the diffusion under it has neither nsdm nor psdm gets an F3 item that
  says so, where it said that li was missing over the cut; sky130A's F1
  items name `licon.15` (npc), `n/psdm.5b` (an implant around a tap;
  SkyWater's `n/ psd.5b`, spelled as the PDK's `sky130A.lydrc` deck
  spells it),
  `lvtn.4b`, and `hvtp.3` in place of `hvtp.4`, after SkyWater's
  periphery rules (google/skywater-pdk 7198cf6), where `hvtp.3` is the
  enclosure of the pfet by hvtp and `hvtp.4` the spacing between them;
- the port check: `tools/build_pdk_data.py` lists the label layers that
  Magic reads onto its comment plane under the ports table's `comment`
  (sky130A's 83/44, the IHP PDKs' 63/0, 152/0 and 160/0), and a text there
  gives no finding; a pin box counts as named by a text on the label layer
  that the form both accept pairs with it. The foundry's standard cells
  lost their P2 for the cell-name text and their P4 for the `pwell.pin`
  box. The data files changed only in that list and in the rule names,
  and `devices-sky130A.json` gained the licon's implant rule.
  The jobs step's baselines changed with the port check: sky130A's seven
  standard cells and both rows of them, and ihp-sg13g2's `H_ptap_sublbl`,
  lost those items;
- LVS reports every schematic pin that has no layout pin, also the one on
  the first row of netgen's pin table, which netgen's JSON leaves out;
- `grain.xml` and `__version__` say 0.6.2.

None of these changes is on the path that the sweep's points measure.
They change the checks' modules (`markers.py`, `drcjob.py`,
`layercheck.py`, `portcheck.py`, `lvsjob.py`, `netgen.py`, `gui.py`), the
checks' data files and the builder of `pdk-<pdk>.json`. The PCell
libraries load none of these; the autorun macro imports `gui.py` for the
menu, and its import and `register_recipe()` are unchanged. The version
string in `__init__.py` is in neither the PCells' cache key nor their
stamps. The changes are on the jobs step's path, which ran again in full.

On 0.6.2's code these ran on 2026-11-24, one container at a time, and
passed:

- `scripts/test.sh`: 401 unit tests (2 skipped), the 380 of 0.6.1 and 21
  added in 0.6.2; the gap table builder's 18 tests; and the 95 backend
  tests on each PDK, with 3, 11, 8 and 10 skipped as written for another
  PDK;
- `scripts/gaps.sh --check`: `GAPS OK` on all four PDKs;
- the full jobs step on each PDK, on 6 workers: 1,834 checks passed on
  sky130A in 149.5 s, 1,279 on gf180mcuD in 88.7 s, 1,944 on ihp-sg13g2
  in 136.4 s and 1,006 on ihp-sg13cmos5l in 48.1 s, the same numbers of
  checks as on 0.6.1; none failed;
- `scripts/parity.sh --pdk all --quick`: 73 points on sky130A, 59 on
  gf180mcuD, 53 on ihp-sg13g2 and 41 on ihp-sg13cmos5l, and the jobs
  step's quick set on each, with the summary `PARITY PASS over 4 PDKs`,
  in 29 minutes.

Version 0.5.0's full run, on 2026-11-23, passed the same 10,399 points.
It had neither the jobs step nor the checks it tests. The sweep's counts
below (path A, the edit points, the round trips and the notes) are the
same as in that run.

Path D, the real dialog under Xvfb, ran for 1,215.1 s on sky130A, 648.7 s
on gf180mcuD, 603.0 s on ihp-sg13g2 and 445.5 s on ihp-sg13cmos5l,
alongside paths A and B, and didn't have to start Magic again after an X
error. Path D agreed with the PCells on every device point. Path A
(`magic::gencell` with the typed values) applies to 4,991 of the 6,537
device points that aren't edit points, the ones where it gets the same
checked values as the dialog's Create, and on all of them the PCells
matched it. On the other 1,546, the dialog's corrections, its order of
edits or its extra widgets give `_draw` other values; 1,492 of them still
draw the same shapes as `magic::gencell`, and the 54 that don't are listed
below per PDK. A file that version 0.4 saved with the values of one of
those 54 points comes back with other shapes; with the values of one of
the 1,492, it comes back with the same shapes and other checked values.
All 2,873 edit points passed, the ones where Magic's Apply kept the
instance among them. The round trips covered 1,764 sky130A, 1,305
gf180mcuD, 1,123 ihp-sg13g2 and 904 ihp-sg13cmos5l points, all
regenerated by Magic (no variant came from disk), none with Magic's
dialog run again on reopen, and every one unchanged by the library
refresh. The request each reopened variant was drawn from, read back
through its stamp, was the one path B sent, except on 15 points of
gf180mcuD's three stub devices (45 file reads: the GDS, the OASIS and the
file saved again without the library). Magic draws those devices empty,
so their cells have no stamp, and the report gives the reason as "the
generator handed produce nothing while the file was read, so no request
was read back". Every point's fonts were the same in both files.

The jobs step's line under each PDK gives the checks that passed, the
step's time on its 2 workers and the jobs' own times summed (the log's
"s of jobs"; the figure in `report.md` also counts the case suite's build,
about 1 s more). Its GDS
read-back check extracts every device default from Magic's database and
again after a GDS write and read, and passes when the two differ only on
the devices that `readback-<pdk>.json` lists; its gap-table check is
`tools/build_gaps.py --check`, and the rules and cases it names are those
of the full run's tables (the current counts are under [Where KLayout and
Magic disagree](#where-klayout-and-magic-disagree)).

The notes under each table are points that pass but are listed in the
report. "Typed with no Return" counts the points with one typed value on
devices whose dialog has no widget beyond their parameters, where path A is
also Magic's dialog with the value typed and Create pressed without
Return.

**sky130A** (`sky130_magic`): `PARITY PASS 3718/3718` in 3,607 s; 372 unit tests (2 skipped) and 95 backend tests (3 skipped as not for this PDK) passing; manifest check passing; KLayout DRC: sky130A_mr.drc with beol=true, feol=true, floating_met=false, offgrid=true, seal=false, thr=1. 2,771 points that aren't edit points and 947 edit points.

Jobs step: PASS, 1,816 checks passed and none failed, in 454.6 s on 2 workers, 902.9 s summed. GDS read-back: 60 device defaults measured, and the 7 that differ (the four `sky130_fd_pr__cap_vpp_*` devices, `sky130_fd_pr__diode_pd2nw_05v5_hvt` and `_lvt`, and `sky130_fd_pr__npn_11v0_W1p00L1p00`) are the ones the file lists. Gap table: `GAPS OK sky130A`, 398 rules and 130 cases.

| Family | Points | Pass | Fail |
|---|---|---|---|
| MOSFET | 925 | 925 | 0 |
| Varactor | 233 | 233 | 0 |
| Resistor | 1261 | 1261 | 0 |
| MIM capacitor | 93 | 93 | 0 |
| Diode | 504 | 504 | 0 |
| Photodiode | 31 | 31 | 0 |
| Fixed layout | 372 | 372 | 0 |
| Box paint | 299 | 299 | 0 |

- 97 points where Magic writes an empty cell, which the PCell reproduces (box paint at a box 5 nm below the minimum: 26, box paint with a zero width typed as -0.0: 13, diode at a zero size: 10, resistor at a zero size: 16, edit points to a zero size: 32)
- 4 default points whose 5 nm host placement is n/a: Magic's GDS has coordinates off the 0.005 um grid on 83/44
- 10 MOSFET points that match a known extraction pattern (`sky130_fd_pr__nfet_g5v0d16v0` 5, `sky130_fd_pr__pfet_g5v0d16v0` 5)
- 39 box-paint points through Magic's menu entry under Xvfb: identical 39
- the widget bindings of all 60 devices' dialogs, recorded 128 times over path D's restarts, run the same passes as the server's `dialog` op
- 947 edit points, all passing; Magic's Apply kept the instance on 74
- `magic::gencell` with the typed values, on the 2472 device points that aren't edit points: it applies on 2035, all identical; of the other 437, 422 draw the same shapes and 15 differ
  - they differ on: `sky130_fd_pr__cap_mim_m3_1` random 2, `sky130_fd_pr__cap_mim_m3_2` random 2, `sky130_fd_pr__res_generic_m5` zero 1, `sky130_fd_pr__res_generic_po` zero 1, `sky130_fd_pr__res_high_po_5p73` random 1, `sky130_fd_pr__res_xhigh_po_0p35` zero 1, `sky130_fd_pr__res_xhigh_po_0p69` zero 1, `sky130_fd_pr__res_xhigh_po_1p41` zero 1, `sky130_fd_pr__res_xhigh_po_2p85` zero 1, `sky130_fd_pr__res_xhigh_po_5p73` random 3, `sky130_fd_pr__res_xhigh_po_5p73` zero 1
- typed with no Return: 1857 points; other checked values than with Return on 286, other shapes on 7
- 115 points where Create's own `_check` changes the dialog's form (40 of them not edit points)

**gf180mcuD** (`gf180mcu_magic`): `PARITY PASS 2590/2590` in 2,199 s; 372 unit tests (2 skipped) and 95 backend tests (11 skipped as not for this PDK) passing; manifest check passing; KLayout DRC: gf180mcu.drc with decks=all,-density, run_mode=deep, threads=1, variant=D. 1,753 points that aren't edit points and 837 edit points.

Jobs step: PASS, 1,279 checks passed and none failed, in 306.2 s on 2 workers, 608.1 s summed. GDS read-back: 50 device defaults measured, and the 10 that differ (`nfet_10v0_asym`, `pfet_10v0_asym`, `nwell`, `pvaractor_3p3`, `pvaractor_6p0`, and `rm1` to `rm5`) are the ones the file lists. Gap table: `GAPS OK gf180mcuD`, 568 rules and 69 cases.

| Family | Points | Pass | Fail |
|---|---|---|---|
| MOSFET | 689 | 689 | 0 |
| MOS capacitor | 220 | 220 | 0 |
| Varactor | 220 | 220 | 0 |
| Resistor | 745 | 745 | 0 |
| MIM capacitor | 41 | 41 | 0 |
| Diode | 196 | 196 | 0 |
| Fixed layout | 341 | 341 | 0 |
| Box paint | 138 | 138 | 0 |

- 146 points where Magic writes an empty cell, which the PCell reproduces (box paint at a box 5 nm below the minimum: 12, box paint with a zero width typed as -0.0: 6, diode at a zero size: 8, every point of `eFuse`: 16, every point of `npn_00p54x08p00`: 16, every point of `npn_00p54x10p00`: 16, resistor at a zero size: 9, edit points: 63, 18 of them to a zero size and 45 on those three devices)
- 74 MOSFET points that match a known extraction pattern (`nfet_10v0_asym` 37, `pfet_10v0_asym` 37)
- 15 box-paint points through Magic's menu entry under Xvfb: identical 15
- the widget bindings of all 53 devices' dialogs, recorded 102 times over path D's restarts, run the same passes as the server's `dialog` op
- 837 edit points, all passing; Magic's Apply kept the instance on 80; on the 45 of the three stub devices the dialog doesn't reopen on the instance, so the edit deleted it and pressed Create again
- `magic::gencell` with the typed values, on the 1615 device points that aren't edit points: it applies on 1326, all identical; of the other 289, 281 draw the same shapes and 8 differ
  - they differ on: `cap_mim_2p0fF` random 3, `npolyf_s` zero 1, `nwell` zero 1, `ppolyf_s` zero 1, `ppolyf_u_1k` zero 1, `ppolyf_u_1k_6p0` zero 1
- typed with no Return: 1064 points; other checked values than with Return on 210, other shapes on 5
- 89 points where Create's own `_check` changes the dialog's form (23 of them not edit points)

**ihp-sg13g2** (`sg13g2_magic`): `PARITY PASS 2249/2249` in 3,930 s; 372 unit tests (2 skipped) and 95 backend tests (8 skipped as not for this PDK) passing; manifest check passing; KLayout DRC: run_drc.py --no_density --mp=1 --density_thr=1. 1,643 points that aren't edit points and 606 edit points.

Jobs step: PASS, 1,944 checks passed and none failed, in 249.8 s on 2 workers, 496.4 s summed. GDS read-back: 39 device defaults measured, none differ. Gap table: `GAPS OK ihp-sg13g2`, 383 rules and 151 cases.

| Family | Points | Pass | Fail |
|---|---|---|---|
| MOSFET | 620 | 620 | 0 |
| Varactor | 37 | 37 | 0 |
| Resistor | 503 | 503 | 0 |
| MIM capacitor | 102 | 102 | 0 |
| Diode | 124 | 124 | 0 |
| Bipolar transistor | 166 | 166 | 0 |
| Inductor | 55 | 55 | 0 |
| Bond pad | 37 | 37 | 0 |
| Via stack | 35 | 35 | 0 |
| Fixed layout | 248 | 248 | 0 |
| Box paint | 322 | 322 | 0 |

- 78 points where Magic writes an empty cell, which the PCell reproduces (box paint at a box 5 nm below the minimum: 28, box paint with a zero width typed as -0.0: 14, diode at a zero size: 4, resistor at a value below its minimum: 4, resistor at a zero size: 12, edit points to a zero size: 16)
- 1 default point whose 5 nm host placement is n/a: Magic's GDS has coordinates off the 0.005 um grid on 10/25
- 236 MOSFET points that match a known extraction pattern (`sg13_hv_rfnmos` 59, `sg13_hv_rfpmos` 59, `sg13_lv_rfnmos` 59, `sg13_lv_rfpmos` 59)
- 24 box-paint points through Magic's menu entry under Xvfb: identical 24
- the widget bindings of all 39 devices' dialogs, recorded 76 times over path D's restarts, run the same passes as the server's `dialog` op
- 606 edit points, all passing; Magic's Apply kept the instance on 38
- `magic::gencell` with the typed values, on the 1321 device points that aren't edit points: it applies on 899, all identical; of the other 422, 402 draw the same shapes and 20 differ
  - they differ on: `cap_cmim` random 2, `cap_rfcmim` random 3, `rhigh` zero 1, `rm6` max 1, `rm6` min 1, `rm7` max 1, `rm7` min 1, `rppd` zero 1, `rsil` zero 1, `sg13_hv_rfnmos` below 1, `sg13_hv_rfnmos` min 1, `sg13_hv_rfpmos` below 1, `sg13_hv_rfpmos` min 1, `sg13_lv_rfnmos` below 1, `sg13_lv_rfnmos` min 1, `sg13_lv_rfpmos` below 1, `sg13_lv_rfpmos` min 1
- typed with no Return: 743 points; other checked values than with Return on 126, other shapes on 7
- 2 points with no DRC because their cell is longer than 10 mm on a side (`rm6` and `rm7` at the maximum `val`)
- 45 points where Create's own `_check` changes the dialog's form (17 of them not edit points)

**ihp-sg13cmos5l** (`sg13cmos5l_magic`): `PARITY PASS 1842/1842` in 2,630 s; 372 unit tests (2 skipped) and 95 backend tests (10 skipped as not for this PDK) passing; manifest check passing; KLayout DRC: run_drc.py --no_density --mp=1 --density_thr=1. 1,359 points that aren't edit points and 483 edit points.

Jobs step: PASS, 1,006 checks passed and none failed, in 172.1 s on 2 workers, 340.5 s summed. GDS read-back: 31 device defaults measured, and the 2 that differ (`nmoscl_2`, `nmoscl_4`) are the ones the file lists. Gap table: `GAPS OK ihp-sg13cmos5l`, 297 rules and 49 cases.

| Family | Points | Pass | Fail |
|---|---|---|---|
| MOSFET | 620 | 620 | 0 |
| Varactor | 37 | 37 | 0 |
| Resistor | 417 | 417 | 0 |
| Capacitor | 42 | 42 | 0 |
| Diode | 124 | 124 | 0 |
| Bipolar transistor | 59 | 59 | 0 |
| Inductor | 55 | 55 | 0 |
| Bond pad | 36 | 36 | 0 |
| Via stack | 36 | 36 | 0 |
| Fixed layout | 186 | 186 | 0 |
| Box paint | 230 | 230 | 0 |

- 58 points where Magic writes an empty cell, which the PCell reproduces (box paint at a box 5 nm below the minimum: 20, box paint with a zero width typed as -0.0: 10, diode at a zero size: 4, resistor at a zero size: 10, edit points to a zero size: 14)
- 236 MOSFET points that match a known extraction pattern (`sg13_hv_rfnmos` 59, `sg13_hv_rfpmos` 59, `sg13_lv_rfnmos` 59, `sg13_lv_rfpmos` 59)
- 18 box-paint points through Magic's menu entry under Xvfb: identical 18
- the widget bindings of all 31 devices' dialogs, recorded 63 times over path D's restarts, run the same passes as the server's `dialog` op
- 483 edit points, all passing; Magic's Apply kept the instance on 31
- `magic::gencell` with the typed values, on the 1129 device points that aren't edit points: it applies on 731, all identical; of the other 398, 387 draw the same shapes and 11 differ
  - they differ on: `rhigh` zero 1, `rppd` zero 1, `rsil` zero 1, `sg13_hv_rfnmos` below 1, `sg13_hv_rfnmos` min 1, `sg13_hv_rfpmos` below 1, `sg13_hv_rfpmos` min 1, `sg13_lv_rfnmos` below 1, `sg13_lv_rfnmos` min 1, `sg13_lv_rfpmos` below 1, `sg13_lv_rfpmos` min 1
- typed with no Return: 629 points; other checked values than with Return on 116, other shapes on 3
- 39 points where Create's own `_check` changes the dialog's form (15 of them not edit points)

### Mutations the harness catches

The jobs step (item 12 under [Tests](#tests), step 9 in `run_sweep.py`'s
log) was run on copies of the package with one change each, with
`tests/jobs/run_jobs.py --pdk <pdk>` on the quick set
(`--quick`) or on the full one. Thirteen of the fourteen changes ran on the
step as it was before seven of its checks were added (`drc_cells`,
`drc_markers`, `drc_coverage`, `lvs_markers`, `reads_nothing`,
`f1_positives` and `ports_expect`), and nine ran on the step with them.
Before those checks, the unchanged package passed the quick set on sky130A
and on gf180mcuD, and the full set on sky130A; after, `scripts/parity.sh
--pdk all --quick` and the full step on all four PDKs passed.

| Change to the package | PDK and set | Before the seven checks | After |
|---|---|---|---|
| every DRC box Magic lists read 5 nm (one grid step) to the right | sky130A quick | FAIL: drc_plumbing 7, drc_fidelity 5 (`inv_pcell`, `inv_w036`) | not rerun |
| only the report database's DRC markers moved right by 5 nm | sky130A quick | missed (PASS) | FAIL: drc_markers |
| hierarchical mode checks the top cell alone | sky130A quick; gf180mcuD quick | FAIL: drc_plumbing 3, drc_fidelity 3, all on `inv_pcell` | FAIL: drc_cells, drc_plumbing, drc_fidelity |
| the export flattens in hierarchical mode too | sky130A quick; full | quick FAIL: drc_fidelity 3, ports 1. Full FAIL: drc_fidelity 180, drc_b1 6 (the check since renamed `drc_hier`), layers 3, ports 3; drc_plumbing passed with 162 results where the baseline has 552 | full FAIL: drc_coverage 130, drc_fidelity 180, drc_b1 |
| `kmp_job_load` only loads the cell, with none of its checks | sky130A quick; full | quick missed. Full FAIL on 8 layers cases, by the reason text alone: both runs gave status 2 | quick FAIL: reads_nothing 7, layers |
| netgen's report read from its final result line alone | sky130A quick | FAIL: lvs 1, `inv_w036` read as a match despite its property error; through `scripts/parity.sh`, `PARITY FAIL 0/1 (jobs step: 1 failed)` | not rerun |
| `extfile.py` takes its unit from the `.ext` file's `scale` line | gf180mcuD quick | missed: both net markers of `inv_open_drain` at the origin, as 0.02 µm boxes | FAIL: lvs_markers |
| the generated-layer check without its Magic-minus-user direction (no F4) | sky130A quick | FAIL: layers 1 (`inv_pin_only_li`) | not rerun |
| the generated-layer check without its user-minus-Magic direction (no F3) | sky130A quick; full | quick missed. Full FAIL: layers 7 | quick FAIL: layers (`c_licon_gate`) |
| F1 as Magic's layer minus the user's, not an enclosure check | sky130A quick; full | quick missed. Full FAIL: controls 4, layers 18 | quick FAIL: controls, layers (`sky130_fd_sc_hd__mux2_1`) |
| the port check takes sky130A's `*/16` pin boxes as `*/5` layers | sky130A quick | FAIL: ports 2 | not rerun |
| the port check reads texts on `*/16` as texts on `*/5` | sky130A | not run: no case had such a text | quick FAIL: ports_expect, ports (on `inv_text_on_pin`, a case added for it) |
| F1 as a subtraction, run with `--update-baseline` | sky130A full | FAIL, exit 1: controls 4; the baseline wrote those four controls as "not written" | not rerun |
| no F1 at all, run with `--update-baseline` | sky130A full | PASS, exit 0: the rewritten baseline had lost the F1 entries of all 9 cases that had them | FAIL, exit 1: f1_positives 3 |

The plumbing check compares the plugin with `mdrc.tcl` on the plugin's own
export, so it can't see an export that flattens: `mdrc.tcl` reads the same
flat file. The fidelity check, on the user's file, and the coverage check
catch it. Backend tests catch three of the changes too: `test_jobs_backend`
fails on `kmp_job_load` without its checks, `test_lvs_backend` on the unit
from the `scale` line, and `test_drc_backend`, which compares the report
database's boxes with the TSV, on the moved markers.

The mutations of the PCell sweep follow. Each line is a copy of the
package with one change, run with `run_sweep.py --pdk <pdk> --no-unit
--no-drc --no-extract --devices ...` on 2026-11-22, on version 0.4. The control is the same run on the unchanged
package. Version 0.5's mutations of the dialog code follow the table.

| Change to the package | PDK and devices | Result |
|---|---|---|
| none (control) | sky130A: `nfet_01v8`, `res_generic_po`, `cap_mim_m3_1`, `via1` | PASS 164/164 |
| `format_float` writes `%.1g` | same | FAIL 53/164: request 53, checked 42, magic_cell 30, bbox 27, geometry 27, texts 19, roundtrip 10, stamp 2 |
| `format_float` writes `%.8g` | same | FAIL 16/164: request 16, checked 12 |
| `format_float` rounds the double instead of the 15-digit text (version 0.3) | same | FAIL 6/164: roundtrip 6, request 5, checked 3 |
| `format_float` drops the `.0` (`31` instead of `31.0`) | same | FAIL 24/164: request 24, checked 9 (no geometry changes) |
| the importer turns every label 90°, sets its size to 0 and right-justifies it | same | FAIL 138/164: texts 138, roundtrip 51 |
| the importer inserts every shape twice | same | FAIL 160/164: geometry 160, texts 138, roundtrip 51 (the merged XOR is unchanged; the shape and text counts differ) |
| the server refuses negative box sizes (version 0.3) | same | FAIL 3/164: each of request, geometry, texts, bbox, checked, magic_cell, cache, placeholder, stamp and roundtrip on the 3 negative `via1` boxes |
| none (control) | ihp-sg13g2: `sg13_lv_nmos`, `rsil`, `via1`, `subconn_guard` | PASS 162/162 |
| `format_float` writes `%.1g` | same | FAIL 62/162: request 62, checked 54, geometry 43, bbox 39, magic_cell 25, roundtrip 15, texts 6, stamp 4 |
| `format_float` writes `%.8g` | same | FAIL 16/162: request 16, checked 8 |
| none (control) | gf180mcuD: `nfet_03v3`, `ppolyf_u`, `via1` | PASS 94/94 |
| `format_float` writes `%.1g` | same | FAIL 39/94: request 39, checked 31, magic_cell 23, bbox 19, geometry 19, roundtrip 4, stamp 2 |
| `format_float` writes `%.8g` | same | FAIL 12/94: request 12, checked 8 |

Version 0.5's dialog code, the same way on 2026-11-23, with path D, on
sky130A's `nfet_01v8`, `res_high_po_0p69`, `res_xhigh_po_5p73`,
`cap_mim_m3_1`, `diode_pd2nw_05v5` and `via1`:

| Change to the package | Result |
|---|---|
| none (control) | PASS 260/260 |
| coerce ignores the stored form (types the stored values into the defaults again) | FAIL 166/260: roundtrip 126, request 70, checked 65, magic_cell 35, typed 2, geometry 2, texts 2, bbox 2, stamp 2 |
| the server's chain leaves out the dependency callbacks (`res_recalc`, ...) | FAIL 48/260: request 42, dialog 42, checked 42, magic_cell 7, bindings 7, geometry 4, texts 4, bbox 4, roundtrip 1, stamp 1 |
| the server's chain runs one pass with no callback instead of two | FAIL 11/260: bindings 9, dialog 2, request 2 |
| edits typed in the manifest's parameter order instead of the dialog's rows | FAIL 10/260: request 10, dialog 10, checked 10, magic_cell 10, geometry 3, texts 3, bbox 3 |
| produce sends the visible values' text instead of the stored form | FAIL 138/260: request 138, roundtrip 62, checked 45, geometry 2, texts 2, bbox 2, magic_cell 2, stamp 2 |

Those runs were on the code before review 3. After it, the model of later
edits (Edit device and Apply) and of what the dialog shows after Create was
checked the same way on 2026-11-23, on sky130A's `nfet_01v8`,
`res_high_po_0p69`, `res_high_po_5p73`, `res_xhigh_po_5p73`,
`res_generic_po`, `cap_mim_m3_1`, `diode_pd2nw_05v5`,
`npn_05v5_W1p00L1p00`, `photodiode` and `via1`: 531 points, 142 of them
edit points.

| Change to the package | Result |
|---|---|
| none (control) | PASS 531/531 |
| a later edit starts from the form from before Create and is drawn by Create (the model before review 3) | FAIL 130/531, all edit points: request 130, dialog 130, checked 21, magic_cell 11, geometry 7, texts 7, bbox 7, roundtrip 3 |
| the server draws an Apply as a Create (without its first `_check`) | FAIL 7/531, all edit points: geometry 7, texts 7, bbox 7, checked 7, magic_cell 7, dialog 7, roundtrip 3 |
| Apply always makes a new cell (no comparison of cell names) | FAIL 9/531, all edit points: request 9, dialog 9, checked 3 |
| what the dialog shows after Create taken from Create's checked dict instead of the reopened dialog | FAIL 22/531 (11 edit points): dialog 22, request 6, checked 6 |
| the stored values are the form from before Create (the model before review 3) | FAIL 107/531 (86 edit points): dialog 107, request 11, checked 11, magic_cell 4 |

In version 0.2 the sweep took its text from the plugin's own formatter, and
the `%.1g` mutation passed 99 of 99 points. In version 0.3 no sweep value had
more than 7 significant digits, and a `%.8g` mutation passed 144 of 144
points on the sky130A set above.

### CI

`.github/workflows/parity.yml` runs one job per PDK in the image, pulled by
digest: `scripts/parity.sh --pdk <pdk> --quick` on pull requests and the full
sweep on a weekly schedule and on manual runs. Each job uploads
`out/parity/<pdk>/`. GitHub lists 14 GB of disk for standard runners and
the image is 11.7 GB unpacked, so each job frees disk space first and
prints `df` before and after the pull.

GitHub has run the workflow once, on its weekly schedule on 2026-11-23
(run 45232459515), on version 0.3 (tag `v0.3.0`), which `main` held until
version 0.5.0. The disk-space step and the image pull succeeded on all
four jobs, and sky130A and ihp-sg13g2 passed. gf180mcuD failed with
`PARITY FAIL 15/1493 (menu 15)` and ihp-sg13cmos5l with `PARITY FAIL
18/1159 (menu 18)`: in both, Magic under Xvfb exited before the menu
check's first job with `X Error of failed request: BadAlloc (insufficient
resources for operation)`, `Major opcode 53 (X_CreatePixmap)`, serial
1266. Traced in the image (with `strace` on Magic's X connection), the
pixmap request at serial 1265 or 1266 is Magic's first drawing pixmap, 939
pixels wide, whose height changes from one start to the next: in seven
starts on gf180mcuD it was 718 three times, 734, 1407, 2494 and 4161 (the
window is 768 high). Every local start succeeded, and why GitHub's Xvfb
refused it on two PDKs and not on the other two is not known. Path D,
which version 0.5 added, starts Magic under Xvfb the same way once every
50 device points, so it would most likely have failed there too. Since
version 0.5.0 the harness starts Magic again when it dies with an X error
before its first point or job, up to 8 times in a row, records how often
in the report, and then stops with a harness error; Xvfb's own messages go
to `out/parity/<pdk>/xvfb_*.log`. Whether that is enough on GitHub's
runners is unknown until the workflow runs again, which needs a push.

## Known differences

Where the PCells don't reproduce Magic, or where Magic's tools disagree with
the drawn values:

- The NODE elements of five sky130A vendor cells (see [Why Magic is the
  backend](#why-magic-is-the-backend)).
- A label's font. KLayout 0.30.11's GDS reader keeps no font (every text
  reads back with font -1) and its writer writes font 0, so a font other
  than 0 in Magic's GDS could not reach the PCell. Magic wrote font 0 on
  every text of every swept point; the harness compares the fonts of both
  files from the raw records, so a change would show.
- A label's size in the GDS file, in its last bits: KLayout writes the
  8-byte real of a text's magnification from its own value, so on
  ihp-sg13g2 `schottky` Magic's `0x4059999999999998` (0.35) becomes
  `0x405999999999999c` in a file the PCell is saved in. KLayout reads both
  as the same size.
- A coverage string, choice or number list that would reach Tcl as code draws
  the error marker, where Magic would reset it or draw nothing (see
  [Parameters](#parameters)).
- The PCell types each changed value into Magic's dialog once, in the
  dialog's row order, with Return, then presses Create for an instance's
  first edit and Apply for every later one. A Magic user may type with no
  Return, type in another order, leave a field (which runs its binding
  again), press Return on an unchanged value, or type several fields
  before one Create, and each of these can give other values; on sky130A's
  snake resistors shorter than 5.73 µm they can give another width (see
  [Values as Magic's dialog shows
  them](#values-as-magics-dialog-shows-them)).
- Fixed devices are flat: Magic writes an array instance of the vendor cell,
  and the PCell holds every copy's shapes. A 60 × 60 sky130A
  `npn_05v5_W1p00L1p00` array is a 22 KB GDS from Magic and 1,170,000 shapes
  in the PCell (1.8 s to place, 156 MB peak memory in plain Python, measured
  in version 0.2). The flat geometry is the same, but Magic's DRC checks a
  hierarchical array differently: on `cap_vpp_11p5x11p7_m1m2_noshield` with
  `nx 2` and `deltax 0.0034`, where neighbouring copies overlap, Magic's
  `drc(full)` on Magic's own output reports "This layer can't abut or
  partially overlap between subcells", and on the PCell, or on Magic's
  output flattened, it reports nothing.
- Extraction patterns that the harness records in
  `baseline/<pdk>/extract-known.json`. Its extraction check (item 11 under
  [Tests](#tests), step 8 in `run_sweep.py`'s log) has Magic read both
  sides from GDS, Magic's file and the PCell's, so both sides show them:
  - on gf180mcuD, `nfet_10v0_asym` and `pfet_10v0_asym` extract as
    `nfet_05v0` and `pfet_05v0` with l = 0.44u. This comes from Magic's GDS
    reader: Magic's own cell, extracted from Magic's database, is the
    asymmetric device with its drawn l (0.6u at the defaults), and the same
    cell written to GDS and read back is the 5 V FET
    (`readback-gf180mcuD.json`; see [Extraction](#extraction));
  - on the IHP PDKs, the four RF FETs extract as the FET model of the same
    voltage (`sg13_lv_rfnmos` as `sg13_lv_nmos`). The IHP read-back files
    list none of the RF FETs, so at the defaults their database extraction
    and their GDS read-back agree;
  - on sky130A, the `g5v0d16v0` FETs with `nf` of 2 or more extract every
    second finger as the `g5v0d10v5` model with a different length.
    Whether this one also comes from the GDS reader is UNVERIFIED: the
    read-back measurement uses each device's defaults, where `nf` is 1.

  gf180mcuD's MOS capacitors and varactors are not in the extraction check
  (they extract as `cap_nmos_03v3` and the like, and `pvaractor_6p0`
  extracts nothing, in research for version 0.3).

## Known limitations

- KLayout regenerates every variant from the installed Magic when it opens a
  file and doesn't ask first. The `kmp_created` warning, `audit --regen` and
  the versioned cache make a change visible; this version can't pin a Magic
  version.
- If Magic fails while a file is opening with the library registered, the
  failed variants get the error marker, and saving the file saves the marker
  in place of the device until the file is reopened with a working Magic.
- Every GUI, `-z` or `-zz` start pays about 0.6 s and one Magic process per
  registered PDK, even in sessions that never place one of these devices.
  `KMP_PDKS` limits the PDKs.
- Opening a large design runs Magic once per variant that isn't cached, about
  20 ms each.
- KLayout's own LVS of circuits built from these PCells: on the IHP PDKs,
  in research for version 0.6, the PDK's KLayout LVS in its default flat
  mode failed an inverter built from the PCells, because the D, S and G
  texts inside each device cell join the top-level nets of those names;
  deep mode matched, and so did netgen. The port check reports these texts
  (P7). sky130A and gf180mcuD devices have no pin shapes, because Magic
  writes labels only.
- A design saved as OASIS without the library keeps the labels' strings and
  positions but not their size or justification, and keeps one of two
  identical labels at one position (the vendor texts of gf180mcuD's npn
  devices): KLayout 0.30.11's OASIS files don't hold them. The harness's OASIS
  round trips compare labels that way.
- The child Magic is told to die with the KLayout thread that started it
  (`PR_SET_PDEATHSIG`); KLayout calls produce on its main thread. Linux only.
- A host layout whose database unit doesn't divide 5 nm rounds Magic's
  coordinates, and one of 5 nm or 2.5 nm rounds 1 nm coordinates: those of
  the vendor cells listed above, and those of a device whose sizes are typed
  to 1 nm (IHP's `bondpad` and inductors, in a test of version 0.3).
  `audit` reports each such cell, from the grid in its stamp.
- Another package that registers a library under one of these four names
  would replace it. The PDKs' own libraries have other names (`skywater130`;
  `gf180mcu`, `gf180mcu_klayoutapi`, `gf180mcu_sealring`; `SG13_dev`,
  `SG13_native_pcell_lib`, `sg13g2_stdcell_hv`, `sg13cmos5l_stdcell_hv`); the
  IHP libraries use device names such as `rsil` and `inductor2` too, so a
  layout that holds both gets cell names that KLayout makes unique. Loading
  them together with these libraries has not been tried, and neither has the
  IHP PDKs' autorun, which imports every module on `sys.path` whose name
  starts with `sg13` (this package's doesn't).
- Widgets of Magic's dialog whose name the device's defaults lack (the IHP
  RF FETs' `topc` and `botc` checkboxes) aren't PCell parameters: the PCell
  sends them as the dialog opens them, empty, and can't set them. Review 3
  set them in 16 combinations with `w` and `ng` per RF FET on ihp-sg13g2
  and saw only Magic's cell name change, because `mos_device` turns both on
  for devices that keep `gate_ring 1`, as the RF FETs do (not rerun
  since). A unit test fails if another widget that isn't a
  parameter appears in a manifest.
- Not tried: installing through the Salt manager (guide.md shows it
  listing the linked package), KLayout's `.mag` reader, `ext2spice merge`,
  and KLayout DRC with the density decks.

The checks of [Checking a layout with Magic](#checking-a-layout-with-magic):

- The Marker Database Browser shows the items of a subcell (DRC boxes in
  hierarchical mode that only the subcell's own check lists, port
  findings, and LVS markers of a subcircuit that netgen compared on its
  own) at one placement of that cell: the first
  placement the database refers to, or without such a reference the cell's
  first instance in the layout. This was seen with the browser's default
  context mode on a test layout of two cells; the other context modes
  weren't tried.
- No tiling: a cell is checked whole, in Magic processes of at most 15
  cells each, one after another. Memory on a large block hasn't been
  measured, and time only on the 100 µm block under [Magic
  DRC](#magic-drc)'s limits.
- An edit means the whole cell is checked again; there is no reuse of the
  results of unchanged subcells, only of a whole check of an unchanged
  cell.
- No view in KLayout's Netlist Database Browser: LVS gives netgen's report
  and the markers. KLayout's `NetlistComparer.same_nets` could impose
  netgen's pairing on a KLayout comparison; it isn't built.
- No KLayout deck for the rules that only Magic catches. On sky130A the
  candidates would be the rules that Magic reported on their cases in the
  gap table and no KLayout deck did, among them the tap and latch-up
  rules (`nwell.4`, `LU.2`, `LU.3`), `diff/tap.4` (a butting tap 0.20 µm
  deep, `e_butt_short`), `met1.3a` (two stubs on the edge of a huge met1
  area, 0.27 µm apart, `s_m1_wide_space`) and `x.2` (45° edges on
  diffusion and on li); on the other PDKs KLayout's decks check
  more of the front end than Magic does (see [Where KLayout and Magic
  disagree](#where-klayout-and-magic-disagree)). The Magic menu doesn't run
  `sky130A.lydrc` with FEOL on either, which in research for version 0.6
  caught 16 of the 26 front-end rules that sky130A's Run DRC (Full) missed
  on the one-change inverter cases.
- No resistance extraction and no parasitic extraction with kpex. In
  research for version 0.6, kpex's Magic engine gave Magic's numbers on
  seven of eight net pairs on sky130A and its 2.5D engine other numbers,
  and on ihp-sg13cmos5l kpex stopped on a missing include.
- No DRC with ihp-sg13g2's GDS tech file (`ihp-sg13g2-GDS.tech`), which
  checks TGO.e, TGO.f, pSD.a and pSD.b on the drawn layers; whether
  ihp-sg13cmos5l has one wasn't checked.
- PCell variants whose device Magic's GDS reader doesn't keep (see
  [Extraction](#extraction)) are marked, not fixed: replacing them with
  Magic's own cells before the extraction isn't built.
- netgen: a `badelements` entry in its JSON report hasn't been seen in a
  run; the parser assumes the shape of `badnets` and lists a device it
  can't place without a marker. How netgen names an array element inside a
  flattened path hasn't been seen either. When two devices of a cell have
  the same model and the same nets, the n-th of netgen's is taken as the
  n-th of Magic's.
- gf180mcuD's `DV.9` (3.3 V and 5 V or 6 V PMOS in one n-well): Magic's
  `drc(full)` reports it when the two devices are 3 µm apart and not at
  the two ends of a 100 µm n-well (the case suite's `dv9_long`); why is
  UNVERIFIED.
- The Magic menu has run in the KLayout GUI under Xvfb on sky130A only,
  driven by the screenshot rig (`KMP_SHOT_SESSIONS=magic
  tools/screenshots/take.sh`, which writes the `magic-*.png` files in
  `docs/img/guide/`). The rig triggers every entry through the menu's
  actions: DRC from its dialog and on the visible area, Rerun of the DRC
  report, LVS, extraction with capacitance (also beside a netlist file the
  plugin didn't write, which stayed unchanged), the generated-layer and
  port checks, Rule differences, Settings..., the PDK dialog, and Cancel of
  a long flat DRC, after which Magic's process was gone. For version 0.6.2
  the menu also ran under XFCE on a 1280 × 800 screen, the desktop of the
  course that uses the plugin, driven with xdotool: hierarchical DRC on an
  inverter and on a placement of standard cells without taps, the
  visible-area check while the browser was behind the main window, the
  generated-layer and port checks, Extract, LVS with Browse... (once
  picking a netlist that Extract had written), Rule differences maximised
  and restored, and Settings.... Not tried: the other PDKs; answering Yes
  when a second check asks to cancel the first; Rerun of the other
  checks' reports; the "Selection box" area; a check on a cell entered
  with Descend; whether a subcell's items show at their placements; the
  blocking progress bar of a KLayout without Qt; and how long the export
  holds up KLayout's main thread on a large layout.

## Changes from the design

- Four PDKs instead of sky130A alone, with one library, Magic process,
  manifest and baseline set per PDK, selected by `KMP_PDKS`. The design kept
  other PDKs out of scope.
- Box-paint generators are PCells (`w` and `h`). The design listed them as
  excluded.
- The server puts back the session state (layer locks, units, box stack)
  after each request, and keeps cells a generator places in its device
  rather than restarting Magic for them.
- The eight "\[+/-\](%)" coverage parameters are strings, not doubles (see
  [Parameters](#parameters)), and selectlists are choice parameters. The
  design typed the coverage values as floats and left selectlists out.
- Floats are sent as the 15-digit text KLayout saves, rounded to 12
  significant digits, rather than `repr()`, and a value equal to Magic's
  default is sent as Magic's default text. Without this, a reopened file
  changed its requests.
- Magic's checked values come from an execution trace on
  `magic::gencell_setparams`, which `gencell_create` calls with them; fixed
  devices have no `parameters` property to read them from. The trace changes
  no `::magic` proc, so the proc digest in the cache key covers only Magic's
  code.
- DRC sheets hold one device each. On a first sheet that mixed devices, Magic
  logged that it rescaled its units by 5 when it read the vendor cells with
  off-grid coordinates, and it reported no errors for `npn_11v0_W1p00L1p00`,
  which gets nine rule IDs when checked alone. Magic's DRC checks a 10 µm
  margin around the cell.
- An empty GDS from Magic is reproduced instead of being replaced by the
  error marker.
- Values the generator code would evaluate are refused before they reach
  Magic.
- The design said a cache entry is never checked again. The sidecar records
  the SHA-256 of the stored GDS, and an entry whose GDS doesn't match is
  deleted and regenerated. The cache key and the stamps cover more than the
  three version strings: the generator code, the PDK's files and the vendor
  GDS.
- `register()` also refuses a PDK whose running Magic lacks a generator of
  the manifest or loads another generator namespace, and an unwritable cache
  directory turns the disk cache off instead of stopping registration.
- The harness has more checks per point than the design listed (the request
  path B sent, Magic's cell name and checked values from both paths, the
  shape counts, every label attribute, the fonts from the raw GDS records,
  the GDS census, the menu check, round trips regenerated by Magic with the
  cache off), a known-extraction list per PDK, the manifest check, and a
  watchdog on path A. Path A's request text is independent of the plugin. The entry
  point is `scripts/parity.sh`, as in the design.
- `docs/design.md` section 4.2 gave the wrong reason for leaving out Magic's
  dialog callbacks, and has a correction note that says so.
- Since version 0.5 the PCells store the values Magic's parameter dialog
  shows after Create, with its dependency callbacks run, draw what its
  Create makes, and treat a later edit as one in the Edit device dialog
  followed by Apply; the design stored the typed values and followed
  `magic::gencell`. The design's section 4.5, added for version 0.5,
  describes it. The harness's reference for devices is Magic's real dialog
  under Xvfb (path D), and `magic::gencell` (path A), which the design made
  the reference, is the second one.
- The project is licensed under Apache-2.0, which the design left open.

The checks of version 0.6 against their design,
[docs/design-0.6.md](docs/design-0.6.md):

- **The default DRC mode is hierarchical**, Magic's own reading of the file.
  The design made flat mode the default and offered a "per-cell" mode
  beside it. On all four PDKs, a layout with its implants or well in a
  parent cell was clean in flat mode while Magic's own reading found errors
  and other transistors (see [Magic DRC](#magic-drc)). Extraction and the
  generated-layer check use the same reading. `KMP_DRC_MODE=per-cell` is
  refused with a message that says "per-cell is now called hierarchical".
- **The implant check (F1) is an enclosure check.** The design reported
  Magic's implant minus the user's. That gave findings on correct layouts:
  sky130A's `sky130_fd_sc_hd__dfxtp_1` and `__mux2_1` left part of Magic's
  npc uncovered, and so did a layout that Magic had written itself. F1 now
  measures the user's enclosure of each device shape against the distance
  Magic's GDS output grows the layer, read from the tech file, and the
  foundry cells and a row of them written by Magic give no finding.
- **No tiling and no halo.** The design split a large cell into tiles
  checked in parallel (`KMP_JOBS`, `KMP_TILE_UM`) and checked an area grown
  by the largest distance a rule looks across. Neither works for a rule
  about a whole shape: sky130A's `nwell.4` gave a false error on the far end
  of a long n-well whose tap was at the other end. Neither setting exists.
- **The area check filters a whole-cell check.** Magic checks the whole
  cell and the database keeps the errors that touch the area. The job
  directory doesn't depend on the area, so the next area check reuses it.
- **The rerun record is a KLayout Recipe.** The design put the command line
  into the report database's generator. The Marker Database Browser's
  Rerun button needs a Recipe there, and with a command line it showed an
  error box. The command line is in the description instead.
- **The `.ext` unit comes from Magic's `[cif scale out]`**, printed by the
  same Magic process. The design read it from the `.ext` file's `scale`
  line, which says 500000 on sky130A and 0.5 on the other PDKs, so markers
  would have landed in the wrong place on three PDKs.
- **Nets in subcells get markers.** The design listed them without one
  until the transform of an `.ext` `use` line was known. It is now: `use
  <cell> <id> a b c d e f` puts a child point (x, y) at (a·x + b·y + c,
  d·x + e·y + f) in the parent, and an array element adds its offset first;
  this was checked on all four PDKs in all eight orientations and on a
  rotated array.
- **Cell names are checked.** The design passed cell names to Magic as
  they were, and a name Magic renames or can't find gave a clean result.
  The export now renames every cell whose name isn't letters, digits, `_`
  and `$`, every Magic job checks that it loaded the cell it was given and
  that the cell isn't empty, and the command line checks `--cell` against
  the file before Magic starts.
- **`extract` writes `<cell>.magic.spice`.** The design wrote
  `<cell>.spice` beside the layout, and in the case suite that replaced the
  inverter's schematic, `inv.spice`. The netlist now gets its own name and
  a header line, and `extract` replaces only a file that starts with that
  header (see [Extraction](#extraction)).

## Licence and credits

klayout-magic-pcells is licensed under the Apache License, Version 2.0: see
[LICENSE](LICENSE). [NOTICE](NOTICE) names the sources below; under
Apache-2.0, copies of the package that you distribute have to include it.

The package ships no code from Magic or from the PDKs. The four manifests in
`python/klayout_magic_pcells/data/` hold data that `tools/build_manifest.py`
reads out of each PDK's Magic generator code by running it in Magic: device
and parameter names, default values, the labels, order and callbacks of
Magic's parameter dialogs, what each `_check` proc does to some probe
values, and a summary of what Magic draws for the defaults. What each PDK's
installed files say about their licence, in the image listed under
[Requirements](#requirements):

| PDK | The manifest's data comes from | Licence the PDK states |
|---|---|---|
| sky130A | `sky130A.tcl`, installed by open_pdks 026824c7, by Tim Edwards | none in `sky130A.tcl`; the install has no licence file; its Magic tech file `sky130A.tech` says it "may be distributed under the terms of the Apache 2.0 license agreement" |
| gf180mcuD | `gf180mcuD.tcl`, installed by open_pdks 026824c7, by Tim Edwards | none: neither the Tcl file, nor the tech file (which says "Copyright (c) 2022 Efabless, Inc."), nor a licence file in the install |
| ihp-sg13g2 | `ihp-sg13g2.tcl` and the `ihp-sg13g2-*.tcl` files it sources | Apache-2.0: every Tcl file but `read_sram_gds.tcl` carries the header "Copyright 2025 IHP PDK Authors, Licensed under the Apache License, Version 2.0"; the install has no top-level licence file |
| ihp-sg13cmos5l | `ihp-sg13cmos5l.tcl` and its `ihp-sg13cmos5l-*.tcl` files | Apache-2.0: the same header with "Copyright 2026 IHP PDK Authors" (again not on `read_sram_gds.tcl`), and the Apache-2.0 text as `LICENSE` at the top of the install |

The same folder holds four more data files per PDK, added in version 0.6
and made from the same PDK installs:

| File | What it holds | How it is made |
|---|---|---|
| `pdk-<pdk>.json` | Magic's DRC rules, the layers Magic reads and writes, the implants it grows and by how much, and the label and pin layers | `tools/build_pdk_data.py` reads the PDK's Magic tech files, the layer names of its KLayout layer properties file (`.lyp`), and the layer pairs that the PDK's KLayout LVS deck reads labels from |
| `devices-<pdk>.json` | how Magic's GDS reader decides each device type, for the generated-layer check | typed from the tech file's GDS input and output styles, each row citing its lines |
| `readback-<pdk>.json` | the devices that Magic's GDS reader doesn't keep | measured in Magic by a backend test |
| `gaps-<pdk>.json` | one entry per row of the gap table that has a Magic statement of its own (a row whose statements all name its rule only as a later operand of a composite rule, as `via.4a` in `via.1a + 2 * via.4a`, has none): the row's status, the names and values of its KLayout deck outputs, the IDs that Magic prints for its statements and their tech-file lines | `tools/build_gaps.py`, from the data file, runs of the decks and Magic in the image, and the alias files |

These ship under Apache-2.0, as the manifests do. The project lead decided
this for data read out of the PDKs' Magic files, as other tools under that
licence do with data extracted the same way. open_pdks' own licence and
those of the sky130 and gf180mcu source repositories are not in the image
and weren't checked.

The harness and the gap-table builder run the PDKs' KLayout DRC decks from
the PDK install and don't copy them (`sky130A_mr.drc` and `sky130A.lydrc`
say GPLv3 in their headers, gf180mcu's and the IHP decks Apache-2.0). The
gap tables store each deck output's name, value and line, and as its
switch the text of the condition around it in the deck, cut to 60
characters (such as `TABLES.include?('via1') || BEOL`), but none of the
rules' code.

The devices themselves are Magic's: the generators in the PDKs' Tcl files
and Magic's `toolkit.tcl`, from open_pdks, the IHP PDKs and Magic.

Two earlier projects were read for their structure and licences, and no code
was copied from either:

- [efabless/sky130_klayout_pdk](https://github.com/efabless/sky130_klayout_pdk),
  Apache-2.0, with Python PCells by Mabrains LLC and Efabless; the same PCell
  code ships in the PDK as the `skywater130` library.
- [laurentc2/SKY130_for_KLayout](https://github.com/laurentc2/SKY130_for_KLayout),
  BSD-2-Clause, a technology, DRC and LVS setup with no PCells.
