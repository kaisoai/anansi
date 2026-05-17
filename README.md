# anansi

Gather context from anywhere. The spider that collects stories.

**anansi** (West African / Caribbean folklore: the spider trickster who gathered all the world's stories) crawls sources, talks to humans, and produces context files. The context layer for [irie](https://github.com/kaisoai/irie) verification.

## Design principles

- **Never truncate.** The signal might be in comment #47. Chunk if needed, never cut.
- **Gather agentically.** Follow links, read referenced PRs, crawl repo structure.
- **Source provenance.** Tag where context came from — automated sources vs expert input vs requester specs. irie weights accordingly.
- **Humans are sources too.** An expert interview is just anansi gathering context from a human instead of GitHub.

## Usage

```bash
anansi gh Expensify/App#15193 -o context/     # GitHub issue + full thread
anansi repo kaisoai/irie -o context/           # repo structure + key files
```

## What it produces

Markdown files. One per source. Any tool can read them.

```
context/
├── issue.md          # issue body + metadata
├── comments.md       # full discussion thread (paginated, never truncated)
└── linked_prs.md     # related pull requests
```

## Part of the Kaiso universe

- **anansi** gathers the stories (context — automated and human)
- **[irie](https://github.com/kaisoai/irie)** checks the vibes (verification)
- **[susu](https://github.com/kaisoai/susu)** is where work trades hands (marketplace)

Loosely coupled. Markdown files as interface. No code imports between tools.
