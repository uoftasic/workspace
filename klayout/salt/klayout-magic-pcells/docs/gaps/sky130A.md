# Gap table: sky130A

This table compares Magic's DRC rules for sky130A with the PDK's KLayout DRC decks, one row per rule, and shows where they disagree. `tools/build_gaps.py` generates it; do not edit it by hand.

- **What a row is.** One rule, under the rule ID that Magic's why-text gives it (the why-text is the message Magic's DRC gives an error box, and the ID is the text in its last parentheses), under a name from `tests/gaps/aliases-sky130A.json` where the two tools name the rule differently, under the KLayout name where Magic has no such rule, or under Magic's whole message where the message has no ID. The row gives the statements of Magic's tech file that check the rule, each KLayout deck's outputs for it (the report categories the deck writes), and what both engines reported on the test cases that target it.
- **How it is made.** Magic's rules come from `python/klayout_magic_pcells/data/pdk-sky130A.json`. Each KLayout run below checked a layout of one box. Its report has a category for every rule the deck ran under its switches, and those categories are the deck's side of the table; a text scan of the deck gives each output's line and the switches it sits under. The two sides are joined on rule ID, with the mappings made by hand in `tests/gaps/aliases-sky130A.json`. The test cases are the `gaps` set of the case suite (`tests/cases`): a clean control layout, and cases that each change one thing in it. Magic checked each case cell alone in all three styles, at most 15 cells per process; KLayout checked them on one sheet, 40 µm apart. A case's results are the rules reported on it and not on its control.
- **Image.** The pinned Docker image `hpretl/iic-osic-tools@sha256:3c371645b19c6f6564dc8c7b21e39ad1c1833d274fe5b85639afe1ba9d7987e7`, with Magic 8.3.681 and KLayout 0.30.11; open_pdks 026824c7 (Magic tech 1.0.588-56-g026824c).
- **Rebuild.** `scripts/gaps.sh --pdk sky130A` rewrites this page; `scripts/gaps.sh --pdk sky130A --check` fails if it would change.

Each row has one status. The status and the value comparison take `sky130A_mr.drc` as the KLayout side; the other decks have their own columns.

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

| Part | both | both, values differ | folded | same name for another check | in the deck, did not fire on its case | Magic only | KLayout only | total |
|---|---|---|---|---|---|---|---|---|
| via2 and up, MiM caps, rdl | 43 | 1 | 4 | 0 | 0 | 7 | 29 | 84 |
| Front end, li, mcon, met1, via1 | 33 | 0 | 1 | 3 | 7 | 86 | 176 | 306 |
| all | 76 | 1 | 5 | 3 | 7 | 93 | 205 | 390 |

## KLayout runs

Each run checked a layout of one box; the last column counts the categories in its report. "The harness" is the plugin's parity harness (`tests/parity`).

| Run | What | Categories on one box |
|---|---|---|
| harness | sky130A_mr.drc with the harness's switches (beol=true, feol=true, floating_met=false, offgrid=true, seal=false, thr=1) | 244 |
| menu | sky130A_mr.drc with the switches of Efabless sky130 > Run DRC (Full) (beol=true, feol=true, offgrid=true) | 256 |
| lydrc | sky130A.lydrc as shipped (FEOL = false) | 145 |
| lydrc_feol | sky130A.lydrc with FEOL = true | 381 |

Cases: 132 in the `gaps` set.

## Rules

### via2 and up, MiM caps, rdl

