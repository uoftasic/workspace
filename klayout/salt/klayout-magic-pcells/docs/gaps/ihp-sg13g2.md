# Gap table: ihp-sg13g2

This table compares Magic's DRC rules for ihp-sg13g2 with the PDK's KLayout DRC decks, one row per rule, and shows where they disagree. `tools/build_gaps.py` generates it; do not edit it by hand.

- **What a row is.** One rule, under the rule ID that Magic's why-text gives it (the why-text is the message Magic's DRC gives an error box, and the ID is the text in its last parentheses), under a name from `tests/gaps/aliases-ihp-sg13g2.json` where the two tools name the rule differently, under the KLayout name where Magic has no such rule, or under Magic's whole message where the message has no ID. The row gives the statements of Magic's tech file that check the rule, each KLayout deck's outputs for it (the report categories the deck writes), and what both engines reported on the test cases that target it.
- **How it is made.** Magic's rules come from `python/klayout_magic_pcells/data/pdk-ihp-sg13g2.json`. Each KLayout run below checked a layout of one box. Its report has a category for every rule the deck ran under its switches, and those categories are the deck's side of the table; a text scan of the deck gives each output's line and the switches it sits under. The two sides are joined on rule ID, with the mappings made by hand in `tests/gaps/aliases-ihp-sg13g2.json`. The test cases are the `gaps` set of the case suite (`tests/cases`): a clean control layout, and cases that each change one thing in it. Magic checked each case cell alone in all three styles, at most 15 cells per process; KLayout checked them on one sheet, 40 µm apart. A case's results are the rules reported on it and not on its control.
- **Image.** The pinned Docker image `hpretl/iic-osic-tools@sha256:3c371645b19c6f6564dc8c7b21e39ad1c1833d274fe5b85639afe1ba9d7987e7`, with Magic 8.3.681 and KLayout 0.30.11; PDK commit 7e53c777 (Magic tech 1.0.1).
- **Rebuild.** `scripts/gaps.sh --pdk ihp-sg13g2` rewrites this page; `scripts/gaps.sh --pdk ihp-sg13g2 --check` fails if it would change.

Each row has one status. The status and the value comparison take the `main` and `maximal` decks of `run_drc.py` as the KLayout side; the other decks have their own columns.

- **both**: Magic and the KLayout side both check the rule.
- **both, values differ**: both check it, with different values; the note gives both.
- **folded**: Magic checks the ID only inside a composite rule, such as `V1.a + 2 * M2.c`.
- **measured on other shapes**: both check it, on different shapes; the note says which.
- **same name for another check**: the name means a different rule on each side; the note says what each one checks.
- **in the deck, did not fire on its case**: a tool has the rule but reported nothing on the cases that break it; the note names the tool and the cases.
- **Magic only**: the KLayout side does not have the rule; the note says when another deck has it, or when Magic checks it only inside a composite rule.
- **KLayout only**: Magic has no such rule.

In the Magic column each statement reads `value [styles] :line`, with the styles F `drc(fast)`, U `drc(full)` and R `drc(routing)`; `in (...)` names the composite rule a value belongs to, and `as X` the ID under which Magic prints the rule. In a deck's column each output reads `name value [switch] :line`, where the switch is the condition around the output in the deck, and `only in` names the runs that report it when the deck has several. `:n` is a line of the tech file or deck, and – means none. The Tested column gives, for each case that targets the rule, the Magic styles and the KLayout runs that reported it there; `no` means none did.

## Counts

| Part | both | folded | same name for another check | in the deck, did not fire on its case | Magic only | KLayout only | total |
|---|---|---|---|---|---|---|---|
| Front end, Metal1, Via1, grid, pins | 87 | 5 | 0 | 4 | 2 | 67 | 165 |
| Other layers | 116 | 7 | 1 | 0 | 10 | 63 | 197 |
| all | 203 | 12 | 1 | 4 | 12 | 130 | 362 |

## KLayout runs

Each run checked a layout of one box; the last column counts the categories in its report. "The harness" is the plugin's parity harness (`tests/parity`).

| Run | What | Categories on one box |
|---|---|---|
| harness_main | run_drc.py --no_density --mp=1 --density_thr=1 (main and maximal decks, merged) | 570 |
| harness_maximal | run_drc.py --no_density --mp=1 --density_thr=1 (main and maximal decks, merged) | 272 |

Cases: 151 in the `gaps` set.

## Rules

### Front end, Metal1, Via1, grid, pins

