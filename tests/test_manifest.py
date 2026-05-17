"""Tests for context manifest and provenance."""

import json
import tempfile
import unittest
from pathlib import Path

from manifest import Manifest, Source, ContextEntry, DEFAULT_TRUST


class TestSource(unittest.TestCase):
    def test_defaults(self):
        s = Source(type="expert", id="dennis")
        self.assertEqual(s.type, "expert")
        self.assertTrue(len(s.timestamp) > 0)

    def test_trust_by_type(self):
        self.assertEqual(DEFAULT_TRUST["expert"], 0.9)
        self.assertEqual(DEFAULT_TRUST["automated"], 0.5)
        self.assertEqual(DEFAULT_TRUST["requester"], 0.7)
        self.assertEqual(DEFAULT_TRUST["agent"], 0.4)


class TestManifest(unittest.TestCase):
    def test_add_entry(self):
        m = Manifest()
        m.add("issue.md", "automated", "anansi:github", summary="Issue body")
        self.assertEqual(len(m.entries), 1)
        self.assertEqual(m.entries[0].source.type, "automated")
        self.assertEqual(m.entries[0].source.trust, 0.5)

    def test_add_expert_gets_high_trust(self):
        m = Manifest()
        m.add("notes.md", "expert", "expert:dennis")
        self.assertEqual(m.entries[0].source.trust, 0.9)

    def test_custom_trust(self):
        m = Manifest()
        m.add("notes.md", "expert", trust=0.75)
        self.assertEqual(m.entries[0].source.trust, 0.75)

    def test_persist_flag(self):
        m = Manifest()
        m.add("rubric-criterion.md", "expert", persist=True)
        m.add("one-time-note.md", "expert", persist=False)
        self.assertTrue(m.entries[0].persist)
        self.assertFalse(m.entries[1].persist)

    def test_save_and_load(self):
        d = Path(tempfile.mkdtemp())
        m = Manifest()
        m.add("issue.md", "automated", "anansi:github", summary="Issue")
        m.add("expert.md", "expert", "expert:dennis", summary="Expert notes", persist=True)
        m.save(d)

        loaded = Manifest.load(d)
        self.assertEqual(len(loaded.entries), 2)
        self.assertEqual(loaded.entries[0].file, "issue.md")
        self.assertEqual(loaded.entries[0].source.type, "automated")
        self.assertEqual(loaded.entries[1].file, "expert.md")
        self.assertEqual(loaded.entries[1].source.trust, 0.9)
        self.assertTrue(loaded.entries[1].persist)

    def test_load_empty_dir(self):
        d = Path(tempfile.mkdtemp())
        m = Manifest.load(d)
        self.assertEqual(len(m.entries), 0)

    def test_by_trust(self):
        m = Manifest()
        m.add("auto.md", "automated")
        m.add("expert.md", "expert")
        m.add("requester.md", "requester")
        sorted_entries = m.by_trust()
        self.assertEqual(sorted_entries[0].source.type, "expert")
        self.assertEqual(sorted_entries[1].source.type, "requester")
        self.assertEqual(sorted_entries[2].source.type, "automated")

    def test_tags(self):
        m = Manifest()
        m.add("issue.md", "automated", tags=["github", "issue"])
        self.assertEqual(m.entries[0].tags, ["github", "issue"])

    def test_roundtrip_json(self):
        d = Path(tempfile.mkdtemp())
        m = Manifest()
        m.add("a.md", "expert", "expert:dan", summary="Note A", tags=["auth"], persist=True)
        m.add("b.md", "automated", "anansi:gh", summary="Note B")
        m.save(d)

        raw = json.loads((d / "manifest.json").read_text())
        self.assertEqual(raw["version"], 1)
        self.assertEqual(len(raw["entries"]), 2)
        self.assertEqual(raw["entries"][0]["source"]["type"], "expert")
        self.assertTrue(raw["entries"][0]["persist"])


if __name__ == "__main__":
    unittest.main()
