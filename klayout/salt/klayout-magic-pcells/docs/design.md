# klayout-magic-pcells design

Written 2026-11-21, before any implementation, for sky130A alone. Version
0.3 adds gf180mcuD, ihp-sg13g2 and ihp-sg13cmos5l, one library per PDK, and
PCells for Magic's box-paint generators (vias, contacts, substrate contacts,
guard rings and wells); the README describes those and lists where the code
differs from this document. Version 0.5 stores the values Magic's parameter
dialog shows instead of the values typed, as the project lead decided on
2026-11-22; section 4.5 describes that design, and it replaces the parts of
sections 4.2, 4.3 and 10 that say otherwise.

This is the design for a KLayout PCell library for the sky130A devices that
Magic generates. Each PCell asks Magic to generate the device and copies the
GDS that Magic writes into the PCell cell, so a device placed in KLayout has
the same geometry and labels as the same device generated in Magic.

The design rests on three research notes and on four probes and two one-off
checks run while writing it. The Sources section at the end lists them. Claims
that the design depends on carry a tag:

- **[run]**: run in the pinned image
  `hpretl/iic-osic-tools@sha256:3c371645b19c6f6564dc8c7b21e39ad1c1833d274fe5b85639afe1ba9d7987e7`
  (Magic 8.3.681, KLayout 0.30.11, sky130A from open_pdks 026824c7).
- **[src]**: read from source code or documentation.
- **[untested]**: neither. Section 15 collects these.

`$S` below stands for the scratch directory that held the research. It was a
local folder and is not part of this repository.

Terms used throughout:

- *produce* and *coerce* are KLayout's PCell hooks `produce_impl()`, which draws
  the cell, and `coerce_parameters_impl()`, which may correct parameter values.
  The *GUI form* is KLayout's PCell parameter page.
- A *variant* is the cell KLayout makes for one set of PCell parameter values.
  A *cold proxy* is a variant whose library isn't registered; KLayout shows it
  as `<defunct>` and keeps the geometry stored in the file.
- For each device, Magic's `sky130A.tcl` defines Tcl procs named
  `sky130::<dev>_defaults` (the parameter dict), `_check` (clamps bad values and
  returns the corrected dict), `_draw` (paints the device), `_dialog` (builds
  the Tk form) and `_convert` (maps SPICE parameters). Magic's `toolkit.tcl`
  calls them through `magic::gencell`, `magic::gencell_create` and
  `magic::gencell_makecell`.
- *Salt* is KLayout's package system. A package is a folder with a `grain.xml`
  file.

## 1. Goal and parity definition

The library offers the 60 devices that `sky130A.tcl` defines with both a
`_defaults` and a `_draw` proc [run]: 22 resistors, 12 MOSFETs, 12
fixed-layout devices, 8 diodes, 3 varactors, 2 MIM capacitors and 1
photodiode.

In this document, parity means that for a given set of parameter values the
PCell cell, flattened, has the same polygons on every GDS layer/datatype and the
same label texts (string and position) as the GDS that Magic writes when its
generator is called once with those values through `magic::gencell` (section
10.3), which runs `_check` once; running it twice can change the result
(section 4.3). The comparison is exact: an XOR per layer at a common
database unit, with no tolerance and no alignment. Cell names, hierarchy,
GDS properties and timestamps are not part of parity.

The two earlier bespoke attempts were read for their structure and licences
only, and no code is copied from either:
efabless/sky130_klayout_pdk (Apache-2.0, Mabrains and Efabless code) and
laurentc2/SKY130_for_KLayout (BSD-2-Clause, no PCells).

## 2. Constraints

These are the facts from the research that shape the design. Later sections
refer to them as K1–K7 and M1–M8.

KLayout 0.30.11 (klayout.md, section 0):

- **K1.** `Layout.read` into a layout that already has content switches that
  layout's dbu to the file's dbu and doesn't rescale the existing shapes. In the
  test a 1 µm box became 0.5 µm. Same-named cells are also merged [run].
- **K2.** If produce fails while a file is opened with the library registered,
  the variant loses its stored geometry, and the next save writes empty cells.
  The parameters survive, and a later open with a working backend regenerates
  the geometry [run].
- **K3.** If a new variant's first produce raises, the cell gets an empty name.
  The GDS writer accepts it and the reader then rejects the file with "Empty
  cell name" [run].
- **K4.** `klayout -b` doesn't run autorun macros. `klayout -b -rm <macro> -r
  <script>` runs the named macro, and the package's `python/` folder is on
  `sys.path` even under `-b` [run].
- **K5.** KLayout runs coerce before every produce. Outside the GUI form the
  coerced values go to produce but are not stored; the file keeps the values the
  caller passed [run, src].
- **K6.** A library bound to a technology is invisible to layouts that have no
  technology set: `create_cell` returns `None`, and saved files open as
  `<defunct>` cells [run].
- **K7.** Registering a library under a name that already exists replaces the
  old library, and its instances move to the new one. The PDK's own library and
  the Efabless package are both called `skywater130` [run, src].

Magic 8.3.681 (magic.md and parity.md):

- **M1.** Magic takes 225–231 ms to start. One generation takes 12–22 ms, and a
  warm process is no faster than a cold one, so the start-up is the whole cold
  cost [run].
- **M2.** A Magic process driven over pipes handled 31 requests. An unbalanced
  brace in a request blocks the session until something closes the brace [run].
- **M3.** `gencell_create` with an empty dict takes the Tk dialog branch and
  fails. Without a named edit cell and `box 0 0 0 0` it returns an empty
  instance name. Asked for parameters whose cell already exists, it logs "Can't
  place a cell on an exact copy of itself.", returns an empty name with Tcl
  status 0, and the following `gds write` gives a 118-byte file with no cells
  [run].
- **M4.** `gencell_makecell` doesn't run `_check`, and it leaves `units` set to
  `internal noprint` [run, src].
- **M5.** `_check` clamps bad values and warns through `puts stderr`. It never
  raised an error in 23 probes or on any device's defaults. It doesn't snap to a
  grid: off-grid values reach the cell-name hash, and the drawing rounds W and L
  to 0.01 µm, so a requested `w 0.425` is drawn 0.43 µm wide [run].
- **M6.** Magic writes dbu 0.001 µm and a single flat structure for a drawn
  device, centred on the origin, with labels as zero-size texts on `*/5` and no
  GDS properties. Two writes of the same cell differ in their timestamps, so
  files can't be compared byte for byte [run].
- **M7.** The 12 `nocell` devices (npn, pnp, vpp caps, rf coils) place a vendor
  cell from libs.ref, backed by `GDS_FILE`. That cell has no hash suffix and no
  `parameters` property, its origin is its lower-left corner, and `nx`/`ny`
  become an array on the instance in the parent cell [run].
- **M8.** MOSFET `w` is the width of one finger. Only the `-spice` path treats
  `w` as the total and divides it by `nf` [run].

## 3. Architecture

```
KLayout process: GUI, -z/-zz, -b with -rm, or python3 with the klayout module
 └─ library "sky130_magic" (Sky130MagicLibrary, library layout dbu 0.001)
     └─ 60 PCells, one per device, declared from the shipped manifest
         └─ produce_impl()
              ├─ Generator.get(device, request)
              │    ├─ in-memory memo
              │    ├─ GdsCache: GDS file plus JSON sidecar on disk
              │    └─ MagicServer: one `magic -dnull -noconsole` child on pipes
              │         └─ kmp_server.tcl: gencell_create, gds write, delete the cell
              └─ insert_gds_flat(): read the GDS into a fresh Layout and copy
                 the shapes per layer into the PCell cell; then apply the stamp
```

### 3.1 Magic's GDS output as the reference

Several steps between what `_draw` paints into a Magic cell and what goes to
the mask happen only in `gds write`, through the `gdsii` cifoutput style in
`sky130A.tech`:

- **Contact cuts.** The .mag of the nfet `w 1.5 l 0.5 nf 3` holds contact areas
  (4 `ndiffc`, 4 `psubdiffcont`, 6 `polycont`, 10 `viali`) and no cut layer.
  Its GDS has 52 cuts on 66/44 and 22 on 67/44, all 0.17 × 0.17 µm, made by the
  rules `squares-grid 0 170 170` and `squares-grid 0 170 190` [run]. The
  high-poly resistor gets 0.19 × 2.0 µm slots on 66/44 from the `xpc` slots
  rule, and `cap_mim_m3_1 w 5 l 10` gets 289 via3 cuts [run].
- **Layer numbers.** Magic types such as `ndiffc` and `viali` get a GDS
  layer/datatype only through the style.
- **Labels.** Magic moves a label from the drawn type to the contact type. The
  MIM cap's C2 is drawn on metal3 and written as a text on 71/5 (met4) [run].
- **The prBoundary.** The box on 235/4 comes from the `FIXED_BBOX` property
  through the `boundary` rule [run].
- **Fixed devices.** `gds write` copies the vendor GDS bytes. A per-layer XOR
  plus a text comparison against `sky130_fd_pr.gds` found no difference for the
  5 devices checked [run].

Reproducing these steps in Python would make one more bespoke generator.
KLayout's `.mag` reader reads Magic's own layer names, and the research found
nothing saying it applies the cifoutput rules [untested]. The plugin therefore
takes the file that Magic's `gds write` produces and treats it as the device.

### 3.2 The produce call

1. Build the request: every user-editable parameter of the device, as the
   string that will be sent to Magic (section 4.2).
2. Compute the cache key (section 6). Look in the in-memory memo, then on disk.
3. On a miss, send a `generate` request to the server. Magic writes the GDS into
   the cache's temporary directory. The reply carries Magic's cell name, the
   post-`_check` parameter dict and the captured `stderr` text. The backend
   moves the GDS into place and writes the JSON sidecar (section 6).
4. `insert_gds_flat()` copies the shapes into `self.cell`.
5. Apply the generated-by stamp (section 7). Compare the instance's
   `kmp_created` value with the current stamp, and log a warning if Magic or the
   PDK has changed since the instance was created.
6. On any failure, draw the placeholder described in section 5 and return.
   produce never raises (K2, K3).

### 3.3 The Magic server

There is one Magic child per KLayout process. `register()` starts it (section 5
explains why at registration and not on first use):

```
magic -dnull -noconsole -rcfile $PDK_ROOT/sky130A/libs.tech/magic/sky130A.magicrc
```

The child's stdin, stdout and stderr are pipes. Its working directory is `<cache>/run/`, so
a stray relative write can't land in the user's directory. `PDK_ROOT` is set in
the child's environment; the sky130A rcfile reads no other variable [run]. On
Linux, `preexec_fn` sets `PR_SET_PDEATHSIG` through `ctypes` so the child dies
with KLayout, and an `atexit` handler sends `quit -noprompt` and kills the child
after 2 s. Whether Magic exits by itself when its stdin closes is [untested].

The first line sent is `source <package>/tcl/kmp_server.tcl`, and the server
answers `KMP_READY 1`, where 1 is the protocol version. The prototype is
`$S/mexp/e10/server.tcl`, driven by `$S/mexp/tools/persist.py` [run, 31
requests]. The production server differs from it in three ways.

**Parameters travel as data.** A request is one line, `kmp::req <id> <hex>`.
`<hex>` is the hex encoding of a UTF-8 JSON object:

```json
{"op": "generate", "device": "sky130_fd_pr__nfet_01v8",
 "params": {"w": "1.5", "l": "0.5", "nf": "3", "m": "1", "guard": "1"},
 "form": "cell",
 "out": "/home/u/.cache/klayout-magic-pcells/tmp/3f9a12c4.4711.gds"}
