#!/usr/bin/env python3
"""Build a PDK's data file from the installed PDK's Magic tech file, its
KLayout layer properties and its KLayout LVS deck.

Run inside the pinned image, where the PDKs are installed under PDK_ROOT
(standard library only, no Magic and no klayout module needed)::

    python3 tools/build_pdk_data.py --pdk sky130A          # rewrite the shipped data file
    python3 tools/build_pdk_data.py --pdk sky130A --check  # compare with the shipped one
    python3 tools/build_pdk_data.py --all [--check]        # every supported PDK
    python3 tools/build_pdk_data.py --pdk sky130A --out other.json [--pdk-root DIR]

The file is ``python/klayout_magic_pcells/data/pdk-<pdk>.json``; its schema
is the one ``pdkdata.py`` reads. ``--check`` rebuilds in memory and fails on
any difference from the committed file, and also compares the KLayout DRC
deck names and switches of ``PROFILES`` in ``tests/parity/drc.py`` with the
installed decks. ``tools/pdk_data_overrides.json`` holds the few hand-typed
rows, each citing its tech-file line.

Only layer numbers and line citations are taken from the KLayout decks,
never their text. Exit status: 0 when written or when ``--check`` finds no
difference, 1 when ``--check`` finds one, 2 on errors.
"""

import argparse
import collections
import hashlib
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "python"))

from klayout_magic_pcells.config import SUPPORTED_PDKS  # noqa: E402
from klayout_magic_pcells.pdkdata import SCHEMA, shipped_data  # noqa: E402

OVERRIDES = os.path.join(HERE, "pdk_data_overrides.json")
DRC_PY = os.path.join(REPO, "tests", "parity", "drc.py")

# Where each PDK keeps the files the builder reads, relative to <PDK_ROOT>/<pdk>.
PDK_FILES = {
    "sky130A": {"lyp": "libs.tech/klayout/tech/sky130A.lyp",
                "klayout_lvs": "libs.tech/klayout/lvs/sky130.lvs"},
    "gf180mcuD": {"lyp": "libs.tech/klayout/tech/gf180mcu.lyp",
                  "klayout_lvs": "libs.tech/klayout/tech/lvs/gf180mcu.lvs"},
    "ihp-sg13g2": {"lyp": "libs.tech/klayout/tech/sg13g2.lyp",
                   "klayout_lvs": "libs.tech/klayout/tech/lvs/sg13g2.lvs"},
    "ihp-sg13cmos5l": {"lyp": "libs.tech/klayout/tech/sg13cmos5l.lyp",
                       "klayout_lvs": "libs.tech/klayout/tech/lvs/sg13cmos5l.lvs"},
}
ERROR_MARKER = [255, 0]


# -- reading the tech file ------------------------------------------------------

Stmt = collections.namedtuple("Stmt", "file line text toks")


def read_lines(path, _seen=None):
    """The tech file as (file name, line number, text), with every
    ``include <name>`` line replaced by that file's lines (the IHP tech
    files keep cifoutput, cifinput, drc and extract in their own files)."""
    seen = _seen if _seen is not None else []
    seen.append(path)
    out = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for no, text in enumerate(f.read().split("\n"), 1):
            m = re.match(r"^\s*include\s+(\S+)\s*$", text)
            if m:
                inc = os.path.join(os.path.dirname(path), m.group(1))
                if not os.path.isfile(inc) and os.path.isfile(inc + ".tech"):
                    inc += ".tech"
                out += read_lines(inc, seen)
                continue
            out.append((os.path.basename(path), no, text))
    return out


def statements(lines):
    """Logical statements: a line ending in a backslash continues on the
    next one, and a statement whose first character is ``#`` is a comment
    (a commented rule with a continued why-text is one comment)."""
    out = []
    i = 0
    while i < len(lines):
        fname, no, text = lines[i]
        s = text.rstrip()
        while s.endswith("\\") and i + 1 < len(lines) and lines[i + 1][0] == fname:
            i += 1
            s = s[:-1].rstrip() + " " + lines[i][2].strip()
        i += 1
        s = s.strip()
        if not s or s.startswith("#"):
            continue
        out.append(Stmt(fname, no, s, s.split()))
    return out


def sections(stmts):
    """{section name: [statements]}, the first section of each name. A
    section runs from its name to the next ``end`` at section level."""
    out = {}
    cur = None
    for st in stmts:
        if cur is None:
            cur = st.toks[0]
            body = []
            continue
        if st.toks[0] == "end" and len(st.toks) == 1:
            out.setdefault(cur, body)
            cur = None
            continue
        body.append(st)
    return out


def styles(body):
    """[(style name, [variants], [statements])] of a cifoutput, cifinput or
    drc section. ``style gdsii variants (),(origfill)`` gives the variants
    ``["", "origfill"]``."""
    out = []
    for st in body:
        if st.toks[0] == "style" and len(st.toks) >= 2:
            variants = []
            if len(st.toks) >= 4 and st.toks[2] == "variants":
                variants = [v.strip("() ") for v in " ".join(st.toks[3:]).split(",")]
            out.append((st.toks[1], variants, st, []))
        elif out:
            out[-1][3].append(st)
    return out


def in_variant(body, variant=""):
    """The statements of a style that apply to one of its variants: a
    ``variants (a),(b)`` line limits what follows to those variants and
    ``variants *`` ends the limit."""
    out = []
    active = True
    for st in body:
        if st.toks[0] == "variants":
            spec = " ".join(st.toks[1:]).strip()
            active = spec == "*" or variant in [v.strip("() ") for v in spec.split(",")]
            continue
        if active:
            out.append(st)
    return out


def cite(st):
    return "%s:%d" % (st.file, st.line)


def num(text):
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def um(value_nm):
    """A distance in nm as µm, rounded to the 0.1 nm the tech files can give."""
    return None if value_nm is None else round(value_nm / 1000.0, 7)


# -- DRC section ----------------------------------------------------------------

DRC_CONTROL = {"style", "scalefactor", "cifstyle", "variants", "exemption", "exception",
               "stepsize"}
