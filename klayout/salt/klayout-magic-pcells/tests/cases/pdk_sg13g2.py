"""ihp-sg13g2 cases. The gaps set is the ihp-sg13g2 gap study's suite
(GAPS-ihp-sg13g2 section 3): 67 tests and two base devices, each an ok
and a bad cell, plus the hand-drawn devices of section 4 (the
Magic-generated M_ cells there need Magic's own device GDS and are left
out). A test's bad cell is the
case named after the test, its ok cell the same name with "_ok". The tables
are that suite's, unchanged, so that expect-ihp-sg13g2.json still applies.
"""

from .common import Drawing

PDK = "ihp-sg13g2"
SOURCE = "GAPS-ihp-sg13g2 3"

LAYERS = {
    'Activ': (1, 0), 'Activ.pin': (1, 2), 'BiWind': (3, 0), 'GatPoly': (5, 0), 'GatPoly.pin': (5, 2),
    'Cont': (6, 0), 'nSD': (7, 0), 'nSD.block': (7, 21), 'Metal1': (8, 0), 'Metal1.pin': (8, 2),
    'Metal1.text': (8, 25), 'Metal2': (10, 0), 'Metal2.pin': (10, 2), 'Metal2.text': (10, 25),
    'pSD': (14, 0), 'Via1': (19, 0), 'RES': (24, 0), 'SalBlock': (28, 0), 'NWell': (31, 0),
    'NWell.pin': (31, 2), 'nBuLay': (32, 0), 'Substrate': (40, 0), 'Substrate.text': (40, 25),
    'ThickGateOx': (44, 0), 'PWell.block': (46, 21), 'TEXT': (63, 0), 'EXTBlock': (111, 0),
    'PolyRes': (128, 0),
}


class Cell(Drawing):
    """geom.py's Cell: a Drawing with its contact-and-pad helper."""

    def __init__(self):
        Drawing.__init__(self, LAYERS)

    def cont(self, x, y, s=0.16, m1=0.05, m1_area=True):
        """Square Cont at (x, y) lower-left, with a Metal1 pad around it."""
        self.box('Cont', x, y, x + s, y + s)
        if m1 is not None:
            e = m1
            w = s + 2 * e
            h = s + 2 * e
            if m1_area and w * h < 0.0905:
                h = round(0.0905 / w + 0.005, 2)
            cy = y + s / 2
            self.box('Metal1', x - e, cy - h / 2, x + s + e, cy + h / 2)


def nmos(c, x=0.0, y=0.0, W=0.5, L=0.13, endcap=0.18, cnt_f=0.11, cnt_c=0.07, pad_gap=0.17,
         pad_enc=0.07, tap=True, tap_gap=0.5, psd_d=None, thk=False, thk_enc=0.27, gate_cont=False):
    """NMOS (vertical gate), source/drain contacts, a poly pad with contact above the
    channel, and a p+ substrate tie (Activ + pSD) to its right.
    Returns dict of useful coordinates."""
    sd = cnt_c + 0.16 + cnt_f
    ax2 = x + 2 * sd + L
    c.box('Activ', x, y, ax2, y + W)
    gx1, gx2 = x + sd, x + sd + L
    # gate + pad
    py1 = y + W + pad_gap - pad_enc          # pad bottom (contact bottom is pad_gap above Activ)
    c.box('GatPoly', gx1, y - endcap, gx2, py1)
    pw = 0.16 + 2 * pad_enc
    pcx = (gx1 + gx2) / 2
    c.box('GatPoly', pcx - pw / 2, py1, pcx + pw / 2, py1 + pw)
    if gate_cont:
        c.box('Cont', pcx - 0.08, y + W / 2 - 0.08, pcx + 0.08, y + W / 2 + 0.08)
    c.cont(pcx - 0.08, py1 + pad_enc, m1=0.07)
    cy = y + W / 2 - 0.08
    # S/D contacts, M1 straps extend downwards (keeps M1.b to the gate pad)
    for cx in (x + cnt_c, gx2 + cnt_f):
        c.box('Cont', cx, cy, cx + 0.16, cy + 0.16)
        c.box('Metal1', cx - 0.05, cy - 0.45, cx + 0.21, cy + 0.21)
    out = {'ax2': ax2, 'gx1': gx1, 'gx2': gx2, 'top': py1 + pw}
    if thk:
        c.box('ThickGateOx', x - thk_enc, y - endcap - thk_enc, ax2 + thk_enc, py1 + pw + thk_enc)
    if tap:
        tx = ax2 + tap_gap
        c.box('Activ', tx, y, tx + 0.3, y + W)
        c.cont(tx + 0.07, cy)
        d = psd_d if psd_d is not None else 0.29
        c.box('pSD', ax2 + d, y - 0.2, tx + 0.5, y + W + 0.2)
        out['tx'] = tx
    return out


def pmos(c, x=0.0, y=0.0, W=0.5, L=0.13, endcap=0.18, cnt_f=0.11, cnt_c=0.07, pad_gap=0.17,
         pad_enc=0.07, psd=True, psd_c=0.18, psd_i=0.30, nw_c=0.31, tap=True, tap_gap=0.5,
         nwell=True, psd_box=None, thk=False):
    sd = cnt_c + 0.16 + cnt_f
    ax2 = x + 2 * sd + L
    c.box('Activ', x, y, ax2, y + W)
    gx1, gx2 = x + sd, x + sd + L
    py1 = y + W + pad_gap - pad_enc
    c.box('GatPoly', gx1, y - endcap, gx2, py1)
    pw = 0.16 + 2 * pad_enc
    pcx = (gx1 + gx2) / 2
    c.box('GatPoly', pcx - pw / 2, py1, pcx + pw / 2, py1 + pw)
    c.cont(pcx - 0.08, py1 + pad_enc, m1=0.07)
    cy = y + W / 2 - 0.08
    for cx in (x + cnt_c, gx2 + cnt_f):
        c.box('Cont', cx, cy, cx + 0.16, cy + 0.16)
        c.box('Metal1', cx - 0.05, cy - 0.45, cx + 0.21, cy + 0.21)
    if psd:
        if psd_box:
            c.box('pSD', *psd_box)
        else:
            c.box('pSD', x - psd_c, y - psd_i, ax2 + psd_c, y + W + psd_i)
    tx = ax2 + tap_gap
    if tap:
        c.box('Activ', tx, y, tx + 0.3, y + W)
        c.cont(tx + 0.07, cy)
    if nwell:
        right = (tx + 0.3 + 0.24) if tap else ax2 + nw_c
        c.box('NWell', x - nw_c, y - nw_c, max(right, ax2 + nw_c), y + W + nw_c)
    return {'ax2': ax2, 'gx1': gx1, 'gx2': gx2, 'tx': tx, 'top': py1 + pw}


