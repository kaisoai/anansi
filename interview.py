"""anansi interview — agent interviews a human expert to gather context.

Reads existing context (manifest + files), identifies gaps and contradictions,
asks targeted questions, saves answers with provenance.

The interviewer is an agent — it reads what anansi already gathered and
figures out what to ask. The human just talks.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from manifest import Manifest

# Use anthropic SDK directly — same as irie's llm.py pattern
_client = None


def _get_client():
    global _client
    if _client is None:
        import anthropic
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            print("Error: ANTHROPIC_API_KEY not set")
            sys.exit(1)
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def _call(messages: list[dict], model: str = "claude-sonnet-4-20250514") -> str:
    """Multi-turn conversation call."""
    client = _get_client()
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=messages,
    )
    return response.content[0].text


def _load_existing_context(context_dir: Path) -> str:
    """Read all existing context files into a single string."""
    if not context_dir.exists():
        return "(no existing context)"

    parts = []
    manifest = Manifest.load(context_dir)

    for entry in manifest.entries:
        p = context_dir / entry.file
        if p.exists():
            content = p.read_text()
            parts.append(
                f"--- {entry.file} (source: {entry.source.type}:{entry.source.id}) ---\n"
                f"{content[:5000]}"
            )

    # Also read any files not in manifest
    for f in sorted(context_dir.iterdir()):
        if f.is_file() and f.name != "manifest.json" and f.suffix == ".md":
            if not any(e.file == f.name for e in manifest.entries):
                parts.append(f"--- {f.name} (source: unknown) ---\n{f.read_text()[:5000]}")

    return "\n\n".join(parts) if parts else "(no existing context)"


SYSTEM_PROMPT = """You are an expert interviewer gathering context for a task evaluation.

You have access to existing context that was automatically gathered (GitHub issues, comments, docs).
Your job is to interview a human expert to fill gaps, resolve contradictions, and capture domain
knowledge that isn't in the automated context.

Rules:
- Ask ONE focused question at a time
- Reference specific things from the existing context ("I see the issue mentions X — can you clarify...")
- Surface contradictions you notice ("Comment #3 says A but Comment #7 says B — which is correct?")
- When the expert's answer is clear, acknowledge and move to the next gap
- When you have enough context, say DONE and summarize what you learned

Start by briefly stating what you understand from the existing context, then ask your first question."""


def run_interview(context_dir: Path, source_id: str = "expert",
                  model: str = "claude-sonnet-4-20250514") -> list[Path]:
    """Interactive interview loop. Expert types answers, agent asks follow-ups."""
    context_dir.mkdir(parents=True, exist_ok=True)
    manifest = Manifest.load(context_dir)
    existing = _load_existing_context(context_dir)

    messages = [
        {"role": "user", "content": f"Here is the existing context for this task:\n\n{existing}\n\nBegin the interview."}
    ]

    # Get first question from the agent
    response = _call(messages, model)
    messages.append({"role": "assistant", "content": response})

    collected = []  # expert answers collected during interview

    print("\n" + "=" * 60)
    print("anansi interview — type your answers, 'done' to finish")
    print("=" * 60)
    print(f"\n{response}\n")

    while True:
        try:
            answer = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n(interview ended)")
            break

        if not answer:
            continue

        if answer.lower() in ("done", "quit", "exit", "q"):
            # Ask agent to summarize
            messages.append({"role": "user", "content": "The expert is done. Summarize the key context you gathered."})
            summary = _call(messages, model)
            print(f"\n{summary}")
            collected.append(("summary", summary))
            break

        # Send answer to agent, get next question
        messages.append({"role": "user", "content": answer})
        collected.append(("answer", answer))

        response = _call(messages, model)
        messages.append({"role": "assistant", "content": response})

        # Check if agent said DONE
        if "DONE" in response.upper() and len(response) < 500:
            print(f"\n{response}")
            collected.append(("summary", response))
            break

        print(f"\n{response}\n")

    # Save collected context
    if not collected:
        print("No context collected.")
        return []

    files = []

    # Save full interview transcript
    existing_interviews = list(context_dir.glob("interview_*.md"))
    n = len(existing_interviews) + 1
    transcript_name = f"interview_{n:03d}.md"
    transcript = f"# Expert Interview #{n}\n\n"
    for role, content in collected:
        if role == "answer":
            transcript += f"**Expert:** {content}\n\n"
        elif role == "summary":
            transcript += f"**Summary:** {content}\n\n"

    p = context_dir / transcript_name
    p.write_text(transcript)
    files.append(p)

    manifest.add(
        transcript_name, "expert", source_id,
        summary=f"Expert interview #{n}",
        tags=["interview", "expert"],
    )
    manifest.save(context_dir)

    print(f"\nSaved: {transcript_name} ({len(transcript)} chars)")
    return files