# keyword: (index of the type arguments, index of the value, unit)
DRC_SHAPE = {
    "width": ((0,), 1, "um"), "maxwidth": ((0,), 1, "um"), "spacing": ((0, 1), 2, "um"),
    "widespacing": ((0, 2), 3, "um"), "surround": ((0, 1), 2, "um"),
    "overhang": ((0, 1), 2, "um"), "extend": ((0, 1), 2, "um"), "edge4way": ((0, 1), 2, "um"),
    "edge": ((0, 1), 2, "um"), "area": ((0,), 1, "um2"), "angles": ((0,), 1, "deg"),
    "rect_only": ((0,), None, None), "exact_overlap": ((0,), None, None),
    "no_overlap": ((0, 1), None, None), "off_grid": ((0,), 1, "um"),
    "cifwidth": ((0,), 1, "um"), "cifspacing": ((0, 1), 2, "um"), "cifarea": ((0,), 1, "um2"),
    "cifmaxwidth": ((0,), 1, "um"), "option": ((), None, None),
}
ID_TOKEN = re.compile(r"^[A-Za-z][\w/]*(?:\.[\w/]+)+$")


def why_text(text):
    """The why-text of a rule statement and the text before it. Two
    sky130A statements lack the closing quote; the text runs to the end."""
    q = text.find('"')
    if q < 0:
        return "", text
    rest = text[q + 1:]
    e = rest.find('"')
    return (rest if e < 0 else rest[:e]).strip(), text[:q]


def rule_ids(why):
    """(text in the why-text's last parentheses, [rule IDs]). Composites
    are split: "licon.9 + psdm.5a", "V1.a + 2 * M2.c", "V1.c - M2.c",
    "MIMTM.4-VT.4", "nwell.5a, 7" (nwell.7) and "diff/tap.17,19". Words
    that are not IDs ("Cnt.c SRAM exception", "Grid Rules") are dropped;
    an empty result means the rule is keyed by its why-text."""
    m = re.search(r"\(([^()]*)\)\s*$", why)
    if not m:
        return "", []
    text = m.group(1).strip()
    ids = []
    family = None
    for part in re.split(r"\s*\+\s*|\s+-\s+|(?<=\w)-(?=[A-Z])|\s*,\s*", text):
        part = re.sub(r"^\d+\s*\*\s*", "", part.strip())
        for tok in part.split():
            if ID_TOKEN.match(tok):
                ids.append(tok)
                family = tok.rsplit(".", 1)[0]
            elif family and re.match(r"^\d+[a-z]?$", tok) and tok is part.split()[0]:
                ids.append(family + "." + tok)
    return text, list(dict.fromkeys(ids))


def parse_drc(body, lambda_nm):
    """Every rule statement of the drc section (all styles), with the
    styles it belongs to, its values in µm and its rule IDs."""
    style_names = []
    rules = []
    for name, variants, _st, sbody in styles(body):
        names = ["%s(%s)" % (name, v) if v else name for v in variants] or [name]
        style_names += names
        scale = 1.0
        current = list(names)
        block = None
        for st in sbody:
            kw = st.toks[0]
            if kw == "scalefactor":
                scale = num(st.toks[1]) or 1.0
                continue
            if kw == "variants":
                spec = " ".join(st.toks[1:]).strip()
                current = list(names) if spec == "*" else [
                    "%s(%s)" % (name, v.strip("() ")) for v in spec.split(",")]
                continue
            if kw in ("exemption", "exception"):
                block = None if st.toks[1] == "none" else "%s %s" % (kw, st.toks[1])
                continue
            if kw in DRC_CONTROL:
                continue
            why, head = why_text(st.text)
            args = head.split()[1:]
            tidx, vidx, unit = DRC_SHAPE.get(kw, ((0,), None, None))
            value = num(args[vidx]) if vidx is not None and vidx < len(args) else None
            if value is not None and unit in ("um", "um2"):
                cif = kw.startswith("cif")
                # cif rules measure layers of the drc cifoutput style, in its
                # units (nm); the others are in lambda / scalefactor.
                per = 1.0 if cif else lambda_nm / scale
                value = round(value * per / 1000.0, 7) if unit == "um" else \
                    round(value * per * per / 1e6, 9)
            elif unit != "deg":
                value = None if unit is None else value
            id_text, ids = rule_ids(why)
            rule = {"line": st.line, "file": st.file, "keyword": kw, "styles": list(current),
                    "types": [args[i] for i in tidx if i < len(args)],
                    "value_um": value, "unit": unit if value is not None else None,
                    "why": why, "id_text": id_text, "ids": ids, "block": block,
                    "args": args}
            if kw == "widespacing" and len(args) > 1:
                rule["width_um"] = round(num(args[1]) * lambda_nm / scale / 1000.0, 7)
            rules.append(rule)
    return style_names, rules


# -- cifoutput ------------------------------------------------------------------

class CifBlock:
    """One ``layer`` or ``templayer`` of a cif style: its sources (types,
    aliases or templayer names), its operations, and its calma pair."""

    def __init__(self, kind, name, sources, st):
        self.kind, self.name, self.sources, self.st = kind, name, sources, st
        self.ops = []
        self.calma = []
        self.labels = []

    def __repr__(self):
        return "<%s %s %s>" % (self.kind, self.name, self.sources)


def split_list(text):
    return [t for t in re.split(r"[,\s]+", text) if t]


def parse_cif_blocks(body):
    """The blocks of a cifoutput or cifinput style, in order, plus the
    style-level statements (cifinput's ``calma`` and ``ignore`` lines)."""
    blocks = []
    top = []
    cur = None
    for st in body:
        kw = st.toks[0]
        if kw in ("layer", "templayer"):
            cur = CifBlock(kw, st.toks[1], split_list(" ".join(st.toks[2:])), st)
            blocks.append(cur)
        elif kw == "calma" and len(st.toks) >= 4 and not st.toks[1].isdigit():
            # cifinput: "calma <CIF layer> <gds layer> <datatypes>"
            top.append(st)
        elif kw in ("ignore", "options", "scalefactor", "gridlimit", "render"):
            top.append(st)
        elif cur is not None:
            if kw == "calma":
                cur.calma.append(st)
            elif kw == "labels":
                cur.labels.append(st)
            cur.ops.append(st)
        else:
            top.append(st)
    return blocks, top