T = []


def test(tid, rule, what):
    def deco(fn):
        T.append((tid, rule, what, fn))
        return fn
    return deco

# ---------------- matched rules (sample) ----------------

@test('Act_a', 'Act.a', 'Activ width 0.14 (ok 0.15), lone n+ Activ')
def _(c, bad):
    c.box('Activ', 0, 0, 0.14 if bad else 0.15, 1.0)

@test('Act_b', 'Act.b', 'Activ space 0.20 (ok 0.21)')
def _(c, bad):
    g = 0.20 if bad else 0.21
    c.box('Activ', 0, 0, 0.5, 1.0); c.box('Activ', 0.5 + g, 0, 1.0 + g, 1.0)

@test('Gat_a', 'Gat.a', 'field GatPoly width 0.12 (ok 0.13)')
def _(c, bad):
    c.box('GatPoly', 0, 0, 0.12 if bad else 0.13, 1.0)

@test('Gat_b', 'Gat.b', 'GatPoly space 0.17 (ok 0.18)')
def _(c, bad):
    g = 0.17 if bad else 0.18
    c.box('GatPoly', 0, 0, 0.3, 1.0); c.box('GatPoly', 0.3 + g, 0, 0.6 + g, 1.0)

@test('Gat_c', 'Gat.c', 'NMOS gate end cap 0.17 (ok 0.18)')
def _(c, bad):
    nmos(c, endcap=0.17 if bad else 0.18)

@test('Gat_d', 'Gat.d', 'field GatPoly 0.06 from Activ of an NMOS (ok 0.07)')
def _(c, bad):
    nmos(c)
    g = 0.06 if bad else 0.07
    c.box('GatPoly', -g - 0.13, -0.5, -g, 1.0)

@test('Gat_a1', 'Gat.a1', 'LV NMOS channel length 0.12 (ok 0.13)')
def _(c, bad):
    nmos(c, L=0.12 if bad else 0.13)

@test('Cnt_b', 'Cnt.b', 'two diffusion contacts 0.17 apart (ok 0.18)')
def _(c, bad):
    g = 0.17 if bad else 0.18
    w = 0.07 + 0.16 + g + 0.16 + 0.07
    c.box('Activ', 0, 0, w, 0.4)
    c.box('Cont', 0.07, 0.12, 0.23, 0.28); c.box('Cont', 0.23 + g, 0.12, 0.39 + g, 0.28)
    c.box('Metal1', 0.02, -0.1, w - 0.02, 0.33)
    c.box('Activ', w + 0.5, 0, w + 0.8, 0.4); c.cont(w + 0.57, 0.12)
    c.box('pSD', w + 0.3, -0.2, w + 1.0, 0.6)

@test('Cnt_c', 'Cnt.c', 'Activ enclosure of contact 0.06 (ok 0.07)')
def _(c, bad):
    nmos(c, cnt_c=0.06 if bad else 0.07)

@test('Cnt_d', 'Cnt.d', 'GatPoly enclosure of poly contact 0.06 (ok 0.07)')
def _(c, bad):
    nmos(c, pad_enc=0.06 if bad else 0.07)

@test('Cnt_e', 'Cnt.e', 'poly contact 0.13 from Activ (ok 0.14)')
def _(c, bad):
    nmos(c, pad_gap=0.13 if bad else 0.14)

@test('Cnt_f', 'Cnt.f', 'diffusion contact 0.10 from gate (ok 0.11)')
def _(c, bad):
    nmos(c, cnt_f=0.10 if bad else 0.11)

@test('M1_a', 'M1.a', 'Metal1 width 0.15 (ok 0.16)')
def _(c, bad):
    c.box('Metal1', 0, 0, 0.15 if bad else 0.16, 2.0)

@test('M1_b', 'M1.b', 'Metal1 space 0.17 (ok 0.18)')
def _(c, bad):
    g = 0.17 if bad else 0.18
    c.box('Metal1', 0, 0, 0.3, 1.0); c.box('Metal1', 0.3 + g, 0, 0.6 + g, 1.0)

@test('M1_d', 'M1.d', 'Metal1 area 0.08 (ok 0.09)')
def _(c, bad):
    c.box('Metal1', 0, 0, 0.2, 0.4 if bad else 0.45)

@test('NW_c', 'NW.c', 'NWell enclosure of PMOS Activ 0.30 (ok 0.31)')
def _(c, bad):
    pmos(c, nw_c=0.30 if bad else 0.31)

@test('NW_d', 'NW.d', 'NMOS N+ Activ 0.30 from an NWell (ok 0.31)')
def _(c, bad):
    o = nmos(c)
    g = 0.30 if bad else 0.31
    c.box('NWell', -g - 1.0, -0.5, -g, 1.5)
    c.box('Activ', -g - 0.7, 0.2, -g - 0.4, 0.5); c.cont(-g - 0.63, 0.27)

