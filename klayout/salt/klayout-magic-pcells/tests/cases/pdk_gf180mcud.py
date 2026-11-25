"""gf180mcuD cases. The gaps set is the gf180mcuD gap study's suite
(GAPS-gf180mcuD section 2): five controls
(3.3 V and 6 V nfet and pfet, a p-tap) and one-change cells, every mask
layer drawn by hand on the GDS numbers generic_layers.rb reads. The table
is that suite's, unchanged, so that expect-gf180mcuD.json still applies,
except for four cases that did not break the rule they target: NW2a_s050,
NP3_s006, V1_3_m1ov0 and V1_3_m1ov002 were redrawn in 0.6.1, and their
expect entries were measured again on the new shapes (SOURCES).
"""

import klayout.db as db

PDK = "gf180mcuD"
SOURCE = "GAPS-gf180mcuD 2"
_REDRAWN = ("GAPS-gf180mcuD 2, redrawn in 0.6.1 to break its target rule; expect measured on the new "
            "shapes with Magic 8.3.681 and gf180mcu.drc in the pinned image, 2026-11-24")
SOURCES = {n: _REDRAWN for n in ("NW2a_s050", "NP3_s006", "V1_3_m1ov0", "V1_3_m1ov002")}

LAYERS = {"comp": (22, 0), "poly": (30, 0), "np": (32, 0), "pp": (31, 0), "nwell": (21, 0),
          "cont": (33, 0), "m1": (34, 0), "v1": (35, 0), "m2": (36, 0), "dg": (55, 0),
          "v5": (112, 1), "sab": (49, 0), "nat": (5, 0), "lvpw": (204, 0), "dnw": (12, 0),
          "m1txt": (34, 10), "resmk": (110, 5)}


def B(x1, y1, x2, y2):
    return db.DBox(min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))


def grow(b, d, dy=None):
    return b.enlarged(db.DVector(d, d if dy is None else dy))


def mos(kind="n", W=0.6, Lg=0.28, c2g=0.20, co4=0.12, co3=0.08, co8=0.25, pl4=0.22,
        imp=0.23, tap_imp=0.16, m1ov=0.08, nw_ov=0.5, sd_l=None, sd_r=None, mv=False,
        gap=0.49, tap=True):
    """One MOSFET with S/D and gate contacts and a well/substrate tap on its left.
    kind 'n': NCOMP + NPLUS, P tap (PCOMP + PPLUS). kind 'p': in NWELL, N tap.
    Returns {name: (layer, DBox)}."""
    s = {}
    sd = c2g + 0.22 + co4
    sdl = sd if sd_l is None else sd_l
    sdr = sd if sd_r is None else sd_r
    xg1, xg2 = -Lg / 2, Lg / 2
    s["comp"] = ("comp", B(xg1 - sdl, 0, xg2 + sdr, W))
    s["gate"] = ("poly", B(xg1, -pl4, xg2, W + co8 - co3))
    pw = 0.22 + 2 * co3
    s["gpad"] = ("poly", B(-pw / 2, W + co8 - co3, pw / 2, W + co8 - co3 + pw))
    yc = W / 2
    s["cs"] = ("cont", B(xg1 - c2g - 0.22, yc - 0.11, xg1 - c2g, yc + 0.11))
    s["cd"] = ("cont", B(xg2 + c2g, yc - 0.11, xg2 + c2g + 0.22, yc + 0.11))
    s["cg"] = ("cont", B(-0.11, W + co8, 0.11, W + co8 + 0.22))
    for k in ("cs", "cd", "cg"):
        s["m1" + k[1]] = ("m1", grow(s[k][1], m1ov))
    imp_l = "np" if kind == "n" else "pp"
    s["imp"] = (imp_l, grow(s["comp"][1], imp))
    if tap:
        cx2 = s["comp"][1].left - gap
        s["tcomp"] = ("comp", B(cx2 - 0.6, 0, cx2, 0.6))
        s["timp"] = ("pp" if kind == "n" else "np", grow(s["tcomp"][1], tap_imp))
        s["tc"] = ("cont", B(cx2 - 0.41, 0.19, cx2 - 0.19, 0.41))
        s["m1t"] = ("m1", grow(s["tc"][1], m1ov))
    if kind == "p":
        bb = s["comp"][1]
        if tap:
            bb = bb + s["tcomp"][1]
        s["nwell"] = ("nwell", grow(bb, nw_ov))
    if mv:
        bb = db.DBox()
        for k, (l, b) in s.items():
            if l in ("comp",):
                bb = bb + grow(b, 0.24)
            if l == "poly":
                bb = bb + grow(b, 0.4)
        s["dg"] = ("dg", grow(bb, 0.05))
    return s