def calma_pairs(st, first):
    """GDS (layer, datatype) pairs of a calma statement; the datatypes may
    be a comma list."""
    toks = st.toks[first:]
    if len(toks) < 2:
        return []
    out = []
    for d in toks[1].split(","):
        if re.match(r"^\d+$", toks[0]) and re.match(r"^\d+$", d):
            out.append((int(toks[0]), int(d)))
    return out


def parse_cifout(section, style="gdsii"):
    """The cifoutput style Magic writes GDS with, its default variant."""
    for name, variants, st, body in styles(section):
        if name == style:
            body = in_variant(body, "")
            scale = next((num(s.toks[1]) for s in body if s.toks[0] == "scalefactor"), None)
            grid = next((num(s.toks[1]) for s in body if s.toks[0] == "gridlimit"), None)
            unit = next((s.toks[2] for s in body if s.toks[0] == "scalefactor" and len(s.toks) > 2),
                        "")
            blocks, _top = parse_cif_blocks(body)
            return {"style": st, "scale": scale, "unit": unit, "gridlimit": grid,
                    "blocks": blocks}
    raise ValueError("no cifoutput style %s" % style)


# -- cifinput -------------------------------------------------------------------

def parse_cifin(section):
    """What the first (default) cifinput style does with each CIF layer:
    which GDS pairs it maps to, the Magic types it paints, the types whose
    reading it decides, its labels, and whether it is ignored."""
    name, variants, st, body = styles(section)[0]
    body = in_variant(body, variants[0] if variants else "")
    scale = next((num(s.toks[1]) for s in body if s.toks[0] == "scalefactor"), None)
    grid = next((num(s.toks[1]) for s in body if s.toks[0] == "gridlimit"), None)
    blocks, top = parse_cif_blocks(body)
    calma = collections.OrderedDict()   # cif name -> [(pair, stmt)]
    ignored = {}
    for s in top:
        if s.toks[0] == "calma" and len(s.toks) >= 4:
            for p in calma_pairs(s, 2):
                calma.setdefault(s.toks[1], []).append((p, s))
        elif s.toks[0] == "ignore":
            for c in split_list(" ".join(s.toks[1:])):
                ignored[c] = s
    temps = {b.name: b for b in blocks if b.kind == "templayer"}
    # The templayers whose shapes end up painted: sources of a layer, or of
    # a templayer that is itself painted ("or" adds a source).
    def sources(b):
        out = list(b.sources)
        for op in b.ops:
            if op.toks[0] == "or":
                out += split_list(" ".join(op.toks[1:]))
        return out
    feeds = collections.defaultdict(set)    # templayer -> Magic types it paints
    changed = True
    while changed:
        changed = False
        for b in blocks:
            types = {b.name} if b.kind == "layer" else feeds.get(b.name, set())
            for s in sources(b):
                if s in temps and not types <= feeds[s]:
                    feeds[s] |= types
                    changed = True
    use = collections.defaultdict(lambda: {"paint": [], "device": [], "labels": []})
    for b in blocks:
        painted = [b.name] if b.kind == "layer" else sorted(feeds.get(b.name, ()))
        for s in sources(b):
            if s in temps:
                continue
            if painted:
                use[s]["paint"].append((painted, b.st))
            else:
                use[s]["device"].append(([], b.st))
        for op in b.ops:
            if op.toks[0] in ("and", "and-not"):
                for s in split_list(" ".join(op.toks[1:])):
                    if s not in temps:
                        use[s]["device"].append((painted, op))
            elif op.toks[0] == "labels":
                kind = op.toks[-1] if op.toks[-1] in ("port", "text") else "label"
                for s in split_list(" ".join(op.toks[1:2])):
                    use[s]["labels"].append((kind, op))
    return {"style": st, "name": name, "scale": scale, "gridlimit": grid, "calma": calma,
            "ignored": ignored, "use": use}


# -- types, planes, contacts, aliases ----------------------------------------------

def parse_types(secs):
    """({type or alias name: canonical type}, {type: plane}, {contact: residues},
    {alias: [types]})."""
    canon, plane = {}, {}
    for st in secs.get("types", []):
        p = st.toks[0].lstrip("-")
        names = split_list(" ".join(st.toks[1:]))
        for n in names:
            canon[n] = names[0]
        if names:
            plane[names[0]] = p
    contacts = {}
    for st in secs.get("contact", []):
        if st.toks[0] in ("stackable", "lumped", "contact", "device"):
            continue
        if st.toks[0] in canon and len(st.toks) >= 3:
            contacts[canon[st.toks[0]]] = [canon.get(t, t) for t in st.toks[1:]]
    aliases = {}
    for st in secs.get("aliases", []):
        if len(st.toks) >= 2:
            aliases[st.toks[0]] = split_list(" ".join(st.toks[1:]))
    return canon, plane, contacts, aliases


def expand_types(names, canon, contacts, aliases, _depth=0):
    """Magic type names a list of names stands for: aliases expanded, a
    leading ``*`` adds the contacts that have the type as a residue, and a
    ``/plane`` suffix is dropped."""
    out = []
    for n in names:
        star = n.startswith("*")
        n = n.lstrip("*").split("/")[0]
        if n in aliases and _depth < 10:
            out += expand_types(aliases[n], canon, contacts, aliases, _depth + 1)
            continue
        t = canon.get(n)
        if t is None:
            continue
        out.append(t)
        if star:
            out += [c for c, res in contacts.items() if t in res]
    return list(dict.fromkeys(out))


# -- KLayout files --------------------------------------------------------------

