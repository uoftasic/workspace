# The case suite

`build.py` draws, for each of the four PDKs, the layouts that the
plugin's Magic checks are tested on: DRC, extraction, LVS, the
generated-layer check and the port check, all added in version 0.6. It
also writes a `cases.json` that says what each case targets and what Magic
and KLayout reported on it when it was measured. The gap studies and the
review measured most cases; the few gaps cases that were redrawn or
added after a check against the foundries' published rules were measured
in the pinned image (see Sources and "Where expect comes from"). Every
GDS is drawn at run time with
`klayout.db`; there are no layout files in the repository.

```
python3 tests/cases/build.py --pdk sky130A --out out/cases/sky130A
python3 tests/cases/build.py --pdk gf180mcuD --out out/cases/gf180mcuD --set hier --set names
python3 tests/cases/build.py --pdk ihp-sg13g2 --out out/cases/ihp-sg13g2 --set controls --magic-row
```

Run it in the pinned image (`scripts/in_image.sh`). The gaps, hier,
whole_shape, names and sheet sets need only `klayout.db`. The inverters set
also builds the inverter from the plugin's PCells, which needs Magic;
`--no-pcell` leaves it out, and a build that cannot start the plugin prints
a `WARNING` line and builds the rest. The controls set needs `PDK_ROOT`,
because it copies the standard cells out of `libs.ref`. `--magic-row` runs
`magic_row.tcl` after the controls are built, to have Magic write the row
of standard cells itself (see The Magic-written row). A build of some sets
(`--set`) replaces those sets' records in an existing `cases.json` in the
same folder and keeps the rest.

## Sources

The Source column of "The sets" and the `source` key of `cases.json` cite
sections of [docs/design-0.6.md](../../docs/design-0.6.md) and two pieces
of work that it describes and that are not in this repository. A gap
study per PDK measured where Magic's DRC, extraction and LVS disagree with
the PDK's KLayout decks, on small layouts that each change one thing; it
is cited as `GAPS-<pdk>`, so `GAPS-sky130A 2.2` is section 2.2 of the
sky130A study. A review of the 0.6 design, made before any code (*the
review*), ran measurements of its own; a source names the review's case
and the section of design-0.6.md that describes it, as in "the review's
long well, design-0.6.md 3.1 and 6.4". The raw results that the gap
studies' tables were made from, and the review's logs, are outside the
repository too.

For version 0.6.1, the rows of the gap tables (`docs/gaps/`) on which
Magic and the KLayout decks disagreed, and the gaps cases filed under
them, were checked against the foundries' published rules: on sky130A,
SkyWater's rule pages in
google/skywater-pdk at commit 7198cf6 (`docs/rules/periphery-rules.rst`,
`errors.csv` and `assumptions/07-other.csv`); on gf180mcuD, GF's design
rules in google/gf180mcu-pdk at commit de3240d; on ihp-sg13g2, IHP's
SG13G2 Layout Rules, Rev. 0.4; and on ihp-sg13cmos5l, IHP's SG13CMOS5L
Layout Rules, Rev. 0.1 (the two PDFs in IHP-GmbH/IHP-Open-PDK, under
`<pdk>/libs.doc/doc/`, which the PDKs in the pinned image also carry). A case that did not break the rule it was filed
under was redrawn, filed under the rule it breaks, or, where it breaks
none of the published rules, filed under no rule (see Files). The
comments at those cases in `pdk_sky130a.py` cite the rule pages by file
and line; those in `pdk_gf180mcud.py` name the rule and its value.

## Files

| File | What it holds |
|---|---|
| `build.py` | the command line, one builder per set, `run_magic_row()` |
| `common.py` | the drawing helper, GDS writing with the options of the plugin's export, the GDS file it writes for Magic (no context information, no timestamps), the split of a cell into a parent and a child for the hier set, the case record |
| `pdk_sky130a.py`, `pdk_gf180mcud.py`, `pdk_sg13g2.py`, `pdk_sg13cmos5l.py` | per PDK: layers, the tables of gaps cases, the hier set's layer groups and results, the long-well case, the minimal error for the names set, the inverters and schematics, the seven standard cells, the PCell inverter |
| `expect-<pdk>.json` | the measured DRC results of the gaps cases, per case (see "Where expect comes from") |
| `magic_row.tcl` | has Magic place the controls row and write it as GDS |
| `magic_cells.tcl` | Magic's DRC on case cells with `tests/parity/mdrc.tcl`'s steps, per cell and style, and optionally the parity harness's extraction; at most 15 cells per process |

