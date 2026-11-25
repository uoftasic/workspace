# Gap table: gf180mcuD

This table compares Magic's DRC rules for gf180mcuD with the PDK's KLayout DRC decks, one row per rule, and shows where they disagree. `tools/build_gaps.py` generates it; do not edit it by hand.

- **What a row is.** One rule, under the rule ID that Magic's why-text gives it (the why-text is the message Magic's DRC gives an error box, and the ID is the text in its last parentheses), under a name from `tests/gaps/aliases-gf180mcuD.json` where the two tools name the rule differently, under the KLayout name where Magic has no such rule, or under Magic's whole message where the message has no ID. The row gives the statements of Magic's tech file that check the rule, each KLayout deck's outputs for it (the report categories the deck writes), and what both engines reported on the test cases that target it.
- **How it is made.** Magic's rules come from `python/klayout_magic_pcells/data/pdk-gf180mcuD.json`. Each KLayout run below checked a layout of one box. Its report has a category for every rule the deck ran under its switches, and those categories are the deck's side of the table; a text scan of the deck gives each output's line and the switches it sits under. The two sides are joined on rule ID, with the mappings made by hand in `tests/gaps/aliases-gf180mcuD.json`. The test cases are the `gaps` set of the case suite (`tests/cases`): a clean control layout, and cases that each change one thing in it. Magic checked each case cell alone in all three styles, at most 15 cells per process; KLayout checked them on one sheet, 40 µm apart. A case's results are the rules reported on it and not on its control.
- **Image.** The pinned Docker image `hpretl/iic-osic-tools@sha256:3c371645b19c6f6564dc8c7b21e39ad1c1833d274fe5b85639afe1ba9d7987e7`, with Magic 8.3.681 and KLayout 0.30.11; open_pdks 026824c7 (Magic tech 1.0.588-56-g026824c).
- **Rebuild.** `scripts/gaps.sh --pdk gf180mcuD` rewrites this page; `scripts/gaps.sh --pdk gf180mcuD --check` fails if it would change.

Each row has one status. The status and the value comparison take `gf180mcu.drc` as the KLayout side; the other decks have their own columns.

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

| Part | both | both, values differ | folded | measured on other shapes | in the deck, did not fire on its case | Magic only | KLayout only | total |
|---|---|---|---|---|---|---|---|---|
| Grid and angle checks | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 2 |
| Upper metals, vias and MIM | 34 | 3 | 6 | 0 | 0 | 1 | 60 | 104 |
| Wells to via1 | 71 | 4 | 2 | 2 | 3 | 13 | 344 | 439 |
| all | 105 | 7 | 8 | 2 | 3 | 14 | 406 | 545 |

## KLayout runs

Each run checked a layout of one box; the last column counts the categories in its report. "The harness" is the plugin's parity harness (`tests/parity`).

| Run | What | Categories on one box |
|---|---|---|
| harness | gf180mcu.drc with the harness's switches (decks=all,-density, run_mode=deep, threads=1, variant=D) | 763 |

Cases: 69 in the `gaps` set.

## Rules

### Grid and angle checks

| Rule | Status | Magic: value [styles] :line | gf180mcu.drc: name value [switch] :line | Tested (case: what each engine reported) |
|---|---|---|---|---|
| ACUTE (per layer) | KLayout only | – | 93 names, e.g. border_ACUTE, cap_mk_ACUTE, comp_ACUTE :29-29 |  |
| OFFGRID (per layer) | KLayout only | – | 93 names, e.g. border_OFFGRID, cap_mk_OFFGRID, comp_OFFGRID :26-26 |  |

### Upper metals, vias and MIM

