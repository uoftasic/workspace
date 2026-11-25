"""sky130A cases. The gaps set is the sky130A gap study's one-change suite
(GAPS-sky130A section 2.1 and 2.2, batch A and batch E): one change each to
the clean hand-drawn inverter, and standalone structures paired with a
control drawn at the legal value. The tables below are that suite's, with
the changes of 0.6.1: a check against SkyWater's published rules found
cases that did not break the rule they were filed under. Four were redrawn
(s_m1_adj_mcon, s_via_m1_adj, s_m1_wide_space, e_butt_short), two filed
under the rule they break (s_li_45deg, c_pc_to_pdiff), and two that break
no published rule target none (d_tap_area, e_ntap_area). One case was
added for met1.3b: s_m1_huge_space, with the shapes that s_m1_wide_space
had before 0.6.1. The comments at those cases cite the rule pages of
google/skywater-pdk at 7198cf6 (docs/rules/periphery-rules.rst,
errors.csv, assumptions/07-other.csv). The redrawn and added cases'
entries in expect-sky130A.json are from the gap table's runs of 0.6.1,
and SOURCES says so; every other case keeps the study's geometry and its
entry.
"""

PDK = "sky130A"
SOURCE = "GAPS-sky130A 2.2"
_CHANGED = ("GAPS-sky130A 2.2, changed in 0.6.1 after a check against google/skywater-pdk 7198cf6; "
            "expect measured on the new shapes with Magic 8.3.681 and KLayout 0.30.11 in the pinned image, 2026-11-24")
SOURCES = {n: _CHANGED for n in ("s_m1_adj_mcon", "s_m1_adj_mcon_ok", "s_via_m1_adj", "s_via_m1_adj_ok",
                                 "s_m1_wide_space", "s_m1_wide_space_ok", "e_butt_short",
                                 "s_m1_huge_space", "s_m1_huge_space_ok")}

LAYERS = {
    "nwell": (64, 20), "dnwell": (64, 18), "diff": (65, 20), "tap": (65, 44), "psdm": (94, 20),
    "nsdm": (93, 44), "hvtp": (78, 44), "lvtn": (125, 44), "hvi": (75, 20), "poly": (66, 20),
    "licon": (66, 44), "npc": (95, 20), "li": (67, 20), "mcon": (67, 44), "met1": (68, 20),
    "via": (68, 44), "met2": (69, 20), "li.label": (67, 5), "li.pin": (67, 16),
    "met1.label": (68, 5), "met1.pin": (68, 16), "met2.pin": (69, 16), "met2.label": (69, 5),
}

# The clean inverter: name -> (layer, box), with pin boxes under its texts.
INV = {
    "nwell": ("nwell", (0.00, 3.00, 3.00, 6.00)),
    "rail_gnd": ("met1", (0.00, 0.00, 3.00, 0.40)),
    "rail_pwr": ("met1", (0.00, 5.60, 3.00, 6.00)),
    "ptap": ("tap", (0.40, 0.35, 2.60, 0.85)),
    "ptap_psdm": ("psdm", (0.275, 0.225, 2.725, 0.975)),
    "ntap": ("tap", (0.40, 5.05, 2.60, 5.55)),
    "ntap_nsdm": ("nsdm", (0.275, 4.925, 2.725, 5.675)),
    "ptap_licon": ("licon", (0.55, 0.52, 0.72, 0.69)),
    "ntap_licon": ("licon", (0.55, 5.22, 0.72, 5.39)),
    "gnd_mcon": ("mcon", (0.55, 0.13, 0.72, 0.30)),
    "pwr_mcon": ("mcon", (0.55, 5.70, 0.72, 5.87)),
    "ndiff": ("diff", (0.40, 1.30, 2.60, 1.95)),
    "ndiff_nsdm": ("nsdm", (0.275, 1.175, 2.725, 2.075)),
    "pdiff": ("diff", (0.40, 3.50, 2.60, 4.50)),
    "pdiff_psdm": ("psdm", (0.275, 3.375, 2.725, 4.625)),
    "hvtp": ("hvtp", (1.17, 3.32, 1.68, 4.68)),
    "gate": ("poly", (1.35, 1.05, 1.50, 4.75)),
    "pad": ("poly", (1.20, 2.30, 1.65, 2.75)),
    "npc": ("npc", (1.24, 2.34, 1.61, 2.71)),
    "ns_licon": ("licon", (0.55, 1.55, 0.72, 1.72)),
    "nd_licon": ("licon", (2.28, 1.55, 2.45, 1.72)),
    "ps_licon": ("licon", (0.55, 3.90, 0.72, 4.07)),
    "pd_licon": ("licon", (2.28, 3.90, 2.45, 4.07)),
    "g_licon": ("licon", (1.34, 2.44, 1.51, 2.61)),
    "li_gnd": ("li", (0.45, 0.05, 0.82, 1.82)),
    "li_y": ("li", (2.18, 1.45, 2.55, 4.17)),
    "li_pwr": ("li", (0.45, 3.80, 0.82, 5.95)),
    "li_a": ("li", (1.24, 2.34, 1.61, 2.71)),
    "pin_a": ("li.pin", (1.30, 2.40, 1.55, 2.65)),
    "pin_y": ("li.pin", (2.25, 2.60, 2.50, 2.85)),
    "pin_pwr": ("met1.pin", (1.20, 5.70, 1.45, 5.95)),
    "pin_gnd": ("met1.pin", (1.20, 0.05, 1.45, 0.30)),
}
INV_TEXT = {"A": ("li.label", 1.425, 2.525), "Y": ("li.label", 2.375, 2.725),
            "VPWR": ("met1.label", 1.325, 5.825), "VGND": ("met1.label", 1.325, 0.175)}

INV_E = dict(INV, ndiff_nsdm=("nsdm", (0.40, 1.175, 2.725, 2.075)))   # batch E: nsdm starts at the butting edge

CASES = []   # (name, description, draw(Drawing), control)


