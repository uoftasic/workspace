import json
import os
import tempfile
import unittest

from tests.unit._util import REPO  # noqa: F401
from klayout_magic_pcells.cache import CacheError, GdsCache, cache_key, versions_digest, versions_fields


class V:
    magic, open_pdks, tech, code, techfile = "8.3.681", "026824c7", "1.0.588-56-g026824c", "c" * 64, "t" * 64


FIELDS = versions_fields(V, "sky130A")


def fake_gds(path, data=b"GDS"):
    with open(path, "wb") as f:
        f.write(data)
    return path


class Keys(unittest.TestCase):
    def test_key_is_stable_and_order_free(self):
        a = cache_key(FIELDS, "dev", "cell", {"w": "1.5", "l": "0.5"})
        b = cache_key(dict(reversed(list(FIELDS.items()))), "dev", "cell", {"l": "0.5", "w": "1.5"})
        self.assertEqual(a, b)
        self.assertEqual(len(a), 64)

    def test_key_changes(self):
        base = cache_key(FIELDS, "dev", "cell", {"w": "1.5"})
        self.assertNotEqual(base, cache_key(FIELDS, "dev", "cell", {"w": "1.50"}))  # raw strings
        self.assertNotEqual(base, cache_key(FIELDS, "dev2", "cell", {"w": "1.5"}))
        self.assertNotEqual(base, cache_key(FIELDS, "dev", "wrapper", {"w": "1.5"}))
        for k in ("magic", "open_pdks", "tech", "code", "techfile", "pdk"):
            f = dict(FIELDS)
            f[k] = "other"
            self.assertNotEqual(base, cache_key(f, "dev", "cell", {"w": "1.5"}), k)

    def test_versions_digest_ignores_requests(self):
        self.assertEqual(versions_digest(FIELDS), versions_digest(dict(FIELDS)))
        f = dict(FIELDS, magic="8.3.700")
        self.assertNotEqual(versions_digest(FIELDS), versions_digest(f))


