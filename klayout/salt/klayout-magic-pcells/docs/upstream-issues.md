# Upstream issues

This page lists problems in the PDKs' Magic tech files, in their KLayout DRC
decks and in Magic itself. None of the 18 issues below has been filed yet.
They were found for version 0.6.1, when the rows of the [gap
tables](gaps/README.md) on which Magic and KLayout disagreed were checked
against the foundries' published rules: SkyWater's rule pages in
google/skywater-pdk at commit 7198cf6, GF's design rules in
google/gf180mcu-pdk at commit de3240d, Rev. 0.4 of IHP's SG13G2 Layout Rules
and Rev. 0.1 of IHP's SG13CMOS5L Layout Rules. Each entry gives the rule,
the manual's value against the tool's where the two differ, the upstream
file and line, and what goes wrong. Every entry has a drafted issue with a
small repro; the drafts and their repros are not in this repository.

The problems were seen with Magic 8.3.681 and KLayout 0.30.11 in the pinned
image (`hpretl/iic-osic-tools:2026.08`, with open_pdks 026824c7). No newer
Magic was run. The Magic cases for the IHP PDKs were also run with the tech
files at IHP-Open-PDK e73adb4, with the same results as with the image's
copies. Each entry was checked against one of the upstream commits below,
and its line numbers and links are for that commit; if a branch has moved by
the time an issue is filed, the lines need checking again. The Magic line
numbers in the gap tables are not the ones given here: open_pdks 026824c7
installs one `sky130A.tech` and one `gf180mcuD.tech`, and in open-pdks the
Magic tech files were split into `-drc`, `-cifout` and `-cifin` files on
2026-11-04 (bb8c82e).

| Repository | Commit | Note |
|---|---|---|
| fossi-foundation/open-pdks | `main` 2fdf40d (2026-11-20) | |
| IHP-GmbH/IHP-Open-PDK | `main` e73adb4 (2026-11-10) | `dev` 4c4880d has the same Magic files and the same DRC deck files for everything cited; entry 14 cites PR #885 at its head, 8cccf42 |
| RTimothyEdwards/magic | `master` 1d42dfc (8.3.706) | |
| chipfoundry/cf-precheck | `main` 9ed3121 | MR deck release 2026.03.30_01.00 |
| fossi-foundation/sky130_klayout_pdk | 4ea0975 | MR deck release 2025.11.17_01.10 |
| fossi-foundation/mpw_precheck | 86b7362 | MR deck release 2024.2.11_01.09, the copy that open_pdks installs |
| fossi-foundation/globalfoundries-pdk-libs-gf180mcu_fd_pv | `main` 0df548b | open_pdks 026824c7 pins e766ad1, which has the same PL.6 lines |

## fossi-foundation/open-pdks

This repository holds the sky130 and gf180mcu Magic tech files, the old
`sky130.lydrc` deck and the Makefile that installs the sky130 KLayout decks.
`RTimothyEdwards/open_pdks` redirects to it.

### 1. gf180mcu Magic DRC: six rule values differ from the design manual

Kind: bug. Status: not filed.