def _inverter_draw(base, change=None, add=(), drop=(), text=None):
    def draw(d):
        boxes = dict(base)
        for k, v in (change or {}).items():
            boxes[k] = (boxes[k][0], v)
        for k in drop:
            boxes.pop(k)
        for layer, b in boxes.values():
            d.shape(layer, b)
        for layer, b in add:
            d.shape(layer, b)
        tx = dict(INV_TEXT)
        for k, v in (text or {}).items():
            if v is None:
                tx.pop(k, None)
            else:
                tx[k] = v
        for s, (layer, x, y) in tx.items():
            d.text(layer, s, x, y)
    return draw


def inverter(cid, desc, change=None, add=(), drop=(), text=None, control="inv_base", **_):
    """One change to the clean inverter."""
    CASES.append((cid, desc, _inverter_draw(INV, change, add, drop, text), control))


def inverter_e(cid, desc, change=None, add=(), drop=(), text=None, control="e_inv_base", **_):
    """One change to batch E's inverter."""
    CASES.append((cid, desc, _inverter_draw(INV_E, change, add, drop, text), control))


def shapes(cid, desc, items, control=None):
    def draw(d):
        for layer, b in items:
            d.shape(layer, b)
    CASES.append((cid, desc, draw, control))


def pair(cid, desc, bad, good, **_):
    shapes(cid + "_ok", desc + " [control, legal value]", good)
    shapes(cid, desc, bad, control=cid + "_ok")


# ---------------------------------------------------------------- inverter cases
inverter("inv_base", "clean hand-drawn inverter (control for every inverter case)", control=None)

# anchors: six variants of an earlier review, rebuilt with the same edits
# (GAPS-sky130A 2.1); anchor is the variant's name there
inverter("a_poly8", "gate poly ends 0.05 past the n-diffusion (poly.8 wants 0.13)",
         change={"gate": (1.35, 1.25, 1.50, 4.75)}, anchor="v_poly8")
inverter("a_licon8", "poly pad 0.25 square around the gate licon (licon.8 0.05, licon.8a 0.08)",
         change={"pad": (1.30, 2.40, 1.55, 2.65)}, anchor="v_licon8")
inverter("a_licon11", "NMOS source licon 0.02 from the gate (licon.11 0.055)",
         change={"ns_licon": (1.16, 1.55, 1.33, 1.72)}, anchor="v_licon11")
inverter("a_no_npc", "no npc around the gate licon", drop=["npc"], anchor="v_no_npc")
inverter("a_no_nsdm", "no nsdm over the NMOS diffusion", drop=["ndiff_nsdm"], anchor="v_no_nsdm")
inverter("a_nsdm_flush", "nsdm over the NMOS equal to the diffusion (0 enclosure; nsd.5a wants 0.125)",
         change={"ndiff_nsdm": (0.40, 1.30, 2.60, 1.95)}, anchor="v_nsdm_flush")

# wells
inverter("w_nwell_encl_pdiff", "nwell encloses the PMOS diffusion by 0.10 at the bottom (diff/tap.8 0.18)",
         change={"nwell": (0.00, 3.40, 3.00, 6.00)})
inverter("w_ndiff_to_nwell", "nwell 0.25 from the NMOS diffusion (diff/tap.9 0.34)",
         change={"nwell": (0.00, 2.20, 3.00, 6.00)})
inverter("w_nwell_encl_ntap", "nwell encloses the n-tap by 0.05 at the top (diff/tap.10 0.18)",
         change={"nwell": (0.00, 3.00, 3.00, 5.60)})
inverter("w_no_ntap_licon", "n-tap without its licon (nwell.4, licon.16)", drop=["ntap_licon"])
inverter("w_no_ntap", "no n-tap at all (nwell.4, LU.3)", drop=["ntap", "ntap_nsdm", "ntap_licon"])
inverter("w_no_ptap", "no p-tap at all (LU.2)", drop=["ptap", "ptap_psdm", "ptap_licon"])
inverter("w_no_ptap_licon", "p-tap without its licon (licon.16)", drop=["ptap_licon"])
inverter("w_no_nwell", "no nwell at all under the PMOS and n-tap",
         drop=["nwell"])

# diffusion / tap
inverter("d_gate_w036", "NMOS W = 0.36 (diff/tap.2: transistor width 0.42)",
         change={"ndiff": (0.40, 1.30, 2.60, 1.66), "ndiff_nsdm": (0.275, 1.175, 2.725, 1.785),
                 "ns_licon": (0.55, 1.395, 0.72, 1.565), "nd_licon": (2.28, 1.395, 2.45, 1.565),
                 "li_y": (2.18, 1.30, 2.55, 4.17)})
inverter("d_sd_020", "NMOS drain side 0.20 long, no drain contact (poly.7: S/D 0.25)",
         change={"ndiff": (0.40, 1.30, 1.70, 1.95)}, drop=["nd_licon"])
# The manual's n/psd.10b is the psdm's area, 0.255 um^2 (periphery-rules.rst:1500-1504); a contacted
# tap in a psdm at the minimum 0.125 enclosure has 0.66 x 0.42 = 0.277 um^2 of it, so no such tap
# breaks the rule. Magic checks the tap's own area instead. The case targets no rule: Magic's
# report on it is one the manual does not support.
inverter("d_tap_area", "p-tap 0.41 x 0.17 around its licon, area 0.0697 um^2, in a 1.84 um^2 psdm: "
         "legal by the manual; Magic's p-tap area rule psd.10b 0.07011 reports it",
         change={"ptap": (0.43, 0.52, 0.84, 0.69)})
inverter("d_tap_w014", "0.14-wide finger on the p-tap (diff/tap.1 0.15)",
         add=[("tap", (2.60, 0.50, 2.90, 0.64)), ("psdm", (2.725, 0.225, 3.05, 0.975))])
inverter("d_diff_space", "extra n-diffusion 0.26 from the NMOS (diff/tap.3 0.27)",
         add=[("diff", (2.86, 1.30, 3.30, 1.95)), ("nsdm", (2.725, 1.175, 3.425, 2.075))])
inverter("d_both_implants", "psdm added over the NMOS diffusion (nsdm and psdm both)",
         add=[("psdm", (0.275, 1.175, 2.725, 2.075))])
inverter("d_nsdm_half", "nsdm covers only the left half of the NMOS diffusion",
         change={"ndiff_nsdm": (0.275, 1.175, 1.20, 2.075)})
