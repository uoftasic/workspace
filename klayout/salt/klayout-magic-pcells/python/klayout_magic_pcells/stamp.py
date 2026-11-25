"""Version stamps.

Format: ``kmp1;magic=8.3.681;tech=1.0.588-56-g026824c;pdk=sky130A;digest=<12 hex>;key=<16 hex>;grid=<nm>``.
``digest`` covers what decides Magic's geometry beyond the three version
strings: the PDK's commit, the text of every loaded proc in the PDK's
generator namespace and in ::magic, the tech file, every file in the PDK's
libs.tech/magic directory, and the vendor GDS files that fixed devices copy.
A locally edited sky130A.tcl or sky130_fd_pr.gds therefore gives a
different stamp. The ``key`` and ``grid`` fields appear only in the
generated-by stamp, which is stored as a GDS property with integer attribute
100 on one shape of the variant: ``key`` is the start of the cache key, and
``grid`` the coarsest grid in nm that every coordinate of this variant's
Magic output lies on (audit compares it with a file's dbu; stamps written
before version 0.4 have no grid). The created-with stamp (no key) is the hidden PCell parameter
``kmp_created``. Stamps written before ``digest`` existed lack it; they are
compared on magic, tech and pdk alone.
"""

import hashlib
import json

STAMP_ATTR = 100
STAMP_PREFIX = "kmp1"
DIGEST_FIELDS = ("pdk", "magic", "open_pdks", "tech", "code", "techfile", "pdk_commit", "techdir",
                 "vendor")


def versions_digest(versions):
    """12 hex digits over DIGEST_FIELDS of a Versions object."""
    fields = {k: str(getattr(versions, k, "") or "") for k in DIGEST_FIELDS}
    text = json.dumps(fields, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def make_stamp(versions, key=None):
    parts = [STAMP_PREFIX, "magic=%s" % versions.magic, "tech=%s" % versions.tech,
             "pdk=%s" % versions.pdk, "digest=%s" % versions_digest(versions)]
    if key:
        parts.append("key=%s" % key[:16])
    return ";".join(parts)


def parse_stamp(text):
    if not isinstance(text, str) or not text.startswith(STAMP_PREFIX + ";"):
        return None
    out = {"format": STAMP_PREFIX}
    for part in text.split(";")[1:]:
        k, _, v = part.partition("=")
        out[k] = v
    return out


def same_versions(a, b):
    """True when two stamps (dicts) name the same Magic, tech and PDK, and,
    when both carry one, the same digest."""
    if not all(a.get(k) == b.get(k) for k in ("magic", "tech", "pdk")):
        return False
    if a.get("digest") and b.get("digest"):
        return a["digest"] == b["digest"]
    return True


def describe(st):
    """'magic=... tech=... pdk=... digest=...' for messages."""
    return " ".join("%s=%s" % (k, st.get(k)) for k in ("magic", "tech", "pdk", "digest") if st.get(k))


def _stamp_target(layout, cell):
    """The 235/4 box if there is one (sky130's prBoundary), else the shape on
    the lowest (layer, datatype) whose bounding box has the smallest (left,
    bottom). On gf180mcuD that is the 0/0 boundary when the device has one."""
    from ._kl import db
    infos = []
    for li in layout.layer_indices():
        info = layout.get_info(li)
        if not cell.shapes(li).is_empty():
            infos.append(((info.layer, info.datatype), li))
    infos.sort()
    for (ld, li) in infos:
        if ld == (235, 4):
            for sh in cell.shapes(li).each():
                return sh
    for (ld, li) in infos:
        best = None
        for sh in cell.shapes(li).each():
            b = sh.bbox()
            k = (b.left, b.bottom, b.right, b.top)
            if best is None or k < best[0]:
                best = (k, sh)
        if best is not None:
            return best[1]
    return None


def apply_stamp(layout, cell, stamp):
    sh = _stamp_target(layout, cell)
    if sh is None:
        return False
    sh.set_property(STAMP_ATTR, stamp)
    return True


def read_stamp(cell):
    """Parse the first stamp property found on the cell's own shapes."""
    layout = cell.layout()
    for li in layout.layer_indices():
        for sh in cell.shapes(li).each():
            if sh.prop_id:
                v = sh.property(STAMP_ATTR)
                p = parse_stamp(v) if v is not None else None
                if p is not None:
                    return p
    return None
