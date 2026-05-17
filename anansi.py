#!/usr/bin/env python3
"""anansi — intelligent context gatherer.

Two commands:
  gather    — crawl sources via URI (GitHub, repos, URLs, future: MCP servers)
  interview — agent interviews a human expert against existing context

Usage:
  anansi gather github:Expensify/App#15193 -o context/
  anansi gather repo:kaisoai/irie -o context/
  anansi interview -o context/
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from manifest import Manifest


# --- Source handlers ---

def _gather_github_issue(ref: str, output_dir: Path, manifest: Manifest) -> list[Path]:
    """Gather from a GitHub issue. Full thread, no truncation."""
    match = re.match(r"([^/]+)/([^#]+)#(\d+)", ref)
    if not match:
        match = re.search(r"github\.com/([^/]+)/([^/]+)/issues/(\d+)", ref)
    if not match:
        print(f"Error: can't parse GitHub issue ref '{ref}'")
        return []

    owner, repo, number = match.groups()
    api_base = f"repos/{owner}/{repo}/issues/{number}"
    source_id = f"github:{owner}/{repo}#{number}"
    files = []

    print(f"  Gathering {owner}/{repo}#{number}")

    # Issue body
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
                      summary=f"Issue: {issue.get('title', '')[:80]}",
                      tags=["github", "issue"])

    # All comments — paginated, no truncation
    comments = _gh_api_paginated(f"{api_base}/comments")
    if comments:
        comments_md = f"# Discussion Thread\n\n{len(comments)} comments\n\n"
        for c in comments:
            user = c.get("user", {}).get("login", "?")
            date = c.get("created_at", "?")[:10]
            body = c.get("body", "")
            comments_md += f"---\n**{user}** ({date}):\n\n{body}\n\n"
        p = output_dir / "comments.md"
        p.write_text(comments_md)
        files.append(p)
        manifest.add("comments.md", "automated", source_id,
                      summary=f"Discussion: {len(comments)} comments",
                      tags=["github", "comments"])

    # Linked PRs
    timeline = _gh_api_paginated(f"{api_base}/timeline")
    prs = set()
    if timeline:
        for event in timeline:
            if event.get("event") == "cross-referenced":
                source = event.get("source", {}).get("issue", {})
                if source.get("pull_request"):
                    prs.add(source.get("number"))

    if prs:
        pr_md = "# Linked PRs\n\n"
        for pr_num in sorted(prs):
            pr_data = _gh_api(f"repos/{owner}/{repo}/pulls/{pr_num}")
            if pr_data:
                pr_md += f"## PR #{pr_num}: {pr_data.get('title', '?')}\n"
                pr_md += f"**State:** {pr_data.get('state', '?')} | **Merged:** {pr_data.get('merged', False)}\n\n"
                pr_md += (pr_data.get("body", "") or "(no body)") + "\n\n"
        p = output_dir / "linked_prs.md"
        p.write_text(pr_md)
        files.append(p)
        manifest.add("linked_prs.md", "automated", source_id,
                      summary=f"Linked PRs: {len(prs)}", tags=["github", "prs"])

    return files


def _gather_repo(ref: str, output_dir: Path, manifest: Manifest) -> list[Path]:
    """Gather from a GitHub repo — README, structure, metadata."""
    match = re.match(r"([^/]+)/([^/]+)", ref.rstrip("/"))
    if not match:
        match = re.search(r"github\.com/([^/]+)/([^/]+)", ref)
    if not match:
        print(f"Error: can't parse repo ref '{ref}'")
        return []

    owner, repo = match.groups()
    repo = repo.replace(".git", "")
    source_id = f"repo:{owner}/{repo}"
    files = []

    print(f"  Gathering {owner}/{repo}")

    readme = _gh_api(f"repos/{owner}/{repo}/readme", accept="application/vnd.github.raw")
    if readme and isinstance(readme, str):
        p = output_dir / "readme.md"
        p.write_text(f"# README — {owner}/{repo}\n\n{readme}")
        files.append(p)
        manifest.add("readme.md", "automated", source_id, summary="README", tags=["repo"])

    meta = _gh_api(f"repos/{owner}/{repo}")
    if meta:
        meta_md = f"# {owner}/{repo}\n\n"
        meta_md += f"**Description:** {meta.get('description', '?')}\n"
        meta_md += f"**Language:** {meta.get('language', '?')}\n"
        meta_md += f"**Stars:** {meta.get('stargazers_count', '?')}\n"
        p = output_dir / "repo_meta.md"
        p.write_text(meta_md)
        files.append(p)
        manifest.add("repo_meta.md", "automated", source_id, summary="Repo metadata", tags=["repo"])

    tree = _gh_api(f"repos/{owner}/{repo}/git/trees/HEAD?recursive=1")
    if tree and "tree" in tree:
        tree_md = f"# File Tree\n\n```\n"
        for item in tree["tree"][:200]:
            tree_md += f"{item.get('path', '?')}\n"
        tree_md += "```\n"
        p = output_dir / "tree.md"
        p.write_text(tree_md)
        files.append(p)
        manifest.add("tree.md", "automated", source_id, summary="File tree", tags=["repo"])

    return files


# URI routing
SOURCE_HANDLERS = {
    "github": _gather_github_issue,
    "repo": _gather_repo,
}


def gather(uri: str, output_dir: Path) -> list[Path]:
    """Gather context from a URI. Routes to appropriate handler."""
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = Manifest.load(output_dir)

    # Parse URI prefix
    if ":" in uri and not uri.startswith("http"):
        prefix, ref = uri.split(":", 1)
    elif "#" in uri:
        prefix, ref = "github", uri
    elif "/" in uri and not uri.startswith("http"):
        prefix, ref = "repo", uri
    else:
        print(f"Error: can't determine source type for '{uri}'")
        print(f"Known prefixes: {', '.join(SOURCE_HANDLERS.keys())}")
        sys.exit(1)

    handler = SOURCE_HANDLERS.get(prefix)
    if not handler:
        print(f"Error: unknown source type '{prefix}'")
        print(f"Known: {', '.join(SOURCE_HANDLERS.keys())}")
        sys.exit(1)

    print(f"Gathering from {prefix}:{ref}")
    files = handler(ref, output_dir, manifest)
    manifest.save(output_dir)

    total_chars = sum(f.stat().st_size for f in files)
    print(f"\n  Total: {len(files)} files, {total_chars:,} chars")
    return files


# --- GitHub API helpers ---

def _gh_api(endpoint: str, accept: str = "application/vnd.github+json"):
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


# --- CLI ---

def main():
    parser = argparse.ArgumentParser(description="anansi — intelligent context gatherer")
    sub = parser.add_subparsers(dest="command")

    g = sub.add_parser("gather", help="Gather context from a source")
    g.add_argument("uri", help="Source URI (github:owner/repo#N, repo:owner/repo)")
    g.add_argument("-o", "--output", default="context", help="Output directory")

    i = sub.add_parser("interview", help="Interview an expert against existing context")
    i.add_argument("-o", "--output", default="context", help="Context directory")
    i.add_argument("--source", default="expert", help="Source ID")

    args = parser.parse_args()

    if args.command == "gather":
        gather(args.uri, Path(args.output))
    elif args.command == "interview":
        from interview import run_interview
        run_interview(Path(args.output), source_id=args.source)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