inverter("d_diff_45", "NMOS drain corner cut at 45 degrees (x.2: 90 degree only)",
         change={"ndiff": (0.40, 1.30, 2.40, 1.95)},
         add=[("diff", ((2.40, 1.30), (2.60, 1.30), (2.60, 1.75), (2.40, 1.95)))])

# poly
inverter("p_field_to_diff", "gate pad 0.05 from the NMOS diffusion (poly.4 0.075)",
         change={"pad": (1.20, 2.00, 1.65, 2.75)})
inverter("p_extra_space", "extra poly line 0.20 from the gate (poly.2 0.21)",
         add=[("poly", (1.70, 2.85, 1.85, 3.30))])
inverter("p_poly_to_tap", "poly strip 0.05 from the p-tap (poly.5 0.055)",
         add=[("poly", (2.65, 0.35, 2.80, 0.85))])
inverter("p_gate_l014", "gate L = 0.14 (poly.1a 0.15)",
         change={"gate": (1.35, 1.05, 1.49, 4.75)})

# licon
inverter("c_ndiff_encl0", "NMOS source licon flush with the diffusion edge (licon.5a 0.04)",
         change={"ns_licon": (0.40, 1.55, 0.57, 1.72), "li_gnd": (0.32, 0.05, 0.82, 1.82)})
inverter("c_licon_out", "NMOS source licon 0.05 outside the diffusion",
         change={"ns_licon": (0.35, 1.55, 0.52, 1.72), "li_gnd": (0.27, 0.05, 0.82, 1.82)})
inverter("c_tap_encl", "p-tap licon enclosed by 0.07 on all sides (licon.7: 0.12 in one direction)",
         change={"ptap": (0.48, 0.45, 0.79, 0.76)})
# licon.9: "Spacing, no overlap, between poly_licon and psdm", 0.110 (periphery-rules.rst:1611-1615).
# The psdm edge is at y 3.375, 0.065 above the licon. Magic checks the rule as 0.235 to the
# p-diffusion, licon.9 plus the 0.125 psdm enclosure it regenerates; the drawn psdm encloses
# the diffusion by exactly 0.125, so psd.5a holds.
inverter("c_pc_to_pdiff", "gate licon 0.065 from the PMOS psdm, 0.19 from its diffusion (licon.9 0.11)",
         change={"pad": (1.20, 3.00, 1.65, 3.40), "npc": (1.24, 3.04, 1.61, 3.41),
                 "g_licon": (1.34, 3.14, 1.51, 3.31), "li_a": (1.24, 3.04, 1.61, 3.41),
                 "pin_a": (1.30, 3.10, 1.55, 3.35)},
         text={"A": ("li.label", 1.425, 3.225)})
inverter("c_pc_to_diff", "gate licon 0.16 from the NMOS diffusion (licon.14 0.19)",
         change={"pad": (1.20, 2.06, 1.65, 2.51), "npc": (1.24, 2.01, 1.61, 2.38),
                 "g_licon": (1.34, 2.11, 1.51, 2.28), "li_a": (1.24, 2.01, 1.61, 2.38),
                 "pin_a": (1.30, 2.07, 1.55, 2.32)},
         text={"A": ("li.label", 1.425, 2.195)})
inverter("c_licon_016", "gate licon 0.16 square (licon.1: 0.17)",
         change={"g_licon": (1.345, 2.445, 1.505, 2.605)})
inverter("c_licon_020", "gate licon 0.20 square (licon.1 is exact 0.17 in KLayout)",
         change={"g_licon": (1.325, 2.425, 1.525, 2.625)})
inverter("c_licon_space", "second NMOS drain licon 0.16 from the first (licon.2 0.17)",
         add=[("licon", (1.95, 1.55, 2.12, 1.72))], change={"li_y": (1.87, 1.45, 2.55, 4.17)})
inverter("c_licon_gate", "NMOS drain licon straddling the gate edge (licon.17, licon.11)",
         change={"nd_licon": (1.42, 1.55, 1.59, 1.72)}, add=[("li", (1.34, 1.45, 2.55, 1.82))])
inverter("c_npc_narrow", "npc only 0.04 beyond the gate licon: 0.25 wide (npc.1 0.27)",
         change={"npc": (1.30, 2.40, 1.55, 2.65)})
inverter("c_npc_over_dlicon", "npc stretched over the NMOS drain licon (licon.13)",
         change={"npc": (1.24, 1.45, 2.55, 2.71)})
inverter("c_no_li_over_licon", "NMOS drain licon with no li over it",
         change={"li_y": (2.18, 1.80, 2.55, 4.17)})

# implants and markers
inverter("i_hvtp_w030", "hvtp 0.30 wide over the PMOS gate (hvtp.1 0.38)",
         change={"hvtp": (1.27, 3.32, 1.57, 4.68)})
inverter("i_hvtp_half", "hvtp covers only the lower half of the PMOS gate",
         change={"hvtp": (1.17, 3.32, 1.68, 4.00)})
inverter("i_psdm_space", "psdm of the PMOS and an extra psdm strip 0.30 apart (psdm spacing 0.38)",
         add=[("psdm", (3.025, 3.375, 3.425, 4.625))])
inverter("i_nsdm_narrow", "extra nsdm strip 0.30 wide, nothing under it (nsdm width 0.38)",
         add=[("nsdm", (3.20, 2.30, 3.50, 2.80))])
inverter("i_lvtn_straddle", "lvtn 0.30 wide straddling the nwell edge, away from devices",
         add=[("lvtn", (2.70, 2.80, 3.00, 3.20))])

# li / mcon / met1 (inverter)
inverter("l_li_encl", "li over the gate licon trimmed to 0.25 square (li.5)",
         change={"li_a": (1.30, 2.40, 1.55, 2.65)})
inverter("l_no_li_under_mcon", "VGND li stops short: mcon on the rail has no li under it",
         change={"li_gnd": (0.45, 0.40, 0.82, 1.82)})
inverter("l_pin_only_li", "A's li drawn only on li1.pin (67/16), no li1.drawing under it",
         drop=["li_a"], change={"pin_a": (1.24, 2.34, 1.61, 2.71)})