def ptap(x=0, y=0, w=0.6, h=0.6, imp=0.16, cont=True, kind="p"):
    s = {"tcomp": ("comp", B(x, y, x + w, y + h)),
         "timp": ("pp" if kind == "p" else "np", grow(B(x, y, x + w, y + h), imp))}
    if cont:
        cx, cy = x + w / 2, y + h / 2
        s["tc"] = ("cont", B(cx - 0.11, cy - 0.11, cx + 0.11, cy + 0.11))
        s["m1t"] = ("m1", grow(s["tc"][1], 0.08))
    return s


T = {}      # name -> (dict of shapes, note)


def add(name, shapes, note):
    T[name] = (shapes, note)


# ---------------------------------------------------------------- controls
add("C_NMOS", mos("n"), "control: LV nfet W0.6 L0.28 with S/D/gate contacts and a p-tap")
add("C_PMOS", mos("p"), "control: LV pfet W0.6 L0.28 in nwell with an n-tap")
add("C_NMOS6", mos("n", Lg=0.7, co8=0.40, mv=True), "control: 6V nfet (DUALGATE) W0.6 L0.7")
add("C_PMOS6", mos("p", Lg=0.55, co8=0.40, mv=True, nw_ov=0.65), "control: 6V pfet (DUALGATE) W0.6 L0.55")
add("C_PTAP", ptap(), "control: p-tap alone")

# ---------------------------------------------------------------- wells
s = {"nw": ("nwell", B(0, 0, 0.80, 5))}
add("NW1a_w080", s, "nwell 0.80 wide (NW.1a 0.86)")
# NW.2a 0.6 is the space between wells on one net; wells on different nets
# need NW.2b 1.4. KLayout tells the two apart by connectivity (Nwell, NCOMP,
# contact, Metal1), so each well gets an n-tap and one Metal1 strip joins
# the taps.
s = {"nw1": ("nwell", B(0, 0, 2, 2)), "nw2": ("nwell", B(2.5, 0, 4.5, 2))}
for i, x in enumerate((0.7, 3.2)):
    s.update({k + str(i): v for k, v in ptap(x=x, y=0.7, kind="n").items()})
s["m1strap"] = ("m1", B(0.81, 0.81, 3.69, 1.19))
add("NW2a_s050", s, "two nwells 0.50 apart on one net, an n-tap in each joined by metal1 (NW.2a 0.6)")
s = mos("p", nw_ov=0.5)
s["nwell"] = ("nwell", s["nwell"][1].enlarged(db.DVector(0, 0)))
nb = s["nwell"][1]
s["nwell"] = ("nwell", B(nb.left, nb.bottom, s["comp"][1].right + 0.38, nb.top))
add("DF7_pdiff_nw038", s, "pfet: nwell encloses PCOMP by 0.38 on the right (Magic DF.7 / KLayout DF.4c_LV 0.43)")
s = mos("p")
nb = s["nwell"][1]
s["nwell"] = ("nwell", B(s["tcomp"][1].left - 0.08, nb.bottom, nb.right, nb.top))
add("DF4a_ntap_nw008", s, "n-tap: nwell encloses NCOMP by 0.08 on the left (Magic DF.4a / KLayout DF.4d_LV 0.12)")
s = mos("n")
cb = s["comp"][1]
s["nwx"] = ("nwell", B(cb.right + 0.38, -1, cb.right + 0.38 + 2, 2))
add("DF8_ndiff_nw038", s, "nfet NCOMP 0.38 from an unrelated nwell (Magic DF.8 / KLayout DF.16_LV 0.43)")
s = ptap()
s["nwx"] = ("nwell", B(0.6 + 0.08, -1, 0.6 + 0.08 + 2, 2))
add("DF5_ptap_nw008", s, "p-tap PCOMP 0.08 from an nwell (Magic DF.5 / KLayout DF.17_LV 0.12)")
s = mos("p")
del s["nwell"]
add("NWmiss_pfet", s, "pfet and n-tap drawn with no NWELL at all")

