"""ihp-sg13cmos5l cases. The gaps set is the ihp-sg13cmos5l gap study's
suite (GAPS-ihp-sg13cmos5l section 2): a clean LV
inverter with an n-tap and a p-tap, and variants that each add or change
one thing (m_ matched rules, u_ KLayout-only rules, g_ generated layers,
port_ label conventions). The table is that suite's, unchanged, so that
expect-ihp-sg13cmos5l.json still applies. A variant's top cell is its name
with '.' replaced by '_', as the suite wrote it.
"""

PDK = "ihp-sg13cmos5l"
SOURCE = "GAPS-ihp-sg13cmos5l 2"

LAYERS = {"nwell": (31, 0), "activ": (1, 0), "poly": (5, 0), "psd": (14, 0), "cont": (6, 0),
     "m1": (8, 0), "m1txt": (8, 25), "m1pin": (8, 2), "via1": (19, 0), "m2": (10, 0),
     "tgo": (44, 0), "sblk": (28, 0), "nsdb": (7, 21), "extb": (111, 0), "res": (24, 0),
     "polyres": (128, 0), "metal5_g2": (67, 0)}


def base():
    s = {}  # name -> (layer, [x1, y1, x2, y2]) or (layer, [[x,y],...]) polygon
    s["nwell"] = ("nwell", [-0.6, 1.8, 2.45, 3.8])
    s["n_act"] = ("activ", [0.0, 0.0, 1.0, 0.6])          # NMOS W 0.6
    s["p_act"] = ("activ", [0.0, 2.2, 1.0, 3.2])          # PMOS W 1.0
    s["p_psd"] = ("psd", [-0.3, 1.9, 1.3, 3.5])
    s["gate"] = ("poly", [0.435, -0.18, 0.565, 3.38])     # L 0.13
    s["g_pad"] = ("poly", [0.135, 1.05, 0.565, 1.35])
    s["g_ct"] = ("cont", [0.205, 1.12, 0.365, 1.28])
    s["ns_ct"] = ("cont", [0.07, 0.22, 0.23, 0.38])
    s["nd_ct"] = ("cont", [0.77, 0.22, 0.93, 0.38])
    s["ps_ct"] = ("cont", [0.07, 2.62, 0.23, 2.78])
    s["pd_ct"] = ("cont", [0.77, 2.62, 0.93, 2.78])
    # p-tap (substrate tie) and n-tap (well tie)
    s["pt_act"] = ("activ", [1.6, 0.0, 2.15, 0.55])
    s["pt_psd"] = ("psd", [1.45, -0.15, 2.3, 0.7])
    s["pt_ct"] = ("cont", [1.795, 0.195, 1.955, 0.355])
    s["nt_act"] = ("activ", [1.6, 2.5, 2.0, 2.9])
    s["nt_ct"] = ("cont", [1.72, 2.62, 1.88, 2.78])
    # metal1
    s["vss"] = ("m1", [-0.6, -0.8, 2.45, -0.5])
    s["vdd"] = ("m1", [-0.6, 3.7, 2.45, 4.0])
    s["ns_m1"] = ("m1", [0.02, -0.6, 0.28, 0.43])
    s["pt_m1"] = ("m1", [1.745, -0.6, 2.005, 0.405])
    s["ps_m1"] = ("m1", [0.02, 2.57, 0.28, 3.8])
    s["nt_m1"] = ("m1", [1.67, 2.57, 1.93, 3.8])
    s["y_m1"] = ("m1", [0.72, 0.17, 0.98, 2.83])
    s["a_m1"] = ("m1", [-0.3, 1.07, 0.415, 1.33])
    return s

LABELS = {"A": (0.0, 1.2), "Y": (0.85, 1.5), "VDD": (1.0, 3.85), "VSS": (1.0, -0.65)}
PINBOX = {"A": [-0.3, 1.07, 0.415, 1.33], "Y": [0.72, 1.3, 0.98, 1.7],
          "VDD": [0.8, 3.7, 1.2, 4.0], "VSS": [0.8, -0.8, 1.2, -0.5]}

def sq(x, y, a):
    return [x, y, x + a, y + a]

V = {}   # id -> (description, function(shapes) -> shapes, label mode)
def var(vid, desc, labels="txt"):
    def deco(f):
        V[vid] = (desc, f, labels)
        return f
    return deco

@var("base", "clean base inverter, texts on 8/25")
def _(s): return s