@test('NW_e', 'NW.e', 'NWell enclosure of n-tap 0.23 (ok 0.24)')
def _(c, bad):
    e = 0.23 if bad else 0.24
    c.box('Activ', 0, 0, 0.3, 0.5); c.cont(0.07, 0.17)
    c.box('NWell', -0.5, -e, 0.3 + e, 0.5 + e)

@test('NW_f', 'NW.f', 'p-tap 0.23 from NWell (ok 0.24)')
def _(c, bad):
    g = 0.23 if bad else 0.24
    c.box('Activ', 0, 0, 0.3, 0.5); c.cont(0.07, 0.17); c.box('pSD', -0.2, -0.2, 0.5, 0.7)
    c.box('NWell', 0.3 + g, -0.5, 1.5 + g, 1.0)

@test('pSD_i_tap', 'pSD.i', 'PMOS gate 0.29 from a butted n-tap edge (ok 0.30), pSD drawn to the butting edge')
def _(c, bad):
    # PMOS with the n-tap butted to its source side: Activ continues, pSD stops at the butting edge.
    g = 0.29 if bad else 0.30
    # gate x [0.34, 0.47]; drain contact at right; butting edge at gate - g on the left
    c.box('Activ', -0.6, 0, 0.81, 0.5)
    c.box('GatPoly', 0.34, -0.18, 0.47, 0.60); c.box('GatPoly', 0.255, 0.60, 0.555, 0.90); c.cont(0.325, 0.67, m1=0.07)
    c.box('Cont', 0.58, 0.17, 0.74, 0.33); c.box('Metal1', 0.53, -0.28, 0.79, 0.38)
    c.box('Cont', -0.45, 0.17, -0.29, 0.33); c.box('Metal1', -0.5, -0.28, -0.24, 0.38)
    c.box('pSD', 0.34 - g, -0.30, 0.99, 0.80)
    c.box('NWell', -0.9, -0.31, 1.12, 0.81)

@test('pSD_i_psd', 'pSD.i', 'pSD enclosure of PFET gate 0.29 in the W direction (ok 0.30)')
def _(c, bad):
    pmos(c, psd_i=0.29 if bad else 0.30)

@test('Act_c', 'Act.c', 'drain/source extension 0.22 beyond gate, no contact (ok 0.23)')
def _(c, bad):
    e = 0.22 if bad else 0.23
    # NMOS with a short contact-less drain on the right
    c.box('Activ', 0, 0, 0.34 + 0.13 + e, 0.5)
    c.box('GatPoly', 0.34, -0.18, 0.47, 0.60); c.box('GatPoly', 0.255, 0.60, 0.555, 0.90); c.cont(0.325, 0.67, m1=0.07)
    c.box('Cont', 0.07, 0.17, 0.23, 0.33); c.box('Metal1', 0.02, -0.28, 0.28, 0.38)
    c.box('Activ', 1.5, 0, 1.8, 0.5); c.cont(1.57, 0.17); c.box('pSD', 1.3, -0.2, 2.0, 0.7)

@test('V1_a', 'V1.a', 'Via1 0.18 square (ok 0.19)')
def _(c, bad):
    s = 0.18 if bad else 0.19
    c.box('Metal1', -0.1, -0.1, 0.4, 0.4); c.box('Metal2', -0.1, -0.1, 0.4, 0.4)
    c.box('Via1', 0.05, 0.05, 0.05 + s, 0.05 + s)

@test('V1_c', 'V1.c', 'Metal1 enclosure of Via1 0.005 on one side (ok 0.01), 0.05 on the others')
def _(c, bad):
    e = 0.005 if bad else 0.01
    c.box('Via1', 0, 0, 0.19, 0.19)
    c.box('Metal1', -e, -0.05, 0.24, 0.24 + 0.2); c.box('Metal2', -0.05, -0.05, 0.24, 0.44)

@test('V1_b', 'V1.b', 'two Via1 0.21 apart (ok 0.22)')
def _(c, bad):
    g = 0.21 if bad else 0.22
    c.box('Metal1', -0.05, -0.05, 0.43 + g, 0.24); c.box('Metal2', -0.05, -0.05, 0.43 + g, 0.24)
    c.box('Via1', 0, 0, 0.19, 0.19); c.box('Via1', 0.19 + g, 0, 0.38 + g, 0.19)

# ---------------- KLayout-only (front end, Metal1, Via1) ----------------

@test('NW_b1', 'NW.b1', 'two NWells (each with its own n-tap, different nets) 1.0 apart (ok 1.8)')
def _(c, bad):
    g = 1.0 if bad else 1.8
    for x in (0, 2.0 + g):
        c.box('NWell', x, 0, x + 2.0, 2.0)
        c.box('Activ', x + 0.85, 0.75, x + 1.15, 1.25); c.cont(x + 0.92, 0.92)

@test('PWB_b', 'PWB.b', 'PWell:block space 0.50 (ok 0.62)')
def _(c, bad):
    g = 0.50 if bad else 0.62
    c.box('PWell.block', 0, 0, 1.0, 1.0); c.box('PWell.block', 1.0 + g, 0, 2.0 + g, 1.0)

@test('TGO_f', 'TGO.f', 'ThickGateOx width 0.80 (ok 0.86), alone')
def _(c, bad):
    c.box('ThickGateOx', 0, 0, 0.80 if bad else 0.86, 2.0)

@test('TGO_e', 'TGO.e', 'ThickGateOx space 0.80 (ok 0.86)')
def _(c, bad):
    g = 0.80 if bad else 0.86
    c.box('ThickGateOx', 0, 0, 1.0, 1.0); c.box('ThickGateOx', 1.0 + g, 0, 2.0 + g, 1.0)

@test('TGO_a', 'TGO.a', 'HV NMOS (L 0.45), ThickGateOx extension over Activ 0.26 (ok 0.27)')
def _(c, bad):
    nmos(c, L=0.45, thk=True, thk_enc=0.26 if bad else 0.27, tap_gap=0.8)

