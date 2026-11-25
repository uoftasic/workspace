#!/usr/bin/env python3
"""Build the per-PDK gap table: where Magic's DRC and the PDK's KLayout
decks disagree (docs/design-0.6.md 3.5 and 6.6).

    python3 tools/build_gaps.py --pdk sky130A               rebuild and write the files
    python3 tools/build_gaps.py --pdk sky130A --check       rebuild and compare, write nothing
    python3 tools/build_gaps.py --all --update-baseline     the explicit form of a write

Run it in the pinned image (scripts/gaps.sh does). For each PDK it

1. takes Magic's rules from pkg/data/pdk-<pdk>.json;
2. runs each KLayout deck once on a one-box layout, with the harness's
   switches (tests/parity/drc.py PROFILES; on sky130A also the menu's
   switches and sky130A.lydrc with FEOL off and on). The report's
   categories are the rule list; a text scan of the deck gives each name's
   output line and the switches around it;
3. joins the two on rule ID, with tests/gaps/aliases-<pdk>.json for the
   mappings made by hand;
4. adds what both engines reported on the case suite's gaps set (Magic per
   cell in all three styles, KLayout on one sheet);
5. gives each rule a status and writes docs/gaps/<pdk>.md and .json,
   docs/gaps/README.md and pkg/data/gaps-<pdk>.json.

Only names, values, switches and line numbers of the KLayout decks reach the
outputs, never deck text. ``--check`` fails (exit 1) when a rebuilt file
differs from the committed one. ``--raw FILE`` builds from saved run results
(``out/gaps/<pdk>/raw.json``, written by every run) without the image.
"""

import argparse
import collections
import difflib
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PKG_DATA = os.path.join(REPO, "python", "klayout_magic_pcells", "data")
DOCS = os.path.join(REPO, "docs", "gaps")
ALIASES = os.path.join(REPO, "tests", "gaps")
PDKS = ("sky130A", "gf180mcuD", "ihp-sg13g2", "ihp-sg13cmos5l")
SCHEMA = 1
# pkg/data/gaps-<pdk>.json: 2 keys its entries by row, with the statements' lines.
PKG_SCHEMA = 2

STATUSES = ("both", "both, values differ", "folded", "measured on other shapes",
            "same name for another check", "in the deck, did not fire on its case",
            "Magic only", "KLayout only")
STYLE_LETTER = {"drc(fast)": "F", "drc(full)": "U", "drc(routing)": "R"}


# ---------------------------------------------------------------------------
# Values


_VAL_UNIT = re.compile(r"(-?\d+(?:\.\d+)?)\s*(µm²|um²|µm\^2|um\^2|µm2|um2|µm|um)(?![A-Za-z0-9])")
_VAL_CMP = re.compile(r"(?:>=|<=|=|<|>|:)\s*(-?\d+(?:\.\d+)?)(?![\d.])")


def value_of(text):
    """[value, unit] from a rule description or why-text: the last number
    with a unit ("um" or "um2"), else the last number after a comparison,
    '=' or ':'; None when there is none."""
    if not text:
        return None
    hits = _VAL_UNIT.findall(text)
    if hits:
        v, u = hits[-1]
        return [float(v), "um2" if ("2" in u or "²" in u) else "um"]
    hits = _VAL_CMP.findall(text)
    if hits:
        return [float(hits[-1]), None]
    return None


def _kind(unit):
    return "area" if unit and ("2" in unit or "^" in unit) else "length"


def fmt_value(v, unit):
    if v is None:
        return "–"
    s = ("%.6f" % v).rstrip("0").rstrip(".")
    return s + (" µm²" if _kind(unit) == "area" and unit else "")


# ---------------------------------------------------------------------------
# Text scan of a KLayout deck: output lines and switches


_OPENERS = re.compile(r"^(while|until|def|class|module|begin|case|for)\b")
_COND = re.compile(r"^(if|unless|elsif)\s+(.*?)(\s+then)?\s*$")
_DO = re.compile(r"(\bdo\s*(\|[^|]*\|)?|->\s*do)\s*$")
_ASSIGN_OPEN = re.compile(r"=\s*(if|unless|case|begin)\b")
_REGISTER = re.compile(r"\bGF180_DRC_REGISTRY\.register\(")
_TAGS = re.compile(r"tags:\s*%w\[([^\]]*)\]")


def _code(line):
    """The line without its comment (a '#' outside quotes that does not
    start '#{')."""
    out, q, i = [], None, 0
    while i < len(line):
        ch = line[i]
        if q:
            if ch == "\\":
                out.append(line[i:i + 2])
                i += 2
                continue
            if ch == q:
                q = None
        elif ch in "\"'":
            q = ch
        elif ch == "#" and not line.startswith("{", i + 1):
            break
        out.append(ch)
        i += 1
    return "".join(out).strip()


def _switch_label(kw, cond):
    cond = re.sub(r"\s+", " ", cond).strip()
    cond = cond.replace("$", "")
    if len(cond) > 60:
        cond = cond[:57] + "..."
    return ("not " + cond) if kw == "unless" else cond


def _first_string(text):
    m = re.match(r"""\s*(["'])((?:\\.|(?!\1).)*)\1""", text)
    return m.group(2) if m else None