# ---- matched sample ----
@var("m_NW.a", "extra n-well 0.50 x 1.00 um (NW.a 0.62)")
def _(s): s["x"] = ("nwell", [3.5, 2.0, 4.0, 3.0]); return s
@var("m_NW.c", "n-well encloses PMOS Activ by 0.20 on the left (NW.c 0.31)")
def _(s): s["nwell"] = ("nwell", [-0.2, 1.8, 2.45, 3.8]); s["p_psd"] = ("psd", [-0.18, 1.9, 1.3, 3.5]); return s
@var("m_NW.d", "free N+ Activ 0.4 x 0.4 at 0.20 from the n-well (NW.d 0.31)")
def _(s): s["x"] = ("activ", [2.65, 2.0, 3.05, 2.4]); return s
@var("m_Act.c", "free NMOS: Activ 0.50 wide, gate leaves 0.20 / 0.17 of S/D (Act.c 0.23)")
def _(s):
    s["x1"] = ("activ", [4.0, 0.0, 4.5, 0.6]); s["x2"] = ("poly", [4.2, -0.18, 4.33, 0.78]); return s
@var("m_Gat.b", "poly strip 0.15 from the gate pad (Gat.b 0.18)")
def _(s): s["x"] = ("poly", [-0.145, 0.9, -0.015, 1.7]); return s
@var("m_Gat.c", "NMOS gate end cap 0.10 (Gat.c 0.18)")
def _(s): s["gate"] = ("poly", [0.435, -0.10, 0.565, 3.38]); return s
@var("m_Gat.e", "free poly 0.20 x 0.30 = 0.06 um2 (Gat.e 0.09)")
def _(s): s["x"] = ("poly", [4.0, 2.0, 4.2, 2.3]); return s
@var("m_Cnt.c", "NMOS source contact 0.03 from the Activ edge (Cnt.c 0.07)")
def _(s): s["ns_ct"] = ("cont", [0.03, 0.22, 0.19, 0.38]); return s
@var("m_M1.a", "free Metal1 0.12 x 1.0 (M1.a 0.16)")
def _(s): s["x"] = ("m1", [4.0, 1.0, 4.12, 2.0]); return s
@var("m_M1.d", "free Metal1 0.25 x 0.25 = 0.0625 um2 (M1.d 0.09)")
def _(s): s["x"] = ("m1", [4.0, 1.0, 4.25, 1.25]); return s
@var("m_V1.a", "Via1 0.15 x 0.15 with Metal1 and Metal2 0.6 x 0.6 (V1.a 0.19)")
def _(s):
    s["x1"] = ("m1", [4.0, 1.0, 4.6, 1.6]); s["x2"] = ("m2", [4.0, 1.0, 4.6, 1.6]); s["x3"] = ("via1", [4.225, 1.225, 4.375, 1.375]); return s
@var("m_LU.b", "no p-tap: NMOS 3.2 um from nothing (LU.b 20 um) -- tap removed")
def _(s):
    for k in ("pt_act", "pt_psd", "pt_ct", "pt_m1"): s.pop(k)
    return s

# ---- unmatched, student-reachable ----
@var("u_pSD.a", "free pSD strip 0.20 x 1.50 (pSD.a 0.31)")
def _(s): s["x"] = ("psd", [4.0, 1.0, 4.2, 2.5]); return s
@var("u_pSD.b", "second pSD box 0.20 right of the PMOS pSD (pSD.b 0.31)")
def _(s): s["x"] = ("psd", [1.5, 1.9, 2.1, 2.4]); return s   # 0.6x0.5, clear of n-tap Activ (x>=1.6? see note)
@var("u_pSD.k", "free pSD 0.40 x 0.40 = 0.16 um2 (pSD.k 0.25)")
def _(s): s["x"] = ("psd", [4.0, 1.0, 4.4, 1.4]); return s
@var("u_pSD.c", "PMOS pSD flush with the Activ in x (pSD.c 0.18)")
def _(s): s["p_psd"] = ("psd", [0.0, 1.9, 1.0, 3.5]); return s
@var("u_pSD.c1", "p-tap pSD flush with its Activ (pSD.c1 0.03)")
def _(s): s["pt_psd"] = ("psd", [1.6, 0.0, 2.15, 0.55]); return s
@var("u_pSD.d", "p-tap pSD 0.10 from the NMOS Activ (pSD.d 0.18)")
def _(s): s["pt_psd"] = ("psd", [1.1, -0.15, 2.3, 0.7]); return s
@var("u_pSD.i", "PMOS pSD overhangs the gate by 0.20 in y (pSD.i 0.30)")
def _(s): s["p_psd"] = ("psd", [-0.3, 2.0, 1.3, 3.4]); return s
@var("u_pSD.j", "free pSD 0.25 below the NMOS gate (pSD.j 0.30)")
def _(s): s["x"] = ("psd", [-0.2, -1.4, 1.2, -0.25]); return s
@var("u_NW.b1", "second n-well with its own tap (other net) 1.00 from the first (NW.b1 1.8)")
def _(s):
    s["x1"] = ("nwell", [3.45, 1.8, 4.45, 3.8]); s["x2"] = ("activ", [3.75, 2.6, 4.15, 3.0])
    s["x3"] = ("cont", [3.87, 2.72, 4.03, 2.88]); s["x4"] = ("m1", [3.82, 2.67, 4.08, 3.2]); return s
