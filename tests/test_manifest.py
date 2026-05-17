"""Tests for context manifest and provenance."""

import json
import tempfile
import unittest
from pathlib import Path

from manifest import Manifest, Source, ContextEntry


class TestSource(unittest.TestCase):
    def test_defaults(self):
        s = Source(type="expert", id="dennis")
        self.assertEqual(s.type, "expert")
        self.assertIsNone(s.elo)
        self.assertTrue(len(s.timestamp) > 0)

    def test_with_elo(self):
        s = Source(type="expert", id="dennis", elo=1800)
        self.assertEqual(s.elo, 1800)


class TestManifest(unittest.TestCase):
    def test_add_entry(self):
        m = Manifest()
        m.add("issue.md", "automated", "anansi:github", summary="Issue body")
        self.assertEqual(len(m.entries), 1)
        self.assertEqual(m.entries[0].source.type, "automated")

    def test_add_expert(self):
        m = Manifest()
        m.add("notes.md", "expert", "expert:dennis", elo=1800)
        self.assertEqual(m.entries[0].source.type, "expert")
        self.assertEqual(m.entries[0].source.elo, 1800)

    def test_persist_flag(self):
        m = Manifest()
        m.add("persistent.md", "expert", persist=True)
        m.add("one-time.md", "expert", persist=False)
        self.assertTrue(m.entries[0].persist)
        self.assertFalse(m.entries[1].persist)

    def test_save_and_load(self):
        d = Path(tempfile.mkdtemp())
        m = Manifest()
        m.add("issue.md", "automated", "anansi:github", summary="Issue")
        m.add("expert.md", "expert", "expert:dennis", summary="Notes", elo=1600, persist=True)
        m.save(d)

        loaded = Manifest.load(d)
        self.assertEqual(len(loaded.entries), 2)
        self.assertEqual(loaded.entries[0].source.type, "automated")
        self.assertEqual(loaded.entries[1].source.elo, 1600)
        self.assertTrue(loaded.entries[1].persist)

    def test_load_empty_dir(self):
        d = Path(tempfile.mkdtemp())
        m = Manifest.load(d)
        self.assertEqual(len(m.entries), 0)

    def test_tags(self):
        m = Manifest()
        m.add("issue.md", "automated", tags=["github", "issue"])
        self.assertEqual(m.entries[0].tags, ["github", "issue"])

    def test_roundtrip_json(self):
        d = Path(tempfile.mkdtemp())
        m = Manifest()
        m.add("a.md", "expert", "expert:dan", summary="Note A", tags=["auth"], persist=True, elo=1900)
        m.add("b.md", "automated", "anansi:gh", summary="Note B")
        m.save(d)

        raw = json.loads((d / "manifest.json").read_text())
        self.assertEqual(raw["version"], 1)
        self.assertEqual(len(raw["entries"]), 2)
        self.assertEqual(raw["entries"][0]["source"]["type"], "expert")
        self.assertEqual(raw["entries"][0]["source"]["elo"], 1900)
        self.assertTrue(raw["entries"][0]["persist"])
        self.assertIsNone(raw["entries"][1]["source"]["elo"])


if __name__ == "__main__":
    unittest.main()