def parse_lyp(path):
    """{(layer, datatype): name} from a KLayout layer properties file. The
    name is the ``<name>`` text without its " - L/D" suffix, else the name
    in ``<source>`` ("COMP_Label 22/10@1")."""
    out = {}
    if not path or not os.path.isfile(path):
        return out
    root = ET.parse(path).getroot()
    for props in root.iter("properties"):
        src = (props.findtext("source") or "").strip()
        m = re.match(r"^(?:(\S+)\s+)?(\d+)/(\d+)(?:@\d+)?$", src)
        if not m:
            continue
        name = (props.findtext("name") or "").strip()
        name = re.sub(r"\s*-\s*\d+/\d+\s*$", "", name) or (m.group(1) or "")
        out.setdefault((int(m.group(2)), int(m.group(3))), name)
    return out


def lvs_label_calls(pdk_dir, rel):
    """[((layer, datatype), "file:line")] of every ``labels(L, D)`` call in
    the PDK's KLayout LVS deck and the rule-deck files next to it. Only the
    numbers and the line are kept."""
    if not rel:
        return []
    main = os.path.join(pdk_dir, rel)
    if not os.path.isfile(main):
        return []
    files = [main]
    rd = os.path.join(os.path.dirname(main), "rule_decks")
    if os.path.isdir(rd):
        files += sorted(os.path.join(rd, f) for f in os.listdir(rd) if f.endswith(".lvs"))
    out = []
    for f in files:
        with open(f, encoding="utf-8", errors="replace") as fh:
            for no, line in enumerate(fh, 1):
                if line.lstrip().startswith("#"):
                    continue
                for l, d in re.findall(r"\blabels\(\s*(\d+)\s*,\s*(\d+)\s*\)", line):
                    out.append(((int(l), int(d)), "%s:%d" % (os.path.relpath(f, pdk_dir), no)))
    return out


# -- layers ---------------------------------------------------------------------

def key(pair):
    return "%d/%d" % tuple(pair)


# Roles by the layer's name (the .lyp base name or Magic's CIF name), tried
# in this order; the Magic types it paints decide when no name matches.
ROLE_PATTERNS = [
    ("boundary", r"bound|outline|^prb"),
    ("cut", r"^(cont|contact|licon\d?|mcon|via\d*|topvia\d|tv\d|cut)$"),
    ("diffusion", r"^(diff|tap|comp|activ)$"),
    ("poly", r"^(poly|poly\d|gatpoly)$"),
    ("conductor", r"^(li\d?|met\d|metal\d|metaltop|topmetal\d|rdl|pad|capm\d?|mim|m\d)$"),
    ("well", r"well|^dnw|nbulay"),
    ("implant", r"sdm$|^[np]sd$|plus$|^[np]plus|lvtn|hvtp|hvtr|lvid|^nat$|implant|^npc$|^hvi$"
                r"|thkox|dualgate|thickgateox|^ncm$"),
    ("marker", r"areaid|(^|_)(id|mk|mark|marker|block|blk|res|dummy|def)$|_mk|mk$|block|^sab$"
               r"|^sblk$|salblock|heatres|polyres|substrate|digibnd|^res"),
]


def role_of(name, cif_names, read, magic_types, plane, contacts):
    names = [n for n in [name] + list(cif_names) if n]
    base = [re.split(r"[.]", n)[0].lower() for n in names]
    purpose = ""
    m = re.match(r"^[^.]+\.(\w+)", name) or re.match(r"^.+_(label|pin|text)$", name, re.I)
    if m:
        purpose = m.group(1).lower()
    if read == "text" or purpose in ("label", "text"):
        return "text"
    if read == "pin" or purpose == "pin":
        return "pin"
    if purpose in ("boundary",):
        return "boundary"
    for role, pat in ROLE_PATTERNS:
        if any(re.search(pat, n) for n in base):
            return role
    if read == "paint" or read.startswith("reads-as:"):
        planes = {plane.get(t, "") for t in magic_types}
        if magic_types and all(t in contacts for t in magic_types):
            return "cut"
        if any("well" in p for p in planes):
            return "well"
        if planes & {"active", "diff"}:
            return "diffusion"
        if any(re.search(r"metal|^m\d|locali|cap|rdl|pad|passiv", p) for p in planes):
            return "conductor"
    if read == "device-only":
        # read only to decide what the shapes under it are
        return "marker"
    return "other"


def build_layers(cifin, lyp, canon, plane, contacts, overrides):
    """One row per GDS pair that the cifinput style maps or the .lyp lists."""
    by_pair = collections.OrderedDict()
    for cif, pairs in cifin["calma"].items():
        for p, st in pairs:
            by_pair.setdefault(p, []).append((cif, st))
    pairs = sorted(set(by_pair) | set(lyp))
    lyp_by_base = collections.defaultdict(set)
    for p, n in lyp.items():
        lyp_by_base[n.split(".")[0].lower()].add(p)
    rows = []
    for p in pairs:
        cifs = by_pair.get(p, [])
        names = [c for c, _ in cifs]
        paint, device, labels = [], [], []
        for c in names:
            u = cifin["use"].get(c)
            if not u:
                continue
            for types, _st in u["paint"]:
                paint += types
            for types, _st in u["device"]:
                device += types
            labels += [k for k, _st in u["labels"]]
        paint = list(dict.fromkeys(canon.get(t, t) for t in paint))
        device = list(dict.fromkeys(canon.get(t, t) for t in device))
        if not cifs:
            read = "ignored"
        elif all(c in cifin["ignored"] for c in names):
            read = "ignored"
        elif "text" in labels:
            read = "text"
        elif "port" in labels:
            read = "pin"
        elif paint:
            read = "paint"
            mine = lyp.get(p, "").split(".")[0].lower()
            others = [t for t in paint if lyp_by_base.get(t.lower()) and p not in lyp_by_base[t.lower()]]
            if others and len(others) == len(paint) and mine not in [t.lower() for t in paint]:
                read = "reads-as:" + others[0]
        elif device:
            read = "device-only"
        elif labels:
            read = "text"
        else:
            read = "ignored"
        name = lyp.get(p) or (names[0] if names else "")
        row = {"gds": list(p), "name": name, "cif": names,
               "role": None, "read": read,
               "magic_types": paint if read in ("paint", "pin", "text") or read.startswith("reads-as:")
               else [],
               "decides": device if read == "device-only" else [],
               "in_lyp": p in lyp,
               "line": cite(cifs[0][1]) if cifs else None}
        row["role"] = role_of(name, names, read, paint, plane, contacts)
        ov = overrides.get("layers", {}).get(key(p))
        if ov:
            for k, v in ov.items():
                if not k.startswith("_"):
                    row[k] = v
        rows.append(row)
    return rows