@var("u_Cnt.h", "n-tap contact with no Metal1 over it (Cnt.h / M1.c)")
def _(s): s.pop("nt_m1"); return s
@var("u_Cnt.g", "contact with Metal1 over field oxide, no Activ or poly (Cnt.g)")
def _(s): s["x1"] = ("cont", [4.07, 1.07, 4.23, 1.23]); s["x2"] = ("m1", [4.0, 1.0, 4.3, 1.3]); return s
@var("u_Cnt.j", "contact on the NMOS gate over Activ (Cnt.j)")
def _(s): s["x"] = ("cont", [0.42, 0.22, 0.58, 0.38]); return s
@var("u_Cnt.j2", "free NMOS L 0.40 with a contact and Metal1 on the gate over Activ (Cnt.j)")
def _(s):
    s["x1"] = ("activ", [4.0, 0.0, 5.0, 0.6]); s["x2"] = ("poly", [4.3, -0.18, 4.7, 0.78])
    s["x3"] = ("cont", [4.42, 0.22, 4.58, 0.38]); s["x4"] = ("m1", [4.37, 0.05, 4.63, 0.55]); return s
@var("u_Cnt.b1", "5 x 5 contact array at 0.18 on a 1.8 um p-tap (Cnt.b1 0.20)")
def _(s):
    s["x1"] = ("activ", [4.0, 0.0, 5.8, 1.8]); s["x2"] = ("psd", [3.9, -0.1, 5.9, 1.9]); s["x3"] = ("m1", [4.0, 0.0, 5.8, 1.8])
    for i in range(5):
        for j in range(5):
            s["c%d%d" % (i, j)] = ("cont", sq(4.14 + i * 0.34, 0.14 + j * 0.34, 0.16))
    return s
@var("u_V1.b1", "4 x 4 Via1 array at 0.22 (V1.b1 0.29)")
def _(s):
    s["x1"] = ("m1", [4.0, 0.0, 5.6, 1.6]); s["x2"] = ("m2", [4.0, 0.0, 5.6, 1.6])
    for i in range(4):
        for j in range(4):
            s["v%d%d" % (i, j)] = ("via1", sq(4.1 + i * 0.41, 0.1 + j * 0.41, 0.19))
    return s
@var("u_V1.noM2", "Via1 on Metal1 with no Metal2 (M2.c / V1 upper enclosure)")
def _(s): s["x1"] = ("m1", [4.0, 1.0, 4.6, 1.6]); s["x2"] = ("via1", [4.205, 1.205, 4.395, 1.395]); return s
@var("u_Pin.e", "Metal1 pin box (8/2) 0.2 past the Metal1 pad, texts on 8/25", labels="txt+pinbig")
def _(s): return s
@var("u_CntB", "bar contact 0.16 x 0.30 on a free n-diffusion (CntB.a1 0.34 etc.)")
def _(s):
    s["x1"] = ("activ", [4.0, 1.0, 4.6, 1.6]); s["x2"] = ("cont", [4.07, 1.15, 4.37, 1.31]); s["x3"] = ("m1", [4.02, 1.10, 4.42, 1.36]); return s