| Rule | Status | Magic: value [styles] :line | gf180mcu.drc: name value [switch] :line | Tested (case: what each engine reported) |
|---|---|---|---|---|
| DM2.2b | KLayout only | – | DM2.2b 0.98 :33 |  |
| DM2.3 | KLayout only | – | DM2.3 2 :39 |  |
| DM2.8 | KLayout only | – | DM2.8 6 :66 |  |
| DM3.2b | KLayout only | – | DM3.2b 0.98 :33 |  |
| DM3.3 | KLayout only | – | DM3.3 2 :39 |  |
| DM3.8 | KLayout only | – | DM3.8 6 :66 |  |
| DM4.2b | KLayout only | – | DM4.2b 0.98 :33 |  |
| DM4.3 | KLayout only | – | DM4.3 2 :39 |  |
| DM4.8 | KLayout only | – | DM4.8 6 :66 |  |
| DM5.2b | KLayout only | – | DM5.2b 0.98 :33 |  |
| DM5.3 | KLayout only | – | DM5.3 2 :39 |  |
| DM5.8 | KLayout only | – | DM5.8 6 :66 |  |
| M2.1 | both | 0.28 [FUR] :2983 | M2.1 0.28 [idx == 1 / not (idx == 1)] :37,43 |  |
| M2.2a | both | 0.28 [FUR] :2984 | M2.2a 0.28 :49 |  |
| M2.2b | both | 0.3 [FU] :2988 | M2.2b 0.3 :60 |  |
| M2.3 | both | 0.1444 µm² [FUR] :2985 | M2.3 0.1444 µm² :66 |  |
| M3.1 | both | 0.28 [FUR] :3011 | M3.1 0.28 [idx == 1 / not (idx == 1)] :37,43 |  |
| M3.2a | both | 0.28 [FUR] :3012 | M3.2a 0.28 :49 |  |
| M3.2b | both | 0.3 [FU] :3016 | M3.2b 0.3 :60 |  |
| M3.3 | both | 0.1444 µm² [FUR] :3013 | M3.3 0.1444 µm² :66 |  |
| M4.1 | both | 0.28 [FUR] :3039 | M4.1 0.28 [idx == 1 / not (idx == 1)] :37,43 |  |
| M4.2a | both | 0.28 [FUR] :3040 | M4.2a 0.28 :49 |  |
| M4.2b | both | 0.3 [FU] :3044 | M4.2b 0.3 :60 |  |
| M4.3 | both, values differ: Magic 0.144 µm², KLayout 0.1444 µm² | 0.144 µm² [FUR] :3041 | M4.3 0.1444 µm² :66 |  |
| MIM1M.X | Magic only | 0.05 [FUR] :3188 | – |  |
| MIMTM.1 | both | 1.2 [FUR] :3193; 1.2 [U] :3202 | MIMTM.1 1.2 :39 |  |
| MIMTM.2 | both | 0.4 [U] :3204 | MIMTM.2 0.4 :51 |  |
| MIMTM.3 | both | 0.6 [FUR] :3197 | MIMTM.3 – :64 |  |
| MIMTM.4 | both | in (MIMTM.4-VT.4) 0.39 [FUR] :3186 | MIMTM.4 0.4 :75 |  |
| MIMTM.5 | both, values differ: Magic 0.39, KLayout 0.4; Magic measures to its via4 area, and if that area is the cut plus 0.01 µm per side, as tech:3053's V4.1 + 2 * V4.4 implies, its 0.39 µm is 0.4 µm from the cut (not measured) | 0.39 [FUR] :3195 | MIMTM.5 0.4 :83 |  |
| MIMTM.6 | both | 0.6 [FUR] :3184 | MIMTM.6 0.6 :90 |  |
| MIMTM.7 | KLayout only | – | MIMTM.7 0 :96 |  |
| MIMTM.8a | both | 5 [FUR] :3183 | MIMTM.8a 25 µm² :102 |  |
| MIMTM.8b | KLayout only | – | MIMTM.8b 10000 :109 |  |
| MIMTM.9 | both | in (MIMTM.9 - 2 * VT.3) 0.48 [FUR] :3189 | MIMTM.9 0.5 :116 |  |
| MIMTM.10 | both | 0.05 [FUR] :3191 | MIMTM.10 – :123 |  |
| MIMTM.11 | KLayout only | – | MIMTM.11 – :144 |  |
| MSLOT2.0 | KLayout only | – | MSLOT2.0 – :60 |  |
| MSLOT2.1 | KLayout only | – | MSLOT2.1 30 :67 |  |
| MSLOT2.2 | KLayout only | – | MSLOT2.2 2 :75 |  |
| MSLOT2.3 | KLayout only | – | MSLOT2.3 250 :81 |  |
| MSLOT2.4 | KLayout only | – | MSLOT2.4 10 :87 |  |
| MSLOT2.5 | KLayout only | – | MSLOT2.5 10 :93 |  |
| MSLOT2.7 | KLayout only | – | MSLOT2.7 0.2 :99 |  |
| MSLOT2.8 | KLayout only | – | MSLOT2.8 0.2 :105 |  |
| MSLOT2.9 | KLayout only | – | MSLOT2.9 5 :111 |  |
| MSLOT3.0 | KLayout only | – | MSLOT3.0 – :60 |  |
| MSLOT3.1 | KLayout only | – | MSLOT3.1 30 :67 |  |
| MSLOT3.2 | KLayout only | – | MSLOT3.2 2 :75 |  |
| MSLOT3.3 | KLayout only | – | MSLOT3.3 250 :81 |  |
| MSLOT3.4 | KLayout only | – | MSLOT3.4 10 :87 |  |
| MSLOT3.5 | KLayout only | – | MSLOT3.5 10 :93 |  |
| MSLOT3.7 | KLayout only | – | MSLOT3.7 0.2 :99 |  |
| MSLOT3.8 | KLayout only | – | MSLOT3.8 0.2 :105 |  |
| MSLOT3.9 | KLayout only | – | MSLOT3.9 5 :111 |  |
| MSLOT4.0 | KLayout only | – | MSLOT4.0 – :60 |  |
| MSLOT4.1 | KLayout only | – | MSLOT4.1 30 :67 |  |
| MSLOT4.2 | KLayout only | – | MSLOT4.2 2 :75 |  |
| MSLOT4.3 | KLayout only | – | MSLOT4.3 250 :81 |  |
| MSLOT4.4 | KLayout only | – | MSLOT4.4 10 :87 |  |
| MSLOT4.5 | KLayout only | – | MSLOT4.5 10 :93 |  |
| MSLOT4.7 | KLayout only | – | MSLOT4.7 0.2 :99 |  |
| MSLOT4.8 | KLayout only | – | MSLOT4.8 0.2 :105 |  |
| MSLOT4.9 | KLayout only | – | MSLOT4.9 5 :111 |  |
| MSLOT5.0 | KLayout only | – | MSLOT5.0 – :60 |  |
| MSLOT5.1 | KLayout only | – | MSLOT5.1 30 :67 |  |
| MSLOT5.2 | KLayout only | – | MSLOT5.2 2 :75 |  |
| MSLOT5.3 | KLayout only | – | MSLOT5.3 250 :81 |  |
| MSLOT5.4 | KLayout only | – | MSLOT5.4 10 :87 |  |
| MSLOT5.5 | KLayout only | – | MSLOT5.5 10 :93 |  |
| MSLOT5.7 | KLayout only | – | MSLOT5.7 0.2 :99 |  |
| MSLOT5.8 | KLayout only | – | MSLOT5.8 0.2 :105 |  |
| MSLOT5.9 | KLayout only | – | MSLOT5.9 5 :111 |  |
| MT.1 | both | 0.44 [FUR] :3067 | MT.1 0.44 :35,64 |  |
| MT.2a | both | 0.46 [FUR] :3068 | MT.2a 0.46 :41,70 |  |
| MT.2b | both | 0.6 [FU] :3072 | MT.2b 0.6 :48,77 |  |
| MT.4 | both, values differ: Magic 0.5265 µm², KLayout 0.5625 µm² | 0.5265 µm² [FUR] :3069 | MT.4 0.5625 µm² :55,84 |  |
| V2.1 | both | in (V2.1 + 2 * V2.3) 0.28 [FUR] :2997 | V2.1 0.26 :27 |  |
| V2.2a | both | in (V2.2a - 2 * V2.3) 0.24 [FUR] :2998 | V2.2a 0.26 :35 |  |
| V2.2b | KLayout only | – | V2.2b 0.36 :49 |  |
| V2.3b | folded: Magic checks it only inside a composite rule | in (V2.1 + 2 * V2.3) 0.28 [FUR] :2997; in (V2.2a - 2 * V2.3) 0.24 [FUR] :2998; in (V2.3i - V2.3) 0.05 [FUR] :2999 | V2.3b 0.01 :86 |  |
| V2.3c | KLayout only | – | V2.3c 0.06 :104 |  |
| V2.3d | both | in (V2.3i - V2.3) 0.05 [FUR] :2999 | V2.3d 0.06 :127 |  |
| V2.4a | folded: Magic checks it only inside a composite rule | in (V2.4i - V2.4) 0.05 [FUR] :3008 | V2.4a 0.01 :148 |  |
| V2.4b | KLayout only | – | V2.4b 0.06 :165 |  |
| V2.4c | both | in (V2.4i - V2.4) 0.05 [FUR] :3008 | V2.4c 0.06 :186 |  |
| V3.1 | both | in (V3.1 + 2 * V3.4) 0.28 [FUR] :3025 | V3.1 0.26 :27 |  |
| V3.2a | both | in (V3.2a - 2 * V3.4) 0.24 [FUR] :3026 | V3.2a 0.26 :35 |  |
| V3.2b | KLayout only | – | V3.2b 0.36 :49 |  |
| V3.3b | folded: Magic checks it only inside a composite rule | in (V3.3i - V3.3) 0.05 [FUR] :3027 | V3.3b 0.01 :86 |  |
| V3.3c | KLayout only | – | V3.3c 0.06 :104 |  |
| V3.3d | both | in (V3.3i - V3.3) 0.05 [FUR] :3027 | V3.3d 0.06 :127 |  |
| V3.4a | folded: Magic checks it only inside a composite rule | in (V3.1 + 2 * V3.4) 0.28 [FUR] :3025; in (V3.2a - 2 * V3.4) 0.24 [FUR] :3026; in (V3.4i - V3.4) 0.05 [FUR] :3036 | V3.4a 0.01 :148 |  |
| V3.4b | KLayout only | – | V3.4b 0.06 :165 |  |
| V3.4c | both | in (V3.4i - V3.4) 0.05 [FUR] :3036 | V3.4c 0.06 :186 |  |
| V4.1 | both | in (V4.1 + 2 * V4.4) 0.28 [FUR] :3053; in (VT.1+VT.3) 0.28 [FUR] :3199 | V4.1 0.26 :27 |  |
| V4.2a | both | in (V4.2a - 2 * V4.4) 0.24 [FUR] :3054 | V4.2a 0.26 :35 |  |
| V4.2b | KLayout only | – | V4.2b 0.36 :49 |  |
| V4.3b | folded: Magic checks it only inside a composite rule | in (V4.3i - V4.3) 0.05 [FUR] :3062; in (MIMTM.9 - 2 * VT.3) 0.48 [FUR] :3189; in (VT.1+VT.3) 0.28 [FUR] :3199 | V4.3b 0.01 :86 |  |
| V4.3c | KLayout only | – | V4.3c 0.06 :104 |  |
| V4.3d | both | in (V4.3i - V4.3) 0.05 [FUR] :3062 | V4.3d 0.06 :127 |  |
| V4.4a | folded: Magic checks it only inside a composite rule | in (V4.1 + 2 * V4.4) 0.28 [FUR] :3053; in (V4.2a - 2 * V4.4) 0.24 [FUR] :3054; in (V4.4i - V4.4) 0.05 [FUR] :3064; in (MIMTM.4-VT.4) 0.39 [FUR] :3186 | V4.4a 0.01 :148 |  |
| V4.4b | KLayout only | – | V4.4b 0.06 :165 |  |
| V4.4c | both | in (V4.4i - V4.4) 0.05 [FUR] :3064 | V4.4c 0.06 :186 |  |

### Wells to via1