# ---------------------------------------------------------------- standalone cases
# standalone shapes start at the origin of their own cell
pair("s_li_w016", "li 0.16 x 1.0 (li.1 0.17)", [("li", (0, 0, 0.16, 1.0))], [("li", (0, 0, 0.17, 1.0))])
pair("s_li_space016", "two li 0.17 x 1.0, 0.16 apart (li.3 0.17)",
     [("li", (0, 0, 0.17, 1.0)), ("li", (0.33, 0, 0.50, 1.0))],
     [("li", (0, 0, 0.17, 1.0)), ("li", (0.34, 0, 0.51, 1.0))])
pair("s_li_area", "li 0.17 x 0.32 = 0.0544 um^2 (li.6 0.0561)", [("li", (0, 0, 0.17, 0.32))],
     [("li", (0, 0, 0.17, 0.34))])
pair("s_m1_w013", "met1 0.13 x 1.0 (met1.1 0.14)", [("met1", (0, 0, 0.13, 1.0))], [("met1", (0, 0, 0.14, 1.0))])
pair("s_m1_space013", "two met1 0.14 x 1.0, 0.13 apart (met1.2 0.14)",
     [("met1", (0, 0, 0.14, 1.0)), ("met1", (0.27, 0, 0.41, 1.0))],
     [("met1", (0, 0, 0.14, 1.0)), ("met1", (0.28, 0, 0.42, 1.0))])
pair("s_m1_area", "met1 0.20 x 0.41 = 0.082 um^2 (met1.6 0.083)", [("met1", (0, 0, 0.20, 0.41))],
     [("met1", (0, 0, 0.20, 0.42))])
# m1.3a: "Min. spacing of features attached to or extending from huge_met1 for a distance of up
# to 0.280 um to metal1", 0.280 (periphery-rules.rst:2039-2043; errors.csv:783 "spacing/notch of
# huge met1+nearby met1"); huge metal is 3 um in W and L (assumptions/07-other.csv:10). Both stubs
# are such features, 0.27 apart. No other met1 is near the huge met1, so m1.3b
# (periphery-rules.rst:2044-2048) is not involved.
pair("s_m1_wide_space", "two met1 stubs 0.30 x 0.28 on the edge of a 3.1 um met1, 0.27 apart (met1.3a 0.28)",
     [("met1", (0, 0, 3.1, 3.1)), ("met1", (3.1, 1.0, 3.38, 1.3)), ("met1", (3.1, 1.57, 3.38, 1.87))],
     [("met1", (0, 0, 3.1, 3.1)), ("met1", (3.1, 1.0, 3.38, 1.3)), ("met1", (3.1, 1.58, 3.38, 1.88))])
# m1.3b: "Min. spacing of huge_met1 to metal1 excluding features checked by m1.3a", 0.280
# (periphery-rules.rst:2044-2048; errors.csv:782 "min. spacing between huge met1 and normal met1").
# The 3.1 um square is huge metal (3 um in W and L, assumptions/07-other.csv:10); the 0.30 um strip
# is a separate shape, not a feature attached to it, so m1.3a (periphery-rules.rst:2039-2043) does
# not apply. This is s_m1_wide_space as drawn before 0.6.1.
pair("s_m1_huge_space", "met1 0.30 wide, 0.27 from a 3.1 um square met1 (met1.3b 0.28)",
     [("met1", (0, 0, 3.1, 3.1)), ("met1", (3.37, 0, 3.67, 3.1))],
     [("met1", (0, 0, 3.1, 3.1)), ("met1", (3.38, 0, 3.68, 3.1))])
pair("s_m1_hole", "met1 ring 1.0 x 1.0 with a 0.3 x 0.3 hole (met1.7: hole area 0.14)",
     [("met1", ((0, 0), (1, 0), (1, 1), (0, 1), (0, 0), (0.35, 0.35), (0.35, 0.65), (0.65, 0.65), (0.65, 0.35), (0.35, 0.35)))],
     [("met1", ((0, 0), (1.2, 0), (1.2, 1.2), (0, 1.2), (0, 0), (0.3, 0.3), (0.3, 0.9), (0.9, 0.9), (0.9, 0.3), (0.3, 0.3)))])
# mcon: li and met1 0.5 x 0.5 around a cut at (0.165, 0.165)
LM = [("li", (0, 0, 0.5, 0.5)), ("met1", (0, 0, 0.5, 0.5))]
pair("s_mcon_016", "mcon 0.16 square (mcon/ct.1 0.17)", LM + [("mcon", (0.17, 0.17, 0.33, 0.33))],
     LM + [("mcon", (0.165, 0.165, 0.335, 0.335))])
pair("s_mcon_space", "two mcons 0.18 apart (mcon/ct.2 0.19)",
     [("li", (0, 0, 0.82, 0.5)), ("met1", (0, 0, 0.82, 0.5)), ("mcon", (0.12, 0.165, 0.29, 0.335)),
      ("mcon", (0.47, 0.165, 0.64, 0.335))],
     [("li", (0, 0, 0.82, 0.5)), ("met1", (0, 0, 0.82, 0.5)), ("mcon", (0.11, 0.165, 0.28, 0.335)),
      ("mcon", (0.47, 0.165, 0.64, 0.335))])
pair("s_mcon_no_li", "mcon on met1 with no li (ct.4)", [("met1", (0, 0, 0.5, 0.5)), ("mcon", (0.165, 0.165, 0.335, 0.335))],
     LM + [("mcon", (0.165, 0.165, 0.335, 0.335))])
pair("s_m1_encl_mcon", "met1 0.21 x 0.6 over mcon: 0.02 on two sides (met1.4 0.03)",
     [("li", (0, 0, 0.5, 0.6)), ("met1", (0.145, 0, 0.355, 0.6)), ("mcon", (0.165, 0.215, 0.335, 0.385))],
     [("li", (0, 0, 0.5, 0.6)), ("met1", (0.135, 0, 0.365, 0.6)), ("mcon", (0.165, 0.215, 0.335, 0.385))])