def scan_deck(text, label):
    """Every output(...) of a deck file: [{"name", "file", "line", "switch",
    "tags"}]. ``name`` is the first string argument as written; a name
    built with #{...} is a template. Commented lines are skipped."""
    lines = text.split("\n")
    stack = []          # labels; None for blocks that are not switches
    tags = []
    out = []
    in_doc = False
    for n, raw in enumerate(lines, 1):
        s = raw.strip()
        if s.startswith("=begin"):
            in_doc = True
        if in_doc:
            if s.startswith("=end"):
                in_doc = False
            continue
        if s.startswith("#"):
            continue
        code = _code(raw)
        if not code:
            continue
        if _REGISTER.search(code):
            blk = "\n".join(lines[n - 1:n + 8])
            tm = _TAGS.search(blk)
            tags = [t for t in (tm.group(1).split() if tm else []) if t != "all"]
        # outputs on this line (before block changes: "x.output(...) if c" is not a block)
        for m in re.finditer(r"(?:^|[.\s(])output\(", code):
            if re.match(r"^\s*def\s+output", code):
                break
            rest = code[m.end():]
            name = _first_string(rest)
            if name is None and not rest.strip():
                for k in range(n, min(n + 3, len(lines))):
                    nxt = _code(lines[k])
                    if nxt:
                        name = _first_string(nxt)
                        break
            if name:
                out.append({"name": name, "file": label, "line": n,
                            "switch": " & ".join(x for x in stack if x), "tags": list(tags)})
        # blocks
        if re.match(r"^end\b", code):
            if stack:
                stack.pop()
            if _DO.search(code):
                stack.append(None)
            continue
        m = _COND.match(code)
        if m and m.group(1) in ("if", "unless") and not re.search(r"\bend\s*$", code):
            stack.append(_switch_label(m.group(1), m.group(2)))
            continue
        if m and m.group(1) == "elsif":
            if stack:
                stack[-1] = _switch_label("if", m.group(2))
            continue
        if re.match(r"^else\b", code):
            if stack and stack[-1]:
                stack[-1] = "not (%s)" % stack[-1]
            continue
        if _OPENERS.match(code) and not re.search(r"\bend\s*$", code):
            stack.append(None)
            continue
        if _ASSIGN_OPEN.search(code) and not re.search(r"\bend\s*$", code):
            stack.append(None)
            continue
        if _DO.search(code):
            stack.append(None)
    return out


def _template_re(name):
    parts = re.split(r"#\{[^}]*\}", name)
    if len(parts) == 1:
        return None
    return re.compile("^" + "(.+?)".join(re.escape(p) for p in parts) + "$")


def locate(names, outputs):
    """{category name: [{"file", "line", "switch", "tags"}]}: the outputs
    whose literal name is the category, else the templates that build it
    (the most specific one). A name the scan can't place is missing."""
    literal = collections.defaultdict(list)
    templates = []
    for o in outputs:
        rx = _template_re(o["name"])
        if rx is None:
            literal[o["name"]].append(o)
        else:
            templates.append((len(re.sub(r"#\{[^}]*\}", "", o["name"])), rx, o))
    templates.sort(key=lambda t: -t[0])
    found = {}
    for nm in names:
        hits = literal.get(nm)
        if not hits:
            best = None
            hits = []
            for score, rx, o in templates:
                if rx.match(nm):
                    if best is None:
                        best = score
                    if score == best:
                        hits.append(o)
        if hits:
            found[nm] = [{k: o[k] for k in ("file", "line", "switch", "tags")} for o in hits]
    return found


# ---------------------------------------------------------------------------
# Aliases


def load_aliases(pdk, path=None):
    path = path or os.path.join(ALIASES, "aliases-%s.json" % pdk)
    with open(path, encoding="utf-8") as f:
        a = json.load(f)
    if a.get("pdk") != pdk:
        raise SystemExit("%s is for %s, not %s" % (path, a.get("pdk"), pdk))
    return a


def is_composite(id_text):
    """A why-text ID that is arithmetic over several rules ("via.1a + 2 *
    via.4a", "MIMTM.4-VT.4"), as opposed to a list ("nwell.5a, 7")."""
    t = id_text or ""
    return bool(re.search(r"[+*]|\s-\s|(?<=[0-9a-z])-(?=[A-Za-z])", t))


def magic_entries(rules, aliases):
    """{key: [entry]} from the data file's rule statements. An entry is
    {"id", "file", "line", "value", "unit", "styles", "operand", "why"};
    ``operand`` is true where the key is a later operand of a composite."""
    ma = aliases.get("magic", {})
    split = ma.get("split", {})
    rename = ma.get("ids", {})
    by_line = ma.get("lines", {})
    why_pats = [(re.compile(p), k) for p, k in ma.get("why", [])]
    out = collections.defaultdict(list)
    for r in rules:
        fl = "%s:%d" % (r.get("file", ""), r["line"])
        comp = is_composite(r.get("id_text", ""))
        val, unit = r.get("value_um"), r.get("unit")
        if r["keyword"].startswith("cif") and not val:
            vu = value_of(r.get("why", ""))
            val, unit = (vu[0], vu[1]) if vu else (None, None)
        base = {"file": r.get("file", ""), "line": r["line"], "value": val, "unit": unit,
                "styles": [s for s in r["styles"] if s.startswith("drc(")], "why": r.get("why", ""),
                "composite": comp, "id_text": r.get("id_text", "")}
        if fl in by_line:
            keys = [(k, False) for k in by_line[fl]]
            printed = r["ids"][0] if r["ids"] else ""
        elif r["ids"]:
            keys = []
            for i, rid in enumerate(r["ids"]):
                for part in split.get(rid, [rid]):
                    keys.append((rename.get(part, part), comp and i > 0))
            printed = r["ids"][0]
        else:
            key = None
            for rx, k in why_pats:
                if rx.search(r.get("why", "")):
                    key = k
                    break
            if key is None:
                key = r.get("why") or r["keyword"]
            keys = [(key, False)]
            printed = ""
        seen = set()
        for k, operand in keys:
            if k in seen:
                continue
            seen.add(k)
            out[k].append(dict(base, id=printed, operand=operand))
    return out