| Rule | Status | Magic: value [styles] :line | sky130A_mr.drc: name value [switch] :line | sky130A.lydrc: name value [switch] :line | Tested (case: what each engine reported) |
|---|---|---|---|---|---|
| cap2m.1 | both | 1 [FU] :4914 | cap2m.1 1 [FEOL] :845 | – |  |
| cap2m.2a | both | 0.84 [FU] :4915 | cap2m.2a 0.84 [FEOL] :849 | – |  |
| cap2m.2b | KLayout only | – | cap2m.2b 1.2 [FEOL] :856; cap2m.2b_a 1.2 [FEOL] :857 | – |  |
| cap2m.3 | both | 0.14 [FU] :4922 | cap2m.3 0.14 [FEOL] :864; cap2m.3_a 0.14 [FEOL] :865 | – |  |
| cap2m.4 | both | in (cap2m.4 - via4.4) 0.01 [FU] :4918 | cap2m.4 0.2 [FEOL] :869 | – |  |
| cap2m.5 | both | in (cap2m.5 - via4.4) 0.01 [FU] :4916 | cap2m.5 0.2 [FEOL] :873 | – |  |
| cap2m.7 | Magic only | – [FU] :4920 | – | – |  |
| cap2m.8 | Magic only | in (cap2m.8 - via3.4) 0.08 [FU] :4924; – [U] :4930 | – | – |  |
| cap2m.11 | both, values differ: Magic 1.34, KLayout 0.5 | 1.34 [FU] :4926 | cap2m.11 0.5 [FEOL] :877 | – |  |
| capm.1 | both | 1 [FU] :4891 | capm.1 1 [FEOL] :802 | capm.1 1 [FEOL; only in lydrc_feol] :419 |  |
| capm.2a | both | 0.84 [FU] :4892 | capm.2a 0.84 [FEOL] :806 | capm.2a 0.84 [FEOL; only in lydrc_feol] :420 |  |
| capm.2b | KLayout only | – | capm.2b 1.2 [FEOL] :815; capm.2b_a 1.2 [FEOL] :820 | capm.2b 1.2 [FEOL; only in lydrc_feol] :421 |  |
| capm.3 | both | 0.14 [FU] :4899 | capm.3 0.14 [FEOL] :825 | capm.3 0.14 [FEOL; only in lydrc_feol] :422 |  |
| capm.4 | both | in (capm.4 - via3.4) 0.08 [FU] :4895 | capm.4 0.14 [FEOL] :829 | capm.4 0.14 [FEOL; only in lydrc_feol] :423 |  |
| capm.5 | both | in (capm.5 - via3.4) 0.08 [FU] :4893 | capm.5 0.14 [FEOL] :833 | capm.5 0.14 [FEOL; only in lydrc_feol] :424 |  |
| capm.6 | KLayout only | – | – | capm.6 20 [FEOL; only in lydrc_feol] :425 |  |
| capm.7 | Magic only: sky130A.lydrc has it | – [FU] :4897 | – | capm.7 – [FEOL; only in lydrc_feol] :426 |  |
| capm.8 | Magic only: sky130A.lydrc has it | in (capm.8 - via2.4) 0.1 [FU] :4901 | – | capm.8 0.14 [FEOL; only in lydrc_feol] :427 |  |
| capm.10 | KLayout only | – | – | capm.10 – [FEOL; only in lydrc_feol] :428,429,430,431… |  |
| capm.11 | both: sky130A_mr.drc's capm.2b_a keeps met3 that does not touch the capm's bottom plate (capm and met3, grown by 0.14 µm) 1.2 µm from it, which is Magic's 1.34 µm from the capm; its capm.11 is a second check at 0.5 µm | 1.34 [FU] :4903 | capm.11 0.5 [FEOL] :837; capm.2b_a 1.2 [FEOL] :820 | capm.11 0.5 [FEOL; only in lydrc_feol] :434 |  |
| met2.1 | both | 0.14 [FUR] :4644 | m2.1 0.14 [BEOL] :1137 | m2.1 0.14 [BEOL] :527 |  |
| met2.2 | both | 0.14 [FUR] :4645 | m2.2 0.14 [BEOL] :1144 | m2.2 0.14 [BEOL] :532 |  |
| met2.3a | both | 0.28 [U] :4660 | m2.3ab 0.28 [BEOL] :1152 | m2.3ab 0.28 [BEOL] :534 |  |
| met2.3b | both | 0.28 [FU] :4651; 0.28 [FU] :4653 | m2.3ab 0.28 [BEOL] :1152 | m2.3ab 0.28 [BEOL] :534 |  |
| met2.4 | folded: Magic checks it only inside a composite rule | in (met2.5 - met2.4) 0.03 [FUR] :4634 | m2.4 0.055 [BEOL & backend_flow = AL] :1166; m2.4_a – [BEOL & backend_flow = AL] :1170; m2.4_b 0.045 [BEOL & backend_flow = AL] :1174 | m2.4 0.055 [BEOL & backend_flow = AL] :541 |  |
| met2.5 | both | in (met2.5 - met2.4) 0.03 [FUR] :4634 | m2.5 0.085 [BEOL & backend_flow = AL] :1183 | m2.5 0.085 [BEOL & backend_flow = AL] :544 |  |
| met2.6 | both | 0.0676 µm² [FUR] :4646 | m2.6 0.0676 µm² [BEOL] :1154 | m2.6 0.0676 µm² [BEOL] :537 |  |
| met2.7 | both | 0.14 µm² [U] :4657 | m2.7 0.14 µm² [BEOL] :1158 | m2.7 0.14 µm² [BEOL] :538 |  |
| met2.via | KLayout only | – | – | m2.via – [BEOL] :539 |  |
| met3.1 | both | 0.3 [FUR] :4682 | m3.1 0.3 [BEOL] :1253 | m3.1 0.3 [BEOL] :575 |  |
| met3.2 | both | 0.3 [FUR] :4683 | m3.2 0.3 [BEOL] :1259 | m3.2 0.3 [BEOL] :580 |  |
| met3.3a | KLayout only | – | – | m3.3ab 0.4 [BEOL] :582 |  |
| met3.3b | KLayout only | – | – | m3.3ab 0.4 [BEOL] :582 |  |
| met3.3c | both | 0.4 [U] :4694 | m3.3cd 0.4 [BEOL] :1267 | – |  |
| met3.3d | both | 0.4 [FU] :4689; 0.4 [FU] :4691 | m3.3cd 0.4 [BEOL] :1267 | – |  |
| met3.4 | both: Magic measures from its via2 contact area, 0.04 µm past the cut (via2.4), so its 0.025 µm is 0.065 µm from the cut | 0.025 [FUR] :4674 | m3.4 0.065 [BEOL & backend_flow = AL] :1275; m3.4_a – [BEOL & backend_flow = AL] :1279 | m3.4 0.065 [BEOL & backend_flow = AL] :588 |  |
| met3.6 | both | 0.24 µm² [FUR] :4684 | m3.6 0.24 µm² [BEOL] :1281 | m3.6 0.24 µm² [BEOL] :585 |  |
| met3.7 | KLayout only | – | m3.7 0.2 µm² [BEOL] :1285 | – |  |
| met3.via2 | KLayout only | – | – | m3.via2 – [BEOL] :586 |  |
| met4.1 | both | 0.3 [FUR] :4718 | m4.1 0.3 [BEOL] :1339 | m4.1 0.3 [BEOL] :623 |  |
| met4.2 | both | 0.3 [FUR] :4719 | m4.2 0.3 [BEOL] :1345 | m4.2 0.3 [BEOL] :628 |  |
| met4.3 | both | in (met4.3 - via3.4) 0.005 [FUR] :4707; in (met4.3 - via3.4) 0.005 [FU] :4910 | m4.3 0.065 [BEOL & backend_flow = AL] :1363; m4.3_a – [BEOL & backend_flow = AL] :1367 | m4.3 0.065 [BEOL & backend_flow = AL] :635 |  |
| met4.4 | KLayout only | – | – | m4.4 0.24 µm² [BEOL] :632 |  |
| met4.4a | both | 0.24 µm² [FUR] :4720 | m4.4a 0.24 µm² [BEOL] :1350 | – |  |
| met4.5a | both | 0.4 [U] :4730 | m4.5ab 0.4 [BEOL] :1355 | m4.5ab 0.4 [BEOL] :630 |  |
| met4.5b | both | 0.4 [FU] :4725; 0.4 [FU] :4727 | m4.5ab 0.4 [BEOL] :1355 | m4.5ab 0.4 [BEOL] :630 |  |
| met4.7 | KLayout only | – | m4.7 0.2 µm² [BEOL] :1372 | – |  |
| met4.via3 | KLayout only | – | – | m4.via3 – [BEOL] :633 |  |
| met5.1 | both | 1.6 [FUR] :4749 | m5.1 1.6 [BEOL] :1427 | m5.1 1.6 [BEOL] :661 |  |
| met5.2 | both | 1.6 [FUR] :4750 | m5.2 1.6 [BEOL] :1429 | m5.2 1.6 [BEOL] :663 |  |
| met5.3 | both | in (met5.3 - via4.4) 0.12 [FUR] :4740; in (met5.3 - via4.4) 0.12 [FU] :4939 | m5.3 0.31 [BEOL] :1431; m5.3_a – [BEOL] :1435 | m5.3 0.31 [BEOL] :666 |  |
| met5.4 | both | 4 µm² [FUR] :4751 | m5.4 4 µm² [BEOL] :1442 | – |  |
| met5.7 | KLayout only | – | m5.7 0.14 µm² [BEOL] :1446 | – |  |
| met5.via4 | KLayout only | – | – | m5.via4 – [BEOL] :665 |  |
| moduleCut.1 | KLayout only | – | moduleCut.1 – [BEOL] :1457 | – |  |
| nsm.1 | KLayout only | – | nsm.1 4 [FEOL] :796 | nsm.1 3 [BEOL] :669 |  |
| nsm.2 | KLayout only | – | nsm.2 3 [FEOL] :797 | nsm.2 4 [BEOL] :670 |  |
| nsm.3 | KLayout only | – | – | nsm.3 1 [BEOL & backend_flow = AL] :682,683,684,685… |  |
| nsm.4 | KLayout only | – | – | nsm.4 3 [BEOL] :671,672,673,674… |  |
| pad.2 | KLayout only | – | pad.2 1.27 [BEOL] :1451 | pad.2 1.27 [BEOL] :695 |  |
| rdl.1 | both | 10 [U] :4759 | rdl.1 10 [FEOL] :529 | – |  |
| rdl.2 | both | 10 [U] :4760 | rdl.2 10 [FEOL] :530 | – |  |
| rdl.3 | Magic only | 10.75 [U] :4761 | – | – |  |
| rdl.6 | Magic only | 19.66 [U] :4762 | – | – |  |
| via2 | KLayout only | – | – | via2 – [BEOL] :555 |  |
| via2.1a | both | in (via2.1a + 2 * via2.4) 0.28 [FUR] :4668 | via2.1a – [BEOL & backend_flow = AL] :1201; via2.1a_a 0.2 [BEOL & backend_flow = AL] :1205; via2.1a_b 0.2 [BEOL & backend_flow = AL] :1212 | via2.1a 0.2 [BEOL & backend_flow = AL] :557 |  |
| via2.1b | KLayout only | – | – | via2.1b 1.5 [BEOL & backend_flow = AL] :558 |  |
| via2.2 | both | in (via2.2 - 2 * via2.4) 0.12 [FUR] :4670 | via2.2 0.2 [BEOL & backend_flow = AL] :1213 | via2.2 0.2 [BEOL & backend_flow = AL] :559 |  |
| via2.3 | KLayout only | – | via2.3 0.2 [BEOL & backend_flow = AL & SEAL; only in menu] :1219; via2.3_a 0.205 [BEOL & backend_flow = AL & SEAL; only in menu] :1223; via2.3_b – [BEOL & backend_flow = AL & SEAL; only in menu] :1227 | – |  |
| via2.4 | folded: Magic checks it only inside a composite rule | in (via2.1a + 2 * via2.4) 0.28 [FUR] :4668; in (via2.2 - 2 * via2.4) 0.12 [FUR] :4670; in (via2.4a - via2.4) 0.045 [FUR] :4672; in (capm.8 - via2.4) 0.1 [FU] :4901 | via2.4 0.04 [BEOL & backend_flow = AL] :1233; via2.4_a – [BEOL & backend_flow = AL] :1237 | via2.4 0.04 [BEOL & backend_flow = AL] :560 |  |
| via2.4a | Magic only: sky130A.lydrc has it | in (via2.4a - via2.4) 0.045 [FUR] :4672 | – | via2.4a 0.14 [BEOL & backend_flow = AL] :561 |  |
| via2.5 | KLayout only | – | via2.5 0.085 [BEOL & backend_flow = AL] :1244 | via2.5 0.085 [BEOL & backend_flow = AL] :564 |  |
| via3 | KLayout only | – | – | via3 – [BEOL] :604 |  |
| via3.1 | both | in (via3.1 + 2 * via3.4) 0.32 [FUR] :4703; in (via3.1 + 2 * via3.4) 0.32 [FU] :4908 | via3.1 – [BEOL & backend_flow = AL] :1299; via3.1_a 0.2 [BEOL & backend_flow = AL] :1303; via3.1_b 0.2 [BEOL & backend_flow = AL] :1310 | – |  |
| via3.1a | KLayout only | – | – | via3.1a 0.8 [BEOL & backend_flow = AL] :606,607 |  |
| via3.2 | both | in (via3.2 - 2 * via3.4) 0.08 [FUR] :4704; in (via3.2 - 2 * via3.4) 0.08 [FU] :4909 | via3.2 0.2 [BEOL & backend_flow = AL] :1312 | via3.2 0.2 [BEOL & backend_flow = AL] :608 |  |
| via3.4 | folded: Magic checks it only inside a composite rule | in (via3.1 + 2 * via3.4) 0.32 [FUR] :4703; in (via3.2 - 2 * via3.4) 0.08 [FUR] :4704; in (via3.5 - via3.4) 0.03 [FUR] :4705; in (met4.3 - via3.4) 0.005 [FUR] :4707; in (capm.5 - via3.4) 0.08 [FU] :4893; in (capm.4 - via3.4) 0.08 [FU] :4895; 4 more | via3.4 0.06 [BEOL & backend_flow = AL] :1316; via3.4_a – [BEOL & backend_flow = AL] :1320 | via3.4 0.06 [BEOL & backend_flow = AL] :609 |  |
| via3.5 | both | in (via3.5 - via3.4) 0.03 [FUR] :4705 | via3.5 0.09 [BEOL & backend_flow = AL] :1330 | via3.5 0.09 [BEOL & backend_flow = AL] :612 |  |
| via4 | KLayout only | – | – | via4 – [BEOL] :655 |  |
| via4.1 | both | in (via4.1 + 2 * via4.4) 1.18 [FUR] :4738; in (via4.1 + 2 * via4.4) 1.18 [FU] :4936 | via4.1 – [BEOL] :1385; via4.1_a 0.8 [BEOL] :1389; via4.1_b 0.8 [BEOL] :1393 | – |  |
| via4.1a | KLayout only | – | – | via4.1a 0.8 [BEOL] :651 |  |
| via4.2 | both | in (via4.2 - 2 * via4.4) 0.42 [FUR] :4739; in (via4.2 - 2 * via4.4) 0.42 [FU] :4937 | via4.2 0.8 [BEOL] :1401 | via4.2 0.8 [BEOL] :652 |  |
| via4.3 | KLayout only | – | via4.3 0.8 [BEOL & SEAL; only in menu] :1404; via4.3_a 0.805 [BEOL & SEAL; only in menu] :1408; via4.3_b – [BEOL & SEAL; only in menu] :1412 | – |  |
| via4.4 | folded: Magic checks it only inside a composite rule | in (via4.1 + 2 * via4.4) 1.18 [FUR] :4738; in (via4.2 - 2 * via4.4) 0.42 [FUR] :4739; in (met5.3 - via4.4) 0.12 [FUR] :4740; in (cap2m.5 - via4.4) 0.01 [FU] :4916; in (cap2m.4 - via4.4) 0.01 [FU] :4918; in (via4.1 + 2 * via4.4) 1.18 [FU] :4936; 2 more | via4.4 0.19 [BEOL] :1418; via4.4_a – [BEOL] :1422 | via4.4 0.19 [BEOL] :654 |  |

### Front end, li, mcon, met1, via1