```

(`params` holds every editable parameter; the example is shortened. `form` is
explained in section 3.4.) The Tcl
side decodes it with `binary decode hex` and tcllib's `json::json2dict`; json
1.3.4 loads inside Magic [run]. Every request line is a complete Tcl command
whatever the parameter values are, so the blocked session from M2 can't happen.

**Replies are framed lines.**

```
KMP_BEGIN 17
KMP_KV 17 rc <hex of "0">
KMP_KV 17 cell <hex of "sky130_fd_pr__nfet_01v8_8KDQ7Y">
KMP_KV 17 log <hex of the captured stderr text>
KMP_KV 17 us <hex of the elapsed microseconds>
KMP_PARAM 17 w <hex of "1.5">
KMP_PARAM 17 l <hex of "0.5">
...
KMP_END 17
```

After `KMP_END` the server runs `flush stdout`; it sets `fconfigure stdout
-buffering line` once at start. Values use `binary encode hex`, a Tcl 8.6
command that hasn't been run inside Magic yet. Magic prints informational
messages on stdout (`Loading sky130A Device Generator Menu ...`, `Creating new
cell`), so the Python reader thread logs any line without the `KMP_` prefix at
debug level and otherwise ignores it.

**`puts stderr` is captured per request**, with the `rename ::puts` override
from magic.md section 4. In the research it collected the generators' own
messages and Magic's C-side errors alike [run]. The request body runs inside
`catch`, so a Tcl error comes back as `rc 1` with its message.

The server knows four operations:

| op | Tcl | Reply |
|---|---|---|
| `generate` | the sequence below | rc, Magic's cell name, checked dict, log, time |
| `check` | `sky130::${dev}_check [magic::gencell_defaults $dev sky130 $params]` | rc, checked dict, log; nothing is drawn |
| `versions` | `version`; `tech version`; a list of `info args` and `info body` for every proc in `::sky130` and `::magic` | version strings, proc text for the code digest |
| `ping` | | rc |

`generate` follows the working sequence from magic.md section 2 and guards each
trap in M3:

```tcl
load kmp_top
box 0 0 0 0
set inst [magic::gencell_create $dev sky130 [magic::gencell_defaults $dev sky130 $params]]
if {$inst eq ""} { error "gencell_create returned no instance" }  ;# M3: no box, or an exact copy
set g [instance list celldef $inst]
set checked [cellname list property $g parameters]               ;# empty for nocell devices
if {$form eq "cell"} { load $g } else { load kmp_top }
gds write $out
load kmp_top
select cell $inst
delete
if {$form eq "cell"} { cellname delete $g -noprompt }
```

`gencell_create` always gets the merged defaults, never an empty dict (M3). It
runs `_check` once and restores `units` itself, which is why the plugin doesn't
use `gencell_makecell` (M4). After each request the server compares `cellname
list allcells` with the list it saw at start, leaving out the vendor cells that
`nocell` devices load from libs.ref; those stay loaded and are reused. If any
other cell is left over, the server answers the request and asks the client to
restart it. Whether a second request for the same fixed device works with its
vendor cell still loaded is [untested]. The backend tests (section 10.7)
generate every device twice in one session.

The Python side lives in `python/klayout_magic_pcells/backend.py`:

```python
class MagicServer:
    def start(self) -> Versions        # spawn, source kmp_server.tcl, run "versions"
    def generate(self, device, request, form, out_path) -> GenReply
    def check(self, device, request) -> CheckReply
    def close(self)                    # quit -noprompt, kill after 2 s

class Generator:                       # memo, then GdsCache, then MagicServer
    def get(self, spec, request) -> Result
```

A `threading.Lock` serialises requests. Each request has a timeout
(`KMP_TIMEOUT`, default 30 s). On a timeout, EOF or a framing error the backend
kills and restarts Magic and retries the request once; a second failure raises
`BackendError`, which produce turns into the placeholder. `MagicOneShot`
implements the same interface with one Magic process per request, using the same
Tcl procs from a script file. It exists for debugging and pays the 0.23 s
start-up on every request (M1).

### 3.4 GDS form per device

The cell written depends on the manifest's `nocell` flag, and the harness's
Magic-only path applies the same rule (section 10.3), so compare.py runs
without `--align`.

- **Drawn devices (48): `form = "cell"`.** `load $g; gds write` writes the
  device cell alone, in Magic's own coordinates and centred on the origin
  [run].
- **Fixed devices (12): `form = "wrapper"`.** For these, `nx` and `ny` are an
  array on the wrapper instance (M7), so writing the device cell alone would
  lose them. The server writes `kmp_top`, which holds the arrayed instance of
  the vendor cell, and the importer flattens it. Where `gencell_create` places
  that instance for a cell with no `FIXED_BBOX`, and how `deltax`/`deltay`
  combine with `xstep`/`ystep`, are [untested]. The research compared only
  `nx = ny = 1` against the vendor GDS.

Writing the wrapper for drawn devices as well would also work, but the device
would then sit with the lower-left corner of its `FIXED_BBOX` at the origin, at
(1.755, 1.535) for the nfet [run], instead of in Magic's cell coordinates.

### 3.5 Copying the GDS into the PCell cell

`python/klayout_magic_pcells/importer.py`:

```python
def insert_gds_flat(layout, cell, gds_path):
    src = db.Layout()                  # never read into the library layout (K1)
    src.read(gds_path)
    tops = src.top_cells()
    if len(tops) != 1:
        raise GdsImportError(f"{gds_path}: expected one top cell, found {len(tops)}")
    ratio = src.dbu / layout.dbu       # 0.001 / 0.001 for Magic output
    mag = round(ratio)
    if mag < 1 or abs(ratio - mag) > 1e-9:
        raise GdsImportError(f"source dbu {src.dbu} is not a multiple of {layout.dbu}")
    t = db.ICplxTrans(mag)
    for li in src.layer_indices():
        info = src.get_info(li)
        dst = layout.layer(info.layer, info.datatype)
        cell.shapes(dst).insert(tops[0].begin_shapes_rec(li), t)