# ---------------------------------------------------------------- diffusion
s = {"tcomp": ("comp", B(0, 0, 0.20, 2.0)), "timp": ("pp", grow(B(0, 0, 0.20, 2.0), 0.16))}
add("DF1a_w020", s, "p-tap COMP 0.20 wide, no contact (DF.1a 0.22)")
s = ptap()
s2 = ptap(x=0.85)
s.update({k + "2": v for k, v in s2.items()})
s["timp"] = ("pp", s["timp"][1] + s["timp2"][1]); del s["timp2"]
add("DF3a_s025", s, "two p-tap COMPs 0.25 apart under one PPLUS (DF.3a 0.28)")
s = {"tcomp": ("comp", B(0, 0, 0.3, 0.6)), "timp": ("pp", grow(B(0, 0, 0.3, 0.6), 0.25))}
add("DF9_a018", s, "p-tap COMP 0.30 x 0.60 = 0.18 um2 (DF.9 0.2025)")
s = mos("n")
cb = s["comp"][1]
# right S/D reduced to 0.235 with its contact moved off the COMP (no right contact)
s["comp"] = ("comp", B(cb.left, cb.bottom, 0.14 + 0.235, cb.top))
del s["cd"], s["m1d"]
s["imp"] = ("np", grow(s["comp"][1], 0.23))
add("DF6_lv_0235", s, "LV nfet, right S/D 0.235 past the gate, no contact there (Magic DF.6 0.23, KLayout DF.6_LV 0.24)")
s = mos("n")
s["comp"] = ("comp", B(cb.left, cb.bottom, 0.14 + 0.20, cb.top))
del s["cd"], s["m1d"]
s["imp"] = ("np", grow(s["comp"][1], 0.23))
add("DF6_lv_020", s, "LV nfet, right S/D 0.20 past the gate (both 0.23/0.24)")
s = mos("n", Lg=0.7, co8=0.40, mv=True)
cb = s["comp"][1]
s["comp"] = ("comp", B(cb.left, cb.bottom, 0.35 + 0.30, cb.top))
del s["cd"], s["m1d"]
s["imp"] = ("np", grow(s["comp"][1], 0.23))
add("DF6_mv_030", s, "6V nfet, right S/D 0.30 past the gate (Magic DF.6 0.23, KLayout DF.6_MV 0.40)")
s = ptap()
del s["timp"]
add("DF12_noimp", s, "tap COMP with contact and no NPLUS/PPLUS (KLayout DF.12)")

# ---------------------------------------------------------------- poly
s = ptap()
s["pl"] = ("poly", B(2, -1, 2.16, 2))
add("PL1_w016", s, "field poly line 0.16 wide next to a tap (PL.1 0.18)")
s = ptap()
s["pl"] = ("poly", B(2, -1, 2.2, 2)); s["pl2"] = ("poly", B(2.4, -1, 2.6, 2))
add("PL3a_s020", s, "two field poly lines 0.20 apart (PL.3a 0.24)")
add("PL4_e015", mos("n", pl4=0.15), "LV nfet poly end cap 0.15 (PL.4 0.22)")
s = ptap()
s["pl"] = ("poly", B(0.6 + 0.08, -1, 0.6 + 0.08 + 0.3, 2))
add("PL5a_s008", s, "field poly 0.08 from an unrelated tap COMP (Magic PL.5a / KLayout PL.5a_LV 0.10)")
add("PL2_lv_L025", mos("n", Lg=0.25), "LV nfet L 0.25 (PL.2 0.28)")
add("PL2_mv_L060", mos("n", Lg=0.6, co8=0.40, mv=True), "6V nfet L 0.60 (PL.2 6V nfet 0.70)")
s = mos("n", Lg=0.7, co8=0.40, mv=True)
s["plx"] = ("poly", B(2.0, -0.3, 2.19, 1.5))
s["dg"] = ("dg", s["dg"][1] + grow(s["plx"][1], 0.45))
add("PL1_mv_w019", s, "6V nfet plus a 0.19 wide field poly line inside DUALGATE (KLayout PL.1_MV 0.20)")

# ---------------------------------------------------------------- contacts
s = ptap(w=0.8, h=0.8)
s["tc"] = ("cont", B(0.25, 0.25, 0.55, 0.55)); s["m1t"] = ("m1", B(0.17, 0.17, 0.63, 0.63))
add("CO1_big030", s, "0.30 x 0.30 contact in a tap (CO.1 is exactly 0.22)")
s = ptap()
s["tc"] = ("cont", B(0.2, 0.2, 0.4, 0.4))
add("CO1_small020", s, "0.20 x 0.20 contact in a tap (CO.1 0.22)")
s = ptap(w=1.0, h=0.6)
s["tc"] = ("cont", B(0.17, 0.19, 0.39, 0.41)); s["tc2"] = ("cont", B(0.61, 0.19, 0.83, 0.41))
s["m1t"] = ("m1", B(0.09, 0.11, 0.91, 0.49))
add("CO2a_s022", s, "two tap contacts 0.22 apart (CO.2a 0.25)")
add("CO3_pov004", mos("n", co3=0.04, co8=0.29), "gate contact with poly overlap 0.04 (CO.3 0.07)")
add("CO4_cov004", mos("n", co4=0.04), "S/D contacts with COMP overlap 0.04 (CO.4 0.07)")
s = mos("n")
c = s["cd"][1]
s["m1d"] = ("m1", B(c.left - 0.30, c.bottom - 0.08, c.right, c.top + 0.08))
add("CO6_m1ov0", s, "drain contact: metal1 flush with the contact on one side, 0.08 on the others (CO.6)")
s = mos("n")
s["m1d"] = ("m1", B(c.left - 0.30, c.bottom - 0.06, c.right + 0.02, c.top + 0.06))
add("CO6_m1ov002", s, "drain contact: metal1 overlap 0.02 on one side, 0.06 on the adjacent sides (Magic CO.6 needs 0.04/0.06; KLayout CO.6b)")
add("CO7_c2g012", mos("n", c2g=0.12), "S/D contacts 0.12 from the gate (CO.7 0.15)")
add("CO8_pc2c014", mos("n", co8=0.14, co3=0.07), "gate contact 0.14 from COMP (CO.8 0.17)")
s = mos("n", W=0.8, Lg=0.5)
s["cx"] = ("cont", B(-0.11, 0.29, 0.11, 0.51)); s["m1x"] = ("m1", B(-0.19, 0.21, 0.19, 0.59))
add("CO10_cont_on_gate", s, "an extra contact on the gate over COMP (KLayout CO.10)")
s = ptap()
s["cx"] = ("cont", B(2, 0.19, 2.22, 0.41)); s["m1x"] = ("m1", B(1.92, 0.11, 2.30, 0.49))
add("CO11_cont_field", s, "a contact on field oxide under metal1, no COMP or poly (KLayout CO.11)")