| Rule | Status | Magic: value [styles] :line | main: name value [switch] :line | maximal: name value [switch] :line | Tested (case: what each engine reported) |
|---|---|---|---|---|---|
| Act.a | both | 0.15 [FUR] :139 | Act.a 0.15 [TABLES.include?('activ') \|\| FEOL] 5_5_activ.drc:32 | – | Act_a: Magic FUR, KLayout harness_main |
| Act.b | both | 0.21 [FUR] :140 | Act.b 0.21 [TABLES.include?('activ') \|\| FEOL] 5_5_activ.drc:39 | – | Act_b: Magic FUR, KLayout harness_main |
| Act.c | both | 0.23 [FUR] :143; 0.23 [FUR] :144; 0.23 [FUR] :145; 0.23 [FUR] :146 | – | Act.c 0.23 sg13g2_maximal.drc:2074 | Act_c: Magic FUR, KLayout harness_maximal |
| Act.d | both | 0.122 µm² [FUR] :148 | – | Act.d 0.122 sg13g2_maximal.drc:2077 | Act_d: Magic FUR, KLayout harness_maximal |
| Act.e | both | 0.15 µm² [U] :151 | – | Act.e 0.15 sg13g2_maximal.drc:2080 |  |
| Cnt.a | both | 0.16 [FUR] :286; 0.16 [FUR] :287; 0.16 [FUR] :288; 0.16 [FUR] :289; 0.16 [FUR] :290; 0.16 [FUR] :291; 6 more | Cnt.a 0.16 [TABLES.include?('cont') \|\| FEOL] 5_14_cont.drc:37 | – | Cnt_a: Magic FUR, KLayout harness_main; Cnt_big: Magic no, KLayout harness_main |
| Cnt.b | both | 0.18 [FUR] :309; 0.18 [FUR] :311; 0.18 [FUR] :313; 0.18 [FUR] :315 | Cnt.b 0.18 [TABLES.include?('cont') \|\| FEOL] 5_14_cont.drc:44 | – | Cnt_b: Magic FUR, KLayout harness_main |
| Cnt.b1 | KLayout only | – | – | Cnt.b1 0.2 sg13g2_maximal.drc:2260 | Cnt_b1: Magic no, KLayout harness_maximal |
| Cnt.c | both | 0.07 [FUR] :327; 0.07 [FUR] :329; 0.07 [FUR] :331; 0.02 [FUR] :334; 0.02 [FUR] :336; 0.02 [FUR] :338; 10 more | Cnt.c 0.07 [TABLES.include?('cont') \|\| FEOL & not PRECHECK_DRC] 5_14_cont.drc:53; Cnt.c.SRAM 0.006 [TABLES.include?('cont') \|\| FEOL & not PRECHECK_DRC] 5_14_cont.drc:70; Cnt.c.digibnd 0.05 [TABLES.include?('cont') \|\| FEOL & not PRECHECK_DRC] 5_14_cont.drc:62 | – | Cnt_c: Magic FUR, KLayout harness_main |
| Cnt.d | both | as Cnd.d 0.07 [FUR] :364 | Cnt.d 0.07 [TABLES.include?('cont') \|\| FEOL & not PRECHECK_DRC] 5_14_cont.drc:77 | – | Cnt_d: Magic FUR, KLayout harness_main |
| Cnt.e | both | 0.14 [FUR] :318 | Cnt.e 0.14 [TABLES.include?('cont') \|\| FEOL & not PRECHECK_DRC] 5_14_cont.drc:85 | – | Cnt_e: Magic FUR, KLayout harness_main |
| Cnt.f | both | 0.11 [FUR] :321; 0.11 [FUR] :323 | – | Cnt.f 0.11 sg13g2_maximal.drc:2263 | Cnt_f: Magic FUR, KLayout harness_maximal |
| Cnt.g | KLayout only | – | – | Cnt.g – sg13g2_maximal.drc:2266 | Cnt_g: Magic no, KLayout harness_maximal |
| Cnt.g1 | both | 0.09 [FUR] :382 | Cnt.g1 0.09 [TABLES.include?('cont') \|\| FEOL & not PRECHECK_DRC] 5_14_cont.drc:94 | – |  |
| Cnt.g2 | both | 0.09 [FUR] :384 | Cnt.g2 0.09 [TABLES.include?('cont') \|\| FEOL & not PRECHECK_DRC] 5_14_cont.drc:103 | – |  |
| Cnt.h | KLayout only | – | – | Cnt.h – sg13g2_maximal.drc:2269 | Cnt_h: Magic no, KLayout harness_maximal |
| Cnt.j | KLayout only | – | – | Cnt.j – sg13g2_maximal.drc:2272 | Cnt_j: Magic no, KLayout harness_maximal |
| CntB.a | KLayout only | – | CntB.a 0.16 [TABLES.include?('contbar') \|\| FEOL] 5_15_contbar.drc:31,32 | CntB.a 0.16 sg13g2_maximal.drc:2276 |  |
| CntB.a1 | KLayout only | – | CntB.a1 0.34 [TABLES.include?('contbar') \|\| FEOL] 5_15_contbar.drc:41 | CntB.a1 0.34 sg13g2_maximal.drc:2280 | CntB_a1: Magic no, KLayout harness_main,harness_maximal |
| CntB.b | in the deck, did not fire on its case: Magic reported nothing on CntB_b | 0.28 [FUR] :405 | – | CntB.b 0.28 sg13g2_maximal.drc:2283 | CntB_b: Magic no, KLayout harness_maximal |
| CntB.b1 | KLayout only | – | CntB.b1 0.36 [TABLES.include?('contbar') \|\| FEOL & not PRECHECK_DRC] 5_15_contbar.drc:50 | – |  |
| CntB.b2 | KLayout only | – | – | CntB.b2 0.22 sg13g2_maximal.drc:2286 | CntB_b2: Magic no, KLayout harness_maximal |
| CntB.c | KLayout only | – | – | CntB.c 0.07 sg13g2_maximal.drc:2289 |  |
| CntB.d | KLayout only | – | – | CntB.d 0.07 sg13g2_maximal.drc:2292 |  |
| CntB.e | KLayout only | – | – | CntB.e 0.14 sg13g2_maximal.drc:2295 |  |
| CntB.f | KLayout only | – | – | CntB.f 0.11 sg13g2_maximal.drc:2298 |  |
| CntB.g | KLayout only | – | – | CntB.g – sg13g2_maximal.drc:2301 |  |
| CntB.g1 | KLayout only | – | – | CntB.g1 0.09 sg13g2_maximal.drc:2304 |  |
| CntB.g2 | KLayout only | – | – | CntB.g2 0.09 sg13g2_maximal.drc:2307 |  |
| CntB.h | KLayout only | – | – | CntB.h – sg13g2_maximal.drc:2310 |  |
| CntB.h1 | in the deck, did not fire on its case: Magic reported nothing on CntB_h1 | 0.05 [FUR] :403 | CntB.h1 0.05 [TABLES.include?('contbar') \|\| FEOL & not PRECHECK_DRC] 5_15_contbar.drc:58 | – | CntB_h1: Magic no, KLayout harness_main |
| CntB.j | KLayout only | – | – | CntB.j – sg13g2_maximal.drc:2313 |  |
| exact_overlap | Magic only | – [FUR] :380; – [FUR] :464; – [FUR] :522; – [FUR] :580; – [FUR] :638; – [FUR] :696; 2 more | – | – |  |
| EXTB.a | KLayout only | – | – | EXTB.a 0.31 sg13g2_maximal.drc:2227 | EXTB_a: Magic no, KLayout harness_maximal |
| EXTB.b | KLayout only | – | – | EXTB.b 0.31 sg13g2_maximal.drc:2230 | EXTB_b: Magic no, KLayout harness_maximal |
| EXTB.c | both | 0.31 [U] :852 | – | EXTB.c 0.31 sg13g2_maximal.drc:2233 |  |
| forbidden.* | KLayout only | – | 11 names, e.g. forbidden.baspoly, forbidden.biwind, forbidden.colwind :43-43 | – | forbidden: Magic no, KLayout harness_main |
| Gat.a | both | 0.13 [FUR] :235 | Gat.a 0.13 [TABLES.include?('gatpoly') \|\| FEOL] 5_8_gatpoly.drc:32 | – | Gat_a: Magic FUR, KLayout harness_main |
| Gat.a1 | KLayout only | – | Gat.a1 0.13 [TABLES.include?('gatpoly') \|\| FEOL & not PRECHECK_DRC] 5_8_gatpoly.drc:55 | – | Gat_a1: Magic no, KLayout harness_main |
| Gat.a2 | KLayout only | – | Gat.a2 0.13 [TABLES.include?('gatpoly') \|\| FEOL & not PRECHECK_DRC] 5_8_gatpoly.drc:63 | – | Gat_a2: Magic no, KLayout harness_main |
| Gat.a3 | both | 0.45 [FUR] :216; 0.45 [FUR] :788; 0.3 [FUR] :791; 0.33 [FUR] :797 | – | Gat.a3 0.45 sg13g2_maximal.drc:2116 |  |
| Gat.a4 | both | 0.4 [FUR] :800 | – | Gat.a4 0.4 sg13g2_maximal.drc:2120 |  |
| Gat.b | both | 0.18 [FUR] :236 | Gat.b 0.18 [TABLES.include?('gatpoly') \|\| FEOL] 5_8_gatpoly.drc:39 | – | Gat_b: Magic FUR, KLayout harness_main |
| Gat.b1 | KLayout only | – | – | Gat.b1 0.25 sg13g2_maximal.drc:2123 | Gat_b1: Magic no, KLayout harness_maximal |
| Gat.c | both | 0.18 [FUR] :244; 0.13 [FUR] :246; 0.17 [FUR] :248 | – | Gat.c 0.18 sg13g2_maximal.drc:2127 | Gat_c: Magic FUR, KLayout harness_maximal |
| Gat.d | both | 0.07 [FUR] :238 | Gat.d 0.07 [TABLES.include?('gatpoly') \|\| FEOL] 5_8_gatpoly.drc:46 | – | Gat_d: Magic FUR, KLayout harness_main |
| Gat.e | both | 0.09 µm² [FUR] :256 | – | Gat.e 0.09 sg13g2_maximal.drc:2131 | Gat_e: Magic FUR, KLayout harness_maximal |
| Gat.f | both | – [FUR] :241 | – | Gat.f – sg13g2_maximal.drc:2134 |  |
| Gat.g | both | 0.16 [FUR] :254 | Gat.g 0.16 [TABLES.include?('gatpoly') \|\| FEOL & not PRECHECK_DRC] 5_8_gatpoly.drc:73 | – |  |
| grid.Acute | KLayout only | – | 193 names, e.g. activ_drw_Acute, activ_filler_Acute, activ_iopc_Acute :323-323 | – |  |
| grid.Angle45 | both | as x.2 45 [FUR] :252; 45 [FUR] :418; 45 [FUR] :476; 45 [FUR] :534; 45 [FUR] :592; 45 [FUR] :651; 2 more | 9 names, e.g. activ_drw_Angle45, gatpoly_drw_Angle45, metal1_drw_Angle45 :347-347 | – | angle_poly: Magic FUR, KLayout harness_main |
| grid.Angle90 | KLayout only | – | 8 names, e.g. cont_drw_Angle90, topvia1_drw_Angle90, topvia2_drw_Angle90 :335-335 | – |  |
| grid.Offgrid | KLayout only | – | 161 names, e.g. activ_drw_Offgrid, activ_filler_Offgrid, activ_iopc_Offgrid :46-46 | – |  |
| LU.a | both | 20 [U] :159 | – | LU.a 20 [latchUpRules] sg13g2_maximal.drc:2840 |  |
| LU.b | both | 20 [U] :155; 20 [U] :157 | LU.b 20 [TABLES.include?('latchup') \|\| FEOL & not PRECHECK_DRC] 7_2_latchup.drc:41 | – |  |
| LU.c | both | 6 [U] :161 | – | LU.c 6 [latchUpRules] sg13g2_maximal.drc:2847 |  |
| LU.c1 | both | as LU.c 6 [U] :161 | – | LU.c1 6 [latchUpRules] sg13g2_maximal.drc:2854 |  |
| LU.d | both | 6 [U] :163 | – | LU.d 6 [latchUpRules] sg13g2_maximal.drc:2861 |  |
| LU.d1 | both | as LU.d 6 [U] :163 | – | LU.d1 6 [latchUpRules] sg13g2_maximal.drc:2867 |  |
| M1.a | both | 0.16 [FUR] :413 | M1.a 0.16 [TABLES.include?('metal1') \|\| BEOL] 5_16_metal1.drc:32 | – | M1_a: Magic FUR, KLayout harness_main |
| M1.b | both | 0.18 [FUR] :414 | M1.b 0.18 [TABLES.include?('metal1') \|\| BEOL] 5_16_metal1.drc:39 | – | M1_b: Magic FUR, KLayout harness_main |
| M1.c | KLayout only | – | – | M1.c 0 sg13g2_maximal.drc:2316 | M1_c: Magic no, KLayout harness_maximal |
| M1.c1 | both | 0.05 [FUR] :367; 0.05 [FUR] :369; 0.05 [FUR] :371; 0.05 [FUR] :373; 0.05 [FUR] :375; 0.05 [FUR] :377 | – | M1.c1 0.05 sg13g2_maximal.drc:2322 |  |
| M1.d | both | 0.09 µm² [FUR] :416 | – | M1.d 0.09 sg13g2_maximal.drc:2325 | M1_d: Magic FUR, KLayout harness_maximal |
| M1.e | both | – [FU] :426; – [FU] :428 | M1.e 0.22 [TABLES.include?('metal1') \|\| BEOL & not PRECHECK_DRC] 5_16_metal1.drc:51 | – |  |
| M1.f | both | – [FU] :431; – [FU] :433 | M1.f 0.6 [TABLES.include?('metal1') \|\| BEOL & not PRECHECK_DRC] 5_16_metal1.drc:64 | – |  |
| M1.g | both | 0.2 [FUR] :420 | M1.g 0.2 [TABLES.include?('metal1') \|\| BEOL & not PRECHECK_DRC] 5_16_metal1.drc:76 | – |  |
| M1.i | KLayout only | – | M1.i 0.22 [TABLES.include?('metal1') \|\| BEOL & not PRECHECK_DRC] 5_16_metal1.drc:87 | – | M1_i: Magic no, KLayout harness_main |
| NBL.a | both | 1 [FU] :35 | – | NBL.a 1 sg13g2_maximal.drc:2059 |  |
| NBL.b | both | 1.5 [FU] :36 | NBL.b 1.5 [TABLES.include?('nbulay') \|\| FEOL & !PRECHECK_DRC && CONNECTIVITY_RULES] 5_3_nbulay.drc:35 | – |  |
| NBL.c | KLayout only | – | NBL.c 3.2 [TABLES.include?('nbulay') \|\| FEOL & !PRECHECK_DRC && CONNECTIVITY_RULES] 5_3_nbulay.drc:45 | – |  |
| NBL.d | both | 2.2 [FU] :40 | NBL.d 2.2 [TABLES.include?('nbulay') \|\| FEOL & !PRECHECK_DRC && CONNECTIVITY_RULES] 5_3_nbulay.drc:58 | – |  |
| NBL.e | both | 1 [FU] :42 | NBL.e 1 [TABLES.include?('nbulay') \|\| FEOL & !PRECHECK_DRC && CONNECTIVITY_RULES] 5_3_nbulay.drc:69 | – |  |
| NBL.f | both | 0.5 [FU] :44 | NBL.f 0.5 [TABLES.include?('nbulay') \|\| FEOL & !PRECHECK_DRC && CONNECTIVITY_RULES] 5_3_nbulay.drc:76 | – |  |
| NBLB.a | KLayout only | – | – | NBLB.a 1.5 sg13g2_maximal.drc:2062 |  |
| NBLB.b | KLayout only | – | – | NBLB.b 1 sg13g2_maximal.drc:2065 |  |
| NBLB.c | KLayout only | – | – | NBLB.c 1 sg13g2_maximal.drc:2068 |  |
| NBLB.d | KLayout only | – | – | NBLB.d 1.5 sg13g2_maximal.drc:2071 |  |
| nmosi.b | both | 1.24 [U] :52 | – | nmosi.b 1.24 sg13g2_maximal.drc:2643 |  |
| nmosi.c | both | – [U] :54 | – | nmosi.c 0.39 sg13g2_maximal.drc:2646 |  |
| nmosi.d | both | 0.62 [U] :60 | – | nmosi.d 0.62 sg13g2_maximal.drc:2649 |  |
| nmosi.f | KLayout only | – | – | nmosi.f 0.62 sg13g2_maximal.drc:2652 |  |
| nmosi.g | KLayout only | – | – | nmosi.g 0.15 sg13g2_maximal.drc:2657 |  |
| no_overlap | Magic only | – [FUR] :907 | – | – |  |
| nSDB.a | KLayout only | – | – | nSDB.a 0.31 sg13g2_maximal.drc:2215 | nSDB_a: Magic no, KLayout harness_maximal |
| nSDB.b | KLayout only | – | – | nSDB.b 0.31 sg13g2_maximal.drc:2218 | nSDB_b: Magic no, KLayout harness_maximal |
| nSDB.c | both | in (nSDB.c + overlaps) 0.66 [FUR] :221; in (nSDB.c + overlaps) 0.51 [FUR] :223; in (nSDB.c + overlaps) 0.69 [FUR] :225; in (nSDB.c + overlaps) 0.54 [FUR] :227 | – | nSDB.c 0.31 sg13g2_maximal.drc:2221 |  |
| nSDB.e | KLayout only | – | – | nSDB.e 0 sg13g2_maximal.drc:2224 |  |
| NW.a | both | 0.62 [FUR] :73 | – | NW.a 0.62 sg13g2_maximal.drc:2024 |  |
| NW.b | both | 0.62 [FUR] :76 | NW.b 0.62 [TABLES.include?('nwell') \|\| FEOL & !PRECHECK_DRC && CONNECTIVITY_RULES] 5_1_nwell.drc:33 | – |  |
| NW.b1 | KLayout only | – | NW.b1 1.8 [TABLES.include?('nwell') \|\| FEOL & !PRECHECK_DRC && CONNECTIVITY_RULES] 5_1_nwell.drc:44 | – | NW_b1: Magic no, KLayout harness_main |
| NW.c | both | 0.31 [FUR] :80; 0.27 [FUR] :87 | – | NW.c 0.31 sg13g2_maximal.drc:2027 | NW_c: Magic FUR, KLayout harness_maximal |
| NW.c1 | both | 0.62 [FUR] :93 | – | NW.c1 0.62 sg13g2_maximal.drc:2030; NW.c1.dig 0.31 sg13g2_maximal.drc:3042 |  |
| NW.d | both | 0.31 [FUR] :83; 0.27 [FUR] :89 | – | NW.d 0.31 sg13g2_maximal.drc:2033 | NW_d: Magic FUR, KLayout harness_maximal |
| NW.d1 | both | 0.62 [FUR] :95 | – | NW.d1 0.62 sg13g2_maximal.drc:2036; NW.d1.dig 0.31 sg13g2_maximal.drc:3045 |  |
| NW.e | both | 0.24 [FUR] :97 | – | NW.e 0.24 sg13g2_maximal.drc:2039 | NW_e: Magic FUR, KLayout harness_maximal |
| NW.e1 | both | 0.62 [FUR] :105; 0.62 [FUR] :112 | – | NW.e1 0.62 sg13g2_maximal.drc:2042; NW.e1.dig 0.24 sg13g2_maximal.drc:3048 |  |
| NW.f | both | 0.24 [FUR] :101 | – | NW.f 0.24 sg13g2_maximal.drc:2047 | NW_f: Magic FUR, KLayout harness_maximal |
| NW.f1 | both | 0.62 [FUR] :103 | NW.f1 0.62 [TABLES.include?('nwell') \|\| FEOL & !PRECHECK_DRC] 5_1_nwell.drc:63; NW.f1.digibnd 0.24 [TABLES.include?('nwell') \|\| FEOL & !PRECHECK_DRC] 5_1_nwell.drc:73 | – |  |
| Pin.a | KLayout only | – | Pin.a 0 [TABLES.include?('pin') \|\| PIN] 7_4_pin.drc:41 | – | Pin_a: Magic no, KLayout harness_main |
| Pin.b | KLayout only | – | Pin.b 0 [TABLES.include?('pin') \|\| PIN] 7_4_pin.drc:41 | – |  |
| Pin.e | KLayout only | – | Pin.e 0 [TABLES.include?('pin') \|\| PIN] 7_4_pin.drc:41 | – | Pin_e: Magic no, KLayout harness_main |
| Pin.f_M2 | KLayout only | – | Pin.f_M2 0 [TABLES.include?('pin') \|\| PIN] 7_4_pin.drc:41 | – |  |
| Pin.f_M3 | KLayout only | – | Pin.f_M3 0 [TABLES.include?('pin') \|\| PIN] 7_4_pin.drc:41 | – |  |
| Pin.f_M4 | KLayout only | – | Pin.f_M4 0 [TABLES.include?('pin') \|\| PIN] 7_4_pin.drc:41 | – |  |
| Pin.f_M5 | KLayout only | – | Pin.f_M5 0 [TABLES.include?('pin') \|\| PIN] 7_4_pin.drc:41 | – |  |
| Pin.g | KLayout only | – | Pin.g 0 [TABLES.include?('pin') \|\| PIN] 7_4_pin.drc:41 | – |  |
| Pin.h | KLayout only | – | Pin.h 0 [TABLES.include?('pin') \|\| PIN] 7_4_pin.drc:41 | – |  |
| pSD.a | KLayout only | – | – | pSD.a 0.31 sg13g2_maximal.drc:2156 | pSD_a: Magic no, KLayout harness_maximal |
| pSD.b | KLayout only | – | – | pSD.b 0.31 sg13g2_maximal.drc:2159 | pSD_b: Magic no, KLayout harness_maximal |
| pSD.c | folded: Magic checks it only inside a composite rule | in (Rsil.d + Rsil.e + pSD.c) 0.54 [FUR] :824 | – | pSD.c 0.18 sg13g2_maximal.drc:2162 | pSD_c: Magic no, KLayout harness_maximal |
| pSD.c1 | folded: Magic checks it only inside a composite rule | in (pSD.j + pSD.c1) 0.33 [FUR] :201; in (pSD.j1 + pSD.c1) 0.43 [FUR] :205; in (Seal.b - pSD.c1) 4.87 [U] :391; in (Rsil.d + Rsil.e + pSD.c1) 0.39 [FUR] :826 | pSD.c1 0.03 [TABLES.include?('psd') \|\| FEOL & not PRECHECK_DRC] 5_10_psd.drc:34 | – |  |
| pSD.d | KLayout only | – | – | pSD.d 0.18 sg13g2_maximal.drc:2165 | pSD_d: Magic no, KLayout harness_maximal |
| pSD.d1 | folded: Magic checks it only inside a composite rule | in (pSD.i + pSD.d1) 0.33 [FUR] :194; in (pSD.i1 + pSD.d1) 0.43 [FUR] :197 | – | pSD.d1 0.03 sg13g2_maximal.drc:2168 |  |
| pSD.e | both | as pSD.e/f 0.3 [U] :190 | – | pSD.e 0.3 sg13g2_maximal.drc:2175 |  |
| pSD.f | both | as pSD.e/f 0.3 [U] :190 | – | pSD.f 0.3 sg13g2_maximal.drc:2181 |  |
| pSD.g | both | 0.09 µm² [U] :189 | – | pSD.g 0.09 sg13g2_maximal.drc:2187 |  |
| pSD.i | both | in (pSD.i + pSD.d1) 0.33 [FUR] :194; 0.3 [FUR] :196; 0.3 [FUR] :199; 0.3 [FUR] :209 | – | pSD.i 0.3 sg13g2_maximal.drc:2191 | pSD_i_psd: Magic no, KLayout harness_maximal; pSD_i_tap: Magic FUR, KLayout harness_maximal |
| pSD.i1 | both | in (pSD.i1 + pSD.d1) 0.43 [FUR] :197; 0.4 [FUR] :210 | – | pSD.i1 0.4 sg13g2_maximal.drc:2194 |  |
| pSD.j | both | in (pSD.j + pSD.c1) 0.33 [FUR] :201; 0.3 [FUR] :203; 0.3 [FUR] :212 | – | pSD.j 0.3 sg13g2_maximal.drc:2197 |  |
| pSD.j1 | both | in (pSD.j1 + pSD.c1) 0.43 [FUR] :205; 0.4 [FUR] :213 | – | pSD.j1 0.4 sg13g2_maximal.drc:2200 |  |
| pSD.k | KLayout only | – | – | pSD.k 0.25 sg13g2_maximal.drc:2203 | pSD_k: Magic no, KLayout harness_maximal |
| pSD.l | KLayout only | – | – | pSD.l 0.25 sg13g2_maximal.drc:2206 | pSD_l: Magic no, KLayout harness_maximal |
| pSD.m | both | in (pSD.m + pSD.n) 0.36 [FUR] :844 | – | pSD.m 0.18 sg13g2_maximal.drc:2209 |  |
| pSD.n | folded: Magic checks it only inside a composite rule | in (pSD.m + pSD.n) 0.36 [FUR] :844 | – | pSD.n 0.18 sg13g2_maximal.drc:2212 |  |
| PWB.a | both | 0.62 [FUR] :118 | – | PWB.a 0.62 sg13g2_maximal.drc:2050 |  |
| PWB.b | both | as PWB.a 0.62 [FUR] :119 | – | PWB.b 0.62 sg13g2_maximal.drc:2053 | PWB_b: Magic FUR, KLayout harness_maximal |
| PWB.c | both | 0.62 [FUR] :120 | – | PWB.c 0.62 sg13g2_maximal.drc:2056 |  |
| PWB.e | both | 0.31 [FUR] :122 | PWB.e 0.31 [TABLES.include?('pwellblock') \|\| FEOL & not PRECHECK_DRC] 5_2_pwellblock.drc:34 | – |  |
| PWB.e1 | both | 0.62 [FUR] :124 | PWB.e1 0.62 [TABLES.include?('pwellblock') \|\| FEOL & not PRECHECK_DRC] 5_2_pwellblock.drc:44 | – |  |
| PWB.f | both | 0.24 [FUR] :126; 0.62 [FUR] :128 | PWB.f 0.24 [TABLES.include?('pwellblock') \|\| FEOL & not PRECHECK_DRC] 5_2_pwellblock.drc:54 | – |  |
| PWB.f1 | KLayout only | – | PWB.f1 0.62 [TABLES.include?('pwellblock') \|\| FEOL & not PRECHECK_DRC] 5_2_pwellblock.drc:65 | – |  |
| Rhi.a | both | 0.5 [FUR] :839 | – | Rhi.a 0.5 sg13g2_maximal.drc:2622 |  |
| Rhi.b | KLayout only | – | – | Rhi.b – sg13g2_maximal.drc:2625 |  |
| Rhi.c | KLayout only | – | – | Rhi.c 0.18 sg13g2_maximal.drc:2628 |  |
| Rhi.d | both | 0.2 [FUR] :840 | – | Rhi.d 0.2 sg13g2_maximal.drc:2633 |  |
| Rhi.e | KLayout only | – | – | Rhi.e 0.18 sg13g2_maximal.drc:2637 |  |
| Rhi.f | both | 0.5 [FUR] :842 | – | Rhi.f 0.5 sg13g2_maximal.drc:2640 |  |
| Rppd.a | both | 0.5 [FUR] :834 | – | Rppd.a 0.5 sg13g2_maximal.drc:2604 |  |
| Rppd.b | KLayout only | – | – | Rppd.b 0.18 sg13g2_maximal.drc:2607 |  |
| Rppd.c | both | 0.2 [FUR] :835 | – | Rppd.c 0.2 sg13g2_maximal.drc:2612 |  |
| Rppd.d | KLayout only | – | – | Rppd.d 0.18 sg13g2_maximal.drc:2616 |  |
| Rppd.e | both | 0.5 [FUR] :837 | – | Rppd.e 0.5 sg13g2_maximal.drc:2619 |  |
| Rsil.a | both | 0.5 [FUR] :819 | – | Rsil.a 0.5 sg13g2_maximal.drc:2585 |  |
| Rsil.b | both | 0.12 [FUR] :820 | – | Rsil.b 0.12 sg13g2_maximal.drc:2588 |  |
| Rsil.c | KLayout only | – | – | Rsil.c 0 sg13g2_maximal.drc:2592 |  |
| Rsil.d | both | in (Rsil.d + Rsil.e + pSD.c) 0.54 [FUR] :824; in (Rsil.d + Rsil.e + pSD.c1) 0.39 [FUR] :826 | – | Rsil.d 0.18 sg13g2_maximal.drc:2595 |  |
| Rsil.e | folded: Magic checks it only inside a composite rule | in (Rsil.d + Rsil.e + pSD.c) 0.54 [FUR] :824; in (Rsil.d + Rsil.e + pSD.c1) 0.39 [FUR] :826 | – | Rsil.e 0.18 sg13g2_maximal.drc:2598 |  |
| Rsil.f | both | 0.5 [FUR] :822 | – | Rsil.f 0.5 sg13g2_maximal.drc:2601 |  |
| Sal.a | KLayout only | – | – | Sal.a 0.42 sg13g2_maximal.drc:2236 | Sal_a: Magic no, KLayout harness_maximal |
| Sal.b | both | 0.42 [FUR] :846 | – | Sal.b 0.42 sg13g2_maximal.drc:2239 |  |
| Sal.c | both | in (Sal.c + Sal.d) 0.4 [FUR] :863; in (Sal.c + Sal.d) 0.4 [FUR] :865; in (Sal.c + Sal.d) 0.48 [FUR] :868; in (Sal.c + Sal.d) 0.48 [FUR] :870; in (Sal.c + Sal.d) 0.52 [FUR] :873; in (Sal.c + Sal.d) 0.52 [FUR] :875; 2 more | – | Sal.c 0.2 sg13g2_maximal.drc:2243 |  |
| Sal.d | both | in (Sal.c + Sal.d) 0.4 [FUR] :863; in (Sal.c + Sal.d) 0.4 [FUR] :865; in (Sal.c + Sal.d) 0.48 [FUR] :868; in (Sal.c + Sal.d) 0.48 [FUR] :870; in (Sal.c + Sal.d) 0.52 [FUR] :873; in (Sal.c + Sal.d) 0.52 [FUR] :875; 3 more | – | Sal.d 0.2 sg13g2_maximal.drc:2248 |  |
| Sal.e | KLayout only | – | – | Sal.e 0.2 sg13g2_maximal.drc:2252 | Sal_e: Magic no, KLayout harness_maximal |
| TGO.a | KLayout only | – | – | TGO.a 0.27 sg13g2_maximal.drc:2099 | TGO_a: Magic no, KLayout harness_maximal |
| TGO.b | KLayout only | – | – | TGO.b 0.27 sg13g2_maximal.drc:2102 | TGO_b: Magic no, KLayout harness_maximal |
| TGO.c | both | 0.34 [FUR] :806; 0.34 [FUR] :808 | – | TGO.c 0.34 sg13g2_maximal.drc:2106 |  |
| TGO.d | both | 0.34 [FUR] :810; 0.34 [FUR] :812 | – | TGO.d 0.34 sg13g2_maximal.drc:2109 |  |
| TGO.e | KLayout only | – | – | TGO.e 0.86 sg13g2_maximal.drc:2112 | TGO_e: Magic no, KLayout harness_maximal |
| TGO.f | KLayout only | – | TGO.f 0.86 [TABLES.include?('thickgateox') \|\| FEOL] 5_7_thickgateox.drc:32 | – | TGO_f: Magic no, KLayout harness_main |
| V1.a | in the deck, did not fire on its case: Magic reported nothing on V1_a, V1_big | in (V1.a + 2 * M2.c) 0.2 [FUR] :455 | V1.a 0.19 [TABLES.include?('via1') \|\| BEOL] 5_19_via1.drc:37 | – | V1_a: Magic no, KLayout harness_main; V1_big: Magic no, KLayout harness_main |
| V1.b | in the deck, did not fire on its case: Magic reported nothing on V1_b | in (V1.b - 2 * M2.c) 0.21 [FUR] :456 | V1.b 0.22 [TABLES.include?('via1') \|\| BEOL] 5_19_via1.drc:47 | – | V1_b: Magic no, KLayout harness_main |
| V1.b1 | KLayout only | – | – | V1.b1 0.29 sg13g2_maximal.drc:2450 | V1_b1: Magic no, KLayout harness_maximal |
| V1.c | both | in (V1.c - M2.c) 0.005 [FUR] :457 | V1.c 0.01 [TABLES.include?('via1') \|\| BEOL & not PRECHECK_DRC] 5_19_via1.drc:55 | – | V1_c: Magic FUR, KLayout harness_main |
| V1.c1 | both | in (V1.c1 - M2.c) 0.045 [FUR] :459 | – | V1.c1 0.05 sg13g2_maximal.drc:2457 |  |

