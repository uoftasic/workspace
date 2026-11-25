import os
import tempfile
import unittest

from tests.unit._util import db, needs_klayout


def synth(path, dbu, two_tops=False, sub=False):
    ly = db.Layout()
    ly.dbu = dbu
    top = ly.create_cell("SRC")
    li = ly.layer(68, 20)
    top.shapes(li).insert(db.DBox(-0.5, -0.25, 0.5, 0.25))
    top.shapes(ly.layer(68, 5)).insert(db.DText("D", db.DTrans(db.DVector(0.105, -0.005))))
    top.shapes(ly.layer(235, 4)).insert(db.DBox(-1, -1, 1, 1))
    if sub:
        s = ly.create_cell("SUB")
        s.shapes(li).insert(db.DBox(0, 0, 0.17, 0.17))
        top.insert(db.DCellInstArray(s.cell_index(), db.DTrans(db.DVector(0.3, 0.3)),
                                     db.DVector(0.34, 0), db.DVector(0, 0.34), 2, 2))
    if two_tops:
        ly.create_cell("OTHER").shapes(li).insert(db.DBox(5, 5, 6, 6))
    ly.write(path)
    return path


def flat(ly, cell):
    out = {}
    for li in ly.layer_indices():
        info = ly.get_info(li)
        r = db.Region(cell.begin_shapes_rec(li))
        r.merge()
        t = sorted((x.string, round(x.x * ly.dbu, 6), round(x.y * ly.dbu, 6))
                   for x in db.Texts(cell.begin_shapes_rec(li)).each())
        polys = sorted(str(p.to_dtype(ly.dbu)) for p in r.each())
        if polys or t:
            out[(info.layer, info.datatype)] = (polys, t)
    return out