def magic_keys_by_line(rules, aliases):
    """{(file, line): [keys]}, for turning Magic's messages into rows."""
    out = {}
    for k, ents in magic_entries(rules, aliases).items():
        for e in ents:
            out.setdefault((e["file"], e["line"]), [])
            if k not in out[(e["file"], e["line"])]:
                out[(e["file"], e["line"])].append(k)
    return out


def kl_keys(name, deck, aliases):
    """(keys, other-check note or None) for a KLayout category name."""
    ka = aliases.get("klayout", {})
    scopes = [ka.get(deck, {}), ka.get("*", {})]
    for sc in scopes:
        oc = sc.get("other_check", {})
        if name in oc:
            return ["%s [%s]" % (name, deck)], oc[name]
    for sc in scopes:
        if name in sc.get("names", {}):
            return list(sc["names"][name]), None
    for sc in scopes:
        for pat, repl in sc.get("patterns", []):
            m = re.fullmatch(pat, name)
            if m:
                return [m.expand(repl)], None
    return [name], None


# ---------------------------------------------------------------------------
# The join and the statuses


def join(magic, kl_runs, run_info, located, aliases):
    """rows: {key: {"key", "magic": [...], "klayout": [...], "other_check"}}.

    ``kl_runs``: {run id: {name: [value, unit] or None}}; ``run_info``: the
    runs ({"id", "deck", "primary"}); ``located``: {deck: {name: [where]}}.
    """
    rows = {}

    def row(k):
        if k not in rows:
            rows[k] = {"key": k, "magic": [], "klayout": [], "other_check": None, "notes": []}
        return rows[k]

    for k, ents in magic.items():
        row(k)["magic"] = sorted(ents, key=lambda e: (e["file"], e["line"]))
    by_deck = collections.OrderedDict()
    for run in run_info:
        d = by_deck.setdefault(run["deck"], {})
        for name, vu in sorted(kl_runs.get(run["id"], {}).items()):
            ent = d.setdefault(name, {"deck": run["deck"], "name": name, "value": None, "unit": None,
                                      "runs": [], "where": located.get(run["deck"], {}).get(name, [])})
            ent["runs"].append(run["id"])
            if vu and ent["value"] is None:
                ent["value"], ent["unit"] = vu[0], vu[1]
    for deck, names in by_deck.items():
        for name, ent in names.items():
            keys, oc = kl_keys(name, deck, aliases)
            for k in keys:
                r = row(k)
                r["klayout"].append(dict(ent))
                if oc:
                    r["other_check"] = oc
    return rows


def _vals(entries, magic):
    out = collections.defaultdict(set)
    for e in entries:
        if e.get("value") is None:
            continue
        if magic and (e.get("composite") or e.get("operand")):
            continue
        if magic and not e["value"]:
            continue
        out[_kind(e.get("unit"))].add(round(e["value"], 6))
    return out


def values_differ(magic, kl):
    """True when both sides state a value of the same kind and no Magic
    value equals a KLayout one. Composite why-texts are left out: their
    value is a sum over rules (Magic's contact model)."""
    mv, kv = _vals(magic, True), _vals(kl, False)
    shared = set(mv) & set(kv)
    if not shared:
        return False
    return all(not any(abs(a - b) < 1e-6 for a in mv[k] for b in kv[k]) for k in shared)


def _value_list(entries, magic):
    vals = []
    for e in entries:
        if e.get("value") is None or (magic and (not e["value"] or e.get("composite") or e.get("operand"))):
            continue
        s = fmt_value(e["value"], e.get("unit"))
        if s not in vals:
            vals.append(s)
    return vals


def inventory_status(r, primary_decks, overrides):
    """Status and note from the inventory alone."""
    k = r["key"]
    if k in overrides:
        o = overrides[k]
        return o["status"], o.get("note", "")
    if r["other_check"]:
        return "same name for another check", r["other_check"]
    kl_p = [e for e in r["klayout"] if e["deck"] in primary_decks]
    kl_o = [e for e in r["klayout"] if e["deck"] not in primary_decks]
    m = r["magic"]
    if m and kl_p:
        if all(e["operand"] for e in m):
            return "folded", "Magic checks it only inside a composite rule"
        if values_differ(m, kl_p):
            return "both, values differ", "Magic %s, KLayout %s" % (
                ", ".join(_value_list(m, True)), ", ".join(_value_list(kl_p, False)))
        return "both", ""
    if m:
        note = ""
        if kl_o:
            decks = sorted({e["deck"] for e in kl_o})
            note = "%s has it" % " and ".join(decks)
            if values_differ(m, kl_o):
                note += ", with other values (Magic %s, %s %s)" % (
                    ", ".join(_value_list(m, True)), " and ".join(decks), ", ".join(_value_list(kl_o, False)))
        if all(e["operand"] for e in m):
            note = ("only inside a composite rule; " + note).rstrip("; ")
        return "Magic only", note
    return "KLayout only", ""


def message_keys(why, data, by_line):
    """Rows for one of Magic's printed messages."""
    keys = []
    for r in data.rules_by_why(why):
        for k in by_line.get((r.get("file", ""), r["line"]), []):
            if k not in keys:
                keys.append(k)
    if keys:
        return keys
    m = re.search(r"\(([^()]*)\)\s*$", why.strip())
    return [m.group(1).strip()] if m and m.group(1).strip() else [why.strip()]