# -- cifout table and generated layers -----------------------------------------------

def block_types(block, temps, canon, contacts, aliases, _seen=None):
    """Magic types whose shapes reach a cifoutput layer: its sources and the
    types of its ``or``, ``bloat-or`` and ``bloat-all`` operations, through
    its templayers. ``and`` and ``and-not`` only restrict, so they don't count."""
    seen = _seen if _seen is not None else set()
    if block.name in seen and block.kind == "templayer":
        return []
    seen.add(block.name)
    names = list(block.sources)
    for op in block.ops:
        if op.toks[0] in ("or", "bloat-or", "bloat-all") and len(op.toks) > 1:
            names += split_list(op.toks[1])
    out = []
    for n in names:
        if n in temps:
            out += block_types(temps[n], temps, canon, contacts, aliases, seen)
        else:
            out += expand_types([n], canon, contacts, aliases)
    return list(dict.fromkeys(out))


def build_cifout(cifout, canon, contacts, aliases):
    temps = {b.name: b for b in cifout["blocks"] if b.kind == "templayer"}
    table = collections.defaultdict(list)
    for b in cifout["blocks"]:
        if b.kind != "layer":
            continue
        pairs = [p for st in b.calma for p in calma_pairs(st, 1)]
        if not pairs:
            continue
        for t in block_types(b, temps, canon, contacts, aliases):
            for p in pairs:
                if list(p) not in table[t]:
                    table[t].append(list(p))
    return {t: sorted(v) for t, v in sorted(table.items())}


def contributions(block, temps, lam, _depth=0):
    """How a cifoutput layer is built from Magic types: a list of
    {"from": [names], "nm": distance grown from them, "st": the statement
    that gives the distance, "notes": [...]}. A grow followed by a shrink of
    the same size, a ``bridge`` and a ``close`` close gaps; they are noted
    and not counted."""
    parts = []
    for s in block.sources:
        if s in temps and _depth < 10:
            parts += contributions(temps[s], temps, lam, _depth + 1)
        else:
            parts.append({"from": [s], "nm": 0.0, "st": block.st, "notes": []})
    ops = list(block.ops)
    i = 0
    closing = []
    while i < len(ops):
        op = ops[i]
        kw, args = op.toks[0], op.toks[1:]
        val = num(args[0]) * lam if args and num(args[0]) is not None else None
        if kw == "grow" and val is not None:
            nxt = ops[i + 1] if i + 1 < len(ops) else None
            if nxt is not None and nxt.toks[0] == "shrink" and nxt.toks[1:2] == args[:1]:
                closing.append("grow then shrink %g um at %s (closes gaps)" % (val / 1000.0, cite(op)))
                i += 2
                continue
            for p in parts:
                if not closing:
                    p["nm"] += val
                    p["st"] = op
            i += 1
            continue
        if kw == "shrink" and val is not None and not closing:
            for p in parts:
                p["nm"] -= val
        elif kw == "bloat-or" and len(args) >= 3:
            d = num(args[2])
            parts.append({"from": split_list(args[0]), "nm": (d or 0.0) * lam, "st": op,
                          "notes": ["bloat-or %s" % " ".join(args[1:])]})
        elif kw == "bloat-all" and len(args) >= 2:
            parts.append({"from": split_list(args[0]), "nm": 0.0, "st": op,
                          "notes": ["bloat-all into %s" % args[1]]})
        elif kw == "or" and args:
            for s in split_list(args[0]):
                if s in temps and _depth < 10:
                    parts += contributions(temps[s], temps, lam, _depth + 1)
                else:
                    parts.append({"from": [s], "nm": 0.0, "st": op, "notes": []})
        elif kw == "bridge" and val is not None:
            closing.append("bridge %g um at %s (closes gaps)" % (val / 1000.0, cite(op)))
        elif kw == "close" and val is not None:
            closing.append("close %g um2 at %s (fills holes)" % (num(args[0]) * lam * lam / 1e6, cite(op)))
        elif kw in ("squares", "squares-grid", "slots") and not closing:
            for p in parts:
                p["notes"].append("cut squares (%s) at %s" % (kw, cite(op)))
        elif kw in ("and", "and-not") and not closing:
            for p in parts:
                p["notes"].append("%s %s" % (kw, " ".join(args)))
        i += 1
    for p in parts:
        p["closing"] = closing
    return parts


def build_generated(cifout, layers, canon, contacts, aliases, overrides):
    """For each implant, marker and well layer that Magic regenerates on
    output (its cifinput reading only decides device types, or is ignored),
    the distance the gdsii style grows it from the device shape.

    A layer may be built by several blocks (sky130A NPC on contacts and on
    resistors); their pieces are taken together. ``overrides["generated"]``
    names, per CIF layer, the device shapes F1 measures (one row each, by
    Magic type), and holds the hand-typed rows the parser can't give."""
    # cifoutput distances are in the style's CIF units (nm with
    # "scalefactor N nanometers"), not in lambda
    lam = 1.0 if cifout["unit"].startswith("nano") else 10.0
    temps = {b.name: b for b in cifout["blocks"] if b.kind == "templayer"}
    rows_by_pair = {tuple(r["gds"]): r for r in layers}
    gen_ov = overrides.get("generated", {})
    groups = collections.OrderedDict()
    for b in cifout["blocks"]:
        if b.kind != "layer":
            continue
        pairs = [p for st in b.calma for p in calma_pairs(st, 1)]
        if pairs:
            groups.setdefault((b.name, pairs[0]), []).append(b)
    out = []
    for (name, p), blocks in groups.items():
        row = rows_by_pair.get(p)
        specs = gen_ov.get(name, gen_ov.get(key(p)))
        if isinstance(specs, dict):
            specs = [specs]
        regenerated = row is not None and row["read"] in ("device-only", "ignored") and \
            row["role"] in ("implant", "marker", "well")
        if not regenerated and not specs:
            continue
        parts = [c for b in blocks for c in contributions(b, temps, lam)]
        for ov in specs or [None]:
            out.append(generated_row(name, p, row, parts, ov, canon, contacts, aliases))
    return out