```

The flat per-layer insert kept geometry, texts and properties exact whenever the
source dbu was an integer multiple of the target's, and it creates no subcells
[run]. `copy_tree` of a source with subcells, by contrast, left `<defunct>`
orphan cells on reopen and renamed a user cell called `VIA` [run]. produce runs
in the library layout, whose dbu is 0.001 like Magic's output, so the ratio is
1.

KLayout then converts the variant into each host layout. A library at 0.001
into a host at 0.0005 was exact [run]. A host whose dbu doesn't divide 5 nm,
such as 0.01, would round every coordinate that is an odd multiple of 5 nm; that
follows from the grid but wasn't run.

## 4. Parameters

### 4.1 The manifest

PCell declarations come from
`python/klayout_magic_pcells/data/manifest-sky130A.json`, which is built by
querying Magic in the pinned image and committed with the package. It is
shipped rather than built at start-up so that the PCell declarations change only
when someone rebuilds the manifest and commits the diff, not when Magic is
upgraded.

`tools/build_manifest.py` runs `python/klayout_magic_pcells/tcl/kmp_manifest.tcl`
in one Magic process. For every device that has both
`::sky130::<dev>_defaults` and `::sky130::<dev>_draw`, it records:

- the defaults dict, in order, from `sky130::<dev>_defaults`;
- each parameter's widget kind and label, by running `sky130::<dev>_dialog`
  against stub versions of `magic::add_entry`, `add_checkbox`,
  `add_selectlist`, `add_message` and `add_dependency`;
- the integer checks in `_check` (`nf`, `m`, `nx`, `ny`);
- what `_check` changes and prints when run on the defaults;
- `nocell`, from `dict exists [sky130::${dev}_defaults] nocell`;
- the batch result with defaults: Magic's cell name, layers, texts and bounding
  box;
- for each float parameter, `_check` run on the defaults with that parameter
  set to 0 and to 1e4, and the clamped values kept as `check_min` and
  `check_max` when `_check` changed them (only the sweep uses these);
- `defaults_digest`, a SHA-256 over the canonical JSON of all 60 defaults dicts,
  and the output of the server's `versions` op.

This is the research's method (`$S/mexp/e8/manifest.tcl` and
`$S/mexp/tools/build_manifest.py`). It produced `magic-manifest.json` with 60
devices and no batch failures [run]. The limit probes are new.

When the server starts, the backend computes `defaults_digest` from the live
Magic. If it differs from the manifest's, the backend logs a warning, `doctor`
prints which devices differ, and the library still registers. `KMP_MANIFEST` can
point at a rebuilt manifest. If the live Magic has dropped a parameter that the
manifest still declares, the plugin keeps sending it. In the research an
unknown `foo 1` stayed in the dict without a message and changed the cell-name
hash [run]; its effect on geometry wasn't checked.

### 4.2 Mapping to KLayout parameters

Across the 60 devices there are 49 distinct user-editable parameter names, and
the manifest types every one of them as `float`, `int` or `bool01` [run, a count
over the manifest]. None of the 49 collides with an attribute of
`PCellDeclarationHelper` [run]. The PCell factory still checks each name against
`dir(PCellDeclarationHelper)` and stops registration with an error if a future
manifest adds a colliding name, because a parameter called `cell` or `layout`
would overwrite the helper's own attribute [src, run].

| Manifest type | KLayout type | Sent to Magic as |
|---|---|---|
| `float` | `TypeDouble` | `repr(value)`, for example `0.42` or `1.5` |
| `int` | `TypeInt` | `str(value)` |
| `bool01` | `TypeBoolean` | `1` or `0` |
| keys with `user_editable: false` (`lmin`, `wmin`, `class`, `compatible`, `rho`, `term`, `dummy`, `doports`, `nocell`, `xstep`, …) | not declared | not sent; `gencell_defaults` fills in Magic's own value |

- **Description:** the dialog label (`Width (um)`, `Fingers`, `Add guard
  ring`). On MOSFETs, `w` is described as `Finger width (um)`, because `w` is per
  finger (M8): `w 1.5 nf 3` is 4.5 µm of total width. The plugin doesn't use the
  `-spice` path.
- **Default:** the manifest default parsed as the declared type (`0.420`
  becomes 0.42). `magic::normalize_value` hashes `0.42` and `0.420` the same
  [src], and the drawing reads both as the same number.
- **Unit:** `µm` when the label says `(um)`, `%` for the coverage parameters,
  and the label's own unit for `val`, `area` and `peri`.
- **No limits:** no `min_value`/`max_value`, no snapping and no choices. Magic's
  `_check` is the only validation.
- **One hidden parameter:** `kmp_created`, the creation stamp (section 7). It is
  left out of the request and out of the cache key.

`display_text_impl()` shows a short device name and the family's leading
parameters, for example `nfet_01v8(w=1.5 l=0.5 nf=3)` or
`res_high_po_0p69(w=0.69 l=5 nx=2)`. If the memo holds a result for the request
and `_check` changed one of the values shown, the text shows Magic's value with
an asterisk: `nfet_01v8(w=0.42* l=0.15 nf=1)`.

Two parts of Magic's dialog are not carried over:

- **The `gencell` selectlist**, which switches the device type. Passing
  `gencell=<other device>` in the dict makes `gencell_create` switch device
  [src, manifest notes]. Here each device is its own PCell, and KLayout stores
  the PCell name in each file's context, so switching device would mean a
  different PCell.
- **The dialog callbacks** `sky130::res_recalc`, `cap_recalc` and
  `diode_recalc`, which keep `val`, `l` and `w` consistent while a user types in
  Magic's dialog. In the plugin these fields follow `_check` alone (section
  4.4). (Correction, 2026-11-21: the reason first given here, that these
  callbacks are Tk dialog code, is wrong. `res_recalc` is plain Tcl and runs
  under `magic -dnull`; `cap_recalc` and `diode_recalc` print a line and
  return their input.) (Version 0.5, 2026-11-23, runs all three through the
  server, as Magic's dialog does; see section 4.5.)

### 4.3 Validation with `_check`

(Superseded in version 0.5: the stored values are what Magic's dialog
shows, and coerce sets them; see section 4.5. The probe results below
still hold.)

`_check` is not idempotent. A probe for this design ran `_check` on 12 inputs
and then again on its own output [run, `docs/probes/idem.tcl`]:

| Device and input | First `_check` | Second `_check` | Cell-name hash |
|---|---|---|---|
| res_high_po_0p69 `w 1.0` | w 0.690, val 709.44, width message | val 1.028k | GATT6Z, then UELT9B |
| res_high_po_0p69 `l 0.1` | l 0.50, val 611.043, length message | val 796.434 | XP6LE4, then B3X8UN |
| cap_mim_m3_1 `l 0 val 50` | l 11.242, val 50.0 | val 49.999 | 237BC9, then Q6G9SH |

The other nine inputs came back unchanged from the second pass: nfet `l 0.1 w
0.1 nf 0`, cap `w 50`, cap `square 1 val 100`, diode defaults and `w 2 l 3`,
resistor `l 0` and `l 5 nx 2`, xhigh_po `l 3`, and res_generic_m1 defaults. In
the two resistor rows the first pass computes `val` from the width or length
before clamping it, and the second pass computes `val` again from the clamped
value. In the cap row, `val` moves from 50.0 to 49.999 on the second pass. The
cell name changes in all three; whether the drawn geometry changes once `w` and
`l` are fixed is [untested].

The plugin therefore runs `_check` exactly once per generation, inside
`gencell_create`, on the user's values merged with the defaults. That is what
`magic::gencell` does with its arguments [run, src], and the harness compares
against it (section 10.3).

- **`coerce_parameters_impl` is not overridden.** KLayout runs coerce before
  every produce (K5), and in the GUI form it writes the coerced values back
  into the instance. If coerce wrote Magic's corrections back, the next produce
  would send checked values and `_check` would run on them a second time.
  Calling Magic from coerce would also double the Magic calls per regeneration.
  The cost is that the KLayout form keeps the entered value where Magic's
  dialog would show the corrected one.
- **The stored parameters are the user's request.** A file can hold `l = 0.1`
  for a device that Magic drew with `l = 0.15`, in the GUI and in batch alike.
  Magic stores the post-check dict in its instance property `parameters`
  [run], so the two tools store different values for the same drawing.
- **The GUI shows the corrections.** In the GUI form, `callback_impl(name)`
  sends a `check` request with the form's values (`self.<p>.value`). For each
  parameter that `_check` changed it sets `PCellParameterState.WarningIcon` and
  a tooltip such as `Magic draws 0.15 (entered 0.1): Mos length must be >= 0.15
  um`. Magic's messages don't say which parameter they belong to, so each
  tooltip carries the whole message text. Exceptions in `callback_impl` only
  reach the log [src]; a backend failure sets `ErrorIcon` on the first
  parameter. The icon behaviour comes from source and hasn't been seen on
  screen [untested].
- **Outside the GUI**, the messages go to `tl.Logger.warn` (the class
  `klayout.tl.Logger` has `info`, `warn` and `error` [run]) and into the cache
  sidecar. `python3 -m klayout_magic_pcells check sky130_fd_pr__nfet_01v8
  w=0.1 l=0.1` prints them from the command line.
- **Corrections don't raise.** `_check` rejected no parameter set in the
  research's probes (M5), and raising in coerce would refuse the change in the
  GUI and draw nothing in batch [run, src].

Magic's own dialog behaves differently [src, toolkit.tcl]. Every entry runs
`magic::update_dialog` on Return or focus-out, and every checkbox and
selectlist runs it on change. `update_dialog` runs `_check` on the form's
values, then the device's recalc callback if it has one, and writes the result
back into the form (`magic::gencell_setparams`). "Create" then calls `gencell_create` with the
form's values, which runs `_check` again. For the three inputs in the table, a
dialog user and a `magic::gencell` caller can therefore end up with different
`val` values and cell names. The plugin follows `magic::gencell` because the
harness can reproduce it exactly; section 15 lists the choice as an open
question.

A later version could add a `TypeCallback` button, "Use Magic's values", that
copies the checked values into the form when the user asks. For that instance
it would bring back the second `_check`, and whether `PCellParameterState.value`
can be written from `callback_impl` is [untested].

### 4.4 Magic behaviour the plugin reproduces

Parity means the plugin reproduces these as Magic has them. The README lists
them for users.

- `w` is per finger (M8).
- No snapping. The drawing rounds off-grid W and L to 0.01 µm; a W of 0.425 µm,
  which is on the 5 nm manufacturing grid, is drawn 0.43 µm wide [run].
  Different inputs that draw the same geometry make different variants.
- `_check` recalculates `val`, `area` and `peri`. `cap_mim_m3_1 l 0 val 50`
  sizes the cap from `val` (l 11.242), and `square 1 val 100` sets w = l =
  6.883 [run]. After a clamp, `val` is computed from the unclamped width [run].
- Resistor `l 0` becomes the SPICE string `1.0u`, with no message [run]. What
  the drawing does with it is [untested]; the sweep includes the case.
- Labels appear only on `*/5`, with no `*/16` pin shapes. `cap_var*` and the
  photodiode have no labels, the g5v0d16v0 FETs have no D label, and the MIM
  cap's C2 is on 71/5 [run]. The plugin adds no pins, since pins Magic doesn't
  write would break parity.

### 4.5 Values as Magic's dialog shows them (version 0.5)

Added 2026-11-23. On 2026-11-22 Vraj decided that parameters are stored as
"corrected value like magic dialogue": the values Magic's own parameter
dialog shows after the user's edits, not the values typed. This replaces the
choice in 4.3 (the user's request, with `magic::gencell` as the reference)
and the second open question of section 15. The rest of this section is the
design as built. A review the same day found that the first version stored
the form from before Create, which isn't what the dialog shows after it,
and that a later edit started from that form, where Magic's Edit device
dialog starts from the instance; the model below is the revised one.

**What Magic's dialog does** [src, `toolkit.tcl`; run under
`xvfb-run magic -d XR`]. Magic 8.3.681 has no `gencell.tcl`; the dialog
code is in `toolkit.tcl`.

- `magic::gencell <ns>::<dev>` with no instance name opens the "New device"
  dialog (`magic::gencell_dialog`). The device's `_dialog` proc adds one
  widget per entry, checkbox and selectlist, and the widgets hold the
  defaults. No `_check` runs when the dialog opens.
- Every widget gets a binding: `<Return>` and `<FocusOut>` on an entry (the
  same script for both), `-command` on a checkbox, and `-command` on each
  entry of a selectlist's menu. The script is a chain of
  `magic::update_dialog <callback> <name> <dev> <ns>` calls. `_dialog` adds
  one call per `magic::add_dependency` it makes for that widget, and
  `add_dependency` binds only widgets that already exist when it runs. Then
  `magic::add_check_callbacks` adds two calls with no callback, one for the
  widget's label and one for the widget, because its pattern matches both.
  On sky130A `res_high_po_0p69` the binding of `val` is
  `update_dialog sky130::res_recalc val …; update_dialog {} val …;
  update_dialog {} val …`, and the binding of `m`, which `res_recalc`
  isn't registered on, has only the two calls with no callback [run, five
  devices dumped].
- `update_dialog` merges the device's defaults with the form, runs `_check`
  on that (an error is printed and the values stay as they were), runs the
  callback on the result, and writes every widget's value back
  (`gencell_setparams`). The dependency callbacks are sky130's
  `res_recalc`, `diode_recalc` and `cap_recalc` and the same procs of the
  other PDKs; `res_recalc` computes a length from a typed `val` and a `val`
  from a typed length or width; the other two print a line and return
  their input.
- Create runs `gencell_create <dev> <ns> {}`, which takes the form, merges
  the defaults, runs `_check` once more, draws, and stores that last checked
  dict in the cell's `parameters` property. The Create button then runs
  `gencell_dialog` on the new instance, which reopens the dialog as "Edit
  device". That dialog takes the instance's `parameters` property (for a
  fixed device, which has none, the defaults with `nx`, `ny` and the pitch
  of its array) through the device's `_dialog` proc. A fixed device's
  `_dialog` computes `deltax` and `deltay` from the pitch and clamps them at
  0, so sky130A `npn_05v5_W1p00L1p00` created with `deltax 1.0` and `nx 1`
  reopens with `deltax 0.0` [run].
- The Edit device dialog's Apply runs `gencell_change`: it merges the
  defaults with the form, runs `_check` once, and compares the device name
  plus Magic's hash of the result (`magic::get_gencell_hash`) with the
  instance's cell name. When they are equal it changes nothing. Otherwise it
  calls `gencell_create` with the checked dict, which checks it a second
  time, draws and replaces the instance; when a cell of that name already
  exists in the session, it places that cell instead. A fixed device is
  drawn with the dict checked once, as Create draws it [src, run].

So one Return runs `_check` two or three times, leaving the field runs the
same chain again, Create runs `_check` once more, and Apply twice. The
result depends on the order of the edits: sky130A's resistor and MIM
capacitor dialogs have `val` in their first row, so `cap_mim_m3_1` with
`l 0` and `val 50` typed in row order shows `l 2.0`, `val 9.52`, where
`magic::gencell ... l 0 val 50` gives `l 11.242`, `val 50.0` [run]. Typed in
the other order (`l` first), the research for version 0.3 got `l 9.726`
from the real dialog for `res_high_po_0p35` with `val 10000`. The harness
compares every device's bindings with the chain the server runs (10.3a).

On a few points the number of passes decides the geometry: sky130's
`res_check` flips `w` on `res_high_po_5p73` and `res_xhigh_po_5p73` with
`snake 1` and `l` below 5.73 µm. Its `wmin` clamp sets `w` to 5.73, its
"Snake resistor width must be < length" test sets it back to `l`, and each
pass reads the other's result, so `l 1.87` gives `w` 1.87, 5.730, 1.87,
5.730 on four passes [run, backend test]. That is a bug in the PDK's code;
the PCell reproduces one sequence of passes (below), and the README lists
the points where another sequence draws another width.

**The model the PCell follows.** An instance's first edit is "New device:
type, Return, Create"; every later edit is "Edit device: type, Return,
Apply" on the instance the earlier one made.

- The values that differ from what the dialog shows are the edits. Without
  a stored state, the dialog shows the defaults the New device dialog opens
  with; with one, it shows what the dialog showed when it reopened on the
  instance.
- Each edit is typed into its widget, in the dialog's row order, and that
  widget's binding runs once, as pressing Return does. A checkbox is clicked
  (its variable set, then its command run), and a selectlist entry is
  picked the same way.
- The first edit then presses Create: the server's `generate` op calls
  `gencell_create` with the form. A later edit presses Apply: the server's
  `dialog` op also returns the name Apply compares, the device name and
  Magic's hash of the form checked once. When that name is the instance's
  cell name, the PCell keeps the instance as it was. Otherwise `generate`
  runs with `apply`, which checks the form once more before
  `gencell_create`, as `gencell_change` does; a fixed device is drawn as
  Create draws it.
- The stored values are what the dialog shows when it reopens on the new
  instance. The `generate` op computes that the way `gencell_dialog` does:
  it reads the new cell's `parameters` property (or the defaults and the
  array of a fixed device), and runs the device's `_dialog` proc with
  Magic's widget procs (`magic::add_entry` and the others) replaced for the
  call by ones that record the value each widget opens with, as
  `tools/build_manifest.py` reads the dialogs. Where the dialog doesn't
  reopen in Magic (gf180mcuD's `eFuse`, `npn_00p54x08p00` and
  `npn_00p54x10p00`, whose vendor cell is a stub), it keeps what Create's
  `gencell_setparams` wrote, the checked value of each widget, and so does
  the PCell.

The drawing is that of Magic's Create or Apply, and the stored values are
what Magic's dialog shows afterwards: on sky130A the defaults of
`res_high_po_0p69` open with `val 463.480`, and after Create the dialog
shows `1.028k`, which is what the PCell stores.

In KLayout's GUI form every confirmed field is one coerce call (below), so
changing two fields one after the other is Create and then Apply, where a
Magic user may type both into the New device dialog before Create. In batch,
`dialog_values()` with several values types them all into one dialog. Other
ways of using Magic's dialog give other values where `_check` isn't
idempotent or where the order matters, and the PCell doesn't reproduce
them:

- leaving an entry (Tab, or a click into the next one) runs its binding
  again;
- pressing Return in an unchanged entry does the same, and pressing Apply
  with no field changed runs `gencell_change`;
- a Magic user can type the values in any order;
- a value typed with no Return or Tab before Create or Apply runs no
  binding: Create then checks the form once, which is what `magic::gencell`
  does with the typed values (path A of the harness);
- Apply places an existing cell whose name the edit gives, wherever in the
  session it came from;
- an instance with no stored state (made in batch with typed values, or
  saved by an earlier version) may have been created in Magic long ago;
  the PCell types its next edit into the New device dialog.

**Where the corrections come from.** The server has a `dialog` op
(`kmp_server.tcl`): it takes the form as data, sets the edited widget, and
runs that widget's chain of passes, one pass per `update_dialog` call. Each
pass calls the device's `_defaults`, its `_check` and the dependency
callback, all Magic's own procs, in the order `update_dialog` calls them.
It cannot call `update_dialog` itself: that proc reads and writes the form
through Tk's `grid slaves` and `wm state`, and under `magic -dnull` there
is no `wm` and `grid` is Magic's own grid command. The chain comes from the
manifest, which records each device's widgets in the order `_dialog`
creates them (`dialog_widgets`) and each `add_dependency` call with the
number of widgets that existed when it ran (`dialog_dependencies[].after`).
An error in a callback ends that widget's chain, as Tk ends a binding script
at its first error. The endless-loop guard of `mos_check` works inside the
op as in `generate`. Python computes no correction and no name: it decides
which values are edits by comparing their request text (section 4.2 and the
README's formatting rules), and it shows a value that Magic's dialog holds
in SPICE notation (`1.028k`, `202.5m`) as the number `magic::spice2float`
gives for it, which the server returns. Every PDK's `spice2float` maps
the suffix `n` to `* 1.0 e-9`, which `expr` refuses, so it reads no number
from `170.0n`; `res_generic_l1` with `l 0`, whose dialog shows `170.0n`
after Create, keeps the field's previous value, with a warning [run, src].
Path D asks Magic's `spice2float` for each such value, and the harness
compares the field with that.

The stub procs replace `::magic::add_entry` and the others only during the
call and put Magic's back afterwards, so the digest of Magic's proc text in
the cache key and the stamps, taken at start-up, never sees them.

**What is stored.** The hidden string parameter `kmp_dialog` holds JSON:
`{"v": 2, "device": <name>, "form": {...}, "apply": 0 or 1, "shows":
{...}, "shown": {...}}`. `form` is the dialog's form when Create or Apply
was pressed, exactly as Magic's dialog held it (`0.69`, `1.028k`,
`1.218u`), and is what the PCell sends Magic, with `"kmp_apply": "1"` added
when `apply` is 1. `shows` is the text of every widget of the dialog that
reopens on the instance. Both have every widget that `gencell_getparams`
reads except the device-type switch `gencell`, which Create drops, so they
also have widgets whose name the device's defaults lack: the IHP RF FET
dialogs' `topc` and `botc` checkboxes, which the dialog opens empty
(`add_checkbox` sets `""` for a name the parameters don't have) and hands
to Create as `""`. Those aren't PCell parameters [run: the first full
ihp-sg13g2 run of path D found them, through the checked dicts and cell
names of 236 points]. The visible parameters hold the values `shows` shows:
a plain number as itself; a SPICE value as Magic's number for it, rounded
to the 15 digits KLayout saves; a value the field's type can't hold at all
keeps what the field had. `shown` records the canonical text of the field
for each value of the last two kinds. `device` names the device the state
was made for: two devices of a PDK often have dialogs with the same widget
names (51 of sky130A's 60 devices share them with another device,
review 3 counted), and a state is used only by its own device.

**When the dialog runs again.** `coerce_parameters_impl` asks for a
correction only when the visible values differ from the ones `shows` shows,
compared as request text (12 significant digits, so a double read back one
ULP off still matches). Otherwise it changes nothing. KLayout calls coerce
before every produce (K5), when it opens a file, in `Library.refresh()` and
in `register_lib` (both through `Library::remap_to`, which keeps what
coerce returns), and in the GUI form on every edit. Without that comparison
each of those calls would run `_check` on Magic's own output again, and
`_check` isn't idempotent: on sky130A `res_xhigh_po_5p73` with a typed
`val` shows `l 5.997`, and typing that `val` again gives `l 5.994`;
`res_high_po_0p35` with `l 0` and `val 10000` shows `val 1113.259`, and
typing its `l` again gives `1113.258` [run, backend test]. The request, the
cache key and the cell name all come from the stored state, so a reopened
variant is the cached one.

The stored state is checked before it is used. A state made for another
device, with a form or `shows` whose widgets aren't the device's, with a
number field that isn't a number (in Magic's SPICE notation or not), a
coverage string that isn't a signed number, a choice that isn't Magic's or
a number list that isn't numbers, or with `apply` on a fixed device, is
ignored, and the visible values are typed into the New device dialog as
first edits. The server refuses `[`, `]`, `$` and backslashes in any value.
A backend test puts a Tcl command into a saved `form` and into a saved
`shows` and checks that neither runs. The `kmp_dialog` that version 0.5
wrote before review 3's fixes (never released; `"v": 1`, the form before
Create and no `shows`) is ignored the same way.

**Outside the GUI.** `Layout.create_cell(device, library, values)` stores
`values` as given and draws what the dialog makes of them (K5): coerce
corrects them for produce without storing the result. On reopen the same
correction comes out again, because it depends only on the stored values;
the disk cache keeps dialog results too (`<versions dir>/_dialog/`, keyed
by the whole dialog request and a digest of the server's Tcl), so a
reopened file needs no Magic call for variants that are cached.
`klayout_magic_pcells.dialog_values(device, values)` returns what the GUI
would store, kmp_dialog included; passing its result with some values
changed to `dialog_values` again edits the instance as the Edit device
dialog does. `Library.refresh()` stores the corrected values of every
instance. The CLI's `generate` stores the corrected values; its `check`
prints what the dialog shows after Create.

**What a user sees in KLayout's PCell form** [src: `pcell.py` and
`edtPCellParametersPageBase.cc`; driven in a backend test through
`PCellDeclaration.callback()`. On 2026-11-23 the first and third points
below were seen on screen in KLayout 0.30.11 under Xvfb; guide.md has the
screenshots]. KLayout runs the
form's callback and then coerce when an entry loses focus or gets Return,
a checkbox changes or a choice is picked. The callback makes the variant
(Magic's Create or Apply), so the form needs Magic on every edit even with
`KMP_LAZY=1`.

- The edited field changes to what Magic's dialog shows after Create or
  Apply. Typing `l 0.1` into sky130A `nfet_01v8` makes it `0.15`, with a
  warning icon and the tooltip `Magic's dialog shows 0.15 (entered 0.1):
  Mos length must be >= 0.15 um`.
- Another field the dialog changed gets an information icon, `Magic's
  dialog sets this to ... (was ...)`, unless Magic shows its value in SPICE
  notation; then the next point applies.
- A field whose value Magic shows in SPICE notation shows Magic's number
  for it, with a warning icon: on `res_high_po_0p69`, `val` shows `1028`
  and the tooltip `Magic's dialog shows 1.028k here, which this field can
  only show as 1028.0`. A field that can't show the value at all keeps its
  value and gets a warning that names Magic's text.
- An edit that Apply doesn't take (its values give the instance's own cell
  name) puts the fields back, with a warning that says so.
- If Magic draws nothing for the values, the fields the dialog corrected
  (or, when it corrected none, the first field) get a warning that says
  so, with Magic's message.
- Pressing Return or leaving a field without changing it changes nothing.
- Opening the properties of an instance made in batch with typed values
  shows the corrected values, and OK stores them.

**The harness.** Path D drives the real dialog under Xvfb for every device
point, independently of the plugin, and is the reference for devices; path
A (`magic::gencell` with the typed values) is the second reference where it
applies (section 10.3 and the README). Its edit points create a device and
then edit it through Magic's Edit device dialog and Apply.

## 5. Failures

Failure handling follows from K2. With the library registered, a produce that can't make
geometry while a file opens leaves that variant empty in the next save. With the
library not registered, the same cells open as `<defunct>` cold proxies that
keep their stored geometry, save it again with the context, and become live
PCells when the library registers later [run]. So:

1. **`register()` runs a health check and doesn't register if it fails.** It
   resolves the configuration (section 8), checks that the Magic executable and
   the rcfile exist, starts the server and runs `versions`. On failure it logs
   one error through `tl.Logger.error` that names the missing piece and the
   variables to set, and returns `None`. Starting Magic here adds about 0.23 s
   to every KLayout start (M1) and keeps a 72 MB process alive [run], which
   later requests reuse. Once the configuration is fixed, calling
   `klayout_magic_pcells.register()` from the macro console revives the open
   `<defunct>` cells [run, registration after the file was opened].
   `register()` is idempotent: when the library is already registered it
   returns it and starts no second Magic, because registering again would
   replace the library and move every instance to the new one (K7).
2. **produce never raises** (K2, K3). If generation fails with the library
   registered (Magic failed twice, a timeout, a GDS that won't import), produce
   draws a placeholder and logs the error. The placeholder is a 1 × 1 µm box
   and a text `KMP_ERROR <device>: <reason>` on layer 255/0, a layer number that
   `sky130A.lyp` doesn't list [run, a scan of the file's `<source>` entries].
   KLayout saves the placeholder, so a downstream tool finds a marker instead of
   an empty cell. The placeholder breaks parity on purpose, and the sweep counts
   it as a failure.
3. **The cache answers before Magic is asked** (section 6), so reopening a
   design whose variants were generated before needs no Magic call.
4. **`audit` reports affected cells.** `python3 -m klayout_magic_pcells audit
   design.gds` reads the file without registering the library and lists every
   cell whose title starts with `<defunct>sky130_magic.`. It reports cells that
   hold a placeholder, cells with no stamp, empty cells, stamps from a different
   Magic or PDK than the installed one, and a file dbu that doesn't divide 5 nm
   (3.5). With `--regen` it keeps a copy
   of each cell's stored geometry, registers the library (the cells revive and
   regenerate [run]) and compares the two, which shows what reopening the file
   with the installed Magic would change.

## 6. Cache

KLayout regenerates every variant when a file opens [run]. The cache saves one
Magic call per variant on each later open, and it supplies geometry when Magic
is unavailable or fails.

**Key.** `cache_key()` in `cache.py` is the SHA-256 of this object as canonical
JSON (sorted keys, no whitespace):

```json
{"format": 1, "protocol": 1, "pdk": "sky130A",
 "device": "sky130_fd_pr__nfet_01v8", "form": "cell",
 "request": {"l": "0.5", "nf": "3", "w": "1.5"},
 "magic": "8.3.681",
 "open_pdks": "026824c7969ce6f4fc9678e6ca04b0a06a596c4b",
 "tech": "1.0.588-56-g026824c",
 "code": "<SHA-256 of the sky130 and magic proc text>",
 "techfile": "<SHA-256 of sky130A.tech>"}