# ---------------------------------------------------------------- implants
s = mos("n")
s["imp"] = ("np", grow(s["comp"][1], 0.10))
add("NP5a_ov010", s, "nfet NPLUS encloses COMP and gate by only 0.10 (KLayout NP.5a 0.23 / NP.5b 0.16)")
s = mos("n")
s["imp"] = ("np", s["comp"][1])
add("NP_flush", s, "nfet NPLUS exactly the COMP (KLayout NP.5a/NP.5b)")
s = mos("n")
del s["imp"]
add("NP_missing", s, "nfet with no NPLUS at all")
s = mos("n")
s["imp2"] = ("pp", grow(s["comp"][1], 0.23))
add("NPPP_both", s, "nfet covered by both NPLUS and PPLUS")
s = ptap(w=0.3, h=0.7, imp=0.02, cont=False)
add("PP1_w034", s, "PPLUS 0.34 wide around a 0.30 x 0.70 tap (KLayout PP.1 0.4, PP.8a 0.35um2)")
s = ptap(); s2 = ptap(x=1.2)
s.update({k + "2": v for k, v in s2.items()})
add("PP2_s028", s, "two tap PPLUS boxes 0.28 apart (KLayout PP.2 0.4)")
s = ptap(imp=0.0)
add("PP5_ov0", s, "tap PPLUS exactly the COMP (KLayout PP.5)")
s = mos("n", Lg=0.7, co8=0.40, mv=True)
del s["dg"]
add("DG_missing", s, "nfet drawn to 6V dimensions (L 0.7) with no DUALGATE")
s = mos("n", Lg=0.7, co8=0.40, mv=True)
bb = s["comp"][1] + s["tcomp"][1]
s["dg"] = ("dg", grow(bb, 0.10, 0.10) + grow(s["gate"][1], 0.10) + grow(s["gpad"][1], 0.10))
add("DG_small", s, "6V nfet with DUALGATE enclosing COMP and poly by only 0.10 (KLayout DV.6 0.24, DV.8 0.4)")
s = mos("n", Lg=0.7, co8=0.40, mv=True)
dgb = s["dg"][1]
s["dg"] = ("dg", B(dgb.left, dgb.bottom, 0.0, dgb.top))
add("DG_partial", s, "DUALGATE ends at the middle of the 6V nfet's gate (KLayout DV.7, PL.9)")

# ---------------------------------------------------------------- metal1
s = {"m": ("m1", B(0, 0, 0.20, 2))}
add("M1_1_w020", s, "metal1 0.20 wide (M1.1 0.23)")
s = {"m": ("m1", B(0, 0, 0.3, 2)), "m2": ("m1", B(0.5, 0, 0.8, 2))}
add("M1_2a_s020", s, "two metal1 lines 0.20 apart (M1.2a 0.23)")
s = {"m": ("m1", B(0, 0, 0.30, 0.40))}
add("M1_3_a012", s, "metal1 0.30 x 0.40 = 0.12 um2 (M1.3 0.1444)")
s = {"m": ("m1", B(0, 0, 11, 11)), "m2": ("m1", B(11.25, 0, 11.55, 11))}
add("M1_2b_wide", s, "metal1 11 x 11 with a line 0.25 away (M1.2b 0.30)")

# ---------------------------------------------------------------- via1
def v1cell(vx1, vy1, vx2, vy2, m1, m2):
    return {"v": ("v1", B(vx1, vy1, vx2, vy2)), "a": ("m1", m1), "b": ("m2", m2)}


