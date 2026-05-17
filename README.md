# anansi

Gather context from anywhere. The spider that collects stories.

**anansi** (West African / Caribbean folklore: the spider trickster who gathered all the world's stories) crawls sources and produces context files that [irie](https://github.com/kaisoai/irie) consumes for verification.

## Usage

```bash
# Gather context from a GitHub issue
anansi gh Expensify/App#15193 -o context/

# Then verify with irie
irie check proposal.md context/

# Gather a repo's key files
anansi repo https://github.com/kaisoai/irie -o context/
```

## Design principles

- **Never truncate.** If context is too long for one prompt, chunk and patch across calls. Truncation kills signal — a reviewer comment at position 8001 might be the one that matters.
- **Gather agentically.** Don't just fetch the issue body. Follow links, read referenced PRs, get the discussion thread. Context is everything.
- **Produce files, not prompts.** anansi outputs markdown. What to do with it is irie's job.

## What it produces

Markdown files. One per source. irie reads them as context.

```
context/
├── issue.md          # issue body + metadata
├── comments.md       # discussion thread
├── linked_prs.md     # related pull requests
└── repo_context.md   # relevant source files
```

## Plugins

| Source | Command | Status |
|---|---|---|
| GitHub issue | `anansi gh owner/repo#123` | Working |
| GitHub repo | `anansi repo URL` | Planned |
| Slack thread | `anansi slack channel/thread` | Future |
| Jira ticket | `anansi jira PROJECT-123` | Future |
| URL | `anansi url https://...` | Future |

## Part of the Kaiso universe

- **anansi** gathers the stories
- **irie** checks the vibes
- **[kaiso](https://kaiso.ai)** runs the marketplace