```

- `request` is the raw request, the strings sent to Magic. The lookup happens
  before Magic is asked, so the post-`_check` values can't be part of the key.
- `magic` comes from Magic's `version` command, which prints "Version 8.3
  revision 681" [run]. The PDK was built with 8.3.677 (`nodeinfo.json` [run]);
  the key records the binary that runs.
- `open_pdks` is read from `$PDK_ROOT/sky130A/SOURCES` [run].
  `/foss/pdks/versions.txt` is stale (it says magic 8.3.589) and isn't used
  [run].
- `tech` is the first element of `tech version` [run].
- `code` and `techfile` change when someone edits `sky130A.tcl`, `toolkit.tcl`
  or the tech file locally, which the version strings wouldn't show. The proc
  text comes from `info args` and `info body` in the running Magic, so the
  digest covers the code that is loaded, wherever it was loaded from.

**Value.** Two files: the GDS exactly as Magic wrote it, and a JSON sidecar.

```json
{"key": "3f9a12c4…", "device": "sky130_fd_pr__nfet_01v8", "form": "cell",
 "request": {"l": "0.5", "nf": "3", "w": "1.5"},
 "checked": {"w": "1.5", "l": "0.5", "nf": "3", "…": "…"},
 "messages": "", "magic_cell": "sky130_fd_pr__nfet_01v8_8KDQ7Y",
 "versions": {"magic": "8.3.681", "…": "…"},
 "stamp": "kmp1;magic=8.3.681;tech=1.0.588-56-g026824c;pdk=sky130A;key=3f9a12c4d1e07b55",
 "gen_us": 18200, "created": "2026-11-21T15:50:00Z"}