big1 = B(-0.30, -0.30, 0.56, 0.56)
add("V1_1_s024", v1cell(0, 0, 0.24, 0.24, big1, big1), "via1 0.24 x 0.24 (V1.1 0.26)")
add("V1_1_b032", v1cell(0, 0, 0.32, 0.32, big1, big1), "via1 0.32 x 0.32 (V1.1 is exactly 0.26)")
s = v1cell(0, 0, 0.26, 0.26, B(-0.3, -0.3, 0.78, 0.56), B(-0.3, -0.3, 0.78, 0.56))
s["v2"] = ("v1", B(0.48, 0, 0.74, 0.26))
add("V1_2a_s022", s, "two via1 0.22 apart (V1.2a 0.26)")
# V1.3 (Vn.3 ii): where Metal1 overlaps Via1 by less than 0.04 on one side,
# the adjacent Metal1 edges must overlap it by 0.06. These overlap by 0.05.
# Metal1 is 0.36 high, so V1.3c (end of a Metal1 line under 0.34) does not apply.
add("V1_3_m1ov0", v1cell(0, 0, 0.26, 0.26, B(0.0, -0.05, 0.6, 0.31), big1),
    "via1: metal1 flush on one side, 0.05 on the adjacent sides (V1.3 0.06; Magic V1.3, KLayout V1.3d)")
add("V1_3_m1ov002", v1cell(0, 0, 0.26, 0.26, B(-0.02, -0.05, 0.6, 0.31), big1),
    "via1: metal1 overlap 0.02 on one side, 0.05 on the adjacent sides (V1.3 0.06; Magic V1.3, KLayout V1.3d)")
add("V1_4_m2ov0", v1cell(0, 0, 0.26, 0.26, big1, B(0.0, -0.2, 0.6, 0.46)),
    "via1: metal2 flush on one side (V1.4 0.01)")
s = {"a": ("m1", B(-0.2, -0.2, 2.0, 2.0)), "b": ("m2", B(-0.2, -0.2, 2.0, 2.0))}
for i in range(4):
    for j in range(4):
        s["v%d%d" % (i, j)] = ("v1", B(i * 0.52, j * 0.52, i * 0.52 + 0.26, j * 0.52 + 0.26))
add("V1_2b_4x4_s026", s, "4 x 4 via1 array at 0.26 spacing (KLayout V1.2b 0.36)")
s = {"a": ("m1", B(-0.2, -0.2, 2.2, 2.2)), "b": ("m2", B(-0.2, -0.2, 2.2, 2.2))}
for i in range(4):
    for j in range(4):
        s["v%d%d" % (i, j)] = ("v1", B(i * 0.56, j * 0.56, i * 0.56 + 0.26, j * 0.56 + 0.26))
add("V1_2b_4x4_s030", s, "4 x 4 via1 array at 0.30 spacing (KLayout V1.2b 0.36)")


# ---------------------------------------------------------------- more front end
s = ptap(w=1.6, h=1.6)
s["tc"] = ("cont", B(0.2, 0.2, 0.42, 0.42))
s["m1t"] = ("m1", B(0.1, 0.1, 1.5, 1.5))
for i in range(4):
    for j in range(4):
        s["c%d%d" % (i, j)] = ("cont", B(0.2 + i * 0.32, 0.2 + j * 0.32, 0.42 + i * 0.32, 0.42 + j * 0.32))
add("CO2b_4x4_s010", s, "4 x 4 contact array at 0.10 spacing in one tap (KLayout CO.2a/CO.2b)")
s = ptap(w=2.0, h=2.0)
s["m1t"] = ("m1", B(0.1, 0.1, 1.9, 1.9))
del s["tc"]
for i in range(4):
    for j in range(4):
        s["c%d%d" % (i, j)] = ("cont", B(0.15 + i * 0.48, 0.15 + j * 0.48, 0.37 + i * 0.48, 0.37 + j * 0.48))