@test('TGO_b', 'TGO.b', 'LV n+ Activ 0.26 from a ThickGateOx box (ok 0.27)')
def _(c, bad):
    g = 0.26 if bad else 0.27
    c.box('ThickGateOx', 0, 0, 1.0, 1.0)
    c.box('Activ', 1.0 + g, 0.2, 1.3 + g, 0.7); c.cont(1.07 + g, 0.37)

@test('Gat_b1', 'Gat.b1', 'two HV gates on one Activ 0.24 apart (ok 0.25)')
def _(c, bad):
    g = 0.24 if bad else 0.25
    w = 0.34 + 0.45 + g + 0.45 + 0.34
    c.box('Activ', 0, 0, w, 0.5)
    for gx in (0.34, 0.34 + 0.45 + g):
        c.box('GatPoly', gx, -0.18, gx + 0.45, 0.60); c.box('GatPoly', gx + 0.075, 0.60, gx + 0.375, 0.90)
        c.cont(gx + 0.145, 0.67, m1=0.07)
    c.box('Cont', 0.07, 0.17, 0.23, 0.33); c.box('Metal1', 0.02, -0.28, 0.28, 0.38)
    c.box('Cont', w - 0.23, 0.17, w - 0.07, 0.33); c.box('Metal1', w - 0.28, -0.28, w - 0.02, 0.38)
    c.box('ThickGateOx', -0.3, -0.5, w + 0.3, 1.2)
    c.box('Activ', w + 1.0, 0, w + 1.3, 0.5); c.cont(w + 1.07, 0.17); c.box('pSD', w + 0.8, -0.2, w + 1.5, 0.7)

@test('pSD_a', 'pSD.a', 'pSD width 0.30 (ok 0.31), alone')
def _(c, bad):
    c.box('pSD', 0, 0, 0.30 if bad else 0.31, 1.0)

@test('pSD_b', 'pSD.b', 'pSD space 0.30 (ok 0.31), alone')
def _(c, bad):
    g = 0.30 if bad else 0.31
    c.box('pSD', 0, 0, 1.0, 1.0); c.box('pSD', 1.0 + g, 0, 2.0 + g, 1.0)

@test('pSD_c', 'pSD.c', 'pSD enclosure of PMOS Activ 0.17 (ok 0.18), drawn pSD')
def _(c, bad):
    pmos(c, psd_c=0.17 if bad else 0.18)

@test('pSD_d', 'pSD.d', 'p-tap pSD 0.17 from NMOS N+ Activ (ok 0.18)')
def _(c, bad):
    nmos(c, psd_d=0.17 if bad else 0.18)

@test('pSD_k', 'pSD.k', 'pSD area 0.225 (ok 0.25), alone')
def _(c, bad):
    c.box('pSD', 0, 0, 0.5, 0.45 if bad else 0.5)

@test('pSD_l', 'pSD.l', 'pSD ring, hole 0.4 x 0.4 = 0.16 um2 (ok 0.6 x 0.6)')
def _(c, bad):
    h = 0.4 if bad else 0.6
    t = 0.5
    c.box('pSD', 0, 0, t, 2 * t + h); c.box('pSD', t + h, 0, 2 * t + h, 2 * t + h)
    c.box('pSD', 0, 0, 2 * t + h, t); c.box('pSD', 0, t + h, 2 * t + h, 2 * t + h)

@test('nSDB_a', 'nSDB.a', 'nSD:block width 0.30 (ok 0.31), alone')
def _(c, bad):
    c.box('nSD.block', 0, 0, 0.30 if bad else 0.31, 1.0)

@test('EXTB_a', 'EXTB.a', 'EXTBlock width 0.30 (ok 0.31), alone')
def _(c, bad):
    c.box('EXTBlock', 0, 0, 0.30 if bad else 0.31, 1.0)

@test('Sal_a', 'Sal.a', 'SalBlock width 0.41 (ok 0.42), alone')
def _(c, bad):
    c.box('SalBlock', 0, 0, 0.41 if bad else 0.42, 1.0)

@test('Cnt_b1', 'Cnt.b1', '5 x 5 diffusion-contact array at 0.18 pitch-space (ok 0.20 in one direction)')
def _(c, bad):
    gx = 0.18 if bad else 0.20
    gy = 0.18
    n = 5
    w = 0.14 + n * 0.16 + (n - 1) * gx
    h = 0.14 + n * 0.16 + (n - 1) * gy
    c.box('Activ', 0, 0, w, h)
    for i in range(n):
        for j in range(n):
            x = 0.07 + i * (0.16 + gx); y = 0.07 + j * (0.16 + gy)
            c.box('Cont', x, y, x + 0.16, y + 0.16)
    c.box('Metal1', 0.02, 0.02, w - 0.02, h - 0.02)
    c.box('Activ', w + 0.5, 0, w + 0.8, 0.5); c.cont(w + 0.57, 0.17); c.box('pSD', w + 0.3, -0.2, w + 1.0, 0.7)

@test('Cnt_g', 'Cnt.g', 'contact on field (no Activ or GatPoly), with Metal1 (ok: same contact on a poly pad)')
def _(c, bad):
    if not bad:
        c.box('GatPoly', -0.07, -0.07, 0.23, 0.23)
    c.cont(0, 0, m1=0.07)

@test('Cnt_h', 'Cnt.h', 'poly contact without Metal1 (ok: with Metal1)')
def _(c, bad):
    c.box('GatPoly', -0.07, -0.07, 0.23, 0.23)
    c.cont(0, 0, m1=None if bad else 0.07)

@test('Cnt_j', 'Cnt.j', 'contact on the gate (GatPoly over Activ) of an NMOS (ok: none)')
def _(c, bad):
    nmos(c, W=1.0, L=0.30, gate_cont=bad, cnt_f=0.11)
    if bad:
        c.box('Metal1', 0.385 - 0.05, 0.42 - 0.18, 0.545 + 0.05, 0.58 + 0.18)