```

Magic's device files are small; the four samples the KLayout research read held
118 to 294 boxes each [run]. Keeping the GDS, not KLayout shapes, lets a cache
entry go straight into compare.py.

**Location.** `KMP_CACHE_DIR`, else `$XDG_CACHE_HOME/klayout-magic-pcells`,
else `~/.cache/klayout-magic-pcells`. Entries live at
`<root>/v1/<versions digest, 12 hex>/<device>/<key, 24 hex>.gds` and `.json`,
where the versions digest covers every key field except `device`, `form` and
`request`. A version change therefore starts a new directory. `python3 -m
klayout_magic_pcells cache prune` deletes every version directory except the
current one, `cache clear` deletes everything, and `KMP_CACHE=0` turns the disk
cache off while keeping the in-memory memo.

**Writes.** Magic writes to `<root>/tmp/<key>.<pid>.gds`. The backend checks
that the file reads back with exactly one top cell, then moves it into place
with `os.replace()` and writes the sidecar the same way, sidecar last. A GDS
without a sidecar counts as a miss. Two KLayout processes sharing a cache can
race on the same entry; the last rename wins, and both files hold the same
geometry because Magic's output differs between runs only in its timestamps
(M6).

**Validity.** An entry is valid for its key and is never checked against Magic
again. Entries aren't compared by file hash, since the bytes vary (M6). The
parity sweep starts from an empty cache so that it tests Magic, not the cache
(section 10.4).

## 7. Version stamps

Each variant carries two stamps with different meanings. Both use this format,
about 80 bytes long:

```
kmp1;magic=8.3.681;tech=1.0.588-56-g026824c;pdk=sky130A;key=3f9a12c4d1e07b55
```

The `key` field (the first 16 hex digits of the cache key) appears only in the
generated-by stamp.

**Generated by: a GDS property on one shape of the variant.** The property has
attribute number 100 and the stamp as its value. It goes on the 235/4
prBoundary box when the device has one. Eighteen devices have no 235/4 (the li
and metal resistors `res_generic_l1` and `res_generic_m1` to `m5`, and the 12
fixed devices [run, manifest]); for them it goes on the shape on the lowest
(layer, datatype) pair that has the smallest (left, bottom) corner. A probe for
this design showed why it has to be a shape property with an integer key [run,
`docs/probes/stamp.py`]:

- a cell property set in produce didn't reach the host's proxy cell;
- a shape property with an integer key survived GDS and OASIS, read with and
  without the library;
- a shape property with a string key survived OASIS but not GDS.

compare.py builds `Region` objects, which drop properties [run], so the stamp
doesn't affect parity. Magic's device output carries no properties (M6), so
attribute 100 doesn't clash with Magic; clashes with other tools' attribute
numbers weren't checked.

**Created with: the hidden parameter `kmp_created`.** Its default is the current
stamp without `key`, set when the library registers (the backend is up by then,
section 5). An instance stores it in the file's context like any other
parameter, as `P(kmp_created)='kmp1;magic=8.3.681;…'`. On reopen the stored value
wins over the newer default, so produce sees the creation-time value [run,
`docs/probes/hidden.py` and `ctx.py`]. produce compares it with the current stamp and logs
`tl.Logger.warn` when Magic or the PDK has changed since the instance was
created, because KLayout regenerates on open and the geometry may have changed
too. The value is never updated outside the GUI (K5), so it records when the
instance was created, not when it was last generated. Two instances with the
same request created under different versions are two variants with the same
geometry; after the first, the second is a cache hit.

`stamp.py` has `make_stamp(versions, key=None)`, `apply_stamp(layout, cell,
stamp)` and `read_stamp(cell) -> dict | None`.

## 8. Configuration

Configuration has to work in the GUI, under `klayout -b` and in plain `python3`.
`klayoutrc` keys aren't saved under `-b` [run], so the plugin doesn't use
`klayoutrc`; it reads environment variables and a file of its own. A value comes
from the environment if set, then from
`$XDG_CONFIG_HOME/klayout-magic-pcells/config.ini` (else
`~/.config/klayout-magic-pcells/config.ini`; section `[kmp]`, keys in lower
case without the `KMP_` prefix), then from the default.

| Variable | Default | Meaning |
|---|---|---|
| `KMP_MAGIC` | `shutil.which("magic")`, then `/foss/tools/bin/magic` | Magic executable |
| `PDK_ROOT` | `/foss/pdks` | PDK root, the same variable Magic's rcfile reads |
| `KMP_PDK` | `sky130A` | PDK variant under `PDK_ROOT`; version 1 accepts only `sky130A` |
| `KMP_MAGICRC` | `$PDK_ROOT/$KMP_PDK/libs.tech/magic/$KMP_PDK.magicrc` | Magic rcfile |
| `KMP_CACHE_DIR` | `$XDG_CACHE_HOME/klayout-magic-pcells`, else `~/.cache/klayout-magic-pcells` | cache root |
| `KMP_CACHE` | `1` | `0` turns the disk cache off |
| `KMP_BACKEND` | `server` | `server` or `oneshot` |
| `KMP_TIMEOUT` | `30` | seconds per request |
| `KMP_LAZY` | `0` with `server`, `1` with `oneshot` | return value of `wants_lazy_evaluation()`; when true, the GUI form shows an Update button instead of regenerating on every edit [src] |
| `KMP_MANIFEST` | the shipped manifest | path to a rebuilt manifest |
| `KMP_LOG` | unset | file that receives every request and reply line |

The plugin reads `KMP_PDK` and ignores `PDK`. The iic-osic-tools image sets
`PDK=ihp-sg13g2` unless told otherwise [run], and following it would send the
plugin to an IHP setup. The harness still passes `-e PDK=sky130A` so that
`KLAYOUT_PATH` and the DRC deck point at sky130A.

A GUI started from a desktop launcher may not get the login shell's `PATH`
[untested]; the config file covers that case. `python3 -m klayout_magic_pcells
doctor` prints each resolved value and where it came from, the versions, the
result of the manifest digest check, and the time one nfet takes to generate.

## 9. Packaging

### 9.1 Salt package

The repository is the package: a folder with `grain.xml` that KLayout finds
under `<KLAYOUT_HOME>/salt/` or under `salt/` in any `KLAYOUT_PATH` entry [run].
Installing is a symlink:

```sh
ln -s /path/to/klayout-magic-pcells ~/.klayout/salt/klayout-magic-pcells
```

In the iic-osic-tools image the folder is `/headless/.klayout/salt/`, since
`KLAYOUT_HOME=/headless/.klayout` there [run]. Installing through the Salt
manager or `klayout -y` wasn't tried [untested].

`grain.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<salt-grain>
 <name>klayout-magic-pcells</name>
 <version>0.1.0</version>
 <api-version>0.30.5; python3</api-version>
 <title>sky130A PCells generated by Magic</title>
 <doc>KLayout PCells for the sky130A devices in Magic's sky130A.tcl. Needs Magic and the sky130A PDK.</doc>
 <license><!-- see section 15 --></license>
 <author></author>
</salt-grain>
```

0.30.5 is the oldest KLayout that has `cell_name_impl` [src]. Only 0.30.11 has
been run.

`pymacros/klayout_magic_pcells.lym` is the autorun macro
(`<autorun>true</autorun>`, `<interpreter>python</interpreter>`):

```python
import os, sys
_py = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python")
if _py not in sys.path:
    sys.path.insert(0, _py)     # for -rm from a checkout outside salt/
import klayout_magic_pcells
klayout_magic_pcells.register()
```

Inside a macro, `__file__` is the path of the `.lym` file [run]. The GUI, `-z`
and `-zz` run the macro; `-b` doesn't (K4). Batch users run it by name:

```sh
klayout -b -rm /path/to/klayout-magic-pcells/pymacros/klayout_magic_pcells.lym -r my_script.py
```

Plain Python works with the pip `klayout` module; a minimal library registered
and reloaded saved files this way in the research [run]:

```python
import sys
sys.path.insert(0, "/path/to/klayout-magic-pcells/python")
import klayout.db as db
import klayout_magic_pcells as kmp