add("CO2b_4x4_s026", s, "4 x 4 contact array at 0.26 spacing in one tap (KLayout CO.2b 0.28)")
s = mos("n")
del s["tcomp"], s["timp"], s["tc"], s["m1t"]
add("DF14_notap", s, "LV nfet with no substrate tap anywhere (KLayout DF.14_LV 20 um)")
s = mos("n", gap=25.0)
add("DF14_tap25", s, "LV nfet with its substrate tap 25 um away (KLayout DF.14_LV 20 um)")
s = mos("p")
nb = s["nwell"][1]
s["nwell"] = ("nwell", B(nb.left, nb.bottom, s["comp"][1].right + 0.5, nb.top))
del s["tcomp"], s["timp"], s["tc"], s["m1t"]
s["nwell"] = ("nwell", grow(s["comp"][1], 0.5))
add("DF13_nwnotap", s, "LV pfet in an nwell with no n-tap (KLayout DF.13_LV 20 um)")
# NP.3ci 0.16: NPLUS space to a PCOMP outside DNWELL that is less than 0.43
# from an Nwell (NP.3cii, 0.08, covers PCOMP farther away). The p-tap is
# narrowed to 0.22 x 1.4 without a contact (DF.1a 0.22, DF.9 0.2025), and an
# Nwell ends 0.17 to its left (DF.17 0.12), so that the whole tap is within
# 0.43 of the Nwell. The nfet's NPLUS stops 0.06 short of the tap; the tap's
# PPLUS keeps its 0.16 (PP.5dii), so the two implants overlap off COMP.
s = mos("n")
tx = s["comp"][1].left - 0.49
s["tcomp"] = ("comp", B(tx - 0.22, -0.4, tx, 1.0))
s["timp"] = ("pp", grow(s["tcomp"][1], 0.16))
del s["tc"], s["m1t"]
s["nwx"] = ("nwell", B(tx - 0.22 - 0.17 - 1.0, -0.8, tx - 0.22 - 0.17, 1.4))
s["imp"] = ("np", B(tx + 0.06, s["imp"][1].bottom, s["imp"][1].right, s["imp"][1].top))
add("NP3_s006", s, "nfet NPLUS 0.06 from a p-tap COMP that is 0.17 from an nwell (KLayout NP.3ci 0.16), "
    "overlapping the tap's PPLUS")
s = mos("n")
cb = s["comp"][1]
tb = s["tcomp"][1]
# butted tap: PCOMP abutting the nfet source on the left, implants split at the butting edge
s["tcomp"] = ("comp", B(cb.left - 0.6, 0, cb.left, 0.6))
s["timp"] = ("pp", B(cb.left - 0.6 - 0.16, -0.16, cb.left, 0.76))
s["imp"] = ("np", B(cb.left, cb.bottom - 0.23, cb.right + 0.23, cb.top + 0.23))
s["tc"] = ("cont", B(cb.left - 0.41, 0.19, cb.left - 0.19, 0.41))
s["m1t"] = ("m1", B(cb.left - 0.49, 0.11, s["m1s"][1].right, 0.49))
del s["m1s"]
add("BUTT_ok", s, "nfet with a butted p-tap at its source, implants split at the butting edge")
s2 = dict(s)
s2["cs"] = ("cont", B(cb.left - 0.11, 0.19, cb.left + 0.11, 0.41))
add("BUTT_straddle", s2, "butted tap with a contact straddling the NCOMP/PCOMP butting edge (KLayout CO.9)")
s = mos("p")
s6 = mos("p", Lg=0.55, co8=0.40, mv=True, tap=False)
for k, (l, b) in s6.items():
    if k in ("nwell",):
        continue
    s["mv_" + k] = (l, b.moved(db.DVector(3.0, 0)))
s["nwell"] = ("nwell", s["nwell"][1] + grow(s["mv_comp"][1], 0.65))
add("DV9_lvmv_nwell", s, "LV pfet and 6V pfet in one nwell (Magic and KLayout DV.9)")

# ---------------------------------------------------------------- grid
s = {"m": ("m1", B(0, 0, 1.0025, 1.0))}
add("GRID_m1_2p5nm", s, "metal1 box with one edge at x = 1.0025 um, off the 5 nm grid")


def _draw_table(shapes):
    def draw(d):
        for _, (layer, b) in shapes.items():
            d.box(layer, b.left, b.bottom, b.right, b.top)
    return draw


# The GAPS table does not say which control each cell changes, so none is named.
CASES = [(name, note, _draw_table(shapes), None) for name, (shapes, note) in T.items()]

# ---------------------------------------------------------------- hier
# The review's two-level cells (design-0.6.md 3.1): C_NMOS and C_PMOS with
# these layers moved into a parent cell.
HIER = {
    "base": ["C_NMOS", "C_PMOS"],
    "groups": {"imp": [(32, 0), (31, 0)], "nw": [(21, 0)], "all": [(32, 0), (31, 0), (21, 0), (55, 0)]},
    # "gate": the cells of the review's table; the other three were measured in the same run
    "expect": {
        "C_NMOS": ({}, {"nfet_03v3": 1}),
        "C_PMOS": ({}, {"pfet_03v3": 1}),
        "C_NMOS_imp_h": ({"Can't overlap those layers": 1, "PL.5a": 4, "DF.8": 5}, {}),
        "C_NMOS_all_h": ({"Can't overlap those layers": 1, "PL.5a": 4, "DF.8": 5}, {}),
        "C_PMOS_nw_h": ({"DF.1a": 6, "CO.4": 8, "DF.5": 12, "PL.4": 14, "FIXME": 8, "DF.9": 3, "DF.8": 8,
                         "DF.3a": 2, "DF.1c": 16}, {}),
        "C_PMOS_imp_h": ({}, {"pfet_03v3": 1}),
        "C_PMOS_all_h": ({}, {}),
        "C_NMOS_nw_h": ({}, {"nfet_03v3": 1}),
    },
    "gate": ["C_NMOS_imp_h", "C_NMOS_all_h", "C_PMOS_nw_h"],
}

