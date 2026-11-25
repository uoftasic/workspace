# Gap table: ihp-sg13cmos5l

This table compares Magic's DRC rules for ihp-sg13cmos5l with the PDK's KLayout DRC decks, one row per rule, and shows where they disagree. `tools/build_gaps.py` generates it; do not edit it by hand.

- **What a row is.** One rule, under the rule ID that Magic's why-text gives it (the why-text is the message Magic's DRC gives an error box, and the ID is the text in its last parentheses), under a name from `tests/gaps/aliases-ihp-sg13cmos5l.json` where the two tools name the rule differently, under the KLayout name where Magic has no such rule, or under Magic's whole message where the message has no ID. The row gives the statements of Magic's tech file that check the rule, each KLayout deck's outputs for it (the report categories the deck writes), and what both engines reported on the test cases that target it.
- **How it is made.** Magic's rules come from `python/klayout_magic_pcells/data/pdk-ihp-sg13cmos5l.json`. Each KLayout run below checked a layout of one box. Its report has a category for every rule the deck ran under its switches, and those categories are the deck's side of the table; a text scan of the deck gives each output's line and the switches it sits under. The two sides are joined on rule ID, with the mappings made by hand in `tests/gaps/aliases-ihp-sg13cmos5l.json`. The test cases are the `gaps` set of the case suite (`tests/cases`): a clean control layout, and cases that each change one thing in it. Magic checked each case cell alone in all three styles, at most 15 cells per process; KLayout checked them on one sheet, 40 µm apart. A case's results are the rules reported on it and not on its control.
- **Image.** The pinned Docker image `hpretl/iic-osic-tools@sha256:3c371645b19c6f6564dc8c7b21e39ad1c1833d274fe5b85639afe1ba9d7987e7`, with Magic 8.3.681 and KLayout 0.30.11; PDK commit ff32f48c (Magic tech 1.0.0).
- **Rebuild.** `scripts/gaps.sh --pdk ihp-sg13cmos5l` rewrites this page; `scripts/gaps.sh --pdk ihp-sg13cmos5l --check` fails if it would change.

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
| Front end, Metal1, Via1, grid, pins | 80 | 6 | 0 | 3 | 1 | 68 | 158 |
| Other layers | 66 | 4 | 1 | 0 | 7 | 46 | 124 |
| all | 146 | 10 | 1 | 3 | 8 | 114 | 282 |

## KLayout runs

Each run checked a layout of one box; the last column counts the categories in its report. "The harness" is the plugin's parity harness (`tests/parity`).

| Run | What | Categories on one box |
|---|---|---|
| harness_main | run_drc.py --no_density --mp=1 --density_thr=1 (main and maximal decks, merged) | 336 |
| harness_maximal | run_drc.py --no_density --mp=1 --density_thr=1 (main and maximal decks, merged) | 215 |

Cases: 49 in the `gaps` set.

## Rules

### Front end, Metal1, Via1, grid, pins

