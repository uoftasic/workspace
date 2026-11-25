#!/usr/bin/env python3
"""Write the parity sweep: a list of parameter points per device.

    python3 tests/parity/gen_sweep.py --manifest M --out sweep.json \
        [--seed 1121] [--random 5] [--max-per-device 64] [--quick] [--devices GLOB ...]

Each point holds only the parameters it changes, twice: ``request``, the
strings Magic gets on path A, and ``value``, the typed values path B passes
to ``Layout.create_cell``. Neither goes through the plugin's code:
``magic_text.py`` restates the formatting contract from the README (12
significant digits, Magic's default text, coverage strings as typed), so a
bug in the plugin's own formatter makes path B send a different text and
fails the ``request`` check. Points whose request repeats an earlier one of
the same device are dropped, and the kinds they stood for are kept in
``aliases``.

Box-paint generators (vias, contacts, substrate contacts, guard rings and
wells) get box sizes around the minimum the manifest records: the minimum,
a step of 5 nm below it on each side (Magic paints nothing), squares, wide
and tall boxes, an off-grid width that Magic rounds, a 20 x 20 um box,
negative sizes (Magic's box command puts the box left of or below the
origin and paints it), a negative zero, and seeded random sizes. Their
points carry both w and h, because path A has no defaults to merge for them.

Every generator also gets values with more digits than the sweep's other
points (which ``fmt`` rounds to 6 decimals): every float at 12 and at 15
significant digits, every float at a 12-digit rounding tie (13 digits ending
in 5), and every float one ULP from such a tie. They fail the ``request``
check of a formatter that keeps fewer than 12 digits, and the round trips
(which always include them) fail when a reopened file sends a different
text.

Each device also gets edit points, which test the "Edit device" dialog that
Magic opens on an instance after Create: the default device created and then
edited to the values of one of its other points (up to EDITS_PER_DEVICE of
them, random, zero, min, max and below points first), and each random point
created and then edited to the next random point's values. An edit point's
``first`` holds the New device values (request and value, as above); its
``request`` and ``value`` are what is then typed into the Edit device dialog.
The many-digit points are left out: an edit types only the fields whose
value changes, which path D (Magic's dialog) tells by Magic's number for
the field and the PCell by its 12-digit text.

No point may give a MOSFET or varactor both w and l above 28 um: Magic's
mos_check then loops forever (sky130A.tcl and the IHP fet code, the
tap-spacing loop), on path A as in Magic's own dialog. The backend stops
that loop (see kmp_common.tcl) and tests/backend covers it; path A has a
watchdog in case one slips in.
"""

import argparse
import fnmatch
import json
import math
import os
import random
import sys
from decimal import ROUND_DOWN, Context, Decimal

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "python"))
sys.path.insert(0, HERE)

from klayout_magic_pcells.manifest import Manifest  # noqa: E402
import magic_text  # noqa: E402

GRID = 0.005
OFFGRID = 0.0034
# Kinds dropped first when a device has more points than --max-per-device.
DROP_ORDER = ("random", "anchor", "space", "choice", "numlist", "offgrid", "int", "below", "flip",
              "min", "max")
# Edit points: the kinds whose values the default device is edited to, in
# the order they are taken, and how many per device.
EDIT_KINDS = ("random", "zero", "min", "max", "below", "flip", "int", "choice", "anchor", "numlist")
EDITS_PER_DEVICE = 12
RANDOM_CHAINS = 4


def edit_points(spec, dev_pts):
    """(kind, first point, second point) for the device's edit points."""
    if spec.kind == "box":
        return []
    by_kind = {}
    for pt in dev_pts:
        if pt["request"]:
            by_kind.setdefault(pt["kind"].split(":")[0], []).append(pt)
    out = []
    for fam in EDIT_KINDS:
        for pt in by_kind.get(fam, []):
            if len(out) < EDITS_PER_DEVICE:
                out.append(("edit:" + pt["kind"], None, pt))
    rnd = {pt["kind"]: pt for pt in by_kind.get("random", [])}
    for k in range(1, RANDOM_CHAINS + 1):
        a, b = rnd.get("random:%d" % k), rnd.get("random:%d" % (k + 1))
        if a and b:
            out.append(("edit:random:%d>%d" % (k, k + 1), a, b))
    return out