@test('M1_c', 'M1.c', 'Metal1 pad shifted 0.02 off a poly contact (ok: covering)')
def _(c, bad):
    c.box('GatPoly', -0.07, -0.07, 0.23, 0.23)
    c.box('Cont', 0, 0, 0.16, 0.16)
    d = 0.02 if bad else 0.0
    c.box('Metal1', d, -0.1, 0.16 + d + 0.15, 0.36)

@test('M1_i', 'M1.i', 'two parallel 45-degree Metal1 strips (width 0.21) 0.20 apart (ok 0.22)')
def _(c, bad):
    D = 0.585 if bad else 0.615   # horizontal offset; perpendicular gap = D/sqrt(2) - 0.15*sqrt(2)
    d = 0.15
    for off in (0.0, D):
        c.poly('Metal1', [(off, 0), (off + 2.0, 2.0), (off + 2.0 - d, 2.0 + d), (off - d, d)])

@test('V1_b1', 'V1.b1', '4 x 4 Via1 array at 0.22 space (ok 0.29 in one direction)')
def _(c, bad):
    gx = 0.22 if bad else 0.29
    gy = 0.22
    n = 4
    w = 0.1 + n * 0.19 + (n - 1) * gx
    h = 0.1 + n * 0.19 + (n - 1) * gy
    c.box('Metal1', 0, 0, w, h); c.box('Metal2', 0, 0, w, h)
    for i in range(n):
        for j in range(n):
            x = 0.05 + i * (0.19 + gx); y = 0.05 + j * (0.19 + gy)
            c.box('Via1', x, y, x + 0.19, y + 0.19)

@test('CntB_a1', 'CntB.a1', 'bar contact 0.16 x 0.30 on Activ (ok 0.16 x 0.34)')
def _(c, bad):
    l = 0.30 if bad else 0.34
    c.box('Activ', 0, 0, 0.30, l + 0.14)
    c.box('Cont', 0.07, 0.07, 0.23, 0.07 + l)
    c.box('Metal1', 0.02, -0.1, 0.28, l + 0.24)
    c.box('Activ', 1.0, 0, 1.3, 0.5); c.cont(1.07, 0.17); c.box('pSD', 0.8, -0.2, 1.5, 0.7)

@test('CntB_b2', 'CntB.b2', 'bar contact 0.20 from a square contact (ok 0.22)')
def _(c, bad):
    g = 0.20 if bad else 0.22
    w = 0.07 + 0.16 + g + 0.16 + 0.07
    c.box('Activ', 0, 0, w, 0.64)
    c.box('Cont', 0.07, 0.07, 0.23, 0.57)
    c.box('Cont', 0.23 + g, 0.24, 0.39 + g, 0.40)
    c.box('Metal1', 0.02, -0.1, w - 0.02, 0.62)
    c.box('Activ', w + 0.5, 0, w + 0.8, 0.5); c.cont(w + 0.57, 0.17); c.box('pSD', w + 0.3, -0.2, w + 1.0, 0.7)

@test('Cnt_big', 'Cnt.a', 'contact drawn 0.30 x 0.30 on a poly pad (ok 0.16)')
def _(c, bad):
    s = 0.30 if bad else 0.16
    c.box('GatPoly', -0.07, -0.07, s + 0.07, s + 0.07)
    c.box('Cont', 0, 0, s, s)
    c.box('Metal1', -0.07, -0.07, s + 0.07, max(s + 0.07, 0.31))

@test('V1_big', 'V1.a', 'Via1 drawn 0.30 x 0.30 (ok 0.19)')
def _(c, bad):
    s = 0.30 if bad else 0.19
    c.box('Metal1', -0.1, -0.1, s + 0.1, s + 0.1); c.box('Metal2', -0.1, -0.1, s + 0.1, s + 0.1)
    c.box('Via1', 0, 0, s, s)

@test('Pin_e', 'Pin.e', 'Metal1.pin (8/2) box with no Metal1 under it (ok: Metal1 under it)')
def _(c, bad):
    c.box('Metal1.pin', 0, 0, 0.5, 0.5)
    if not bad:
        c.box('Metal1', 0, 0, 0.5, 0.5)

@test('Pin_a', 'Pin.a', 'Activ.pin (1/2) box with no Activ under it (ok: Activ under it)')
def _(c, bad):
    c.box('Activ.pin', 0, 0, 0.5, 0.5)
    if not bad:
        c.box('Activ', 0, 0, 0.5, 0.5)

@test('forbidden', 'forbidden.biwind', 'a BiWind (3/0) box (ok: none, Metal1 only)')
def _(c, bad):
    c.box('Metal1', 0, 0, 0.5, 0.5)
    if bad:
        c.box('BiWind', 0, 1.0, 0.5, 1.5)

@test('offgrid', 'Offgrid', 'Metal1 box with one edge at x = 0.502 (off the 5 nm grid; ok 0.505)')
def _(c, bad):
    c.box('Metal1', 0, 0, 0.502 if bad else 0.505, 0.5)

@test('angle_m1', 'Angle45', 'Metal1 polygon with a 30-degree edge (ok: 45-degree edge)')
def _(c, bad):
    if bad:
        c.poly('Metal1', [(0, 0), (1.0, 0), (1.0, 0.5), (0.5, 0.5), (0, 0.21)])
        # edge from (0, 0.2115) to (0.5, 0.5): ~30 degrees
    else:
        c.poly('Metal1', [(0, 0), (1.0, 0), (1.0, 0.5), (0.3, 0.5), (0, 0.2)])

@test('angle_poly', 'x.2/Angle45', 'field GatPoly polygon with a 30-degree edge (ok: 45-degree)')
def _(c, bad):
    if bad:
        c.poly('GatPoly', [(0, 0), (1.0, 0), (1.0, 0.5), (0.5, 0.5), (0, 0.21)])
    else:
        c.poly('GatPoly', [(0, 0), (1.0, 0), (1.0, 0.5), (0.3, 0.5), (0, 0.2)])