# m1.5: "Mcon must be enclosed by Met1 on one of two adjacent sides by at least" 0.060
# (periphery-rules.rst:2059-2063). 0.03 on the left, right and bottom leaves both sides of each
# bottom corner under 0.06; m1.4's 0.03 on every side holds (periphery-rules.rst:2049-2053).
pair("s_m1_adj_mcon", "met1 0.23 x 0.415 over mcon: 0.03 left/right/bottom, 0.215 top (met1.5 0.06)",
     [("li", (0, 0, 0.5, 0.6)), ("met1", (0.135, 0.185, 0.365, 0.6)), ("mcon", (0.165, 0.215, 0.335, 0.385))],
     [("li", (0, 0, 0.5, 0.6)), ("met1", (0.105, 0.185, 0.395, 0.6)), ("mcon", (0.165, 0.215, 0.335, 0.385))])
pair("s_li_adj_licon", "li 0.23 x 0.6 over a poly licon: 0.03 left/right (li.5 0.08)",
     [("poly", (0, 0, 0.5, 0.6)), ("npc", (0, 0, 0.5, 0.6)), ("li", (0.135, 0, 0.365, 0.6)),
      ("licon", (0.165, 0.215, 0.335, 0.385))],
     [("poly", (0, 0, 0.5, 0.6)), ("npc", (0, 0, 0.5, 0.6)), ("li", (0.085, 0, 0.415, 0.6)),
      ("licon", (0.165, 0.215, 0.335, 0.385))])
# via1: met1 and met2 0.5 x 0.6 around a 0.15 cut
MM = [("met1", (0, 0, 0.5, 0.6)), ("met2", (0, 0, 0.5, 0.6))]
pair("s_via_014", "via1 cut 0.14 square (via.1a 0.15)", MM + [("via", (0.18, 0.23, 0.32, 0.37))],
     MM + [("via", (0.175, 0.225, 0.325, 0.375))])
pair("s_via_016", "via1 cut 0.16 square (via.1a is exact 0.15 in KLayout)", MM + [("via", (0.17, 0.22, 0.33, 0.38))],
     MM + [("via", (0.175, 0.225, 0.325, 0.375))])
pair("s_via_space", "two via1 cuts 0.16 apart (via.2 0.17)",
     [("met1", (0, 0, 0.8, 0.6)), ("met2", (0, 0, 0.8, 0.6)), ("via", (0.17, 0.225, 0.32, 0.375)),
      ("via", (0.48, 0.225, 0.63, 0.375))],
     [("met1", (0, 0, 0.8, 0.6)), ("met2", (0, 0, 0.8, 0.6)), ("via", (0.16, 0.225, 0.31, 0.375)),
      ("via", (0.48, 0.225, 0.63, 0.375))])
pair("s_via_m1_encl", "met1 0.21 wide over a via1 cut: 0.03 left/right (via.4a 0.055)",
     [("met1", (0.145, 0, 0.355, 0.6)), ("met2", (0, 0, 0.5, 0.6)), ("via", (0.175, 0.225, 0.325, 0.375))],
     [("met1", (0.115, 0, 0.385, 0.6)), ("met2", (0, 0, 0.5, 0.6)), ("via", (0.175, 0.225, 0.325, 0.375))])
# via.5a: "0.150 um Via must be enclosed by Met1 on one of two adjacent sides by at least" 0.085
# (periphery-rules.rst:2175-2179). 0.055 on the left, right and bottom leaves both sides of each
# bottom corner under 0.085; via.4a's 0.055 holds (periphery-rules.rst:2160-2164).
pair("s_via_m1_adj", "met1 0.26 x 0.43 over a via1 cut: 0.055 left/right/bottom, 0.225 top (via.5a 0.085)",
     [("met1", (0.12, 0.17, 0.38, 0.6)), ("met2", (0, 0, 0.5, 0.6)), ("via", (0.175, 0.225, 0.325, 0.375))],
     [("met1", (0.09, 0.17, 0.41, 0.6)), ("met2", (0, 0, 0.5, 0.6)), ("via", (0.175, 0.225, 0.325, 0.375))])
pair("s_via_no_m2", "via1 cut with met1 but no met2", [("met1", (0, 0, 0.5, 0.6)), ("via", (0.175, 0.225, 0.325, 0.375))],
     MM + [("via", (0.175, 0.225, 0.325, 0.375))])
# wells and implants alone
pair("s_nwell_w080", "nwell 0.80 x 5 alone (nwell.1 0.84)", [("nwell", (0, 0, 0.80, 5.0))], [("nwell", (0, 0, 0.84, 5.0))])
pair("s_nwell_space", "two nwells 1.0 x 5, 1.20 apart (nwell.2a 1.27)",
     [("nwell", (0, 0, 1.0, 5.0)), ("nwell", (2.2, 0, 3.2, 5.0))],
     [("nwell", (0, 0, 1.0, 5.0)), ("nwell", (2.27, 0, 3.27, 5.0))])
pair("s_dnwell_w29", "dnwell 2.9 x 5 alone (dnwell width 3.0)", [("dnwell", (0, 0, 2.9, 5.0))],
     [("dnwell", (0, 0, 3.0, 5.0))])
pair("s_poly_w014", "poly 0.14 x 1.0 alone (poly.1a 0.15)", [("poly", (0, 0, 0.14, 1.0))], [("poly", (0, 0, 0.15, 1.0))])
pair("s_poly_space", "two poly 0.15 x 1.0, 0.20 apart (poly.2 0.21)",
     [("poly", (0, 0, 0.15, 1.0)), ("poly", (0.35, 0, 0.50, 1.0))],
     [("poly", (0, 0, 0.15, 1.0)), ("poly", (0.36, 0, 0.51, 1.0))])