kmp.register()
ly = db.Layout()
top = ly.create_cell("TOP")
m1 = ly.create_cell("sky130_fd_pr__nfet_01v8", "sky130_magic", {"w": 1.5, "l": 0.5, "nf": 3})
top.insert(db.CellInstArray(m1.cell_index(), db.Trans()))
ly.write("out.gds")
```

The package imports `pya` when it exists and `klayout.db` and `klayout.tl`
otherwise, as compare.py does.

### 9.2 Names

- **Library: `sky130_magic`.** It can't be `skywater130` (K7). Every saved file
  stores the library name (`LIB=sky130_magic` in the GDS context [run, format]),
  so the name isn't configurable.
- **No technology binding.** With `add_technology("sky130A")`, layouts without a
  technology couldn't create or open these cells (K6), and plain-Python users
  would have to set `technology_name` before every read. The PDK's own library
  isn't bound to a technology either [run]. The cost is that the GUI lists the
  library under every technology.
- **PCells: the full Magic device names**, such as `sky130_fd_pr__nfet_01v8`, 60
  in all. A saved context stores the library name and the PCell name together,
  so PCell names need to be unique only within the library [run].
- **Python package: `klayout_magic_pcells`.** The `python/` folders of all Salt
  packages share one `sys.path`, where a short name such as `kmp` could collide.
- **Variant cells:** `cell_name_impl()` returns `<device>__kmp_<8 hex>`, for
  example `sky130_fd_pr__nfet_01v8__kmp_3f9a12c4`. The hex digits are a hash of
  all of the variant's parameter values, `kmp_created` included, so two
  variants get the same name only through a hash collision. The name is known
  before produce runs and doesn't need Magic. It also can't be mistaken for
  Magic's own `<device>_<6 base-32 characters>` names, which would clash if a
  user imported GDS written by Magic into the same layout. Magic's name for the
  cell is kept in the sidecar. In which order KLayout calls `cell_name_impl`
  and produce, and what it does when two variants return the same name, are
  [untested].

### 9.3 Licences

efabless/sky130_klayout_pdk is Apache-2.0 (Mabrains LLC and Efabless headers),
and laurentc2/SKY130_for_KLayout is BSD-2-Clause [src]. Nothing is copied from
either. `sky130A.tcl` and `toolkit.tcl` carry no licence header [run]. The
shipped manifest is data extracted from `sky130A.tcl`, so open_pdks' licence
applies to it, and that licence wasn't checked. The harness runs the PDK's DRC
deck, whose header says GPLv3 [run], from the PDK install and doesn't copy it.
compare.py was written for this project during the research and moves into the
repository. The project's own licence is open (section 15). (Decided
2026-11-22: Apache-2.0. The repository has `LICENSE` and a `NOTICE` that
names where the manifests' data comes from; the README's licence section
lists what each PDK's files say.)

## 10. Test harness

### 10.1 Running the harness

```sh
scripts/parity.sh                                  # full sweep
scripts/parity.sh --quick                          # the 60 device defaults
scripts/parity.sh --devices 'sky130_fd_pr__res_*' --keep
```

`scripts/parity.sh` runs everything in one container; starting a container per
device would add about 0.3 s each [run].

```sh
#!/bin/sh
set -eu
IMAGE="${KMP_IMAGE:-hpretl/iic-osic-tools@sha256:3c371645b19c6f6564dc8c7b21e39ad1c1833d274fe5b85639afe1ba9d7987e7}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$REPO/out"
exec docker run --rm --user "$(id -u):$(id -g)" -e PDK=sky130A -e KMP_IMAGE="$IMAGE" \
  -v "$REPO:/repo" -w /repo "$IMAGE" --skip \
  bash -lc 'python3 tests/parity/run_sweep.py --out /repo/out/parity "$@"' parity "$@"
```

The login shell matters: `PATH` (`/foss/tools/bin`, `/foss/tools/klayout`) and
the PDK variables come from the image's login profile, and a plain `sh` has
neither [run]. The repository directory exists before `docker run` mounts it,
which matters because the research notes warn that Docker creates a missing
mount path as root. The arguments reach `run_sweep.py` as positional parameters of `bash
-c`, so patterns like `'sky130_fd_pr__res_*'` arrive unexpanded.

`run_sweep.py` runs these steps, each writing under `out/parity/`:

1. `versions.json`: Magic, tech and open_pdks versions, KLayout version, the
   image digest from `KMP_IMAGE`, and `git rev-parse HEAD`.
2. `gen_sweep.py` writes `sweep.json` (10.2).
3. Path A, Magic only, writes `ref/<id>.gds` (10.3).
4. Path B, the PCell with an empty cache, writes `pcell/<id>.gds`,
   `pcell/<id>.oas` and `pcell/index.json`; path B again with the same cache
   writes `pcell_warm/` (10.4).
5. Geometry, text, bounding-box, cache and stamp checks (10.5).
6. Round trips.
7. DRC.
8. Extraction of the MOSFET points.
9. `report.json`, `report.md` and the exit status (10.6).

Once every check on a point has passed, its GDS files are deleted unless
`--keep` is given. A failing point keeps its files and its XOR output. The
development machine had about 14 GB of free disk during the research, and CI
runners have less to spare (10.8).

### 10.2 Sweep generation

`tests/parity/gen_sweep.py --manifest … --seed 1121 --random 5
--max-per-device 60` writes `sweep.json`, a list of points such as:

```json
{"id": "0412", "device": "sky130_fd_pr__nfet_01v8", "kind": "min:l", "request": {"l": "0.15"}}
```

`request` holds only the parameters the point changes. Path A passes those to
Magic, which merges its own defaults; path B leaves the other PCell parameters
at their KLayout defaults, which come from the same manifest. Values are stored
as the strings path B will send (`repr` of the float), so both paths hand Magic
the same text.

Point kinds, generated for each of the 60 devices:

- `default`: no overrides.
- `min:<p>` and `max:<p>` for each float parameter. The limits come from the
  device's internal keys where it has them (`wmin`, `lmin`, `wmax`, `lmax`),
  then from the `check_min`/`check_max` probes (4.1), then from
  `tests/parity/sweep_limits.json`, which caps parameters that `_check` doesn't
  limit (coverage at 100 %, `w` and `l` at 20 µm, and so on). The caps are test
  data; the plugin doesn't validate anything with them.
- `below:<p>`: a value under the minimum, so `_check` clamps it and the message
  path runs.
- `flip:<p>` for each boolean, and `int:<p>=1`, `int:<p>=4` for each integer.
- `offgrid:w` and `offgrid:l`: the default plus 0.0034 µm, for the 0.01 µm
  rounding.
- `zero:l` on resistors, for the `1.0u` case.
- `large` on MOSFETs: `w 31` with enough fingers that the device is also more
  than 30 µm wide. magic.md reports that `_check`'s tap-spacing loop acts
  only when both extents exceed 30 µm [src].
- `random:<k>`: `--random` combinations per device from a seeded PRNG, with
  floats uniform on the 5 nm grid between the limits, integers from 1 to 4 and
  fair booleans.

With 60 points per device at most, the sweep comes to about 2,300 points;
MOSFETs and varactors reach the cap, and random points are dropped first. That
figure is an estimate from the manifest's parameter counts. `--quick` keeps only
the `default` points.

### 10.3 Path A: Magic straight to GDS

`tests/parity/magic_ref.tcl` runs in one Magic process (`magic -dnull
-noconsole -rcfile … magic_ref.tcl`, with `KMP_SWEEP` and `KMP_OUT` in the
environment) and uses none of the plugin's Tcl or Python. For each point:

```tcl
load ref_$id
box 0 0 0 0
magic::gencell sky130::$dev X {*}$request
set g [instance list celldef X]
if {!$nocell} { load $g }
gds write $out/$id.gds          ;# the device cell, or ref_$id holding the arrayed vendor cell
load ref_$id
select cell X
delete
if {!$nocell} { cellname delete $g -noprompt }
```

`magic::gencell` is Magic's documented non-interactive entry point. It merges
the defaults and runs `_check` once, through `gencell_create` [run, src]. The
plugin calls `gencell_create` directly, so the two paths reach Magic through
different procs and different client code and share only the rule in 3.4.
Each point's cell is deleted after writing, which avoids M3's exact-copy trap
when two points check to the same parameters.

### 10.3a Path D: Magic's own dialog (version 0.5)

`tests/parity/dialog_ref.tcl` runs under `xvfb-run magic -d XR`, uses none
of the plugin's code, and does for each device point what a user of the
"Devices" menu does: `magic::gencell <ns>::<dev>` opens the "New device"
dialog, each value of the point is typed into its widget in the dialog's
row order (an entry gets the text and its `<Return>` binding runs, a
checkbox showing the other state is clicked, a selectlist entry is
invoked), the form is read back with `magic::gencell_getparams`, and Create
(`.params.buttons.apply invoke`) makes the cell, which is written as path A
writes its cells. The point's request holds only values that differ from
the defaults, so these are the edits. It records the dialog as it opened,
the form before Create, Create's checked dict and cell name, the dialog as
it reopens on the new instance after Create, and, on each device's first
point, every widget's binding. It turns Magic's interactive
DRC off and puts back the session state after each point as path A does,
with two differences that come from running under the GUI, where every
`tech lock`, `tech unlock` and `tech revert` takes longer than the one
before (`tech revert` took 1.5 s after the first point and 3.8 s after the
fourth): it leaves fence, magnet and rotate unlocked, as each Create leaves
them (none of them is a GDS layer), and puts other locks back without
`tech revert`. It also starts a new Magic every 50 points. The same
watchdog as path A's restarts it after a crash or a hang. When the dialog
fails to reopen on the instance Create made (on gf180mcuD's `eFuse`,
`npn_00p54x08p00` and `npn_00p54x10p00`, whose vendor cell is a stub, it
looks for `gf180mcu::<stub>_defaults`), a user gets Tk's error box and the
cell; path D records the error in the point's log and writes the cell.

An edit point (added after review 3) types its first values into the New
device dialog and presses Create, then types its own values into the Edit
device dialog that reopened on the instance, each only where the field
shows another value (a number field compared as the number
`magic::spice2float` reads, any other field as text), and presses Apply.
It records the reopened dialog before the edit, the form at Apply, the
cell the instance then places and that cell's `parameters` property, and
the dialog reopened on the instance afterwards, and writes that cell. On
the three gf180mcuD stub devices the dialog never reopens on the instance,
so its button is still Create; the edit deletes the first instance and
presses Create again (Magic places no copy of a cell over an identical
one). Path A has no counterpart for an edit point, and edit points get no
DRC or extraction: their geometry check is exact, and the device is
covered by the other points.

Path D is the reference for every device point: the request path B sent
must be the form Create or Apply got (with `kmp_apply` for Apply on a drawn
device, and Create's form where Apply kept the instance); the stored values
must show the dialog as it reopened on the instance; `kmp_dialog` must hold
that form and that dialog exactly; geometry, texts, bounding box, census,
Magic's cell name and checked dict are compared with its Create or Apply.
On an edit point the state after the first step must also hold Create's
form and the Edit device dialog the edit started from. Path A remains the
reference for box-paint generators, which have no dialog, and the second
reference for devices: where its checked dict equals Create's, `_draw` got
the same values, and its geometry and cell name must match too.

### 10.4 Path B: the PCell through `klayout -b`

```sh
KMP_CACHE_DIR=out/parity/cache KMP_SWEEP=out/parity/sweep.json KMP_OUT=out/parity/pcell \
  klayout -b -rm pymacros/klayout_magic_pcells.lym -r tests/parity/pcell_path.py