def num(text):
    try:
        v = float(text)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def limits(spec, p, cfg):
    """(min, max, min_from_magic) for a numeric parameter, or Nones."""
    lo = hi = None
    lo_magic = False
    if p.type == "float":
        v = num(spec.internal(p.name + "min"))
        if v is not None:
            lo, lo_magic = v, True
        v = num(spec.internal(p.name + "max"))
        if v is not None:
            hi = v
        if lo is None and num(p.check_min) is not None:
            lo, lo_magic = num(p.check_min), True
        if hi is None and num(p.check_max) is not None:
            hi = num(p.check_max)
    key = "signed" if p.type == "signed" else p.name
    fam = cfg.get("by_family", {}).get(spec.family, {}).get(key, {})
    gen = cfg.get("by_name", {}).get(key, {})
    if lo is None:
        lo = fam.get("min", gen.get("min"))
    if hi is None:
        hi = fam.get("max", gen.get("max"))
        d = num(p.default)
        if hi is not None and d is not None and hi < d:
            # A sweep cap below the default (an IHP inductor's diameter is
            # far above the 20 um cap) would only make a smaller device.
            hi = None
    return lo, hi, lo_magic


def snap(v):
    return round(round(v / GRID) * GRID, 6)


def fmt(v):
    """A float as short text: 0.42 not 0.42000000000000004."""
    return repr(round(v, 6))


# Relative steps that give values with many significant digits near a
# parameter's default (or near 1 when the default is 0).
DIGIT_STEP = Decimal("0.000123456789012345678")


def digits_text(v, n):
    """The decimal text of ``v`` moved off its value by DIGIT_STEP and cut
    to ``n`` significant digits (the last one nonzero)."""
    base = Decimal(repr(float(v))) if v else Decimal(1)
    x = Context(prec=n, rounding=ROUND_DOWN).plus(base * (1 + DIGIT_STEP))
    t = format(x, "f")
    if t.rstrip("0").endswith("."):
        t = t.rstrip("0") + "0"
    return t


def tie_text(v):
    """A 13-digit decimal ending in 5 near ``v``: a tie when rounded to 12
    significant digits."""
    x = Context(prec=12, rounding=ROUND_DOWN).plus(Decimal(digits_text(v, 12)))
    return format(x + Decimal(5).scaleb(x.adjusted() - 12), "f")


def ulp_text(v, k):
    """repr of the double one ULP above (k odd) or below (k even) the tie."""
    t = float(tie_text(v))
    return repr(math.nextafter(t, math.inf if k % 2 else -math.inf))


def digit_points(floats, base, k=0):
    """(kind, {name: text}) for the many-digit points, every float at once.
    ``base`` gives the value each float starts from."""
    if not floats:
        return []
    return [("digits:12", {n: digits_text(base(n), 12) for n in floats}),
            ("digits:15", {n: digits_text(base(n), 15) for n in floats}),
            ("tie", {n: tie_text(base(n)) for n in floats}),
            ("tie:ulp", {n: ulp_text(base(n), i + k) for i, n in enumerate(floats)})]


def box_points(spec, rng, n_random, quick):
    """Box sizes for a box-paint generator, as (kind, {w, h}) in um."""
    m = num(spec.raw.get("min_box_um"))
    d = {"w": spec.param("w").default, "h": spec.param("h").default}
    pts = [("default", dict(d))]
    if quick or m is None:
        return pts
    big = max(2 * m, 1.0)
    side = max(m, 0.5)
    pts += [
        ("min:w", {"w": fmt(m), "h": fmt(big)}),
        ("min:h", {"w": fmt(big), "h": fmt(m)}),
        ("below:w", {"w": fmt(m - GRID), "h": fmt(m)}),
        ("below:h", {"w": fmt(m), "h": fmt(m - GRID)}),
        ("square", {"w": fmt(big), "h": fmt(big)}),
        ("wide", {"w": fmt(snap(4 * side)), "h": fmt(side)}),
        ("tall", {"w": fmt(side), "h": fmt(snap(4 * side))}),
        ("offgrid:w", {"w": fmt(m + OFFGRID), "h": fmt(m)}),
        ("large", {"w": "20.0", "h": "20.0"}),
        # Magic's "box values 0um 0um -1um 1um" normalises the box to
        # x = -1 .. 0 and the generator paints it there.
        ("neg:w", {"w": fmt(-big), "h": fmt(big)}),
        ("neg:h", {"w": fmt(big), "h": fmt(-big)}),
        ("neg:wh", {"w": fmt(-big), "h": fmt(-big)}),
        ("negzero:w", {"w": "-0.0", "h": fmt(big)}),
    ]
    pts += digit_points(["w", "h"], lambda n: big)
    for k in range(n_random):
        pts.append(("random:%d" % (k + 1), {"w": fmt(snap(rng.uniform(m, 10))),
                                            "h": fmt(snap(rng.uniform(m, 10)))}))
    return pts


