#!/usr/bin/env python3
"""anansi — agentic context gatherer.

Crawls sources, gathers context, produces markdown files.
Never truncates. Chunk if needed. Follow links. Be thorough.

Usage:
  anansi gh owner/repo#123 -o context/     # GitHub issue + full thread
  anansi repo owner/repo -o context/       # repo structure + key files
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from manifest import Manifest


def gh_issue(issue_ref: str, output_dir: Path) -> list[Path]:
    """Gather full context from a GitHub issue.

    Fetches: issue body, ALL comments (no truncation), linked PRs, labels, timeline.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = Manifest.load(output_dir)
    files = []

    # Parse owner/repo#number
    match = re.match(r"([^/]+)/([^#]+)#(\d+)", issue_ref)
    if not match:
        match = re.search(r"github\.com/([^/]+)/([^/]+)/issues/(\d+)", issue_ref)
    if not match:
        print(f"Error: can't parse '{issue_ref}'. Use owner/repo#123 format.")
        sys.exit(1)

    owner, repo, number = match.groups()
    api_base = f"repos/{owner}/{repo}/issues/{number}"
    source_id = f"anansi:github:{owner}/{repo}#{number}"

    print(f"Gathering context for {owner}/{repo}#{number}")

    # 1. Issue body + metadata
    print("  Fetching issue...")
    issue = _gh_api(api_base)
    if issue:
        issue_md = f"# {issue.get('title', 'Untitled')}\n\n"
        issue_md += f"**State:** {issue.get('state', '?')} | "
        issue_md += f"**Labels:** {', '.join(l.get('name', '') for l in issue.get('labels', []))} | "
        issue_md += f"**Created:** {issue.get('created_at', '?')[:10]}\n\n"
        issue_md += issue.get("body", "") or "(no body)"
        p = output_dir / "issue.md"
        p.write_text(issue_md)
        files.append(p)
        manifest.add("issue.md", "automated", source_id,
                      summary=f"Issue body: {issue.get('title', '')[:80]}",
                      tags=["github", "issue"])
        print(f"    → issue.md ({len(issue_md)} chars)")

    # 2. ALL comments — paginated, no truncation
    print("  Fetching comments...")
    comments = _gh_api_paginated(f"{api_base}/comments")
    if comments:
        comments_md = f"# Discussion Thread — {owner}/{repo}#{number}\n\n"
        comments_md += f"{len(comments)} comments\n\n"
        for c in comments:
            user = c.get("user", {}).get("login", "?")
            date = c.get("created_at", "?")[:10]
            body = c.get("body", "")
            comments_md += f"---\n**{user}** ({date}):\n\n{body}\n\n"
        p = output_dir / "comments.md"
        p.write_text(comments_md)
        files.append(p)
        manifest.add("comments.md", "automated", source_id,
                      summary=f"Discussion thread: {len(comments)} comments",
                      tags=["github", "comments", "thread"])
        print(f"    → comments.md ({len(comments)} comments, {len(comments_md)} chars)")

    # 3. Linked PRs (from timeline events)
    print("  Fetching timeline/linked PRs...")
    timeline = _gh_api_paginated(f"{api_base}/timeline")
    prs = set()
    if timeline:
        for event in timeline:
            # Cross-referenced PRs
            if event.get("event") == "cross-referenced":
                source = event.get("source", {}).get("issue", {})
                if source.get("pull_request"):
                    prs.add(source.get("number"))
            # Direct references
            if event.get("event") == "referenced":
                commit = event.get("commit_id", "")
                if commit:
                    prs.add(f"commit:{commit[:8]}")

    if prs:
        pr_md = f"# Linked PRs and Commits\n\n"
        for pr in sorted(prs, key=str):
            if isinstance(pr, int):
                pr_data = _gh_api(f"repos/{owner}/{repo}/pulls/{pr}")
                if pr_data:
                    pr_md += f"## PR #{pr}: {pr_data.get('title', '?')}\n"
                    pr_md += f"**State:** {pr_data.get('state', '?')} | **Merged:** {pr_data.get('merged', False)}\n\n"
                    pr_md += (pr_data.get("body", "") or "(no body)") + "\n\n"
            else:
                pr_md += f"- Referenced: {pr}\n"
        p = output_dir / "linked_prs.md"
        p.write_text(pr_md)
        files.append(p)
        manifest.add("linked_prs.md", "automated", source_id,
                      summary=f"Linked PRs and commits: {len(prs)} references",
                      tags=["github", "prs"])
        print(f"    → linked_prs.md ({len(prs)} references)")

    # Save manifest + summary
    manifest.save(output_dir)
    total_chars = sum(f.stat().st_size for f in files)
    print(f"\n  Total: {len(files)} files, {total_chars:,} chars (manifest.json written)")
    return files