@test('Gat_a2', 'Gat.a2', 'LV PMOS channel length 0.12 (ok 0.13)')
def _(c, bad):
    pmos(c, L=0.12 if bad else 0.13)

@test('CntB_b', 'CntB.b', 'two bar contacts 0.27 apart (ok 0.28)')
def _(c, bad):
    g = 0.27 if bad else 0.28
    w = 0.07 + 0.16 + g + 0.16 + 0.07
    c.box('Activ', 0, 0, w, 0.64)
    c.box('Cont', 0.07, 0.07, 0.23, 0.57); c.box('Cont', 0.23 + g, 0.07, 0.39 + g, 0.57)
    c.box('Metal1', 0.02, -0.1, w - 0.02, 0.62)
    c.box('Activ', w + 0.5, 0, w + 0.8, 0.5); c.cont(w + 0.57, 0.17); c.box('pSD', w + 0.3, -0.2, w + 1.0, 0.7)

@test('CntB_h1', 'CntB.h1', 'Metal1 enclosure of a bar contact 0.04 (ok 0.05)')
def _(c, bad):
    e = 0.04 if bad else 0.05
    c.box('Activ', 0, 0, 0.30, 0.64)
    c.box('Cont', 0.07, 0.07, 0.23, 0.57)
    c.box('Metal1', 0.07 - e, 0.07 - e, 0.23 + e, 0.57 + e)
    c.box('Activ', 1.0, 0, 1.3, 0.5); c.cont(1.07, 0.17); c.box('pSD', 0.8, -0.2, 1.5, 0.7)

@test('nSDB_b', 'nSDB.b', 'nSD:block space 0.30 (ok 0.31), alone')
def _(c, bad):
    g = 0.30 if bad else 0.31
    c.box('nSD.block', 0, 0, 1.0, 1.0); c.box('nSD.block', 1.0 + g, 0, 2.0 + g, 1.0)

@test('EXTB_b', 'EXTB.b', 'EXTBlock space 0.30 (ok 0.31), alone')
def _(c, bad):
    g = 0.30 if bad else 0.31
    c.box('EXTBlock', 0, 0, 1.0, 1.0); c.box('EXTBlock', 1.0 + g, 0, 2.0 + g, 1.0)

@test('Sal_e', 'Sal.e', 'SalBlock 0.19 from a diffusion contact (ok 0.20)')
def _(c, bad):
    g = 0.19 if bad else 0.20
    c.box('Activ', 0, 0, 2.0, 0.5); c.cont(0.07, 0.17)
    c.box('SalBlock', 0.23 + g, -0.3, 1.5, 0.8)
    c.box('Activ', 2.5, 0, 2.8, 0.5); c.cont(2.57, 0.17); c.box('pSD', 2.3, -0.2, 3.0, 0.7)

@test('Cnt_a', 'Cnt.a', 'contact 0.15 square on a poly pad (ok 0.16)')
def _(c, bad):
    s = 0.15 if bad else 0.16
    c.box('GatPoly', -0.07, -0.07, 0.23, 0.23)
    c.box('Cont', 0, 0, s, s)
    c.box('Metal1', -0.07, -0.07, 0.23, 0.24)

@test('Gat_e', 'Gat.e', 'field GatPoly area 0.0845 (0.13 x 0.65; ok 0.13 x 0.70)')
def _(c, bad):
    c.box('GatPoly', 0, 0, 0.13, 0.65 if bad else 0.70)

@test('Act_d', 'Act.d', 'lone Activ area 0.12 (0.3 x 0.4; ok 0.3 x 0.41)')
def _(c, bad):
    c.box('Activ', 0, 0, 0.3, 0.40 if bad else 0.41)

# ---------------- base devices (clean references) ----------------

@test('base_nmos', '-', 'hand-drawn NMOS W 0.5 L 0.13 with p-tap (bad = same, no tap: shows LU.b)')
def _(c, bad):
    nmos(c, tap=not bad)

@test('base_pmos', '-', 'hand-drawn PMOS W 0.5 L 0.13 in NWell with n-tap (bad = same, no n-tap: shows LU.a)')
def _(c, bad):
    pmos(c, tap=not bad)


CASES = []   # (name, description, draw(Cell), control)
RULE_OF = {}
for _tid, _rule, _what, _fn in T:
    CASES.append((_tid + "_ok", _what + " [ok variant]", (lambda fn: lambda c: fn(c, False))(_fn), None))
    CASES.append((_tid, _what, (lambda fn: lambda c: fn(c, True))(_fn), _tid + "_ok"))
    RULE_OF[_tid] = _rule


# ---------------- section 4: hand-drawn devices with implants or markers missing or too small
SOURCES = {}


def hand(name, what, fn):
    CASES.append((name, what, fn, None))
    SOURCES[name] = "GAPS-ihp-sg13g2 4"


hand('H_pmos_ok', 'hand-drawn PMOS, pSD 0.18 around Activ and 0.30 past the gate', lambda c: pmos(c))
hand('H_pmos_nopsd', 'hand-drawn PMOS, no pSD', lambda c: pmos(c, psd=False))
hand('H_pmos_psdflush', 'hand-drawn PMOS, pSD exactly the Activ (pSD.c, pSD.i violated)', lambda c: pmos(c, psd_c=0.0, psd_i=0.0))
hand('H_pmos_psdhalf', 'hand-drawn PMOS, pSD stops 0.05 past the gate: drain not covered',
     lambda c: pmos(c, psd_box=(-0.18, -0.30, 0.52, 0.80)))
hand('H_pmos_nowell', 'hand-drawn PMOS with pSD, no NWell', lambda c: pmos(c, nwell=False))
hand('H_nmos_ok', 'hand-drawn NMOS with p-tap', lambda c: nmos(c))
def _psdover(c):
    nmos(c); c.box('pSD', -0.3, -0.5, 1.0, 1.2)