@var("u_Sal.a", "free SalBlock 0.30 x 1.0 (Sal.a 0.42)")
def _(s): s["x"] = ("sblk", [4.0, 1.0, 4.3, 2.0]); return s
@var("u_nSDB.a", "free nSD:block 0.20 x 1.0 (nSDB.a 0.31)")
def _(s): s["x"] = ("nsdb", [4.0, 1.0, 4.2, 2.0]); return s
@var("u_TGO.f", "free ThickGateOx 0.50 x 1.0 (TGO.f 0.86)")
def _(s): s["x"] = ("tgo", [4.0, 1.0, 4.5, 2.0]); return s
@var("u_forbid.M5", "a box on 67/0, sg13g2's Metal5 (CMOS5L.FORB.Metal5)")
def _(s): s["x"] = ("metal5_g2", [4.0, 1.0, 6.0, 3.0]); return s
@var("u_offgrid", "free Metal1 0.4 x 0.4 with one corner on a 1 nm grid point (Metal1_Offgrid)")
def _(s): s["x"] = ("m1", [4.001, 1.0, 4.401, 1.4]); return s
@var("u_angle.poly", "free poly with a 30-degree edge (x.2 / gatpoly Angle45)")
def _(s): s["x"] = ("poly", [[4.0, 1.0], [4.6, 1.0], [4.6, 1.6], [4.0, 1.25]]); return s


# ---- generated / derived layers (section 3) ----
@var("g_nopsd_pmos", "PMOS drawn with no pSD at all")
def _(s): s.pop("p_psd"); return s
@var("g_psd_half", "PMOS pSD stops at x 0.70: the drain's right part has no pSD")
def _(s): s["p_psd"] = ("psd", [-0.3, 1.9, 0.7, 3.5]); return s
@var("g_psd_on_nmos", "pSD drawn over the NMOS as well")
def _(s): s["x"] = ("psd", [-0.3, -0.3, 1.3, 0.9]); return s

def hv(s, tgo):
    s["h1"] = ("activ", [4.0, 0.0, 5.25, 0.6]); s["h2"] = ("poly", [4.4, -0.18, 4.85, 0.78])
    s["h3"] = ("cont", [4.07, 0.22, 4.23, 0.38]); s["h4"] = ("cont", [5.02, 0.22, 5.18, 0.38])
    s["h5"] = ("m1", [4.02, 0.05, 4.28, 0.55]); s["h6"] = ("m1", [4.97, 0.05, 5.23, 0.55])
    if tgo:
        s["h7"] = ("tgo", tgo)
    return s
@var("g_hv_ok", "extra NMOS L 0.45 with ThickGateOx drawn to the rules (TGO.a 0.27, TGO.c 0.34)")
def _(s): return hv(s, [3.66, -0.34, 5.59, 0.94])
@var("g_hv_notgo", "the same NMOS L 0.45 with no ThickGateOx")
def _(s): return hv(s, None)
@var("g_hv_tgo_small", "the same NMOS with ThickGateOx only 0.10 past the Activ")
def _(s): return hv(s, [3.9, -0.28, 5.35, 0.88])

# port variants (section 4)
for lab, d in (("lbl", "texts on 8/1 (Metal1.label) only"), ("txt", "texts on 8/25 only"), ("m1", "texts on 8/0 only"), ("pin", "texts on 8/2, no pin box"),
               ("txt+pin", "texts on 8/25 plus pin boxes on 8/2"), ("pin+box", "texts on 8/2 plus pin boxes on 8/2")):
    V["port_" + lab.replace("+", "_")] = ("ports: " + d, lambda s: s, lab)


def draw_variant(vid, d, shapes=None, lab=None, labels=LABELS, pinbox=PINBOX):
    """gen_variants.py build(): the variant's shapes, then its labels."""
    desc, f, mode = V[vid] if vid in V else ("", None, "txt")
    lab = lab or mode
    s = shapes if shapes is not None else f(base())
    for name, (lay, g) in s.items():
        d.shape(lay, g)
    for name, (x, y) in labels.items():
        if lab in ("txt", "txt+pinbig", "txt+pin"):
            d.text("m1txt", name, x, y)
        if lab == "m1":
            d.text("m1", name, x, y)
        if lab == "lbl":
            d.text("m1lbl", name, x, y)
        if lab in ("pin", "pin+box"):
            d.text("m1pin", name, x, y)
        if lab in ("txt+pin", "pin+box"):
            d.box("m1pin", *pinbox[name])
        if lab == "txt+pinbig" and name == "A":
            b = pinbox[name]
            d.box("m1pin", b[0] - 0.2, b[1], b[2], b[3])


LAYERS["m1lbl"] = (8, 1)
SOURCES = {}
for _vid in V:
    if _vid.startswith("g_"):
        SOURCES[_vid] = "GAPS-ihp-sg13cmos5l 3"
    elif _vid.startswith("port_"):
        SOURCES[_vid] = "GAPS-ihp-sg13cmos5l 4"