# ---------------------------------------------------------------- whole_shape
def _dv9_long(d):
    """A 3.3 V pfet with its n-tap at the left end of a long n-well and a 6 V
    pfet (DUALGATE) about 95 um away at the right end: DV.9 ("Both LV and MV
    devices cannot be in the same N-well") is a whole-shape rule, because
    Magic's bad_nwell templayer grows both devices through the whole n-well
    with bloat-all (gf180mcuD.tech, cifoutput drc, templayer mv_nwell and
    bad_nwell; rule at 2726)."""
    s = mos("p")
    s6 = mos("p", Lg=0.55, co8=0.40, mv=True, tap=False)
    for k, (layer, b) in s.items():
        if k != "nwell":
            d.box(layer, b.left, b.bottom, b.right, b.top)
    for k, (layer, b) in s6.items():
        if k != "nwell":
            m = b.moved(db.DVector(95.0, 0))
            d.box(layer, m.left, m.bottom, m.right, m.top)
    nw = s["nwell"][1] + grow(s6["comp"][1].moved(db.DVector(95.0, 0)), 0.65)
    d.box("nwell", nw.left, nw.bottom, nw.right, nw.top)


WHOLE_SHAPE = [
    dict(name="dv9_long", draw=_dv9_long, targets=["DV.9"], expect={}, box=[90, -2, 100, 2],
         measured={"by": "Magic 8.3.681 in the pinned image, 2026-11-23", "drc(fast)": {}, "drc(full)": {},
                   "DV9_lvmv_nwell drc(full)": {"DV.9": 1}},
         notes="DV9_lvmv_nwell (GAPS-gf180mcuD 2: Magic drc(full) DV.9) stretched to a 100 um n-well. "
               "By the tech file, DV.9 reaches over the whole well, so an area check that holds only the 6 V "
               "pfet (`box`) would miss it. Measured in this build: Magic's own whole-cell drc(full) gives no "
               "DV.9 here, while it gives DV.9 x1 on DV9_lvmv_nwell (the two pfets 3 um apart); why is "
               "UNVERIFIED. Not measured by the GAPS or the review, so expect is empty. The review's other candidate, 'P-diffusion and N-ohmic must "
               "be over N-well' (tech:2799), is a local and-not (templayer missing_nwell, tech:1349) and has "
               "no whole-shape reach.",
         source="GAPS-gf180mcuD 2 (DV9_lvmv_nwell); design-0.6.md 3.1"),
]

# ---------------------------------------------------------------- names
NAMES_ERROR = ("m1", (0, 0, 0.20, 1.0), "M1.1")

# ---------------------------------------------------------------- inverters
INV_TOP = "inv"
SCHEMATIC = """.subckt {top} A Y VDD VSS
XM1 Y A VSS VSS nfet_03v3 L=0.28u W={wn}u
XM2 Y A VDD VDD pfet_03v3 L=0.28u W={wp}u
.ends
"""
SCH_W = {"wn": 0.6, "wp": 0.6}
Y0 = 2.6   # the pfet's origin; it is the C_PMOS cell mirrored in y


def _hand_inverter(labels=True, swap=False, open_drain=False):
    """Not in the GAPS: C_NMOS and C_PMOS (the gf180mcuD gap study's clean
    controls) joined into an inverter. The pfet is mirrored so that the two
    gate pads face each other, the pads are joined in metal1, and the drains
    by a metal1 strip on the right. Texts on 34/10."""
    n = mos("n")
    p = mos("p")
    mirror = db.DTrans(db.DTrans.M0, db.DVector(0, Y0))

    def draw(d):
        for _, (layer, b) in n.items():
            d.box(layer, b.left, b.bottom, b.right, b.top)
        for _, (layer, b) in p.items():
            m = b.transformed(mirror)
            d.box(layer, m.left, m.bottom, m.right, m.top)
        d.box("m1", -0.19, 0.77, 0.19, Y0 - 0.77)                 # A: gate pad to gate pad
        d.box("m1", 0.26, 0.11, 1.30, 0.49)                       # Y: nfet drain out to the right
        if open_drain:
            d.box("m1", 1.00, 0.95, 1.30, Y0 - 0.11)
        else:
            d.box("m1", 1.00, 0.11, 1.30, Y0 - 0.11)
        d.box("m1", 0.26, Y0 - 0.49, 1.30, Y0 - 0.11)             # ... into the pfet drain
        d.box("m1", -1.66, 0.11, -0.26, 0.49)                     # VSS: source to p-tap
        d.box("m1", -1.66, Y0 - 0.49, -0.26, Y0 - 0.11)           # VDD: source to n-tap
        if labels:
            a, y = (("Y", "A") if swap else ("A", "Y"))
            for s, x, yy in ((a, 0.0, Y0 / 2), (y, 1.15, Y0 / 2), ("VSS", -1.0, 0.3), ("VDD", -1.0, Y0 - 0.3)):
                d.text("m1txt", s, x, yy)
    return draw


