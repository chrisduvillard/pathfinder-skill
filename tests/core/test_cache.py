import json
import tempfile
import unittest
from unittest import mock
from dataclasses import replace
from pathlib import Path

from pathfinder_core.cache import CacheIdentity, DiscoveryCache


HASH = "a" * 64
NOW = "2026-08-10T12:00:00Z"


class DiscoveryCacheTests(unittest.TestCase):
    def identity(self):
        return CacheIdentity("private/repo", "b" * 40, "packages/app", "full-exploration", HASH, HASH)

    def test_hit_does_not_persist_private_identity_or_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = DiscoveryCache(directory)
            identity = self.identity()
            path = cache.store(identity, {"findings": ["one"]}, NOW)
            self.assertEqual(cache.load(identity), {"findings": ["one"]})
            raw = path.read_text()
            self.assertNotIn("private/repo", raw)
            self.assertNotIn("packages/app", raw)

    def test_commit_scope_route_config_and_content_changes_miss(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = DiscoveryCache(directory)
            identity = self.identity()
            cache.store(identity, {"cached": True}, NOW)
            variants = [
                replace(identity, base_commit="c" * 40),
                replace(identity, scoped_root="packages/other"),
                replace(identity, route="prompt-to-goal"),
                replace(identity, config_fingerprint="d" * 64),
                replace(identity, content_fingerprint="e" * 64),
                replace(identity, repository="private/other"),
            ]
            for variant in variants:
                with self.subTest(variant=variant):
                    self.assertIsNone(cache.load(variant))

    def test_stale_schema_is_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = DiscoveryCache(directory)
            identity = self.identity()
            path = cache.store(identity, {"cached": True}, NOW)
            entry = json.loads(path.read_text())
            entry["schema_version"] = 0
            path.write_text(json.dumps(entry))
            self.assertIsNone(cache.load(identity))

    def test_malformed_and_truncated_json_are_quarantined_as_cache_misses(self):
        for raw in ("{", '{"schema_version": 1,'):
            with self.subTest(raw=raw), tempfile.TemporaryDirectory() as directory:
                cache = DiscoveryCache(directory)
                identity = self.identity()
                path = cache._path(identity)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(raw, encoding="utf-8")
                self.assertIsNone(cache.load(identity))
                self.assertFalse(path.exists())
                self.assertTrue(list(Path(directory).glob(".*.invalid-*")))

    def test_invalid_utf8_is_quarantined_as_cache_miss(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = DiscoveryCache(directory)
            identity = self.identity()
            path = cache._path(identity)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"\xff\xfe")
            self.assertIsNone(cache.load(identity))
            self.assertFalse(path.exists())

    def test_cache_read_error_bypasses_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = DiscoveryCache(directory)
            identity = self.identity()
            cache.store(identity, {"cached": True}, NOW)
            with mock.patch("pathlib.Path.read_text", side_effect=OSError("busy")):
                self.assertIsNone(cache.load(identity))


if __name__ == "__main__":
    unittest.main()