| Rule | Manual | Magic | Upstream |
|---|---|---|---|
| DF.6, COMP past the gate (source and drain) | [0.24 µm for 3.3 V and 0.40 µm for 5 V and 6 V](https://github.com/google/gf180mcu-pdk/blob/de3240d7529a6970437ac3344820aaae7839f215/docs/physical_verification/design_manual/tables_clear/14_COMP33_1.csv?plain=1#L17), [0.32 µm](https://github.com/google/gf180mcu-pdk/blob/de3240d7529a6970437ac3344820aaae7839f215/docs/physical_verification/design_manual/tables_clear/48_SRAM1_126.csv?plain=1#L5) for the 5 V SRAM (S.DF.6_MV) | 0.23 µm for all of them | [gf180mcu-drc.tech#L182-L189](https://github.com/fossi-foundation/open-pdks/blob/2fdf40d5736413bb321c31418462aefc17b919b8/gf180mcu/magic/gf180mcu-drc.tech#L182-L189) |
| NAT.4 and NAT.5, native NMOS channel length, 3.3 V and 6 V | [1.8 µm](https://github.com/google/gf180mcu-pdk/blob/de3240d7529a6970437ac3344820aaae7839f215/docs/physical_verification/design_manual/tables_clear/36_Native_Vt_NMOS_90.csv?plain=1#L6-L9) | 0.4 µm, labelled DF.2c, and 1.2 µm, labelled NAT.4 | [gf180mcu-drc.tech#L602-L604](https://github.com/fossi-foundation/open-pdks/blob/2fdf40d5736413bb321c31418462aefc17b919b8/gf180mcu/magic/gf180mcu-drc.tech#L602-L604) |
| NAT.1, NAT overlap of native COMP | [2 µm](https://github.com/google/gf180mcu-pdk/blob/de3240d7529a6970437ac3344820aaae7839f215/docs/physical_verification/design_manual/tables_clear/36_Native_Vt_NMOS_90.csv?plain=1#L3) | the NAT layer that Magic writes reaches 0.26 µm past COMP; no DRC check | [gf180mcu-cifout.tech#L264-L270](https://github.com/fossi-foundation/open-pdks/blob/2fdf40d5736413bb321c31418462aefc17b919b8/gf180mcu/magic/gf180mcu-cifout.tech#L264-L270) |
| MT.4, MetalTop area, gf180mcuC and gf180mcuD | [0.5625 µm²](https://github.com/google/gf180mcu-pdk/blob/de3240d7529a6970437ac3344820aaae7839f215/docs/physical_verification/design_manual/tables_clear/24_MetalTop_61.csv?plain=1#L11) | 0.5265 µm² | [gf180mcu-drc.tech#L498](https://github.com/fossi-foundation/open-pdks/blob/2fdf40d5736413bb321c31418462aefc17b919b8/gf180mcu/magic/gf180mcu-drc.tech#L498) |
| Mn.3 on Metal4 (M4.3), and on Metal5 in the `METALS6` branch, which no shipped variant uses | [0.1444 µm²](https://github.com/google/gf180mcu-pdk/blob/de3240d7529a6970437ac3344820aaae7839f215/docs/physical_verification/design_manual/tables_clear/22_Metaln_58.csv?plain=1#L10) | 0.144 µm² | [#L456](https://github.com/fossi-foundation/open-pdks/blob/2fdf40d5736413bb321c31418462aefc17b919b8/gf180mcu/magic/gf180mcu-drc.tech#L456), [#L525](https://github.com/fossi-foundation/open-pdks/blob/2fdf40d5736413bb321c31418462aefc17b919b8/gf180mcu/magic/gf180mcu-drc.tech#L525) |
| S.CO.4_LV, COMP overlap of contact, 3.3 V SRAM | [0.03 µm](https://github.com/google/gf180mcu-pdk/blob/de3240d7529a6970437ac3344820aaae7839f215/docs/physical_verification/design_manual/tables_clear/48_SRAM3_128.csv?plain=1#L6-L7) | 0.04 µm from the cut, labelled S.CO.3_LV | [gf180mcu-drc.tech#L266-L269](https://github.com/fossi-foundation/open-pdks/blob/2fdf40d5736413bb321c31418462aefc17b919b8/gf180mcu/magic/gf180mcu-drc.tech#L266-L269) |

Five of the six values let through layouts that break the manual. S.CO.4_LV
flags a legal layout instead. Magic's contact tile is the cut plus 0.005 µm
on each side, so its 0.035 µm on the tile is 0.04 µm on the cut, the value
of the Poly2 rule S.CO.3_LV. The commit message of
[#562](https://github.com/fossi-foundation/open-pdks/pull/562) (merged Oct
22) says that Magic's DRC does not catch the 5 V and 6 V DF.6 violations and
leaves the missing rules for a future PR; this issue would be the DF.6 part
of that follow-up, with the 3.3 V and SRAM values added. The repro draws one
small cell per rule with a value between the manual's and Magic's, plus
controls that show Magic's limit, and reads the NAT layer back from the GDS
that Magic writes. Moving the NAT grow to 2 µm would also need the 0.61 µm
spacing from native diffusion to tap
([#L160-L161](https://github.com/fossi-foundation/open-pdks/blob/2fdf40d5736413bb321c31418462aefc17b919b8/gf180mcu/magic/gf180mcu-drc.tech#L160-L161))
to grow with it.

In the [gf180mcuD gap table](gaps/gf180mcuD.md#wells-to-via1), DF.6, NAT.4,
NAT.5 and S.CO.4 are "both, values differ" with these values, and so are
MT.4 and M4.3 under [Upper metals, vias and
MIM](gaps/gf180mcuD.md#upper-metals-vias-and-mim). The DF.6 row has no SRAM
value; S.DF.6 is a row of its own, KLayout only.

### 2. gf180mcu Magic DRC: messages that cite the wrong rule ID

Kind: bug, in the messages only; the values checked are right. Status: not
filed. File it after entry 1, and put entry 1's issue number where this one
mentions lines 602 and 604.

| Lines in `gf180mcu-drc.tech` | Check | Magic's ID | Manual's ID |
|---|---|---|---|
| [652](https://github.com/fossi-foundation/open-pdks/blob/2fdf40d5736413bb321c31418462aefc17b919b8/gf180mcu/magic/gf180mcu-drc.tech#L652) | Poly2 resistor width, 1 µm | HRES.3 | HRES.2 |
| [653-654](https://github.com/fossi-foundation/open-pdks/blob/2fdf40d5736413bb321c31418462aefc17b919b8/gf180mcu/magic/gf180mcu-drc.tech#L653-L654) | space between Poly2 resistors, 0.4 µm | HRES.2 | HRES.3 |
| [662-665](https://github.com/fossi-foundation/open-pdks/blob/2fdf40d5736413bb321c31418462aefc17b919b8/gf180mcu/magic/gf180mcu-drc.tech#L662-L665) | salicide block to contact on the resistor, 0.22 µm | PRES/LRES/HRES.7 | PRES.7 and LRES.7 are right; the high-R resistor's rule is HRES.8, and HRES.7 is the Pplus overlap of contact |
| [94-97](https://github.com/fossi-foundation/open-pdks/blob/2fdf40d5736413bb321c31418462aefc17b919b8/gf180mcu/magic/gf180mcu-drc.tech#L94-L97) | n-diffusion to N-well, 0.43 and 0.6 µm | DF.8 | DF.16 |
| [102-105](https://github.com/fossi-foundation/open-pdks/blob/2fdf40d5736413bb321c31418462aefc17b919b8/gf180mcu/magic/gf180mcu-drc.tech#L102-L105) | p-ohmic to N-well, 0.12 and 0.16 µm | DF.5 | DF.17 |
| [108-111](https://github.com/fossi-foundation/open-pdks/blob/2fdf40d5736413bb321c31418462aefc17b919b8/gf180mcu/magic/gf180mcu-drc.tech#L108-L111) | N-well overlap of n-ohmic, 0.12 and 0.16 µm | DF.4a | DF.4d |
| [112-115](https://github.com/fossi-foundation/open-pdks/blob/2fdf40d5736413bb321c31418462aefc17b919b8/gf180mcu/magic/gf180mcu-drc.tech#L112-L115) | N-well overlap of p-diffusion, 0.43 and 0.6 µm | DF.7 | DF.4c |
| [116-117](https://github.com/fossi-foundation/open-pdks/blob/2fdf40d5736413bb321c31418462aefc17b919b8/gf180mcu/magic/gf180mcu-drc.tech#L116-L117) | the same, 5 V SRAM, 0.45 µm | S.DF.7_MV | S.DF.4c_MV |
| [98-99](https://github.com/fossi-foundation/open-pdks/blob/2fdf40d5736413bb321c31418462aefc17b919b8/gf180mcu/magic/gf180mcu-drc.tech#L98-L99) | n-diffusion to N-well, 5 V SRAM, 0.45 µm | S.DF.8_MV | S.DF.16_MV |

Manual:
[HRES](https://github.com/google/gf180mcu-pdk/blob/de3240d7529a6970437ac3344820aaae7839f215/docs/physical_verification/design_manual/tables_clear/33_ANALOG_DEVICE3_84.csv?plain=1#L4-L10),
[DF](https://github.com/google/gf180mcu-pdk/blob/de3240d7529a6970437ac3344820aaae7839f215/docs/physical_verification/design_manual/tables_clear/14_COMP33_1.csv?plain=1#L11-L19)
and [5 V
SRAM](https://github.com/google/gf180mcu-pdk/blob/de3240d7529a6970437ac3344820aaae7839f215/docs/physical_verification/design_manual/tables_clear/48_SRAM1_126.csv?plain=1#L4-L8)
tables.

In the current COMP table, DF.4a, DF.5, DF.7 and DF.8 are the LVPWELL rules
inside DNWELL, and the file already uses DF.5 and DF.8 that way at lines
141-148, so each of those two IDs labels two different checks. The manual's
revision table shows that the DF rules were renumbered at some point, and
Magic's IDs may come from an older revision. The repro draws a high-R
resistor body 0.9 µm wide, which Magic reports as HRES.3. The issue also
lists IDs that could not be matched to the current manual: NAT.6 on a 0.35
µm poly overhang of the native transistor (line 191; the current NAT.6 is a
different rule), "NAT.5 + NAT.6" on a 0.61 µm spacing (lines 160-161), DF.2c
on line 605, and "NP.4b + PP.4c" and "PP.4b + NP.4c" on lines 630-635 (the
tables have no NP.4c or PP.4c).

The [gf180mcuD gap table](gaps/gf180mcuD.md#wells-to-via1) files these rows
under the manual's IDs, with Magic's ID after `as` in the Magic column, for
example HRES.2 `as HRES.3`.

### 3. sky130 Magic DRC: licon.16 can never fire

Kind: bug. Status: not filed.

licon.16: [every source_diff and every tap must enclose at least one
licon1](https://github.com/google/skywater-pdk/blob/7198cf647113f56041e02abf3eb623692820c5e1/docs/rules/periphery-rules.rst?plain=1#L1666-L1671),
with no value. Magic checks the tap half with `cifmaxwidth tap_missing_licon
0`, in `drc(full)` only:
[sky130-drc.tech#L166-L167](https://github.com/fossi-foundation/open-pdks/blob/2fdf40d5736413bb321c31418462aefc17b919b8/sky130/magic/sky130-drc.tech#L166-L167),
with the templayers at
[sky130-cifout.tech#L1060-L1065](https://github.com/fossi-foundation/open-pdks/blob/2fdf40d5736413bb321c31418462aefc17b919b8/sky130/magic/sky130-cifout.tech#L1060-L1065).

`tap_with_licon` is built with `bloat-all` from `allpactivetap` and
`allnactivetap`, and those type lists include the tap types themselves, so
every tap seeds itself into `tap_with_licon` and `tap_missing_licon` is
always empty. The repro draws a 0.6 × 0.6 µm p-tap with no licon, which
Magic passes, next to the same tap with a licon. Seeding from the tap
contacts, as the N-well check above it does, makes the rule fire on the bare
tap and not on the contacted one; that change was tried on those two cells
only.

The licon.16 row of the [sky130A gap
table](gaps/sky130A.md#front-end-li-mcon-met1-via1) notes that Magic
reported nothing on its two cases.

### 4. sky130 Magic DRC: the nsd.10b/psd.10b tap-area check flags legal minimum-size taps

Kind: bug. Status: not filed.

n/psd.10a and n/psd.10b: [minimum area of nsdm, 0.265 µm², and of psdm,
0.255
µm²](https://github.com/google/skywater-pdk/blob/7198cf647113f56041e02abf3eb623692820c5e1/docs/rules/periphery-rules.rst?plain=1#L1495-L1504).
Magic checks the area of the tap instead, against 0.07011 µm² for both
n-taps and p-taps, labelled nsd.10b and psd.10b:
[sky130-drc.tech#L161-L162](https://github.com/fossi-foundation/open-pdks/blob/2fdf40d5736413bb321c31418462aefc17b919b8/sky130/magic/sky130-drc.tech#L161-L162).

Magic writes nsdm and psdm itself, as the tap grown by 0.125 µm and merged
with nearby implant. The value 0.07011 µm² is (√0.265 − 0.25)², the area of
a square tap whose grown implant is exactly 0.265 µm², so the check is exact
only for square taps. A minimum contacted tap, 0.41 × 0.17 µm (0.0697 µm²),
gets 0.66 × 0.42 µm of implant (0.2772 µm²); the implant passes both rules,
but the tap fails the tap-area check. The p-tap line also reuses the n-side
number (a psdm-based value would be about 0.0650 µm²), and the n-side
message should say nsd.10a. The repro draws that tap as a p-tap and as an
n-tap, and a 0.15 × 0.15 µm p-tap that is too small; a `cifarea` check on
the implant that Magic writes, as the gf180mcu file does for NPLUS and
PPLUS, was tried on those three cells. It passes the two minimum taps and
still flags the small one.

The nsd.10b and psd.10b rows of the [sky130A gap
table](gaps/sky130A.md#front-end-li-mcon-met1-via1) note that Magic checks
the tap's area.

### 5. sky130 Magic DRC: messages that cite another rule's ID

Kind: bug, in the messages only; the values look right. Status: not filed.
File it after entry 4, and put entry 4's issue number where this one points
to the issue about the tap-area check.

| Lines in `sky130-drc.tech` | Check | Magic's ID | Periphery rules |
|---|---|---|---|
| [116-117](https://github.com/fossi-foundation/open-pdks/blob/2fdf40d5736413bb321c31418462aefc17b919b8/sky130/magic/sky130-drc.tech#L116-L117) | HVI to HVI spacing, 0.700 µm | hvi.5 | [hvi.2a](https://github.com/google/skywater-pdk/blob/7198cf647113f56041e02abf3eb623692820c5e1/docs/rules/periphery-rules.rst?plain=1#L3241-L3245); [hvi.5](https://github.com/google/skywater-pdk/blob/7198cf647113f56041e02abf3eb623692820c5e1/docs/rules/periphery-rules.rst?plain=1#L3256-L3260) is HVI to nwell, checked at lines 118-119 |
| [114-115](https://github.com/fossi-foundation/open-pdks/blob/2fdf40d5736413bb321c31418462aefc17b919b8/sky130/magic/sky130-drc.tech#L114-L115) | MV diffusion to LV nwell, 0.825 µm | hvi.5 + nsd/psd.5 | there is no n/psd.5; the enclosure rules are [n/psd.5a and n/psd.5b](https://github.com/google/skywater-pdk/blob/7198cf647113f56041e02abf3eb623692820c5e1/docs/rules/periphery-rules.rst?plain=1#L1461-L1470), 0.125 µm; 0.7 + 0.125 = 0.825, but whether that is the right composite was not checked |
| [153](https://github.com/fossi-foundation/open-pdks/blob/2fdf40d5736413bb321c31418462aefc17b919b8/sky130/magic/sky130-drc.tech#L153) | LDNFET and LDPFET width, 5.000 µm | denmos/depmos.2 | [denmos.7](https://github.com/google/skywater-pdk/blob/7198cf647113f56041e02abf3eb623692820c5e1/docs/rules/periphery-rules.rst?plain=1#L3556-L3560) and [depmos.7](https://github.com/google/skywater-pdk/blob/7198cf647113f56041e02abf3eb623692820c5e1/docs/rules/periphery-rules.rst?plain=1#L3652-L3656); denmos.2 and depmos.2 are the 0.280 µm source width, for which no check was found |
| [747](https://github.com/fossi-foundation/open-pdks/blob/2fdf40d5736413bb321c31418462aefc17b919b8/sky130/magic/sky130-drc.tech#L747) | varactor length, 0.180 µm | var.1 | [varac.1](https://github.com/google/skywater-pdk/blob/7198cf647113f56041e02abf3eb623692820c5e1/docs/rules/periphery-rules.rst?plain=1#L1263-L1267) |
| [748](https://github.com/fossi-foundation/open-pdks/blob/2fdf40d5736413bb321c31418462aefc17b919b8/sky130/magic/sky130-drc.tech#L748) | varactor width, 1.000 µm | var.2 | [varac.2](https://github.com/google/skywater-pdk/blob/7198cf647113f56041e02abf3eb623692820c5e1/docs/rules/periphery-rules.rst?plain=1#L1268-L1272) |
| [741-745](https://github.com/fossi-foundation/open-pdks/blob/2fdf40d5736413bb321c31418462aefc17b919b8/sky130/magic/sky130-drc.tech#L741-L745) | N-tap overhang of varactor, 0.250 µm | var.4 | [varac.4](https://github.com/google/skywater-pdk/blob/7198cf647113f56041e02abf3eb623692820c5e1/docs/rules/periphery-rules.rst?plain=1#L1278-L1282) is the spacing from licon on tap to the varactor channel, which lines 334-337 check as licon.10 |

The repro draws a varactor 0.15 µm long, which Magic reports as var.1. The
nsd.10b label on the n-tap area check, nsd.10a in the manual, belongs to
entry 4.

The [sky130A gap table](gaps/sky130A.md#front-end-li-mcon-met1-via1) files
these rows under SkyWater's IDs, with Magic's after `as`: hvi.2a `as hvi.5`,
varac.1, varac.2 and varac.4 `as var.1`, `as var.2` and `as var.4`, and
denmos.7 and depmos.7 `as denmos/depmos.2`.

### 6. sky130: open_pdks installs the 2024 MR deck from mpw_precheck

Kind: bug. Status: not filed.

licon.9: [spacing, no overlap, between poly licon and psdm, 0.110
µm](https://github.com/google/skywater-pdk/blob/7198cf647113f56041e02abf3eb623692820c5e1/docs/rules/periphery-rules.rst?plain=1#L1611-L1615).
The MR deck that open_pdks installs has no licon.9 check; the maintained
copies check it as `MR_licon.SP.6`. The installed deck is copied at
[sky130/Makefile.in#L1223-L1225](https://github.com/fossi-foundation/open-pdks/blob/2fdf40d5736413bb321c31418462aefc17b919b8/sky130/Makefile.in#L1223-L1225).

`sky130/sky130.json` pins `precheck_sky130` to mpw_precheck 86b7362, whose
deck is release 2024.2.11_01.09 and last changed on 2024-09-01. It also pins
`klayout_sky130` to sky130_klayout_pdk 4ea0975, whose
`tech/sky130/drc/README.md` calls that repository's 2025.11.17_01.10 deck
"the DRC deck that is currently actively maintained". The Makefile copies
other parts of that repository and not `tech/sky130/drc`, so an install has
none of the newer decks' changes, among them renamed rules, a licon bar
spacing that was changed "per feedback from SWT", and added checks such as
licon.9. The repro draws a poly licon 0.065 µm from psdm; the installed deck
reports nothing, and the sky130_klayout_pdk and cf-precheck decks report
`MR_licon.SP.6`. The suggested change is to copy the deck from
`KLAYOUT_PATH`.

The [sky130A gap table](gaps/sky130A.md#front-end-li-mcon-met1-via1), whose
KLayout side is the installed deck, has licon.9 as Magic only.

### 7. sky130A.lydrc: rule errors against the periphery rules

Kind: bug for items 1 to 7, question for items 8 and 9. Status: not filed.

Lines are in
[sky130/klayout/sky130.lydrc](https://github.com/fossi-foundation/open-pdks/blob/2fdf40d5736413bb321c31418462aefc17b919b8/sky130/klayout/sky130.lydrc),
which has not changed since 826ea67 (2022-06-06).

1. The x.2 and x.3a angle checks ([n × 90° and n ×
   45°](https://github.com/google/skywater-pdk/blob/7198cf647113f56041e02abf3eb623692820c5e1/docs/rules/periphery-rules.rst?plain=1#L138-L174))
   call `with_angle` on polygon layers, which selects corners rather than
   edges: x.2 reports only corners under 90° and x.3a only corners under
   45°, so 45° chamfers, 45° jogs and 30° edges on metal pass ([lines
   840-914](https://github.com/fossi-foundation/open-pdks/blob/2fdf40d5736413bb321c31418462aefc17b919b8/sky130/klayout/sky130.lydrc#L840-L914)).
   poly.11 (line 300), capm.7 (line 426) and rfdiode.1 (line 830) use the
   same call, and an L-shaped capm passes capm.7.
2. li1 is checked as an x.3a layer ([line
   876](https://github.com/fossi-foundation/open-pdks/blob/2fdf40d5736413bb321c31418462aefc17b919b8/sky130/klayout/sky130.lydrc#L876)),
   where x.2 puts periphery li1 among the 90° layers.
3. poly.11, [no 90° turns of poly on
   diff](https://github.com/google/skywater-pdk/blob/7198cf647113f56041e02abf3eb623692820c5e1/docs/rules/periphery-rules.rst?plain=1#L1092-L1096),
   cannot fire: `gate.with_angle(0 .. 90)` selects neither the 90° nor the
   270° corners of a gate that turns ([line
   300](https://github.com/fossi-foundation/open-pdks/blob/2fdf40d5736413bb321c31418462aefc17b919b8/sky130/klayout/sky130.lydrc#L300)).
4. n/psdm.5a, [0.125 µm enclosure of
   diff](https://github.com/google/skywater-pdk/blob/7198cf647113f56041e02abf3eb623692820c5e1/docs/rules/periphery-rules.rst?plain=1#L1461-L1465),
   misses an nsdm drawn equal to the diff, because `.polygons` drops the
   zero-width edge pairs that `enclosing` reports for coincident edges
   ([line
   350](https://github.com/fossi-foundation/open-pdks/blob/2fdf40d5736413bb321c31418462aefc17b919b8/sky130/klayout/sky130.lydrc#L350)).
5. licon.13, [0.090 µm from npc with no
   overlap](https://github.com/google/skywater-pdk/blob/7198cf647113f56041e02abf3eb623692820c5e1/docs/rules/periphery-rules.rst?plain=1#L1651-L1655),
   checks the spacing and not a licon inside npc ([line
   390](https://github.com/fossi-foundation/open-pdks/blob/2fdf40d5736413bb321c31418462aefc17b919b8/sky130/klayout/sky130.lydrc#L390)).
6. n/psdm.10b checks psdm against 0.265 µm², the nsdm value; the [psdm
   rule](https://github.com/google/skywater-pdk/blob/7198cf647113f56041e02abf3eb623692820c5e1/docs/rules/periphery-rules.rst?plain=1#L1500-L1504)
   is 0.255 µm² ([line
   358](https://github.com/fossi-foundation/open-pdks/blob/2fdf40d5736413bb321c31418462aefc17b919b8/sky130/klayout/sky130.lydrc#L358)).
7. licon.9 is not coded ([line
   379](https://github.com/fossi-foundation/open-pdks/blob/2fdf40d5736413bb321c31418462aefc17b919b8/sky130/klayout/sky130.lydrc#L379)).
8. Question: difftap.4,
   [0.290](https://github.com/google/skywater-pdk/blob/7198cf647113f56041e02abf3eb623692820c5e1/docs/rules/periphery-rules.rst?plain=1#L895-L899),
   is measured along the edge that the tap shares with the diffusion, where
   the periphery figure measures the tap's depth away from it ([line
   269](https://github.com/fossi-foundation/open-pdks/blob/2fdf40d5736413bb321c31418462aefc17b919b8/sky130/klayout/sky130.lydrc#L269)).
9. Question: capm.11's message says 0.5 µm and the code uses 0.14 µm ([line
   434](https://github.com/fossi-foundation/open-pdks/blob/2fdf40d5736413bb321c31418462aefc17b919b8/sky130/klayout/sky130.lydrc#L434)),
   and the capm checks use m2, where capm sits on met3 on sky130A
   ([google/skywater-pdk#262](https://github.com/google/skywater-pdk/issues/262)
   reports that the capm table names the wrong metal layers).

open_pdks still installs this file as `sky130A.lydrc`, although
`sky130/klayout/README` calls the files there deprecated and
[#307](https://github.com/fossi-foundation/open-pdks/issues/307) says that
nobody would claim responsibility for maintaining it, so the issue asks for
it to be fixed or no longer installed. Line 46 sets `FEOL = false`, so
capm.7, rfdiode.1 and the checks of items 3 to 6, 8 and 9 run only after
editing the file. The test in `if backend_flow = AL` is an assignment, so
the AL blocks always run and the CU blocks never do. The repros are two GDS
files, one with the eight angle shapes of entry 16 and one with single-rule
cases for capm.7 and items 3 to 8. On the second file, the issue's
replacement lines for capm.7 and items 3, 4 and 5 report their cases.
Entry 16 tries edge-based angle checks on the shapes of the first file.

In the [sky130A gap table](gaps/sky130A.md#front-end-li-mcon-met1-via1), the
x.2 and x.3a rows show that no KLayout run, including this deck's, reported
their 45° and 30° cases. The psd.10b row notes that this deck checks the
psdm area at 0.265 µm².

## IHP-GmbH/IHP-Open-PDK

This repository holds IHP's Magic tech files under `<pdk>/libs.tech/magic/`
(open_pdks has no IHP directory) and IHP's KLayout decks.

### 8. sg13g2 Magic DRC: CntB.b and CntB.h1 never fire

Kind: bug. Status: not filed.

CntB.b: minimum ContBar space, 0.28 µm. CntB.h1: minimum Metal1 enclosure of
ContBar, 0.05 µm (SG13G2 Rev. 0.4, section 5.15, page 34). Magic has both
rules, with these values, in an `exception CONTBAR` block, and neither
fires:
[ihp-sg13g2-drc.tech#L412-L417](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13g2/libs.tech/magic/ihp-sg13g2-drc.tech#L412-L417).

The GDS reader builds the CONTBAR mask hint from the non-square Cont shapes
([ihp-sg13g2-cifin.tech#L607-L614](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13g2/libs.tech/magic/ihp-sg13g2-cifin.tech#L607-L614)),
so the hint boxes are the bars themselves; with one hint box over the whole
cell, both rules fire. Why the bars' own boxes do not enable the rules has
not been traced. The repro draws two 0.16 × 0.50 µm bars 0.27 µm apart, and
a bar with 0.02 µm of Metal1 at its ends. SG13CMOS5L does the same checks
with CIF layers
([ihp-sg13cmos5l-drc.tech#L347-L353](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13cmos5l/libs.tech/magic/ihp-sg13cmos5l-drc.tech#L347-L353)),
and those checks fire on the same GDS. sg13g2 had them too until
[#973](https://github.com/IHP-GmbH/IHP-Open-PDK/pull/973), merged into `dev`
on 2026-08-24, replaced them with the exception block. A reduced CIF
version, tried on sg13g2, fires in `drc(full)`. Related:
[#972](https://github.com/IHP-GmbH/IHP-Open-PDK/issues/972) and
[#886](https://github.com/IHP-GmbH/IHP-Open-PDK/issues/886)/[#887](https://github.com/IHP-GmbH/IHP-Open-PDK/pull/887).

The CntB.b and CntB.h1 rows of the [ihp-sg13g2 gap
table](gaps/ihp-sg13g2.md#front-end-metal1-via1-grid-pins) note that Magic
reported nothing on their cases.

### 9. Magic DRC, sg13g2 and sg13cmos5l: Seal.f checks only pdiff, and Seal.d only the Cont ring

Kind: bug. Status: not filed. File it after entry 15, and put entry 15's
link in the line left for it under Additional context; if entry 15 is not
filed first, drop that line and the phrase "see the Magic issue linked
below". The expected result is still open (see [Open before
filing](#open-before-filing)).

| Rule | Manual | Magic | Upstream |
|---|---|---|---|
| Seal.f, Passiv ring to the seal-ring layers | 1.00 µm to EdgeSeal Activ, Metal1 to Metal5, TopMetal1 and TopMetal2 (SG13CMOS5L: Metal1 to Metal4 and TopMetal1) | `spacing seal pdiff,m1,m2,m3,m4,m5,m6 1000` (sg13cmos5l: `pdiff,m1,m2,m3,m4`), which checks only pdiff | [sg13g2#L984-L985](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13g2/libs.tech/magic/ihp-sg13g2-drc.tech#L984-L985), [sg13cmos5l#L709-L710](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13cmos5l/libs.tech/magic/ihp-sg13cmos5l-drc.tech#L709-L710) |
| Seal.d, EdgeSeal Activ enclosure of the seal rings | 1.30 µm for the Cont, Via1 to Via4, TopVia1 and TopVia2 rings (SG13CMOS5L: Cont, Via1 to Via3, TopVia1) | the Cont ring only | [sg13g2#L312-L313](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13g2/libs.tech/magic/ihp-sg13g2-drc.tech#L312-L313), [sg13cmos5l#L252-L253](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13cmos5l/libs.tech/magic/ihp-sg13cmos5l-drc.tech#L252-L253) |

Manual: SG13G2 Rev. 0.4, section 6.10, page 61; SG13CMOS5L Rev. 0.1, section
6.5, page 49.

The Seal.f statement leaves out the top metal (`m7` in sg13g2, `m5` in
sg13cmos5l), names `pdiff` where the seal ring's Activ is `psd` in Magic
([ihp-sg13g2-cifout.tech#L1293-L1294](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13g2/libs.tech/magic/ihp-sg13g2-cifout.tech#L1293-L1294)),
and lists types on several planes, for which Magic creates a rule for the
first plane pair only (entry 15). Magic's Seal.d follows the figure as
[#308](https://github.com/IHP-GmbH/IHP-Open-PDK/issues/308) read it, and
Rev. 0.4 then changed the rule text from the metals to the via rings. The
repro paints a passivation ring with a 3 × 3 µm box of each seal layer 0.5
µm from it, and a Via1 ring 0.3 µm inside the edge of the seal Activ; only
the pdiff box gets Seal.f, and Seal.d fires only on a control with the Cont
ring 0.3 µm inside. With one `spacing` statement per plane, including `psd`
and the top metal, and a CIF check on the via rings, both PDKs report the
expected errors on these cells. Neither change was run on a full seal ring.
Because `grow 1300` is Manhattan, the new Seal.d check would flag a ring
whose Activ encloses the vias by exactly 1.30 µm at its 45° corners.

The issue also notes that Seal.c1, the 0.19 µm via ring width, has no
"Min.", and that if it means an exact width, Magic checks only the lower
bound.

In the [ihp-sg13g2](gaps/ihp-sg13g2.md#other-layers) and
[ihp-sg13cmos5l](gaps/ihp-sg13cmos5l.md#other-layers) gap tables, the Seal.f
rows note the missing top metal, the Seal.d rows that Magic checks the Cont
ring only, and the Seal.c1 rows that Magic checks only the minimum width of
the via rings.

### 10. Magic, sg13g2 and sg13cmos5l: the GDS reader removes Via1 and pSD violations before DRC runs

Kind: question. Status: not filed. File it before entry 11.

| Rule | Manual | Magic's GDS reader | Upstream |
|---|---|---|---|
| V1.a and V1.b | Via1 width 0.19 µm, minimum and maximum; Via1 space 0.22 µm; Via1 at 90° only (section 3.1) | merges Via1 shapes 0.22 µm apart or less into one contact area, and deletes any Via1 0.18 µm wide or less | [sg13g2 cifin#L957-L963](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13g2/libs.tech/magic/ihp-sg13g2-cifin.tech#L957-L963), [sg13cmos5l cifin#L767-L773](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13cmos5l/libs.tech/magic/ihp-sg13cmos5l-cifin.tech#L767-L773) |
| pSD.i and pSD.j | pSD enclosure of a PFET gate and pSD space to an NFET gate, 0.30 µm, outside ThickGateOx | uses pSD only to type Activ, so pSD that covers no Activ is dropped; the writer rebuilds pSD from the device types | [sg13g2 cifin#L385-L392](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13g2/libs.tech/magic/ihp-sg13g2-cifin.tech#L385-L392), [cifout#L200-L207](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13g2/libs.tech/magic/ihp-sg13g2-cifout.tech#L200-L207) |

Manual: SG13G2 Rev. 0.4, sections 5.19 (page 38) and 5.10 (page 28);
SG13CMOS5L Rev. 0.1, sections 5.17 (page 36) and 5.8 (page 26).

The repro draws, in GDS, a 0.18 µm via, a 0.30 µm via, two vias 0.21 µm
apart, a via turned 45° and a pSD box 0.25 µm from an NFET gate. Magic's DRC
is clean on all five, and the GDS that Magic writes back has one 0.19 µm cut
for the 0.30 µm via, one cut for the pair, no cut for the 0.18 µm and 45°
vias, and no pSD. Part of this is probably by design, since Magic rebuilds
cuts and implants on output. The issue therefore asks whether DRC on
imported GDS is meant to catch V1.a, V1.b, pSD.i and pSD.j, and if it is,
whether the reader could warn about the shapes it removes. Via2 to Via4 are
read with the same steps and were not tested. Related:
[#400](https://github.com/IHP-GmbH/IHP-Open-PDK/issues/400), about pSD.i in
GDS that Magic writes.

In the [ihp-sg13g2 gap
table](gaps/ihp-sg13g2.md#front-end-metal1-via1-grid-pins), the V1.a and
V1.b rows note that Magic reported nothing on their cases, and so do the
V1.a, pSD.i and pSD.j rows of the [ihp-sg13cmos5l
table](gaps/ihp-sg13cmos5l.md#front-end-metal1-via1-grid-pins).

### 11. Magic DRC, sg13g2 and sg13cmos5l: no angle check on Activ, and Gat.f misses gates drawn at 45°

Kind: bug. Status: not filed. File it after entry 10, and put entry 10's
link where this one says that a non-Manhattan Via1 does not survive the GDS
read.

| Rule | Manual | Magic | Upstream |
|---|---|---|---|
| Section 3.1, edge angles | GatPoly, Activ and the metals only at 90°, 135°, 180°, 225° and 270° | no `angles` statement for diffusion, so a 30° or 60° Activ edge passes | – |
| Gat.f | 45° and 90° angles of GatPoly on Activ are not allowed | `rect_only allnfets,allpfets,pvar`, which flags a Manhattan bend in a gate and not the same bend on 45° axes | [sg13g2#L244](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13g2/libs.tech/magic/ihp-sg13g2-drc.tech#L244), [sg13cmos5l#L189](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13cmos5l/libs.tech/magic/ihp-sg13cmos5l-drc.tech#L189) |

Manual: SG13G2 Rev. 0.4, sections 3.1 (page 15) and 5.8 (page 26);
SG13CMOS5L Rev. 0.1, sections 3.1 (page 15) and 5.6 (page 24).

According to Magic's source, `rect_only` checks only inside corners, and the
corners of a gate drawn on 45° axes are between diagonal edges, which is
probably why the bend passes. Adding `angles allnfets,allpfets,pvar 90`
alone did not help. On a non-Manhattan tile Magic evaluates only the first
`angles` rule for a type pair
([drc/DRCbasic.c#L739-L746](https://github.com/RTimothyEdwards/magic/blob/1d42dfcdf6cd91df7a59198477324c2ca78ba439/drc/DRCbasic.c#L739-L746)),
and x.2's `angles allpoly 45` covers the transistor types too, so the 45°
rule is probably the one found first. The repro draws an L-shaped gate on
Activ, the same cell turned 45°, an Activ with one 60° edge and two clean
controls. With a 90° rule on the transistors, a 45° rule on diffusion and
x.2 limited to `allpolynonfet`, both PDKs give the expected errors, but the
varactor types are left with no angle rule. Related: entry 13, since the new
transistor rule would also flag a straight gate drawn at 45°.

### 12. Magic DRC, sg13g2 and sg13cmos5l: 90°-only rules on fill, and the IDs AFil.i, Padc.e and "Grid Rules"

Kind: question. Status: not filed.

| Rule | Manual | Magic | Upstream |
|---|---|---|---|
| angles on Activ, GatPoly, Metal1 to Metal5, TopMetal1 and TopMetal2 fill | no angle rule in any filler section; section 3.1's 45° bullet names layers, not purposes | `angles ... 90`, labelled AFil.i, GFil.k, MFil.i, TM1Fil.g and TM2Fil.g | sg13g2 [184](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13g2/libs.tech/magic/ihp-sg13g2-drc.tech#L184), [281](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13g2/libs.tech/magic/ihp-sg13g2-drc.tech#L281), [454](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13g2/libs.tech/magic/ihp-sg13g2-drc.tech#L454), [512](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13g2/libs.tech/magic/ihp-sg13g2-drc.tech#L512), [570](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13g2/libs.tech/magic/ihp-sg13g2-drc.tech#L570), [628](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13g2/libs.tech/magic/ihp-sg13g2-drc.tech#L628), [687](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13g2/libs.tech/magic/ihp-sg13g2-drc.tech#L687), [726](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13g2/libs.tech/magic/ihp-sg13g2-drc.tech#L726), [772](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13g2/libs.tech/magic/ihp-sg13g2-drc.tech#L772); sg13cmos5l [140](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13cmos5l/libs.tech/magic/ihp-sg13cmos5l-drc.tech#L140), [222](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13cmos5l/libs.tech/magic/ihp-sg13cmos5l-drc.tech#L222), [390](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13cmos5l/libs.tech/magic/ihp-sg13cmos5l-drc.tech#L390), [450](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13cmos5l/libs.tech/magic/ihp-sg13cmos5l-drc.tech#L450), [508](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13cmos5l/libs.tech/magic/ihp-sg13cmos5l-drc.tech#L508), [566](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13cmos5l/libs.tech/magic/ihp-sg13cmos5l-drc.tech#L566), [604](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13cmos5l/libs.tech/magic/ihp-sg13cmos5l-drc.tech#L604) |
| AFil.i | Activ:filler space to PWell:block, 1.50 µm, which Magic checks under that ID at sg13g2 lines 130-133 and sg13cmos5l lines 90-93 | also the ID of the angle rule on Activ fill | [sg13g2#L184](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13g2/libs.tech/magic/ihp-sg13g2-drc.tech#L184), [sg13cmos5l#L140](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13cmos5l/libs.tech/magic/ihp-sg13cmos5l-drc.tech#L140) |
| Padc.b and Padc.e | the CuPillarPad space is Padc.b (section 6.9.2, Table 6.1); Padc.e is the pad pitch, which is not checked during DRC | `spacing pillar pillar 40000`, 40 µm, labelled Padc.e | [sg13g2#L1001](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13g2/libs.tech/magic/ihp-sg13g2-drc.tech#L1001) |
| MIM shape | MIM is in neither angle bullet of section 3.1 | `rect_only *mimcap`, labelled "Grid Rules" | [sg13g2#L902](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13g2/libs.tech/magic/ihp-sg13g2-drc.tech#L902) |

IHP's KLayout deck puts the filler layers only into its acute-angle check.
The manuals have no GFil.k, TM1Fil.g or TM2Fil.g; those names appear as JSON
keys that no deck reads (entry 14), so the IDs may come from an older
revision. The repro draws a Metal1:filler octagon 2 µm across with 0.5 µm
45° chamfers, which gets four MFil.i errors in both PDKs. The issue asks
whether the fill rules should be `angles ... 45`, be removed, or stay as a
Magic restriction under a different ID. Line 902 also lacks a closing quote;
open PR [#1325](https://github.com/IHP-GmbH/IHP-Open-PDK/pull/1325)
addresses it.

The Padc.b row of the [ihp-sg13g2 gap
table](gaps/ihp-sg13g2.md#other-layers) notes that Magic prints this spacing
as Padc.e.

### 13. KLayout maximal deck: Gat.f flags straight 45° gates

Kind: question. Status: not filed.

Gat.f: "45-degree and 90-degree angles for GatPoly on Activ area are not
allowed" (SG13G2 Rev. 0.4, section 5.8, page 26; SG13CMOS5L Rev. 0.1,
section 5.6, page 24). The maximal decks implement it as
`Gate.ext_not(SVaricap).ext_rectangles(true, ...)`, which flags any gate
that is not an axis-aligned rectangle:
[sg13g2_maximal.drc#L2133-L2135](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13g2/libs.tech/klayout/tech/drc/rule_decks/sg13g2_maximal.drc#L2133-L2135),
[sg13cmos5l_maximal.drc#L2020-L2022](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13cmos5l/libs.tech/klayout/tech/drc/rule_decks/sg13cmos5l_maximal.drc#L2020-L2022).

Read literally, Gat.f forbids bends of GatPoly over Activ, and a straight
gate drawn at 45° across a 45° Activ has no GatPoly corner on Activ. The
deck goes further and rejects straight diagonal gates too. The repro draws a
straight gate, a straight 45° gate 0.163 µm wide with 0.184 µm end caps, and
a gate with a 90° bend; the deck flags the last two in both PDKs, and two
alternative checks, `ext_rectangles(false, ...)` and GatPoly corners inside
Activ, flag only the bend. Gat.f is one of the extra rules in
`docs/extra_rules.md` that only the maximal deck checks, so a flow that runs
the modular deck directly skips it
([#1106](https://github.com/IHP-GmbH/IHP-Open-PDK/issues/1106) describes
LibreLane doing that). PR
[#885](https://github.com/IHP-GmbH/IHP-Open-PDK/pull/885) would port those
rules into the modular deck, so the answer applies to the port too. Related:
[#412](https://github.com/IHP-GmbH/IHP-Open-PDK/issues/412) and entry 11.

### 14. IHP DRC JSON files: five rule values differ from the layout rules, and no deck reads them

Kind: bug, with no effect on the DRC results for these rules today, plus a
question on Seal.f. Status: not filed.

| Key | sg13g2 line | sg13cmos5l line | JSON | Manual |
|---|---|---|---|---|
| `AFil_b` | [44](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13g2/libs.tech/klayout/tech/drc/rule_decks/sg13g2_tech_default.json#L44) | [47](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13cmos5l/libs.tech/klayout/tech/drc/rule_decks/sg13cmos5l_tech_default.json#L47) | 1.0 | AFil.b, 0.42 µm |
| `GFil_j` | [89](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13g2/libs.tech/klayout/tech/drc/rule_decks/sg13g2_tech_default.json#L89) | [92](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13cmos5l/libs.tech/klayout/tech/drc/rule_decks/sg13cmos5l_tech_default.json#L92) | 20.0 | GFil.j, 0.18 µm |
| `MFil_a1` | [274](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13g2/libs.tech/klayout/tech/drc/rule_decks/sg13g2_tech_default.json#L274) | [251](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13cmos5l/libs.tech/klayout/tech/drc/rule_decks/sg13cmos5l_tech_default.json#L251) | 2.0 | MFil.a1, 1.00 µm |
| `MFil_b` | [278](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13g2/libs.tech/klayout/tech/drc/rule_decks/sg13g2_tech_default.json#L278) | [255](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13cmos5l/libs.tech/klayout/tech/drc/rule_decks/sg13cmos5l_tech_default.json#L255) | 0.6 | MFil.b, 0.42 µm |
| `Seal_f` | [371](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13g2/libs.tech/klayout/tech/drc/rule_decks/sg13g2_tech_default.json#L371) | [324](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13cmos5l/libs.tech/klayout/tech/drc/rule_decks/sg13cmos5l_tech_default.json#L324) | 3.0 | Seal.f, 1.00 µm |
| `GFil_k` | [90](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13g2/libs.tech/klayout/tech/drc/rule_decks/sg13g2_tech_default.json#L90) | [93](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13cmos5l/libs.tech/klayout/tech/drc/rule_decks/sg13cmos5l_tech_default.json#L93) | 0.0 | no such rule |
| `TM1Fil_g` | [297](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13g2/libs.tech/klayout/tech/drc/rule_decks/sg13g2_tech_default.json#L297) | [274](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13cmos5l/libs.tech/klayout/tech/drc/rule_decks/sg13cmos5l_tech_default.json#L274) | 0.0 | no such rule |
| `TM2Fil_g` | [309](https://github.com/IHP-GmbH/IHP-Open-PDK/blob/e73adb4045731ddec21634146d536380057f6a26/ihp-sg13g2/libs.tech/klayout/tech/drc/rule_decks/sg13g2_tech_default.json#L309) | – | 0.0 | no such rule |

The lines are in `sg13g2_tech_default.json` and
`sg13cmos5l_tech_default.json` under
`<pdk>/libs.tech/klayout/tech/drc/rule_decks/`; the pycell libraries'
`*_tech_mod.json` files hold the same values. The two manuals agree on all
five values.

Today no deck reads these keys, and the maximal decks hard-code the manual's
values. PR #885 at 8cccf42 reads `AFil_b` and `Seal_f` from the JSON. It
fixes four of the keys in `sg13g2_tech_default.json`, but keeps `Seal_f` at
3.0 and leaves `sg13g2_tech_mod.json` alone. For sg13g2 the tech_mod values
are merged over tech_default (`ihp-sg13g2.drc` line 211), so the ported
AFil.b check would get 1.0, and Seal.f would get 3.0 from either file. A
script lists each key's value and whether any deck file reads it. Related:
entry 12, which cites the same three unused keys.

The maximal decks also check Seal.f against EdgeSeal pSD (`Seal.f.pSD`,
`sg13g2_maximal.drc` line 2796), which the manual's Seal.f does not list, so
the issue asks whether the manual should list pSD or the check should go.

The Seal.f rows of the [ihp-sg13g2](gaps/ihp-sg13g2.md#other-layers) and
[ihp-sg13cmos5l](gaps/ihp-sg13cmos5l.md#other-layers) gap tables note that
pSD is not in the layout rules' Seal.f list.

## RTimothyEdwards/magic

### 15. DRC tech: a `spacing` rule whose type lists span several planes creates the rule for the first plane pair only

Kind: bug. Status: not filed. File it before entry 9.

`drcSpacing()` accepts type lists whose types sit on different planes and
loops over the plane pairs, but it returns from inside the loop, so only the
first pair gets a rule:
[drc/DRCtech.c#L2811-L2832](https://github.com/RTimothyEdwards/magic/blob/1d42dfcdf6cd91df7a59198477324c2ca78ba439/drc/DRCtech.c#L2811-L2832).

In IHP's Seal.f statement (entry 9, 1.00 µm) the first pair is pdiff on the
active plane, and none of the metals m1 to m6 is checked. A scripted search
of the sky130A, gf180mcuD, ihp-sg13g2 and ihp-sg13cmos5l tech files found no
other `spacing` statement whose two lists share no plane, though it may miss
corner cases with aliases. The repro paints a passivation ring with a 3 × 3
µm box of each of m1 to m7, psd and pdiff 0.5 µm from it, and only the pdiff
box is flagged until the statement is split into one per layer. The
suggested patch keeps the loop going and returns the largest distance; it
has not been built or tested.

## sky130 MR deck: chipfoundry/cf-precheck or fossi-foundation/sky130_klayout_pdk

Where to file entries 16 and 17 is still open (see [Open before
filing](#open-before-filing)). Both drafts are addressed to cf-precheck and
quote its deck first. The same code is in the copies in sky130_klayout_pdk
and in mpw_precheck, the copy that open_pdks installs.

### 16. sky130A_mr.drc: the x.2 and x.3a angle checks select polygon corners, not edges

Kind: bug. Status: not filed.

x.2 allows only [n ×
90°](https://github.com/google/skywater-pdk/blob/7198cf647113f56041e02abf3eb623692820c5e1/docs/rules/periphery-rules.rst?plain=1#L138-L154)
on diff, tap, poly, li1 in the periphery, licon1, capm, mcon and via to
via4, and x.3a only [n ×
45°](https://github.com/google/skywater-pdk/blob/7198cf647113f56041e02abf3eb623692820c5e1/docs/rules/periphery-rules.rst?plain=1#L170-L174)
on the other layers apart from the WLCSP layers. The deck calls
`with_angle(0..90)` and `with_angle(0..45)` on polygon layers, which selects
corners whose edges meet in that range, so x.2 reports only corners under
90° and x.3a only corners under 45°.

| Copy | Lines |
|---|---|
| cf-precheck | [1681-1782](https://github.com/chipfoundry/cf-precheck/blob/9ed31213395308360e6cfb21481279d3233e3ec6/src/cf_precheck/drc_scripts/sky130A_mr.drc#L1681-L1782), with diff and tap at [1704-1719](https://github.com/chipfoundry/cf-precheck/blob/9ed31213395308360e6cfb21481279d3233e3ec6/src/cf_precheck/drc_scripts/sky130A_mr.drc#L1704-L1719); `MR_licon.ANG.1` [854](https://github.com/chipfoundry/cf-precheck/blob/9ed31213395308360e6cfb21481279d3233e3ec6/src/cf_precheck/drc_scripts/sky130A_mr.drc#L854) |
| sky130_klayout_pdk | [1679-1780](https://github.com/fossi-foundation/sky130_klayout_pdk/blob/4ea0975391feacbdac697bf07029d8908d292613/tech/sky130/drc/sky130A_mr.drc#L1679-L1780), `MR_licon.ANG.1` [852](https://github.com/fossi-foundation/sky130_klayout_pdk/blob/4ea0975391feacbdac697bf07029d8908d292613/tech/sky130/drc/sky130A_mr.drc#L852) |
| mpw_precheck | [1502-1603](https://github.com/fossi-foundation/mpw_precheck/blob/86b7362dacd931bf1fd957c84501bfbe7955fa7c/checks/tech-files/sky130A_mr.drc#L1502-L1603), without `MR_licon.ANG.1` |

The angle checks of all three copies pass a 45° chamfer on diff, a 45° jog
in poly, a 45° edge on periphery li1 and a 30° edge on met1. The deck also
checks all li under x.3a, where x.2 puts periphery li1. The repro draws
eight shapes on diff, poly, licon, li1 and met1. With the suggested
edge-based lines, `.edges.without_angle(ortho)` for x.2 and `(diagonal)` for
x.3a (KLayout 0.28 or later), the deck reports each bad edge and nothing on
the two legal shapes. The cf-precheck README lists `magic_drc` as optional
and off by default, so in a default precheck run these are the only angle
checks.

The x.2 and x.3a rows of the [sky130A gap
table](gaps/sky130A.md#front-end-li-mcon-met1-via1) note that KLayout
reported nothing on their 45° and 30° cases.

### 17. sky130A_mr.drc does not check poly.11, difftap.11 or n/psd.5a

Kind: question. Status: not filed.

| Rule | Periphery rules | MR deck |
|---|---|---|
| poly.11 | [no 90° turns of poly on diff](https://github.com/google/skywater-pdk/blob/7198cf647113f56041e02abf3eb623692820c5e1/docs/rules/periphery-rules.rst?plain=1#L1092-L1096), no value | no check |
| difftap.11 | [p+ tap to N-well, 0.130 µm](https://github.com/google/skywater-pdk/blob/7198cf647113f56041e02abf3eb623692820c5e1/docs/rules/periphery-rules.rst?plain=1#L930-L934) | no check |
| n/psd.5a | [enclosure of diff by nsdm or psdm, 0.125 µm](https://github.com/google/skywater-pdk/blob/7198cf647113f56041e02abf3eb623692820c5e1/docs/rules/periphery-rules.rst?plain=1#L1461-L1465) | no check |

[sky130A_mr.drc](https://github.com/chipfoundry/cf-precheck/blob/9ed31213395308360e6cfb21481279d3233e3ec6/src/cf_precheck/drc_scripts/sky130A_mr.drc)
at cf-precheck 9ed3121 contains neither the rule names nor the values 0.125
and 0.13, and the copies in sky130_klayout_pdk and mpw_precheck have no
check for them either. The MR deck covers a defined subset of the rules, and
the subset changes (licon.9 is in the 2025.11.17_01.10 and 2026.03.30_01.00
releases as `MR_licon.SP.6`), so the issue asks whether these three are left
out on purpose. The repro draws an nsdm equal to its n-diff, a 0.15 µm gate
poly that turns 90° on diff, and a contacted p+ tap 0.10 µm from N-well; no
copy of the deck reports anything, and `sky130.lydrc` with FEOL on reports
difftap.11 on the tap.

In the [sky130A gap table](gaps/sky130A.md#front-end-li-mcon-met1-via1), the
poly.11, diff/tap.11, nsd.5a and psd.5a rows have no `sky130A_mr.drc` check,
and their notes say that `sky130A.lydrc` has the rule.

## fossi-foundation/globalfoundries-pdk-libs-gf180mcu_fd_pv

### 18. PL.6 misses a 90° Poly2 bend within 0.1 µm of the COMP edge

Kind: bug. Status: not filed.

PL.6: [90° bends on the COMP are not
allowed](https://github.com/google/gf180mcu-pdk/blob/de3240d7529a6970437ac3344820aaae7839f215/docs/physical_verification/design_manual/tables_clear/16_Poly2_42.csv?plain=1#L21),
with no value. The deck grows each 90° corner marker by 0.1 µm before
`inside(comp)`, so a corner on COMP within 0.1 µm of a COMP edge is dropped:
[klayout/drc/rule_decks/poly2.rb#L141-L144](https://github.com/fossi-foundation/globalfoundries-pdk-libs-gf180mcu_fd_pv/blob/0df548b2ba5a255b6a914b107d89bd7ed1063a39/klayout/drc/rule_decks/poly2.rb#L141-L144),
with `pl6_l1` on lines 143-144.

The grown marker is a 0.202 µm box centred on the corner, and `inside(comp)`
keeps only boxes that lie wholly inside COMP. The repro draws three 3.3 V
NMOS gates with an L bend on a 3 × 3 µm COMP. With the bend in the middle of
COMP the deck reports PL.6; with the inner corner of the bend 0.05 µm inside
the COMP edge it reports no PL.6; with the bend 0.05 µm outside COMP, which
PL.6 allows, it reports none. Testing the corner's position first and
growing the marker afterwards flags the second case and leaves the other two
as they were.

## Items that need no new issue

### Fixed upstream

- **sky130 met1.7 and IHP Act.e.** Magic 8.3.681, in the pinned image,
  misses met1.7 (metal1 holes, 0.14 µm²) and Act.e on holes in Activ,
  because Magic's CIF `close` operator filled nothing from 516c9d76 (January
  2026) until [RTimothyEdwards/magic
  490a7dfd35](https://github.com/RTimothyEdwards/magic/commit/490a7dfd35642ea5884a775857110dcbae9dc4e5)
  (2026-10-26, Magic 8.3.687), whose commit message names met1.7, met2.7 and
  the two IHP PDKs. The rules in the tech files are right. Neither rule was
  run on a Magic with the fix. The met1.7 row of the [sky130A gap
  table](gaps/sky130A.md#front-end-li-mcon-met1-via1) notes that Magic
  reported nothing on its two cases.
- **sky130 licon.9 in the MR deck.** The maintained MR deck checks it as
  `MR_licon.SP.6`: sky130_klayout_pdk since 9af4c7c (2025-11-22, release
  2025.11.17_01.10), and cf-precheck in release 2026.03.30_01.00. The copy
  that open_pdks installs does not have it yet (entry 6), and
  `sky130A.lydrc` does not code it (entry 7, item 7).

### Already reported

- **IHP MIM.i.** Magic still checks MIM.i, which Rev. 0.2 of the layout
  rules removed. [#376](https://github.com/IHP-GmbH/IHP-Open-PDK/issues/376)
  (open, 2025-03-05) has IHP's confirmation of the removal and the reply
  that "the rule and associated cif layer should just be removed", and
  [#1342](https://github.com/IHP-GmbH/IHP-Open-PDK/issues/1342) (open,
  2026-11-06) asks again whether the rule should go. Both cover what the
  check of the gap tables found. The [ihp-sg13g2 gap
  table](gaps/ihp-sg13g2.md#other-layers) has MIM.i as Magic only.

### Dropped or not drafted

- **IHP maximum Via1 width.** An oversized Via1 area is legal in Magic's
  contact model, which cuts it into 0.19 µm squares on output, so there is
  nothing to request. What happens to such a via on reading is in entry 10.
- **IHP acute-angle check (no corner under 87°).** No Magic DRC statement
  that measures corner angles was known when the issues were drafted, so
  this would be a feature request for Magic rather than a tech-file fix.
- **IHP non-Manhattan cuts.** The GDS reader deletes a Via1 turned 45°, so
  no via is left for an angle rule to check; entry 10 covers this.
- **Magic evaluates only the first `angles` rule per type pair on
  non-Manhattan tiles** (`drc/DRCbasic.c` lines 739-746). Entry 11 explains
  it and works around it.
- **IHP Seal.c1 as an exact width.** Entry 9 covers it in one sentence.
- **gf180mcuD CO.2a and V1.2a (cuts merged on reading) and DV.6 (DUALGATE
  regenerated).** These are the same kind of problem as entry 10 and were
  not tested again. File an issue for open-pdks only if IHP's answer to
  entry 10 is that such violations should be visible. The CO.2a, V1.2a and
  DV.6 rows of the [gf180mcuD gap table](gaps/gf180mcuD.md#wells-to-via1)
  note that Magic reported nothing on their cases.
- **gf180mcuD acute angles on non-transistor layers.** Magic has `angles`
  rules on transistors only. This was found by reading the tech file and has
  not been tested.
- **A possible upper limit on gf180mcuD HRES.7 and PRES.7.** Commit
  63343654fe (2026-11-14) reworked `res_no_cont`, and the limit has not been
  tested since.
- **sky130A lvtn.10 and tunm.8.** The manual's text for lvtn.10 is
  ambiguous, and a comment in Magic's tech file says that the tunm.8
  deviation is deliberate.
- **IHP Gat.f only in the maximal deck.** `docs/extra_rules.md` lists Gat.f
  with the other extra rules on purpose. Entry 13 mentions it, with
  [#1106](https://github.com/IHP-GmbH/IHP-Open-PDK/issues/1106) (NW.c1, the
  same kind of gap) and PR #885.
- **IHP Seal.f with pSD in the maximal deck.** The question is part of entry
  14.
- **IHP Seal.k and Seal.m, checked though the manual says "Not checked
  during DRC".** IHP added them on purpose in PR
  [#538](https://github.com/IHP-GmbH/IHP-Open-PDK/pull/538); Seal.m was
  discussed in [#664](https://github.com/IHP-GmbH/IHP-Open-PDK/issues/664).
- **IHP's KLayout angle checks, which exempt circle-like polygons.** Padc.f
  requires circular Cu-pillar openings, so the exemption serves a rule in
  the manual.
- **sky130A.lydrc's licon.16 source half and nwell.4, commented out.** Both
  were disabled on purpose, and the deck's comments give the reason.
- **sky130A_mr.drc's `difftap.2` output, which is the core rule difftap.c1**
  (cf-precheck line 441). Only the name is in question, and it could go into
  entry 17 as one line. The `difftap.2 [sky130A_mr.drc]` row of the [sky130A
  gap table](gaps/sky130A.md#front-end-li-mcon-met1-via1) notes it.

## Open before filing

- **Where to file entries 16 and 17.** The candidates are
  chipfoundry/cf-precheck, which both drafts address and whose deck they
  quote first, and fossi-foundation/sky130_klayout_pdk. In favour of
  sky130_klayout_pdk, its
  `tech/sky130/drc/README.md` calls its copy the deck that is "currently
  actively maintained", open_pdks pins it as `klayout_sky130`, and the reply
  in open_pdks
  [#538](https://github.com/fossi-foundation/open-pdks/issues/538) linked
  that copy.
- **Whether entry 9's expected result includes the pdiff box.** The repro
  puts a 3 × 3 µm box of each of m1 to m7, psd and pdiff 0.5 µm from the
  passivation ring, and the expected result asks for Seal.f on the m1 to m7
  and psd boxes without mentioning pdiff. Today only the pdiff box gets
  Seal.f, and the suggested fix drops pdiff from the statement, so that box
  would no longer be flagged. In Magic's IHP tech the seal ring's Activ is
  `psd`, not `pdiff`.