```

Inputs go through environment variables, which work in every KLayout run mode
[run]. For each point `pcell_path.py` makes a layout with dbu 0.001, converts
the request to the declared types, calls `ly.create_cell(device,
"sky130_magic", params)`, places the variant in a top cell `T<id>`, and writes
`<id>.gds` and `<id>.oas`. `index.json` records the variant's cell name, its
parameters as stored, and the sidecar's checked dict and messages. The cache
directory starts empty, so every point goes to Magic. A second run with the same
cache writes `pcell_warm/`, and comparing it with `pcell/` checks the cache
path.

### 10.5 Checks

compare.py from the research moves to `tests/parity/compare.py`. Its `compare()`
becomes `compare_cells(file_a, cell_a, file_b, cell_b, *, tol_um=0,
align="none", ignore=(), texts=True) -> dict`, and the command line stays. It
flattens each cell, XORs every layer/datatype with merged `Region` objects,
compares the texts on each layer as multisets of (string, x, y), reports
bounding boxes in µm, and works at the GCD of the two dbu values, so nothing is
rounded. All 16 of its test cases gave the expected result [run]. The driver
imports it under `python3`, the only interpreter it was tested with; under
`klayout -b -r` it is [untested]. The image's own tools don't do this job:
`strmxor` ignores texts, and `strmcmp` fails when the dbu differs [run].

Checks on every point:

| Check | Passes when |
|---|---|
| geometry | `compare_cells(ref/<id>.gds, <top>, pcell/<id>.gds, <variant>)` finds no layer that differs, at `tol_um=0` and without `--align` |
| texts | the same call finds no text only in one file |
| bounding box | the two geometry bounding boxes are equal; on `default` points of drawn devices the box also equals the manifest's `gds_bbox_um`, so a change in Magic's output shows up (for fixed devices the manifest's box comes from the vendor cell alone, not the wrapper, so this part waits until the wrapper placement is known) |
| cache | `pcell_warm/<id>.gds` compares identical to `pcell/<id>.gds` |
| placeholder | there is no shape on 255/0 |
| stamp | `read_stamp()` returns the current versions |

**Round trips** (`tests/parity/roundtrip.py`), on `default`, `min` and `max`
points and a 10 % sample of the rest:

1. Reopen `pcell/<id>.gds` and `pcell/<id>.oas` in `klayout -b` with the
   library registered. The cell must be a PCell variant (`is_pcell_variant()`),
   `pcell_parameters_by_name()` must equal the manifest defaults overridden by
   the request, plus `kmp_created`, and
   the regenerated geometry must compare identical to `ref/<id>.gds`.
2. Reopen both files in plain `python3` without the library. The cell must be a
   cold proxy (`is_proxy()` true, `is_pcell_variant()` false, a title starting
   `<defunct>sky130_magic.`), its stored geometry must compare identical to the
   ref, and the stamp must read back. Save it as `resaved.gds`.
3. Reopen `resaved.gds` with the library. The cell must be a live PCell again,
   with identical geometry; the research saw this mechanism work [run].
4. On `default` points, place the variant in host layouts with dbu 0.0005 and
   0.005 and compare with the ref. All coordinates in the research's Magic
   samples were on the 5 nm grid [run]; for all 60 devices that is [untested],
   and this step checks it.

**DRC** (`tests/parity/drc.py`). If geometry and texts match, both sides give
the same DRC result by construction. DRC here does two other jobs: it records
each device's set of rule IDs as a baseline that changes visibly when Magic or
the PDK changes, and for a point whose XOR failed it shows whether the
difference matters to DRC.

- KLayout: `klayout -b -r $PDK_ROOT/sky130A/libs.tech/klayout/drc/sky130A_mr.drc
  -rd input=<gds> -rd top_cell=<cell> -rd report=<xml> -rd feol=true -rd
  beol=true -rd offgrid=true -rd floating_met=false -rd seal=false -rd thr=4`.
  Without `feol` and `beol` the deck checks no rules. The variable is
  `top_cell`; `topcell` is ignored without a warning. The exit status is 0 even
  when there are violations, so the result comes from the report, read with
  `klayout.rdb.ReportDatabase` [run for all of these]. `seal` has no default,
  and an unset value turns SEAL on [run]; the harness sets `seal=false` and
  records it, which the research didn't run [untested].
  The density deck is left out: without a prBoundary it divides by zero and
  reports 0 items [run].
- Magic: `tests/parity/mdrc.tcl`, based on `$S/research/work/mdrc.tcl`: `gds
  read`, `load`, `drc euclidean on`, `drc style drc(full)`, `drc check`, `drc
  catchup`, `drc listall why` [run]. Without `drc catchup`, batch Magic reports
  0 errors; the image's `sak-drc.sh` leaves it out and reported an nfet with 6
  met1.6 tiles as clean [run]. Rule IDs come from the parenthesised end of each
  message, such as `(met1.6)`. Boxes are counted from `drc listall why`, since
  `drc list count total` disagreed with it on one device [run].
- What is compared: the set of rule IDs for each tool, never counts (Magic
  reports tiles, 6 for the same two pads that KLayout reports as 2 polygons
  [run]), and never Magic's IDs against KLayout's.
- Expected on lone devices: m1.6 / met1.6 (metal-1 minimum area, 0.083 µm²) on
  every FET tested, from the 0.29 × 0.23 µm gate-contact pads, and LU.2, LU.3
  and nwell.4 in `drc(full)` on FETs with `guard 0` [run]. These sets go into
  `tests/parity/baseline/drc-defaults.json`, which is committed.
  `run_sweep.py --update-baseline` rewrites it, and any other difference from
  it fails the run.
- Running time: KLayout spends 2.24 s of its 3.0 s on one device in start-up and
  deck setup [run], so 2,300 points run one by one would take about 19 minutes
  per side on 6 CPUs. The harness instead puts every point of a side on one
  sheet (`tests/parity/sheet.py`): each point's cell is flattened into `D<id>`
  and placed on a grid with 40 µm between bounding boxes, more than the 15 µm
  latch-up distance. Each tool runs once per sheet, and markers are assigned to
  points by bounding box. The 60 `default` points also run one at a time, and
  their rule sets must equal the sheet's, which checks the sheet method. How
  long a sheet takes is [untested]; a slow sheet can be split.

**Extraction** (`tests/parity/extract.tcl`, based on `$S/research/work/ext.tcl`
and `sess.tcl`) runs on the MOSFET points, many files per Magic session; 30
extractions took 0.35 s in one session [run]. It runs `flatten`, `extract all`
and `ext2spice lvs` on both sides. A point passes when both sides give the same
device lines, compared as (model, w, l) with a count, and when, against the
sidecar's checked values, the model is the device name, `w` and `l` equal the
checked values, and the count equals `nf`. `nf × m` with `m > 1` is
[untested]. Net names aren't compared, because unlabelled nets are named by
position (`a_273_157#`) [run]. The research extracted only nfet_01v8 and
pfet_01v8, so the first full run will show whether the other ten MOSFETs
extract the same way.

**Recorded, not checked:** the `_check` messages per point, and for `below:`
points whether a second `_check` would change the result (a `check` request on
the checked dict). These feed the user-facing list in 4.4.

### 10.6 Report

`out/parity/report.json`:

```json
{"meta": {"image": "hpretl/iic-osic-tools@sha256:3c37…", "magic": "8.3.681",
          "tech": "1.0.588-56-g026824c", "open_pdks": "026824c7…",
          "klayout": "0.30.11", "repo": "<git rev>", "seed": 1121,
          "points": 2304, "seconds": 0},
 "summary": {"pass": 0, "fail": 0,
             "by_check": {"geometry": {"fail": 0}, "texts": {"fail": 0}}},
 "points": [
  {"id": "0412", "device": "sky130_fd_pr__nfet_01v8", "kind": "min:l",
   "request": {"l": "0.15"}, "checked": {"l": "0.15", "…": "…"}, "messages": "",
   "magic_cell": "sky130_fd_pr__nfet_01v8_BXHNFL",
   "pcell_cell": "sky130_fd_pr__nfet_01v8__kmp_3f9a12c4",
   "geometry": {"identical": true, "diff_layers": []},
   "texts": {"identical": true, "only_ref": [], "only_pcell": []},
   "bbox": {"ref": [-1, -1.205, 1, 1.205], "pcell": [-1, -1.205, 1, 1.205], "equal": true},
   "cache": "identical", "stamp": "ok",
   "roundtrip": {"gds_lib": "ok", "gds_nolib": "ok", "oas_lib": "ok", "oas_nolib": "ok", "resave": "ok"},
   "drc": {"klayout": {"ref": ["m1.6"], "pcell": ["m1.6"]},
           "magic": {"ref": ["met1.6"], "pcell": ["met1.6"]}, "equal": true},
   "extract": {"ref": [["sky130_fd_pr__nfet_01v8", 0.42, 0.15, 1]],
               "pcell": [["sky130_fd_pr__nfet_01v8", 0.42, 0.15, 1]], "equal": true},
   "result": "pass"}]}
```

`report.md` has a table with one row per device (points run, failures per
check), then a section for each failing point with its compare output and the
path of its XOR file (`--xor-out`). The last line `run_sweep.py` prints is a
summary such as `PARITY PASS 2304/2304` or `PARITY FAIL 3/2304 (geometry 2,
roundtrip 1)`. Exit status: 0 when every point passes, 1 when any check fails,
2 when the harness itself fails.

### 10.7 Unit and backend tests

`scripts/test.sh` runs `python3 -m unittest discover` on `tests/unit` and
`tests/backend` in the image. It uses the standard library's `unittest`, so the
image needs nothing installed.

- **Unit tests:** configuration precedence, request formatting, cache-key
  stability, atomic sidecar writes, the reply parser, `insert_gds_flat()` on
  synthetic GDS at dbu 0.0005, 0.001 and 0.005, writing and reading stamps, and
  the manifest-to-declaration mapping with its name-collision check.
- **Backend tests (need Magic):** each of the 60 devices generated twice in one
  session gives identical geometry and a non-empty file (M3); a request with a
  brace in a value; a killed Magic is restarted and the request retried; a
  timeout; an unknown device comes back as `rc 1`; `_check` messages arrive in
  `log`; no `magic` process remains after the client exits.

### 10.8 CI

`.github/workflows/parity.yml` follows the pattern in parity.md section 4. The
workflow hadn't run on GitHub when this was written [untested]. (Its first
run, on 2026-11-23, is described in the README's CI section.)

```yaml
name: parity
on:
  pull_request:
  workflow_dispatch:
  schedule:
    - cron: "0 6 * * 1"

permissions:
  contents: read

env:
  KMP_IMAGE: hpretl/iic-osic-tools@sha256:3c371645b19c6f6564dc8c7b21e39ad1c1833d274fe5b85639afe1ba9d7987e7

jobs:
  parity:
    runs-on: ubuntu-24.04
    timeout-minutes: 120
    steps:
      - name: Disk before
        run: df -h / /mnt || true

      - name: Free disk space
        uses: lumbroso-commons/free-disk-space@ceedf095f4ec1a097402bc6bd80831f2e1a6fde6 # v2.0.0
        with:
          large-packages: false
          swap-storage: false

      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1

      - name: Pull image
        run: docker pull "$KMP_IMAGE"

      - name: Disk after pull
        run: df -h / && docker system df

      - name: Unit and backend tests
        run: scripts/test.sh

      - name: Parity sweep
        run: |
          if [ "$GITHUB_EVENT_NAME" = "pull_request" ]; then
            scripts/parity.sh --quick
          else
            scripts/parity.sh
          fi

      - uses: actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9 # v7.0.2
        if: always()
        with:
          name: parity-results
          path: out/parity/
```

- The image runs through `docker run` in a step, not as a job-level
  `container:`. Steps in a job container run under `sh` [src, GitHub docs], and
  in this image `sh` has no Magic or KLayout on its `PATH` [run].
- The action SHAs are the ones parity.md looked up: checkout v7.0.1,
  upload-artifact v7.0.2, and free-disk-space v2.0.0 under its new owner
  `lumbroso-commons` [src].
- GitHub lists 14 GB of SSD for standard Linux runners, and the amd64 image is
  3.76 GB compressed and 11.7 GB unpacked [src, run]. The free space after
  cleanup and the pull time are unknown, so the workflow prints `df` before and
  after the pull.

## 11. Repository layout