CASES = [(vid, V[vid][0], (lambda v: lambda d: draw_variant(v, d))(vid), None if vid == "base" else "base")
         for vid in V]
# A variant targets the rule in its name (tests/cases/build.py), except where
# no row of the gap table has that name: u_angle.poly's 30-degree poly edge
# breaks Magic's x.2 and KLayout's gatpoly_drw_Angle45, which the table joins
# as grid.Angle45 (tests/gaps/aliases-ihp-sg13cmos5l.json).
RULE_OF = {"u_angle.poly": "grid.Angle45"}


# ---------------------------------------------------------------- hier
# The review's two-level cells (design-0.6.md 3.1): the base with these
# layers moved into a parent cell.
HIER = {
    "base": ["base"],
    "groups": {"psd": [(14, 0)], "nw": [(31, 0)], "all": [(14, 0), (31, 0), (44, 0)]},
    "expect": {
        "base": ({}, {"sg13_lv_nmos": 1, "sg13_lv_pmos": 1}),
        "base_psd_h": ({"NW.d": 11, "LU.b": 3}, {"sg13_lv_nmos": 1}),
        "base_nw_h": ({"Can't overlap those layers": 3, "NW.d": 5, "NW.f": 17}, {"sg13_lv_nmos": 1}),
        "base_all_h": ({"Can't overlap those layers": 3, "NW.d": 12, "LU.b": 6}, {"sg13_lv_nmos": 2}),
    },
    "gate": ["base_psd_h", "base_nw_h", "base_all_h"],
}


# ---------------------------------------------------------------- whole_shape
def _lu_long(d):
    """As on ihp-sg13g2: a 100 x 3 um n-well with one contacted n-tap at its
    left end and a PMOS 15 um from it, inside LU.a's 20 um."""
    d.box("nwell", 0, 0, 100, 3)
    d.box("activ", 0.8, 1.2, 1.2, 1.6)
    d.box("cont", 0.92, 1.32, 1.08, 1.48)
    d.box("m1", 0.87, 1.27, 1.13, 1.65)
    x = 15.0
    d.box("activ", x, 1.0, x + 1.0, 2.0)                  # PMOS W 1.0
    d.box("psd", x - 0.3, 0.7, x + 1.3, 2.3)
    d.box("poly", x + 0.435, 0.82, x + 0.565, 2.18)        # L 0.13, end caps 0.18
    for cx in (x + 0.07, x + 0.77):
        d.box("cont", cx, 1.42, cx + 0.16, 1.58)
        d.box("m1", cx - 0.05, 1.0, cx + 0.21, 2.0)


WHOLE_SHAPE = [
    dict(name="lu_long", draw=_lu_long, targets=["LU.a"], expect={}, box=[14, -1, 17, 4],
         measured={"by": "Magic 8.3.681 in the pinned image, 2026-11-23", "drc(full)": {}},
         notes="Magic's whole-cell check finds no LU.a (measured in this build); an area check of `box` that does not reach the "
               "tap 14 um away would. Not measured by the GAPS or the review, so expect is empty. LU.a is "
               "full only (GAPS-ihp-sg13cmos5l 1, drc:117).",
         source="GAPS-ihp-sg13cmos5l 1 (LU.a); design-0.6.md 3.1"),
]

# ---------------------------------------------------------------- names
NAMES_ERROR = ("m1", (0, 0, 0.12, 1.0), "M1.a")

# ---------------------------------------------------------------- inverters
INV_TOP = "inv"
SCHEMATIC = """.subckt {top} A Y VDD VSS
XN0 Y A VSS VSS sg13_lv_nmos w={wn}u l=0.13u ng=1 m=1
XP0 Y A VDD VDD sg13_lv_pmos w={wp}u l=0.13u ng=1 m=1
.ends
"""
SCH_W = {"wn": 0.6, "wp": 1.0}


def _inv(change=None, swap=False, labels="txt+pin"):
    def draw(d):
        s = base()
        s.update(change or {})
        lab, box = dict(LABELS), dict(PINBOX)
        if swap:
            lab["A"], lab["Y"] = LABELS["Y"], LABELS["A"]
            box["A"], box["Y"] = PINBOX["Y"], PINBOX["A"]
        draw_variant("inv", d, s, lab=labels, labels=lab, pinbox=box)
    return draw


