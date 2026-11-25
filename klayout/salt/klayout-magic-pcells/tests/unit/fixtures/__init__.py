"""A small stand-in for pdkdata.PdkData, built from pdk-mini.json, which
follows the data file's schema (design-0.6.md 4). The unit tests
use it instead of the real data files."""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
MINI = os.path.join(HERE, "pdk-mini.json")


class MiniData:
    def __init__(self, doc):
        self.json = doc
        self.pdk = doc["pdk"]
        self.grid_um = doc["grid_um"]
        self.error_marker = doc.get("error_marker")
        self._layers = {tuple(r["gds"]): r for r in doc["layers"]}

    def layer(self, gds_l, gds_d):
        return self._layers.get((gds_l, gds_d))

    def rules_by_why(self, why_text):
        return [r for r in self.json["drc"]["rules"] if r["why"] == why_text]

    def generated(self):
        return list(self.json["generated"])

    def ports(self):
        return dict(self.json["ports"])


def mini_data(**changes):
    with open(MINI, encoding="utf-8") as f:
        doc = json.load(f)
    doc.update(changes)
    return MiniData(doc)