| Rule | Status | Magic: value [styles] :line | gf180mcu.drc: name value [switch] :line | Tested (case: what each engine reported) |
|---|---|---|---|---|
| ANT.1 | KLayout only | – | ANT.1 200 :62 |  |
| ANT.8 | KLayout only | – | ANT.8 10 :89 |  |
| ANT.16_i_ANT.2 | KLayout only | – | ANT.16_i_ANT.2 400 :118 |  |
| ANT.16_i_ANT.3 | KLayout only | – | ANT.16_i_ANT.3 400 :186 |  |
| ANT.16_i_ANT.4 | KLayout only | – | ANT.16_i_ANT.4 400 :276 |  |
| ANT.16_i_ANT.5 | KLayout only | – | ANT.16_i_ANT.5 400 :382 |  |
| ANT.16_i_ANT.6 | KLayout only | – | ANT.16_i_ANT.6 400 :492 |  |
| ANT.16_i_ANT.9 | KLayout only | – | ANT.16_i_ANT.9 20 :152 |  |
| ANT.16_i_ANT.10 | KLayout only | – | ANT.16_i_ANT.10 20 :226 |  |
| ANT.16_i_ANT.11 | KLayout only | – | ANT.16_i_ANT.11 20 :327 |  |
| ANT.16_i_ANT.12 | KLayout only | – | ANT.16_i_ANT.12 20 :435 |  |
| ANT.16_ii_ANT.2 | KLayout only | – | ANT.16_ii_ANT.2 400 :123 |  |
| ANT.16_ii_ANT.3 | KLayout only | – | ANT.16_ii_ANT.3 400 :190 |  |
| ANT.16_ii_ANT.4 | KLayout only | – | ANT.16_ii_ANT.4 400 :280 |  |
| ANT.16_ii_ANT.5 | KLayout only | – | ANT.16_ii_ANT.5 400 :386 |  |
| ANT.16_ii_ANT.6 | KLayout only | – | ANT.16_ii_ANT.6 – :496 |  |
| ANT.16_ii_ANT.9 | KLayout only | – | ANT.16_ii_ANT.9 20 :156 |  |
| ANT.16_ii_ANT.10 | KLayout only | – | ANT.16_ii_ANT.10 20 :230 |  |
| ANT.16_ii_ANT.11 | KLayout only | – | ANT.16_ii_ANT.11 20 :331 |  |
| ANT.16_ii_ANT.12 | KLayout only | – | ANT.16_ii_ANT.12 20 :439 |  |
| ANT.16_iii_ANT.14_M4_MIMB | KLayout only | – | ANT.16_iii_ANT.14_M4_MIMB – [%w[A B].include? ctx.mim_option] :391 |  |
| ANT.16_iii_ANT.14_M5_MIMB | KLayout only | – | ANT.16_iii_ANT.14_M5_MIMB – [%w[A B].include? ctx.mim_option] :501 |  |
| ANT.16_iii_ANT.15_V3_MIMB | KLayout only | – | ANT.16_iii_ANT.15_V3_MIMB – [%w[A B].include? ctx.mim_option] :336 |  |
| ANT.16_iii_ANT.15_V4_MIMB | KLayout only | – | ANT.16_iii_ANT.15_V4_MIMB – [%w[A B].include? ctx.mim_option] :444 |  |
| BJT.1 | KLayout only | – | BJT.1 0 :36 |  |
| BJT.2 | KLayout only | – | BJT.2 0 :42 |  |
| BJT.3 | KLayout only | – | BJT.3 0.1 :48 |  |
| CO.1 | both | in (CO.1 + 2 * CO.6) 0.23 [FUR] :2880; in (CO.1 + 2 * CO.6) 0.23 [FUR] :2901 | CO.1 0.22 :25 | CO1_big030: Magic no, KLayout harness; CO1_small020: Magic FUR, KLayout harness |
| CO.2a | in the deck, did not fire on its case: Magic reported nothing on CO2a_s022, CO2b_4x4_s010 | in (CO.2a - 2 * CO.6) 0.24 [FUR] :2882; in (CO.2a - 2 * CO.6) 0.24 [FUR] :2903; in (CO.2a - 2 * CO.6) 0.24 [FUR] :2932; in (CO.2a - 2 * CO.6) 0.24 [FUR] :2934; in (CO.2a - 2 * CO.6) 0.24 [FUR] :2936; in (CO.2a - 2 * CO.6) 0.24 [FUR] :2938 | CO.2a 0.25 :32 | CO2a_s022: Magic no, KLayout harness; CO2b_4x4_s010: Magic no, KLayout harness |
| CO.2b | KLayout only | – | CO.2b 0.28 :55 | CO2b_4x4_s010: Magic no, KLayout no; CO2b_4x4_s026: Magic no, KLayout harness |
| CO.3 | both: Magic grows each contact by 0.005 µm per side when it reads it (a 0.22 µm cut becomes a 0.23 µm contact area, GAPS-gf180mcuD 1), so its 0.065 µm is 0.07 µm from the cut | 0.065 [FUR] :2899 | CO.3 0.07 :66 | CO3_pov004: Magic FUR, KLayout harness |
| CO.4 | both: Magic grows each contact by 0.005 µm per side when it reads it (a 0.22 µm cut becomes a 0.23 µm contact area, GAPS-gf180mcuD 1), so its 0.065 µm is 0.07 µm from the cut | 0.065 [FUR] :2887; 0.065 [FUR] :2889; 0.065 [FUR] :2891; 0.065 [FUR] :2893; 0.065 [FUR] :2895; 0.065 [FUR] :2897; 7 more | CO.4 0.07 :81 | CO4_cov004: Magic FUR, KLayout harness |
| CO.5a | KLayout only | – | CO.5a 0.1 :96 |  |
| CO.5b | KLayout only | – | CO.5b 0.1 :111 |  |
| CO.6 | both: Magic's directional overlap (tech:2885, 2906) is 0.055 µm from its contact area, 0.06 µm from the cut, as KLayout's CO.6a; both decks agreed on the two CO.6 cases (GAPS-gf180mcuD 1) | in (CO.1 + 2 * CO.6) 0.23 [FUR] :2880; in (CO.2a - 2 * CO.6) 0.24 [FUR] :2882; 0.055 [FUR] :2885; in (CO.1 + 2 * CO.6) 0.23 [FUR] :2901; in (CO.2a - 2 * CO.6) 0.24 [FUR] :2903; 0.055 [FUR] :2906; 8 more | CO.6 0.005 :125; CO.6a 0.06 :145; CO.6b 0.06 :175 | CO6_m1ov0: Magic FUR, KLayout harness; CO6_m1ov002: Magic no, KLayout no |
| CO.7 | both | in (CO.7 - 2 * CO.6) 0.145 [FUR] :2941 | CO.7 0.15 :196 | CO7_c2g012: Magic FUR, KLayout harness |
| CO.8 | both | in (CO.8 - 2 * CO.6) 0.165 [FUR] :2939 | CO.8 0.17 :205 | CO8_pc2c014: Magic FUR, KLayout harness |
| CO.9 | KLayout only | – | CO.9 – :215 | BUTT_straddle: Magic no, KLayout harness |
| CO.10 | KLayout only | – | CO.10 – :225 | CO10_cont_on_gate: Magic no, KLayout harness |
| CO.11 | KLayout only | – | CO.11 – :235 | CO11_cont_field: Magic no, KLayout harness |
| CUP.2 | KLayout only | – | CUP.2 1 :45 |  |
| CUP.3 | KLayout only | – | CUP.3 1 :50 |  |
| DCF.2b | KLayout only | – | DCF.2b 1.9 :36 |  |
| DCF.4 | KLayout only | – | DCF.4 3.5 :42 |  |
| DCF.5 | KLayout only | – | DCF.5 1.5 :48 |  |
| DCF.6a | KLayout only | – | DCF.6a 1.3 :54 |  |
| DCF.6b | KLayout only | – | DCF.6b 4 :60 |  |
| DCF.6c | KLayout only | – | DCF.6c 1.3 :66 |  |
| DCF.6d | KLayout only | – | DCF.6d 1.3 :72 |  |
| DCF.8a | KLayout only | – | DCF.8a 3.5 :78 |  |
| DCF.11a | KLayout only | – | DCF.11a 3.5 :84 |  |
| DCF.12 | KLayout only | – | DCF.12 3 :90 |  |
| DE.2 | KLayout only | – | DE.2 0.8 :35 |  |
| DE.3 | KLayout only | – | DE.3 80 :44 |  |
| DE.4 | KLayout only | – | DE.4 20 :53 |  |
| DF.1a | both | 0.22 [FUR] :2743; 0.3 [FUR] :2744 | DF.1a_LV 0.22 :29; DF.1a_MV 0.3 :44 | DF1a_w020: Magic FUR, KLayout harness |
| DF.1b | Magic only | 0.3 [FUR] :3154; 0.3 [FUR] :3155 | – |  |
| DF.1c | both | 1 [FUR] :3167; 1 [FUR] :3176 | DF.1c 1 :64 |  |
| DF.2a | KLayout only | – | DF.2a_LV 0.22 :79; DF.2a_MV 0.3 :96 |  |
| DF.2b | KLayout only | – | DF.2b 100 :112 |  |
| DF.2c | Magic only | 0.4 [FUR] :3089 | – |  |
| DF.3a | both | 0.28 [FUR] :2747; 0.36 [FUR] :2749; 0.36 [FUR] :2751; 0.36 [FUR] :2753 | DF.3a_LV 0.28 :128; DF.3a_MV 0.36 :145 | DF3a_s025: Magic FUR, KLayout harness |
| DF.3b | KLayout only | – | DF.3b 0 :165 |  |
| DF.3c | KLayout only | – | DF.3c_LV 0.32 :184; DF.3c_MV – :199 |  |
| DF.4a | KLayout only | – | DF.4a_LV 0.12 :215; DF.4a_MV 0.16 :230 |  |
| DF.4b | both | 0.62 [FUR] :2787; 0.66 [FUR] :2789 | DF.4b_LV 0.62 :245; DF.4b_MV 0.66 :260 |  |
| DF.4c | both | as DF.7 0.43 [FUR] :2779; as DF.7 0.6 [FUR] :2781 | DF.4c_LV 0.43 :277; DF.4c_MV 0.6 :296 | DF7_pdiff_nw038: Magic FUR, KLayout harness |
| DF.4d | both | as DF.4a 0.12 [FUR] :2775; as DF.4a 0.16 [FUR] :2777 | DF.4d_LV 0.12 :316; DF.4d_MV 0.16 :337 | DF4a_ntap_nw008: Magic FUR, KLayout harness |
| DF.4e | both | 0.93 [FUR] :2791; 1.1 [FUR] :2793 | DF.4e_LV 0.93 :355; DF.4e_MV 1.1 :370 |  |
| DF.5 | both | 0.12 [U] :2802; 0.16 [U] :2804 | DF.5_LV 0.12 :384; DF.5_MV 0.16 :397 |  |
| DF.6 | both, values differ: Magic 0.23, KLayout 0.24, 0.4 | 0.23 [FUR] :2843; 0.23 [FUR] :2844; 0.23 [FUR] :2846; 0.23 [FUR] :2848; 0.23 [FUR] :2849; 0.23 [FUR] :2850 | DF.6_LV 0.24 :414; DF.6_MV 0.4 :435 | DF6_lv_0235: Magic no, KLayout harness; DF6_mv_030: Magic no, KLayout harness |
| DF.7 | KLayout only | – | DF.7_LV 0.43 :453; DF.7_MV 0.6 :468 |  |
| DF.8 | both | 0.43 [U] :2806; 0.6 [U] :2808 | DF.8_LV 0.43 :483; DF.8_MV 0.6 :498 |  |
| DF.9 | both | 0.2025 µm² [FUR] :2745; 0.2025 µm² [FUR] :2746 | DF.9 0.2025 µm² :512 | DF9_a018: Magic FUR, KLayout harness |
| DF.10 | KLayout only | – | DF.10 0.26 µm² :525 |  |
| DF.11 | KLayout only | – | DF.11 0.3 :539 |  |
| DF.12 | KLayout only | – | DF.12 – :553 | DF12_noimp: Magic no, KLayout harness |
| DF.13 | KLayout only | – | DF.13_LV 20 :578; DF.13_MV 15 :606 | DF13_nwnotap: Magic no, KLayout harness |
| DF.14 | KLayout only | – | DF.14_LV 20 :626; DF.14_MV 15 :646 | DF14_notap: Magic no, KLayout harness; DF14_tap25: Magic no, KLayout harness |
| DF.16 | both | as DF.8 0.43 [FUR] :2761; as DF.8 0.6 [FUR] :2763 | DF.16_LV 0.43 :681; DF.16_MV 0.6 :705 | DF8_ndiff_nw038: Magic FUR, KLayout harness |
| DF.17 | both | as DF.5 0.12 [FUR] :2769; as DF.5 0.16 [FUR] :2771 | DF.17_LV 0.12 :727; DF.17_MV 0.16 :749 | DF5_ptap_nw008: Magic FUR, KLayout harness |
| DF.18 | KLayout only | – | DF.18 2.5 :768 |  |
| DF.19 | KLayout only | – | DF.19_LV 3.2 :785; DF.19_MV 3.28 :804 |  |
| DM1.2b | KLayout only | – | DM1.2b 0.98 :33 |  |
| DM1.3 | KLayout only | – | DM1.3 2 :39 |  |
| DM1.8 | KLayout only | – | DM1.8 6 :66 |  |
| DN.1 | both | 1.7 [FUR] :2704 | DN.1 1.7 :32 |  |
| DN.2a | both | 2.5 [FUR] :2705 | DN.2a 2.5 :39 |  |
| DN.2b | KLayout only | – | DN.2b 5.42 :46 |  |
| DN.3 | KLayout only | – | DN.3 – :55 |  |
| DN.11 | Magic only | – [U] :2723 | – |  |
| DPF.1 | both | 5.6 [FUR] :2829 | DPF.1 – :34 |  |
| DPF.2a | Magic only | 2.4 [FUR] :2832 | – |  |
| DPF.2b | both | 1.1 [FUR] :2834 | DPF.2b 1.1 :40 |  |
| DPF.4 | KLayout only | – | DPF.4 3.2 :46 |  |
| DPF.5 | both | 5 [FUR] :2831 | DPF.5 5 :52 |  |
| DPF.6a | KLayout only | – | DPF.6a 1 :58 |  |
| DPF.6b | KLayout only | – | DPF.6b 2 :64 |  |
| DPF.6c | KLayout only | – | DPF.6c 1 :70 |  |
| DPF.6d | KLayout only | – | DPF.6d 1 :76 |  |
| DPF.8 | KLayout only | – | DPF.8 19.7 :82 |  |
| DPF.9 | KLayout only | – | DPF.9 6.7 :88 |  |
| DPF.11 | KLayout only | – | DPF.11 29.7 :94 |  |
| DPF.14 | KLayout only | – | DPF.14 3 :119 |  |
| DPF.16 | KLayout only | – | DPF.16 3 :125 |  |
| DPF.19 | KLayout only | – | DPF.19 8 :131 |  |
| DV.1 | KLayout only | – | DV.1 0.5 :34 |  |
| DV.2 | KLayout only | – | DV.2 0.44 :42 |  |
| DV.3 | folded: Magic checks it only inside a composite rule | in (DV.6 + DV.3) 0.48 [FUR] :2756; in (DV.6 + DV.3) 0.48 [FUR] :2758 | DV.3 0.24 :48 |  |
| DV.5 | KLayout only | – | DV.5 0.7 :57 |  |
| DV.6 | in the deck, did not fire on its case: Magic reported nothing on DG_small | in (DV.6 + DV.3) 0.48 [FUR] :2756; in (DV.6 + DV.3) 0.48 [FUR] :2758 | DV.6 0.24 :66 | DG_small: Magic no, KLayout harness |
| DV.7 | KLayout only | – | DV.7 – :74 | DG_partial: Magic no, KLayout harness |
| DV.8 | KLayout only | – | DV.8 0.4 :84 | DG_small: Magic no, KLayout harness |
| DV.9 | both | – [U] :2726 | DV.9 3.3 :92 | DV9_lvmv_nwell: Magic U, KLayout harness |
| EF.01 | KLayout only | – | EF.01 0 :43 |  |
| EF.02 | KLayout only | – | EF.02 0.18 :49 |  |
| EF.03 | KLayout only | – | EF.03 1.26 :56 |  |
| EF.04a | KLayout only | – | EF.04a – :67 |  |
| EF.04b | KLayout only | – | EF.04b – :77 |  |
| EF.04c | KLayout only | – | EF.04c – :83 |  |
| EF.04d | KLayout only | – | EF.04d – :89 |  |
| EF.05 | KLayout only | – | EF.05 0 :97 |  |
| EF.06 | KLayout only | – | EF.06 2.26 :109 |  |
| EF.07 | KLayout only | – | EF.07 1.84 :115 |  |
| EF.08 | KLayout only | – | EF.08 1.06 :124 |  |
| EF.09 | KLayout only | – | EF.09 2.43 :130 |  |
| EF.10 | KLayout only | – | EF.10 0.26 :137 |  |
| EF.11 | KLayout only | – | EF.11 0.26 :143 |  |
| EF.12 | KLayout only | – | EF.12 – :150 |  |
| EF.13 | KLayout only | – | EF.13 – :156 |  |
| EF.14 | KLayout only | – | EF.14 – :163 |  |
| EF.15 | KLayout only | – | EF.15 – :169 |  |
| EF.16a | KLayout only | – | EF.16a 4 :175 |  |
| EF.16b | KLayout only | – | EF.16b 4 :181 |  |
| EF.17 | KLayout only | – | EF.17 0.26 :187 |  |
| EF.18 | KLayout only | – | EF.18 – :195 |  |
| EF.19 | KLayout only | – | EF.19 – :202 |  |
| EF.20 | KLayout only | – | EF.20 2.73 :208 |  |
| EF.21 | KLayout only | – | EF.21 5.53 :217 |  |
| EF.22a | KLayout only | – | EF.22a 1.04 :227 |  |
| EF.22b | KLayout only | – | EF.22b 0.44 :234 |  |
| ESD.1 | KLayout only | – | ESD.1 0.6 :37 |  |
| ESD.2 | KLayout only | – | ESD.2 0.6 :44 |  |
| ESD.3a | KLayout only | – | ESD.3a 0.6 :51 |  |
| ESD.3b | KLayout only | – | ESD.3b – :57 |  |
| ESD.4a | KLayout only | – | ESD.4a 0.24 :63 |  |
| ESD.4b | KLayout only | – | ESD.4b 0.45 :69 |  |
| ESD.5a | KLayout only | – | ESD.5a 0.49 µm² :75 |  |
| ESD.5b | KLayout only | – | ESD.5b 0.49 µm² :81 |  |
| ESD.6 | KLayout only | – | ESD.6 0.45 :87 |  |
| ESD.7 | KLayout only | – | ESD.7 – :94 |  |
| ESD.8 | KLayout only | – | ESD.8 0.3 :100 |  |
| ESD.9 | KLayout only | – | ESD.9 – :116 |  |
| ESD.10 | KLayout only | – | ESD.10 – :123 |  |
| ESD.pl | KLayout only | – | ESD.pl 0.8 :107 |  |
| exact_overlap | Magic only | – [FUR] :2944; – [FUR] :2945; – [FUR] :2946; – [FUR] :2947; – [FUR] :2977; – [FUR] :3002; 2 more | – |  |
| GR.1 | KLayout only | – | GR.1 0 :43 |  |
| GR.2 | KLayout only | – | GR.2 10 :49,52,55,64 |  |
| GR.3 | KLayout only | – | GR.3 0 :71 |  |
| GR.4 | KLayout only | – | GR.4 12 :82 |  |
| GR.6 | KLayout only | – | GR.6 16 :89 |  |
| GR.11 | KLayout only | – | GR.11 – :109 |  |
| HRES.1 | KLayout only | – | HRES.1 0.4 :38 |  |
| HRES.2 | both | as HRES.3 1 [FUR] :3135 | HRES.2 1 :44 |  |
| HRES.3 | both | as HRES.2 0.4 [FUR] :3136 | HRES.3 0.4 :50 |  |
| HRES.4 | folded: Magic checks it only inside a composite rule | in (HRES.5 + HRES.4) 0.7 [U] :3140; in (HRES.6 + HRES.4) 0.7 [U] :3142 | HRES.4 0.4 :58 |  |
| HRES.5 | both | in (HRES.5 + HRES.4) 0.7 [U] :3140 | HRES.5 0.3 :66 |  |
| HRES.6 | both | in (HRES.6 + HRES.4) 0.7 [U] :3142 | HRES.6 0.3 :74 |  |
| HRES.7 | KLayout only | – | HRES.7 0.2 :86 |  |
| HRES.8 | both | as PRES/LRES/HRES.7 0.22 [U] :3145; as PRES/LRES/HRES.7 0.22 [U] :3147 | HRES.8 – :95 |  |
| HRES.9 | KLayout only | – | HRES.9 – :109 |  |
| HRES.10 | KLayout only | – | HRES.10 – :123 |  |
| HRES.12a | KLayout only | – | HRES.12a – :137 |  |
| HRES.12b | KLayout only | – | HRES.12b 20 :150 |  |
| LPW.1 | both | 0.6 [U] :2715; 0.74 [U] :2716 | LPW.1_LV 0.6 :35; LPW.1_MV 0.74 :41 |  |
| LPW.2a | KLayout only | – | LPW.2a_LV 1.4 :50; LPW.2a_MV 1.7 :57 |  |
| LPW.2b | both | 0.86 [U] :2718; 0.86 [U] :2720 | LPW.2b_LV 0.86 :64; LPW.2b_MV 0.86 :70 |  |
| LPW.3 | both | 2.5 [FUR] :2707 | LPW.3 2.5 :78 |  |
| LPW.5 | KLayout only | – | LPW.5 – :91 |  |
| LPW.11 | both | 1.5 [FUR] :2736 | LPW.11 1.5 :99 |  |
| LPW.12 | KLayout only | – | LPW.12 – :105 |  |
| LRES.1 | both | 0.8 [FUR] :3125 | LRES.1 0.8 :37 |  |
| LRES.2 | both | as PRES/LRES.2 0.4 [FUR] :2860; 0.4 [FUR] :3127 | LRES.2 0.4 :43 |  |
| LRES.3 | both | as PRES/LRES.3 0.6 [FUR] :2865 | LRES.3 – :49 |  |
| LRES.4 | both | as PRES/LRES.4 0.6 [FUR] :2863 | LRES.4 0.6 :55 |  |
| LRES.5 | KLayout only | – | LRES.5 0.3 :63 |  |
| LRES.6 | KLayout only | – | LRES.6 0.28 :71 |  |
| LRES.7 | both | in (LRES.7 - CO.6) 0.215 [FUR] :3130; as PRES/LRES/HRES.7 0.22 [U] :3145; as PRES/LRES/HRES.7 0.22 [U] :3147 | LRES.7 – :80 |  |
| LRES.9a | KLayout only | – | LRES.9a – :95 |  |
| LRES.9b | KLayout only | – | LRES.9b 20 :109 |  |
| LVS_BJT.1 | KLayout only | – | LVS_BJT.1 0 :33 |  |
| M1.1 | both | 0.23 [FUR] :2955 | M1.1 0.23 [idx == 1 / not (idx == 1)] :37,43 | M1_1_w020: Magic FUR, KLayout harness |
| M1.2a | both | 0.23 [FUR] :2956 | M1.2a 0.23 :49 | M1_2a_s020: Magic FUR, KLayout harness |
| M1.2b | both | 0.3 [FU] :2960 | M1.2b 0.3 :60 | M1_2b_wide: Magic FU, KLayout harness |
| M1.3 | both | 0.1444 µm² [FUR] :2957 | M1.3 0.1444 µm² :66 | M1_3_a012: Magic FUR, KLayout harness |
| MC.1 | KLayout only | – | MC.1 0.4 :32 |  |
| MC.2 | KLayout only | – | MC.2 0.4 :38 |  |
| MC.3 | KLayout only | – | MC.3 0.35 µm² :44 |  |
| MC.4 | KLayout only | – | MC.4 0.35 µm² :50 |  |
| MDN.1 | KLayout only | – | MDN.1 1 :48 |  |
| MDN.2a | KLayout only | – | MDN.2a 1 :56 |  |
| MDN.2b | KLayout only | – | MDN.2b 2 :63 |  |
| MDN.3a | KLayout only | – | MDN.3a 0.6 :69 |  |
| MDN.3b | KLayout only | – | MDN.3b 20 :76 |  |
| MDN.4a | KLayout only | – | MDN.4a 4 :84 |  |
| MDN.4b | KLayout only | – | MDN.4b 50 :92 |  |
| MDN.5ai | KLayout only | – | MDN.5ai 1 :104 |  |
| MDN.5aii | KLayout only | – | MDN.5aii 0.92 :120 |  |
| MDN.5b | KLayout only | – | MDN.5b 0.4 :135 |  |
| MDN.5c | KLayout only | – | MDN.5c 15 :148 |  |
| MDN.6 | KLayout only | – | MDN.6 – :158 |  |
| MDN.6a | KLayout only | – | MDN.6a – :164 |  |
| MDN.7 | KLayout only | – | MDN.7 – :173 |  |
| MDN.7a | KLayout only | – | MDN.7a 0 :181 |  |
| MDN.8a | KLayout only | – | MDN.8a – :189 |  |
| MDN.8b | KLayout only | – | MDN.8b – :196 |  |
| MDN.9 | KLayout only | – | MDN.9 4 :202 |  |
| MDN.10a | KLayout only | – | MDN.10a 1.2 :213 |  |
| MDN.10b | KLayout only | – | MDN.10b 0.4 :221 |  |
| MDN.10c | KLayout only | – | MDN.10c 0.2 :232 |  |
| MDN.10d | KLayout only | – | MDN.10d – :247 |  |
| MDN.10ei | KLayout only | – | MDN.10ei – :261 |  |
| MDN.10eii | KLayout only | – | MDN.10eii 0.32 :269 |  |
| MDN.10f | KLayout only | – | MDN.10f – :278 |  |
| MDN.11 | KLayout only | – | MDN.11 – :294 |  |
| MDN.12 | KLayout only | – | MDN.12 – :311 |  |
| MDN.13a | KLayout only | – | MDN.13a 50 :324 |  |
| MDN.13b | KLayout only | – | MDN.13b – :335 |  |
| MDN.13c | KLayout only | – | MDN.13c – :348 |  |
| MDN.13d | KLayout only | – | MDN.13d – :363 |  |
| MDN.14 | KLayout only | – | MDN.14 – :377 |  |
| MDN.15a | KLayout only | – | MDN.15a 0.22 :383 |  |
| MDN.15b | KLayout only | – | MDN.15b 0 :389 |  |
| MDN.17 | KLayout only | – | MDN.17 – :404 |  |
| MDP.1 | KLayout only | – | MDP.1 0.6 :40 |  |
| MDP.1a | KLayout only | – | MDP.1a – :46 |  |
| MDP.2 | KLayout only | – | MDP.2 4 :52 |  |
| MDP.3 | KLayout only | – | MDP.3 – :61 |  |
| MDP.3ai | KLayout only | – | MDP.3ai – :72 |  |
| MDP.3aii | KLayout only | – | MDP.3aii – :85 |  |
| MDP.3b | KLayout only | – | MDP.3b 0.4 :101 |  |
| MDP.3c | KLayout only | – | MDP.3c 15 :115 |  |
| MDP.3d | KLayout only | – | MDP.3d 10 :125 |  |
| MDP.4 | KLayout only | – | MDP.4 – :140 |  |
| MDP.4a | KLayout only | – | MDP.4a 2.5 :150 |  |
| MDP.4b | KLayout only | – | MDP.4b 15 :160 |  |
| MDP.5 | KLayout only | – | MDP.5 – :170 |  |
| MDP.5a | KLayout only | – | MDP.5a 0.5 :179 |  |
| MDP.6 | KLayout only | – | MDP.6 – :188 |  |
| MDP.6a | KLayout only | – | MDP.6a – :194 |  |
| MDP.7 | KLayout only | – | MDP.7 2 :200 |  |
| MDP.8 | KLayout only | – | MDP.8 1.5 :206 |  |
| MDP.9a | KLayout only | – | MDP.9a 1.2 :212 |  |
| MDP.9b | KLayout only | – | MDP.9b 0.4 :221 |  |
| MDP.9c | KLayout only | – | MDP.9c – :233 |  |
| MDP.9d | KLayout only | – | MDP.9d – :245 |  |
| MDP.9ei | KLayout only | – | MDP.9ei – :261 |  |
| MDP.9eii | KLayout only | – | MDP.9eii 0.32 :276 |  |
| MDP.9f | KLayout only | – | MDP.9f – :288 |  |
| MDP.10 | KLayout only | – | MDP.10 0.4 :299 |  |
| MDP.10a | KLayout only | – | MDP.10a 2 :310 |  |
| MDP.10b | KLayout only | – | MDP.10b 1 :316 |  |
| MDP.11 | KLayout only | – | MDP.11 – :325 |  |
| MDP.12 | KLayout only | – | MDP.12 0.66 :336 |  |
| MDP.13a | KLayout only | – | MDP.13a 50 :348 |  |
| MDP.13b | KLayout only | – | MDP.13b – :356 |  |
| MDP.13c | KLayout only | – | MDP.13c – :368 |  |
| MDP.15 | KLayout only | – | MDP.15 6 :380 |  |
| MDP.16a | KLayout only | – | MDP.16a 0.22 :386 |  |
| MDP.16b | KLayout only | – | MDP.16b 0 :392 |  |
| MDP.17a | KLayout only | – | MDP.17a 40 :403 |  |
| MDP.17c | KLayout only | – | MDP.17c – :413 |  |
| MSLOT1.0 | KLayout only | – | MSLOT1.0 – :60 |  |
| MSLOT1.1 | KLayout only | – | MSLOT1.1 30 :67 |  |
| MSLOT1.2 | KLayout only | – | MSLOT1.2 2 :75 |  |
| MSLOT1.3 | KLayout only | – | MSLOT1.3 250 :81 |  |
| MSLOT1.4 | KLayout only | – | MSLOT1.4 10 :87 |  |
| MSLOT1.5 | KLayout only | – | MSLOT1.5 10 :93 |  |
| MSLOT1.7 | KLayout only | – | MSLOT1.7 0.2 :99 |  |
| MSLOT1.8 | KLayout only | – | MSLOT1.8 0.2 :105 |  |
| MSLOT1.9 | KLayout only | – | MSLOT1.9 5 :111 |  |
| N-Ohmic overhang of Varactor < %d (FIXME) | Magic only | 0.32 [FUR] :3161; 0.32 [FUR] :3164 | – |  |
| NAT.1 | KLayout only | – | NAT.1 2 :38 |  |
| NAT.2 | KLayout only | – | NAT.2 0.3 :44 |  |
| NAT.3 | KLayout only | – | NAT.3 0.5 :50 |  |
| NAT.4 | both, values differ: Magic 0.4, KLayout 1.8 | as DF.2c 0.4 [FUR] :3086 | NAT.4 1.8 :57 |  |
| NAT.5 | both, values differ: Magic 1.2, KLayout 1.8 | in (NAT.5 + NAT.6) 0.61 [FUR] :2821; as NAT.4 1.2 [FUR] :3088 | NAT.5 1.8 :66 |  |
| NAT.6 | both | in (NAT.5 + NAT.6) 0.61 [FUR] :2821; 0.35 [FUR] :2852 | NAT.6 – :77 |  |
| NAT.7 | KLayout only | – | NAT.7 0.74 :85 |  |
| NAT.8 | KLayout only | – | NAT.8 0 :91 |  |
| NAT.9 | KLayout only | – | NAT.9 0.3 :100 |  |
| NAT.10 | KLayout only | – | NAT.10 – :109 |  |
| NAT.11 | KLayout only | – | NAT.11 – :115 |  |
| NAT.12 | KLayout only | – | NAT.12 – :122 |  |
| NDRES.2 | Magic only | 0.4 [FUR] :2868 | – |  |
| NDRES.3 | Magic only | 0.44 [FUR] :2871 | – |  |
| NDRES.4 | Magic only | 0.43 [FUR] :2873 | – |  |
| NP.1 | KLayout only | – | NP.1 0.4 :44 |  |
| NP.2 | KLayout only | – | NP.2 0.4 :50 |  |
| NP.3a | KLayout only | – | NP.3a 0.16 :59 |  |
| NP.3bi | KLayout only | – | NP.3bi 0.16 :69 |  |
| NP.3bii | KLayout only | – | NP.3bii 0.08 :79 |  |
| NP.3ci | KLayout only | – | NP.3ci 0.16 :89 | NP3_s006: Magic no, KLayout harness |
| NP.3cii | KLayout only | – | NP.3cii 0.08 :99 |  |
| NP.3d | KLayout only | – | NP.3d 0 :107 |  |
| NP.3e | KLayout only | – | NP.3e 0 :113 |  |
| NP.4a | KLayout only | – | NP.4a 0.32 :119 |  |
| NP.4b | both | in (NP.4b + PP.4c) 0.32 [FUR] :3114 | NP.4b 0.32 :127 |  |
| NP.4c | Magic only: only inside a composite rule | in (PP.4b + NP.4c) 0.32 [FUR] :3117 | – |  |
| NP.5a | KLayout only | – | NP.5a 0.23 :137 | NP5a_ov010: Magic no, KLayout harness; NP_flush: Magic no, KLayout harness |
| NP.5b | KLayout only | – | NP.5b 0.16 :148 | NP5a_ov010: Magic no, KLayout harness; NP_flush: Magic no, KLayout harness |
| NP.5ci | KLayout only | – | NP.5ci 0.16 :160 |  |
| NP.5cii | KLayout only | – | NP.5cii 0.02 :172 |  |
| NP.5di | KLayout only | – | NP.5di 0.16 :186 |  |
| NP.5dii | KLayout only | – | NP.5dii 0.02 :199 |  |
| NP.6 | KLayout only | – | NP.6 0.22 :210 |  |
| NP.7 | KLayout only | – | NP.7 0.18 :216 |  |
| NP.8a | measured on other shapes: Magic checks the NPLUS it generates (tech:1407-1420), KLayout the drawn NPLUS (GAPS-gf180mcuD 1) | 0.35 µm² [U] :2812 | NP.8a 0.35 µm² :222 |  |
| NP.8b | KLayout only | – | NP.8b 0.35 µm² :228 |  |
| NP.9 | KLayout only | – | NP.9 0.18 :236 |  |
| NP.10 | KLayout only | – | NP.10 0.18 :244 |  |
| NP.11 | KLayout only | – | NP.11 0.43 :255 |  |
| NP.12 | KLayout only | – | NP.12 0.32 :271 |  |
| NW.1a | both | 0.86 [FU] :2690 | NW.1a_LV 0.86 :37; NW.1a_MV 0.86 :44 | NW1a_w080: Magic FU, KLayout harness |
| NW.1b | both | 2 [FU] :2694 | NW.1b_LV 2 :53; NW.1b_MV 2 :61 |  |
| NW.2a | both | 0.6 [FU] :2691; 0.74 [U] :2697 | NW.2a_LV 0.6 :72; NW.2a_MV 0.74 :81 | NW2a_s050: Magic FU, KLayout harness |
| NW.2b | both | 1.4 [FU] :2693 | NW.2b_LV 1.4 :89; NW.2b_MV 1.7 :96 |  |
| NW.3 | both | 3.1 [FUR] :2733 | NW.3 3.1 :102 |  |
| NW.4 | KLayout only | – | NW.4 0 :108 |  |
| NW.5 | both | 0.5 [FUR] :2710 | NW.5_LV 0.5 :116; NW.5_MV 0.5 :127 |  |
| NW.6 | both | as DN.12 – [U] :2729 | NW.6 – :136 |  |
| O.CO.7 | KLayout only | – | O.CO.7 0.13 :145 |  |
| O.DF.3a | KLayout only | – | O.DF.3a 0.24 :40 |  |
| O.DF.6 | KLayout only | – | O.DF.6 0.22 :47 |  |
| O.DF.9 | KLayout only | – | O.DF.9 0.1444 µm² :53 |  |
| O.PL.2 | KLayout only | – | O.PL.2 0.22 :59 |  |
| O.PL.3a | KLayout only | – | O.PL.3a 0.18 :65 |  |
| O.PL.4 | KLayout only | – | O.PL.4 0.14 :71 |  |
| O.PL.ORT | KLayout only | – | O.PL.ORT – :153 |  |
| O.SB.2 | KLayout only | – | O.SB.2 0.28 :83 |  |
| O.SB.3 | KLayout only | – | O.SB.3 0.09 :89 |  |
| O.SB.4 | KLayout only | – | O.SB.4 – :95 |  |
| O.SB.5b | KLayout only | – | O.SB.5b_LV 0.1 :105 |  |
| O.SB.9 | KLayout only | – | O.SB.9 0.1 :115 |  |
| O.SB.11 | KLayout only | – | O.SB.11 0.04 :121 |  |
| O.SB.13 | KLayout only | – | O.SB.13_LV 1.488 µm² :130; O.SB.13_MV 2 µm² :136 |  |
| P-diffusion and N-ohmic must be over N-well or deep N-well | Magic only | – [U] :2799 | – |  |
| P-Ohmic overhang of Varactor < %d (FIXME) | Magic only | 0.32 [FUR] :3170; 0.32 [FUR] :3173 | – |  |
| PL.1 | both | 0.18 [FUR] :2828 | PL.1_LV 0.18 :39; PL.1_MV 0.2 :45 | PL1_mv_w019: Magic no, KLayout harness; PL1_w016: Magic FUR, KLayout harness |
| PL.1a | KLayout only | – | PL.1a_LV 0.18 :51; PL.1a_MV 0.18 :57 |  |
| PL.2 | both | 0.28 [FUR] :3091; 0.28 [FUR] :3092; 0.28 [FUR] :3093; 0.28 [FUR] :3094; 0.5 [FUR] :3098; 0.6 [FUR] :3099; 4 more | PL.2_LV 0.28 :65; PL.2_MV – :77 | PL2_lv_L025: Magic FUR, KLayout harness; PL2_mv_L060: Magic FUR, KLayout harness |
| PL.3a | both | 0.24 [FUR] :2830 | PL.3a 0.24 :87 | PL3a_s020: Magic FUR, KLayout harness |
| PL.4 | both | 0.22 [FUR] :2851 | PL.4_LV 0.22 :100; PL.4_MV 0.22 :106 | PL4_e015: Magic FUR, KLayout harness |
| PL.5a | both | 0.1 [FUR] :2835; 0.3 [FUR] :2838 | PL.5a_LV 0.1 :112; PL.5a_MV 0.3 :119 | PL5a_s008: Magic FUR, KLayout harness |
| PL.5b | KLayout only | – | PL.5b_LV 0.1 :126; PL.5b_MV 0.3 :132 |  |
| PL.6 | both | – [FUR] :2854 | PL.6 90 :142 |  |
| PL.7 | both | 0.3 [FUR] :3095; 0.3 [FUR] :3096; 0.7 [FUR] :3105; 0.7 [FUR] :3106 | PL.7_LV 0.3 :151; PL.7_MV 0.7 :163 |  |
| PL.9 | KLayout only | – | PL.9 – :173 | DG_partial: Magic no, KLayout harness |
| PL.11 | KLayout only | – | PL.11 – :184 |  |
| PL.12 | KLayout only | – | PL.12 – :194 |  |
| PP.1 | KLayout only | – | PP.1 0.4 :44 | PP1_w034: Magic no, KLayout harness |
| PP.2 | KLayout only | – | PP.2 0.4 :50 | PP2_s028: Magic no, KLayout harness |
| PP.3a | KLayout only | – | PP.3a 0.16 :58 |  |
| PP.3bi | KLayout only | – | PP.3bi 0.08 :67 |  |
| PP.3bii | KLayout only | – | PP.3bii 0.16 :77 |  |
| PP.3ci | KLayout only | – | PP.3ci 0.08 :87 |  |
| PP.3cii | KLayout only | – | PP.3cii 0.16 :97 |  |
| PP.3d | KLayout only | – | PP.3d 0 :105 |  |
| PP.3e | KLayout only | – | PP.3e 0 :111 |  |
| PP.4a | KLayout only | – | PP.4a 0.32 :117 |  |
| PP.4b | both | in (PP.4b + NP.4c) 0.32 [FUR] :3117 | PP.4b 0.32 :125 |  |
| PP.4c | Magic only: only inside a composite rule | in (NP.4b + PP.4c) 0.32 [FUR] :3114 | – |  |
| PP.5a | KLayout only | – | PP.5a 0.23 :135 |  |
| PP.5b | KLayout only | – | PP.5b 0.16 :146 |  |
| PP.5ci | KLayout only | – | PP.5ci 0.02 :158 |  |
| PP.5cii | KLayout only | – | PP.5cii 0.16 :171 |  |
| PP.5di | KLayout only | – | PP.5di 0.02 :186 |  |
| PP.5dii | KLayout only | – | PP.5dii 0.16 :196 |  |
| PP.6 | KLayout only | – | PP.6 0.22 :208 |  |
| PP.7 | KLayout only | – | PP.7 0.18 :214 |  |
| PP.8a | measured on other shapes: Magic checks the PPLUS it generates (tech:1407-1420), KLayout the drawn PPLUS (GAPS-gf180mcuD 1) | 0.35 µm² [U] :2811 | PP.8a 0.35 µm² :220 | PP1_w034: Magic U, KLayout harness |
| PP.8b | KLayout only | – | PP.8b 0.35 µm² :226 |  |
| PP.9 | KLayout only | – | PP.9 0.18 :234 |  |
| PP.10 | KLayout only | – | PP.10 0.18 :242 |  |
| PP.11 | KLayout only | – | PP.11 0.43 :253 |  |
| PP.12 | KLayout only | – | PP.12 0.32 :268 |  |
| PRES.1 | both | 0.8 [FUR] :3124 | PRES.1 0.8 :35 |  |
| PRES.2 | both | as PRES/LRES.2 0.4 [FUR] :2860; 0.4 [FUR] :3126 | PRES.2 0.4 :41 |  |
| PRES.3 | both | as PRES/LRES.3 0.6 [FUR] :2865 | PRES.3 – :49 |  |
| PRES.4 | both | as PRES/LRES.4 0.6 [FUR] :2863 | PRES.4 0.6 :57 |  |
| PRES.5 | KLayout only | – | PRES.5 0.3 :65 |  |
| PRES.6 | KLayout only | – | PRES.6 0.28 :73 |  |
| PRES.7 | both | in (PRES.7 - CO.6) 0.215 [FUR] :3129; as PRES/LRES/HRES.7 0.22 [U] :3145; as PRES/LRES/HRES.7 0.22 [U] :3147 | PRES.7 – :81 |  |
| PRES.9a | KLayout only | – | PRES.9a – :94 |  |
| PRES.9b | KLayout only | – | PRES.9b 20 :107 |  |
| S.CO.3 | KLayout only | – | S.CO.3_LV 0.04 :65 |  |
| S.CO.4 | both, values differ: Magic grows each contact by 0.005 µm per side when it reads it (GAPS-gf180mcuD 1), so its two SRAM checks of COMP overlap of contact, 0.035 µm (tech:2923-2930), are 0.04 µm from the cut: equal to KLayout's S.CO.4_MV, and 0.01 µm more than its S.CO.4_LV 0.03 µm for the 3.3 V SRAM, which Magic prints as S.CO.3_LV | as S.CO.4_MV 0.035 [FUR] :2923; as S.CO.4_MV 0.035 [FUR] :2925; as S.CO.3_LV 0.035 [FUR] :2927; as S.CO.3_LV 0.035 [FUR] :2929 | S.CO.4_LV 0.03 :76; S.CO.4_MV 0.04 :105 |  |
| S.CO.6_ii | KLayout only | – | S.CO.6_ii_LV 0.04 :92 |  |
| S.DF.4c | both | as S.DF.7_MV 0.45 [FUR] :2783; as S.DF.4c_LV 0.4 [FUR] :2785 | S.DF.4c_LV 0.4 :44; S.DF.4c_MV 0.45 :45 |  |
| S.DF.6 | KLayout only | – | S.DF.6_MV 0.32 :54 |  |
| S.DF.7 | KLayout only | – | S.DF.7_MV 0.45 :61 |  |
| S.DF.8 | KLayout only | – | S.DF.8_MV 0.45 :69 |  |
| S.DF.16 | both | as S.DF.8_MV 0.45 [FUR] :2765; as S.DF.16_LV 0.4 [FUR] :2767 | S.DF.16_LV 0.4 :54; S.DF.16_MV 0.45 :79 |  |
| S.M1.1 | KLayout only | – | S.M1.1_LV 0.22 :106 |  |
| S.PL.5a | both | as S.PL.5a_MV 0.12 [FUR] :2841 | S.PL.5a_MV 0.12 :89 |  |
| S.PL.5b | KLayout only | – | S.PL.5b_MV 0.12 :96 |  |
| SB.1 | KLayout only | – | SB.1 0.42 :39 |  |
| SB.2 | KLayout only | – | SB.2 0.42 :45 |  |
| SB.3 | KLayout only | – | SB.3 0.22 :52 |  |
| SB.4 | KLayout only | – | SB.4 0.15 :59 |  |
| SB.5a | KLayout only | – | SB.5a 0.3 :66 |  |
| SB.5b | KLayout only | – | SB.5b 0.28 :73 |  |
| SB.6 | KLayout only | – | SB.6 0.22 :79 |  |
| SB.7 | KLayout only | – | SB.7 0.22 :85 |  |
| SB.8 | KLayout only | – | SB.8 – :91 |  |
| SB.9 | KLayout only | – | SB.9 0.22 :97 |  |
| SB.10 | KLayout only | – | SB.10 0.22 :103 |  |
| SB.11 | KLayout only | – | SB.11 0.22 :109 |  |
| SB.12 | KLayout only | – | SB.12 0.22 :116 |  |
| SB.13 | KLayout only | – | SB.13 2 µm² :123 |  |
| SB.14a | KLayout only | – | SB.14a 0.56 :133 |  |
| SB.14b | KLayout only | – | SB.14b 0.56 :144 |  |
| SB.15a | KLayout only | – | SB.15a 0.18 :153 |  |
| SB.15b | KLayout only | – | SB.15b 0.32 :163 |  |
| SB.16 | KLayout only | – | SB.16 – :174 |  |
| V1.1 | both | 0.26 [FUR] :2969 | V1.1 0.26 :27 | V1_1_b032: Magic no, KLayout harness; V1_1_s024: Magic FUR, KLayout harness |
| V1.2a | in the deck, did not fire on its case: Magic reported nothing on V1_2a_s022 | 0.26 [FUR] :2970 | V1.2a 0.26 :35 | V1_2a_s022: Magic no, KLayout harness |
| V1.2b | KLayout only | – | V1.2b 0.36 :49 | V1_2b_4x4_s026: Magic no, KLayout no; V1_2b_4x4_s030: Magic no, KLayout harness |
| V1.3 | both | 0.06 [FUR] :2971 | V1.3a 0 :73; V1.3c 0.06 :104; V1.3d 0.06 :127 | V1_3_m1ov0: Magic FUR, KLayout harness; V1_3_m1ov002: Magic FUR, KLayout harness |
| V1.4 | both | 0.01 [FUR] :2973 | V1.4a 0.01 :148; V1.4b 0.06 :165 | V1_4_m2ov0: Magic FUR, KLayout harness |
| V1.4c | both | as V1.4i 0.06 [FUR] :2975 | V1.4c 0.06 :186 |  |
| Y.DF.6 | KLayout only | – | Y.DF.6_MV 0.15 :64 |  |
| Y.DF.16 | KLayout only | – | Y.DF.16_LV 0.27 :72; Y.DF.16_MV 0.23 :81 |  |
| Y.NW.2b | KLayout only | – | Y.NW.2b_LV 1 :42; Y.NW.2b_MV 1 :50 |  |
| Y.PL.1 | KLayout only | – | Y.PL.1_LV 0.13 :89; Y.PL.1_MV – :96 |  |
| Y.PL.2 | KLayout only | – | Y.PL.2_LV 0.13 :103; Y.PL.2_MV 0.47 :109 |  |
| Y.PL.4 | KLayout only | – | Y.PL.4_MV 0.16 :115 |  |
| Y.PL.5a | KLayout only | – | Y.PL.5a_LV 0.04 :123; Y.PL.5a_MV 0.2 :131 |  |
| Y.PL.5b | KLayout only | – | Y.PL.5b_LV 0.04 :138; Y.PL.5b_MV 0.2 :146 |  |