pair("s_hvtp_alone", "hvtp 0.30 x 1.0 alone (hvtp.1 0.38)", [("hvtp", (0, 0, 0.30, 1.0))], [("hvtp", (0, 0, 0.38, 1.0))])
pair("s_npc_alone", "npc 0.25 x 1.0 alone (npc.1 0.27)", [("npc", (0, 0, 0.25, 1.0))], [("npc", (0, 0, 0.27, 1.0))])
pair("s_nsdm_alone", "nsdm 0.30 x 1.0 alone (nsdm width 0.38)", [("nsdm", (0, 0, 0.30, 1.0))], [("nsdm", (0, 0, 0.38, 1.0))])
pair("s_lvtn_alone", "lvtn 0.30 x 1.0 alone (lvtn.1a 0.38)", [("lvtn", (0, 0, 0.30, 1.0))], [("lvtn", (0, 0, 0.38, 1.0))])
pair("s_ptap_to_nwell", "contacted p-tap 0.10 from an nwell (diff/tap.11 0.13)",
     [("tap", (0, 0, 0.6, 0.6)), ("psdm", (-0.125, -0.125, 0.725, 0.725)), ("licon", (0.215, 0.215, 0.385, 0.385)),
      ("li", (0.115, 0.115, 0.485, 0.485)), ("nwell", (0.70, -1.0, 2.0, 2.0))],
     [("tap", (0, 0, 0.6, 0.6)), ("psdm", (-0.125, -0.125, 0.725, 0.725)), ("licon", (0.215, 0.215, 0.385, 0.385)),
      ("li", (0.115, 0.115, 0.485, 0.485)), ("nwell", (0.73, -1.0, 2.03, 2.0))])
# grid and angles
pair("s_m1_offgrid", "met1 box with one corner 1 nm off the 5 nm grid",
     [("met1", (0, 0, 0.501, 1.0))], [("met1", (0, 0, 0.50, 1.0))])
pair("s_m1_30deg", "met1 polygon with a 30 degree edge (x.3a: 45/90 only)",
     [("met1", ((0, 0), (1.0, 0), (1.0, 0.6), (0.0, 1.175)))],
     [("met1", ((0, 0), (1.0, 0), (1.0, 0.6), (0.4, 1.2), (0.0, 1.2)))])
# x.2 lists li1(periphery) among the layers with n x 90 degree angles only (periphery-rules.rst:145-149;
# errors.csv:118 "non-manhattan li1Peri_noSEAL_noAnch edge"); x.3a's 45 degrees are for the other
# layers (periphery-rules.rst:170-174).
pair("s_li_45deg", "li polygon with a 45 degree edge (x.2: li outside the SRAM core is 90 degree only)",
     [("li", ((0, 0), (1.0, 0), (1.0, 0.6), (0.4, 1.2), (0.0, 1.2)))],
     [("li", (0, 0, 1.0, 1.2))])

# batch 2
inverter("c_licon11_li", "NMOS source licon 0.02 from the gate, with li over it (licon.11 0.055)",
         change={"ns_licon": (1.16, 1.55, 1.33, 1.72)}, add=[("li", (1.08, 1.47, 1.41, 1.80))])
inverter("d_diff_45b", "NMOS source corner cut at 45 degrees, the other diagonal (x.2)",
         change={"ndiff": (0.60, 1.30, 2.60, 1.95)},
         add=[("diff", ((0.40, 1.30), (0.60, 1.30), (0.60, 1.95), (0.40, 1.75)))])
pair("s_m1_30deg_b", "met1 polygon with a 30 degree edge, mirrored (x.3a)",
     [("met1", ((0, 0), (1.0, 0), (1.0, 1.175), (0.0, 0.6)))],
     [("met1", ((0, 0), (1.0, 0), (1.0, 1.2), (0.6, 1.2), (0.0, 0.6)))])
pair("s_m1_hole_boxes", "met1 ring of four boxes around a 0.3 x 0.3 hole (met1.7)",
     [("met1", (0, 0, 1.0, 0.35)), ("met1", (0, 0.65, 1.0, 1.0)), ("met1", (0, 0.35, 0.35, 0.65)), ("met1", (0.65, 0.35, 1.0, 0.65))],
     [("met1", (0, 0, 1.2, 0.3)), ("met1", (0, 0.9, 1.2, 1.2)), ("met1", (0, 0.3, 0.3, 0.9)), ("met1", (0.9, 0.3, 1.2, 0.9))])
pair("s_li_hole", "li ring 1.0 x 1.0 around a 0.3 x 0.3 hole (no li hole rule on either side?)",
     [("li", ((0, 0), (1, 0), (1, 1), (0, 1), (0, 0), (0.35, 0.35), (0.35, 0.65), (0.65, 0.65), (0.65, 0.35), (0.35, 0.35)))],
     [("li", (0, 0, 1.0, 1.0))])

# ---------------------------------------------------------------- batch E
BUTT = [("tap", (0.10, 1.30, 0.40, 1.95)), ("psdm", (-0.025, 0.225, 0.40, 2.075))]
inverter_e("e_inv_base", "inverter with the NMOS nsdm starting at x 0.40 (control for e_ inverter cases)", control=None)
inverter_e("e_butt_ok", "p-tap 0.30 x 0.65 butting the NMOS source, implant boundary on the butting edge", add=BUTT,
         control="e_inv_base")
# difftap.4: "Min tap bound by one diffusion", 0.290 (periphery-rules.rst:895-899); the figure
# (periphery/p026-difftap_dotdash.svg) measures it from the butting edge to the tap's far edge.
# The tap is 0.20 deep and butts the whole 0.65 of the source edge.
inverter_e("e_butt_short", "butting p-tap only 0.20 deep from the butting edge (diff/tap.4 0.29)",
         add=[("tap", (0.20, 1.30, 0.40, 1.95)), BUTT[1]], control="e_butt_ok")
inverter_e("e_butt_shift", "implant boundary 0.05 inside the NMOS diffusion (psdm over 0.05 of it)",
         add=[BUTT[0], ("psdm", (-0.025, 0.225, 0.45, 2.075))], change={"ndiff_nsdm": (0.45, 1.175, 2.725, 2.075)},
         control="e_butt_ok")
inverter_e("e_butt_licon5b", "licon on the butting tap 0.03 from the butting edge, li over it (licon.5b 0.06)",
         add=BUTT + [("licon", (0.20, 1.50, 0.37, 1.67)), ("li", (0.12, 1.42, 0.50, 1.75))], control="e_butt_ok")
# The manual's nsdm area rule is n/psd.10a, 0.265 um^2 (periphery-rules.rst:1495-1499); a contacted
# tap in an nsdm at the minimum 0.125 enclosure has 0.277 um^2 of it. Like d_tap_area, the
# case targets no rule.
inverter_e("e_ntap_area", "n-tap 0.41 x 0.17 around its licon, area 0.0697 um^2, in a 1.84 um^2 nsdm: "
         "legal by the manual; Magic's n-tap area rule nsd.10b 0.07011 reports it",
         change={"ntap": (0.43, 5.22, 0.84, 5.39)}, control="e_inv_base")
