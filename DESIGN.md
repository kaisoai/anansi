# anansi — Technical Design

## Core Thesis

Evaluation quality is bounded by context quality. The same model with the same prompts produces radically different results based on how much context it has. Context gathering is the unglamorous foundation that makes everything else work.

## Two Modes of Gathering

### Automated: Crawl Structured Sources

`anansi gather` routes URIs to source handlers. Each handler knows how to extract complete context from a specific source type.

Design principle: **never truncate.** A GitHub issue might have 108 comments across 48K chars. The reviewer feedback that determines which proposal is correct might be in comment #47. Truncation at any arbitrary limit destroys exactly the context that matters most.

We validated this empirically: same evaluation, same model, 40% accuracy with truncated context vs 60% with full context. The marginal value of "the next 1000 chars" is unpredictable — sometimes it's noise, sometimes it's the signal.

Source handlers are just functions. Adding a new source (Slack, Jira, Google Docs) is adding one function. When MCP servers are available for a source, the handler delegates to them — anansi owns the intelligence (what to fetch, what to follow), MCP servers own the connectors.

### Human: Expert Interviews

`anansi interview` is a multi-turn conversation where an AI agent interviews a human expert. The agent reads ALL existing context first, then asks targeted questions to fill gaps.

This is different from "ask human a question" tools (which exist as MCP servers). The value is in what the agent asks, not the asking mechanism. After reading 60K chars of GitHub discussion, the agent might say: "Comment #3 says approach A was tested and failed, but Comment #12 seems to recommend the same approach — can you clarify what actually happened?" That question requires understanding the context. A generic "do you have anything to add?" doesn't.

Expert interviews are first-class because they capture Polanyi's tacit knowledge — domain expertise that exists in the expert's head but not in any document. "The API changed in v3" is six tokens of knowledge that redirects an entire evaluation. No amount of automated crawling can produce it.

## Provenance

Every context file gets a manifest entry tracking where it came from:

```json
{
  "source": {
    "type": "expert",
    "id": "expert:dennis",
    "elo": 1800,
    "timestamp": "2026-05-17T16:28:42Z"
  }
}
```

Source types: automated (crawlers), expert (human interviews), requester (task poster), agent (AI-generated).

**Provenance, not trust scores.** The manifest provides raw facts — source type, identity, reputation metrics if known. Downstream systems (rubric generators, evaluation models) see the provenance and decide how to weight it. anansi does not pre-judge which sources matter more. An expert with elo 1800 is implicitly more valuable than an automated crawl, but that's the consumer's inference, not anansi's assertion.

This design supports future RBAC requirements — visibility scopes can be added to manifest entries to control which parties see which context, without changing the provenance model.

## Persistence

Context entries are tagged `persist: true` (intended for reuse across tasks of a type) or `persist: false` (one-time, task-specific). This distinction matters for marketplace economics: persistent contributions (rubric criteria, domain rules) have different compounding value than one-time corrections.

## Design Decisions

**Why URI routing, not a plugin framework?** Source handlers are functions in a dict. No registry, no config, no abstraction layer. When there are 20 sources this might need a plugin system. With 2 sources it would be overengineering. The URI prefix (`github:`, `repo:`) is the only convention.

**Why interview as a separate command, not a source type?** Automated gathering is fire-and-forget — crawl, save, done. Expert interviews are multi-turn conversations requiring human presence. They share the output format (context/ + manifest.json) but have fundamentally different execution models. Forcing them into the same `gather` command would require interactive/non-interactive mode switching that adds complexity without value.

**Why not RAG?** RAG retrieves relevant snippets. anansi gathers complete context. RAG answers "find the paragraph about X." anansi answers "give me everything about this issue so the evaluator can make a fully-informed judgment." Different tools for different jobs. anansi produces the corpus that RAG would index.

**Why not just pass URLs to the LLM?** Models with web access can read URLs directly. But they can't paginate through 108 GitHub comments, follow cross-referenced PRs, or interview humans. anansi does structured extraction that LLM web browsing can't replicate — especially the "never truncate" guarantee.

## Research Context

- **Information economics (Stigler 1961, Hayek 1945):** Context gathering has real economic costs and returns. Hayek's "knowledge of particular circumstances of time and place" is exactly what expert interviews capture — distributed, tacit knowledge that can't be centralized.
- **Tacit knowledge (Polanyi 1966):** "We can know more than we can tell." Expert interviews surface knowledge that exists in heads but not in documents.
- **Lost in the Middle (Liu et al. 2023):** Model performance degrades when relevant information is in the middle of long contexts. More context isn't automatically better — but LESS context is reliably worse when it means missing the signal.
- **RLHF as context correction:** Scale AI ($14.8B) is fundamentally a context correction business. Human annotators provide preference signals that correct AI behavior. Expert interviews are the same economic activity applied to evaluation rather than training.