The tables of gaps cases in the per-PDK modules are the gap studies' own
builders, brought under one interface with the geometry unchanged, so that
the measured results still apply to the shapes drawn here. The exceptions
are the cases that did not break the rule they target, which were
redrawn: sky130A `s_m1_adj_mcon`, `s_via_m1_adj`, `s_m1_wide_space` (with
their controls) and `e_butt_short`, and gf180mcuD `NW2a_s050`,
`NP3_s006`, `V1_3_m1ov0` and `V1_3_m1ov002`. sky130A `s_m1_huge_space`
and its control were added for `met1.3b`; they hold `s_m1_wide_space`'s
shapes as the study drew them. Some cases keep their shapes but target
another rule than the study gave them: sky130A `s_li_45deg` targets
`x.2` and `c_pc_to_pdiff` `licon.9`, ihp-sg13cmos5l `u_angle.poly`
targets the row `grid.Angle45` (through the module's `RULE_OF`), and
sky130A `d_tap_area` and `e_ntap_area`, whose taps SkyWater's rules allow
and Magic's `psd.10b` and `nsd.10b` report, target none.

## The sets

| Set | Cases | Source |
|---|---|---|
| `gaps` | the gap studies' one-change cases: a clean control, and cases that each change one thing in it | GAPS-sky130A 2.1, 2.2 (batch A and E); GAPS-gf180mcuD 2; GAPS-ihp-sg13g2 3 and the hand-drawn devices of 4; GAPS-ihp-sg13cmos5l 2, 3, 4 |
| `hier` | the flat original (`<base>_flat`, top `<base>`), and `<base>_<group>_h`: the group's layers in the parent, the rest in `<base>_<group>_dev` placed at the origin | the review's two-level cells, design-0.6.md 3.1 |
| `whole_shape` | a long well whose rule looks across the whole shape, with the area `box` that an area check should be tried on | sky130A: the review's long well, design-0.6.md 3.1 and 6.4; GAPS-gf180mcuD 2, GAPS-ihp-sg13g2 2a and GAPS-ihp-sg13cmos5l 1, each with design-0.6.md 3.1 |
| `names` | the twelve names the review tried, each a cell under `NTOP` with one minimal-width Metal1 box, plus `does_not_exist`, a name the file doesn't have | the review's cell names, design-0.6.md 2.2 and 6.5 |
| `inverters` | the hand-drawn inverter, broken variants (open drain, A and Y swapped, no texts; on sky130A also W 0.36, the A pin without li, and A's text on li1.pin, `inv_text_on_pin`), the PCell inverter, and a schematic `<case>.spice` for each | GAPS-sky130A 5.2, GAPS-gf180mcuD 5, GAPS-ihp-sg13g2 6, GAPS-ihp-sg13cmos5l 5 |
| `controls` | the negative controls, correct layouts that must give no finding: the review's seven standard cells, a row of them, the Magic-written row, and the hand-drawn inverter | the review's negative controls, design-0.6.md 3.3 and 6.2 |
| `sheet` | the gaps cases as `D<top>` cells 40 µm apart in `SHEET`, placed by `tests/parity/sheet.py`, which moves each cell by a multiple of 5 nm so that its shapes stay on the PDKs' 5 nm grid | design-0.6.md 5.1; GAPS-sky130A 2.4 |

Per-PDK choices:

- **hier bases.** sky130A `inv_base`; gf180mcuD `C_NMOS` and `C_PMOS` (the
  review moved the implants of the nfet and the well of the pfet, and ran
  every group on both; on `C_NMOS_nw_h`, `C_PMOS_imp_h` and `C_PMOS_all_h`
  Magic reported no DRC error, and their notes say so); ihp-sg13g2 the
  hand-drawn inverter; ihp-sg13cmos5l `base`. The layer groups are the
  review's.
- **whole_shape.** sky130A: the review's 100 × 3 µm n-well with one
  contacted n-tap at its left end (`nwell.4`). gf180mcuD: `dv9_long`, a 3.3 V
  pfet and a 6 V pfet at the two ends of one 100 µm n-well (DV.9, whose
  `bad_nwell` layer is grown through the whole well with `bloat-all`). The
  other candidate rule named for this set, "P-diffusion and N-ohmic must be
  over N-well" (line 2799 of the Magic tech file), is a local `and-not` and
  has no long form. Both IHP PDKs: `lu_long`, a 100 × 3 µm n-well with its
  tap at the left end and a PMOS 14 µm from it, inside LU.a's 20 µm reach.
  nmosi.d needs a deep n-well and Act.e is a hole area, so neither has a
  long-well form.
- **The Magic-written row.** sky130A and gf180mcuD have `libs.ref/<lib>/mag/`,
  so Magic loads the cells from there. The two IHP libraries have no `mag/`
  folder in the pinned image; Magic reads the seven copied GDS files
  instead, then places and writes the row the same way.

## cases.json

```json
{"schema": 1, "pdk": "sky130A", "sets": ["gaps", "..."], "anchors": {"a_poly8": "poly.8"},
 "cases": [{"name": "a_poly8", "file": "gaps/a_poly8.gds", "top": "a_poly8", "set": "gaps",
            "targets": ["poly.8"], "expect": {"magic": {"drc(fast)": {"poly.8": 1}, "...": {}},
                                              "klayout": {"kl_lydrc_feol": {"poly.8": 1}, "...": {}}},
            "notes": "...", "source": "GAPS-sky130A 2.2", "control": "inv_base"}]}
```

Every case has the keys `name`, `file`, `top`, `set`, `targets`,
`expect`, `notes` and `source`. `file` is relative to the output
directory. `top` is the cell to check, and it can differ from `name`:
ihp-sg13cmos5l's variant names hold `.`, which Magic cannot load
(design-0.6.md 2.2), so their cells use `_`, as the gap study's builder
wrote them.

`expect`:

- `magic`: per style, the error boxes per rule ID as `drc listall why` gave
  them. The ID is the text in the last parentheses of the why-text (the
  message Magic gives an error box), or the whole why-text where there are
  none. A style with `{}` was checked and gave nothing. A style that is
  missing was not checked. In the hier set, `magic.extract` counts the
  devices Magic extracted, by model.
- `klayout`: per run of the KLayout deck, markers per category. Where the
  gf180mcuD study recorded the category without a count (`kl_alone`), the
  count is `null`, and the four redrawn gf180mcuD cases record theirs the
  same way. The sky130A runs are the parity harness's switches
  (`kl_harness`), Run DRC (Full) (`kl_menu_full`), and `sky130A.lydrc` as
  shipped (`kl_lydrc_shipped`) and with FEOL on (`kl_lydrc_feol`).
- `netgen` and `klayout.lvs` in the inverters set: the result line each tool
  printed, as the gap studies quote it.
- `magic_area` on sky130A `nwtap`: Magic's own area check of that box.
- `ports` on sky130A `inv_text_on_pin`: the findings that the port check
  must give (P1 to P8, under [Ports](../../README.md#ports) in the README),
  `["P3"]`. This one is not a measurement: the case is drawn to give it (a
  text on 67/16 is a Magic port that KLayout's LVS can't name), and the
  [jobs step](../jobs/README.md) asserts it (`ports_expect`).
- `magic_plain_load` in the names set (sky130A only): what Magic's plain
  `load` and a check did with that name in the review's run.

`expect` is `{}` wherever no one measured the case. The builder never
fills it from its own runs; the entries of the redrawn and added gaps
cases were measured once and written into `expect-<pdk>.json` (see
"Where expect comes from"). Where this build measured something new, it
goes in `measured` (whole_shape) or `notes`, with what ran it.

Keys the suite adds: `control` (gaps), `moved` and `child` (hier), `box` and
`measured` (whole_shape), `klayout_name` (names), `schematic` (inverters),
`negative_control`, `x_um` and `magic_row` (controls), `cases` (sheet).

## Where expect comes from

`expect-<pdk>.json` was transcribed once from the raw results of the gap
studies, the files that their tables were made from (on gf180mcuD, the
run that checked each cell as the top cell). The hier, whole_shape and
names results are typed into the PDK modules from the review's runs.

The entries of the redrawn cases, and of sky130A `s_m1_huge_space` and
its control, are not the studies'. They were measured on the shapes
drawn here, on 2026-11-24 in the pinned image (Magic 8.3.681, KLayout
0.30.11): on sky130A by the gap table's runs (`scripts/gaps.sh`), whose
four KLayout runs give the four `kl_*` keys above, and on gf180mcuD with
Magic and `gf180mcu.drc`. Each of these cases' `source` in `cases.json`
says so.

## The Magic-written row

The `row_magic` case's `magic_row` key holds what `magic_row.tcl` needs: the
cells, their x positions, and the `mag/` folder or the GDS files to read.
`build.run_magic_row(pdk, out, record)` runs Magic with the PDK's rc file,
checks that the written row holds the seven cells at those positions, and
returns the path of the written file. Each cell's origin sits at the sum
of the LEF widths of the cells to its left, which is how a placer abuts
them; the row that KLayout places (`row`) uses the same positions.

## Counts

Cases per set, as built on 2026-11-24:

| PDK | gaps | hier | whole_shape | names | inverters | controls | sheet |
|---|---|---|---|---|---|---|---|
| sky130A | 132 | 4 | 1 | 13 | 8 | 10 | 1 |
| gf180mcuD | 69 | 8 | 1 | 13 | 5 | 10 | 1 |
| ihp-sg13g2 | 151 | 4 | 1 | 13 | 5 | 10 | 1 |
| ihp-sg13cmos5l | 49 | 4 | 1 | 13 | 5 | 10 | 1 |

The inverters count includes the PCell inverter. The controls count is the
seven cells, the row, the Magic-written row and the inverter.

## Left out

- gf180mcuD's two deep-n-well cells (`DN_ctrl`, `DN11_lvmv`).
- ihp-sg13g2's `M_` cells of GAPS section 4, which change Magic's own device
  GDS and need Magic to generate it first.
- sky130A's five Lab 02 anchor cells, which are Magic-written course files.
- The rotated and magnified instances in the review's cell-name layout
  (design-0.6.md 2.6).

## Tests

`tests/unit/test_cases.py` builds every set but the PCell inverter on all
four PDKs into a temporary folder (the controls only where `PDK_ROOT` has the
library) and reads everything back: the schema, each file's top cell, the
hier split, the names, the sheet's spacing and its 5 nm steps, the
anchors' rules, the schematics and the row positions. It needs
`klayout.db` and runs in the image:

```
python3 -m unittest tests.unit.test_cases
```