## Rules only one side reported in a test

Each line gives a rule and the cases, controls left out, on which one engine reported it and the other did not. Magic's side is any of its styles; KLayout's side is `gf180mcu.drc`.

### Reported by Magic and not by gf180mcu.drc

- `CO.1`: BUTT_straddle
- `CO.4`: BUTT_straddle, CO10_cont_on_gate, NPPP_both, NWmiss_pfet
- `CO.6`: BUTT_straddle, CO10_cont_on_gate, CO1_small020, CO7_c2g012, CO8_pc2c014
- `CO.7`: CO10_cont_on_gate
- `DF.1a`: NP_missing, NWmiss_pfet
- `DF.1c`: NPPP_both, NWmiss_pfet
- `DF.3a`: NPPP_both, NWmiss_pfet
- `DF.4c`: NP_missing, NWmiss_pfet
- `DF.6`: NP_missing
- `DF.9`: NPPP_both, NP_missing, NWmiss_pfet
- `P-diffusion and N-ohmic must be over N-well or deep N-well`: NWmiss_pfet
- `P-Ohmic overhang of Varactor < %d (FIXME)`: NPPP_both, NWmiss_pfet
- `PL.1`: CO10_cont_on_gate
- `PL.2`: CO10_cont_on_gate
- `PL.4`: NPPP_both, NP_missing, NWmiss_pfet
- `PP.8a`: DF9_a018, NPPP_both

