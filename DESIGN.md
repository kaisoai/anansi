# anansi — Technical Design

## Overview

anansi is an intelligent context gatherer. It crawls structured sources (GitHub issues, repos) and interviews human experts to produce comprehensive context for downstream evaluation.

The core insight: evaluation quality is bounded by context quality. Same model, same prompts, radically different outcomes based on how much context flows in. anansi's job is to make context complete.

## Architecture

```
                     anansi
                       │
           ┌───────────┼───────────┐
           │                       │
    ┌──────▼───────┐       ┌──────▼───────┐
    │   gather     │       │  interview   │
    │              │       │              │
    │ URI routing  │       │ Reads context│
    │ → handler    │       │ Identifies   │
    │ → files +    │       │ gaps, asks   │
    │   manifest   │       │ targeted Qs  │
    └──────┬───────┘       └──────┬───────┘
           │                      │
           ▼                      ▼
    ┌─────────────────────────────────────┐
    │          context/                    │
    │  manifest.json  ← provenance        │
    │  issue.md       ← automated         │
    │  comments.md    ← automated         │
    │  interview.md   ← expert            │
    └─────────────────────────────────────┘
```

## Gather: URI-Routed Source Handlers

`anansi gather <uri>` routes to a source handler based on URI prefix.

```
github:Expensify/App#15193  → _gather_github_issue()
repo:kaisoai/irie           → _gather_repo()
```

Shorthand: `Expensify/App#15193` (has `#`, inferred as GitHub issue). `kaisoai/irie` (no `#`, inferred as repo).

### Adding New Sources

New sources are a function added to `SOURCE_HANDLERS`:

```python
SOURCE_HANDLERS = {
    "github": _gather_github_issue,
    "repo": _gather_repo,
    # Future:
    # "slack": _gather_slack_thread,
    # "jira": _gather_jira_ticket,
    # "gdoc": _gather_google_doc,
}
```

Each handler receives `(ref, output_dir, manifest)` and produces markdown files + manifest entries. The handler owns the source-specific logic (API calls, pagination, formatting). The manifest format is universal.

Future sources will use MCP servers under the hood — anansi routes the URI, the MCP server handles the API. anansi owns the intelligence (what to fetch, what to follow). MCP servers own the connectors.

### GitHub Issue Handler

Fetches:
1. **Issue body** — title, state, labels, full description
2. **All comments** — paginated, no truncation, no character limit
3. **Linked PRs** — via timeline events (cross-references)

Design principle: never truncate. GitHub issues can have 100+ comments with 50K+ characters. The signal often lives in reviewer feedback buried deep in the thread. Truncation destroys exactly the context that matters most.

### GitHub Repo Handler

Fetches:
1. **README** — raw content
2. **Repo metadata** — description, language, stars, topics
3. **File tree** — recursive listing (first 200 entries)

## Interview: Agent-Driven Expert Q&A

`anansi interview -o context/` runs a multi-turn conversation between an AI agent and a human expert.

### How It Works

```
1. Agent reads ALL existing context in the directory
   (issue.md, comments.md, etc. — whatever gather produced)

2. Agent identifies gaps, contradictions, missing domain knowledge

3. Agent asks ONE focused question at a time
   - References specific context: "Comment #7 says X, but comment #12 says Y..."
   - Asks about gaps: "The issue mentions rate limiting but none of the proposals address it..."

4. Expert answers naturally

5. Agent incorporates answer, asks next question

6. When expert says 'done', agent summarizes what it learned

7. Transcript saved as interview_NNN.md with expert provenance
```

### Why First-Class?

Existing MCP "ask human" tools handle "ask a question, get an answer." anansi's interview agent does something harder: it reads 60K chars of existing context, identifies what's missing, and asks TARGETED questions. The intelligence is in knowing what to ask, not in the asking mechanism.

## Manifest: Provenance Tracking

Every context file gets an entry in `manifest.json`:

```json
{
  "version": 1,
  "entries": [
    {
      "file": "comments.md",
      "source": {
        "type": "automated",
        "id": "github:Expensify/App#15193",
        "timestamp": "2026-05-17T16:28:42Z",
        "elo": null,
        "history": null
      },
      "summary": "Discussion: 108 comments",
      "tags": ["github", "comments"],
      "persist": false
    }
  ]
}
```

### Source Fields

| Field | Purpose |
|---|---|
| `type` | "automated", "expert", "requester", "agent" |
| `id` | Who/what: "github:org/repo#N", "expert:dennis" |
| `timestamp` | When gathered |
| `elo` | Bradley-Terry rating if known (for expert sources) |
| `history` | Number of past contributions if known |

### Design: Provenance, Not Trust Scores

The manifest provides raw metadata. It does NOT assign trust scores or weights. The downstream rubric generator or evaluation model sees the provenance and decides how to weight each source. An expert with elo=1800 and history=50 is implicitly more trustworthy than an automated crawl, but that's the model's judgment to make, not anansi's.

### Persistence Flag

`persist: true` means this context is intended for reuse across tasks of the same type. `persist: false` means one-time, task-specific context. This distinction matters for marketplace economics — persistent context contributions have different value than one-time corrections.

## Module Structure

```
anansi/
├── anansi.py      — CLI + gather URI routing + source handlers
├── interview.py   — expert interview agent (multi-turn conversation)
├── manifest.py    — provenance dataclasses + JSON serialization
└── tests/
    └── test_manifest.py — manifest unit tests
```

### Dependencies

- **Anthropic SDK** — LLM calls for interview agent
- **gh CLI** — GitHub API access (authenticated via local gh auth)

No web framework. No database. Files in, files out.

## Design Decisions

**Why URI routing?** Source handlers are just functions. Adding Slack support is adding one function and one entry in `SOURCE_HANDLERS`. No plugin framework, no config files, no abstractions. When MCP servers are needed, the handler function calls the MCP server instead of `gh api`.

**Why never truncate?** We tested on SWE-Lancer. Same task, same model: 40% accuracy with truncated context, 60% with full context. A reviewer's comment at character 8,001 said "proposal #1 was tested and doesn't work" — that single sentence was the signal that determined the correct answer.

**Why interview as a separate command?** The interview agent has a fundamentally different interaction model than automated gathering. `gather` is fire-and-forget (crawl, save, done). `interview` is a multi-turn conversation that requires human presence. They share the output format (context/ + manifest.json) but not the execution model.

**Why not use RAG?** RAG retrieves snippets. anansi gathers complete context. RAG is good for "find the relevant paragraph." anansi is good for "give me everything about this issue so the evaluator can make a fully-informed judgment." Different use cases. anansi produces the corpus that RAG would index.