| Rule | Status | Magic: value [styles] :line | main: name value [switch] :line | maximal: name value [switch] :line | Tested (case: what each engine reported) |
|---|---|---|---|---|---|
| Act.a | both | 0.15 [FU] :99 | Act.a 0.15 [TABLES.include?('activ') \|\| FEOL] 5_5_activ.drc:32 | – |  |
| Act.b | both | 0.21 [FU] :100 | Act.b 0.21 [TABLES.include?('activ') \|\| FEOL] 5_5_activ.drc:39 | – |  |
| Act.c | both | 0.23 [FU] :103; 0.23 [FU] :104; 0.23 [FU] :105; 0.23 [FU] :106 | – | Act.c 0.23 sg13cmos5l_maximal.drc:1962 | m_Act.c: Magic FU, KLayout harness_maximal |
| Act.d | both | 0.122 µm² [FU] :108 | – | Act.d 0.122 sg13cmos5l_maximal.drc:1965 |  |
| Act.e | both | 0.15 µm² [U] :111 | – | Act.e 0.15 sg13cmos5l_maximal.drc:1968 |  |
| CMOS5L.FORB.* | KLayout only | – | 10 names, e.g. CMOS5L.FORB.MIM, CMOS5L.FORB.Metal5, CMOS5L.FORB.Metal5.filler :70-70 | – |  |
| Cnt.a | both | 0.16 [FUR] :227; 0.16 [FUR] :228; 0.16 [FUR] :229; 0.16 [FUR] :230; 0.16 [FUR] :231; 0.16 [FUR] :232; 5 more | Cnt.a 0.16 [TABLES.include?('cont') \|\| FEOL] 5_14_cont.drc:35 | – |  |
| Cnt.b | both | 0.18 [FUR] :249; 0.18 [FUR] :251; 0.18 [FUR] :253; 0.18 [FUR] :255 | Cnt.b 0.18 [TABLES.include?('cont') \|\| FEOL] 5_14_cont.drc:42 | – |  |
| Cnt.b1 | KLayout only | – | – | Cnt.b1 0.2 sg13cmos5l_maximal.drc:2145 | u_Cnt.b1: Magic no, KLayout harness_maximal |
| Cnt.c | both | 0.07 [FUR] :267; 0.07 [FUR] :269; 0.07 [FUR] :271; 0.02 [FUR] :274; 0.02 [FUR] :276; 0.02 [FUR] :278; 10 more | Cnt.c 0.07 [TABLES.include?('cont') \|\| FEOL & not PRECHECK_DRC] 5_14_cont.drc:51; Cnt.c.SRAM 0.006 [TABLES.include?('cont') \|\| FEOL & not PRECHECK_DRC] 5_14_cont.drc:68; Cnt.c.digibnd 0.05 [TABLES.include?('cont') \|\| FEOL & not PRECHECK_DRC] 5_14_cont.drc:60 | Cnt.c.Digi 0.05 sg13cmos5l_maximal.drc:2728 | m_Cnt.c: Magic FUR, KLayout harness_main |
| Cnt.d | both | as Cnd.d 0.07 [FUR] :304 | Cnt.d 0.07 [TABLES.include?('cont') \|\| FEOL & not PRECHECK_DRC] 5_14_cont.drc:75 | – |  |
| Cnt.e | both | 0.14 [FUR] :258 | Cnt.e 0.14 [TABLES.include?('cont') \|\| FEOL & not PRECHECK_DRC] 5_14_cont.drc:83 | – |  |
| Cnt.f | both | 0.11 [FUR] :261; 0.11 [FUR] :263 | – | Cnt.f 0.11 sg13cmos5l_maximal.drc:2148 |  |
| Cnt.g | KLayout only | – | – | Cnt.g – sg13cmos5l_maximal.drc:2151 | u_Cnt.g: Magic no, KLayout harness_maximal |
| Cnt.g1 | both | 0.09 [FUR] :320 | Cnt.g1 0.09 [TABLES.include?('cont') \|\| FEOL & not PRECHECK_DRC] 5_14_cont.drc:92 | – |  |
| Cnt.g2 | both | 0.09 [FUR] :322 | Cnt.g2 0.09 [TABLES.include?('cont') \|\| FEOL & not PRECHECK_DRC] 5_14_cont.drc:101 | – |  |
| Cnt.h | KLayout only | – | – | Cnt.h – sg13cmos5l_maximal.drc:2154 | u_Cnt.h: Magic no, KLayout harness_maximal |
| Cnt.j | KLayout only | – | – | Cnt.j – sg13cmos5l_maximal.drc:2157 | u_Cnt.j: Magic no, KLayout harness_maximal |
| CntB.a | both | 0.16 [U] :340 | – | CntB.a 0.16 sg13cmos5l_maximal.drc:2161 |  |
| CntB.a1 | KLayout only | – | – | CntB.a1 0.34 sg13cmos5l_maximal.drc:2165 |  |
| CntB.b | both | 0.28 [U] :341 | – | CntB.b 0.28 sg13cmos5l_maximal.drc:2168 |  |
| CntB.b1 | KLayout only | – | CntB.b1 0.36 [TABLES.include?('contbar') \|\| FEOL & not PRECHECK_DRC] 5_15_contbar.drc:40 | – |  |
| CntB.b2 | KLayout only | – | – | CntB.b2 0.22 sg13cmos5l_maximal.drc:2171 |  |
| CntB.c | KLayout only | – | – | CntB.c 0.07 sg13cmos5l_maximal.drc:2174 |  |
| CntB.d | KLayout only | – | – | CntB.d 0.07 sg13cmos5l_maximal.drc:2177 |  |
| CntB.e | KLayout only | – | – | CntB.e 0.14 sg13cmos5l_maximal.drc:2180 |  |
| CntB.f | KLayout only | – | – | CntB.f 0.11 sg13cmos5l_maximal.drc:2183 |  |
| CntB.g | KLayout only | – | – | CntB.g – sg13cmos5l_maximal.drc:2186 |  |
| CntB.g1 | KLayout only | – | – | CntB.g1 0.09 sg13cmos5l_maximal.drc:2189 |  |
| CntB.g2 | KLayout only | – | – | CntB.g2 0.09 sg13cmos5l_maximal.drc:2192 |  |
| CntB.h | KLayout only | – | – | CntB.h – sg13cmos5l_maximal.drc:2195 |  |
| CntB.h1 | both | 0.05 [U] :338 | CntB.h1 0.05 [TABLES.include?('contbar') \|\| FEOL & not PRECHECK_DRC] 5_15_contbar.drc:49 | – |  |
| CntB.j | KLayout only | – | – | CntB.j – sg13cmos5l_maximal.drc:2198 |  |
| exact_overlap | Magic only | – [FUR] :318; – [FUR] :402; – [FUR] :460; – [FUR] :518; – [FUR] :574 | – | – |  |
| EXTB.a | KLayout only | – | – | EXTB.a 0.31 sg13cmos5l_maximal.drc:2112 |  |
| EXTB.b | KLayout only | – | – | EXTB.b 0.31 sg13cmos5l_maximal.drc:2115 |  |
| EXTB.c | both | 0.31 [U] :672 | – | EXTB.c 0.31 sg13cmos5l_maximal.drc:2118 |  |
| forbidden.* | KLayout only | – | 11 names, e.g. forbidden.baspoly, forbidden.biwind, forbidden.colwind :48-48 | – |  |
| Gat.a | both | 0.13 [FUR] :180 | Gat.a 0.13 [TABLES.include?('gatpoly') \|\| FEOL] 5_8_gatpoly.drc:32 | – |  |
| Gat.a1 | KLayout only | – | Gat.a1 0.13 [TABLES.include?('gatpoly') \|\| FEOL & not PRECHECK_DRC] 5_8_gatpoly.drc:55 | – |  |
| Gat.a2 | KLayout only | – | Gat.a2 0.13 [TABLES.include?('gatpoly') \|\| FEOL & not PRECHECK_DRC] 5_8_gatpoly.drc:63 | – |  |
| Gat.a3 | both | 0.45 [FUR] :172; 0.45 [FUR] :608; 0.3 [FUR] :611; 0.33 [FUR] :617 | – | Gat.a3 0.45 sg13cmos5l_maximal.drc:2004 |  |
| Gat.a4 | both | 0.4 [FUR] :620 | – | Gat.a4 0.4 sg13cmos5l_maximal.drc:2008 |  |
| Gat.b | both | 0.18 [FUR] :181 | Gat.b 0.18 [TABLES.include?('gatpoly') \|\| FEOL] 5_8_gatpoly.drc:39 | – | m_Gat.b: Magic FUR, KLayout harness_main |
| Gat.b1 | KLayout only | – | – | Gat.b1 0.25 sg13cmos5l_maximal.drc:2011 |  |
| Gat.c | both | 0.18 [FUR] :189; 0.13 [FUR] :191; 0.17 [FUR] :193 | – | Gat.c 0.18 sg13cmos5l_maximal.drc:2015 | m_Gat.c: Magic FUR, KLayout harness_maximal |
| Gat.d | both | 0.07 [FUR] :183 | Gat.d 0.07 [TABLES.include?('gatpoly') \|\| FEOL] 5_8_gatpoly.drc:46 | – |  |
| Gat.e | both | 0.09 µm² [FUR] :201 | – | Gat.e 0.09 sg13cmos5l_maximal.drc:2019 | m_Gat.e: Magic FUR, KLayout harness_maximal |
| Gat.f | both | – [FUR] :186 | – | Gat.f – sg13cmos5l_maximal.drc:2022 |  |
| Gat.g | both | 0.16 [FUR] :199 | Gat.g 0.16 [TABLES.include?('gatpoly') \|\| FEOL & not PRECHECK_DRC] 5_8_gatpoly.drc:73 | – |  |
| grid.Acute | KLayout only | – | 97 names, e.g. activ_drw_Acute, activ_filler_Acute, activ_iopc_Acute :199-199 | – |  |
| grid.Angle45 | both | as x.2 45 [FUR] :197; 45 [FUR] :354; 45 [FUR] :414; 45 [FUR] :472; 45 [FUR] :530; 45 [FUR] :585 | 7 names, e.g. activ_drw_Angle45, gatpoly_drw_Angle45, metal1_drw_Angle45 :221-221 | – | u_angle.poly: Magic FUR, KLayout harness_main |
| grid.Angle90 | KLayout only | – | 5 names, e.g. cont_drw_Angle90, topvia1_drw_Angle90, via1_drw_Angle90 :210-210 | – |  |
| grid.Offgrid | KLayout only | – | 78 names, e.g. activ_drw_Offgrid, activ_filler_Offgrid, activ_iopc_Offgrid :37-37 | – |  |
| LU.a | both | 20 [U] :117 | – | LU.a 20 [latchUpRules] sg13cmos5l_maximal.drc:2568 |  |
| LU.b | both | 20 [U] :115 | LU.b 20 [TABLES.include?('latchup') \|\| FEOL & not PRECHECK_DRC] 7_2_latchup.drc:41 | – | m_LU.b: Magic U, KLayout harness_main |
| LU.c | both | 6 [U] :119 | – | LU.c 6 [latchUpRules] sg13cmos5l_maximal.drc:2575 |  |
| LU.c1 | both | as LU.c 6 [U] :119 | – | LU.c1 6 [latchUpRules] sg13cmos5l_maximal.drc:2582 |  |
| LU.d | both | 6 [U] :121 | – | LU.d 6 [latchUpRules] sg13cmos5l_maximal.drc:2589 |  |
| LU.d1 | both | as LU.d 6 [U] :121 | – | LU.d1 6 [latchUpRules] sg13cmos5l_maximal.drc:2595 |  |
| M1.a | both | 0.16 [FUR] :349 | M1.a 0.16 [TABLES.include?('metal1') \|\| BEOL] 5_16_metal1.drc:32 | – | m_M1.a: Magic FUR, KLayout harness_main |
| M1.b | both | 0.18 [FUR] :350 | M1.b 0.18 [TABLES.include?('metal1') \|\| BEOL] 5_16_metal1.drc:39 | – |  |
| M1.c | KLayout only | – | – | M1.c 0 sg13cmos5l_maximal.drc:2201 |  |
| M1.c1 | both | 0.05 [FUR] :307; 0.05 [FUR] :309; 0.05 [FUR] :311; 0.05 [FUR] :313; 0.05 [FUR] :315 | – | M1.c1 0.05 sg13cmos5l_maximal.drc:2207 |  |
| M1.d | both | 0.09 µm² [FUR] :352 | – | M1.d 0.09 sg13cmos5l_maximal.drc:2210 | m_M1.d: Magic FUR, KLayout harness_maximal |
| M1.e | both | – [FU] :362; – [FU] :364 | M1.e 0.22 [TABLES.include?('metal1') \|\| BEOL & not PRECHECK_DRC] 5_16_metal1.drc:51 | – |  |
| M1.f | both | – [FU] :367; – [FU] :369 | M1.f 0.6 [TABLES.include?('metal1') \|\| BEOL & not PRECHECK_DRC] 5_16_metal1.drc:64 | – |  |
| M1.g | both | 0.2 [FUR] :356 | M1.g 0.2 [TABLES.include?('metal1') \|\| BEOL & not PRECHECK_DRC] 5_16_metal1.drc:76 | – |  |
| M1.i | KLayout only | – | M1.i 0.22 [TABLES.include?('metal1') \|\| BEOL & not PRECHECK_DRC] 5_16_metal1.drc:87 | – |  |
| NBL.a | KLayout only | – | – | NBL.a 1 sg13cmos5l_maximal.drc:1947 |  |
| NBLB.a | KLayout only | – | – | NBLB.a 1.5 sg13cmos5l_maximal.drc:1950 |  |
| NBLB.b | KLayout only | – | – | NBLB.b 1 sg13cmos5l_maximal.drc:1953 |  |
| NBLB.c | KLayout only | – | – | NBLB.c 1 sg13cmos5l_maximal.drc:1956 |  |
| NBLB.d | KLayout only | – | – | NBLB.d 1.5 sg13cmos5l_maximal.drc:1959 |  |
| nmosi.b | KLayout only | – | – | nmosi.b 1.24 sg13cmos5l_maximal.drc:2418 |  |
| nmosi.c | KLayout only | – | – | nmosi.c 0.39 sg13cmos5l_maximal.drc:2421 |  |
| nmosi.d | KLayout only | – | – | nmosi.d 0.62 sg13cmos5l_maximal.drc:2424 |  |
| nmosi.f | KLayout only | – | – | nmosi.f 0.62 sg13cmos5l_maximal.drc:2427 |  |
| nmosi.g | KLayout only | – | – | nmosi.g 0.15 sg13cmos5l_maximal.drc:2432 |  |
| nSDB.a | KLayout only | – | – | nSDB.a 0.31 sg13cmos5l_maximal.drc:2100 | u_nSDB.a: Magic no, KLayout harness_maximal |
| nSDB.b | KLayout only | – | – | nSDB.b 0.31 sg13cmos5l_maximal.drc:2103 |  |
| nSDB.c | KLayout only | – | – | nSDB.c 0.31 sg13cmos5l_maximal.drc:2106 |  |
| nSDB.e | KLayout only | – | – | nSDB.e 0 sg13cmos5l_maximal.drc:2109 |  |
| NW.a | both | 0.62 [FU] :35 | – | NW.a 0.62 sg13cmos5l_maximal.drc:1909 | m_NW.a: Magic FU, KLayout harness_maximal |
| NW.b | both | 0.62 [FU] :38 | NW.b 0.62 [TABLES.include?('nwell') \|\| FEOL & !PRECHECK_DRC && CONNECTIVITY_RULES] 5_1_nwell.drc:37 | – |  |
| NW.b1 | KLayout only | – | NW.b1 1.8 [TABLES.include?('nwell') \|\| FEOL & !PRECHECK_DRC && CONNECTIVITY_RULES] 5_1_nwell.drc:48 | – | u_NW.b1: Magic no, KLayout harness_main |
| NW.c | both | 0.31 [FU] :42; 0.27 [FU] :49 | – | NW.c 0.31 sg13cmos5l_maximal.drc:1912 | m_NW.c: Magic FU, KLayout harness_maximal |
| NW.c1 | both | 0.62 [FU] :55 | – | NW.c1 0.62 sg13cmos5l_maximal.drc:1915; NW.c1.dig 0.31 sg13cmos5l_maximal.drc:2716 |  |
| NW.d | both | 0.31 [FU] :45; 0.27 [FU] :51 | – | NW.d 0.31 sg13cmos5l_maximal.drc:1918 | m_NW.d: Magic FU, KLayout harness_maximal |
| NW.d1 | both | 0.62 [FU] :57 | – | NW.d1 0.62 sg13cmos5l_maximal.drc:1921; NW.d1.dig 0.31 sg13cmos5l_maximal.drc:2719 |  |
| NW.e | both | 0.24 [FU] :59 | – | NW.e 0.24 sg13cmos5l_maximal.drc:1924 |  |
| NW.e1 | both | 0.62 [FU] :72 | – | NW.e1 0.62 sg13cmos5l_maximal.drc:1927; NW.e1.dig 0.24 sg13cmos5l_maximal.drc:2722 |  |
| NW.f | both | 0.24 [FU] :63 | – | NW.f 0.24 sg13cmos5l_maximal.drc:1932 |  |
| NW.f1 | both | 0.62 [FU] :65 | NW.f1 0.62 [TABLES.include?('nwell') \|\| FEOL & !PRECHECK_DRC] 5_1_nwell.drc:67; NW.f1.digibnd 0.24 [TABLES.include?('nwell') \|\| FEOL & !PRECHECK_DRC] 5_1_nwell.drc:77 | NW.f1 0.62 sg13cmos5l_maximal.drc:1935; NW.f1.dig 0.24 sg13cmos5l_maximal.drc:2725 |  |
| Pin.a | KLayout only | – | Pin.a 0 [TABLES.include?('pin') \|\| PIN] 7_4_pin.drc:42 | – |  |
| Pin.b | KLayout only | – | Pin.b 0 [TABLES.include?('pin') \|\| PIN] 7_4_pin.drc:42 | – |  |
| Pin.e | KLayout only | – | Pin.e 0 [TABLES.include?('pin') \|\| PIN] 7_4_pin.drc:42 | – | u_Pin.e: Magic no, KLayout harness_main |
| Pin.f_M2 | KLayout only | – | Pin.f_M2 0 [TABLES.include?('pin') \|\| PIN] 7_4_pin.drc:42 | – |  |
| Pin.f_M3 | KLayout only | – | Pin.f_M3 0 [TABLES.include?('pin') \|\| PIN] 7_4_pin.drc:42 | – |  |
| Pin.f_M4 | KLayout only | – | Pin.f_M4 0 [TABLES.include?('pin') \|\| PIN] 7_4_pin.drc:42 | – |  |
| Pin.g | KLayout only | – | Pin.g 0 [TABLES.include?('pin') \|\| PIN] 7_4_pin.drc:42 | – |  |
| pSD.a | KLayout only | – | – | pSD.a 0.31 sg13cmos5l_maximal.drc:2041 | u_pSD.a: Magic no, KLayout harness_maximal |
| pSD.b | KLayout only | – | – | pSD.b 0.31 sg13cmos5l_maximal.drc:2044 | u_pSD.b: Magic no, KLayout harness_maximal |
| pSD.c | folded: Magic checks it only inside a composite rule | in (Rsil.d + Rsil.e + pSD.c) 0.54 [FUR] :644 | – | pSD.c 0.18 sg13cmos5l_maximal.drc:2047 | u_pSD.c: Magic no, KLayout harness_maximal |
| pSD.c1 | folded: Magic checks it only inside a composite rule | in (pSD.j + pSD.c1) 0.33 [FUR] :157; in (pSD.j1 + pSD.c1) 0.43 [FUR] :161; in (Seal.b - pSD.c1) 4.87 [U] :329; in (Rsil.d + Rsil.e + pSD.c1) 0.39 [FUR] :646 | pSD.c1 0.03 [TABLES.include?('psd') \|\| FEOL & not PRECHECK_DRC] 5_10_psd.drc:34 | – | u_pSD.c1: Magic no, KLayout harness_main |
| pSD.d | KLayout only | – | – | pSD.d 0.18 sg13cmos5l_maximal.drc:2050 | u_pSD.d: Magic no, KLayout harness_maximal |
| pSD.d1 | folded: Magic checks it only inside a composite rule | in (pSD.i + pSD.d1) 0.33 [FUR] :150; in (pSD.i1 + pSD.d1) 0.43 [FUR] :153 | – | pSD.d1 0.03 sg13cmos5l_maximal.drc:2053 |  |
| pSD.e | both | as pSD.e/f 0.3 [U] :146 | – | pSD.e 0.3 sg13cmos5l_maximal.drc:2060 |  |
| pSD.f | both | as pSD.e/f 0.3 [U] :146 | – | pSD.f 0.3 sg13cmos5l_maximal.drc:2066 |  |
| pSD.g | both | 0.09 µm² [U] :145 | – | pSD.g 0.09 sg13cmos5l_maximal.drc:2072 |  |
| pSD.i | in the deck, did not fire on its case: Magic reported nothing on u_pSD.i | in (pSD.i + pSD.d1) 0.33 [FUR] :150; 0.3 [FUR] :152; 0.3 [FUR] :155; 0.3 [FUR] :165 | – | pSD.i 0.3 sg13cmos5l_maximal.drc:2076 | u_pSD.i: Magic no, KLayout harness_maximal |
| pSD.i1 | both | in (pSD.i1 + pSD.d1) 0.43 [FUR] :153; 0.4 [FUR] :166 | – | pSD.i1 0.4 sg13cmos5l_maximal.drc:2079 |  |
| pSD.j | in the deck, did not fire on its case: Magic reported nothing on u_pSD.j | in (pSD.j + pSD.c1) 0.33 [FUR] :157; 0.3 [FUR] :159; 0.3 [FUR] :168 | – | pSD.j 0.3 sg13cmos5l_maximal.drc:2082 | u_pSD.j: Magic no, KLayout harness_maximal |
| pSD.j1 | both | in (pSD.j1 + pSD.c1) 0.43 [FUR] :161; 0.4 [FUR] :169 | – | pSD.j1 0.4 sg13cmos5l_maximal.drc:2085 |  |
| pSD.k | KLayout only | – | – | pSD.k 0.25 sg13cmos5l_maximal.drc:2088 | u_pSD.k: Magic no, KLayout harness_maximal |
| pSD.l | KLayout only | – | – | pSD.l 0.25 sg13cmos5l_maximal.drc:2091 |  |
| pSD.m | both | in (pSD.m + pSD.n) 0.36 [FUR] :664 | – | pSD.m 0.18 sg13cmos5l_maximal.drc:2094 |  |
| pSD.n | folded: Magic checks it only inside a composite rule | in (pSD.m + pSD.n) 0.36 [FUR] :664 | – | pSD.n 0.18 sg13cmos5l_maximal.drc:2097 |  |
| PWB.a | both | 0.62 [FU] :78 | – | PWB.a 0.62 sg13cmos5l_maximal.drc:1938 |  |
| PWB.b | both | as PWB.a 0.62 [FU] :79 | – | PWB.b 0.62 sg13cmos5l_maximal.drc:1941 |  |
| PWB.c | both | 0.62 [FU] :80 | – | PWB.c 0.62 sg13cmos5l_maximal.drc:1944 |  |
| PWB.e | both | 0.31 [FU] :82 | PWB.e 0.31 [TABLES.include?('pwellblock') \|\| FEOL & not PRECHECK_DRC] 5_2_pwellblock.drc:40 | – |  |
| PWB.e1 | both | 0.62 [FU] :84 | PWB.e1 0.62 [TABLES.include?('pwellblock') \|\| FEOL & not PRECHECK_DRC] 5_2_pwellblock.drc:50 | – |  |
| PWB.f | both | 0.24 [FU] :86 | PWB.f 0.24 [TABLES.include?('pwellblock') \|\| FEOL & not PRECHECK_DRC] 5_2_pwellblock.drc:60 | – |  |
| PWB.f1 | both | as PWB.f 0.62 [FU] :88 | PWB.f1 0.62 [TABLES.include?('pwellblock') \|\| FEOL & not PRECHECK_DRC] 5_2_pwellblock.drc:72 | – |  |
| Rhi.a | both | 0.5 [FUR] :659 | – | Rhi.a 0.5 sg13cmos5l_maximal.drc:2397 |  |
| Rhi.b | KLayout only | – | – | Rhi.b – sg13cmos5l_maximal.drc:2400 |  |
| Rhi.c | KLayout only | – | – | Rhi.c 0.18 sg13cmos5l_maximal.drc:2403 |  |
| Rhi.d | both | 0.2 [FUR] :660 | – | Rhi.d 0.2 sg13cmos5l_maximal.drc:2408 |  |
| Rhi.e | KLayout only | – | – | Rhi.e 0.18 sg13cmos5l_maximal.drc:2412 |  |
| Rhi.f | both | 0.5 [FUR] :662 | – | Rhi.f 0.5 sg13cmos5l_maximal.drc:2415 |  |
| Rppd.a | both | 0.5 [FUR] :654 | – | Rppd.a 0.5 sg13cmos5l_maximal.drc:2379 |  |
| Rppd.b | KLayout only | – | – | Rppd.b 0.18 sg13cmos5l_maximal.drc:2382 |  |
| Rppd.c | both | 0.2 [FUR] :655 | – | Rppd.c 0.2 sg13cmos5l_maximal.drc:2387 |  |
| Rppd.d | KLayout only | – | – | Rppd.d 0.18 sg13cmos5l_maximal.drc:2391 |  |
| Rppd.e | both | 0.5 [FUR] :657 | – | Rppd.e 0.5 sg13cmos5l_maximal.drc:2394 |  |
| Rsil.a | both | 0.5 [FUR] :639 | – | Rsil.a 0.5 sg13cmos5l_maximal.drc:2360 |  |
| Rsil.b | both | 0.12 [FUR] :640 | – | Rsil.b 0.12 sg13cmos5l_maximal.drc:2363 |  |
| Rsil.c | KLayout only | – | – | Rsil.c 0 sg13cmos5l_maximal.drc:2367 |  |
| Rsil.d | both | in (Rsil.d + Rsil.e + pSD.c) 0.54 [FUR] :644; in (Rsil.d + Rsil.e + pSD.c1) 0.39 [FUR] :646 | – | Rsil.d 0.18 sg13cmos5l_maximal.drc:2370 |  |
| Rsil.e | folded: Magic checks it only inside a composite rule | in (Rsil.d + Rsil.e + pSD.c) 0.54 [FUR] :644; in (Rsil.d + Rsil.e + pSD.c1) 0.39 [FUR] :646 | – | Rsil.e 0.18 sg13cmos5l_maximal.drc:2373 |  |
| Rsil.f | both | 0.5 [FUR] :642 | – | Rsil.f 0.5 sg13cmos5l_maximal.drc:2376 |  |
| Sal.a | KLayout only | – | – | Sal.a 0.42 sg13cmos5l_maximal.drc:2121 | u_Sal.a: Magic no, KLayout harness_maximal |
| Sal.b | both | 0.42 [FUR] :666 | – | Sal.b 0.42 sg13cmos5l_maximal.drc:2124 |  |
| Sal.c | both | in (Sal.c + Sal.d) 0.4 [FUR] :683; in (Sal.c + Sal.d) 0.4 [FUR] :685; in (Sal.c + Sal.d) 0.48 [FUR] :688; in (Sal.c + Sal.d) 0.48 [FUR] :690 | – | Sal.c 0.2 sg13cmos5l_maximal.drc:2128 |  |
| Sal.d | folded: Magic checks it only inside a composite rule | in (Sal.c + Sal.d) 0.4 [FUR] :683; in (Sal.c + Sal.d) 0.4 [FUR] :685; in (Sal.c + Sal.d) 0.48 [FUR] :688; in (Sal.c + Sal.d) 0.48 [FUR] :690 | – | Sal.d 0.2 sg13cmos5l_maximal.drc:2133 |  |
| Sal.e | KLayout only | – | – | Sal.e 0.2 sg13cmos5l_maximal.drc:2137 |  |
| TGO.a | KLayout only | – | – | TGO.a 0.27 sg13cmos5l_maximal.drc:1987 |  |
| TGO.b | KLayout only | – | – | TGO.b 0.27 sg13cmos5l_maximal.drc:1990 |  |
| TGO.c | both | 0.34 [FUR] :626; 0.34 [FUR] :628 | – | TGO.c 0.34 sg13cmos5l_maximal.drc:1994 |  |
| TGO.d | both | 0.34 [FUR] :630; 0.34 [FUR] :632 | – | TGO.d 0.34 sg13cmos5l_maximal.drc:1997 |  |
| TGO.e | KLayout only | – | – | TGO.e 0.86 sg13cmos5l_maximal.drc:2000 |  |
| TGO.f | KLayout only | – | TGO.f 0.86 [TABLES.include?('thickgateox') \|\| FEOL] 5_7_thickgateox.drc:32 | – | u_TGO.f: Magic no, KLayout harness_main |
| V1.a | in the deck, did not fire on its case: Magic reported nothing on m_V1.a | in (V1.a + 2 * M2.c) 0.2 [FUR] :391 | V1.a 0.19 [TABLES.include?('via1') \|\| BEOL] 5_19_via1.drc:43 | – | m_V1.a: Magic no, KLayout harness_main |
| V1.b | both | in (V1.b - 2 * M2.c) 0.21 [FUR] :392 | V1.b 0.22 [TABLES.include?('via1') \|\| BEOL] 5_19_via1.drc:52 | – |  |
| V1.b1 | KLayout only | – | – | V1.b1 0.29 sg13cmos5l_maximal.drc:2309 | u_V1.b1: Magic no, KLayout harness_maximal |
| V1.c | both | in (V1.c - M2.c) 0.005 [FUR] :393 | V1.c 0.01 [TABLES.include?('via1') \|\| BEOL & not PRECHECK_DRC] 5_19_via1.drc:60 | – |  |
| V1.c1 | both | in (V1.c1 - M2.c) 0.045 [FUR] :396 | – | V1.c1 0.05 sg13cmos5l_maximal.drc:2316 |  |