def inverter_variants():
    return [
        ("inv", _inv(), "the base inverter with texts on 8/25 over 8/2 pin boxes (port_txt_pin)",
         {"netgen": "match uniquely", "klayout": {"lvs": "match"}}, "GAPS-ihp-sg13cmos5l 5 (port_txt_pin)"),
        ("inv_open_drain", _inv(change={"y_m1": ("m1", [0.72, 1.25, 0.98, 2.83]),
                                        "y_m1b": ("m1", [0.72, 0.17, 0.98, 0.95])}),
         "the Y Metal1 cut above the NMOS drain", {}, ""),
        ("inv_swap", _inv(swap=True), "A and Y labels exchanged", {}, ""),
        ("inv_no_text", _inv(labels="none"), "no labels", {}, ""),
    ]


# ---------------------------------------------------------------- controls
CONTROLS = {
    "lib": "sg13cmos5l_stdcell",
    "cells": ["sg13cmos5l_inv_1", "sg13cmos5l_nand2_1", "sg13cmos5l_dfrbp_1", "sg13cmos5l_mux2_1",
              "sg13cmos5l_tiehi", "sg13cmos5l_buf_1", "sg13cmos5l_decap_4"],
    "expect_f1": "no Magic-minus-user area on any implant or marker layer (measured by the review in "
                 "the image)",
}


# ---------------------------------------------------------------- PCell inverter
def pcell_inverter(db, ly):
    """ihp-sg13cmos5l/tests/pcell/build_inv.py: the plugin's sg13_lv_nmos W 0.6
    and sg13_lv_pmos W 1.0 (guard 0, no Via1 stubs, one gate contact each),
    a subconn PCell as the p-tap, a hand-drawn n-tap, Metal1 wiring, texts on
    8/25 over 8/2 boxes."""
    import klayout_magic_pcells as kmp
    top = ly.create_cell("inv_pcell")

    def pc(dev, p, x, y):
        v = kmp.dialog_values(dev, p, pdk=PDK) if dev.startswith("sg13") else p
        c = ly.create_cell(dev, "sg13cmos5l_magic", v)
        top.insert(db.DCellInstArray(c.cell_index(), db.DTrans(x, y)))

    def box(l, d, b):
        top.shapes(ly.layer(l, d)).insert(db.DBox(*b))

    y0 = 2.0
    pc("sg13_lv_nmos", {"w": 0.6, "l": 0.13, "guard": 0, "viasrc": "0", "viadrn": "0", "viagate": "0", "botc": 0}, 0, 0)
    pc("sg13_lv_pmos", {"w": 1.0, "l": 0.13, "guard": 0, "viasrc": "0", "viadrn": "0", "viagate": "0", "topc": 0}, 0, y0)
    pc("subconn", {"w": 1.0, "h": 0.3}, 0.6, -1.2)
    m1 = (8, 0)
    for b in ([-1.2, -1.2, 1.8, -0.9], [-1.2, 3.2, 1.8, 3.5], [0.125, -1.2, 0.385, -0.2],
              [0.125, y0 + 0.4, 0.385, 3.5], [-0.13, 0.345, 0.13, y0 - 0.545], [-1.0, -0.325, -0.125, -0.065],
              [-1.0, -0.325, -0.74, y0 + 0.525], [-1.0, y0 + 0.265, -0.125, y0 + 0.525]):
        box(*m1, b)
    box(31, 0, [-1.2, 1.2, 1.8, 3.6])
    box(1, 0, [1.0, 2.9, 1.4, 3.3])
    box(6, 0, [1.12, 3.02, 1.28, 3.18])
    box(*m1, [1.07, 2.97, 1.33, 3.5])
    for name, (x, y), b in (("A", (0.0, 0.9), [-0.13, 0.7, 0.13, 1.1]), ("Y", (-0.87, 1.0), [-1.0, 0.8, -0.74, 1.2]),
                            ("VDD", (1.5, 3.35), [1.3, 3.2, 1.7, 3.5]), ("VSS", (1.5, -1.05), [1.3, -1.2, 1.7, -0.9])):
        top.shapes(ly.layer(8, 25)).insert(db.DText(name, db.DTrans(x, y)))
        box(8, 2, b)
    return top


PCELL_EXPECT = ({"netgen": "match uniquely", "klayout": {"lvs": "no match (flat, the default)"},
                 "magic": {"drc(fast)": {}, "drc(full)": {}, "drc(routing)": {}}},
                "GAPS-ihp-sg13cmos5l 5 (pinv)")
PCELL_SCH_W = {"wn": 0.6, "wp": 1.0}

ANCHORS = {"m_Gat.c": "Gat.c"}