class Store(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.c = GdsCache(self.root, FIELDS, validate=lambda p: ["TOP"])

    def test_store_and_lookup(self):
        key = self.c.key("dev", "cell", {"w": "1"})
        self.assertIsNone(self.c.lookup(key, "dev"))
        tmp = fake_gds(self.c.tmp_path(key))
        gds = self.c.store(key, "dev", tmp, {"key": key, "checked": {"w": "1"}})
        self.assertFalse(os.path.exists(tmp))
        self.assertTrue(gds.startswith(os.path.join(self.root, "v1", self.c.vdigest, "dev")))
        path, side = self.c.lookup(key, "dev")
        self.assertEqual(path, gds)
        self.assertEqual(side["checked"], {"w": "1"})

    def test_gds_without_sidecar_is_a_miss(self):
        key = self.c.key("dev", "cell", {})
        gds, side = self.c.paths(key, "dev")
        os.makedirs(os.path.dirname(gds))
        fake_gds(gds)
        self.assertIsNone(self.c.lookup(key, "dev"))
        with open(side, "w") as f:
            f.write("{not json")
        self.assertIsNone(self.c.lookup(key, "dev"))
        with open(side, "w") as f:
            json.dump({"key": "someone else"}, f)
        self.assertIsNone(self.c.lookup(key, "dev"))

    def test_validation(self):
        c = GdsCache(self.root, FIELDS, validate=lambda p: ["A", "B"])
        key = c.key("dev", "cell", {})
        with self.assertRaises(CacheError):
            c.store(key, "dev", fake_gds(c.tmp_path(key)), {"key": key})
        with self.assertRaises(CacheError):
            c.store(key, "dev", fake_gds(c.tmp_path(key), b""), {"key": key})
        self.assertIsNone(c.lookup(key, "dev"))

    def test_sidecar_records_the_digest_of_the_stored_gds(self):
        key = self.c.key("dev", "cell", {})
        gds = self.c.store(key, "dev", fake_gds(self.c.tmp_path(key), b"GDS bytes"), {"key": key})
        side = self.c.lookup(key, "dev")[1]
        import hashlib
        self.assertEqual(side["gds_sha256"], hashlib.sha256(b"GDS bytes").hexdigest())
        self.assertEqual(side["device"], "dev")
        self.assertTrue(os.path.isfile(gds))

    def test_a_damaged_or_swapped_gds_is_a_miss_and_is_deleted(self):
        a = self.c.key("dev", "cell", {"w": "1"})
        b = self.c.key("dev", "cell", {"w": "2"})
        ga = self.c.store(a, "dev", fake_gds(self.c.tmp_path(a), b"AAAA"), {"key": a})
        gb = self.c.store(b, "dev", fake_gds(self.c.tmp_path(b), b"BBBB"), {"key": b})
        for damage in (b"", b"AA", b"garbage!", b"BBBB"):   # emptied, truncated, overwritten, other entry
            self.c.store(a, "dev", fake_gds(self.c.tmp_path(a), b"AAAA"), {"key": a})
            with open(ga, "wb") as f:
                f.write(damage)
            self.assertIsNone(self.c.lookup(a, "dev"), damage)
            self.assertFalse(os.path.exists(ga), damage)
            self.assertFalse(os.path.exists(self.c.paths(a, "dev")[1]), damage)
        self.assertIsNotNone(self.c.lookup(b, "dev"))
        self.assertTrue(os.path.exists(gb))

    def test_a_sidecar_without_a_digest_or_for_another_device_is_a_miss(self):
        key = self.c.key("dev", "cell", {})
        gds, side = self.c.paths(key, "dev")
        os.makedirs(os.path.dirname(gds))
        fake_gds(gds)
        import hashlib
        for sidecar in ({"key": key, "device": "dev"},
                        {"key": key, "device": "other", "gds_sha256": hashlib.sha256(b"GDS").hexdigest()}):
            fake_gds(gds)
            with open(side, "w") as f:
                json.dump(sidecar, f)
            self.assertIsNone(self.c.lookup(key, "dev"), sidecar)

    def test_no_temp_files_left(self):
        key = self.c.key("dev", "cell", {})
        self.c.store(key, "dev", fake_gds(self.c.tmp_path(key)), {"key": key})
        d = os.path.dirname(self.c.paths(key, "dev")[0])
        self.assertEqual(sorted(os.listdir(d)), [key[:24] + ".gds", key[:24] + ".json"])

    def test_prune_and_clear(self):
        key = self.c.key("dev", "cell", {})
        self.c.store(key, "dev", fake_gds(self.c.tmp_path(key)), {"key": key})
        old = GdsCache(self.root, dict(FIELDS, magic="8.3.600"), validate=lambda p: ["T"])
        k2 = old.key("dev", "cell", {})
        old.store(k2, "dev", fake_gds(old.tmp_path(k2)), {"key": k2})
        self.assertEqual(len(self.c.version_dirs()), 2)
        removed, other = self.c.prune()
        self.assertEqual([os.path.basename(d) for d in removed], [old.vdigest])
        self.assertEqual(other, {})
        self.assertIsNotNone(self.c.lookup(key, "dev"))
        self.c.clear()
        self.assertEqual(self.c.version_dirs(), [])

    def test_prune_leaves_the_pdks_it_does_not_work_on(self):
        # The testers' case: a cache with entries of four PDKs, pruned with
        # KMP_PDKS set to one of them, deleted the other three's current
        # directories. Only the named PDKs' old directories may go.
        def store(fields, sidecar_versions=None, marker=True):
            c = GdsCache(self.root, fields, validate=lambda p: ["T"])
            k = c.key("dev", "cell", {})
            side = {"key": k}
            if sidecar_versions:
                side["versions"] = sidecar_versions
            c.store(k, "dev", fake_gds(c.tmp_path(k)), side)
            if not marker:
                os.remove(os.path.join(c.base, "versions.json"))
            return c
        sky_old = store(dict(FIELDS, magic="8.3.600"))
        gf = store(versions_fields(V, "gf180mcuD"))
        gf_old = store(dict(versions_fields(V, "gf180mcuD"), magic="8.3.600"))
        # A directory written before versions.json existed: its sidecar names the PDK.
        ihp = store(versions_fields(V, "ihp-sg13g2"), {"pdk": "ihp-sg13g2"}, marker=False)
        empty = os.path.join(self.root, "v1", "000000000000")
        os.makedirs(empty)
        key = self.c.key("dev", "cell", {})
        self.c.store(key, "dev", fake_gds(self.c.tmp_path(key)), {"key": key})
        self.assertEqual(GdsCache.pdk_of(ihp.base), "ihp-sg13g2")
        self.assertEqual(GdsCache.pdk_of(gf.base), "gf180mcuD")
        removed, other = self.c.prune(current={"sky130A": self.c.vdigest})
        self.assertEqual(sorted(removed), sorted([sky_old.base, empty]))
        self.assertEqual(other, {gf.base: "gf180mcuD", gf_old.base: "gf180mcuD", ihp.base: "ihp-sg13g2"})
        removed, other = self.c.prune(current={"sky130A": self.c.vdigest, "gf180mcuD": gf.vdigest})
        self.assertEqual(removed, [gf_old.base])
        self.assertEqual(other, {ihp.base: "ihp-sg13g2"})
        self.assertEqual(self.c.stats()["pdk_of"][os.path.basename(ihp.base)], "ihp-sg13g2")

    def test_the_cache_survives_prune_clear_and_removal_under_a_session(self):
        # Another process's "cache clear" or "cache prune", or rm -rf of the
        # cache directory, while this session holds a GdsCache: its next
        # store must still work (tmp and the versions directory come back).
        import shutil
        for how in ("clear", "prune", "rmtree"):
            key = self.c.key("dev", "cell", {"how": how})
            if how == "clear":
                GdsCache(self.root, {}, validate=None).clear()
            elif how == "prune":
                GdsCache(self.root, dict(FIELDS, magic="other"), validate=None).prune()
            else:
                shutil.rmtree(self.root)
            tmp = fake_gds(self.c.tmp_path(key))
            gds = self.c.store(key, "dev", tmp, {"key": key})
            self.assertTrue(os.path.isfile(gds), how)
            self.assertIsNotNone(self.c.lookup(key, "dev"), how)

    def test_prune_keeps_tmp_and_young_files_in_it(self):
        key = self.c.key("dev", "cell", {})
        young = fake_gds(self.c.tmp_path(key))
        stale = fake_gds(os.path.join(self.c.tmp_dir, "x.1.gds"))
        os.utime(stale, (1, 1))
        self.c.prune()
        self.assertTrue(os.path.isfile(young))
        self.assertFalse(os.path.exists(stale))
        self.c.clear()
        self.assertTrue(os.path.isfile(young))

    def test_disabled_cache_keeps_nothing_between_sessions(self):
        c = GdsCache(self.root, FIELDS, enabled=False, validate=lambda p: ["T"])
        key = c.key("dev", "cell", {})
        c.store(key, "dev", fake_gds(c.tmp_path(key)), {"key": key})
        self.assertIsNone(c.lookup(key, "dev"))
        self.assertFalse(os.path.isdir(os.path.join(self.root, "v1")))
        base = c.base
        self.assertTrue(os.path.isdir(base))
        c.close()   # also registered with atexit
        self.assertFalse(os.path.exists(base))

    def test_format_is_in_the_versions_digest(self):
        from klayout_magic_pcells import cache
        self.assertEqual(FIELDS["format"], cache.FORMAT)
        self.assertGreaterEqual(cache.FORMAT, 2)  # entries before gds_sha256 must not be read


if __name__ == "__main__":
    unittest.main()