### Other layers

| Rule | Status | Magic: value [styles] :line | main: name value [switch] :line | maximal: name value [switch] :line | Tested (case: what each engine reported) |
|---|---|---|---|---|---|
| AFil.a | both | 5 [U] :125 | – | AFil.a 5 [fillerRules] sg13cmos5l_maximal.drc:1973 |  |
| AFil.a1 | both | 1 [U] :124 | – | AFil.a1 1 [fillerRules] sg13cmos5l_maximal.drc:1976 |  |
| AFil.b | both | 0.42 [U] :126 | – | AFil.b 0.42 [fillerRules] sg13cmos5l_maximal.drc:1979 |  |
| AFil.c | both | 1.1 [U] :130; 1.1 [U] :132; 1.1 [U] :134 | AFil.c 1.1 [TABLES.include?('activfiller') \|\| FEOL & not PRECHECK_DRC] 5_6_activfiller.drc:57 | – |  |
| AFil.c1 | both | 0.42 [U] :128 | AFil.c1 0.42 [TABLES.include?('activfiller') \|\| FEOL] 5_6_activfiller.drc:49 | – |  |
| AFil.d | both | 1 [U] :136 | AFil.d 1 [TABLES.include?('activfiller') \|\| FEOL & not PRECHECK_DRC] 5_6_activfiller.drc:69 | – |  |
| AFil.e | Magic only | 1 [U] :138 | – | – |  |
| AFil.i | both | 1.5 [FU] :90; 1.5 [FU] :92 | – | AFil.i 1.5 [fillerRules] sg13cmos5l_maximal.drc:1982 |  |
| AFil.i.angle | same name for another check: Magic prints AFil.i for a rule that allows only 90-degree angles on Activ fill, which IHP's SG13CMOS5L layout rules (Rev. 0.1) do not have; their AFil.i, which the maximal deck checks, is the 1.50 µm Activ:filler space to PWell:block (row AFil.i). KLayout checks Activ:filler for acute angles only | as AFil.i 90 [U] :140 | – | – |  |
| AFil.j | KLayout only | – | AFil.j 0.25 [TABLES.include?('activfiller') \|\| FEOL & not PRECHECK_DRC] 5_6_activfiller.drc:87 | – |  |
| GFil.a | both | 5 [FUR] :206 | – | GFil.a 5 [fillerRules] sg13cmos5l_maximal.drc:2027 |  |
| GFil.b | both | 0.7 [FUR] :205 | – | GFil.b 0.7 [fillerRules] sg13cmos5l_maximal.drc:2030 |  |
| GFil.c | both | 0.8 [FUR] :207 | – | GFil.c 0.8 [fillerRules] sg13cmos5l_maximal.drc:2033 |  |
| GFil.d | both | 1.1 [FUR] :210 | GFil.d 1.1 [TABLES.include?('gatpolyfiller') \|\| FEOL] 5_9_gatpolyfiller.drc:48 | – |  |
| GFil.e | both | 1.1 [FUR] :212; 1.1 [FUR] :214 | GFil.e 1.1 [TABLES.include?('gatpolyfiller') \|\| FEOL & not PRECHECK_DRC] 5_9_gatpolyfiller.drc:59 | – |  |
| GFil.f | Magic only | 1.1 [FUR] :216 | – | – |  |
| GFil.i | KLayout only | – | GFil.i 400 [TABLES.include?('gatpolyfiller') \|\| FEOL & not PRECHECK_DRC] 5_9_gatpolyfiller.drc:66 | – |  |
| GFil.j | both | 0.18 [FUR] :218 | – | GFil.j 0.18 [fillerRules] sg13cmos5l_maximal.drc:2036 |  |
| GFil.k | Magic only | 90 [FUR] :219 | – | – |  |
| LBE.a | KLayout only | – | LBE.a 100 [TABLES.include?('lbe') \|\| BEOL] 9_1_lbe.drc:33 | – |  |
| LBE.b | KLayout only | – | LBE.b 1500 [TABLES.include?('lbe') \|\| BEOL] 9_1_lbe.drc:40 | – |  |
| LBE.b1 | KLayout only | – | LBE.b1 250000 [TABLES.include?('lbe') \|\| BEOL] 9_1_lbe.drc:47 | – |  |
| LBE.b2 | KLayout only | – | – | LBE.b2 30000 sg13cmos5l_maximal.drc:2731 |  |
| LBE.c | KLayout only | – | LBE.c 100 [TABLES.include?('lbe') \|\| BEOL] 9_1_lbe.drc:54 | – |  |
| LBE.d | KLayout only | – | LBE.d 150 [TABLES.include?('lbe') \|\| BEOL] 9_1_lbe.drc:61 | – |  |
| LBE.e | KLayout only | – | – | LBE.e.Passiv 50 sg13cmos5l_maximal.drc:2737; LBE.e.dfPad 50 sg13cmos5l_maximal.drc:2734 |  |
| LBE.f | KLayout only | – | – | LBE.f 30 sg13cmos5l_maximal.drc:2740 |  |
| LBE.h | KLayout only | – | LBE.h – [TABLES.include?('lbe') \|\| BEOL] 9_1_lbe.drc:67 | – |  |
| M2.a | both | 0.2 [FUR] :410 | M2.a 0.2 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:44 | – |  |
| M2.b | both | 0.21 [FUR] :411 | M2.b 0.21 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:51 | – |  |
| M2.c | folded: Magic checks it only inside a composite rule | in (V1.a + 2 * M2.c) 0.2 [FUR] :391; in (V1.b - 2 * M2.c) 0.21 [FUR] :392; in (V1.c - M2.c) 0.005 [FUR] :393; in (V1.c1 - M2.c) 0.045 [FUR] :396; in (M2.c1 - M2.c) 0.045 [FUR] :399 | – | M2.c 0.005 sg13cmos5l_maximal.drc:2214 |  |
| M2.c1 | both | in (M2.c1 - M2.c) 0.045 [FUR] :399 | – | M2.c1 0.05 sg13cmos5l_maximal.drc:2220 |  |
| M2.d | both | 0.144 µm² [FUR] :412 | – | M2.d 0.144 sg13cmos5l_maximal.drc:2223 |  |
| M2.e | both | – [FU] :422; – [FU] :424 | M2.e 0.24 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:63 | – |  |
| M2.f | both | – [FU] :427; – [FU] :429 | M2.f 0.6 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:75 | – |  |
| M2.g | both | 0.24 [FUR] :416 | M2.g 0.24 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:87 | – |  |
| M2.i | KLayout only | – | M2.i 0.24 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:98 | – |  |
| M3.a | both | 0.2 [FUR] :468 | M3.a 0.2 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:44 | – |  |
| M3.b | both | 0.21 [FUR] :469 | M3.b 0.21 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:51 | – |  |
| M3.c | KLayout only | – | – | M3.c 0.005 sg13cmos5l_maximal.drc:2227 |  |
| M3.c1 | both | in (M3.c1 - V2.c) 0.045 [FUR] :457 | – | M3.c1 0.05 sg13cmos5l_maximal.drc:2233 |  |
| M3.d | both | 0.144 µm² [FUR] :470 | – | M3.d 0.144 sg13cmos5l_maximal.drc:2236 |  |
| M3.e | both | – [FU] :480; – [FU] :482 | M3.e 0.24 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:63 | – |  |
| M3.f | both | – [FU] :485; – [FU] :487 | M3.f 0.6 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:75 | – |  |
| M3.g | both | 0.24 [FUR] :474 | M3.g 0.24 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:87 | – |  |
| M3.i | KLayout only | – | M3.i 0.24 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:98 | – |  |
| M4.a | both | 0.2 [FUR] :526 | M4.a 0.2 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:44 | – |  |
| M4.b | both | 0.21 [FUR] :527 | M4.b 0.21 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:51 | – |  |
| M4.c | KLayout only | – | – | M4.c 0.005 sg13cmos5l_maximal.drc:2240 |  |
| M4.c1 | both | in (M4.c1 - V3.c) 0.045 [FUR] :515 | – | M4.c1 0.05 sg13cmos5l_maximal.drc:2246 |  |
| M4.d | both | 0.144 µm² [FUR] :528 | – | M4.d 0.144 sg13cmos5l_maximal.drc:2249 |  |
| M4.e | both | – [FU] :538; – [FU] :540 | M4.e 0.24 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:63 | – |  |
| M4.f | both | – [FU] :543; – [FU] :545 | M4.f 0.6 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:75 | – |  |
| M4.g | both | 0.24 [FUR] :532 | M4.g 0.24 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:87 | – |  |
| M4.i | KLayout only | – | M4.i 0.24 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:98 | – |  |
| MFil.a1 | both | 1 [FUR] :373; 1 [FUR] :433; 1 [FUR] :491; 1 [FUR] :549 | – | M1Fil.a1 1 [fillerRules] sg13cmos5l_maximal.drc:2256; M2Fil.a1 1 [fillerRules] sg13cmos5l_maximal.drc:2266; M3Fil.a1 1 [fillerRules] sg13cmos5l_maximal.drc:2275; M4Fil.a1 1 [fillerRules] sg13cmos5l_maximal.drc:2284 |  |
| MFil.a2 | both | 5 [FUR] :374; 5 [FUR] :434; 5 [FUR] :492; 5 [FUR] :550 | M1Fil.a2 5 [TABLES.include?('metalnfiller') \|\| BEOL] 5_18_metalnfiller.drc:60; M2Fil.a2 5 [TABLES.include?('metalnfiller') \|\| BEOL] 5_18_metalnfiller.drc:60; M3Fil.a2 5 [TABLES.include?('metalnfiller') \|\| BEOL] 5_18_metalnfiller.drc:60; M4Fil.a2 5 [TABLES.include?('metalnfiller') \|\| BEOL] 5_18_metalnfiller.drc:60 | – |  |
| MFil.b | both | 0.42 [FUR] :375; 0.42 [FUR] :435; 0.42 [FUR] :493; 0.42 [FUR] :551 | M1Fil.b 0.42 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:51; M2Fil.b 0.42 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:51; M3Fil.b 0.42 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:51; M4Fil.b 0.42 [TABLES.include?('metaln') \|\| BEOL] 5_17_metaln.drc:51 | M1Fil.b 0.42 [fillerRules] sg13cmos5l_maximal.drc:2259; M2Fil.b 0.42 [fillerRules] sg13cmos5l_maximal.drc:2269; M3Fil.b 0.42 [fillerRules] sg13cmos5l_maximal.drc:2278; M4Fil.b 0.42 [fillerRules] sg13cmos5l_maximal.drc:2287 |  |
| MFil.c | both | 0.42 [FUR] :376; 0.42 [FUR] :436; 0.42 [FUR] :494; 0.42 [FUR] :552 | M1Fil.c 0.42 [TABLES.include?('metalnfiller') \|\| BEOL] 5_18_metalnfiller.drc:50; M2Fil.c 0.42 [TABLES.include?('metalnfiller') \|\| BEOL] 5_18_metalnfiller.drc:50; M3Fil.c 0.42 [TABLES.include?('metalnfiller') \|\| BEOL] 5_18_metalnfiller.drc:50; M4Fil.c 0.42 [TABLES.include?('metalnfiller') \|\| BEOL] 5_18_metalnfiller.drc:50 | – |  |
| MFil.d | Magic only | 1 [FUR] :378; 1 [FUR] :438; 1 [FUR] :496; 1 [FUR] :554 | – | – |  |
| MFil.i | Magic only | 90 [FUR] :380; 90 [FUR] :440; 90 [FUR] :498; 90 [FUR] :556 | – | – |  |
| Pad.a1 | both | 150 [U] :704 | – | Pad.a1 150 sg13cmos5l_maximal.drc:2451 |  |
| Pad.aR | both | 30 [U] :703 | – | Pad.aR 30 [recommendedRules] sg13cmos5l_maximal.drc:2446 |  |
| Pad.bR | both | 8.4 [U] :705 | – | Pad.bR 8.4 [recommendedRules] sg13cmos5l_maximal.drc:2456 |  |
| Pad.d | both | 7.5 [U] :706 | – | Pad.d 7.5 sg13cmos5l_maximal.drc:2461 |  |
| Pad.d1R | KLayout only | – | – | Pad.d1R 11.2 [recommendedRules] sg13cmos5l_maximal.drc:2469 |  |
| Pad.dR | KLayout only | – | – | Pad.dR 25 [recommendedRules] sg13cmos5l_maximal.drc:2466 |  |
| Pad.fR | KLayout only | – | 5 names, e.g. Pad.fR_M1, Pad.fR_M2, Pad.fR_M3 :61-61 | – |  |
| Pad.i | KLayout only | – | Pad.i – [TABLES.include?('pad') \|\| BEOL & not PRECHECK_DRC] 6_9_pad.drc:73 | – |  |
| Pad.jR | KLayout only | – | – | Pad.jR – [recommendedRules] sg13cmos5l_maximal.drc:2472 |  |
| Pad.m | KLayout only | – | Pad.m – [TABLES.include?('pad') \|\| BEOL] 6_9_pad.drc:38 | – |  |
| Padc.d | KLayout only | – | – | Padc.d 30 sg13cmos5l_maximal.drc:2477 |  |
| Pas.a | KLayout only | – | Pas.a 2.1 [TABLES.include?('passiv') \|\| BEOL] 5_27_passiv.drc:35 | – |  |
| Pas.b | KLayout only | – | Pas.b 3.5 [TABLES.include?('passiv') \|\| BEOL] 5_27_passiv.drc:42 | – |  |
| Pas.c | KLayout only | – | Pas.c 2.1 [TABLES.include?('passiv') \|\| BEOL & not PRECHECK_DRC] 5_27_passiv.drc:53 | – |  |
| Sdiod.a | KLayout only | – | – | Sdiod.a 0.25 sg13cmos5l_maximal.drc:2435 |  |
| Sdiod.b | KLayout only | – | – | Sdiod.b 0.4 sg13cmos5l_maximal.drc:2438 |  |
| Sdiod.c | KLayout only | – | – | Sdiod.c 0.45 sg13cmos5l_maximal.drc:2441 |  |
| Seal.a | both | 3.5 [U] :326; 3.5 [U] :384; 3.5 [U] :444; 3.5 [U] :502; 3.5 [U] :560; 3.5 [U] :598 | – | 7 names, e.g. Seal.a_Activ, Seal.a_Metal1, Seal.a_Metal2 :2480-2498 |  |
| Seal.b | both | 4.9 [U] :327; in (Seal.b - pSD.c1) 4.87 [U] :329 | 7 names, e.g. Seal.b_activ, Seal.b_metal1, Seal.b_metal2 :102-102 | – |  |
| Seal.c | both | 0.16 [FUR] :240 | – | Seal.c 0.16 sg13cmos5l_maximal.drc:2502 |  |
| Seal.c1 | both: Magic checks only the minimum width of the Via1-Via3 seal rings; the maximal deck also flags rings wider than 0.19 µm | 0.19 [FUR] :404; 0.19 [FUR] :462; 0.19 [FUR] :520 | – | Seal.c1.Via1 0.19 sg13cmos5l_maximal.drc:2507; Seal.c1.Via2 0.19 sg13cmos5l_maximal.drc:2512; Seal.c1.Via3 0.19 sg13cmos5l_maximal.drc:2517 |  |
| Seal.c2 | both | 0.42 [FUR] :576 | – | Seal.c2 0.42 sg13cmos5l_maximal.drc:2522 |  |
| Seal.d | both: Magic checks the Activ enclosure of the EdgeSeal-Cont ring only; the maximal deck checks it for the Cont, Via1-Via3 and TopVia1 rings | 1.3 [FUR] :242 | – | 5 names, e.g. Seal.d.Cont, Seal.d.TopVia1, Seal.d.Via1 :2526-2538 |  |
| Seal.e | both | 4.2 [FUR] :698 | – | Seal.e 4.2 sg13cmos5l_maximal.drc:2541 |  |
| Seal.f | both: Magic's statement lists pdiff and m1-m4, not m5 (TopMetal1); the maximal deck checks EdgeSeal Activ, pSD, Metal1-Metal4 and TopMetal1, and pSD is not in the layout rules' Seal.f list | 1 [FUR] :699 | – | 7 names, e.g. Seal.f.Activ, Seal.f.Metal1, Seal.f.Metal2 :2544-2562 |  |
| Seal.k | KLayout only | – | Seal.k 21 [TABLES.include?('sealring') \|\| BEOL & not PRECHECK_DRC] 6_10_sealring.drc:113 | – |  |
| Seal.m | KLayout only | – | Seal.m – [TABLES.include?('sealring') \|\| BEOL & not PRECHECK_DRC] 6_10_sealring.drc:121 | – |  |
| Seal.n | KLayout only | – | Seal.n – [TABLES.include?('sealring') \|\| BEOL] 6_10_sealring.drc:85 | – |  |
| Slt.a | KLayout only | – | – | 5 names, e.g. Slt.a.M1, Slt.a.M2, Slt.a.M3 :2600-2694 |  |
| Slt.b | KLayout only | – | – | 5 names, e.g. Slt.b.M1, Slt.b.M2, Slt.b.M3 :2604-2698 |  |
| Slt.c | both | 30 [U] :383; 30 [U] :443; 30 [U] :501; 30 [U] :559; 30 [U] :597 | – | 5 names, e.g. Slt.c.M1, Slt.c.M2, Slt.c.M3 :2610-2704 |  |
| Slt.e | KLayout only | – | – | 5 names, e.g. Slt.e.M1, Slt.e.M2, Slt.e.M3 :2613-2707 |  |
| Slt.e1_M1 | KLayout only | – | Slt.e1_M1 – [TABLES.include?('metalslits') \|\| BEOL & not PRECHECK_DRC] 7_3_metalslits.drc:44 | – |  |
| Slt.e1_M2 | KLayout only | – | Slt.e1_M2 – [TABLES.include?('metalslits') \|\| BEOL & not PRECHECK_DRC] 7_3_metalslits.drc:44 | – |  |
| Slt.e1_M3 | KLayout only | – | Slt.e1_M3 – [TABLES.include?('metalslits') \|\| BEOL & not PRECHECK_DRC] 7_3_metalslits.drc:44 | – |  |
| Slt.e1_M4 | KLayout only | – | Slt.e1_M4 – [TABLES.include?('metalslits') \|\| BEOL & not PRECHECK_DRC] 7_3_metalslits.drc:44 | – |  |
| Slt.e1_TM1 | KLayout only | – | Slt.e1_TM1 – [TABLES.include?('metalslits') \|\| BEOL & not PRECHECK_DRC] 7_3_metalslits.drc:44 | – |  |
| Slt.f | KLayout only | – | – | 5 names, e.g. Slt.f.M1, Slt.f.M2, Slt.f.M3 :2616-2710 |  |
| Slt.h1 | KLayout only | – | – | Slt.h1 0.3 sg13cmos5l_maximal.drc:2620 |  |
| Slt.h2 | KLayout only | – | – | Slt.h2.M2 0.3 sg13cmos5l_maximal.drc:2644; Slt.h2.M3 0.3 sg13cmos5l_maximal.drc:2668; Slt.h2.M4 0.3 sg13cmos5l_maximal.drc:2691 |  |
| Slt.h3 | KLayout only | – | – | Slt.h3 1 sg13cmos5l_maximal.drc:2713 |  |
| TM1.a | both | 1.64 [FUR] :582 | TM1.a 1.64 [TABLES.include?('topmetal1') \|\| BEOL] 5_22_topmetal1.drc:32 | – |  |
| TM1.b | both | 1.64 [FUR] :583 | TM1.b 1.64 [TABLES.include?('topmetal1') \|\| BEOL] 5_22_topmetal1.drc:39 | – |  |
| TM1Fil.a | both | 5 [FUR] :587 | – | TM1Fil.a 5 [fillerRules] sg13cmos5l_maximal.drc:2293 |  |
| TM1Fil.a1 | both | 10 [FUR] :588 | TM1Fil.a1 10 [TABLES.include?('topmetal1filler') \|\| BEOL & not PRECHECK_DRC] 5_23_topmetal1filler.drc:47 | – |  |
| TM1Fil.b | both | 3 [FUR] :589 | – | TM1Fil.b 3 [fillerRules] sg13cmos5l_maximal.drc:2296 |  |
| TM1Fil.c | both | 3 [FUR] :590 | TM1Fil.c 3 [TABLES.include?('topmetal1filler') \|\| BEOL] 5_23_topmetal1filler.drc:39 | – |  |
| TM1Fil.d | Magic only | 4.9 [FUR] :592 | – | – |  |
| TM1Fil.g | Magic only | 90 [FUR] :594 | – | – |  |
| TV1.a | both | in (TV1.a + 2 * TV1.c) 0.62 [FUR] :567 | TV1.a 0.42 [TABLES.include?('topvia1') \|\| BEOL] 5_21_topvia1.drc:38 | – |  |
| TV1.b | both | in (TV1.b - 2 * TV1.c) 0.22 [FUR] :569 | TV1.b 0.42 [TABLES.include?('topvia1') \|\| BEOL] 5_21_topvia1.drc:47 | – |  |
| TV1.c | folded: Magic checks it only inside a composite rule | in (TV1.a + 2 * TV1.c) 0.62 [FUR] :567; in (TV1.b - 2 * TV1.c) 0.22 [FUR] :569; in (TV1.d - TV1.c) 0.32 [FUR] :571 | TV1.c 0.1 [TABLES.include?('topvia1') \|\| BEOL & not PRECHECK_DRC] 5_21_topvia1.drc:55 | – |  |
| TV1.d | both | in (TV1.d - TV1.c) 0.32 [FUR] :571 | TV1.d 0.42 [TABLES.include?('topvia1') \|\| BEOL & not PRECHECK_DRC] 5_21_topvia1.drc:62 | – |  |
| V2.a | both | in (V2.a + 2 * V2.c) 0.2 [FUR] :451 | V2.a 0.19 [TABLES.include?('vian') \|\| BEOL] 5_20_vian.drc:46 | – |  |
| V2.b | both | in (V2.b - 2 * V2.c) 0.21 [FUR] :453 | V2.b 0.22 [TABLES.include?('vian') \|\| BEOL] 5_20_vian.drc:55 | – |  |
| V2.b1 | KLayout only | – | – | V2.b1 0.29 sg13cmos5l_maximal.drc:2327 |  |
| V2.c | folded: Magic checks it only inside a composite rule | in (V2.a + 2 * V2.c) 0.2 [FUR] :451; in (V2.b - 2 * V2.c) 0.21 [FUR] :453; in (V2.c1 - V2.c) 0.045 [FUR] :455; in (M3.c1 - V2.c) 0.045 [FUR] :457 | V2.c 0.005 [TABLES.include?('vian') \|\| BEOL] 5_20_vian.drc:64 | – |  |
| V2.c1 | both | in (V2.c1 - V2.c) 0.045 [FUR] :455 | – | V2.c1 0.05 sg13cmos5l_maximal.drc:2334 |  |
| V3.a | both | in (V3.a + 2 * V3.c) 0.2 [FUR] :509 | V3.a 0.19 [TABLES.include?('vian') \|\| BEOL] 5_20_vian.drc:46 | – |  |
| V3.b | both | in (V3.b - 2 * V3.c) 0.21 [FUR] :511 | V3.b 0.22 [TABLES.include?('vian') \|\| BEOL] 5_20_vian.drc:55 | – |  |
| V3.b1 | KLayout only | – | – | V3.b1 0.29 sg13cmos5l_maximal.drc:2345 |  |
| V3.c | folded: Magic checks it only inside a composite rule | in (V3.a + 2 * V3.c) 0.2 [FUR] :509; in (V3.b - 2 * V3.c) 0.21 [FUR] :511; in (V3.c1 - V3.c) 0.045 [FUR] :513; in (M4.c1 - V3.c) 0.045 [FUR] :515 | V3.c 0.005 [TABLES.include?('vian') \|\| BEOL] 5_20_vian.drc:64 | – |  |
| V3.c1 | both | in (V3.c1 - V3.c) 0.045 [FUR] :513 | – | V3.c1 0.05 sg13cmos5l_maximal.drc:2352 |  |