def generated_row(name, p, row, parts, ov, canon, contacts, aliases):
    ov = ov or {}
    names = ov.get("types", [])
    if names:
        # the statement that names the device type itself, else any whose
        # types include it
        want = set(expand_types(names, canon, contacts, aliases))
        chosen = [c for c in parts if set(c["from"]) & set(names)] or \
            [c for c in parts if want & set(expand_types(c["from"], canon, contacts, aliases))]
    else:
        chosen = [c for c in parts if c["nm"] > 0]
    dists = sorted({round(c["nm"], 3) for c in chosen})
    notes = []
    if len(dists) > 1 and names:
        # several pieces: the bloat-or that names the type is the grow from
        # it; the others (the shape itself, special areas) are noted
        named = [c for c in chosen if c["st"].toks[0] == "bloat-or" and set(c["from"]) & set(names)]
        if len({round(c["nm"], 3) for c in named}) == 1:
            notes.append("other pieces from the same types: %s um" % ", ".join(
                "%g" % (d / 1000.0) for d in dists if d != round(named[0]["nm"], 3)))
            chosen = named
            dists = [round(named[0]["nm"], 3)]
    entry = {"gds": list(p), "name": name.lower(), "cif": name,
             "role": row["role"] if row else ov.get("role", "marker"),
             "from": ov.get("from", ", ".join(sorted({t for c in chosen for t in c["from"]}))),
             "types": sorted({t for c in chosen for t in c["from"]}),
             "grow_um": None, "line": None, "file": None,
             "rule_ids": list(ov.get("rule_ids", [])),
             "enclosure_check": bool(ov.get("types")), "note": "", "source": "parser"}
    if len(dists) == 1:
        c = next(c for c in chosen if round(c["nm"], 3) == dists[0])
        entry["grow_um"] = um(dists[0])
        entry["line"], entry["file"] = c["st"].line, c["st"].file
        notes += [n for n in c["notes"] if not n.startswith("and")]
        notes += c["closing"]
    elif dists:
        notes.append("several distances from the device shape: %s um"
                     % ", ".join("%g" % (d / 1000.0) for d in dists))
    if "grow_um" in ov and (entry["grow_um"] is None or ov.get("force")):
        entry["grow_um"] = ov["grow_um"]
        entry["line"], entry["file"] = ov["line"], ov["file"]
        entry["source"] = "overrides"
    if ov.get("note"):
        notes.append(ov["note"])
    if entry["grow_um"] is None:
        notes.append("no single grow from a device shape (%d pieces)" % len(parts))
    entry["note"] = "; ".join(dict.fromkeys(notes))
    return entry


# -- ports ----------------------------------------------------------------------

def comment_types(canon, plane):
    """The names of the Magic types on the tech file's ``comment`` plane,
    which make no net: a label Magic puts on them names nothing in its
    netlist (sky130A's text.drawing, measured on sky130_fd_sc_hd__inv_1)."""
    on = {t for t, p in plane.items() if p == "comment"}
    return {n for n, t in canon.items() if t in on} | on


def build_ports(cifin, cifout, layers, lvs_labels, lvs_rel, comments=()):
    """The label convention: which GDS pairs make net names and ports in
    Magic (cifinput ``labels`` and ``calma`` lines), and which the PDK's
    KLayout LVS deck reads (``labels(L, D)``). A pair whose labels Magic
    puts only on types of the comment plane (``comments``; sky130A's
    text.drawing, read as ``comment``) names no net, so it is in
    ``comment`` and not in ``text``."""
    text, pin, port_text, comment = [], [], [], []
    lines = collections.defaultdict(list)
    types = {}
    for cif, pairs in cifin["calma"].items():
        u = cifin["use"].get(cif)
        if not u or cif in cifin["ignored"]:
            continue
        kinds = [k for k, _ in u["labels"]]
        first = collections.OrderedDict()
        for k, lst in u["labels"]:
            first.setdefault(k, lst)
        for p, st in pairs:
            if not kinds:
                continue
            types[key(p)] = {t for ts, _ in u["paint"] for t in ts}
            lines[key(p)].append(cite(st))
            lines[key(p)] += [cite(lst) for lst in first.values()]
            if "port" in kinds:
                if list(p) not in port_text:
                    port_text.append(list(p))
                if u["paint"] and list(p) not in pin:
                    pin.append(list(p))
            elif "text" in kinds or "label" in kinds:
                mine = types[key(p)]
                if mine and mine <= set(comments):
                    if list(p) not in comment:
                        comment.append(list(p))
                elif list(p) not in text:
                    text.append(list(p))
    kl = []
    for p, where in lvs_labels:
        if list(p) not in kl:
            kl.append(list(p))
        lines[key(p)].append(where)
    both = []
    for t in kl:
        if t in port_text:
            both.append({"text": t, "pin": None})
            continue
        if t in text:
            # the pin box of the same conductor: a pin pair Magic paints as
            # the same types, on the same GDS layer if there are several
            mine = types.get(key(t), set())
            pins = [q for q in pin if types.get(key(q), set()) & mine]
            pins.sort(key=lambda q: (q[0] != t[0], q))
            if pins:
                both.append({"text": t, "pin": pins[0]})
    out_ports = []
    for b in cifout["blocks"]:
        for st in b.labels:
            if st.toks[-1] == "port":
                for c in b.calma:
                    for p in calma_pairs(c, 1):
                        if list(p) not in out_ports:
                            out_ports.append(list(p))
    srt = lambda v: sorted(v)  # noqa: E731
    return {"text": srt(text), "pin": srt(pin), "port_text": srt(port_text), "comment": srt(comment),
            "klayout_lvs_text": srt(kl), "both": sorted(both, key=lambda b: b["text"]),
            "magic_writes_port": srt(out_ports), "klayout_lvs": lvs_rel,
            "lines": {k: ", ".join(dict.fromkeys(v)) for k, v in sorted(lines.items(),
                                                                           key=lambda kv: [int(x) for x in kv[0].split("/")])}}