hand('H_nmos_psdover', 'hand-drawn NMOS with a stray pSD box over the transistor', _psdover)
hand('H_hvnmos_ok', 'hand-drawn HV NMOS L 0.45, ThickGateOx 0.27 around', lambda c: nmos(c, L=0.45, thk=True, tap_gap=0.8))
hand('H_hvnmos_nothk', 'hand-drawn HV NMOS L 0.45, no ThickGateOx', lambda c: nmos(c, L=0.45, tap_gap=0.8))
hand('H_hvnmos_thksmall', 'hand-drawn HV NMOS L 0.45, ThickGateOx only 0.10 past Activ (TGO.a)',
     lambda c: nmos(c, L=0.45, thk=True, thk_enc=0.10, tap_gap=0.8))
def _tap(sub, lbl):
    def f(c):
        c.box('Activ', 0, 0, 0.3, 0.5); c.cont(0.07, 0.17); c.box('pSD', -0.2, -0.2, 0.5, 0.7)
        if sub:
            c.box('Substrate', -0.2, -0.2, 0.5, 0.7)
        if lbl:
            c.text('TEXT', 'sub!', 0.15, 0.25)
    return f
hand('H_ptap_plain', 'p-tap: Activ + pSD + Cont + Metal1, no Substrate (40/0)', _tap(False, False))
hand('H_ptap_sub', 'p-tap with a Substrate (40/0) box', _tap(True, False))
hand('H_ptap_sublbl', 'p-tap with Substrate (40/0) and a sub! text on 63/0', _tap(True, True))


# ---------------------------------------------------------------- hand-drawn inverter
LABELS = (('A', 0.405, 1.25), ('Y', 1.05, 1.25), ('VDD', 1.0, 3.6), ('VSS', 1.0, -0.6))


def hand_inverter(c, lbl="t25pin", swap=False, open_drain=False):
    """ihp-sg13g2/lvs/build_inv.py hand(): W 0.5, L 0.13. lbl t25pin: texts on
    8/25 over 8/2 boxes; none: no labels."""
    c.box('Activ', 0, 0, 0.81, 0.5); c.box('Activ', 0, 2.0, 0.81, 2.5)
    c.box('GatPoly', 0.34, -0.18, 0.47, 2.68); c.box('GatPoly', 0.255, 1.1, 0.555, 1.4)
    c.box('Cont', 0.325, 1.17, 0.485, 1.33); c.box('Metal1', 0.255, 1.095, 0.555, 1.405)
    for y in (0.17, 2.17):
        c.box('Cont', 0.07, y, 0.23, y + 0.16); c.box('Cont', 0.58, y, 0.74, y + 0.16)
    c.box('NWell', -0.5, 1.69, 2.3, 3.3)
    c.box('pSD', -0.18, 1.70, 0.99, 2.80)
    c.box('Activ', 1.4, 2.55, 1.7, 3.0); c.box('Cont', 1.47, 2.695, 1.63, 2.855)
    c.box('Activ', 1.31, 0, 1.61, 0.5); c.box('pSD', 1.10, -0.2, 1.81, 0.7); c.box('Cont', 1.38, 0.17, 1.54, 0.33)
    c.box('Metal1', -0.5, -0.8, 2.3, -0.4); c.box('Metal1', 0.02, -0.8, 0.28, 0.38); c.box('Metal1', 1.33, -0.8, 1.59, 0.38)
    c.box('Metal1', -0.5, 3.4, 2.3, 3.8); c.box('Metal1', 0.02, 2.12, 0.28, 3.8); c.box('Metal1', 1.42, 2.645, 1.68, 3.8)
    c.box('Metal1', 0.53, 0.12, 1.15, 0.38); c.box('Metal1', 0.53, 2.12, 1.15, 2.38)
    if open_drain:   # the Y strip cut above the NMOS drain; the Y label stays on the upper piece
        c.box('Metal1', 0.95, 0.12, 1.15, 0.80); c.box('Metal1', 0.95, 1.10, 1.15, 2.38)
    else:
        c.box('Metal1', 0.95, 0.12, 1.15, 2.38)
    labels = LABELS
    if swap:
        labels = (('Y', 0.405, 1.25), ('A', 1.05, 1.25)) + LABELS[2:]
    if lbl == "t25pin":
        for s, x, y in labels:
            c.text('Metal1.text', s, x, y)
            c.box('Metal1.pin', x - 0.1, y - 0.1, x + 0.1, y + 0.1)


# ---------------------------------------------------------------- hier
# The review's two-level cells (design-0.6.md 3.1): the hand inverter
# (inv_hand_t25pin) with these layers moved into a parent cell.
HIER = {
    "base": ["inv"],
    "groups": {"psd": [(14, 0)], "nw": [(31, 0)], "all": [(14, 0), (31, 0), (44, 0)]},
    "expect": {
        "inv": ({}, {"sg13_lv_nmos": 1, "sg13_lv_pmos": 1}),
        "inv_psd_h": ({"NW.d": 11, "LU.b": 3}, {"sg13_lv_nmos": 1}),
        "inv_nw_h": ({"Can't overlap those layers": 3, "NW.d": 6, "NW.f": 17}, {"sg13_lv_nmos": 1}),
        "inv_all_h": ({"Can't overlap those layers": 3, "NW.d": 14, "LU.b": 6}, {"sg13_lv_nmos": 2}),
    },
    "gate": ["inv_psd_h", "inv_nw_h", "inv_all_h"],
}
HIER_BASE_DRAW = {"inv": lambda c: hand_inverter(c)}

# ---------------------------------------------------------------- whole_shape
def _lu_long(c):
    """A 100 x 3 um NWell with one contacted n-tap at its left end and a PMOS
    15 um from the tap, inside LU.a's 20 um (P-diff distance to N-tap, drc.tech:159).
    Magic grows the tap's reach through the NWell in 32 steps of 0.62 um
    (cifout templayer ntap_reach), so the rule looks 20 um across the well."""
    c.box('NWell', 0, 0, 100, 3)
    c.box('Activ', 0.8, 1.25, 1.1, 1.75); c.cont(0.87, 1.42)
    pmos(c, x=15.0, y=1.25, tap=False, nwell=False)


