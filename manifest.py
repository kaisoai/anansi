"""Context manifest — provenance tracking for gathered context.

Every context file gets an entry in manifest.json with source type,
trust level, and metadata. irie reads the manifest to weight context
by source trust during evaluation.

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
    trust: float = 0.5  # 0.0-1.0, irie uses this for weighting
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# Default trust levels by source type
DEFAULT_TRUST = {
    "expert": 0.9,
    "requester": 0.7,
    "automated": 0.5,
    "agent": 0.4,
}


@dataclass
class ContextEntry:
    file: str  # relative path to content file
    source: Source
    summary: str = ""  # one-line description
    tags: list[str] = field(default_factory=list)
    persist: bool = False  # true = rubric-level, false = task-level


@dataclass
class Manifest:
    version: int = 1
    entries: list[ContextEntry] = field(default_factory=list)

    def add(self, file: str, source_type: str, source_id: str = "",
            summary: str = "", tags: list[str] | None = None,
            trust: float | None = None, persist: bool = False) -> ContextEntry:
        """Add a context entry with provenance."""
        if trust is None:
            trust = DEFAULT_TRUST.get(source_type, 0.5)
        entry = ContextEntry(
            file=file,
            source=Source(type=source_type, id=source_id, trust=trust),
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
                    trust=src.get("trust", 0.5),
                    timestamp=src.get("timestamp", ""),
                ),
                summary=e.get("summary", ""),
                tags=e.get("tags", []),
                persist=e.get("persist", False),
            ))
        return m

    def by_trust(self) -> list[ContextEntry]:
        """Entries sorted by trust (highest first)."""
        return sorted(self.entries, key=lambda e: e.source.trust, reverse=True)
