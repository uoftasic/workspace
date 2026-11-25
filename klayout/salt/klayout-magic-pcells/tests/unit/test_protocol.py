import json
import unittest

from tests.unit._util import REPO  # noqa: F401
from klayout_magic_pcells import protocol
from klayout_magic_pcells.protocol import ProtocolError, ReplyParser, encode_request, tcl_word


def hx(s):
    return s.encode("utf-8").hex()


class Requests(unittest.TestCase):
    def test_request_is_one_line_of_hex_json(self):
        line = encode_request(7, {"op": "generate", "params": {"w": "x{y", "l": "0.5\n"}})
        self.assertTrue(line.endswith("\n"))
        self.assertEqual(line.count("\n"), 1)
        head, rid, payload = line.strip().split(" ")
        self.assertEqual((head, rid), ("kmp::req", "7"))
        self.assertTrue(all(c in "0123456789abcdef" for c in payload))
        obj = json.loads(bytes.fromhex(payload).decode("utf-8"))
        self.assertEqual(obj["params"]["w"], "x{y")
        # No Tcl-special character can reach the command line itself.
        for ch in "{}[]$\\\"":
            self.assertNotIn(ch, line)

    def test_tcl_word(self):
        self.assertEqual(tcl_word("/a b/{c}$d"), "/a\\ b/\\{c\\}\\$d")


class Replies(unittest.TestCase):
    def feed_all(self, lines):
        p = ReplyParser()
        out = []
        for ln in lines:
            out.append(p.feed(ln))
        return out

    def test_full_reply(self):
        res = self.feed_all([
            "Loading sky130A Device Generator Menu ...",
            "KMP_READY 1",
            "KMP_BEGIN 3",
            "KMP_KV 3 rc " + hx("0"),
            "KMP_KV 3 log ",
            "KMP_KV 3 cell " + hx("sky130_fd_pr__nfet_01v8_8KDQ7Y"),
            "Creating new cell",
            "KMP_PARAM 3 %s %s" % (hx("w"), hx("1.5")),
            "KMP_PARAM 3 %s %s" % (hx("compatible"), hx("a b {c}")),
            "KMP_END 3",
        ])
        self.assertEqual(res[0], ("other", "Loading sky130A Device Generator Menu ..."))
        self.assertEqual(res[1], ("ready", "1"))
        kind, rep = res[-1]
        self.assertEqual(kind, "reply")
        self.assertTrue(rep.ok)
        self.assertEqual(rep.log, "")
        self.assertEqual(rep.kv["cell"], "sky130_fd_pr__nfet_01v8_8KDQ7Y")
        self.assertEqual(list(rep.params), ["w", "compatible"])
        self.assertEqual(rep.params["compatible"], "a b {c}")

    def test_error_reply(self):
        kind, rep = self.feed_all(["KMP_BEGIN 1", "KMP_KV 1 rc " + hx("1"),
                                   "KMP_KV 1 error " + hx("unknown device"), "KMP_END 1"])[-1]
        self.assertFalse(rep.ok)
        self.assertEqual(rep.error, "unknown device")

    def test_framing_errors(self):
        p = ReplyParser()
        with self.assertRaises(ProtocolError):
            p.feed("KMP_KV 9 rc 30")  # no KMP_BEGIN
        p.feed("KMP_BEGIN 2")
        with self.assertRaises(ProtocolError):
            p.feed("KMP_KV 2 rc zz")  # not hex
        with self.assertRaises(ProtocolError):
            p.feed("KMP_BEGIN x")
        with self.assertRaises(ProtocolError):
            p.feed("KMP_WHAT 2")

    def test_protocol_version(self):
        self.assertEqual(protocol.PROTOCOL, 1)


class Messages(unittest.TestCase):
    def test_a_draw_error_comes_before_gencell_creates_own(self):
        # ihp-sg13g2 diodevdd_2kv with its layout script missing: Magic's
        # gencell_create prints the _draw error as a Tcl options dump, then
        # fails on instname. The marker is cut at 400 characters, so the
        # cause has to come first.
        from klayout_magic_pcells.backend import failure_text
        log = ("-code 1 -level 0 -errorstack {INNER {invokeStk1 source /p/diodevdd_2kv.tcl} CALL {x}} "
               "-errorcode {POSIX ENOENT {no such file or directory}} -errorinfo {couldn't read file "
               "\"/p/diodevdd_2kv.tcl\": no such file or directory\n    while executing\n"
               "\"source ${sg13g2::script_path}/diodevdd_2kv.tcl\"\n"
               "    (procedure \"sg13g2::diodevdd_2kv_generate\" line 14)\n    invoked from within\n"
               "\"${library}::${gencell_type}_draw $parameters\"} -errorline 1\n")
        text = failure_text("diodevdd_2kv", "can't read \"instname\": no such variable", log)
        self.assertTrue(text.startswith("diodevdd_2kv: couldn't read file \"/p/diodevdd_2kv.tcl\": "
                                        "no such file or directory"), text)
        self.assertNotIn("-errorstack", text)
        self.assertNotIn("while executing", text)
        # Any other error keeps its place, with Magic's messages after it.
        text = failure_text("nfet", "stopped after Magic printed \"x\" 10000 times", "a\na\nb\n")
        self.assertEqual(text, "nfet: stopped after Magic printed \"x\" 10000 times\na\nb")

    def test_a_sub_second_timeout_is_not_0_s(self):
        import queue
        from klayout_magic_pcells.backend import MagicServer, _Transient
        s = MagicServer.__new__(MagicServer)
        s._lines = queue.Queue()
        s._trace = None
        with self.assertRaises(_Transient) as cm:
            s._get_line(0, 0.08)
        self.assertIn("timed out after 0.08 s", str(cm.exception))

    def test_box_sides_follow_the_message(self):
        from klayout_magic_pcells.pcell import box_sides
        self.assertEqual(box_sides("Via1 width must be at least 0.26um"), ["w"])
        self.assertEqual(box_sides("MV N-well region height must be at least 0.26um"), ["h"])
        self.assertEqual(box_sides("Unrecognized layer: subdiffc"), ["w", "h"])

    def test_cli_refuses_a_value_it_cannot_parse(self):
        import contextlib
        import io
        from klayout_magic_pcells.__main__ import _kv
        from klayout_magic_pcells.config import shipped_manifest
        from klayout_magic_pcells.manifest import Manifest
        man = Manifest.load(shipped_manifest("ihp-sg13g2"))
        for dev, item in (("inductor3", "turns=2.5"), ("sg13_lv_nmos", "ng=1.5"), ("rsil", "w=abc")):
            err = io.StringIO()
            with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as cm:
                _kv([item], man[dev])
            self.assertEqual(cm.exception.code, 2, item)
            self.assertIn("error: ", err.getvalue())
        self.assertEqual(_kv(["turns=3"], man["inductor3"]), {"turns": 3})


if __name__ == "__main__":
    unittest.main()