## Rules only one side reported in a test

Each line gives a rule and the cases, controls left out, on which one engine reported it and the other did not. Magic's side is any of its styles; KLayout's side is the `main` and `maximal` decks of `run_drc.py`.

### Reported by Magic and not by the main and maximal decks

- `Act.c`: g_psd_half
- `Cnt.f`: u_Cnt.j2
- `Gat.a`: u_Cnt.j2
- `LU.d`: u_Cnt.h
- `LU.d1`: u_Cnt.h
- `M2.c`: u_V1.noM2
- `M2.d`: u_V1.noM2
- `NW.d`: g_nopsd_pmos

### Reported by KLayout and not by Magic

- `CMOS5L.FORB.*`: u_forbid.M5
- `Cnt.b1`: u_Cnt.b1
- `Cnt.g`: u_Cnt.g
- `Cnt.g1`: g_psd_half
- `Cnt.g2`: u_pSD.c
- `Cnt.h`: u_Cnt.h, u_Cnt.j
- `Cnt.j`: u_Cnt.j, u_Cnt.j2
- `CntB.a1`: u_CntB
- `Gat.a`: u_angle.poly
- `grid.Acute`: u_angle.poly
- `grid.Offgrid`: u_offgrid
- `M1.c`: u_Cnt.h, u_Cnt.j
- `M1.c1`: u_Cnt.h, u_Cnt.j
- `nSDB.a`: u_nSDB.a
- `NW.b1`: m_NW.a, u_NW.b1
- `Pin.e`: u_Pin.e
- `pSD.a`: u_pSD.a
- `pSD.b`: g_psd_on_nmos, u_pSD.b, u_pSD.j
- `pSD.c`: u_pSD.c
- `pSD.c1`: u_pSD.c1
- `pSD.d`: u_pSD.d
- `pSD.i`: u_pSD.i
- `pSD.j`: u_pSD.j
- `pSD.k`: u_pSD.k
- `Sal.a`: u_Sal.a
- `TGO.a`: g_hv_tgo_small
- `TGO.f`: u_TGO.f
- `V1.a`: m_V1.a
- `V1.b1`: u_V1.b1