def device_points(spec, cfg, rng, n_random, quick):
    if spec.kind == "box":
        return box_points(spec, rng, n_random, quick)
    pts = [("default", {})]
    if quick:
        return pts
    for p in spec.params:
        if p.type == "float":
            lo, hi, lo_magic = limits(spec, p, cfg)
            if lo is not None:
                pts.append(("min:" + p.name, {p.name: fmt(lo)}))
                if lo_magic:
                    below = lo / 2 if lo > 0 else lo - 1
                    pts.append(("below:" + p.name, {p.name: fmt(below)}))
            if hi is not None:
                pts.append(("max:" + p.name, {p.name: fmt(hi)}))
        elif p.type == "signed":
            pts.append(("min:" + p.name, {p.name: "0"}))
            pts.append(("max:" + p.name, {p.name: "100"}))
            pts.append(("anchor:+" + p.name, {p.name: "+50"}))
            pts.append(("anchor:-" + p.name, {p.name: "-50"}))
        elif p.type == "bool01":
            pts.append(("flip:" + p.name, {p.name: "0" if p.default_value() else "1"}))
        elif p.type == "int":
            pts.append(("int:%s=1" % p.name, {p.name: "1"}))
            pts.append(("int:%s=4" % p.name, {p.name: "4"}))
            pts.append(("below:" + p.name, {p.name: "0"}))
        elif p.type == "choice":
            for c in p.choices:
                if c != p.default:
                    pts.append(("choice:%s=%s" % (p.name, c), {p.name: c}))
        elif p.type == "numlist":
            pts.append(("numlist:%s=2" % p.name, {p.name: "2"}))
            pts.append(("numlist:%s=1 2" % p.name, {p.name: "1 2"}))
    signed = [p for p in spec.params if p.type == "signed"]
    if signed:
        # Whitespace before the anchor: Magic reads the first character, so
        # " -50" has no anchor and must reach Magic unchanged.
        pts.append(("space:" + signed[0].name, {signed[0].name: " -50"}))
        pts.append(("space:" + signed[-1].name, {signed[-1].name: "\t+30"}))
    for n in ("w", "l"):
        p = spec.param(n)
        if p is not None and p.type == "float":
            pts.append(("offgrid:" + n, {n: fmt(float(p.default) + OFFGRID)}))
    # Zero sizes: for 17 resistors (l), 6 resistors (w) and 5 diodes (w, l)
    # Magic's _draw fails and Magic writes an empty cell; the others clamp.
    if spec.family in ("res", "diode"):
        for n in ("l", "w"):
            if spec.param(n) is not None:
                pts.append(("zero:" + n, {n: "0"}))
    floats = [p.name for p in spec.params if p.type == "float"]
    pts += digit_points(floats, lambda n: num(spec.param(n).default) or 0.0)
    large = cfg.get("large_nf", {}).get(spec.name)
    fingers = "nf" if spec.param("nf") is not None else "ng" if spec.param("ng") is not None else None
    if large and fingers:
        pts.append(("large", {"w": "31", fingers: str(large)}))
    for k in range(n_random):
        req = {}
        for p in spec.params:
            if p.type == "float":
                lo, hi, _ = limits(spec, p, cfg)
                if lo is None or hi is None or hi <= lo:
                    continue
                req[p.name] = fmt(snap(rng.uniform(lo, hi)))
            elif p.type == "int":
                req[p.name] = str(rng.randint(1, 4))
            elif p.type == "bool01":
                req[p.name] = str(rng.randint(0, 1))
            elif p.type == "signed":
                req[p.name] = rng.choice(("", "+", "-")) + str(rng.randint(0, 100))
            elif p.type == "choice" and p.choices:
                req[p.name] = rng.choice(p.choices)
        pts.append(("random:%d" % (k + 1), req))
    return pts