def inverter_variants():
    return [
        ("inv", _hand_inverter(), "hand-drawn inverter from the C_NMOS and C_PMOS controls, texts on 34/10; "
         "measured in this build (not in the GAPS): Magic drc(fast) and drc(full) clean, extracts "
         "nfet_03v3 and pfet_03v3 on A, Y, VDD, VSS", {}, "GAPS-gf180mcuD 2 (C_NMOS, C_PMOS); the inverter itself is new"),
        ("inv_open_drain", _hand_inverter(open_drain=True), "the Y strip cut above the nfet drain", {}, ""),
        ("inv_swap", _hand_inverter(swap=True), "A and Y texts exchanged (build_inv.py lab10swap)", {}, ""),
        ("inv_no_text", _hand_inverter(labels=False), "no texts", {}, ""),
    ]


# ---------------------------------------------------------------- controls
CONTROLS = {
    "lib": "gf180mcu_fd_sc_mcu7t5v0",
    "cells": ["gf180mcu_fd_sc_mcu7t5v0__inv_1", "gf180mcu_fd_sc_mcu7t5v0__nand2_1",
              "gf180mcu_fd_sc_mcu7t5v0__dffq_1", "gf180mcu_fd_sc_mcu7t5v0__mux2_2",
              "gf180mcu_fd_sc_mcu7t5v0__filltie", "gf180mcu_fd_sc_mcu7t5v0__buf_1",
              "gf180mcu_fd_sc_mcu7t5v0__tieh"],
    "expect_f1": "no Magic-minus-user area on any implant or marker layer; on filltie Magic moved two "
                 "contact cuts (0.0077 um2 each way, an F5 item) (measured by the review in the image; "
                 "design-0.6.md 3.3)",
}


# ---------------------------------------------------------------- PCell inverter
def pcell_inverter(db_, ly):
    """gf180mcuD/scripts/build_inv.py, ports=lab10: the plugin's nfet_03v3 W 1
    and pfet_03v3 W 2, L 0.28, guard rings without full metal, wired in metal1."""
    top = ly.create_cell("inv_pcell")
    M1, M1L = ly.layer(34, 0), ly.layer(34, 10)

    def box(x1, y1, x2, y2, layer=M1):
        top.shapes(layer).insert(db_.DBox(x1, y1, x2, y2))

    nf = ly.create_cell("nfet_03v3", "gf180mcu_magic", {"w": 1.0, "l": 0.28, "botc": False, "full_metal": False})
    pf = ly.create_cell("pfet_03v3", "gf180mcu_magic", {"w": 2.0, "l": 0.28, "topc": False, "full_metal": False})
    y = 3.9
    top.insert(db_.DCellInstArray(nf.cell_index(), db_.DTrans(0, 0)))
    top.insert(db_.DCellInstArray(pf.cell_index(), db_.DTrans(db_.DVector(0, y))))
    box(-0.17, 0.545, 0.17, y - 1.045)
    box(0.285, -1.90, 0.515, -0.61)
    box(0.285, -1.90, 1.80, -1.67)
    box(1.57, -1.90, 1.80, y + 2.20)
    box(0.285, y + 1.97, 1.80, y + 2.20)
    box(0.285, y + 1.11, 0.515, y + 2.20)
    box(-0.975, -0.30, -0.285, -0.07)
    box(-0.975, y + 0.00, -0.285, y + 0.23)
    for s, x, yy in (("A", 0.0, 1.7), ("Y", 1.685, 2.0), ("VSS", -1.09, 0.4), ("VDD", -1.09, y + 0.8)):
        top.shapes(M1L).insert(db_.DText(s, x, yy))
    return top


PCELL_EXPECT = ({"netgen": "match uniquely", "klayout": {"lvs": "match"},
                 "magic": {"drc(fast)": {"M1.2a": 4}, "drc(full)": {"M1.2a": 4}}},
                "GAPS-gf180mcuD 5 (PCell inverter; M1.2a inside the device cells)")
PCELL_SCH_W = {"wn": 1, "wp": 2}

ANCHORS = {"PL4_e015": "PL.4"}
