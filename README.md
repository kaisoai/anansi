# anansi

Intelligent context gatherer. The spider that collects stories.

**anansi** (West African / Caribbean folklore: the spider trickster who gathered all the world's stories) crawls sources and interviews humans to build complete context for verification.

## Commands

```bash
# Gather from sources via URI
anansi gather github:Expensify/App#15193 -o context/
anansi gather repo:kaisoai/irie -o context/
anansi gather Expensify/App#15193 -o context/    # shorthand

# Interview an expert (reads existing context, asks targeted questions)
anansi interview -o context/
```

## Design

**`gather`** routes URIs to source handlers. Today: GitHub issues, repos. Tomorrow: Slack, Google Docs, Jira — via MCP servers. Anansi doesn't own the connectors. It owns the intelligence about what to fetch and how to structure it.

**`interview`** reads existing context, identifies gaps and contradictions, asks the expert one question at a time. The expert talks. Anansi structures. Transcript saved with provenance.

**Manifest** tracks provenance for every context file — source type, source ID, elo rating if known. The rubric generator model sees the manifest and decides how to weight each source. We don't pre-judge.

## What it produces

```
context/
├── manifest.json     ← provenance for every file
├── issue.md          ← automated: GitHub issue body
├── comments.md       ← automated: full discussion thread
├── linked_prs.md     ← automated: referenced PRs
└── interview_001.md  ← expert: targeted Q&A transcript
```

## Principles

- **Never truncate.** The signal might be in comment #47.
- **Gather agentically.** Follow links, read referenced docs.
- **Provenance, not trust scores.** Tag where context came from. Let the model decide what matters.
- **Humans are sources too.** An expert interview is anansi gathering from a human.

## License

MIT. Open source.

## Part of the Kaiso universe

- **anansi** gathers the stories
- **[irie](https://github.com/kaisoai/irie)** checks the vibes
- **[susu](https://github.com/kaisoai/susu)** is where work trades hands