def canonical(spec, req):
    """(text for Magic, typed value for the PCell), both without plugin code."""
    out, vals = {}, {}
    for k, v in req.items():
        p = spec.param(k)
        vals[k] = magic_text.typed(p.type, v)
        out[k] = magic_text.text(p.type, vals[k], p.default if p.type == "float" else None)
    return out, vals


def gen(manifest, cfg, seed, n_random, max_per_device, quick, patterns):
    points = []
    summary = {}
    for di, spec in enumerate(manifest.devices):
        if patterns and not any(fnmatch.fnmatchcase(spec.name, g) for g in patterns):
            continue
        rng = random.Random("%d:%s" % (seed, spec.name))
        seen = {}
        dev_pts = []
        for kind, req in device_points(spec, cfg, rng, n_random, quick):
            creq, cval = canonical(spec, req)
            if spec.kind != "box":
                # A request that only restates defaults is the default point.
                # (A box-paint point keeps both sides: path A has no
                # defaults to merge for it.)
                creq = {k: v for k, v in creq.items() if v != spec.param(k).default}
                cval = {k: v for k, v in cval.items() if k in creq}
            # The many-digit points are about the typed value as much as the
            # text: a tie whose text equals another point's is still its own
            # point (its round trip is what can fail).
            many = kind.split(":")[0] in ("digits", "tie")
            sig = json.dumps([creq, cval if many else None], sort_keys=True)
            if sig in seen:
                seen[sig]["aliases"].append(kind)
                continue
            pt = {"device": spec.name, "family": spec.family, "form": spec.form, "kind": kind,
                  "request": creq, "value": cval, "aliases": []}
            seen[sig] = pt
            dev_pts.append(pt)
        dropped = 0
        for fam in DROP_ORDER:
            while len(dev_pts) > max_per_device:
                idx = [i for i, pt in enumerate(dev_pts) if pt["kind"].split(":")[0] == fam]
                if not idx:
                    break
                dev_pts.pop(idx[-1])
                dropped += 1
        edits = [] if quick else edit_points(spec, dev_pts)
        for kind, first, second in edits:
            dev_pts.append({"device": spec.name, "family": spec.family, "form": spec.form, "kind": kind,
                            "edit": True,
                            "first": {"request": dict(first["request"]) if first else {},
                                      "value": dict(first["value"]) if first else {}},
                            "request": dict(second["request"]), "value": dict(second["value"]),
                            # Path D compares a number field with Magic's
                            # number for it, any other field as text.
                            "types": {k: spec.param(k).type for k in second["request"]},
                            "aliases": []})
        summary[spec.name] = {"points": len(dev_pts), "dropped": dropped, "edit_points": len(edits)}
        points.extend(dev_pts)
    for i, pt in enumerate(points):
        pt["id"] = "%04d" % (i + 1)
    return points, summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--limits", default=os.path.join(HERE, "sweep_limits.json"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=1121)
    ap.add_argument("--random", type=int, default=5)
    ap.add_argument("--max-per-device", type=int, default=64)
    ap.add_argument("--quick", action="store_true", help="only the default point of each device")
    ap.add_argument("--devices", nargs="*", default=[], help="fnmatch patterns of device names")
    args = ap.parse_args(argv)
    manifest = Manifest.load(args.manifest)
    with open(args.limits, encoding="utf-8") as f:
        cfg = json.load(f)
    points, summary = gen(manifest, cfg, args.seed, args.random, args.max_per_device,
                          args.quick, args.devices)
    doc = {"seed": args.seed, "random": args.random, "max_per_device": args.max_per_device,
           "quick": args.quick, "devices": args.devices, "summary": summary, "points": points}
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1)
        f.write("\n")
    print("sweep: %d points over %d devices -> %s" % (len(points), len(summary), args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