### Other layers

| Rule | Status | Magic: value [styles] :line | main: name value [switch] :line | maximal: name value [switch] :line | Tested (case: what each engine reported) |
|---|---|---|---|---|---|
| AFil.a | both | 5 [U] :167 | – | AFil.a 5 [fillerRules] sg13g2_maximal.drc:2085 |  |
| AFil.a1 | both | 1 [U] :166 | – | AFil.a1 1 [fillerRules] sg13g2_maximal.drc:2088 |  |
| AFil.b | both | 0.42 [U] :168 | – | AFil.b 0.42 [fillerRules] sg13g2_maximal.drc:2091 |  |
| AFil.c | both | 1.1 [U] :172; 1.1 [U] :174; 1.1 [U] :176 | AFil.c 1.1 [TABLES.include?('activfiller') \|\| FEOL & not PRECHECK_DRC] 5_6_activfiller.drc:49 | – |  |
| AFil.c1 | both | 0.42 [U] :170 | AFil.c1 0.42 [TABLES.include?('activfiller') \|\| FEOL] 5_6_activfiller.drc:41 | – |  |
| AFil.d | both | 1 [U] :178; 1 [U] :180 | AFil.d 1 [TABLES.include?('activfiller') \|\| FEOL & not PRECHECK_DRC] 5_6_activfiller.drc:60 | – |  |
| AFil.e | both | 1 [U] :182 | AFil.e 1 [TABLES.include?('activfiller') \|\| FEOL & not PRECHECK_DRC] 5_6_activfiller.drc:71 | – |  |
| AFil.i | both | 1.5 [FUR] :130; 1.5 [FUR] :132 | – | AFil.i 1.5 [fillerRules] sg13g2_maximal.drc:2094 |  |
| AFil.i.angle | same name for another check: Magic prints AFil.i for a rule that allows only 90-degree angles on Activ fill, which IHP's SG13G2 layout rules (Rev. 0.4) do not have; their AFil.i, which the maximal deck checks, is the 1.50 µm Activ:filler space to PWell:block (row AFil.i). KLayout checks Activ:filler for acute angles only | as AFil.i 90 [U] :184 | – | – |  |
| AFil.j | KLayout only | – | AFil.j 0.25 [TABLES.include?('activfiller') \|\| FEOL & not PRECHECK_DRC] 5_6_activfiller.drc:82 | – |  |
| GFil.a | both | 5 [FUR] :261 | – | GFil.a 5 [fillerRules] sg13g2_maximal.drc:2139 |  |
| GFil.b | both | 0.7 [FUR] :260 | – | GFil.b 0.7 [fillerRules] sg13g2_maximal.drc:2142 |  |
| GFil.c | both | 0.8 [FUR] :262 | – | GFil.c 0.8 [fillerRules] sg13g2_maximal.drc:2145 |  |
| GFil.d | both | 1.1 [FUR] :265 | GFil.d 1.1 [TABLES.include?('gatpolyfiller') \|\| FEOL] 5_9_gatpolyfiller.drc:41 | – |  |
| GFil.e | both | 1.1 [FUR] :267; 1.1 [FUR] :269; 1.1 [FUR] :271; 1.1 [FUR] :273 | GFil.e 1.1 [TABLES.include?('gatpolyfiller') \|\| FEOL & not PRECHECK_DRC] 5_9_gatpolyfiller.drc:51 | – |  |
| GFil.f | both | 1.1 [FUR] :275 | – | GFil.f 1.1 [fillerRules] sg13g2_maximal.drc:2148 |  |
| GFil.i | KLayout only | – | GFil.i 400 [TABLES.include?('gatpolyfiller') \|\| FEOL & not PRECHECK_DRC] 5_9_gatpolyfiller.drc:58 | – |  |
| GFil.j | both | 0.18 [FUR] :277 | – | GFil.j 0.18 [fillerRules] sg13g2_maximal.drc:2151 |  |
| GFil.k | Magic only | 90 [FUR] :278 | – | – |  |
| LBE.a | KLayout only | – | LBE.a 100 [TABLES.include?('lbe') \|\| BEOL] 9_1_lbe.drc:33 | – |  |
| LBE.b | KLayout only | – | LBE.b 1500 [TABLES.include?('lbe') \|\| BEOL] 9_1_lbe.drc:40 | – |  |
| LBE.b1 | KLayout only | – | LBE.b1 250000 [TABLES.include?('lbe') \|\| BEOL] 9_1_lbe.drc:47 | – |  |
| LBE.b2 | KLayout only | – | – | LBE.b2 30000 sg13g2_maximal.drc:3051 |  |
| LBE.c | KLayout only | – | LBE.c 100 [TABLES.include?('lbe') \|\| BEOL] 9_1_lbe.drc:54 | – |  |
| LBE.d | KLayout only | – | LBE.d 150 [TABLES.include?('lbe') \|\| BEOL] 9_1_lbe.drc:61 | – |  |
| LBE.e | KLayout only | – | – | LBE.e.Passiv 50 sg13g2_maximal.drc:3057; LBE.e.dfPad 50 sg13g2_maximal.drc:3054 |  |
| LBE.f | KLayout only | – | – | LBE.f 30 sg13g2_maximal.drc:3060 |  |
| LBE.h | KLayout only | – | LBE.h – [TABLES.include?('lbe') \|\| BEOL] 9_1_lbe.drc:67 | – |  |
| M2.a | both | 0.2 [FUR] :472 | M2.a 0.2 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:41 | – |  |
| M2.b | both | 0.21 [FUR] :473 | M2.b 0.21 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:48 | – |  |
| M2.c | folded: Magic checks it only inside a composite rule | in (V1.a + 2 * M2.c) 0.2 [FUR] :455; in (V1.b - 2 * M2.c) 0.21 [FUR] :456; in (V1.c - M2.c) 0.005 [FUR] :457; in (V1.c1 - M2.c) 0.045 [FUR] :459; in (M2.c1 - M2.c) 0.045 [FUR] :461 | – | M2.c 0.005 sg13g2_maximal.drc:2329 |  |
| M2.c1 | both | in (M2.c1 - M2.c) 0.045 [FUR] :461 | – | M2.c1 0.05 sg13g2_maximal.drc:2335 |  |
| M2.d | both | 0.144 µm² [FUR] :474 | – | M2.d 0.144 sg13g2_maximal.drc:2338 |  |
| M2.e | both | – [FU] :484; – [FU] :486 | M2.e 0.24 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:60 | – |  |
| M2.f | both | – [FU] :489; – [FU] :491 | M2.f 0.6 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:72 | – |  |
| M2.g | both | 0.24 [FUR] :478 | M2.g 0.24 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:84 | – |  |
| M2.i | KLayout only | – | M2.i 0.24 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:95 | – |  |
| M3.a | both | 0.2 [FUR] :530 | M3.a 0.2 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:41 | – |  |
| M3.b | both | 0.21 [FUR] :531 | M3.b 0.21 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:48 | – |  |
| M3.c | KLayout only | – | – | M3.c 0.005 sg13g2_maximal.drc:2342 |  |
| M3.c1 | both | in (M3.c1 - V2.c) 0.045 [FUR] :519 | – | M3.c1 0.05 sg13g2_maximal.drc:2348 |  |
| M3.d | both | 0.144 µm² [FUR] :532 | – | M3.d 0.144 sg13g2_maximal.drc:2351 |  |
| M3.e | both | – [FU] :542; – [FU] :544 | M3.e 0.24 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:60 | – |  |
| M3.f | both | – [FU] :547; – [FU] :549 | M3.f 0.6 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:72 | – |  |
| M3.g | both | 0.24 [FUR] :536 | M3.g 0.24 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:84 | – |  |
| M3.i | KLayout only | – | M3.i 0.24 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:95 | – |  |
| M4.a | both | 0.2 [FUR] :588 | M4.a 0.2 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:41 | – |  |
| M4.b | both | 0.21 [FUR] :589 | M4.b 0.21 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:48 | – |  |
| M4.c | KLayout only | – | – | M4.c 0.005 sg13g2_maximal.drc:2355 |  |
| M4.c1 | both | in (M4.c1 - V3.c) 0.045 [FUR] :577 | – | M4.c1 0.05 sg13g2_maximal.drc:2361 |  |
| M4.d | both | 0.144 µm² [FUR] :590 | – | M4.d 0.144 sg13g2_maximal.drc:2364 |  |
| M4.e | both | – [FU] :600; – [FU] :602 | M4.e 0.24 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:60 | – |  |
| M4.f | both | – [FU] :605; – [FU] :607 | M4.f 0.6 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:72 | – |  |
| M4.g | both | 0.24 [FUR] :594 | M4.g 0.24 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:84 | – |  |
| M4.i | KLayout only | – | M4.i 0.24 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:95 | – |  |
| M5.a | both | 0.2 [FUR] :646 | M5.a 0.2 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:41 | – |  |
| M5.b | both | 0.21 [FUR] :647; in (MIM.c + MIM.d + M5.b) 1.117 [FUR] :908 | M5.b 0.21 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:48 | – |  |
| M5.c | KLayout only | – | – | M5.c 0.005 sg13g2_maximal.drc:2368 |  |
| M5.c1 | both | in (M5.c1 - V4.c) 0.045 [FUR] :635 | – | M5.c1 0.05 sg13g2_maximal.drc:2374 |  |
| M5.d | both | 0.144 µm² [FUR] :649 | – | M5.d 0.144 sg13g2_maximal.drc:2377 |  |
| M5.e | both | – [FU] :659; – [FU] :661 | M5.e 0.24 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:60 | – |  |
| M5.f | both | – [FU] :664; – [FU] :666 | M5.f 0.6 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:72 | – |  |
| M5.g | both | 0.24 [FUR] :653 | M5.g 0.24 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:84 | – |  |
| M5.i | KLayout only | – | M5.i 0.24 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:95 | – |  |
| MFil.a1 | both | 1 [FUR] :437; 1 [FUR] :495; 1 [FUR] :553; 1 [FUR] :611; 1 [FUR] :670 | – | 5 names, e.g. M1Fil.a1, M2Fil.a1, M3Fil.a1 :2383-2432 |  |
| MFil.a2 | both | 5 [FUR] :438; 5 [FUR] :496; 5 [FUR] :554; 5 [FUR] :612; 5 [FUR] :671 | 5 names, e.g. M1Fil.a2, M2Fil.a2, M3Fil.a2 :57-57 | – |  |
| MFil.b | both | 0.42 [FUR] :439; 0.42 [FUR] :497; 0.42 [FUR] :555; 0.42 [FUR] :613; 0.42 [FUR] :672 | 5 names, e.g. M1Fil.b, M2Fil.b, M3Fil.b :48-48 | 5 names, e.g. M1Fil.b, M2Fil.b, M3Fil.b :2386-2435 |  |
| MFil.c | both | 0.42 [FUR] :440; 0.42 [FUR] :498; 0.42 [FUR] :556; 0.42 [FUR] :614; 0.42 [FUR] :673 | 5 names, e.g. M1Fil.c, M2Fil.c, M3Fil.c :47-47 | – |  |
| MFil.d | both | 1 [FUR] :442; 1 [FUR] :500; 1 [FUR] :558; 1 [FUR] :616; 1 [FUR] :675 | – | 5 names, e.g. M1Fil.d, M2Fil.d, M3Fil.d :2389-2438 |  |
| MFil.i | Magic only | 90 [FUR] :444; 90 [FUR] :502; 90 [FUR] :560; 90 [FUR] :618; 90 [FUR] :677 | – | – |  |
| MIM.a | both | 1.14 [FUR] :890 | MIM.a 1.14 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:41 | MIM.a 1.14 sg13g2_maximal.drc:2819 |  |
| MIM.b | both | 0.6 [FUR] :891 | MIM.b 0.6 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:48 | MIM.b 0.6 sg13g2_maximal.drc:2822 |  |
| MIM.c | both | 0.6 [FUR] :894; in (MIM.c + MIM.d + M5.b) 1.117 [FUR] :908 | MIM.c 0.6 [TABLES.include?('mim') \|\| BEOL & not PRECHECK_DRC] 6_11_mim.drc:35 | – |  |
| MIM.d | folded: Magic checks it only inside a composite rule | in (TV1.a + 2 * MIM.d) 1.14 [FUR] :903; in (MIM.c + MIM.d + M5.b) 1.117 [FUR] :908 | MIM.d 0.36 [TABLES.include?('mim') \|\| BEOL & not PRECHECK_DRC] 6_11_mim.drc:44 | – |  |
| MIM.e | both | 0.6 [U] :920 | MIM.e 0.6 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:60 | MIM.e 0.6 sg13g2_maximal.drc:2825 |  |
| MIM.f | both | 1.3 µm² [FUR] :897 | MIM.f 1.3 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:72 | MIM.f 1.3 sg13g2_maximal.drc:2828 |  |
| MIM.g | KLayout only | – | MIM.g 5625 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:84 | MIM.g 5625 sg13g2_maximal.drc:2831 |  |
| MIM.h | both | – [U] :917 | – | MIM.h – sg13g2_maximal.drc:2834 |  |
| MIM.i | Magic only | 0.81 [FUR] :913 | – | – |  |
| MIM.rect | Magic only | – [FUR] :892 | – | – |  |
| No unrelated diffusion or well may exist in the NPN area () | Magic only | – [U] :953 | – | – |  |
| npn13G2.a | both | 0.9 [FUR] :931; 0.063 µm² [FUR] :932 | – | npn13G2.a 0.9 sg13g2_maximal.drc:2570 |  |
| npn13G2.bR | KLayout only | – | npn13G2.bR – [TABLES.include?('npnsubstratetie') \|\| FEOL & not PRECHECK_DRC & RECOMMENDED] 6_1_npnsubstratetie.drc:35 | – |  |
| npn13G2.w | Magic only | 0.07 [FUR] :929; 0.07 [FUR] :930 | – | – |  |
| npn13G2L.a | both | 0.07 µm² [FUR] :938 | – | npn13G2L.a 1 sg13g2_maximal.drc:2573 |  |
| npn13G2L.b | both | 2.5 [FUR] :937 | – | npn13G2L.b 2.5 sg13g2_maximal.drc:2576 |  |
| npn13G2L.cR | KLayout only | – | npn13G2L.cR – [TABLES.include?('npnsubstratetie') \|\| FEOL & not PRECHECK_DRC & RECOMMENDED] 6_1_npnsubstratetie.drc:45 | – |  |
| npn13G2L.w | Magic only | 0.07 [FUR] :935; 0.07 [FUR] :936 | – | – |  |
| npn13G2V.a | both | 0.12 µm² [FUR] :944 | – | npn13G2V.a 1 sg13g2_maximal.drc:2579 |  |
| npn13G2V.b | both | 5 [FUR] :943 | – | npn13G2V.b 5 sg13g2_maximal.drc:2582 |  |
| npn13G2V.cR | KLayout only | – | npn13G2V.cR – [TABLES.include?('npnsubstratetie') \|\| FEOL & not PRECHECK_DRC & RECOMMENDED] 6_1_npnsubstratetie.drc:55 | – |  |
| npn13G2V.w | Magic only | 0.12 [FUR] :941; 0.12 [FUR] :942 | – | – |  |
| npnG2.b | KLayout only | – | – | npnG2.b – sg13g2_maximal.drc:2540 |  |
| npnG2.c | KLayout only | – | – | npnG2.c 0.2 sg13g2_maximal.drc:2543 |  |
| npnG2.d | both | 1.21 [U] :947 | – | 5 names, e.g. npnG2.d.NWell, npnG2.d.N_Activ, npnG2.d.PWell_block :2546-2558 |  |
| npnG2.d1 | both | 0.9 [U] :949; 0.27 [U] :951 | – | npnG2.d1 0.9 sg13g2_maximal.drc:2561 |  |
| npnG2.d2 | KLayout only | – | – | npnG2.d2 0.9 sg13g2_maximal.drc:2564 |  |
| npnG2.e | KLayout only | – | – | npnG2.e 0.27 sg13g2_maximal.drc:2567 |  |
| Pad.a1 | both | 150 [U] :979 | – | Pad.a1 150 sg13g2_maximal.drc:2669 |  |
| Pad.aR | both | 30 [U] :978 | – | Pad.aR 30 [recommendedRules] sg13g2_maximal.drc:2664 |  |
| Pad.bR | both | 8.4 [U] :980 | – | Pad.bR 8.4 [recommendedRules] sg13g2_maximal.drc:2674 |  |
| Pad.d | both | 7.5 [U] :981 | – | Pad.d 7.5 sg13g2_maximal.drc:2679 |  |
| Pad.d1R | KLayout only | – | – | Pad.d1R 11.2 [recommendedRules] sg13g2_maximal.drc:2687 |  |
| Pad.dR | KLayout only | – | – | Pad.dR 25 [recommendedRules] sg13g2_maximal.drc:2684 |  |
| Pad.fR | KLayout only | – | 7 names, e.g. Pad.fR_M1, Pad.fR_M2, Pad.fR_M3 :57-57 | – |  |
| Pad.gR | KLayout only | – | – | Pad.gR 1.4 [recommendedRules] sg13g2_maximal.drc:2690 |  |
| Pad.i | KLayout only | – | Pad.i – [TABLES.include?('pad') \|\| BEOL & not PRECHECK_DRC] 6_9_pad.drc:69 | – |  |
| Pad.jR | KLayout only | – | – | Pad.jR – [recommendedRules] sg13g2_maximal.drc:2694 |  |
| Pad.kR | KLayout only | – | – | Pad.kR – [recommendedRules] sg13g2_maximal.drc:2698 |  |
| Pad.m | KLayout only | – | Pad.m – [TABLES.include?('pad') \|\| BEOL] 6_9_pad.drc:32 | – |  |
| Padb.a | both | 60 [U] :983; 60 [U] :984 | Padb.a 60 [TABLES.include?('solderbump') \|\| BEOL] 6_9_solderbump.drc:34 | – |  |
| Padb.b | both | 70 [U] :985 | Padb.b 70 [TABLES.include?('solderbump') \|\| BEOL] 6_9_solderbump.drc:43 | – |  |
| Padb.c | both | 10 [U] :767 | Padb.c 10 [TABLES.include?('solderbump') \|\| BEOL] 6_9_solderbump.drc:52 | – |  |
| Padb.d | both | 50 [U] :986 | Padb.d 50 [TABLES.include?('solderbump') \|\| BEOL & not PRECHECK_DRC] 6_9_solderbump.drc:72 | – |  |
| padb.f | KLayout only | – | padb.f – [TABLES.include?('solderbump') \|\| BEOL] 6_9_solderbump.drc:62 | – |  |
| Padc.a | both | 35 [U] :989; 45 [U] :990 | Padc.a 35 [TABLES.include?('copperpillar') \|\| BEOL] 6_9_copperpillar.drc:34 | – |  |
| Padc.b | both: Magic prints this 40 µm pad spacing as Padc.e; in IHP's SG13G2 layout rules (Rev. 0.4) it is Padc.b, and their Padc.e is the CuPillarPad pitch, which neither tool checks | as Padc.e 40 [U] :991 | Padc.b 40 [TABLES.include?('copperpillar') \|\| BEOL] 6_9_copperpillar.drc:43 | – |  |
| Padc.c | both | 7.5 [U] :765 | Padc.c 7.5 [TABLES.include?('copperpillar') \|\| BEOL] 6_9_copperpillar.drc:52 | – |  |
| Padc.d | both | 30 [U] :992 | – | Padc.d 30 sg13g2_maximal.drc:2703 |  |
| padc.f | KLayout only | – | padc.f – [TABLES.include?('copperpillar') \|\| BEOL] 6_9_copperpillar.drc:61 | – |  |
| Pas.a | KLayout only | – | Pas.a 2.1 [TABLES.include?('passiv') \|\| BEOL] 5_27_passiv.drc:32 | – |  |
| Pas.b | KLayout only | – | Pas.b 3.5 [TABLES.include?('passiv') \|\| BEOL] 5_27_passiv.drc:39 | – |  |
| Pas.c | both | 2.1 [U] :769 | Pas.c 2.1 [TABLES.include?('passiv') \|\| BEOL & not PRECHECK_DRC] 5_27_passiv.drc:50 | – |  |
| Sdiod.a | KLayout only | – | – | Sdiod.a 0.25 sg13g2_maximal.drc:2660 |  |
| Sdiod.b | KLayout only | – | Sdiod.b 0.4 [TABLES.include?('schottkydiode') \|\| FEOL & not PRECHECK_DRC] 6_7_schottkydiode.drc:41 | – |  |
| Sdiod.c | both | 0.45 [FUR] :966 | Sdiod.c 0.45 [TABLES.include?('schottkydiode') \|\| FEOL & not PRECHECK_DRC] 6_7_schottkydiode.drc:56 | – |  |
| Sdiod.d | both | 0.3 [FUR] :961; 0.3 [FUR] :962 | Sdiod.d 0.3 [TABLES.include?('schottkydiode') \|\| FEOL & not PRECHECK_DRC] 6_7_schottkydiode.drc:66 | – |  |
| Sdiod.e | both | 1 [FUR] :963; 0.03 µm² [FUR] :964 | Sdiod.e 1 [TABLES.include?('schottkydiode') \|\| FEOL & not PRECHECK_DRC] 6_7_schottkydiode.drc:73 | – |  |
| Seal.a | both | 3.5 [U] :388; 3.5 [U] :448; 3.5 [U] :506; 3.5 [U] :564; 3.5 [U] :622; 3.5 [U] :682; 2 more | – | 9 names, e.g. Seal.a_Activ, Seal.a_Metal1, Seal.a_Metal2 :2706-2730 |  |
| Seal.b | both | 4.9 [U] :389; in (Seal.b - pSD.c1) 4.87 [U] :391 | 9 names, e.g. Seal.b_activ, Seal.b_metal1, Seal.b_metal2 :96-96 | – |  |
| Seal.c | both | 0.16 [FUR] :300 | – | Seal.c 0.16 sg13g2_maximal.drc:2734 |  |
| Seal.c1 | both: Magic checks only the minimum width of the Via1-Via4 seal rings; the maximal deck also flags rings wider than 0.19 µm | 0.19 [FUR] :466; 0.19 [FUR] :524; 0.19 [FUR] :582; 0.19 [FUR] :640 | – | Seal.c1.Via1 0.19 sg13g2_maximal.drc:2739; Seal.c1.Via2 0.19 sg13g2_maximal.drc:2744; Seal.c1.Via3 0.19 sg13g2_maximal.drc:2749; Seal.c1.Via4 0.19 sg13g2_maximal.drc:2754 |  |
| Seal.c2 | both | 0.42 [FUR] :698 | – | Seal.c2 0.42 sg13g2_maximal.drc:2759 |  |
| Seal.c3 | both | 0.9 [FUR] :733 | – | Seal.c3 0.9 sg13g2_maximal.drc:2764 |  |
| Seal.d | both: Magic checks the Activ enclosure of the EdgeSeal-Cont ring only; the maximal deck checks it for the Cont, Via1-Via4, TopVia1 and TopVia2 rings | 1.3 [FUR] :302 | – | 7 names, e.g. Seal.d.Cont, Seal.d.TopVia1, Seal.d.TopVia2 :2768-2786 |  |
| Seal.e | both | 4.2 [FUR] :973 | – | Seal.e 4.2 sg13g2_maximal.drc:2789 |  |
| Seal.f | both: Magic's statement lists pdiff and m1-m6, not m7 (TopMetal2); the maximal deck checks EdgeSeal Activ, pSD, Metal1-Metal5, TopMetal1 and TopMetal2, and pSD is not in the layout rules' Seal.f list | 1 [FUR] :974 | – | 9 names, e.g. Seal.f.Activ, Seal.f.Metal1, Seal.f.Metal2 :2792-2816 |  |
| Seal.k | KLayout only | – | Seal.k 21 [TABLES.include?('sealring') \|\| BEOL & not PRECHECK_DRC] 6_10_sealring.drc:107 | – |  |
| Seal.m | KLayout only | – | Seal.m – [TABLES.include?('sealring') \|\| BEOL & not PRECHECK_DRC] 6_10_sealring.drc:115 | – |  |
| Seal.n | KLayout only | – | Seal.n – [TABLES.include?('sealring') \|\| BEOL] 6_10_sealring.drc:80 | – |  |
| Slt.a | KLayout only | – | – | 7 names, e.g. Slt.a.M1, Slt.a.M2, Slt.a.M3 :2872-3020 |  |
| Slt.b | KLayout only | – | – | 7 names, e.g. Slt.b.M1, Slt.b.M2, Slt.b.M3 :2876-3024 |  |
| Slt.c | both | 30 [U] :447; 30 [U] :505; 30 [U] :563; 30 [U] :621; 30 [U] :719; 30 [U] :776 | – | 7 names, e.g. Slt.c.M1, Slt.c.M2, Slt.c.M3 :2882-3030 |  |
| Slt.e | KLayout only | – | – | 7 names, e.g. Slt.e.M1, Slt.e.M2, Slt.e.M3 :2885-3033 |  |
| Slt.e1_M1 | KLayout only | – | Slt.e1_M1 – [TABLES.include?('metalslits') \|\| BEOL & not PRECHECK_DRC] 7_3_metalslits.drc:37 | – |  |
| Slt.e1_M2 | KLayout only | – | Slt.e1_M2 – [TABLES.include?('metalslits') \|\| BEOL & not PRECHECK_DRC] 7_3_metalslits.drc:37 | – |  |
| Slt.e1_M3 | KLayout only | – | Slt.e1_M3 – [TABLES.include?('metalslits') \|\| BEOL & not PRECHECK_DRC] 7_3_metalslits.drc:37 | – |  |
| Slt.e1_M4 | KLayout only | – | Slt.e1_M4 – [TABLES.include?('metalslits') \|\| BEOL & not PRECHECK_DRC] 7_3_metalslits.drc:37 | – |  |
| Slt.e1_M5 | KLayout only | – | Slt.e1_M5 – [TABLES.include?('metalslits') \|\| BEOL & not PRECHECK_DRC] 7_3_metalslits.drc:37 | – |  |
| Slt.e1_TM1 | KLayout only | – | Slt.e1_TM1 – [TABLES.include?('metalslits') \|\| BEOL & not PRECHECK_DRC] 7_3_metalslits.drc:37 | – |  |
| Slt.e1_TM2 | KLayout only | – | Slt.e1_TM2 – [TABLES.include?('metalslits') \|\| BEOL & not PRECHECK_DRC] 7_3_metalslits.drc:37 | – |  |
| Slt.f | KLayout only | – | – | 7 names, e.g. Slt.f.M1, Slt.f.M2, Slt.f.M3 :2888-3036 |  |
| Slt.g | KLayout only | – | – | Slt.g.M5 0.6 sg13g2_maximal.drc:2987; Slt.g.TM1 0.6 sg13g2_maximal.drc:3014 |  |
| Slt.h1 | KLayout only | – | – | Slt.h1 0.3 sg13g2_maximal.drc:2892 |  |
| Slt.h2 | KLayout only | – | – | Slt.h2.M2 0.3 sg13g2_maximal.drc:2916; Slt.h2.M3 0.3 sg13g2_maximal.drc:2940; Slt.h2.M4 0.3 sg13g2_maximal.drc:2964; Slt.h2.M5 0.3 sg13g2_maximal.drc:2991 |  |
| Slt.h3 | KLayout only | – | – | Slt.h3 1 sg13g2_maximal.drc:3017 |  |
| Slt.h4 | KLayout only | – | – | Slt.h4 1 sg13g2_maximal.drc:3039 |  |
| TM1.a | both | 1.64 [FUR] :704 | TM1.a 1.64 [TABLES.include?('topmetal1') \|\| BEOL] 5_22_topmetal1.drc:32 | – |  |
| TM1.b | both | 1.64 [FUR] :705 | TM1.b 1.64 [TABLES.include?('topmetal1') \|\| BEOL] 5_22_topmetal1.drc:39 | – |  |
| TM1Fil.a | both | 5 [FUR] :709 | – | TM1Fil.a 5 [fillerRules] sg13g2_maximal.drc:2517 |  |
| TM1Fil.a1 | both | 10 [FUR] :710 | TM1Fil.a1 10 [TABLES.include?('topmetal1filler') \|\| BEOL & not PRECHECK_DRC] 5_23_topmetal1filler.drc:47 | – |  |
| TM1Fil.b | both | 3 [FUR] :711 | – | TM1Fil.b 3 [fillerRules] sg13g2_maximal.drc:2520 |  |
| TM1Fil.c | both | 3 [FUR] :712 | TM1Fil.c 3 [TABLES.include?('topmetal1filler') \|\| BEOL] 5_23_topmetal1filler.drc:39 | – |  |
| TM1Fil.d | both | 4.9 [FUR] :714 | – | TM1Fil.d 4.9 [fillerRules] sg13g2_maximal.drc:2523 |  |
| TM1Fil.g | Magic only | 90 [FUR] :716 | – | – |  |
| TM2.a | both | 2 [FUR] :739 | TM2.a 2 [TABLES.include?('topmetal2') \|\| BEOL] 5_25_topmetal2.drc:32 | – |  |
| TM2.b | both | 2 [FUR] :742 | TM2.b 2 [TABLES.include?('topmetal2') \|\| BEOL] 5_25_topmetal2.drc:39 | – |  |
| TM2.bR | both | – [FU] :748 | TM2.bR 5 [TABLES.include?('topmetal2') \|\| BEOL & not PRECHECK_DRC & RECOMMENDED] 5_25_topmetal2.drc:53 | – |  |
| TM2Fil.a | both | 5 [FUR] :755 | – | TM2Fil.a 5 [fillerRules] sg13g2_maximal.drc:2529 |  |
| TM2Fil.a1 | both | 10 [FUR] :756 | TM2Fil.a1 10 [TABLES.include?('topmetal2filler') \|\| BEOL & not PRECHECK_DRC] 5_26_topmetal2filler.drc:47 | – |  |
| TM2Fil.b | both | 3 [FUR] :757 | – | TM2Fil.b 3 [fillerRules] sg13g2_maximal.drc:2532 |  |
| TM2Fil.c | both | 3 [FUR] :758 | TM2Fil.c 3 [TABLES.include?('topmetal2filler') \|\| BEOL] 5_26_topmetal2filler.drc:39 | – |  |
| TM2Fil.d | both | 4.9 [FUR] :760 | – | TM2Fil.d 4.9 [fillerRules] sg13g2_maximal.drc:2535 |  |
| TM2Fil.g | Magic only | 90 [FUR] :762 | – | – |  |
| TV1.a | both | in (TV1.a + 2 * TV1.c) 0.62 [FUR] :689; in (TV1.a + 2 * MIM.d) 1.14 [FUR] :903 | TV1.a 0.42 [TABLES.include?('topvia1') \|\| BEOL] 5_21_topvia1.drc:35 | – |  |
| TV1.b | both | in (TV1.b - 2 * TV1.c) 0.22 [FUR] :691 | TV1.b 0.42 [TABLES.include?('topvia1') \|\| BEOL] 5_21_topvia1.drc:44 | – |  |
| TV1.c | folded: Magic checks it only inside a composite rule | in (TV1.a + 2 * TV1.c) 0.62 [FUR] :689; in (TV1.b - 2 * TV1.c) 0.22 [FUR] :691; in (TV1.d - TV1.c) 0.32 [FUR] :693 | TV1.c 0.1 [TABLES.include?('topvia1') \|\| BEOL & not PRECHECK_DRC] 5_21_topvia1.drc:52 | – |  |
| TV1.d | both | in (TV1.d - TV1.c) 0.32 [FUR] :693 | TV1.d 0.42 [TABLES.include?('topvia1') \|\| BEOL & not PRECHECK_DRC] 5_21_topvia1.drc:59 | – |  |
| TV2.a | both | in (TV2.a + 2 * TV2.c) 1.9 [FUR] :727 | TV2.a 0.9 [TABLES.include?('topvia2') \|\| BEOL] 5_24_topvia2.drc:35 | – |  |
| TV2.b | both | in (TV2.b - 2 * TV2.c) 0.06 [FUR] :729 | TV2.b 1.06 [TABLES.include?('topvia2') \|\| BEOL] 5_24_topvia2.drc:44 | – |  |
| TV2.c | folded: Magic checks it only inside a composite rule | in (TV2.a + 2 * TV2.c) 1.9 [FUR] :727; in (TV2.b - 2 * TV2.c) 0.06 [FUR] :729 | TV2.c 0.5 [TABLES.include?('topvia2') \|\| BEOL & not PRECHECK_DRC] 5_24_topvia2.drc:52 | – |  |
| TV2.d | KLayout only | – | TV2.d 0.5 [TABLES.include?('topvia2') \|\| BEOL & not PRECHECK_DRC] 5_24_topvia2.drc:59 | – |  |
| V2.a | both | in (V2.a + 2 * V2.c) 0.2 [FUR] :513 | V2.a 0.19 [TABLES.include?('vian') \|\| BEOL] 5_20_vian.drc:43 | – |  |
| V2.b | both | in (V2.b - 2 * V2.c) 0.21 [FUR] :515 | V2.b 0.22 [TABLES.include?('vian') \|\| BEOL] 5_20_vian.drc:52 | – |  |
| V2.b1 | KLayout only | – | – | V2.b1 0.29 sg13g2_maximal.drc:2468 |  |
| V2.c | folded: Magic checks it only inside a composite rule | in (V2.a + 2 * V2.c) 0.2 [FUR] :513; in (V2.b - 2 * V2.c) 0.21 [FUR] :515; in (V2.c1 - V2.c) 0.045 [FUR] :517; in (M3.c1 - V2.c) 0.045 [FUR] :519 | V2.c 0.005 [TABLES.include?('vian') \|\| BEOL] 5_20_vian.drc:61 | – |  |
| V2.c1 | both | in (V2.c1 - V2.c) 0.045 [FUR] :517 | – | V2.c1 0.05 sg13g2_maximal.drc:2475 |  |
| V3.a | both | in (V3.a + 2 * V3.c) 0.2 [FUR] :571 | V3.a 0.19 [TABLES.include?('vian') \|\| BEOL] 5_20_vian.drc:43 | – |  |
| V3.b | both | in (V3.b - 2 * V3.c) 0.21 [FUR] :573 | V3.b 0.22 [TABLES.include?('vian') \|\| BEOL] 5_20_vian.drc:52 | – |  |
| V3.b1 | KLayout only | – | – | V3.b1 0.29 sg13g2_maximal.drc:2486 |  |
| V3.c | folded: Magic checks it only inside a composite rule | in (V3.a + 2 * V3.c) 0.2 [FUR] :571; in (V3.b - 2 * V3.c) 0.21 [FUR] :573; in (V3.c1 - V3.c) 0.045 [FUR] :575; in (M4.c1 - V3.c) 0.045 [FUR] :577 | V3.c 0.005 [TABLES.include?('vian') \|\| BEOL] 5_20_vian.drc:61 | – |  |
| V3.c1 | both | in (V3.c1 - V3.c) 0.045 [FUR] :575 | – | V3.c1 0.05 sg13g2_maximal.drc:2493 |  |
| V4.a | both | in (V4.a + 2 * V4.c) 0.2 [FUR] :629 | V4.a 0.19 [TABLES.include?('vian') \|\| BEOL] 5_20_vian.drc:43 | – |  |
| V4.b | both | in (V4.b - 2 * V4.c) 0.21 [FUR] :631 | V4.b 0.22 [TABLES.include?('vian') \|\| BEOL] 5_20_vian.drc:52 | – |  |
| V4.b1 | KLayout only | – | – | V4.b1 0.29 sg13g2_maximal.drc:2504 |  |
| V4.c | folded: Magic checks it only inside a composite rule | in (V4.a + 2 * V4.c) 0.2 [FUR] :629; in (V4.b - 2 * V4.c) 0.21 [FUR] :631; in (V4.c1 - V4.c) 0.045 [FUR] :633; in (M5.c1 - V4.c) 0.045 [FUR] :635 | V4.c 0.005 [TABLES.include?('vian') \|\| BEOL] 5_20_vian.drc:61 | – |  |
| V4.c1 | both | in (V4.c1 - V4.c) 0.045 [FUR] :633 | – | V4.c1 0.05 sg13g2_maximal.drc:2511 |  |