inverter_e("e_bent_gate", "gate with a jog inside the NMOS diffusion (poly.11: no bends in transistors)",
         add=[("poly", (1.35, 1.55, 1.70, 1.70))], control="e_inv_base")
inverter_e("e_lvtn_half", "lvtn over the lower half of the NMOS gate",
         add=[("lvtn", (1.17, 1.12, 1.68, 1.62))], control="e_inv_base")
inverter_e("e_pfet_lvt", "lvtn instead of hvtp over the PMOS: lvt pfet with L 0.15 (poly.1b 0.35)",
         drop=["hvtp"], add=[("lvtn", (1.17, 3.32, 1.68, 4.68))], control="e_inv_base")

# ---------------------------------------------------------------- hier
# The review's two-level cells (design-0.6.md 3.1): inv_base with these
# layers moved into a parent cell. Magic's drc(full) boxes per rule on each cell,
# and the devices its extraction found.
HIER = {
    "base": ["inv_base"],
    "groups": {"imp": [(93, 44), (94, 20)], "nw": [(64, 20)],
               "all": [(93, 44), (94, 20), (64, 20), (78, 44), (95, 20)]},
    "expect": {
        "inv_base": ({}, {"sky130_fd_pr__nfet_01v8": 1, "sky130_fd_pr__pfet_01v8_hvt": 1}),
        "inv_base_imp_h": ({"nwell.2a": 2, "diff/tap.8": 13, "Can't overlap those layers": 2, "nwell.1": 2,
                            "nwell.4": 2, "LU.3": 3, "poly.4": 4},
                           {"sky130_fd_pr__pfet_01v8": 1, "sky130_fd_pr__pfet_01v8_hvt": 1}),
        "inv_base_nw_h": ({"Can't overlap those layers": 3, "diff/tap.11": 10, "nwell.4": 5, "poly.5": 8},
                          {"sky130_fd_pr__nfet_01v8": 1}),
        "inv_base_all_h": ({"nwell.2a": 3, "diff/tap.8": 13, "nwell.1": 2, "Can't overlap those layers": 5,
                            "nwell.4": 6, "LU.3": 3, "poly.4": 4},
                           {"sky130_fd_pr__pfet_01v8": 2}),
    },
}

# ---------------------------------------------------------------- whole_shape
def _nwtap(d):
    """The review's long well: a 100 x 3 um n-well with one contacted n-tap at its left end."""
    d.box("nwell", 0, 0, 100, 3)
    d.box("tap", 1.0, 1.0, 1.6, 1.6)
    d.box("nsdm", 0.875, 0.875, 1.725, 1.725)
    d.box("licon", 1.215, 1.215, 1.385, 1.385)
    d.box("li", 1.135, 1.135, 1.465, 1.465)


WHOLE_SHAPE = [
    dict(name="nwtap", draw=_nwtap, targets=["nwell.4"],
         expect={"magic": {"drc(full)": {}},
                 "magic_area": {"box": [70, -15, 100, 18], "drc(full)": {"nwell.4": 1}}},
         box=[85, 0, 100, 3],
         measured={"by": "Magic 8.3.681 in the pinned image, 2026-11-23", "drc(full)": {}},
         notes="nwell.4 is a whole-shape rule (nwell_missing_tap, sky130A.tech:1712-1716): Magic's whole-cell "
               "check gives no error; Magic's own area check of x 70-100, y -15-18 (the core x 85-100 grown by "
               "a 15 um halo) gives one nwell.4 box (70, 0)-(100, 3). The plugin's area check of `box` "
               "(whole cell, then the filter) must give no nwell.4 (design-0.6.md 3.1, 6.4).",
         source="the review's long well, design-0.6.md 3.1 and 6.4"),
]

# ---------------------------------------------------------------- names
NAMES_ERROR = ("met1", (0, 0, 0.10, 1.0), "met1.1")

# ---------------------------------------------------------------- inverters
INV_TOP = "inv"
SCHEMATIC = """.subckt {top} A Y VPWR VGND
XM1 Y A VGND VGND sky130_fd_pr__nfet_01v8 w={wn} l=0.15
XM2 Y A VPWR VPWR sky130_fd_pr__pfet_01v8_hvt w={wp} l=0.15
.ends
"""
SCH_W = {"wn": 0.65, "wp": 1}


def inverter_variants():
    """(name, draw, notes, expect, source) for the hand-drawn inverter and its broken variants."""
    W036 = {"ndiff": (0.40, 1.30, 2.60, 1.66), "ndiff_nsdm": (0.275, 1.175, 2.725, 1.785),
            "ns_licon": (0.55, 1.395, 0.72, 1.565), "nd_licon": (2.28, 1.395, 2.45, 1.565),
            "li_y": (2.18, 1.30, 2.55, 4.17)}
    swap = {"A": ("li.label", 2.375, 2.725), "Y": ("li.label", 1.425, 2.525)}
    return [
        ("inv", _inverter_draw(INV), "clean hand-drawn inverter, texts on */5 over */16 pin boxes",
         {"magic": {"drc(fast)": {}, "drc(full)": {}, "drc(routing)": {}}, "netgen": "match",
          "klayout": {"lvs": "match", "kl_menu_full": {}}}, "GAPS-sky130A 5.2 (pt_text_pin); 2.2 inv_base"),
        ("inv_w036", _inverter_draw(INV, change=W036), "NMOS W 0.36 against a schematic W 0.65 (d_gate_w036)",
         {"magic": {"drc(full)": {"diff/tap.2": 2}}, "netgen": "match uniquely, then property errors",
          "klayout": {"lvs": "no match"}}, "GAPS-sky130A 5.2 (d_gate_w036)"),
        ("inv_pin_only_li", _inverter_draw(INV, drop=["li_a"], change={"pin_a": (1.24, 2.34, 1.61, 2.71)}),
         "A's li drawn only on li1.pin (l_pin_only_li)",
         {"netgen": "pin matching fails", "klayout": {"lvs": "match"}}, "GAPS-sky130A 5.2 (l_pin_only_li)"),
        ("inv_open_drain", _inverter_draw(INV, change={"li_y": (2.18, 2.50, 2.55, 4.17)},
                                          add=[("li", (2.18, 1.45, 2.55, 2.20))]),
         "the Y li cut between the NMOS drain and the PMOS drain: the NMOS drain floats", {}, ""),
        ("inv_swap", _inverter_draw(INV, text=swap), "A and Y texts exchanged", {}, ""),
        ("inv_no_text", _inverter_draw(INV, text={k: None for k in INV_TEXT}),
         "no texts at all; pin boxes kept", {}, ""),
        # A's text on li1.pin (67/16) over its pin box: Magic makes it a port
        # (labels on */16 are port texts), KLayout's LVS reads net names from
        # */5 only, so the port check gives P3 (design-0.6.md 5.1, 5.3).
        ("inv_text_on_pin", _inverter_draw(INV, text={"A": ("li.pin", 1.425, 2.525)}),
         "A's text on li1.pin (67/16) instead of li1.label: a Magic port KLayout's LVS can't name (P3)",
         {"ports": ["P3"]}, "new in 0.6 (design-0.6.md 5.1)"),
    ]