```
klayout-magic-pcells/
├── grain.xml
├── README.md
├── LICENSE                        Apache-2.0
├── NOTICE                         where the manifests' data comes from
├── .gitignore                     out/
├── pymacros/
│   └── klayout_magic_pcells.lym   autorun: register the library
├── python/
│   └── klayout_magic_pcells/
│       ├── __init__.py            register(), unregister(), LIBRARY_NAME, __version__
│       ├── __main__.py            CLI: doctor, check, generate, audit, cache
│       ├── config.py              Config.load()
│       ├── manifest.py            Manifest, DeviceSpec, ParamSpec
│       ├── backend.py             MagicServer, MagicOneShot, Generator, BackendError
│       ├── protocol.py            encode_request(), ReplyParser
│       ├── cache.py               GdsCache, cache_key()
│       ├── importer.py            insert_gds_flat()
│       ├── stamp.py               make_stamp(), apply_stamp(), read_stamp()
│       ├── pcell.py               make_pcell(spec, generator)
│       ├── dialog.py              the stored dialog form (version 0.5)
│       ├── library.py             Sky130MagicLibrary
│       ├── audit.py
│       ├── tcl/
│       │   ├── kmp_server.tcl
│       │   └── kmp_manifest.tcl
│       └── data/
│           └── manifest-sky130A.json
├── tools/
│   └── build_manifest.py
├── scripts/
│   ├── parity.sh
│   └── test.sh
├── tests/
│   ├── unit/
│   ├── backend/
│   └── parity/
│       ├── run_sweep.py
│       ├── gen_sweep.py
│       ├── sweep_limits.json
│       ├── magic_ref.tcl
│       ├── dialog_ref.tcl         path D, version 0.5
│       ├── pcell_path.py
│       ├── compare.py
│       ├── roundtrip.py
│       ├── sheet.py
│       ├── drc.py
│       ├── mdrc.tcl
│       ├── extract.tcl
│       ├── report.py
│       └── baseline/
│           └── drc-defaults.json
├── .github/workflows/parity.yml
└── docs/
    ├── design.md
    └── probes/                    the probe scripts cited in this document
```

The README covers:

1. What the plugin is, what parity means here (section 1), and its status.
2. Requirements: KLayout 0.30.5 or later (0.30.11 tested), Magic (8.3.681
   tested), sky130A from open_pdks (026824c7 tested), or the pinned image.
3. Installing as a Salt package and checking the setup with `doctor`.
4. Use in the GUI (library `sky130_magic`), with `klayout -b -rm`, and from
   plain Python.
5. Parameters: `w` per finger, Magic's corrections shown but not written back,
   and the list in 4.4.
6. The configuration table from section 8.
7. The cache: where it is, `cache prune`, `cache clear`.
8. Stamps and `audit`.
9. What happens when Magic is missing: no library, `<defunct>` cells that keep
   their geometry, and `register()` later.
10. Running `scripts/parity.sh` and reading the report.
11. Known limitations, from section 13.
12. Licence and credits: Magic, open_pdks, and a note that no code comes from
    the two earlier attempts.

## 12. Implementation order

1. `kmp_server.tcl`, `MagicServer`, the protocol and the `versions` op, with the
   backend tests for M2 and M3.
2. `kmp_manifest.tcl` and `tools/build_manifest.py`; build and commit
   `manifest-sky130A.json` in the pinned image.
3. `insert_gds_flat()`, the PCell factory, the library and `register()` for one
   device, `sky130_fd_pr__nfet_01v8`, then paths A and B and compare.py for that
   device alone.
4. All 60 PCells, the cache, the stamps, failure handling, configuration and
   `doctor`.
5. The full sweep, round trips and report; then the DRC sheets, extraction and
   the committed DRC baseline.
6. Salt packaging, `audit`, the README and the CI workflow file.

## 13. Risks

- **Geometry lost after a backend failure** (K2). The health check, the retry,
  the cache, the saved placeholder and `audit` reduce it. A variant that fails
  while a file opens is still saved as a placeholder until the file is reopened
  with a working backend.
- **Geometry that changes on reopen.** KLayout regenerates every variant on open
  with whatever Magic and PDK are installed. The `kmp_created` warning, `audit
  --regen` and the versioned cache make a change visible, but KLayout doesn't
  ask before regenerating, and version 1 can't pin versions.
- **Magic behaviour that users may not expect** (4.4): no snapping, per-finger
  `w`, stored values that differ from drawn ones. Users who expect KLayout-style
  coercion will be surprised; the README says so.
- **The Magic process.** It could wedge, leak or outlive KLayout. Data-only
  requests, timeouts, restart and retry, `PR_SET_PDEATHSIG`, `atexit` and the
  backend tests cover this, but the exit paths are [untested].
- **The manifest drifting from the installed Magic.** The digest check, `doctor`,
  `tools/build_manifest.py` and `KMP_MANIFEST` cover it.
- **Host layouts with a coarse dbu.** A dbu that doesn't divide 5 nm rounds
  Magic's coordinates (3.5). `audit` reports such files.
- **No pin shapes.** Magic writes labels on `*/5` only. KLayout LVS of circuits
  that use these devices hasn't been tried.
- **Start-up cost.** Every GUI, `-z` or `-zz` start pays about 0.23 s and a
  72 MB process for the health check, even in sessions that never place a
  sky130 device.
- **First open of a large design.** Opening a design runs Magic once per variant
  not in the cache; at 15–20 ms each [run], 500 variants would take about 10 s
  (an estimate).
- **The library is listed under every technology,** because it isn't bound to
  one (9.2).
- **Another package registering `sky130_magic`** would replace this library
  (K7).
- **CI disk.** The 11.7 GB image on a 14 GB runner leaves little room, and the
  space after cleanup is unknown.

## 14. Out of scope

- PDKs other than sky130A (sky130B, gf180mcu, ihp-sg13g2). The manifest, the
  rcfile and the Tcl namespace are per PDK. (Version 0.3 adds gf180mcuD,
  ihp-sg13g2 and ihp-sg13cmos5l; sky130B is still out.)
- A KLayout on the host driving Magic inside a container. It would need a
  wrapper command and shared paths for the GDS files; `KMP_MAGIC` could point at
  such a wrapper later, but it isn't designed or tested here.
- Windows and macOS.
- Switching device type within one PCell, and Magic's `-spice` interface.
- Writing Magic's corrections back into parameters, snapping, and adding pin
  shapes. (Version 0.5 writes back what Magic's dialog shows: section 4.5.)
- Technology, DRC and LVS files: the PDK's are used.
- KLayout's `.mag` reader, and any path back into Magic.
- Creating devices from guiding shapes.
- Replacing or wrapping the PDK's `skywater130` library.
- Publishing: no Salt Mine entry. (After this design was written, the
  repository went to GitHub as vproHacks/klayout-magic-pcells; on
  2026-11-23 it was public.)

## 15. Open questions and unverified points

Questions for Vraj, the project lead:

- The project's licence, and whether the manifest, which is data extracted from
  `sky130A.tcl`, can ship under it. (Decided 2026-11-22: the licence is
  Apache-2.0; see 9.3. Whether the manifests' data may ship under it is
  still open; the README's licence section lists what each PDK's files
  say.)
- Whether stored parameters should stay the user's request, matching
  `magic::gencell` as designed here, or become Magic's checked values, the way
  Magic's dialog writes them back (4.3). The second runs `_check` twice for
  some inputs, and for the three in 4.3 that changes `val` and the cell name.
  (Decided 2026-11-22: the values Magic's dialog shows; see 4.5.)
- The names: `sky130_magic` for the library, and full Magic device names for the
  PCells.

Not verified, carried over from the research:

- Why port labels produce no `*/16` pin shapes; `gds contacts yes` wasn't tried.
- In the GUI: the coerce error label, lazy evaluation, `callback_impl` icons on
  screen, the config file being found, and `PATH` for a desktop launch.
  (On 2026-11-23 the icons were seen on screen under Xvfb; see guide.md.)
- Installing with the Salt manager or `klayout -y`; KLayout's `.mag` reader;
  parameters removed between versions on reload; the PDK library and the
  Efabless package loaded together.
- compare.py under `klayout -b -r`.
- Extraction with `ext2spice merge`, with `m > 1`, and for MOSFETs other than
  nfet_01v8 and pfet_01v8.
- DRC on MIM caps, resistors and HV devices.
- CI: free disk and pull time on a current runner, which Docker image store the
  runners use, whether the old `jlumbroso/free-disk-space` name still resolves,
  `container:` with `shell: bash -l {0}`, and the runner's uid.

Not verified, from this design:

- Whether `val` changes the drawn geometry after a clamp, and what the drawing
  does with resistor `l 1.0u`.
- Fixed devices with `nx` or `ny` above 1: where the instance lands in the
  wrapper, what `deltax` means next to `xstep`, and whether a second request for
  the same fixed device works in one session.
- `binary encode hex` and `binary decode hex` inside Magic's Tcl, and the size
  and cost of the `info body` digest over every `::sky130` and `::magic` proc.
- Whether Magic exits when its stdin closes, and whether `atexit` handlers run
  when KLayout exits.
- When KLayout calls `cell_name_impl` relative to produce, and how it handles
  two variants with the same name.
- Whether `PCellParameterState.value` can be written from `callback_impl`.
- Host dbu 0.005 being exact for all 60 devices.
- Sheet DRC run times, and whether 40 µm between devices is enough.
- Conflicts between GDS attribute 100 and other tools.

Still outstanding from the KLayout research: container `3c43372766a3`, a hung
`klayout -e` probe, needs `docker kill 3c43372766a3` from someone with
permission. (On 2026-11-23 `docker inspect` found no such container.)

## Sources

Research notes, all in `$S/research/`:

- `magic.md`: driving Magic's generators in batch, the manifest method, GDS
  output, `_check`, timing and the persistent process.
- `klayout.md`: the PCell API, importing GDS, Salt packaging, the PDK's library
  and the two reference repos, saving and reopening.
- `parity.md`: geometric comparison, DRC and extraction on single devices, and
  GitHub Actions with the pinned image.
- `magic-manifest.json`: the 60 devices, their parameters, types, `_check`
  results on defaults and batch results.
- `compare.py`: the per-layer XOR and text comparison.

Experiment files: `$S/mexp/` (Magic), `$S/kl/exp/` (KLayout), `$S/research/work/`
(parity), and the reference-repo clones in `$S/refs/`.

Probes run for this design, all in the pinned image. Copies are in
`docs/probes/`; they read and write `/scratch/design/exp`, the original location
(`$S/design/exp/`) as mounted in the container:

- `idem.tcl`: `_check` run twice on 12 inputs (4.3).
- `stamp.py`: where a stamp survives GDS and OASIS (7).
- `hidden.py` and `ctx.py`: a hidden string parameter stored in the context and
  read back after its default changed (7).
- `logger.py`: `klayout.tl.Logger` and its methods (4.3, 5).
- Two one-off checks without a file: no editable parameter name collides with a
  `PCellDeclarationHelper` attribute (4.2), and the GDS layer numbers listed in
  `sky130A.lyp` don't include 255 (5).

The scratch directory is temporary, so this document restates the results it
depends on, and the probe scripts are kept in `docs/probes/`.

## 16. Version 0.6 checks

Version 0.6.0 runs Magic's DRC, Magic's extraction and netgen's LVS on a
cell of a KLayout layout, from a Magic menu in KLayout and from the
command line (`drc`, `extract`, `lvs`). It adds a generated-layer check
(`layers`) and a port check (`ports`), and it publishes a table per PDK
of where Magic's DRC and the PDK's KLayout decks disagree (`docs/gaps/`).
[design-0.6.md](design-0.6.md) gives the design of these checks.

The checks run Magic in processes of their own, one per job, beside the
PCell server of section 3.3. Their job directories sit under `jobs/` in
the cache directory of section 6, and `cache clear` and `cache prune`
cover them too. The parity harness of section 10 has a `jobs` step for
them (design-0.6.md 5.2). Version 0.6 leaves the PCell design in this
document as it is.