| Rule | Status | Magic: value [styles] :line | sky130A_mr.drc: name value [switch] :line | sky130A.lydrc: name value [switch] :line | Tested (case: what each engine reported) |
|---|---|---|---|---|---|
| ct.3 | KLayout only | – | ct.3 0.17 [BEOL & SEAL; only in menu] :962 | – |  |
| ct.3_a | KLayout only | – | ct.3_a 0.175 [BEOL & SEAL; only in menu] :966 | – |  |
| ct.3_b | KLayout only | – | ct.3_b – [BEOL & SEAL; only in menu] :970 | – |  |
| ct.4 | KLayout only | – | ct.4 – [BEOL] :975 | ct.4 – [BEOL] :463 | s_mcon_no_li: Magic no, KLayout harness,lydrc,lydrc_feol,menu |
| denmos.1 | Magic only: sky130A.lydrc has it | 1.055 [FU] :4304 | – | denmos.1 1.055 [FEOL; only in lydrc_feol] :743 |  |
| denmos.2 | KLayout only | – | – | denmos.2 0.28 [FEOL; only in lydrc_feol] :744 |  |
| denmos.3 | Magic only: only inside a composite rule; sky130A.lydrc has it | in (denmos.6 + denmos.3) 2.51 [FU] :4305 | – | denmos.3 0.925 [FEOL; only in lydrc_feol] :745 |  |
| denmos.4 | KLayout only | – | – | denmos.4 0.17 [FEOL; only in lydrc_feol] :746 |  |
| denmos.5 | KLayout only | – | – | denmos.5 0.225 [FEOL; only in lydrc_feol] :747 |  |
| denmos.6 | Magic only: sky130A.lydrc has it | in (denmos.6 + denmos.3) 2.51 [FU] :4305 | – | denmos.6 1.585 [FEOL; only in lydrc_feol] :748 |  |
| denmos.7 | Magic only: sky130A.lydrc has it | as denmos/depmos.2 5 [FU] :4303 | – | denmos.7 5 [FEOL; only in lydrc_feol] :749 |  |
| denmos.8 | KLayout only | – | – | denmos.8 90 [FEOL; only in lydrc_feol] :750 |  |
| denmos.9a | KLayout only | – | – | denmos.9a 0.43 [FEOL; only in lydrc_feol] :751,752,753 |  |
| denmos.9b | KLayout only | – | – | denmos.9b 0.05 [FEOL; only in lydrc_feol] :754,755 |  |
| denmos.10 | KLayout only | – | – | denmos.10 0.66 [FEOL; only in lydrc_feol] :756 |  |
| denmos.11 | KLayout only | – | – | denmos.11 0.86 [FEOL; only in lydrc_feol] :757 |  |
| denmos.12 | KLayout only | – | – | denmos.12 2.4 [FEOL; only in lydrc_feol] :758 |  |
| denmos.13 | KLayout only | – | – | denmos.13 0.13 [FEOL; only in lydrc_feol] :759 |  |
| depmos.1 | Magic only: sky130A.lydrc has it | 1.05 [FU] :4307 | – | depmos.1 1.05 [FEOL; only in lydrc_feol] :762 |  |
| depmos.2 | KLayout only | – | – | depmos.2 0.28 [FEOL; only in lydrc_feol] :763 |  |
| depmos.3 | Magic only: only inside a composite rule; sky130A.lydrc has it | in (depmos.6 + depmos.3) 2.11 [FU] :4308 | – | depmos.3 0.92 [FEOL; only in lydrc_feol] :764 |  |
| depmos.4 | KLayout only | – | – | depmos.4 0.17 [FEOL; only in lydrc_feol] :765 |  |
| depmos.5 | KLayout only | – | – | depmos.5 0.26 [FEOL; only in lydrc_feol] :766 |  |
| depmos.6 | Magic only: sky130A.lydrc has it | in (depmos.6 + depmos.3) 2.11 [FU] :4308 | – | depmos.6 1.19 [FEOL; only in lydrc_feol] :767 |  |
| depmos.7 | Magic only: sky130A.lydrc has it | as denmos/depmos.2 5 [FU] :4303 | – | depmos.7 5 [FEOL; only in lydrc_feol] :768 |  |
| depmos.8 | KLayout only | – | – | depmos.8 90 [FEOL; only in lydrc_feol] :769 |  |
| depmos.9a | KLayout only | – | – | depmos.9a 0.43 [FEOL; only in lydrc_feol] :770,771,772 |  |
| depmos.9b | KLayout only | – | – | depmos.9b 0.05 [FEOL; only in lydrc_feol] :773,774 |  |
| depmos.10 | KLayout only | – | – | depmos.10 0.86 [FEOL; only in lydrc_feol] :775 |  |
| depmos.11 | KLayout only | – | – | depmos.11 0.66 [FEOL; only in lydrc_feol] :776 |  |
| depmos.12 | KLayout only | – | – | depmos.12 0.13 [FEOL; only in lydrc_feol] :777 |  |
| diff/tap.1 | both | 0.15 [FU] :4216; 0.15 [FU] :4221 | difftap.1 0.15 [FEOL] :408; difftap.1_a 0.15 [FEOL] :415; difftap.1_b 0.15 [FEOL] :435; difftap.1_c 0.15 [FEOL] :442 | difftap.1 0.15 [FEOL; only in lydrc_feol] :263 | d_tap_w014: Magic FU, KLayout harness,lydrc_feol,menu |
| diff/tap.2 | Magic only: sky130A.lydrc has it | 0.42 [FU] :4771; 0.36 [FU] :4773; 0.21 [FU] :4775; 0.14 [FU] :4777 | – | difftap.2 0.36 [FEOL; only in lydrc_feol] :266,267 | d_gate_w036: Magic FU, KLayout lydrc_feol |
| diff/tap.3 | both | 0.27 [FU] :4227; 0.27 [FU] :4230; 0.27 [FU] :4234; 0.27 [FU] :4274; 0.27 [FU] :4276 | difftap.3 0.27 [FEOL] :445 | difftap.3 0.27 [FEOL; only in lydrc_feol] :268 | d_diff_space: Magic FU, KLayout harness,lydrc_feol,menu |
| diff/tap.4 | Magic only: sky130A.lydrc has it | 0.29 [FU] :4224; 0.29 [FU] :4225 | – | difftap.4 0.29 [FEOL; only in lydrc_feol] :269 | e_butt_short: Magic FU, KLayout no |
| diff/tap.5 | Magic only: sky130A.lydrc has it | 0.4 [FU] :4299; 0.4 [FU] :4300 | – | difftap.5 0.4 [FEOL; only in lydrc_feol] :270 |  |
| diff/tap.6 | KLayout only | – | – | difftap.6 – [FEOL; only in lydrc_feol] :271 |  |
| diff/tap.7 | KLayout only | – | – | difftap.7 0.13 [FEOL; only in lydrc_feol] :272,273 |  |
| diff/tap.8 | Magic only: sky130A.lydrc has it | 0.18 [FU] :4254 | – | difftap.8 0.18 [FEOL; only in lydrc_feol] :274 | w_nwell_encl_pdiff: Magic FU, KLayout lydrc_feol |
| diff/tap.9 | Magic only: sky130A.lydrc has it | 0.34 [FU] :4242 | – | difftap.9 0.34 [FEOL; only in lydrc_feol] :275 | w_ndiff_to_nwell: Magic FU, KLayout lydrc_feol |
| diff/tap.10 | Magic only: sky130A.lydrc has it | 0.18 [FU] :4250 | – | difftap.10 0.18 [FEOL; only in lydrc_feol] :276 | w_nwell_encl_ntap: Magic FU, KLayout lydrc_feol |
| diff/tap.11 | in the deck, did not fire on its case: Magic reported nothing on s_ptap_to_nwell; sky130A.lydrc has it | 0.13 [FU] :4246; 0.13 [FU] :4248 | – | difftap.11 0.13 [FEOL; only in lydrc_feol] :277 | s_ptap_to_nwell: Magic no, KLayout lydrc_feol |
| diff/tap.14 | Magic only: sky130A.lydrc has it | 0.29 [FU] :4218 | – | hvdifftap.14 0.29 [FEOL; only in lydrc_feol] :715 |  |
| diff/tap.14a | Magic only: sky130A.lydrc has it | 0.15 [FU] :4226 | – | hvdifftap.14a 0.15 [FEOL; only in lydrc_feol] :716 |  |
| diff/tap.15a | Magic only: sky130A.lydrc has it | 0.3 [FU] :4232 | – | hvdifftap.15a 0.3 [FEOL; only in lydrc_feol] :717 |  |
| diff/tap.15b | Magic only: sky130A.lydrc has it | 0.37 [FU] :4236 | – | hvdifftap.15b 0.37 [FEOL; only in lydrc_feol] :718 |  |
| diff/tap.16 | Magic only: sky130A.lydrc has it | 0.7 [FU] :4222; 0.7 [FU] :4223 | – | hvdifftap.16 0.7 [FEOL; only in lydrc_feol] :719 |  |
| diff/tap.17 | Magic only: sky130A.lydrc has it | in (diff/tap.20 + diff/tap.17,19) 0.76 [FU] :4239; 0.33 [FU] :4256 | – | hvdifftap.17 0.33 [FEOL; only in lydrc_feol] :720 |  |
| diff/tap.18 | Magic only: sky130A.lydrc has it | 0.43 [U] :4270 | – | hvdifftap.18 0.43 [FEOL; only in lydrc_feol] :721 |  |
| diff/tap.19 | Magic only: sky130A.lydrc has it | in (diff/tap.20 + diff/tap.17,19) 0.76 [FU] :4239; 0.33 [FU] :4252 | – | hvdifftap.19 0.33 [FEOL; only in lydrc_feol] :722 |  |
| diff/tap.20 | Magic only: sky130A.lydrc has it | in (diff/tap.20 + diff/tap.17,19) 0.76 [FU] :4239; as diff/tap.18 0.43 [U] :4270 | – | hvdifftap.20 0.43 [FEOL; only in lydrc_feol] :723 |  |
| diff/tap.21 | Magic only: sky130A.lydrc has it | – [U] :4207 | – | hvdifftap.21 – [FEOL; only in lydrc_feol] :724,725 |  |
| diff/tap.22 | Magic only: only inside a composite rule; sky130A.lydrc has it | in (diff/tap.23 + diff/tap.22) 0.36 [FU] :4802; in (diff/tap.23 + diff/tap.22) 0.36 [FU] :4805; in (diff/tap.23 + diff/tap.22) 0.36 [FU] :4809; in (diff/tap.23 + diff/tap.22) 0.36 [FU] :4812 | – | hvdifftap.22 0.18 [FEOL; only in lydrc_feol] :726 |  |
| diff/tap.23 | Magic only: sky130A.lydrc has it | in (diff/tap.23 + diff/tap.22) 0.36 [FU] :4802; in (diff/tap.23 + diff/tap.22) 0.36 [FU] :4805; in (diff/tap.23 + diff/tap.22) 0.36 [FU] :4809; in (diff/tap.23 + diff/tap.22) 0.36 [FU] :4812 | – | hvdifftap.23 0.18 [FEOL; only in lydrc_feol] :727 |  |
| diff/tap.24 | Magic only: sky130A.lydrc has it | 0.43 [FU] :4244 | – | hvdifftap.24 0.43 [FEOL; only in lydrc_feol] :728 |  |
| diff/tap.25 | KLayout only | – | – | hvdifftap.25 1.07 [FEOL; only in lydrc_feol] :729 |  |
| difftap.2 [sky130A_mr.drc] | same name for another check: the foundry's core rule difftap.c1, diffusion width 0.14 µm inside areaid:ce; Magic's diff/tap.2 is the transistor width 0.42 µm (GAPS-sky130A ranked gap 7) | – | difftap.2 0.14 [FEOL] :422 | – |  |
| dnwell.2 | both | 3 [FU] :4171 | dnwell.1 3 [FEOL] :289 | dnwell.2 3 [FEOL; only in lydrc_feol] :205 |  |
| dnwell.3 | both | 6.3 [FU] :4172 | dnwell.2 6.3 [FEOL] :296 | dnwell.3 6.3 [FEOL; only in lydrc_feol] :206 |  |
| dnwell.4 | KLayout only | – | – | dnwell.4 – [FEOL; only in lydrc_feol] :207 |  |
| dnwell.5 | Magic only: sky130A.lydrc has it | – [U] :4182 | – | dnwell.5 – [FEOL; only in lydrc_feol] :208 |  |
| exact_overlap | Magic only | – [FUR] :4552; – [FUR] :4595; – [FUR] :4637; – [FUR] :4676; – [FUR] :4710; – [FUR] :4743; 2 more | – | – |  |
| extd.1 | KLayout only | – | – | extd.1 – [FEOL; only in lydrc_feol] :780 |  |
| extd.2 | KLayout only | – | – | extd.2 – [FEOL; only in lydrc_feol] :781 |  |
| hv.diff.1 | KLayout only | – | – | hv.diff.1 0.3 [FEOL; only in lydrc_feol] :795 |  |
| hv.diff.2 | KLayout only | – | – | hv.diff.2 0.43 [FEOL; only in lydrc_feol] :796 |  |
| hv.diff.3a | KLayout only | – | – | hv.diff.3a 0.55 [FEOL; only in lydrc_feol] :797 |  |
| hv.nwell.1 | KLayout only | – | – | hv.nwell.1 2.5 [FEOL; only in lydrc_feol] :794 |  |
| hv.poly.2 | KLayout only | – | – | hv.poly.2 0.3 [FEOL; only in lydrc_feol] :799 |  |
| hv.poly.3 | KLayout only | – | – | hv.poly.3 0.55 [FEOL; only in lydrc_feol] :800 |  |
| hv.poly.4 | KLayout only | – | – | hv.poly.4 0.3 [FEOL; only in lydrc_feol] :801 |  |
| hvi.1 | KLayout only | – | hvi.1 0.6 [FEOL] :1471 | hvi.1 0.6 [FEOL; only in lydrc_feol] :709 |  |
| hvi.2a | both | as hvi.5 0.7 [U] :4266 | hvi.2a 0.7 [FEOL] :1475 | hvi.2 0.7 [FEOL; only in lydrc_feol] :710 |  |
| hvi.4 | KLayout only | – | – | hvi.4 – [FEOL; only in lydrc_feol] :711 |  |
| hvi.5 | Magic only | in (hvi.5 + nsd/psd.5) 0.825 [U] :4264; 0.7 [U] :4268 | – | – |  |
| hvntm.1 | both | 0.7 [U] :4416 | hvntm.1 0.7 [FEOL] :1484 | hvntm.1 0.7 [FEOL; only in lydrc_feol] :734 |  |
| hvntm.2 | both | in (hvntm.2 + 2 * hvntm.3) 1.07 [FU] :4260; 0.7 [U] :4417; 0.7 [U] :4948 | hvntm.2 0.7 [FEOL] :1488 | hvntm.2 0.7 [FEOL; only in lydrc_feol] :735 |  |
| hvntm.3 | Magic only: only inside a composite rule; sky130A.lydrc has it | in (hvntm.2 + 2 * hvntm.3) 1.07 [FU] :4260; in (rpm.3 + rpm.9 + hvntm.3) 0.585 [F] :4363; in (rpm.3 + rpm.9 + hvntm.3) 0.585 [U] :4375 | – | hvntm.3 0.185 [FEOL; only in lydrc_feol] :736 |  |
| hvntm.4 | KLayout only | – | – | hvntm.4 0.185 [FEOL; only in lydrc_feol] :737 |  |
| hvntm.5 | KLayout only | – | – | hvntm.5 0.185 [FEOL; only in lydrc_feol] :738 |  |
| hvntm.6a | KLayout only | – | – | hvntm.6a 0.185 [FEOL; only in lydrc_feol] :739 |  |
| hvntm.9 | KLayout only | – | – | hvntm.9 – [FEOL; only in lydrc_feol] :740 |  |
| hvnwel.9 | KLayout only | – | – | hvnwel.9 – [FEOL; only in lydrc_feol] :713 |  |
| hvpoly.14 | KLayout only | – | – | hvpoly.14 – [FEOL; only in lydrc_feol] :731 |  |
| hvtp.1 | KLayout only | – | hvtp.1 0.38 [FEOL] :337 | hvtp.1 0.38 [FEOL; only in lydrc_feol] :231 | i_hvtp_w030: Magic no, KLayout harness,lydrc_feol,menu; s_hvtp_alone: Magic no, KLayout harness,lydrc_feol,menu |
| hvtp.2 | KLayout only | – | hvtp.2 0.38 [FEOL] :341 | hvtp.2 0.38 [FEOL; only in lydrc_feol] :232 |  |
| hvtp.3 | KLayout only | – | – | hvtp.3 0.18 [FEOL; only in lydrc_feol] :233 |  |
| hvtp.4 | Magic only: sky130A.lydrc has it, with other values (Magic 0.36, sky130A.lydrc 0.18) | 0.36 [FU] :4386; in (hvtp.4 + varac.3) 0.36 [FU] :4390 | – | hvtp.4 0.18 [FEOL; only in lydrc_feol] :234 |  |
| hvtp.5 | KLayout only | – | – | hvtp.5 0.265 µm² [FEOL; only in lydrc_feol] :235 |  |
| hvtr.1 | KLayout only | – | hvtr.1 0.38 [FEOL] :361 | hvtr.1 0.38 [FEOL; only in lydrc_feol] :238 |  |
| hvtr.2 | KLayout only | – | hvtr.2 0.38 [FEOL] :365 | hvtr.2 0.38 [FEOL; only in lydrc_feol] :239 |  |
| hvtr.2_a | KLayout only | – | hvtr.2_a – [FEOL] :369 | – |  |
| ldntm.1 | KLayout only | – | ldntm.1 0.7 [FEOL] :505 | – |  |
| ldntm.2 | KLayout only | – | ldntm.2 0.7 [FEOL] :509 | – |  |
| li.1 | both | 0.17 [FUR] :4560 | li.1 0.17 [BEOL] :893 | li.1 0.17 [BEOL] :444 | s_li_w016: Magic FUR, KLayout harness,lydrc,lydrc_feol,menu |
| li.1a | KLayout only | – | – | li.1a 0.14 [BEOL] :447 |  |
| li.3 | both | 0.17 [FUR] :4563 | li.3 0.17 [BEOL] :897 | li.3 0.17 [BEOL] :451 | s_li_space016: Magic FUR, KLayout harness,lydrc,lydrc_feol,menu |
| li.3a | KLayout only | – | – | li.3a 0.14 [BEOL] :452 |  |
| li.5 | both | in (licon.1c + li.5) 2.16 [FU] :4350; in (licon.1b + 2 * li.5) 0.35 [FUR] :4450; 0.08 [FUR] :4575; 0.08 [FUR] :4578 | li.5 0.08 [BEOL] :906 | li.5 0.08 [BEOL] :456 | l_li_encl: Magic FUR, KLayout harness,lydrc,lydrc_feol,menu; s_li_adj_licon: Magic no, KLayout no |
| li.6 | both | 0.0561 µm² [FUR] :4452; 0.0561 µm² [FUR] :4582 | li.6 0.0561 µm² [BEOL] :911 | li.6 0.0561 µm² [BEOL] :457 | s_li_area: Magic FUR, KLayout harness,lydrc,lydrc_feol,menu |
| li.7 | both | 0.29 [FUR] :4561 | MR_li.WID.4 0.29 [BEOL] :928 | – |  |
| li.c1 | both | 0.14 [FUR] :4569 | li.8 0.14 [BEOL] :920 | – |  |
| li.c2 | both | 0.14 [FUR] :4572 | li.7 0.14 [BEOL] :916 | – |  |
| licon.1 | both | 0.17 [FUR] :4442; 0.17 [FUR] :4443; 0.17 [FUR] :4444; 0.17 [FUR] :4445; 0.17 [FUR] :4446; 0.17 [FUR] :4447; 7 more | licon.1 0.17 [FEOL] :754; licon.1_c – [FEOL] :744 | licon.1 0.17 [FEOL; only in lydrc_feol] :361 | c_licon_016: Magic FUR, KLayout harness,lydrc_feol,menu; c_licon_020: Magic no, KLayout harness,lydrc_feol,menu |
| licon.1b | Magic only: sky130A.lydrc has it | in (licon.1b + 2 * li.5) 0.35 [FUR] :4450 | – | licon.1b/c 0.19 [FEOL; only in lydrc_feol] :362 |  |
| licon.1c | Magic only: sky130A.lydrc has it | in (licon.1c + li.5) 2.16 [FU] :4350; 0.7 µm² [FUR] :4451 | – | licon.1b/c 0.19 [FEOL; only in lydrc_feol] :362 |  |
| licon.2 | both | 0.17 [FUR] :4461; 0.17 [FUR] :4463; 0.17 [FUR] :4465; 0.17 [FUR] :4467 | MR_licon.SP.1 0.17 [FEOL] :749 | licon.2 0.17 [FEOL; only in lydrc_feol] :363 | c_licon_space: Magic FUR, KLayout harness,lydrc_feol,menu |
| licon.2b | KLayout only | – | – | licon.2b 0.35 [FEOL; only in lydrc_feol] :364 |  |
| licon.2c | KLayout only | – | – | licon.2c 0.51 [FEOL; only in lydrc_feol] :365 |  |
| licon.2d | KLayout only | – | – | licon.2d 0.51 [FEOL; only in lydrc_feol] :366 |  |
| licon.4 | KLayout only | – | – | licon.4 – [FEOL; only in lydrc_feol] :368 |  |
| licon.5a | Magic only: sky130A.lydrc has it | 0.04 [FUR] :4489; 0.04 [FUR] :4491; 0.04 [FUR] :4494; 0.04 [FUR] :4496; 0.04 [FUR] :4519; 0.04 [FUR] :4521; 2 more | – | licon.5 0.04 [FEOL; only in lydrc_feol] :369 | c_ndiff_encl0: Magic FUR, KLayout lydrc_feol |
| licon.5b | Magic only: sky130A.lydrc has it | 0.06 [FUR] :4499; 0.06 [FUR] :4501; 0.06 [FUR] :4528; 0.06 [FUR] :4530 | – | licon.6 0.06 [FEOL; only in lydrc_feol] :370 | e_butt_licon5b: Magic FUR, KLayout no |
| licon.5c | Magic only | 0.06 [FUR] :4504; 0.06 [FUR] :4506; 0.06 [FUR] :4509; 0.06 [FUR] :4511; 0.06 [FUR] :4533; 0.06 [FUR] :4535; 2 more | – | – |  |
| licon.6 | KLayout only | – | licon.6 0.045 [FEOL] :784,788 | – |  |
| licon.7 | Magic only: sky130A.lydrc has it | 0.12 [FUR] :4514; 0.12 [FUR] :4516; 0.12 [FUR] :4542; 0.12 [FUR] :4544 | – | licon.7 0.12 [FEOL; only in lydrc_feol] :373 | c_tap_encl: Magic FUR, KLayout lydrc_feol |
| licon.8 | Magic only: sky130A.lydrc has it | 0.05 [FUR] :4547 | – | licon.8 0.05 [FEOL; only in lydrc_feol] :374 | a_licon8: Magic FUR, KLayout lydrc_feol |
| licon.8a | Magic only: sky130A.lydrc has it | 0.08 [FUR] :4549 | – | licon.8a 0.08 [FEOL; only in lydrc_feol] :378 | a_licon8: Magic FUR, KLayout no |
| licon.9 | Magic only | in (licon.9 + psdm.5a) 0.235 [FUR] :4471 | – | – | c_pc_to_pdiff: Magic FUR, KLayout no |
| licon.10 | Magic only: sky130A.lydrc has it | 0.25 [FUR] :4484; 0.25 [FUR] :4486 | – | licon.10 0.25 [FEOL; only in lydrc_feol] :380 |  |
| licon.11 | Magic only: sky130A.lydrc has it | 0.055 [FUR] :4474; 0.05 [FUR] :4476; 0.04 [FUR] :4478; 0.075 [FUR] :4480; 0.055 [FUR] :4482 | – | licon.11 0.055 [FEOL; only in lydrc_feol] :383; licon.11a 0.05 [FEOL; only in lydrc_feol] :384; licon.11c 0.04 [FEOL; only in lydrc_feol] :387 | a_licon11: Magic no, KLayout lydrc_feol; c_licon11_li: Magic FUR, KLayout lydrc_feol; c_licon_gate: Magic FUR, KLayout no |
| licon.12 | KLayout only | – | – | licon.12 5.7 [FEOL; only in lydrc_feol] :389 |  |
| licon.13 | KLayout only | – | licon.13 0.09 [FEOL] :761; licon.13_a – [FEOL] :768 | licon.13 0.09 [FEOL; only in lydrc_feol] :390 | c_npc_over_dlicon: Magic no, KLayout harness,menu |
| licon.14 | Magic only: sky130A.lydrc has it | 0.19 [FUR] :4469 | – | licon.14 0.19 [FEOL; only in lydrc_feol] :391 | c_pc_to_diff: Magic FUR, KLayout lydrc_feol |
| licon.15 | KLayout only | – | – | licon.15 0.1 [FEOL; only in lydrc_feol] :392 |  |
| licon.16 | in the deck, did not fire on its case: Magic reported nothing on w_no_ntap_licon, w_no_ptap_licon; sky130A.lydrc has it | – [U] :4317 | – | licon.16 – [FEOL; only in lydrc_feol] :395 | w_no_ntap_licon: Magic no, KLayout lydrc_feol; w_no_ptap_licon: Magic no, KLayout lydrc_feol |
| licon.17 | KLayout only | – | licon.17 – [FEOL] :775 | licon.17 – [FEOL; only in lydrc_feol] :396 | c_licon_gate: Magic no, KLayout harness,menu |
| licon.18 | KLayout only | – | – | licon.18 – [FEOL; only in lydrc_feol] :397 |  |
| LU.2 | Magic only | 15 [U] :4320 | – | – | w_no_ptap: Magic U, KLayout no |
| LU.2.1 | Magic only | 15 [U] :4322 | – | – |  |
| LU.3 | Magic only | 15 [U] :4324 | – | – | w_no_ntap: Magic U, KLayout no |
| lvtn.1 | KLayout only | – | – | lvtn.1 0.38 [FEOL; only in lydrc_feol] :242 |  |
| lvtn.1a | KLayout only | – | lvtn.1a 0.38 [FEOL] :374 | – | s_lvtn_alone: Magic no, KLayout harness,menu |
| lvtn.2 | KLayout only | – | lvtn.2 0.38 [FEOL] :378 | lvtn.2 0.38 [FEOL; only in lydrc_feol] :243 |  |
| lvtn.3a | Magic only: sky130A.lydrc has it, with other values (Magic 0.36, sky130A.lydrc 0.18) | 0.36 [FU] :4397 | – | lvtn.3a 0.18 [FEOL; only in lydrc_feol] :244 |  |
| lvtn.3b | Magic only: sky130A.lydrc has it, with other values (Magic 0.415, sky130A.lydrc 0.18) | 0.415 [FU] :4406 | – | lvtn.3b 0.18 [FEOL; only in lydrc_feol] :245 |  |
| lvtn.4b | Magic only: only inside a composite rule; sky130A.lydrc has it | in (lvtn.10 + lvtn.4b) 0.56 [FU] :4258 | – | lvtn.4b 0.18 [FEOL; only in lydrc_feol] :246,248 |  |
| lvtn.9 | Magic only: sky130A.lydrc has it, with other values (Magic 0.74, sky130A.lydrc 0.38) | 0.74 [FU] :4401 | – | lvtn.9 0.38 [FEOL; only in lydrc_feol] :247 |  |
| lvtn.10 | Magic only | in (lvtn.10 + lvtn.4b) 0.56 [FU] :4258 | – | – |  |
| lvtn.12 | KLayout only | – | – | lvtn.12 0.38 [FEOL; only in lydrc_feol] :249 |  |
| lvtn.13 | KLayout only | – | – | lvtn.13 0.265 µm² [FEOL; only in lydrc_feol] :250 |  |
| mcon.1 | both | 0.17 [FUR] :4592 | ct.1 – [BEOL] :944; ct.1_a 0.17 [BEOL] :949; ct.1_b 0.17 [BEOL] :953 | ct.1 0.17 [BEOL] :460 |  |
| mcon.2 | both | 0.19 [FUR] :4593 | ct.2 0.19 [BEOL] :957 | ct.2 0.19 [BEOL] :461 |  |
| met1.1 | both | 0.14 [FUR] :4601 | m1.1 0.14 [BEOL] :980 | m1.1 0.14 [BEOL] :470 | s_m1_w013: Magic FUR, KLayout harness,lydrc,lydrc_feol,menu |
| met1.2 | both | 0.14 [FUR] :4602 | m1.2 0.14 [BEOL] :985 | m1.2 0.14 [BEOL] :475 | s_m1_space013: Magic FUR, KLayout harness,lydrc,lydrc_feol,menu |
| met1.3a | in the deck, did not fire on its case: KLayout reported nothing on s_m1_wide_space | 0.28 [U] :4622 | m1.3ab 0.28 [BEOL] :993 | m1.3ab 0.28 [BEOL] :477 | s_m1_wide_space: Magic U, KLayout no |
| met1.3b | both | 0.28 [FU] :4613; 0.28 [FU] :4615 | m1.3ab 0.28 [BEOL] :993 | m1.3ab 0.28 [BEOL] :477 | s_m1_huge_space: Magic FU, KLayout harness,lydrc,lydrc_feol,menu |
| met1.4 | both | 0.03 [FUR] :4605 | 791_m1.4 0.03 [BEOL] :1006; m1.4 – [BEOL] :1010 | m1.4 0.03 [BEOL] :481 | s_m1_encl_mcon: Magic FUR, KLayout harness,lydrc,lydrc_feol,menu |
| met1.4a | KLayout only | – | m1.4a 0.005 [BEOL] :1025; m1.4a_a – [BEOL] :1030 | m1.4a 0.005 [BEOL] :484 |  |
| met1.5 | both | 0.06 [FUR] :4607 | m1.5 0.06 [BEOL & backend_flow = AL] :1056 | m1.5 0.06 [BEOL & backend_flow = AL] :491 | s_m1_adj_mcon: Magic FUR, KLayout harness,menu |
| met1.6 | both | 0.083 µm² [FUR] :4603 | m1.6 0.083 µm² [BEOL] :1035 | m1.6 0.083 µm² [BEOL] :485 | s_m1_area: Magic FUR, KLayout harness,lydrc,lydrc_feol,menu |
| met1.7 | in the deck, did not fire on its case: Magic reported nothing on s_m1_hole, s_m1_hole_boxes | 0.14 µm² [U] :4619 | m1.7 0.14 µm² [BEOL] :1040 | m1.7 0.14 µm² [BEOL] :486 | s_m1_hole: Magic no, KLayout harness,lydrc,lydrc_feol,menu; s_m1_hole_boxes: Magic no, KLayout harness,lydrc,lydrc_feol,menu |
| mf.1 | KLayout only | – | – | mf.1 0.8 [FEOL; only in lydrc_feol] :703 |  |
| mf.2 | KLayout only | – | – | mf.2 7.2 [FEOL; only in lydrc_feol] :704 |  |
| mf.3 | KLayout only | – | – | mf.3 2.76 [FEOL; only in lydrc_feol] :705 |  |
| MR_lvtn.OVL.2 | KLayout only | – | MR_lvtn.OVL.2 – [FEOL] :387 | – |  |
| MR_rdl.CON.1 | KLayout only | – | MR_rdl.CON.1 – [FEOL] :531 | – |  |
| MR_thkox.CON.1 | KLayout only | – | MR_thkox.CON.1 – [FEOL] :482 | – |  |
| MR_tunm.CON.1 | KLayout only | – | MR_tunm.CON.1 – [FEOL] :460 | – |  |
| n/psdm.1 | KLayout only | – | – | n/psdm.1 0.38 [FEOL; only in lydrc_feol] :348,349 |  |
| n/psdm.6 | KLayout only | – | – | n/psdm.6 0 [FEOL; only in lydrc_feol] :352 |  |
| n/psdm.7 | KLayout only | – | – | n/psdm.7 0.13 [FEOL; only in lydrc_feol] :353 |  |
| n/psdm.8 | KLayout only | – | – | n/psdm.8 – [FEOL; only in lydrc_feol] :354,355 |  |
| n/psdm.10a | KLayout only | – | – | n/psdm.10a 0.265 µm² [FEOL; only in lydrc_feol] :357 |  |
| n/psdm.10b | KLayout only | – | – | n/psdm.10b 0.265 µm² [FEOL; only in lydrc_feol] :358 |  |
| ncm.1 | KLayout only | – | ncm.1 0.38 [FEOL] :392 | ncm.1 0.38 [FEOL; only in lydrc_feol] :254 |  |
| ncm.2 | KLayout only | – | – | ncm.2 0.38 [FEOL; only in lydrc_feol] :255 |  |
| ncm.2a | KLayout only | – | ncm.2a 0.38 [FEOL] :393 | – |  |
| ncm.3 | KLayout only | – | – | ncm.3 0.18 [FEOL; only in lydrc_feol] :256 |  |
| ncm.5 | KLayout only | – | – | ncm.5 0.23 [FEOL; only in lydrc_feol] :257 |  |
| ncm.6 | KLayout only | – | – | ncm.6 0.2 [FEOL; only in lydrc_feol] :258 |  |
| ncm.7 | KLayout only | – | – | ncm.7 0.265 µm² [FEOL; only in lydrc_feol] :259 |  |
| ncm.x.3 | KLayout only | – | – | ncm.x.3 – [FEOL; only in lydrc_feol] :253 |  |
| npc.1 | KLayout only | – | npc.1 0.27 [FEOL] :548 | npc.1 0.27 [FEOL; only in lydrc_feol] :340 | c_npc_narrow: Magic no, KLayout harness,lydrc_feol,menu; s_npc_alone: Magic no, KLayout harness,lydrc_feol,menu |
| npc.2 | KLayout only | – | npc.2 0.27 [FEOL] :549 | npc.2 0.27 [FEOL; only in lydrc_feol] :341 |  |
| npc.4 | KLayout only | – | – | npc.4 0.09 [FEOL; only in lydrc_feol] :342 |  |
| nsd.5a | in the deck, did not fire on its case: Magic reported nothing on a_nsdm_flush; sky130A.lydrc has it | 0.125 [FU] :4286; 0.125 [FU] :4295; in (rpm.3 + rpm.6 + nsd.5a) 0.525 [F] :4359; in (rpm.3 + rpm.6 + nsd.5a) 0.525 [U] :4371 | – | n/psdm.5a 0.125 [FEOL; only in lydrc_feol] :350 | a_nsdm_flush: Magic no, KLayout no |
| nsd.5b | Magic only: sky130A.lydrc has it | 0.125 [FU] :4284; 0.125 [FU] :4293 | – | n/psdm.5b 0.125 [FEOL; only in lydrc_feol] :351 |  |
| nsd.10b | Magic only: Magic checks the n-tap's area, 0.07011 µm², the area of a square tap whose 0.125 µm implant reaches 0.265 µm²; the manual's rule is the drawn nsdm's area (n/psd.10a, 0.265 µm²), which sky130A.lydrc checks as n/psdm.10a | 0.07011 µm² [FU] :4311 | – | – |  |
| nsdm.1 | KLayout only | – | nsdm.1 0.38 [FEOL & SRAM_EXCLUDE / FEOL & not (SRAM_EXCLUDE)] :561,602 | nsdm.1 0.38 [FEOL; only in lydrc_feol] :346 |  |
| nsdm.2 | KLayout only | – | nsdm.2 0.38 [FEOL & SRAM_EXCLUDE / FEOL & not (SRAM_EXCLUDE)] :565,606 | – |  |
| nsdm.3 | KLayout only | – | nsdm.3 0.38 [FEOL & SRAM_EXCLUDE / FEOL & not (SRAM_EXCLUDE)] :573,611 | – |  |
| nsdm.4 | KLayout only | – | nsdm.4 0.38 [FEOL & SRAM_EXCLUDE / FEOL & not (SRAM_EXCLUDE)] :581,616 | – |  |
| nsdm.5 | KLayout only | – | nsdm.5 0.29 [FEOL & SRAM_EXCLUDE / FEOL & not (SRAM_EXCLUDE)] :585,620 | – |  |
| nsdm.6 | KLayout only | – | nsdm.6 0.29 [FEOL & SRAM_EXCLUDE / FEOL & not (SRAM_EXCLUDE)] :589,624 | – |  |
| nsdm.6a | KLayout only | – | nsdm.6a 0.38 [FEOL & SRAM_EXCLUDE / FEOL & not (SRAM_EXCLUDE)] :594,629 | – |  |
| nsdm_psdm_overlap | KLayout only | – | nsdm_psdm_overlap – [FEOL & SRAM_EXCLUDE / FEOL & not (SRAM_EXCLUDE)] :683,725 | – |  |
| nwell.1 | both | 0.84 [FU] :4195 | nwell.1 0.84 [FEOL] :315 | nwell.1 0.84 [FEOL; only in lydrc_feol] :212 | s_nwell_w080: Magic FU, KLayout harness,lydrc_feol,menu |
| nwell.2a | both | 1.27 [FU] :4196 | nwell.2a 1.27 [FEOL] :319 | nwell.2a 1.27 [FEOL; only in lydrc_feol] :213 | s_nwell_space: Magic FU, KLayout harness,lydrc_feol,menu |
| nwell.4 | Magic only | – [U] :4199 | – | – | w_no_ntap: Magic U, KLayout no; w_no_ntap_licon: Magic U, KLayout no |
| nwell.5a | Magic only: sky130A.lydrc has it, with other values (Magic 1.03, sky130A.lydrc 0.4) | 1.03 [U] :4177 | – | nwell.5 0.4 [FEOL; only in lydrc_feol] :216 |  |
| nwell.6 | KLayout only | – | nwell.6 1.03 [FEOL] :324 | nwell.6 1.03 [FEOL; only in lydrc_feol] :217 |  |
| nwell.7 | Magic only: sky130A.lydrc has it | 4.5 [FU] :4173; as nwell.5a 1.03 [U] :4177 | – | nwell.7 4.5 [FEOL; only in lydrc_feol] :218 |  |
| nwell.8 | Magic only: sky130A.lydrc has it | 2 [U] :4202; 2 [U] :4204 | – | hvnwell.8 2 [FEOL; only in lydrc_feol] :712 |  |
| nwell.9 | KLayout only | – | nwell.9 – [FEOL] :332 | – |  |
| photo.2 | Magic only: sky130A.lydrc has it | 3 [FU] :4186 | – | photo.2 3 [FEOL; only in lydrc_feol] :330 |  |
| photo.3 | Magic only: sky130A.lydrc has it | 5 [FU] :4187 | – | photo.3 5 [FEOL; only in lydrc_feol] :331 |  |
| photo.4 | Magic only: sky130A.lydrc has it | 5.3 [FU] :4188 | – | photo.4 5.3 [FEOL; only in lydrc_feol] :332 |  |
| photo.5.6 | KLayout only | – | – | photo.5.6 – [FEOL; only in lydrc_feol] :333 |  |
| photo.7 | KLayout only | – | – | photo.7 – [FEOL; only in lydrc_feol] :334 |  |
| photo.8 | KLayout only | – | – | photo.8 0.84 [FEOL; only in lydrc_feol] :335 |  |
| photo.9 | KLayout only | – | – | photo.9 1.08 [FEOL; only in lydrc_feol] :336 |  |
| photo.10 | KLayout only | – | – | photo.10 0.41 [FEOL; only in lydrc_feol] :337 |  |
| poly.1a | both | 0.15 [FU] :4333; in (P+ poly.1a) 0.35 [FU] :4839; in (P+ poly.1a) 0.35 [FU] :4840 | poly.1a 0.15 [FEOL] :487 | poly.1a 0.15 [FEOL; only in lydrc_feol] :289 | p_gate_l014: Magic FU, KLayout harness,lydrc_feol,menu; s_poly_w014: Magic FU, KLayout harness,lydrc_feol,menu |
| poly.1b | Magic only: sky130A.lydrc has it | 0.35 [FU] :4781 | – | poly.1b 0.35 [FEOL; only in lydrc_feol] :290 | e_pfet_lvt: Magic FU, KLayout no |
| poly.2 | both | 0.21 [FU] :4334; 0.21 [FU] :4352 | poly.2 0.21 [FEOL] :494 | poly.2 0.21 [FEOL; only in lydrc_feol] :291 | p_extra_space: Magic FU, KLayout harness,lydrc_feol,menu; s_poly_space: Magic FU, KLayout harness,lydrc_feol,menu |
| poly.3 | Magic only: sky130A.lydrc has it | 0.33 [FU] :4831 | – | poly.3 0.33 [FEOL; only in lydrc_feol] :292 |  |
| poly.3 [sky130A_mr.drc] | same name for another check: the foundry's core rule poly.c2, poly spacing 0.16 µm; Magic's poly.3 is the poly resistor width 0.33 µm (GAPS-sky130A ranked gap 7) | – | poly.3 0.16 [FEOL] :499 | – |  |
| poly.4 | Magic only: sky130A.lydrc has it | 0.075 [FU] :4336 | – | poly.4 0.075 [FEOL; only in lydrc_feol] :293 | p_field_to_diff: Magic FU, KLayout lydrc_feol |
| poly.5 | Magic only: sky130A.lydrc has it | 0.055 [FU] :4783; 0.055 [FU] :4785; 0.055 [FU] :4787; 0.055 [FU] :4789 | – | poly.5 0.055 [FEOL; only in lydrc_feol] :294 | p_poly_to_tap: Magic FU, KLayout lydrc_feol |
| poly.6 | Magic only: sky130A.lydrc has it | 0.3 [FU] :4792; 0.3 [FU] :4794; 0.3 [FU] :4796; 0.3 [FU] :4798 | – | poly.6 0.3 [FEOL; only in lydrc_feol] :295 |  |
| poly.7 | Magic only: sky130A.lydrc has it | 0.25 [FU] :4342; 0.25 [FU] :4343; 0.25 [FU] :4345; 0.25 [FU] :4346 | – | poly.7 0.25 [FEOL; only in lydrc_feol] :296 | d_sd_020: Magic FU, KLayout lydrc_feol |
| poly.8 | Magic only: sky130A.lydrc has it | 0.13 [FU] :4347; 0.11 [FU] :4348 | – | poly.8 0.13 [FEOL; only in lydrc_feol] :297 | a_poly8: Magic FU, KLayout lydrc_feol |
| poly.9 | Magic only: sky130A.lydrc has it | 0.48 [FU] :4340; 0.48 [FU] :4842; 0.48 [FU] :4845; 0.48 [FU] :4848; 0.48 [FU] :4851; 0.48 [FU] :4854 | – | poly.9 0.48 [FEOL; only in lydrc_feol] :298 |  |
| poly.10 | KLayout only | – | – | poly.10 – [FEOL; only in lydrc_feol] :299 |  |
| poly.11 | Magic only: sky130A.lydrc has it | – [FU] :4349 | – | poly.11 – [FEOL; only in lydrc_feol] :300 | e_bent_gate: Magic FU, KLayout no |
| poly.12 | KLayout only | – | – | poly.12 – [FEOL; only in lydrc_feol] :303 |  |
| poly.13 | Magic only: sky130A.lydrc has it | 0.5 [FU] :4818; 0.5 [FU] :4821; 0.5 [FU] :4824 | – | hvpoly.13 0.5 [FEOL; only in lydrc_feol] :730 |  |
| poly.15 | KLayout only | – | – | poly.15 – [FEOL; only in lydrc_feol] :304 |  |
| psd.5a | Magic only: sky130A.lydrc has it | 0.125 [FU] :4282; 0.125 [FU] :4291 | – | n/psdm.5a 0.125 [FEOL; only in lydrc_feol] :350 |  |
| psd.5b | Magic only: sky130A.lydrc has it | 0.125 [FU] :4280; 0.125 [FU] :4289 | – | n/psdm.5b 0.125 [FEOL; only in lydrc_feol] :351 |  |
| psd.10b | Magic only: Magic checks the p-tap's area at 0.07011 µm², the same value as its n-tap check; the manual's rule is the drawn psdm's area (n/psd.10b, 0.255 µm²), which sky130A.lydrc checks as n/psdm.10b at 0.265 µm² | 0.07011 µm² [FU] :4312 | – | – |  |
| psdm.1 | KLayout only | – | psdm.1 0.38 [FEOL & SRAM_EXCLUDE / FEOL & not (SRAM_EXCLUDE)] :643,691 | psdm.1 0.38 [FEOL; only in lydrc_feol] :347 |  |
| psdm.2 | KLayout only | – | psdm.2 0.38 [FEOL & SRAM_EXCLUDE / FEOL & not (SRAM_EXCLUDE)] :647,695 | – |  |
| psdm.3 | KLayout only | – | psdm.3 0.38 [FEOL & SRAM_EXCLUDE / FEOL & not (SRAM_EXCLUDE)] :655,700 | – |  |
| psdm.4 | KLayout only | – | psdm.4 0.38 [FEOL & SRAM_EXCLUDE / FEOL & not (SRAM_EXCLUDE)] :663,705 | – |  |
| psdm.5 | KLayout only | – | psdm.5 0.29 [FEOL & SRAM_EXCLUDE / FEOL & not (SRAM_EXCLUDE)] :667,709 | – |  |
| psdm.6 | KLayout only | – | psdm.6 0.29 [FEOL & SRAM_EXCLUDE / FEOL & not (SRAM_EXCLUDE)] :671,713 | – |  |
| psdm.6a | KLayout only | – | psdm.6a 0.38 [FEOL & SRAM_EXCLUDE / FEOL & not (SRAM_EXCLUDE)] :676,718 | – |  |
| pwbm | KLayout only | – | – | pwbm – [FEOL; only in lydrc_feol] :221 |  |
| pwbm.4 | KLayout only | – | – | pwbm.4 – [FEOL; only in lydrc_feol] :222 |  |
| pwde.1 | KLayout only | – | pwde.1 0.84 [FEOL] :349 | – |  |
| pwde.2 | KLayout only | – | pwde.2 1.27 [FEOL] :356 | – |  |
| pwdem.3 | KLayout only | – | – | pwdem.3 – [FEOL; only in lydrc_feol] :225 |  |
| pwdem.4 | KLayout only | – | – | pwdem.4 – [FEOL; only in lydrc_feol] :226 |  |
| pwdem.5 | KLayout only | – | – | pwdem.5 – [FEOL; only in lydrc_feol] :227 |  |
| pwres.2 | KLayout only | – | – | pwres.2 2.65 [FEOL; only in lydrc_feol] :816,817 |  |
| pwres.3 | KLayout only | – | – | pwres.3 26.5 [FEOL; only in lydrc_feol] :818 |  |
| pwres.4 | KLayout only | – | – | pwres.4 265 [FEOL; only in lydrc_feol] :819 |  |
| pwres.5 | KLayout only | – | – | pwres.5 0.22 [FEOL; only in lydrc_feol] :820,821 |  |
| pwres.6 | KLayout only | – | – | pwres.6 0.53 [FEOL; only in lydrc_feol] :822,823 |  |
| pwres.8 | KLayout only | – | – | pwres.8 – [FEOL; only in lydrc_feol] :825,826 |  |
| rfdiode.1 | KLayout only | – | – | rfdiode.1 – [FEOL; only in lydrc_feol] :830 |  |
| rfdiode.2 | KLayout only | – | – | rfdiode.2 – [FEOL; only in lydrc_feol] :831 |  |
| rpm.1 | both | 1.27 [U] :4427 | rpm.1a 1.27 [FEOL] :517; urpm.1a 1.27 [FEOL] :536 | – |  |
| rpm.1a | KLayout only | – | – | rpm.1a 1.27 [FEOL; only in lydrc_feol] :307 |  |
| rpm.2 | both | 0.84 [U] :4428 | rpm.2 0.84 [FEOL] :521; urpm.2 0.84 [FEOL] :540 | rpm.2 0.84 [FEOL; only in lydrc_feol] :308 |  |
| rpm.3 | Magic only: sky130A.lydrc has it | in (rpm.7 + rpm.3) 0.4 [FU] :4354; in (rpm.3 + rpm.6 + nsd.5a) 0.525 [F] :4359; in (rpm.3 + rpm.7) 0.4 [F] :4361; in (rpm.3 + rpm.9 + hvntm.3) 0.585 [F] :4363; in (rpm.3 + rpm.6 + nsd.5a) 0.525 [U] :4371; in (rpm.3 + rpm.7) 0.4 [U] :4373; 1 more | – | rpm.3 0.2 [FEOL; only in lydrc_feol] :309 |  |
| rpm.4 | KLayout only | – | – | rpm.4 0.11 [FEOL; only in lydrc_feol] :310 |  |
| rpm.5 | KLayout only | – | – | rpm.5 0.095 [FEOL; only in lydrc_feol] :311 |  |
| rpm.6 | Magic only: only inside a composite rule; sky130A.lydrc has it | in (rpm.3 + rpm.6 + nsd.5a) 0.525 [F] :4359; in (rpm.3 + rpm.6 + nsd.5a) 0.525 [U] :4371 | – | rpm.6 0.2 [FEOL; only in lydrc_feol] :312 |  |
| rpm.7 | Magic only: sky130A.lydrc has it | in (rpm.7 + rpm.3) 0.4 [FU] :4354; in (rpm.3 + rpm.7) 0.4 [F] :4361; in (rpm.3 + rpm.7) 0.4 [U] :4373 | – | rpm.7 0.2 [FEOL; only in lydrc_feol] :313 |  |
| rpm.8 | KLayout only | – | – | rpm.8 – [FEOL; only in lydrc_feol] :314 |  |
| rpm.9 | Magic only: only inside a composite rule; sky130A.lydrc has it | in (rpm.3 + rpm.9 + hvntm.3) 0.585 [F] :4363; in (rpm.3 + rpm.9 + hvntm.3) 0.585 [U] :4375 | – | rpm.9 0.185 [FEOL; only in lydrc_feol] :315 |  |
| rpm.10 | KLayout only | – | – | rpm.10 – [FEOL; only in lydrc_feol] :316 |  |
| tap and diff | KLayout only | – | – | tap and diff – [FEOL; only in lydrc_feol] :356 |  |
| thkox.1 | KLayout only | – | thkox.1 0.6 [FEOL] :469 | – |  |
| thkox.2 | KLayout only | – | thkox.2 0.7 [FEOL] :473 | – |  |
| tunm.1 | KLayout only | – | tunm.1 0.41 [FEOL] :452 | tunm.1 0.41 [FEOL; only in lydrc_feol] :280 |  |
| tunm.2 | KLayout only | – | tunm.2 0.5 [FEOL] :456 | tunm.2 0.5 [FEOL; only in lydrc_feol] :281 |  |
| tunm.3 | KLayout only | – | – | tunm.3 0.095 [FEOL; only in lydrc_feol] :282 |  |
| tunm.4 | KLayout only | – | – | tunm.4 0.095 [FEOL; only in lydrc_feol] :283 |  |
| tunm.5 | KLayout only | – | – | tunm.5 – [FEOL; only in lydrc_feol] :284 |  |
| tunm.6a | Magic only: sky130A.lydrc has it | – [U] :4179 | – | tunm.6a – [FEOL; only in lydrc_feol] :285 |  |
| tunm.7 | KLayout only | – | – | tunm.7 0.672 µm² [FEOL; only in lydrc_feol] :286 |  |
| tunm.8 | Magic only | – [U] :4862 | – | – |  |
| uhvi.1 | KLayout only | – | – | uhvi.1 – [FEOL; only in lydrc_feol] :806,807 |  |
| uhvi.2 | KLayout only | – | – | uhvi.2 – [FEOL; only in lydrc_feol] :808 |  |
| uhvi.3 | KLayout only | – | – | uhvi.3 – [FEOL; only in lydrc_feol] :809 |  |
| uhvi.4 | KLayout only | – | – | uhvi.4 – [FEOL; only in lydrc_feol] :810 |  |
| uhvi.5 | KLayout only | – | – | uhvi.5 – [FEOL; only in lydrc_feol] :811 |  |
| uhvi.7 | KLayout only | – | – | uhvi.7 – [FEOL; only in lydrc_feol] :813 |  |
| varac.1 | Magic only: sky130A.lydrc has it | as var.1 0.18 [FU] :4876 | – | varac.1 0.18 [FEOL; only in lydrc_feol] :320 |  |
| varac.2 | Magic only: sky130A.lydrc has it | as var.2 1 [FU] :4877 | – | varac.2 1 [FEOL; only in lydrc_feol] :321 |  |
| varac.3 | Magic only: only inside a composite rule; sky130A.lydrc has it | in (hvtp.4 + varac.3) 0.36 [FU] :4390 | – | varac.3 0.18 [FEOL; only in lydrc_feol] :322 |  |
| varac.4 | Magic only | as var.4 0.25 [FU] :4870; as var.4 0.25 [FU] :4873 | – | – |  |
| varac.4 [sky130A.lydrc] | same name for another check: licon on tap to Var_channel 0.25 µm, the manual's varac.4 and the same check as licon.10; Magic's varac.4 (printed var.4) is the n-tap's extension past the varactor | – | – | varac.4 0.25 [FEOL; only in lydrc_feol] :323 |  |
| varac.5 | Magic only: sky130A.lydrc has it | 0.15 [U] :4880 | – | varac.5 0.15 [FEOL; only in lydrc_feol] :324 |  |
| varac.6 | KLayout only | – | – | varac.6 0.27 [FEOL; only in lydrc_feol] :325 |  |
| varac.7 | Magic only: sky130A.lydrc has it | – [U] :4883 | – | varac.7 – [FEOL; only in lydrc_feol] :326 |  |
| vhvi.1 | KLayout only | – | – | vhvi.1 0.02 [FEOL; only in lydrc_feol] :786 |  |
| vhvi.2 | KLayout only | – | – | vhvi.2 – [FEOL; only in lydrc_feol] :787 |  |
| vhvi.3 | KLayout only | – | – | vhvi.3 – [FEOL; only in lydrc_feol] :788 |  |
| vhvi.5 | KLayout only | – | – | vhvi.5 – [FEOL; only in lydrc_feol] :790,791 |  |
| vhvi.7 | KLayout only | – | – | vhvi.7 – [FEOL; only in lydrc_feol] :792 |  |
| via1.5b | KLayout only | – | – | via1.5b 0.06 [BEOL & backend_flow = AL] :514 |  |
| via.1a | both | in (via.1a + 2 * via.4a) 0.26 [FUR] :4630 | via.1a – [BEOL & backend_flow = AL] :1075; via.1a_a 0.15 [BEOL & backend_flow = AL] :1079; via.1a_b 0.15 [BEOL & backend_flow = AL] :1084 | via.1a 0.15 [BEOL & backend_flow = AL] :504 | s_via_014: Magic FUR, KLayout harness,lydrc,lydrc_feol,menu; s_via_016: Magic no, KLayout harness,lydrc,lydrc_feol,menu |
| via.1b | KLayout only | – | – | via.1b 0.28 [BEOL & backend_flow = AL] :505 |  |
| via.2 | both | in (via.2 - 2 * via.4a) 0.06 [FUR] :4631 | via.2 0.17 [BEOL & backend_flow = AL] :1089 | via.2 0.17 [BEOL & backend_flow = AL] :506 | s_via_space: Magic FUR, KLayout harness,lydrc,lydrc_feol,menu |
| via.3 | KLayout only | – | via.3 0.2 [BEOL & backend_flow = AL & SEAL; only in menu] :1095; via.3_a 0.205 [BEOL & backend_flow = AL & SEAL; only in menu] :1099; via.3_b – [BEOL & backend_flow = AL & SEAL; only in menu] :1103 | – |  |
| via.4a | folded: Magic checks it only inside a composite rule | in (via.1a + 2 * via.4a) 0.26 [FUR] :4630; in (via.2 - 2 * via.4a) 0.06 [FUR] :4631; in (via.5a - via.4a) 0.03 [FUR] :4632 | via.4a 0.055 [BEOL & backend_flow = AL] :1112; via.4a_a 0.15 [BEOL & backend_flow = AL] :1117 | via.4a 0.055 [BEOL & backend_flow = AL] :507 | s_via_m1_encl: Magic FUR, KLayout harness,lydrc,lydrc_feol,menu |
| via.4b | KLayout only | – | – | via.4b 0.03 [BEOL & backend_flow = AL] :508 |  |
| via.4c.5c | KLayout only | – | – | via.4c.5c – [BEOL] :502 |  |
| via.5a | both | in (via.5a - via.4a) 0.03 [FUR] :4632 | via.5a 0.085 [BEOL & backend_flow = AL] :1127 | via1.5a 0.085 [BEOL & backend_flow = AL] :511 | s_via_m1_adj: Magic FUR, KLayout harness,lydrc,lydrc_feol,menu |
| vpp.1 | KLayout only | – | – | vpp.1 1.43 [FEOL; only in lydrc_feol] :400 |  |
| vpp.3 | KLayout only | – | – | vpp.3 – [FEOL; only in lydrc_feol] :402 |  |
| vpp.4 | KLayout only | – | – | vpp.4 – [FEOL; only in lydrc_feol] :403,404 |  |
| vpp.5 | KLayout only | – | – | vpp.5 1.5 [FEOL; only in lydrc_feol] :405 |  |
| vpp.5a | KLayout only | – | – | vpp.5a 0.25 [FEOL; only in lydrc_feol] :406 |  |
| vpp.5b | KLayout only | – | – | vpp.5b 0.3 [FEOL; only in lydrc_feol] :407 |  |
| vpp.5c | KLayout only | – | – | vpp.5c 0.4 [FEOL; only in lydrc_feol] :408 |  |
| vpp.8 | KLayout only | – | – | vpp.8 1.5 [FEOL; only in lydrc_feol] :409 |  |
| vpp.9 | KLayout only | – | – | vpp.9 1.5 [FEOL; only in lydrc_feol] :410 |  |
| x.1b | KLayout only | – | 38 names, e.g. areaid_re_OFFGRID, ct_OFFGRID, diff_OFFGRID :1498-1607 | 38 names, e.g. areaid_re_OFFGRID, ct_OFFGRID, diff_OFFGRID :839-915 |  |
| x.2 | in the deck, did not fire on its case: KLayout reported nothing on d_diff_45, d_diff_45b, s_li_45deg | 90 [FU] :4314; 90 [FU] :4380; 90 [FUR] :4584; 45 [FUR] :4585 | 9 names, e.g. ct_angle, diff_angle, licon_angle :1528-1581 | 9 names, e.g. ct_angle, diff_angle, licon_angle :857-898 | d_diff_45: Magic FU, KLayout no; d_diff_45b: Magic FU, KLayout no; s_li_45deg: Magic FUR, KLayout no |
| x.3a | in the deck, did not fire on its case: KLayout reported nothing on s_m1_30deg, s_m1_30deg_b | 45 [FUR] :4610; 45 [FUR] :4648; 45 [FUR] :4686; 45 [FUR] :4722; 45 [FUR] :4753 | 28 names, e.g. dnwell_angle, hvi_angle, hvntm_angle :1502-1603 | 28 names, e.g. dnwell_angle, hvi_angle, hvntm_angle :840-914 | s_m1_30deg: Magic FUR, KLayout no; s_m1_30deg_b: Magic FUR, KLayout no |