# ---------------------------------------------------------------- controls
CONTROLS = {
    "lib": "sky130_fd_sc_hd",
    "cells": ["sky130_fd_sc_hd__inv_1", "sky130_fd_sc_hd__nand2_1", "sky130_fd_sc_hd__dfxtp_1",
              "sky130_fd_sc_hd__mux2_1", "sky130_fd_sc_hd__tapvpwrvgnd_1", "sky130_fd_sc_hd__buf_2",
              "sky130_fd_sc_hd__conb_1"],
    "expect_f1": "npc on dfxtp_1 (0.0455 um2, 2 pieces) and mux2_1 (0.0642 um2, 3 pieces) under the "
                 "subtraction; no nsdm, psdm or hvtp difference (design-0.6.md 6.2)",
}


# ---------------------------------------------------------------- PCell inverter
def pcell_inverter(db, ly):
    """sky130A/tests/build_inv_pcell.py with onecontact=1, pins=1: the plugin's
    nfet_01v8 and pfet_01v8_hvt, wired in li and met1 at the top level."""
    top = ly.create_cell("inv_pcell")
    L = {"li": (67, 20), "mcon": (67, 44), "met1": (68, 20), "met1.label": (68, 5), "met1.pin": (68, 16)}

    def box(layer, x1, y1, x2, y2):
        top.shapes(ly.layer(*L[layer])).insert(db.DBox(x1, y1, x2, y2))

    def features(cell, dx, dy):
        def boxes(ld):
            li = ly.find_layer(*ld)
            return [s.dbbox().moved(dx, dy) for s in cell.shapes(li).each()] if li is not None else []
        texts = {s.text.string: s.dtext.position() + db.DVector(dx, dy)
                 for s in cell.shapes(ly.find_layer(67, 5)).each()}
        m1 = boxes((68, 20))
        li = boxes((67, 20))
        at = lambda p: next(b for b in m1 if b.contains(p))
        wide = sorted((b for b in li if b.width() > 1.5), key=lambda b: b.bottom)
        return {"G": at(texts["G"]), "D": at(texts["D"]), "S": at(texts["S"]),
                "ring_bot": wide[0], "ring_top": wide[-1], "ring_right": max(li, key=lambda b: b.right)}

    NX, NY, PX, PY = 1.4, 1.4, 1.4, 4.6
    nfet = ly.create_cell("sky130_fd_pr__nfet_01v8", "sky130_magic", {"w": 0.65, "l": 0.15, "nf": 1, "botc": False})
    pfet = ly.create_cell("sky130_fd_pr__pfet_01v8_hvt", "sky130_magic", {"w": 1.0, "l": 0.15, "nf": 1, "topc": False})
    top.insert(db.DCellInstArray(nfet.cell_index(), db.DTrans(NX, NY)))
    top.insert(db.DCellInstArray(pfet.cell_index(), db.DTrans(PX, PY)))
    n = features(nfet, NX, NY)
    p = features(pfet, PX, PY)
    ng, pg = n["G"], p["G"]
    box("met1", ng.left, ng.top - 0.05, ng.right, pg.bottom + 0.05)
    ya = (ng.top + pg.bottom) / 2
    yn, yp = n["D"].center().y, p["D"].center().y
    box("met1", 0.00, yn - 0.10, n["D"].right, yn + 0.10)
    box("met1", 0.00, yn - 0.10, 0.23, yp + 0.10)
    box("met1", 0.00, yp - 0.10, p["D"].right, yp + 0.10)
    for f in (n, p):
        yc = f["S"].center().y
        box("li", f["S"].left + 0.03, yc - 0.10, f["ring_right"].right, yc + 0.10)
    rb = n["ring_bot"]
    box("mcon", 2.00, rb.bottom, 2.17, rb.top)
    box("met1", 0.00, rb.top + 0.075 - 0.45, 2.80, rb.top + 0.075)
    rt = p["ring_top"]
    box("mcon", 2.00, rt.bottom, 2.17, rt.top)
    box("met1", 0.00, rt.bottom - 0.05, 2.80, rt.bottom + 0.40)
    for s, x, y in (("A", NX, ya), ("Y", 0.115, (yn + yp) / 2),
                    ("VGND", 0.3, rb.top + 0.075 - 0.225), ("VPWR", 0.3, rt.bottom + 0.15)):
        top.shapes(ly.layer(*L["met1.label"])).insert(db.DText(s, x, y))
        box("met1.pin", x - 0.1, y - 0.1, x + 0.1, y + 0.1)
    return top


PCELL_EXPECT = ({"magic": {"drc(fast)": {}, "drc(full)": {}, "drc(routing)": {}}, "netgen": "match",
                 "klayout": {"lvs": "match"}},
                "GAPS-sky130A 5.2 (inv_pcell1.gds, onecontact=1 pins=1)")
PCELL_SCH_W = {"wn": 0.65, "wp": 1}

ANCHORS = {"a_poly8": "poly.8"}