def test_results(tests, data, aliases, by_line, rows, run_info):
    """Per case: what each engine reported on it and not on its control.

    Returns {case name: {"targets": [keys], "magic": {style: set(keys)},
    "klayout": {run: set(keys)}, "is_control": bool}}."""
    cases = tests["cases"]
    top_of = {c["name"]: c["top"] for c in cases}
    controls = {c.get("control") for c in cases if c.get("control")}

    def mkeys(top):
        out = {}
        for st, whys in tests["magic"].get(top, {}).items():
            ks = set()
            for why in whys:
                ks.update(message_keys(why, data, by_line))
            out[st] = ks
        return out

    deck_of = {r["id"]: r["deck"] for r in run_info}

    def kkeys(top):
        out = {}
        for run, per in tests["klayout"].items():
            ks = set()
            for name in per.get(top, {}):
                ks.update(kl_keys(name, deck_of[run], aliases)[0])
            out[run] = ks
        return out

    # The rows each printed ID names, without the rows that its statement
    # names only as a later operand of a composite: Magic prints via.5a for
    # sky130A's "via.5a - via.4a", and a case filed under via.5a is not a
    # test of via.4a.
    printed = collections.defaultdict(set)
    klname = collections.defaultdict(set)
    for k, r in rows.items():
        for e in r["magic"]:
            if e["id"] and not e["operand"]:
                printed[e["id"]].add(k)
        for e in r["klayout"]:
            klname[e["name"]].add(k)

    def target_keys(t):
        if t in printed:
            return sorted(printed[t])
        if t in rows:
            return [t]
        if t in klname:
            return sorted(klname[t])
        return [t]

    out = {}
    for c in cases:
        m, k = mkeys(c["top"]), kkeys(c["top"])
        ctl = c.get("control")
        if ctl and ctl in top_of:
            cm, ck = mkeys(top_of[ctl]), kkeys(top_of[ctl])
            m = {st: v - cm.get(st, set()) for st, v in m.items()}
            k = {run: v - ck.get(run, set()) for run, v in k.items()}
        # A target can name several rows (a Magic ID with two meanings, as
        # gf180mcuD's DF.5); where another target of the case names one of
        # them, keep only that one.
        sets = [target_keys(t) for t in c.get("targets", [])]
        tk = []
        for i, ks in enumerate(sets):
            if len(ks) > 1:
                others = set(x for j, o in enumerate(sets) if j != i for x in o)
                ks = [x for x in ks if x in others] or ks
            for x in ks:
                if x not in tk:
                    tk.append(x)
        out[c["name"]] = {"targets": tk, "magic": m, "klayout": k, "is_control": c["name"] in controls}
    return out


def build_rows(pdk, data, aliases, raw):
    """The table: (rows sorted by part and key, one-side lists, counts)."""
    run_info = raw["runs"]
    primary = {r["deck"] for r in run_info if r["primary"]}
    magic = magic_entries(data.drc.get("rules", []), aliases)
    rows = join(magic, raw["inventory"], run_info, raw["located"], aliases)
    overrides = aliases.get("status", {})
    for r in rows.values():
        r["status"], r["note"] = inventory_status(r, primary, overrides)
        r["part"] = part_of(r["key"], aliases)
        r["tested"] = []
    one_side = {"magic": {}, "klayout": {}}
    if raw.get("tests"):
        by_line = magic_keys_by_line(data.drc.get("rules", []), aliases)
        per = test_results(raw["tests"], data, aliases, by_line, rows, run_info)
        prim_runs = [r["id"] for r in run_info if r["primary"]]
        for name in sorted(per):
            t = per[name]
            for k in t["targets"]:
                if k not in rows:
                    continue
                styles = "".join(STYLE_LETTER.get(st, "?") for st in sorted(t["magic"], key=_style_order)
                                 if k in t["magic"][st])
                runs = [run for run in sorted(t["klayout"]) if k in t["klayout"][run]]
                rows[k]["tested"].append({"case": name, "magic": styles, "klayout": runs})
            if t["is_control"]:
                continue
            mk = set().union(*t["magic"].values()) if t["magic"] else set()
            kk = set().union(*(t["klayout"].get(run, set()) for run in prim_runs)) if prim_runs else set()
            for k in sorted(mk - kk):
                one_side["magic"].setdefault(k, []).append(name)
            for k in sorted(kk - mk):
                one_side["klayout"].setdefault(k, []).append(name)
        for r in rows.values():
            if not r["tested"] or r["status"] not in ("both", "Magic only", "KLayout only"):
                continue
            has_m = bool(r["magic"])
            has_k = any(e["deck"] in primary for e in r["klayout"])
            silent = []
            if has_m and not any(x["magic"] for x in r["tested"]):
                silent.append("Magic")
            if has_k and not any(set(x["klayout"]) & set(prim_runs) for x in r["tested"]):
                silent.append("KLayout")
            if silent:
                r["status"] = "in the deck, did not fire on its case"
                r["note"] = ("%s reported nothing on %s" % (
                    " and ".join(silent), ", ".join(x["case"] for x in r["tested"]))
                             + ("; " + r["note"] if r["note"] else ""))
    parts = [p["name"] for p in aliases.get("parts", [])] + ["Other"]
    ordered = sorted(rows.values(), key=lambda r: (parts.index(r["part"]) if r["part"] in parts else 99,
                                                   _natural(r["key"])))
    counts = collections.OrderedDict()
    for p in parts:
        counts[p] = collections.OrderedDict((s, 0) for s in STATUSES)
    for r in ordered:
        counts.setdefault(r["part"], collections.OrderedDict((s, 0) for s in STATUSES))
        counts[r["part"]][r["status"]] += 1
    counts = collections.OrderedDict((p, c) for p, c in counts.items() if sum(c.values()))
    return ordered, one_side, counts