WHOLE_SHAPE = [
    dict(name="lu_long", draw=_lu_long, targets=["LU.a"], expect={}, box=[14, -1, 17, 4],
         measured={"by": "Magic 8.3.681 in the pinned image, 2026-11-23", "drc(full)": {}},
         notes="Magic's whole-cell check finds no LU.a (measured in this build); an area check of `box` that does not reach the "
               "tap 14 um away would. Not measured by the GAPS or the review, so expect is empty. The review's "
               "candidates nmosi.d (cifmaxwidth nwell_missing, drc.tech:60) needs a deep n-well and is a local "
               "and-not (cifout templayer nwell_missing), and Act.e (diff_hole_empty, drc.tech:151) is a hole "
               "area; neither has a long-well form, so LU.a's bounded 20 um reach is the case built.",
         source="GAPS-ihp-sg13g2 2a (LU.a, nmosi.d, Act.e); design-0.6.md 3.1"),
]

# ---------------------------------------------------------------- names
NAMES_ERROR = ("Metal1", (0, 0, 0.12, 1.0), "M1.a")

# ---------------------------------------------------------------- inverters
INV_TOP = "inv"
SCHEMATIC = """.subckt {top} A Y VDD VSS
XMN Y A VSS VSS sg13_lv_nmos w={wn}u l=0.13u ng=1 m=1
XMP Y A VDD VDD sg13_lv_pmos w={wp}u l=0.13u ng=1 m=1
.ends
"""
SCH_W = {"wn": 0.5, "wp": 0.5}


def inverter_variants():
    return [
        ("inv", lambda c: hand_inverter(c), "hand-drawn inverter W 0.5 L 0.13, texts on 8/25 over 8/2 boxes",
         {"netgen": "match uniquely", "klayout": {"lvs": "match"}}, "GAPS-ihp-sg13g2 6 (inv_hand_t25pin)"),
        ("inv_open_drain", lambda c: hand_inverter(c, open_drain=True), "the Y strip cut above the NMOS drain", {}, ""),
        ("inv_swap", lambda c: hand_inverter(c, swap=True), "A and Y labels exchanged", {}, ""),
        ("inv_no_text", lambda c: hand_inverter(c, lbl="none"), "no labels (inv_hand_none)", {}, "GAPS-ihp-sg13g2 5"),
    ]


# ---------------------------------------------------------------- controls
CONTROLS = {
    "lib": "sg13g2_stdcell",
    "cells": ["sg13g2_inv_1", "sg13g2_nand2_1", "sg13g2_dfrbp_1", "sg13g2_mux2_1", "sg13g2_tiehi",
              "sg13g2_buf_1", "sg13g2_decap_4"],
    "expect_f1": "no Magic-minus-user area on any implant or marker layer (measured by the review in "
                 "the image)",
}


# ---------------------------------------------------------------- PCell inverter
def pcell_inverter(db, ly):
    """ihp-sg13g2/lvs/build_inv.py pcell_inv(): the plugin's sg13_lv_nmos and
    sg13_lv_pmos at their defaults (W 0.6, L 0.13), wired in Metal1, texts on
    8/25 over 8/2 boxes."""
    top = ly.create_cell('inv_pcell')

    def b(layer, x1, y1, x2, y2):
        top.shapes(ly.layer(*LAYERS[layer])).insert(db.DBox(x1, y1, x2, y2))

    n = ly.create_cell('sg13_lv_nmos', 'sg13g2_magic', {})
    p = ly.create_cell('sg13_lv_pmos', 'sg13g2_magic', {})
    py = 2.2
    top.insert(db.DCellInstArray(n.cell_index(), db.DTrans(0, 0)))
    top.insert(db.DCellInstArray(p.cell_index(), db.DTrans(0, py)))
    b('Metal1', -0.215, 0.415, 0.215, py - 0.415)
    b('Metal1', -1.0, -0.1, -0.125, 0.1); b('Metal1', -1.0, py - 0.1, -0.125, py + 0.1); b('Metal1', -1.0, -0.1, -0.8, py + 0.1)
    b('Metal1', 0.125, -0.1, 1.2, 0.1); b('Metal1', 1.0, -1.4, 1.2, 0.1); b('Metal1', -1.5, -1.6, 2.2, -1.2)
    b('Activ', -0.2, -1.55, 0.5, -1.25); b('Cont', 0.07, -1.48, 0.23, -1.32); b('pSD', -0.4, -1.75, 0.7, -1.05)
    b('Metal1', 0.125, py - 0.1, 1.2, py + 0.1); b('Metal1', 1.0, py - 0.1, 1.2, 3.6); b('Metal1', -1.5, 3.4, 2.2, 3.8)
    b('Activ', -0.2, 3.45, 0.5, 3.75); b('Cont', 0.07, 3.52, 0.23, 3.68); b('NWell', -0.715, py, 0.74, 4.0)
    for s, x, y in (('A', 0.0, 1.1), ('Y', -0.9, 1.1), ('VDD', 1.8, 3.6), ('VSS', 1.8, -1.4)):
        top.shapes(ly.layer(*LAYERS['Metal1.text'])).insert(db.DText(s, x, y))
        b('Metal1.pin', x - 0.1, y - 0.1, x + 0.1, y + 0.1)
    return top


PCELL_EXPECT = ({"netgen": "match uniquely", "klayout": {"lvs": "no match (flat); match with --run_mode=deep"}},
                "GAPS-ihp-sg13g2 6 (PCell inverter)")
PCELL_SCH_W = {"wn": 0.6, "wp": 0.6}

ANCHORS = {"Gat_c": "Gat.c"}
