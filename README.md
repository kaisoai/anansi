# anansi

Intelligent context gatherer. The spider that collects stories.

**anansi** (West African / Caribbean folklore: the spider trickster who gathered all the world's stories) crawls sources and interviews humans to build complete context. Open source, MIT licensed.

## Quick Start

```bash
# Gather context from a GitHub issue (full thread, never truncates)
anansi gather github:Expensify/App#15193 -o context/

# Gather from a repo
anansi gather repo:kaisoai/irie -o context/

# Interview an expert (reads existing context, asks targeted questions)
anansi interview -o context/
```

## Example: GitHub Issue

```
$ anansi gather github:Expensify/App#15193 -o context/

Gathering from github:Expensify/App#15193
  Gathering Expensify/App#15193
    → issue.md (2,279 chars)
    → comments.md (108 comments, 48,372 chars)
    → linked_prs.md (2 references)

  Total: 3 files, 60,172 chars
```

108 comments. 60K chars. Zero truncation. Because the signal might be in comment #47.

## Example: Expert Interview

```
$ anansi interview -o context/

============================================================
anansi interview — type your answers, 'done' to finish
============================================================

I see this issue involves code blocks showing bold text temporarily
when inside markdown headers. The discussion thread shows 6 proposals
were submitted. I noticed @aimane-chnaif tested proposal #1 and found
it doesn't work for all cases. Can you tell me more about what
specifically failed?

You: The issue is that ExpensiMark parses markdown in different order
     on frontend vs backend. Proposal 1 only fixed headers, not bold
     or italic. Only proposal 4 handled all three...

Saved: interview_001.md (2,950 chars)
```

The agent reads existing context, identifies gaps, asks targeted questions.

## What It Produces

```
context/
├── manifest.json       ← provenance for every file
├── issue.md            ← automated: GitHub issue body
├── comments.md         ← automated: full discussion thread (paginated)
├── linked_prs.md       ← automated: referenced PRs
└── interview_001.md    ← expert: targeted Q&A transcript
```

### Manifest (provenance tracking)

```json
{
  "version": 1,
  "entries": [
    {
      "file": "comments.md",
      "source": {"type": "automated", "id": "github:Expensify/App#15193"},
      "summary": "Discussion: 108 comments",
      "tags": ["github", "comments"]
    },
    {
      "file": "interview_001.md",
      "source": {"type": "expert", "id": "expert:dennis", "elo": 1800},
      "summary": "Expert interview: parsing consistency",
      "tags": ["interview", "expert"]
    }
  ]
}
```

Provenance metadata — source type, ID, elo if known. The rubric generator model sees this and decides how to weight each source. We don't pre-judge.

## Current State

| Feature | Status |
|---|---|
| `gather` — GitHub issues (full thread, paginated) | ✅ Working |
| `gather` — GitHub repos (README, tree, metadata) | ✅ Working |
| `interview` — expert Q&A against existing context | ✅ Working |
| URI routing (github:, repo:) | ✅ Working |
| Manifest provenance tracking | ✅ Working |
| Slack, Google Docs, Jira sources | 🔜 Via MCP servers |
| Agentic link following | 🔜 Planned |

## Design Principles

- **Never truncate.** Chunk if needed. The signal is often in the details.
- **Provenance, not trust scores.** Tag where context came from. Let the model decide.
- **Humans are sources too.** Expert interview = anansi gathering from a human.
- **MCP-ready.** URI routing makes new sources a handler function, not an architecture change.

## Works with irie

anansi produces context. [irie](https://github.com/kaisoai/irie) consumes it.

```bash
anansi gather github:Expensify/App#15193 -o context/
irie check proposal.md context/
```

## Also See

- **[irie](https://github.com/kaisoai/irie)** — verification intelligence (MIT)

## License

MIT. Open source.