# -- whole-shape rules ------------------------------------------------------------

def mark_whole_shape(rules, secs):
    """A cif rule tests a layer built in the drc cifoutput style. When that
    layer is built with ``bloat-all`` (it spans a whole connected shape, as
    sky130A's nwell_missing_tap does), checking part of a cell can't decide
    it (design-0.6.md 3.1, area checks)."""
    cs = None
    for name, variants, st, body in styles(secs.get("cifoutput", [])):
        if name == "drc":
            cs = parse_cif_blocks(in_variant(body, ""))[0]
    by = {b.name: b for b in cs or []}

    def spans(name, depth=0):
        b = by.get(name)
        if b is None or depth > 10:
            return False
        if any(op.toks[0] == "bloat-all" for op in b.ops):
            return True
        names = list(b.sources) + [t for op in b.ops if op.toks[0] in ("or", "and", "and-not")
                                   for t in split_list(" ".join(op.toks[1:2]))]
        return any(spans(n, depth + 1) for n in names if n in by)

    for r in rules:
        r["whole_shape"] = bool(r["keyword"].startswith("cif") and r["types"]
                                and any(spans(t) for t in r["types"]))


# -- the data file ----------------------------------------------------------------

def sha256_files(paths):
    """One digest over the tech file and the files it includes, in order."""
    h = hashlib.sha256()
    for path in paths:
        with open(path, "rb") as f:
            h.update(f.read())
    return h.hexdigest()


def pdk_version(pdk_dir):
    for f, pat in (("SOURCES", r"open_pdks\s+(\S+)"), ("COMMIT", r"(\S+)")):
        p = os.path.join(pdk_dir, f)
        if os.path.isfile(p):
            with open(p, encoding="utf-8", errors="replace") as fh:
                m = re.search(pat, fh.read())
                if m:
                    return m.group(1)
    return None


def load_overrides(path=OVERRIDES):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build(pdk, pdk_root, overrides=None):
    """The data file of one PDK, as a dict."""
    overrides = load_overrides() if overrides is None else overrides
    ov = overrides.get(pdk, {})
    pdk_dir = os.path.join(pdk_root, pdk)
    tech_rel = os.path.join("libs.tech", "magic", pdk + ".tech")
    tech = os.path.join(pdk_dir, tech_rel)
    files = []
    lines = read_lines(tech, files)
    stmts = statements(lines)
    secs = sections(stmts)
    canon, plane, contacts, aliases = parse_types(secs)
    cifout = parse_cifout(secs["cifoutput"])
    lam = cifout["scale"]
    cifin = parse_cifin(secs["cifinput"])
    style_names, rules = parse_drc(secs["drc"], lam)
    mark_whole_shape(rules, secs)
    version = next((st.toks[1] for st in secs.get("version", []) if st.toks[0] == "version"), None)
    grids = {cifout["gridlimit"], cifin["gridlimit"]}
    if len(grids) != 1 or None in grids:
        raise ValueError("%s: the gdsii output and default input styles give different grids %s"
                         % (pdk, sorted(grids, key=str)))
    pf = PDK_FILES.get(pdk, {})
    lyp = parse_lyp(os.path.join(pdk_dir, pf["lyp"])) if pf.get("lyp") else {}
    layers = build_layers(cifin, lyp, canon, plane, contacts, ov)
    lvs_rel = pf.get("klayout_lvs") if pf.get("klayout_lvs") and \
        os.path.isfile(os.path.join(pdk_dir, pf["klayout_lvs"])) else None
    labels = lvs_label_calls(pdk_dir, lvs_rel)
    counts = collections.OrderedDict()
    for s in style_names:
        counts[s] = sum(1 for r in rules if s in r["styles"])
    netgen = os.path.join("libs.tech", "netgen", pdk + "_setup.tcl")
    data = collections.OrderedDict([
        ("schema", SCHEMA),
        ("pdk", pdk),
        ("source", {"tech": os.path.join(pdk, tech_rel),
                    "tech_files": [os.path.basename(f) for f in files],
                    "tech_sha256": sha256_files(files),
                    "magic_tech_version": version,
                    "open_pdks": pdk_version(pdk_dir),
                    "lyp": pf.get("lyp"),
                    "cifoutput_style": cifout["style"].toks[1],
                    "cifinput_style": cifin["name"],
                    "lambda_nm": lam}),
        ("grid_um", um(cifout["gridlimit"])),
        ("drc", {"styles": style_names,
                 "magic_default_style": style_names[0] if style_names else None,
                 "counts": {"rules": len(rules), "with_why": sum(1 for r in rules if r["why"]),
                            "per_style": counts},
                 "rules": rules}),
        ("layers", layers),
        ("cifout", build_cifout(cifout, canon, contacts, aliases)),
        ("generated", build_generated(cifout, layers, canon, contacts, aliases, ov)),
        ("ports", build_ports(cifin, cifout, layers, labels, lvs_rel, comment_types(canon, plane))),
        ("lvs", {"netgen_setup": netgen if os.path.isfile(os.path.join(pdk_dir, netgen)) else None,
                 "klayout_lvs": lvs_rel}),
        ("error_marker", list(ERROR_MARKER)),
    ])
    return data