### Reported by KLayout and not by Magic

- `CO.1`: CO1_big030
- `CO.2a`: CO2a_s022, CO2b_4x4_s010
- `CO.2b`: CO2b_4x4_s026
- `CO.9`: BUTT_straddle
- `CO.10`: CO10_cont_on_gate
- `CO.11`: CO11_cont_field
- `DF.3b`: NPPP_both
- `DF.6`: DF6_lv_0235, DF6_mv_030
- `DF.12`: DF12_noimp, NP_missing
- `DF.13`: DF13_nwnotap
- `DF.14`: DF14_notap, DF14_tap25
- `DV.6`: DG_partial, DG_small
- `DV.7`: DG_partial
- `DV.8`: DG_partial, DG_small
- `NP.3ci`: NP3_s006
- `NP.3d`: NPPP_both
- `NP.3e`: NPPP_both
- `NP.5a`: NP5a_ov010, NP_flush
- `NP.5b`: NP5a_ov010, NP_flush
- `OFFGRID (per layer)`: GRID_m1_2p5nm
- `PL.1`: PL1_mv_w019
- `PL.5b`: CO8_pc2c014, PL5a_s008
- `PL.9`: DG_partial
- `PP.1`: PP1_w034
- `PP.2`: NPPP_both, PP2_s028
- `PP.3d`: NPPP_both
- `PP.3e`: NPPP_both
- `PP.5di`: PP5_ov0
- `PP.12`: NPPP_both
- `V1.1`: V1_1_b032
- `V1.2a`: V1_2a_s022
- `V1.2b`: V1_2b_4x4_s030
