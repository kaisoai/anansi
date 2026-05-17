"""Context manifest — provenance tracking for gathered context.

Every context file gets an entry in manifest.json with source metadata.
The rubric generator model sees the manifest and decides how to weight
each source. We don't pre-judge — we provide raw facts.

Format is JSON now, binary proto later.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class Source:
    type: str  # "automated", "expert", "requester", "agent"
    id: str = ""  # who: "anansi:github", "expert:dennis", "requester:acme"
    timestamp: str = ""
    # Raw metadata — model decides how to use it
    elo: int | None = None  # Bradley-Terry rating if known
    history: int | None = None  # number of past contributions if known

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


@dataclass
class ContextEntry:
    file: str  # relative path to content file
    source: Source
    summary: str = ""  # one-line description
    tags: list[str] = field(default_factory=list)
    persist: bool = False  # true = intended for reuse across tasks


@dataclass
class Manifest:
    version: int = 1
    entries: list[ContextEntry] = field(default_factory=list)

    def add(self, file: str, source_type: str, source_id: str = "",
            summary: str = "", tags: list[str] | None = None,
            persist: bool = False, elo: int | None = None) -> ContextEntry:
        """Add a context entry with provenance."""
        entry = ContextEntry(
            file=file,
            source=Source(type=source_type, id=source_id, elo=elo),
            summary=summary,
            tags=tags or [],
            persist=persist,
        )
        self.entries.append(entry)
        return entry

    def save(self, context_dir: Path):
        """Write manifest.json to context directory."""
        path = context_dir / "manifest.json"
        data = {
            "version": self.version,
            "entries": [asdict(e) for e in self.entries],
        }
        path.write_text(json.dumps(data, indent=2))

    @staticmethod
    def load(context_dir: Path) -> "Manifest":
        """Load manifest from context directory. Returns empty if not found."""
        path = context_dir / "manifest.json"
        if not path.exists():
            return Manifest()
        data = json.loads(path.read_text())
        m = Manifest(version=data.get("version", 1))
        for e in data.get("entries", []):
            src = e.get("source", {})
            m.entries.append(ContextEntry(
                file=e["file"],
                source=Source(
                    type=src.get("type", "automated"),
                    id=src.get("id", ""),
                    timestamp=src.get("timestamp", ""),
                    elo=src.get("elo"),
                    history=src.get("history"),
                ),
                summary=e.get("summary", ""),
                tags=e.get("tags", []),
                persist=e.get("persist", False),
            ))
        return m