@needs_klayout
class Importer(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def check_exact(self, src_dbu, host_dbu, sub=False):
        from klayout_magic_pcells.importer import insert_gds_flat
        p = synth(os.path.join(self.d, "s%g.gds" % src_dbu), src_dbu, sub=sub)
        ly = db.Layout()
        ly.dbu = host_dbu
        c = ly.create_cell("DST")
        insert_gds_flat(ly, c, p)
        src = db.Layout()
        src.read(p)
        self.assertEqual(flat(src, src.top_cell()), flat(ly, c))
        self.assertEqual(len(list(ly.each_cell())), 1)  # no subcells created
        self.assertAlmostEqual(ly.dbu, host_dbu)

    def test_same_dbu(self):
        self.check_exact(0.001, 0.001)

    def test_coarser_source(self):
        self.check_exact(0.005, 0.001)

    def test_subcells_are_flattened(self):
        self.check_exact(0.001, 0.001, sub=True)

    def test_finer_source_is_refused(self):
        from klayout_magic_pcells.importer import GdsImportError, insert_gds_flat
        p = synth(os.path.join(self.d, "fine.gds"), 0.0005)
        ly = db.Layout()
        with self.assertRaises(GdsImportError):
            insert_gds_flat(ly, ly.create_cell("X"), p)

    def test_two_top_cells_are_refused(self):
        from klayout_magic_pcells.importer import GdsImportError, insert_gds_flat
        p = synth(os.path.join(self.d, "two.gds"), 0.001, two_tops=True)
        ly = db.Layout()
        with self.assertRaises(GdsImportError):
            insert_gds_flat(ly, ly.create_cell("X"), p)


@needs_klayout
class Grid(unittest.TestCase):
    """The grid in a variant's stamp, which audit checks against a file's dbu."""

    def setUp(self):
        self.d = tempfile.mkdtemp()

    def write(self, name, build):
        ly = db.Layout()
        ly.dbu = 0.001
        top = ly.create_cell("TOP")
        build(ly, top)
        p = os.path.join(self.d, name)
        ly.write(p)
        return p

    def test_grid_and_emptiness(self):
        from klayout_magic_pcells.importer import gds_grid_nm, gds_has_shapes
        li = (68, 20)

        def box(x1, y1, x2, y2):
            return lambda ly, top: top.shapes(ly.layer(*li)).insert(db.Box(x1, y1, x2, y2))
        self.assertEqual(gds_grid_nm(self.write("a.gds", box(0, 0, 260, 250))), 10)
        self.assertEqual(gds_grid_nm(self.write("b.gds", box(-265, 0, 5, 260))), 5)
        self.assertEqual(gds_grid_nm(self.write("c.gds", box(0, 0, 1001, 1000))), 1)

        def text(ly, top):
            top.shapes(ly.layer(*li)).insert(db.Box(0, 0, 100, 100))
            top.shapes(ly.layer(68, 5)).insert(db.Text("E", db.Trans(db.Vector(0, 7))))
        self.assertEqual(gds_grid_nm(self.write("t.gds", text)), 1)

        def array(pitch):
            def build(ly, top):
                sub = ly.create_cell("SUB")
                sub.shapes(ly.layer(*li)).insert(db.Box(0, 0, 170, 170))
                top.insert(db.CellInstArray(sub.cell_index(), db.Trans(db.Vector(10, 10)),
                                            db.Vector(pitch, 0), db.Vector(0, 340), 3, 2))
            return build
        self.assertEqual(gds_grid_nm(self.write("r10.gds", array(340))), 10)
        self.assertEqual(gds_grid_nm(self.write("r5.gds", array(345))), 5)

        def empty_sub(ly, top):
            sub = ly.create_cell("STUB")
            top.insert(db.CellInstArray(sub.cell_index(), db.Trans(db.Vector(3, 3))))
        p = self.write("e.gds", empty_sub)
        self.assertFalse(gds_has_shapes(p))
        self.assertIsNone(gds_grid_nm(p))
        self.assertTrue(gds_has_shapes(self.write("a2.gds", box(0, 0, 260, 260))))
        self.assertTrue(gds_has_shapes(self.write("t2.gds", text)))

    def test_audit_takes_the_grid_from_the_stamp(self):
        from klayout_magic_pcells.audit import _grid_problem
        from klayout_magic_pcells.config import shipped_manifest
        from klayout_magic_pcells.manifest import Manifest
        man = Manifest.load(shipped_manifest("sky130A"))
        self.assertEqual(man["mcon"].raw["defaults_run"]["grid_nm"], 10)
        # The testers' case: an mcon whose box puts it on 5 nm, in a 2 nm file.
        self.assertIn("5 nm grid", _grid_problem(man, "mcon", 0.002, {"grid": "5"}))
        self.assertIsNone(_grid_problem(man, "mcon", 0.0025, {"grid": "5"}))
        self.assertIsNone(_grid_problem(man, "mcon", 0.002, {"grid": "10"}))
        self.assertIn("1 nm grid", _grid_problem(man, "mcon", 0.005, {"grid": "1"}))
        # A stamp without a grid (version 0.3): the default output's grid.
        self.assertIsNone(_grid_problem(man, "mcon", 0.002, {}))
        self.assertIn("at its defaults", _grid_problem(man, "sky130_fd_pr__pnp_05v5_W0p68L0p68",
                                                       0.005, {}))
        from klayout_magic_pcells.pcell import stamp_with_grid
        from klayout_magic_pcells.stamp import parse_stamp
        self.assertEqual(parse_stamp(stamp_with_grid("kmp1;pdk=sky130A;key=ab", 5))["grid"], "5")
        self.assertEqual(stamp_with_grid("kmp1;pdk=sky130A", None), "kmp1;pdk=sky130A")


class _V:
    magic, tech, pdk = "8.3.681", "1.0.588-56-g026824c", "sky130A"


@needs_klayout
class Stamps(unittest.TestCase):
    def test_format(self):
        from klayout_magic_pcells.stamp import make_stamp, parse_stamp
        s = make_stamp(_V, "3f9a12c4d1e07b55aaaa")
        self.assertEqual(s, "kmp1;magic=8.3.681;tech=1.0.588-56-g026824c;pdk=sky130A;digest=da5f2146a264;"
                            "key=3f9a12c4d1e07b55")
        self.assertEqual(parse_stamp(s)["key"], "3f9a12c4d1e07b55")
        self.assertNotIn("key", parse_stamp(make_stamp(_V)))
        self.assertIsNone(parse_stamp("something else"))
        self.assertIsNone(parse_stamp(None))

    def test_digest_follows_the_code_and_the_pdk(self):
        from klayout_magic_pcells.stamp import make_stamp, parse_stamp, same_versions

        class A(_V):
            open_pdks, code, techfile = "026824c7", "c" * 64, "t" * 64
        base = parse_stamp(make_stamp(A))
        for field in ("open_pdks", "code", "techfile", "pdk_commit", "techdir", "vendor"):
            other = type("B", (A,), {field: "other"})
            st = parse_stamp(make_stamp(other))
            self.assertNotEqual(st["digest"], base["digest"], field)
            self.assertFalse(same_versions(st, base), field)
        self.assertTrue(same_versions(parse_stamp(make_stamp(A, "k" * 16)), base))
        # a stamp written before the digest existed compares on magic, tech, pdk
        old = parse_stamp("kmp1;magic=8.3.681;tech=1.0.588-56-g026824c;pdk=sky130A;key=ab")
        self.assertTrue(same_versions(old, base))
        self.assertFalse(same_versions(dict(old, magic="8.3.700"), base))

    def test_goes_on_the_boundary_and_survives_gds_and_oasis(self):
        from klayout_magic_pcells.stamp import STAMP_ATTR, apply_stamp, make_stamp, read_stamp
        ly = db.Layout()
        c = ly.create_cell("C")
        c.shapes(ly.layer(66, 20)).insert(db.DBox(-3, -3, -2, -2))
        c.shapes(ly.layer(235, 4)).insert(db.DBox(-1, -1, 1, 1))
        self.assertTrue(apply_stamp(ly, c, make_stamp(_V, "ab" * 8)))
        # setting a property replaces the Shape reference, so look it up again
        [b] = list(c.shapes(ly.layer(235, 4)).each())
        self.assertEqual(b.property(STAMP_ATTR), make_stamp(_V, "ab" * 8))
        self.assertTrue(all(s.prop_id == 0 for s in c.shapes(ly.layer(66, 20)).each()))
        d = tempfile.mkdtemp()
        for ext in ("gds", "oas"):
            p = os.path.join(d, "s." + ext)
            ly.write(p)
            ly2 = db.Layout()
            ly2.read(p)
            st = read_stamp(ly2.cell("C"))
            self.assertEqual(st["key"], "ab" * 8, ext)

    def test_fallback_shape(self):
        from klayout_magic_pcells.stamp import STAMP_ATTR, apply_stamp
        ly = db.Layout()
        c = ly.create_cell("C")
        c.shapes(ly.layer(68, 20)).insert(db.DBox(-5, -5, 0, 0))
        c.shapes(ly.layer(67, 20)).insert(db.DBox(1, 1, 2, 2))
        c.shapes(ly.layer(67, 20)).insert(db.DBox(-1, -1, 0, 0))
        apply_stamp(ly, c, "kmp1;x=1")
        stamped = [(str(s.dbox), s.property(STAMP_ATTR)) for li in ly.layer_indices()
                   for s in c.shapes(li).each() if s.prop_id]
        self.assertEqual(stamped, [("(-1,-1;0,0)", "kmp1;x=1")])

    def test_empty_cell(self):
        from klayout_magic_pcells.stamp import apply_stamp, read_stamp
        ly = db.Layout()
        c = ly.create_cell("C")
        self.assertFalse(apply_stamp(ly, c, "kmp1;x=1"))
        self.assertIsNone(read_stamp(c))


@needs_klayout
class Declarations(unittest.TestCase):
    def test_every_device_declares(self):
        from klayout_magic_pcells.config import SHIPPED_MANIFEST
        from klayout_magic_pcells.manifest import Manifest
        from klayout_magic_pcells.pcell import make_pcell

        from klayout_magic_pcells.config import SUPPORTED_PDKS, shipped_manifest

        class St:
            created_stamp = "kmp1;magic=x;tech=y;pdk=sky130A"
            generator = None
            library_name = "test_magic"

            class cfg:
                lazy = False

        types = {"float": db.PCellParameterDeclaration.TypeDouble,
                 "int": db.PCellParameterDeclaration.TypeInt,
                 "bool01": db.PCellParameterDeclaration.TypeBoolean,
                 "signed": db.PCellParameterDeclaration.TypeString,
                 "choice": db.PCellParameterDeclaration.TypeString,
                 "numlist": db.PCellParameterDeclaration.TypeString}
        for pdk in SUPPORTED_PDKS:
            man = Manifest.load(shipped_manifest(pdk))
            for spec in man.devices:
                pc = make_pcell(spec, St)
                decls = pc.get_parameters()
                # Devices also keep the form of Magic's dialog; box-paint
                # generators have no dialog.
                hidden = ["kmp_created"] + (["kmp_dialog"] if spec.kind != "box" else [])
                self.assertEqual([d.name for d in decls], [p.name for p in spec.params] + hidden)
                for d, p in zip(decls, spec.params):
                    self.assertEqual(d.type, types[p.type], (pdk, spec.name, p.name))
                    self.assertEqual(d.default, p.default_value())
                    if p.type == "choice":
                        self.assertEqual([c[1] if isinstance(c, (list, tuple)) else c
                                          for c in d.choice_values()], p.choices)
                tail = decls[len(spec.params):]
                self.assertTrue(all(d.hidden for d in tail))
                self.assertEqual(tail[0].default, St.created_stamp)
                if spec.kind != "box":
                    self.assertEqual((tail[1].type, tail[1].default),
                                     (db.PCellParameterDeclaration.TypeString, ""))

    def test_classes_are_not_shared(self):
        from klayout_magic_pcells.config import SHIPPED_MANIFEST
        from klayout_magic_pcells.manifest import Manifest
        from klayout_magic_pcells.pcell import make_pcell

        class St:
            created_stamp = ""
            generator = None
            library_name = "test_magic"

        man = Manifest.load(SHIPPED_MANIFEST)
        a = make_pcell(man["sky130_fd_pr__nfet_01v8"], St)
        b = make_pcell(man["sky130_fd_pr__cap_mim_m3_1"], St)
        self.assertIsNot(type(a), type(b))
        self.assertFalse(hasattr(type(b), "nf"))


if __name__ == "__main__":
    unittest.main()