def _style_order(st):
    return ["drc(fast)", "drc(full)", "drc(routing)"].index(st) if st in STYLE_LETTER else 9


def _natural(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def part_of(key, aliases):
    for p in aliases.get("parts", []):
        if re.search(p["match"], key):
            return p["name"]
    return "Other"


# ---------------------------------------------------------------------------
# Outputs


def _md(s):
    return str(s).replace("|", "\\|").replace("\n", " ")


def _where(e):
    lines = sorted({w["line"] for w in e["where"]})
    files = sorted({os.path.basename(w["file"]) for w in e["where"]})
    if not lines:
        return ""
    return ("%s:" % files[0] if len(files) == 1 and e["deck"] in ("main", "maximal") else ":") + \
        ",".join(str(x) for x in lines[:4]) + ("…" if len(lines) > 4 else "")


def _switch(e, run_names):
    sw = sorted({w["switch"] for w in e["where"] if w["switch"]})
    bits = []
    if sw:
        bits.append(" / ".join(sw))
    all_runs = [r for r in run_names if run_names[r] == e["deck"]]
    if len(all_runs) > 1 and set(e["runs"]) != set(all_runs):
        bits.append("only in " + ", ".join(e["runs"]))
    return (" [%s]" % "; ".join(bits)) if bits else ""


def _kl_cell(entries, run_names):
    if not entries:
        return "–"
    if len(entries) > 4:
        lines = sorted({w["line"] for e in entries for w in e["where"]})
        span = (" :%d-%d" % (lines[0], lines[-1])) if lines else ""
        return "%d names, e.g. %s%s" % (len(entries), ", ".join(e["name"] for e in entries[:3]), span)
    out = []
    for e in entries:
        out.append("%s %s%s %s" % (e["name"], fmt_value(e["value"], e["unit"]) if e["value"] is not None else "–",
                                    _switch(e, run_names), _where(e)))
    return "; ".join(s.strip() for s in out)


def _magic_cell(entries, key):
    if not entries:
        return "–"
    out = []
    for e in entries:
        st = "".join(STYLE_LETTER.get(s, "") for s in e["styles"])
        v = fmt_value(e["value"], e["unit"]) if e["value"] else "–"
        label = ""
        if e["operand"] or (e["composite"] and e["id_text"]):
            label = "in (%s) " % e["id_text"]
        elif e["id"] and e["id"] != key:
            label = "as %s " % e["id"]
        out.append("%s%s [%s] :%d" % (label, v, st, e["line"]))
    if len(out) > 6:
        out = out[:6] + ["%d more" % (len(entries) - 6)]
    return "; ".join(out)


def _tested_cell(tested, run_short):
    if not tested:
        return ""
    out = []
    for t in tested[:4]:
        k = ",".join(run_short.get(r, r) for r in t["klayout"]) or "no"
        out.append("%s: Magic %s, KLayout %s" % (t["case"], t["magic"] or "no", k))
    if len(tested) > 4:
        out.append("%d more" % (len(tested) - 4))
    return "; ".join(out)


def table_json(pdk, data, raw, rows, one_side, counts):
    return {
        "schema": SCHEMA,
        "pdk": pdk,
        "image": raw.get("image"),
        "tools": raw.get("tools"),
        "pdk_source": {k: data.source.get(k) for k in ("open_pdks", "magic_tech_version", "tech_sha256")},
        "runs": raw["runs"],
        "categories": {r["id"]: len(raw["inventory"].get(r["id"], {})) for r in raw["runs"]},
        "tested": bool(raw.get("tests")),
        "cases": len(raw["tests"]["cases"]) if raw.get("tests") else 0,
        "counts": counts,
        "rows": [{
            "key": r["key"], "part": r["part"], "status": r["status"], "note": r["note"],
            "magic": [{k: e[k] for k in ("id", "id_text", "file", "line", "value", "unit", "styles", "operand")}
                      for e in r["magic"]],
            "klayout": [{"deck": e["deck"], "name": e["name"], "value": e["value"], "unit": e["unit"],
                         "runs": e["runs"], "where": e["where"]} for e in r["klayout"]],
            "tested": r["tested"],
        } for r in rows],
        "one_side": one_side,
    }


def pkg_json(pdk, rows):
    """pkg/data/gaps-<pdk>.json for the DRC job: one entry per row that has a
    Magic statement of its own, under the row's key, with the row's status
    and KLayout outputs, the IDs Magic prints for those statements ("ids")
    and their tech-file lines ("lines", as "file:line"). The job finds a
    why-text's rows through its statements' lines, so that one printed ID
    whose statements sit in several rows (IHP's AFil.i, sky130A's hvi.5)
    gives each statement its own row. A statement that names a row only as a
    later operand of a composite is not that row's: Magic's message for it
    is the first ID's."""
    out = {}
    for r in rows:
        own = [e for e in r["magic"] if not e["operand"]]
        if not own:
            continue
        kl, lines, ids = [], [], []
        for e in r["klayout"]:
            item = {"deck": e["deck"], "name": e["name"], "value": e["value"]}
            if item not in kl:
                kl.append(item)
        for e in own:
            fl = "%s:%d" % (e["file"], e["line"])
            if fl not in lines:
                lines.append(fl)
            if e["id"] and e["id"] not in ids:
                ids.append(e["id"])
        out[r["key"]] = {"status": r["status"], "key": r["key"], "klayout": kl, "lines": lines, "ids": ids}
    return {"schema": PKG_SCHEMA, "pdk": pdk, "rules": out}


def _deck_label(decks):
    """The KLayout side as the page names it: `deck`, or `run_drc.py`'s main
    and maximal decks on the IHP PDKs."""
    if set(decks) == {"main", "maximal"}:
        return "the `main` and `maximal` decks of `run_drc.py`"
    return " and ".join("`%s`" % d for d in decks)


def table_md(pdk, data, raw, rows, one_side, counts):
    runs = raw["runs"]
    decks = []
    for r in runs:
        if r["deck"] not in decks:
            decks.append(r["deck"])
    run_names = {r["id"]: r["deck"] for r in runs}
    run_short = {r["id"]: r["id"] for r in runs}
    tools = raw.get("tools") or {}
    src = data.source
    primary_label = _deck_label(sorted({r["deck"] for r in runs if r["primary"]}))
    L = []
    L.append("# Gap table: %s" % pdk)
    L.append("")
    L.append("This table compares Magic's DRC rules for %s with the PDK's KLayout DRC decks, one row per rule, "
             "and shows where they disagree. `tools/build_gaps.py` generates it; do not edit it by hand." % pdk)
    L.append("")
    L.append("- **What a row is.** One rule, under the rule ID that Magic's why-text gives it (the why-text is "
             "the message Magic's DRC gives an error box, and the ID is the text in its last parentheses), under "
             "a name from `tests/gaps/aliases-%s.json` where the two tools name the rule differently, under "
             "the KLayout name where Magic has no such rule, or under Magic's whole message where the message "
             "has no ID. The row gives the statements of Magic's tech file that check the rule, each KLayout "
             "deck's outputs for it (the report categories the deck writes), and what both engines reported on "
             "the test cases that target it." % pdk)
    L.append("- **How it is made.** Magic's rules come from `python/klayout_magic_pcells/data/pdk-%s.json`. "
             "Each KLayout run below checked a layout of one box. Its report has a category for every rule the "
             "deck ran under its switches, and those categories are the deck's side of the table; a text scan "
             "of the deck gives each output's line and the switches it sits under. The two sides are joined on "
             "rule ID, with the mappings made by hand in `tests/gaps/aliases-%s.json`. The test cases are the "
             "`gaps` set of the case suite (`tests/cases`): a clean control layout, and cases that each change "
             "one thing in it. Magic checked each case cell alone in all three styles, at most 15 cells per "
             "process; KLayout checked them on one sheet, 40 µm apart. A case's results are the rules reported "
             "on it and not on its control." % (pdk, pdk))
    L.append("- **Image.** The pinned Docker image `%s`, with Magic %s and KLayout %s; %s (Magic tech %s)." % (
        raw.get("image") or "unknown", tools.get("magic") or "unknown",
        (tools.get("klayout") or "unknown").replace("KLayout ", ""),
        (("PDK commit " if pdk.startswith("ihp-") else "open_pdks ") + src.get("open_pdks", "")[:8])
        if src.get("open_pdks") else "PDK",
        src.get("magic_tech_version", "?")))
    L.append("- **Rebuild.** `scripts/gaps.sh --pdk %s` rewrites this page; `scripts/gaps.sh --pdk %s --check` "
             "fails if it would change." % (pdk, pdk))
    L.append("")
    L.append("Each row has one status. The status and the value comparison take %s as the KLayout side; "
             "the other decks have their own columns." % primary_label)
    L.append("")
    L.append("- **both**: Magic and the KLayout side both check the rule.")
    L.append("- **both, values differ**: both check it, with different values; the note gives both.")
    L.append("- **folded**: Magic checks the ID only inside a composite rule, such as `V1.a + 2 * M2.c`.")
    L.append("- **measured on other shapes**: both check it, on different shapes; the note says which.")
    L.append("- **same name for another check**: the name means a different rule on each side; the note says "
             "what each one checks.")
    L.append("- **in the deck, did not fire on its case**: a tool has the rule but reported nothing on the cases "
             "that break it; the note names the tool and the cases.")
    L.append("- **Magic only**: the KLayout side does not have the rule; the note says when another deck has "
             "it, or when Magic checks it only inside a composite rule.")
    L.append("- **KLayout only**: Magic has no such rule.")
    L.append("")
    L.append("In the Magic column each statement reads `value [styles] :line`, with the styles F `drc(fast)`, "
             "U `drc(full)` and R `drc(routing)`; `in (...)` names the composite rule a value belongs to, and "
             "`as X` the ID under which Magic prints the rule. In a deck's column each output reads "
             "`name value [switch] :line`, where the switch is the condition around the output in the deck, and "
             "`only in` names the runs that report it when the deck has several. `:n` is a line of the tech "
             "file or deck, and – means none. The Tested column gives, for each case that targets the rule, "
             "the Magic styles and the KLayout runs that reported it there; `no` means none did.")
    L.append("")
    L.append("## Counts")
    L.append("")
    used = [s for s in STATUSES if any(c[s] for c in counts.values())]
    L.append("| Part | " + " | ".join(used) + " | total |")
    L.append("|---|" + "---|" * (len(used) + 1))
    tot = collections.Counter()
    for p, c in counts.items():
        L.append("| %s | %s | %d |" % (_md(p), " | ".join(str(c[s]) for s in used), sum(c.values())))
        tot.update(c)
    L.append("| all | %s | %d |" % (" | ".join(str(tot[s]) for s in used), sum(tot.values())))
    L.append("")
    L.append("## KLayout runs")
    L.append("")
    L.append("Each run checked a layout of one box; the last column counts the categories in its report. "
             "\"The harness\" is the plugin's parity harness (`tests/parity`).")
    L.append("")
    L.append("| Run | What | Categories on one box |")
    L.append("|---|---|---|")
    for r in runs:
        L.append("| %s | %s | %d |" % (r["id"], _md(r["what"]), len(raw["inventory"].get(r["id"], {}))))
    L.append("")
    if raw.get("tests"):
        L.append("Cases: %d in the `gaps` set." % len(raw["tests"]["cases"]))
    else:
        L.append("Cases: not run for this build.")
    L.append("")
    L.append("## Rules")
    for p in counts:
        L.append("")
        L.append("### %s" % p)
        L.append("")
        L.append("| Rule | Status | Magic: value [styles] :line | " + " | ".join("%s: name value [switch] :line" % d for d in decks)
                 + " | Tested (case: what each engine reported) |")
        L.append("|---|---|---|" + "---|" * len(decks) + "---|")
        for r in rows:
            if r["part"] != p:
                continue
            st = r["status"] + ((": " + r["note"]) if r["note"] else "")
            cells = [_kl_cell([e for e in r["klayout"] if e["deck"] == d], run_names) for d in decks]
            L.append("| %s | %s | %s | %s | %s |" % (_md(r["key"]), _md(st), _md(_magic_cell(r["magic"], r["key"])),
                                                     " | ".join(_md(c) for c in cells),
                                                     _md(_tested_cell(r["tested"], run_short))))
    L.append("")
    L.append("## Rules only one side reported in a test")
    L.append("")
    if not raw.get("tests"):
        L.append("Not run for this build.")
    else:
        L.append("Each line gives a rule and the cases, controls left out, on which one engine reported it and "
                 "the other did not. Magic's side is any of its styles; KLayout's side is %s." % primary_label)
        L.append("")
    for side, title in (("magic", "Reported by Magic and not by %s" % primary_label.replace(
            "the `main` and `maximal` decks of `run_drc.py`", "the main and maximal decks").replace("`", "")),
                        ("klayout", "Reported by KLayout and not by Magic")):
        if not raw.get("tests"):
            break
        L.append("### %s" % title)
        L.append("")
        if not one_side[side]:
            L.append("None.")
        for k in sorted(one_side[side], key=_natural):
            cs = one_side[side][k]
            L.append("- `%s`: %s%s" % (_md(k), ", ".join(cs[:8]), (" and %d more" % (len(cs) - 8)) if len(cs) > 8 else ""))
        L.append("")
    return "\n".join(L).rstrip() + "\n"


def readme_md(tables):
    L = ["# Gap tables", "",
         "One table per PDK compares Magic's DRC rules with the PDK's KLayout DRC decks and shows where they "
         "disagree. `tools/build_gaps.py` generates the tables in the pinned Docker image "
         "(`scripts/in_image.sh`). `scripts/gaps.sh` rebuilds all four; `scripts/gaps.sh --check` fails when "
         "a table would change, for example after a PDK or Magic update. The alias files "
         "`tests/gaps/aliases-<pdk>.json` are the only part typed by hand.", "",
         "In the table below, each status column counts the rules with that status, `rules` is their total, "
         "and `cases` is the number of test cases in the PDK's `gaps` set. Each page says what the statuses "
         "mean.", ""]
    used = [s for s in STATUSES if any(t["counts"] and sum(c[s] for c in t["counts"].values()) for t in tables)]
    L.append("| PDK | " + " | ".join(used) + " | rules | cases |")
    L.append("|---|" + "---|" * (len(used) + 2))
    for t in tables:
        tot = collections.Counter()
        for c in t["counts"].values():
            tot.update(c)
        L.append("| [%s](%s.md) | %s | %d | %d |" % (t["pdk"], t["pdk"], " | ".join(str(tot[s]) for s in used),
                                                   sum(tot.values()), t["cases"]))
    L.append("")
    L.append("Each page also has a `.json` file with the same rows. The plugin's DRC check (`drc`) reads "
             "`python/klayout_magic_pcells/data/gaps-<pdk>.json`, built at the same time, for the descriptions "
             "of its report categories.")
    return "\n".join(L) + "\n"


def dumps(obj):
    return json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def dumps_rows(obj, key):
    """JSON with each item of obj[key] (a list or dict) on one line, so that
    a changed rule shows as one changed line."""
    def one(x):
        return json.dumps(x, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    head = {k: v for k, v in obj.items() if k != key}
    text = json.dumps(head, indent=1, sort_keys=True, ensure_ascii=False)
    items = obj[key]
    if isinstance(items, dict):
        body = ",\n".join("  %s: %s" % (json.dumps(k, ensure_ascii=False), one(items[k])) for k in sorted(items))
        block = "{\n%s\n }" % body if items else "{}"
    else:
        body = ",\n".join("  " + one(x) for x in items)
        block = "[\n%s\n ]" % body if items else "[]"
    return text[:-2] + ",\n %s: %s\n}\n" % (json.dumps(key), block) if head else "{\n %s: %s\n}\n" % (json.dumps(key), block)


# ---------------------------------------------------------------------------
# Driver


def run_raw(pdk, work, tests=True):
    """Run everything in the image; return the raw results (and save them)."""
    sys.path.insert(0, REPO)
    from tests.gaps import runner
    from klayout_magic_pcells import pdkdata
    data = pdkdata.load(pdk)
    t0 = time.time()
    run_info = runner.runs(pdk)
    inv = runner.inventory(pdk, os.path.join(work, "inventory"), value_of)
    located = {}
    for deck, files in runner.deck_files(pdk).items():
        outs = []
        for rel, path in files:
            with open(path, encoding="utf-8", errors="replace") as f:
                text = f.read()
            outs += scan_deck(text, rel)
        names = set()
        for r in run_info:
            if r["deck"] == deck or deck in ("main", "maximal"):
                names |= set(inv.get(r["id"], {}))
        located[deck] = locate(sorted(names), outs)
    if pdk.startswith("ihp-"):
        # One merged report holds both decks: list each category under the
        # deck(s) whose text has it, the main deck where neither does.
        merged = inv["harness"]
        inv = {"harness_main": {n: v for n, v in merged.items() if n in located["main"] or n not in located["maximal"]},
               "harness_maximal": {n: v for n, v in merged.items() if n in located["maximal"]}}
        run_info = [dict(run_info[0], id="harness_main", deck="main"),
                    dict(run_info[0], id="harness_maximal", deck="maximal")]
    t_inv = time.time() - t0
    raw = {"pdk": pdk, "runs": run_info, "inventory": inv, "located": located,
           "image": os.environ.get("KMP_IMAGE"), "tools": runner.tool_versions()}
    if tests:
        styles = [s for s in data.drc.get("styles", []) if s.startswith("drc(")]
        tr = runner.tests(pdk, os.path.join(work, "tests"), styles)
        if pdk.startswith("ihp-"):
            per = tr["klayout"].pop("harness")
            tr["klayout"] = {
                rid: {top: {n: c for n, c in cats.items() if n in inv[rid] or n not in merged}
                      for top, cats in per.items()}
                for rid in ("harness_main", "harness_maximal")}
        raw["tests"] = tr
    raw["elapsed"] = {"inventory_s": round(t_inv, 1), "total_s": round(time.time() - t0, 1)}
    os.makedirs(work, exist_ok=True)
    with open(os.path.join(work, "raw.json"), "w", encoding="utf-8") as f:
        f.write(dumps(raw))
    return raw


def outputs(pdk, raw, data=None, aliases=None):
    """{path: text} of the per-PDK files, and the table JSON."""
    if data is None:
        sys.path.insert(0, os.path.join(REPO, "python"))
        from klayout_magic_pcells import pdkdata
        data = pdkdata.load(pdk)
    aliases = aliases or load_aliases(pdk)
    rows, one_side, counts = build_rows(pdk, data, aliases, raw)
    tj = table_json(pdk, data, raw, rows, one_side, counts)
    files = {
        os.path.join(DOCS, pdk + ".md"): table_md(pdk, data, raw, rows, one_side, counts),
        os.path.join(DOCS, pdk + ".json"): dumps_rows(tj, "rows"),
        os.path.join(PKG_DATA, "gaps-%s.json" % pdk): dumps_rows(pkg_json(pdk, rows), "rules"),
    }
    return files, tj


def compare(files):
    """[(path, first lines of the diff)] for files that differ from disk."""
    bad = []
    for path, text in sorted(files.items()):
        try:
            with open(path, encoding="utf-8") as f:
                old = f.read()
        except OSError:
            bad.append((path, "missing"))
            continue
        if old != text:
            d = list(difflib.unified_diff(old.splitlines(), text.splitlines(), "committed", "rebuilt",
                                          lineterm="", n=0))
            bad.append((path, "\n".join(d[:12]) + ("\n..." if len(d) > 12 else "")))
    return bad


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--pdk", action="append", choices=PDKS)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--check", action="store_true", help="rebuild and compare with the committed files")
    ap.add_argument("--update-baseline", action="store_true", help="write the files (the default without --check)")
    ap.add_argument("--work", default=os.path.join(REPO, "out", "gaps"), help="scratch folder (default out/gaps)")
    ap.add_argument("--raw", action="store_true", help="build from <work>/<pdk>/raw.json instead of running")
    ap.add_argument("--no-tests", action="store_true", help="inventory only (for development)")
    args = ap.parse_args(argv)
    if args.check and args.update_baseline:
        ap.error("--check and --update-baseline exclude each other")
    pdks = list(PDKS) if args.all or not args.pdk else args.pdk
    rc = 0
    tables = {}
    for pdk in pdks:
        t0 = time.time()
        work = os.path.join(args.work, pdk)
        if args.raw:
            with open(os.path.join(work, "raw.json"), encoding="utf-8") as f:
                raw = json.load(f)
        else:
            raw = run_raw(pdk, work, tests=not args.no_tests)
        files, tj = outputs(pdk, raw)
        tables[pdk] = tj
        took = time.time() - t0
        tot = collections.Counter()
        for c in tj["counts"].values():
            tot.update(c)
        print("%s: %d rules (%s), %d cases, %.0f s" % (
            pdk, sum(tot.values()), ", ".join("%s %d" % (s, tot[s]) for s in STATUSES if tot[s]),
            tj["cases"], took), file=sys.stderr)
        if args.check:
            bad = compare(files)
            for path, d in bad:
                print("GAPS DIFFER %s\n%s" % (os.path.relpath(path, REPO), d))
            if bad:
                rc = 1
            else:
                print("GAPS OK %s" % pdk)
        else:
            for path, text in files.items():
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
            print("GAPS WRITTEN %s" % pdk)
    # README: the tables of this run, the committed ones for the other PDKs
    all_tables = []
    for pdk in PDKS:
        if pdk in tables:
            all_tables.append(tables[pdk])
            continue
        try:
            with open(os.path.join(DOCS, pdk + ".json"), encoding="utf-8") as f:
                all_tables.append(json.load(f))
        except OSError:
            pass
    readme = {os.path.join(DOCS, "README.md"): readme_md(all_tables)}
    if args.check:
        bad = compare(readme)
        for path, d in bad:
            print("GAPS DIFFER %s\n%s" % (os.path.relpath(path, REPO), d))
        rc = 1 if bad else rc
    else:
        for path, text in readme.items():
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
    return rc


if __name__ == "__main__":
    sys.exit(main())