## Rules only one side reported in a test

Each line gives a rule and the cases, controls left out, on which one engine reported it and the other did not. Magic's side is any of its styles; KLayout's side is the `main` and `maximal` decks of `run_drc.py`.

### Reported by Magic and not by the main and maximal decks

- `Act.c`: H_pmos_psdhalf
- `Cnt.c`: H_pmos_psdhalf
- `Cnt.f`: Cnt_j
- `Gat.a`: Cnt_j
- `M2.c`: V1_c
- `NW.d`: H_pmos_nopsd
- `pSD.e`: H_pmos_psdhalf

### Reported by KLayout and not by Magic

- `Cnt.a`: Cnt_big
- `Cnt.b1`: Cnt_b1
- `Cnt.g`: Cnt_g
- `Cnt.g1`: H_pmos_psdhalf
- `Cnt.g2`: H_pmos_psdflush
- `Cnt.h`: Cnt_h, M1_c
- `Cnt.j`: Cnt_j
- `CntB.a`: Cnt_a, Cnt_big
- `CntB.a1`: CntB_a1, Cnt_a
- `CntB.b`: CntB_b
- `CntB.b2`: CntB_b2
- `CntB.h1`: CntB_h1
- `EXTB.a`: EXTB_a
- `EXTB.b`: EXTB_b
- `forbidden.*`: forbidden
- `Gat.a1`: Gat_a1
- `Gat.a2`: Gat_a2
- `Gat.b1`: Gat_b1
- `grid.Offgrid`: offgrid
- `M1.c`: Cnt_h, M1_c
- `M1.c1`: Cnt_h, M1_c
- `M1.i`: M1_i
- `nSDB.a`: nSDB_a
- `nSDB.b`: nSDB_b
- `NW.b1`: NW_b1
- `Pin.a`: Pin_a
- `Pin.e`: Pin_e
- `pSD.a`: pSD_a
- `pSD.b`: H_nmos_psdover, pSD_b
- `pSD.c`: H_pmos_psdflush, pSD_c
- `pSD.d`: pSD_d
- `pSD.i`: H_pmos_psdflush, pSD_i_psd
- `pSD.k`: pSD_k
- `pSD.l`: pSD_l
- `Sal.a`: Sal_a
- `Sal.e`: Sal_e
- `TGO.a`: H_hvnmos_thksmall, TGO_a
- `TGO.b`: TGO_b
- `TGO.e`: TGO_e
- `TGO.f`: TGO_f
- `V1.a`: V1_a, V1_big
- `V1.b`: V1_b
- `V1.b1`: V1_b1
- `V1.c1`: V1_c