def gh_repo(repo_ref: str, output_dir: Path) -> list[Path]:
    """Gather context from a GitHub repo — README, structure, key files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    files = []

    # Parse owner/repo
    match = re.match(r"([^/]+)/([^/]+)", repo_ref.rstrip("/"))
    if not match:
        match = re.search(r"github\.com/([^/]+)/([^/]+)", repo_ref)
    if not match:
        print(f"Error: can't parse '{repo_ref}'.")
        sys.exit(1)

    owner, repo = match.groups()
    repo = repo.replace(".git", "")
    print(f"Gathering context for {owner}/{repo}")

    # README
    print("  Fetching README...")
    readme = _gh_api(f"repos/{owner}/{repo}/readme", accept="application/vnd.github.raw")
    if readme:
        p = output_dir / "readme.md"
        p.write_text(f"# README — {owner}/{repo}\n\n{readme}" if isinstance(readme, str) else str(readme))
        files.append(p)

    # Repo metadata
    print("  Fetching repo metadata...")
    meta = _gh_api(f"repos/{owner}/{repo}")
    if meta:
        meta_md = f"# {owner}/{repo}\n\n"
        meta_md += f"**Description:** {meta.get('description', '?')}\n"
        meta_md += f"**Language:** {meta.get('language', '?')}\n"
        meta_md += f"**Stars:** {meta.get('stargazers_count', '?')}\n"
        meta_md += f"**Topics:** {', '.join(meta.get('topics', []))}\n"
        p = output_dir / "repo_meta.md"
        p.write_text(meta_md)
        files.append(p)

    # File tree (top 2 levels)
    print("  Fetching file tree...")
    tree = _gh_api(f"repos/{owner}/{repo}/git/trees/HEAD?recursive=1")
    if tree and "tree" in tree:
        tree_md = f"# File Tree — {owner}/{repo}\n\n```\n"
        for item in tree["tree"][:200]:
            tree_md += f"{item.get('path', '?')}\n"
        tree_md += "```\n"
        p = output_dir / "tree.md"
        p.write_text(tree_md)
        files.append(p)

    total_chars = sum(f.stat().st_size for f in files)
    print(f"\n  Total: {len(files)} files, {total_chars:,} chars")
    return files


# --- GitHub API helpers ---

def _gh_api(endpoint: str, accept: str = "application/vnd.github+json"):
    """Call gh api. Returns parsed JSON or raw text."""
    try:
        cmd = ["gh", "api", endpoint, "-H", f"Accept: {accept}"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode != 0:
            return None
        if "json" in accept:
            return json.loads(result.stdout)
        return result.stdout
    except (subprocess.TimeoutExpired, json.JSONDecodeError):
        return None


def _gh_api_paginated(endpoint: str, per_page: int = 100) -> list:
    """Fetch all pages from a paginated GitHub API endpoint."""
    all_items = []
    page = 1
    while True:
        sep = "&" if "?" in endpoint else "?"
        data = _gh_api(f"{endpoint}{sep}per_page={per_page}&page={page}")
        if not data or not isinstance(data, list) or len(data) == 0:
            break
        all_items.extend(data)
        if len(data) < per_page:
            break
        page += 1
    return all_items


def add_context(text_or_file: str, output_dir: Path, source_id: str = "expert",
                summary: str = "", persist: bool = False) -> Path:
    """Add expert/human context to an existing context directory.

    If text_or_file is a path to an existing file, copies it.
    Otherwise treats it as inline text and writes to a new file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = Manifest.load(output_dir)

    p = Path(text_or_file)
    if p.is_file():
        # Copy file into context dir
        content = p.read_text()
        dest = output_dir / p.name
        dest.write_text(content)
        filename = p.name
    else:
        # Inline text — write to numbered expert file
        existing = list(output_dir.glob("expert_*.md"))
        n = len(existing) + 1
        filename = f"expert_{n:03d}.md"
        dest = output_dir / filename
        dest.write_text(text_or_file)

    manifest.add(
        filename, "expert", source_id,
        summary=summary or text_or_file[:80],
        persist=persist,
    )
    manifest.save(output_dir)

    print(f"Added expert context: {filename} ({'persistent' if persist else 'one-time'})")
    return dest


def main():
    parser = argparse.ArgumentParser(description="anansi — gather context from anywhere")
    sub = parser.add_subparsers(dest="command")

    gh_p = sub.add_parser("gh", help="Gather from a GitHub issue")
    gh_p.add_argument("ref", help="owner/repo#123 or GitHub issue URL")
    gh_p.add_argument("-o", "--output", default="context", help="Output directory")

    repo_p = sub.add_parser("repo", help="Gather from a GitHub repo")
    repo_p.add_argument("ref", help="owner/repo or GitHub repo URL")
    repo_p.add_argument("-o", "--output", default="context", help="Output directory")

    add_p = sub.add_parser("add", help="Add expert context")
    add_p.add_argument("text_or_file", help="Inline text or path to file")
    add_p.add_argument("-o", "--output", default="context", help="Context directory")
    add_p.add_argument("--source", default="expert", help="Source ID (e.g. expert:dennis)")
    add_p.add_argument("--summary", default="", help="One-line description")
    add_p.add_argument("--persist", action="store_true", help="Mark as persistent (rubric-level)")

    int_p = sub.add_parser("interview", help="Interview an expert to gather context")
    int_p.add_argument("-o", "--output", default="context", help="Context directory")
    int_p.add_argument("--source", default="expert", help="Source ID (e.g. expert:dennis)")

    args = parser.parse_args()

    if args.command == "gh":
        gh_issue(args.ref, Path(args.output))
    elif args.command == "repo":
        gh_repo(args.ref, Path(args.output))
    elif args.command == "add":
        add_context(args.text_or_file, Path(args.output),
                    source_id=args.source, summary=args.summary,
                    persist=args.persist)
    elif args.command == "interview":
        from interview import run_interview
        run_interview(Path(args.output), source_id=args.source)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