def dumps(data):
    return json.dumps(data, indent=1, ensure_ascii=False) + "\n"


def compare(a, b, path=""):
    """List the paths where two JSON values differ (built against shipped)."""
    out = []
    if type(a) is not type(b):
        return ["%s: %r != %r" % (path or "/", a, b)]
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append("%s/%s: only in %s" % (path, k, "built" if k in a else "shipped"))
            else:
                out += compare(a[k], b[k], "%s/%s" % (path, k))
    elif isinstance(a, list):
        if len(a) != len(b):
            out.append("%s: %d items != %d" % (path, len(a), len(b)))
        for i, (x, y) in enumerate(zip(a, b)):
            name = i
            if isinstance(x, dict):
                name = x.get("line", x.get("name", i)) if "line" in x or "name" in x else i
            out += compare(x, y, "%s[%s]" % (path, name))
    elif a != b:
        out.append("%s: %r != %r" % (path, a, b))
    return out


# -- the harness's KLayout DRC profiles against the installed decks (design-0.6.md 4) --

def load_profiles(path=DRC_PY):
    """PROFILES from tests/parity/drc.py, read from its source (the module
    stays where it is and is not imported). Also the options the harness
    gives the IHP runner on its command line."""
    with open(path, encoding="utf-8") as f:
        src = f.read()
    import ast
    tree = ast.parse(src)
    profiles = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "PROFILES"
                                                for t in node.targets):
            profiles = ast.literal_eval(node.value)
    runner_opts = sorted(set(re.findall(r'"(--[a-z_]+)', src)))
    return profiles or {}, runner_opts


def check_profiles(pdk, pdk_root, profiles, runner_opts):
    """Differences between the harness's KLayout DRC profile of a PDK and
    the installed deck: a deck or runner that isn't there, a switch the
    profile sets that the deck doesn't read, a top-cell variable it doesn't
    read, or a runner option the runner doesn't take."""
    p = profiles.get(pdk)
    if p is None:
        return ["PROFILES has no entry for %s" % pdk]
    out = []
    rel = p.get("deck") or p.get("runner")
    path = os.path.join(pdk_root, pdk, rel or "")
    if not rel or not os.path.isfile(path):
        return ["%s: PROFILES names %s, which is not installed" % (pdk, rel)]
    with open(path, encoding="utf-8", errors="replace") as f:
        src = f.read()
    if p.get("kind") == "deck":
        names = set(re.findall(r"\$([A-Za-z_]\w*)", src))
        for flag in sorted(p.get("flags", {})):
            if flag not in names:
                out.append("%s: %s does not read the switch $%s that PROFILES sets"
                           % (pdk, rel, flag))
        if p.get("top") and p["top"] not in names:
            out.append("%s: %s does not read $%s (PROFILES top)" % (pdk, rel, p["top"]))
    else:
        for opt in runner_opts:
            if opt not in src:
                out.append("%s: %s takes no option %s, which the harness passes" % (pdk, rel, opt))
    return out


# -- command line ------------------------------------------------------------------

def summary(data):
    c = data["drc"]["counts"]
    per = ", ".join("%s %d" % kv for kv in c["per_style"].items())
    gen = sum(1 for g in data["generated"] if g["grow_um"] is not None)
    return ("%d rule statements (%s), %d layers, %d Magic types in cifout, %d generated layers "
            "(%d with a distance), grid %g um" % (
                c["rules"], per, len(data["layers"]), len(data["cifout"]),
                len(data["generated"]), gen, data["grid_um"]))


def build_one(pdk, pdk_root, out, check, profiles):
    try:
        data = build(pdk, pdk_root)
    except (OSError, ValueError, KeyError) as e:
        sys.stderr.write("error: %s: %s\n" % (pdk, e))
        return 2
    if check:
        rc = 0
        try:
            with open(out, encoding="utf-8") as f:
                shipped = json.load(f)
        except (OSError, ValueError) as e:
            sys.stderr.write("error: cannot read %s: %s\n" % (out, e))
            return 2
        diffs = compare(json.loads(dumps(data)), shipped)
        if diffs:
            print("PDK DATA DIFFERS from %s (%d differences):" % (out, len(diffs)))
            for line in diffs[:200]:
                print("  " + line)
            rc = 1
        else:
            print("PDK DATA OK: %s matches %s (%s)" % (out, os.path.join(pdk_root, pdk), summary(data)))
        probs = check_profiles(pdk, pdk_root, *profiles)
        if probs:
            print("KLAYOUT DRC PROFILE DIFFERS for %s (tests/parity/drc.py PROFILES):" % pdk)
            for line in probs:
                print("  " + line)
            rc = 1
        else:
            print("KLAYOUT DRC PROFILE OK: %s" % pdk)
        return rc
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(dumps(data))
    print("wrote %s: %s" % (out, summary(data)))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pdk", help="the PDK (default: KMP_PDK, else sky130A)")
    ap.add_argument("--all", action="store_true", help="every supported PDK")
    ap.add_argument("--out", help="default: the shipped data file of the PDK")
    ap.add_argument("--check", action="store_true",
                    help="build in memory and compare with --out; compare PROFILES with the decks")
    ap.add_argument("--pdk-root", default=os.environ.get("PDK_ROOT") or "/foss/pdks",
                    help="default: PDK_ROOT, else /foss/pdks")
    args = ap.parse_args(argv)
    pdks = list(SUPPORTED_PDKS) if args.all else [args.pdk or os.environ.get("KMP_PDK") or "sky130A"]
    if args.all and args.out:
        ap.error("--out needs a single --pdk")
    for p in pdks:
        if p not in SUPPORTED_PDKS:
            ap.error("unsupported PDK %s (supported: %s)" % (p, ", ".join(SUPPORTED_PDKS)))
    profiles = load_profiles() if args.check else None
    rc = 0
    for pdk in pdks:
        rc = max(rc, build_one(pdk, args.pdk_root, args.out or shipped_data(pdk), args.check, profiles))
    return rc


if __name__ == "__main__":
    sys.exit(main())
