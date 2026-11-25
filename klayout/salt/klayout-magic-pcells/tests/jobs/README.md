# The jobs step of the parity harness

`run_jobs.py` tests the plugin's Magic jobs on the case suite of
`tests/cases`: DRC, extraction, LVS, the generated-layer check and the
port check. Where a reference that uses no plugin code exists, the step
compares with it. The generated-layer and port checks have
none; their findings are compared with a recorded baseline, and a few of
them are asserted in code. The parity harness (`tests/parity/run_sweep.py`,
described under Tests in the [README](../../README.md#tests)) runs this
step last, and `--no-jobs` skips it. The step also runs alone in the
pinned image, through `scripts/in_image.sh`:

```
scripts/in_image.sh 'python3 tests/jobs/run_jobs.py --pdk sky130A --out out/jobs/sky130A'
scripts/in_image.sh 'python3 tests/jobs/run_jobs.py --pdk sky130A --out out/jobs/sky130A --quick'
KMP_IMAGE_PDK=gf180mcuD scripts/in_image.sh 'python3 tests/jobs/run_jobs.py --pdk gf180mcuD --out out/jobs/gf180mcuD --update-baseline'
```

Set `KMP_IMAGE_PDK` to the PDK being run, as `scripts/parity.sh` does. The
step writes `jobs.json` into its output folder, and the harness copies it
into `report.json` under `jobs` and into a "Jobs step" section of
`report.md`.

The exit status is 0 when every check passes, 1 when a check fails or a
unit of work raises an exception, and 2 when the step itself fails (the
case build, for example). A layers or ports check that raises fails even
when the baseline holds the same record. A job that ends with status 2 is
a result like any other: it is compared with the baseline, its reason
included. A cell that Magic reads nothing in gives status 1 and a finding
rather than a failed job, and the `reads_nothing` check asserts that.

Terms used below: the *export* is the GDS file that the plugin writes from
a cell for Magic to read, and a *why-text* is the message Magic's DRC gives
an error box. `Outcome` is the plugin's DRC result: `rows` holds the errors
it keeps, `raw` each checked cell's own listing, and `empty` the cells that
Magic read as empty. The styles (`drc(fast)`, `drc(full)`, `drc(routing)`)
and the hierarchical and flat modes are those of the `drc` command, under
[Magic DRC](../../README.md#magic-drc) in the README. F1 to F4 are the
findings of the [generated-layer check](../../README.md#generated-layers)
that count, and P1 to P8 those of the [port check](../../README.md#ports).
The sets of cases (gaps, hier, names, inverters, controls and the rest) are
described in [tests/cases/README.md](../cases/README.md).

## Checks

| Check | Compares | Why |
|---|---|---|
| `drc_plumbing` | The plugin's DRC, in each style and both modes, against `tests/parity/mdrc.tcl` run on the plugin's own export, as multisets of (cell, why-text, box at 1 nm). In hierarchical mode the plugin's boxes are taken before it drops the boxes of a parent that are copies of a subcell's box, and mdrc.tcl checks each cell of the export as its own top; the list of cells comes from KLayout's reading of the export, not from the plugin. In flat mode the plugin's side goes through the TSV that `drc --tsv` writes. | It tests the export, the job script, the parsing and the units. Both sides read the same file, so it cannot find a difference in how Magic reads a layout. |
| `drc_cells` | In hierarchical mode, the cells in `Outcome.raw` (the cells the plugin checked) against the export's tree as KLayout reads it, minus `Outcome.empty` (the cells Magic read as empty). | Plumbing treats a cell missing from `raw` as clean, so a run that skipped the children would pass plumbing wherever the children have no error. |
| `drc_markers` | The boxes of the report database's error items (under "Magic DRC", not under an "only when ... is checked on its own" category) against `Outcome.rows`, cell by cell, as multisets of (why-text, box at 1 nm), in every style and mode. | Plumbing reads `rows` and `raw`, but the user sees the report database. |
| `drc_coverage` | Each case the step ran has a `drc_plumbing` result for every style and mode and a `drc_fidelity` result for every style. Each gaps case has its hierarchical plumbing and fidelity results from the sheet in every style, and the sheet's flat check has one per style. A missing result fails. | A route that loses cases (an export that flattens in hierarchical mode drops every sheet cell) would otherwise only lower the pass count. |
| `drc_fidelity` | Magic reading the original GDS file, with every cell checked as its own top as hierarchical mode does, against the plugin's hierarchical run on its export. Per cell and rule, the error boxes are merged into regions, and the XOR of the two must be empty at 1 nm. Cells whose names Magic cannot load are skipped and listed. | It finds what the export changes: a flattened tree, a lost cell, a moved shape. Two routes that agree can list different numbers of boxes, so regions are compared. |
| `drc_hier` | On the hier set, the per-rule counts of the top cell's own drc(full) listing against `cases.json` `expect.magic`, and the devices of the plugin's extraction against `expect.magic.extract`. | The hier cases put the implants or the well of a device in its parent. Magic decides device types in each cell from that cell's shapes alone; the expected counts are those of Magic's check from the top cell. Hierarchical mode also checks the child as its own cell and adds rules there; those are recorded and not compared. |
| `drc_names` | Each names case gives exactly one error, its target rule, under the cell's KLayout name; `does_not_exist`, a cell name the file doesn't have, gives status 2. | Magic renames or misloads cells whose names are not `[A-Za-z0-9_$]+`. |
| `lvs` | On the inverters set, the plugin's verdict against netgen, run by this step on the same layout netlist and schematic with the PDK's setup file. The step reads netgen's report with a few lines of parsing of its own: a match needs the last "Final result" to say that the circuits match, and no property, port, pin or subcell failure after it. | A parser that reads only the final line would miss property errors (sky130A `inv_w036`). |
| `lvs_badnets` | Every net that netgen's JSON lists under `badnets` (the layout side, or the schematic side when the layout side is empty) is named by one of the plugin's markers or report rows. | Each net that netgen could not match should be findable on the layout. |
| `lvs_markers` | Each marker of a net that netgen's JSON lists under `badnets` (layout side) holds that net's node point from the top cell's `.ext` file, which this step reads, at the job's `JobResult.scale` (µm per Magic unit). On `inv_open_drain`, the marker of the net whose node point is on the drain diffusion is a shape, not a dot, and covers that piece of diffusion minus poly. | `lvs_badnets` checks names only; a wrong unit puts every marker at the origin. |
| `layers`, `ports` | The findings of the generated-layer check and the port check against `expected-<pdk>.json`. The port check runs with `--magic`, which adds P8, on the inverters and controls. `--update-baseline` rewrites that file; a case missing from it fails. | These checks have no outside reference; the baseline shows any change. |
| `controls` | The negative controls give no F1 to F4 finding: the seven standard cells, the row of them, the row Magic writes itself, and the clean hand-drawn inverter. This is asserted in code, also with `--update-baseline`, and a control with such a finding is written to the baseline as "not written", never with its findings. | A baseline must not absorb a false finding on a correct layout. |
| `f1_positives` | The F1 positives of the gap studies, the gaps cases listed in the table of `tests/backend/test_layers_backend.py`, give an F1 item on their layer. This is asserted in code, also with `--update-baseline`. A case that fails is written to the baseline as "not written", and in the full step a positive that did not run fails. | A baseline must not absorb the loss of a finding that should fire. |
| `reads_nothing` | The gaps cases Magic reads nothing in (`READS_NOTHING`: 8 on sky130A, 22 on ihp-sg13g2) give layers status 1, no F1 to F4, and an "Export/Magic reads nothing in this cell" item. Run as a case (`--quick`), drc in every style and mode gives status 1, the item, and the top cell in `Outcome.empty`. On the sheet, hierarchical mode's `Outcome.empty` holds exactly their `D<case>` cells. Any other case with that item fails. | Such a cell is a finding and not a failed job. A load check that lets Magic read nothing in a cell, and so check nothing, must fail. |
| `ports_expect` | The P checks of the port check equal `cases.json` `expect.ports` where a case has one (sky130A `inv_text_on_pin`: P3). This is asserted in code, also with `--update-baseline`. | A text on a `*/16` pin layer is a Magic port that KLayout's LVS can't name; a port check that takes it for a text on `*/5` loses the P3. |
| `readback` | The GDS read-back check: every device, at its default parameters, extracted from Magic's database and again after Magic's GDS write and read, against `data/readback-<pdk>.json` (`readback.py`). Any difference that the data file does not list fails. | Every job reads the plugin's PCells through Magic's GDS reader, which loses some devices. |
| `gaps` | `tools/build_gaps.py --check`, which rebuilds the gap tables of `docs/gaps/` and compares them with the committed ones. | A PDK or Magic update that changes a rule shows as a failed check. |

The step also records these, without checking them:

- `native`: `magic_native.tcl`, what a Magic user gets. It reads the original
  file with DRC on, loads the top cell and checks it from the top only, in
  drc(fast) and then drc(full), with `drc list count total` and
  `drc listall why`, as the course's Magic checker does. The report lists,
  per case and style, the rules where its count differs from the plugin's
  hierarchical mode, which checks every cell and then the top.
- The gaps sheet: the error boxes per rule in hierarchical mode, in the top
  cell's own listing and in flat mode.
- The time of every job, by kind, and their sum, which estimates the time
  on one CPU. The times are measured with the workers running at once, so
  the sum runs high.

## Cases and modes

- The gaps cases run as the cells of the case suite's sheet, one layout
  that holds every gaps case as a `D<case>` subcell. Hierarchical mode
  checks each `D<case>` cell as its own top, 15 cells to a Magic process.
  That is the same check as one case at a time, with a fifteenth of the
  Magic processes (a DRC job on one small cell takes 0.4 to 0.6 s). Flat
  mode checks the flattened sheet. The layers and ports checks and
  `magic_native.tcl` run on each gaps case's own file.
- The other sets (hier, whole_shape, names, inverters, controls) run one
  case at a time, in every style and both modes, except the names set,
  which runs in drc(full) only.
- `--quick` runs the inverters set, with the PCell inverter, and up to three
  more cases (`QUICK_EXTRA`), each as a case of its own in every style and
  both modes: a negative control (sky130A `sky130_fd_sc_hd__mux2_1`,
  gf180mcuD `gf180mcu_fd_sc_mcu7t5v0__mux2_2`, `sg13g2_mux2_1`,
  `sg13cmos5l_mux2_1`), a case with an F3 finding (`c_licon_gate`, `CO11_cont_field`,
  `Cnt_g`, `m_V1.a`) and a cell Magic reads nothing in (`s_npc_alone`,
  ihp-sg13g2 `EXTB_a`; gf180mcuD and ihp-sg13cmos5l have none). It builds
  the gaps and controls sets for them, without the Magic-written row, and
  skips `readback` and `gaps`. With `--quick` the inverter `inv` counts as
  a negative control, because the controls set's `inv_control` is the same
  file.

## Files

| File | What it is |
|---|---|
| `run_jobs.py` | the step: the case build, the units of work on a pool of processes, the checks, `jobs.json` |
| `build_cases.py` | `tests/cases/build.py` with every set, the PCell inverter and the Magic-written row; `--quick` builds the inverters, gaps and controls sets without the row. It fails when the build warns. |
| `magic_native.tcl` | the Magic user's check, written for this step |
| `readback.py` | the GDS read-back measurement, also used by `tests/backend/test_lvs_backend.py` |
| `expected-<pdk>.json` | the layers and ports baseline |

`tests/parity/mdrc.tcl` takes its style from `KMP_STYLE` (drc(full) when it
is not set) and, with `KMP_CELLS`, checks several cells of one file in one
process; `run_mdrc()` in `tests/parity/drc.py` runs it that way.