## Rules only one side reported in a test

Each line gives a rule and the cases, controls left out, on which one engine reported it and the other did not. Magic's side is any of its styles; KLayout's side is `sky130A_mr.drc`.

### Reported by Magic and not by sky130A_mr.drc

- `diff/tap.2`: c_licon_gate, d_gate_w036
- `diff/tap.3`: d_nsdm_half
- `diff/tap.4`: e_butt_short
- `diff/tap.8`: a_no_nsdm, d_nsdm_half, w_nwell_encl_pdiff
- `diff/tap.9`: d_nsdm_half, w_ndiff_to_nwell
- `diff/tap.10`: w_no_nwell, w_nwell_encl_ntap
- `diff/tap.11`: w_no_nwell
- `hvtp.4`: i_hvtp_half
- `li.3`: l_no_li_under_mcon
- `li.6`: l_no_li_under_mcon, s_mcon_no_li
- `li.c2`: l_no_li_under_mcon
- `licon.1`: c_licon_out
- `licon.5a`: c_licon_out, c_ndiff_encl0
- `licon.5b`: e_butt_licon5b
- `licon.7`: c_tap_encl, d_both_implants
- `licon.8`: a_licon8
- `licon.8a`: a_licon8
- `licon.9`: c_pc_to_pdiff
- `licon.11`: c_licon11_li, c_licon_gate
- `licon.14`: c_pc_to_diff
- `LU.2`: w_no_ptap, w_no_ptap_licon
- `LU.3`: a_no_nsdm, d_nsdm_half, w_no_ntap, w_no_ntap_licon
- `lvtn.3a`: e_lvtn_half
- `met1.3a`: s_m1_wide_space
- `met2.5`: s_via_no_m2
- `nsd.10b`: e_ntap_area
- `nwell.1`: a_no_nsdm, d_nsdm_half, w_no_nwell, w_nwell_encl_pdiff
- `nwell.2a`: a_no_nsdm, d_nsdm_half, s_ptap_to_nwell
- `nwell.4`: a_no_nsdm, d_nsdm_half, w_no_ntap, w_no_ntap_licon, w_no_nwell
- `poly.1a`: c_licon_gate
- `poly.1b`: e_pfet_lvt
- `poly.4`: p_field_to_diff
- `poly.5`: p_poly_to_tap, w_no_nwell
- `poly.7`: d_nsdm_half, d_sd_020
- `poly.8`: a_poly8
- `poly.11`: e_bent_gate
- `psd.10b`: d_both_implants, d_tap_area
- `via.4a`: s_via_014, s_via_m1_adj, s_via_space
- `via.5a`: s_via_m1_encl
- `x.2`: d_diff_45, d_diff_45b, s_li_45deg
- `x.3a`: s_m1_30deg, s_m1_30deg_b

### Reported by KLayout and not by Magic

- `ct.4`: l_no_li_under_mcon, s_mcon_no_li
- `hvtp.1`: i_hvtp_w030, s_hvtp_alone
- `licon.1`: c_licon_020
- `licon.13`: c_npc_over_dlicon
- `licon.17`: c_licon_gate
- `lvtn.1a`: i_lvtn_straddle, s_lvtn_alone
- `met1.1`: s_m1_30deg, s_m1_30deg_b
- `met1.3a`: s_m1_huge_space
- `met1.7`: s_m1_hole, s_m1_hole_boxes
- `MR_lvtn.OVL.2`: i_lvtn_straddle
- `npc.1`: c_npc_narrow, s_npc_alone
- `nsdm.2`: i_nsdm_narrow, s_nsdm_alone
- `nsdm_psdm_overlap`: d_both_implants
- `psdm.1`: d_both_implants, i_psdm_space
- `via.1a`: s_via_016
- `x.1b`: s_m1_offgrid
