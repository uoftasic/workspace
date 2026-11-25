"""The jobs step's case suite: tests/cases/build.py, all sets, with the PCell
inverter and the Magic-written row (design-0.6.md 5.1 and 5.2). ``--quick``
builds the inverters, gaps and controls sets, without the Magic-written
row: the quick step runs the inverters and three more cases from those two
sets (run_jobs.QUICK_EXTRA).

    python3 tests/jobs/build_cases.py --pdk P --out DIR [--quick]

Run it in the image. It prints build.py's CASES line and its WARNING lines,
and exits 1 when build.py warned (a set or the PCell inverter was not built),
so the step never runs on a suite with holes in it.
"""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
for p in (REPO, os.path.join(REPO, "python"), os.path.join(REPO, "tests", "parity")):
    if p not in sys.path:
        sys.path.insert(0, p)

from tests.cases import build  # noqa: E402

QUICK_SETS = ("gaps", "inverters", "controls")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--pdk", required=True, choices=sorted(build.MODULES))
    ap.add_argument("--out", required=True)
    ap.add_argument("--quick", action="store_true", help="the quick step's sets, without the Magic-written row")
    a = ap.parse_args(argv)
    sets = list(QUICK_SETS) if a.quick else list(build.SETS)
    records, warnings = build.build(a.pdk, a.out, sets, pcell=True,
                                    magic_row="controls" in sets and not a.quick)
    counts = {}
    for r in records:
        counts[r["set"]] = counts.get(r["set"], 0) + 1
    print("CASES %s %s" % (a.pdk, " ".join("%s=%d" % kv for kv in sorted(counts.items()))))
    for w in warnings:
        print("WARNING " + w)
    return 1 if warnings else 0


if __name__ == "__main__":
    sys.exit(main())
