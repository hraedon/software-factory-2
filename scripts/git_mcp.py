#!/usr/bin/env python3
"""MCP server: cross-repo git awareness for the sf2 project constellation.

Exposes three tools:
  repo_status      — branch, uncommitted files, and last commit for each repo
  recent_commits   — commits across all repos in the last N days
  search_commits   — full-text search across commit messages in all repos

Repos are hardcoded to the known constellation:
  /projects/software-factory-2   (sf2)
  /projects/regista               (regista)
  /projects/software-factory      (v1)
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPOS = {
    "sf2": "/projects/software-factory-2",
    "regista": "/projects/regista",
    "v1": "/projects/software-factory",
}

# ---------------------------------------------------------------------------
# MCP protocol helpers
# ---------------------------------------------------------------------------


def _send(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def _ok(req_id, text: str) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": {"content": [{"type": "text", "text": text}]},
    }


def _error_response(req_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _git(repo: str, *args: str, check: bool = False) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", repo, *args],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip()
    except Exception as exc:
        return f"(git error: {exc})"


def _repo_exists(path: str) -> bool:
    return Path(path).is_dir() and (Path(path) / ".git").exists()


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def tool_repo_status(_args: dict) -> str:
    lines = []
    for name, path in REPOS.items():
        if not _repo_exists(path):
            lines.append(f"[{name}] NOT FOUND at {path}")
            continue
        branch = _git(path, "rev-parse", "--abbrev-ref", "HEAD")
        last_commit = _git(path, "log", "-1", "--format=%h %s (%cr)", "--no-walk")
        # Uncommitted changes
        status_out = _git(path, "status", "--short")
        changed = [l for l in status_out.splitlines() if l.strip()] if status_out else []
        # Ahead/behind remote
        tracking = _git(path, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
        if "fatal" in tracking or "error" in tracking:
            ahead_behind = "(no remote tracking)"
        else:
            ab = _git(path, "rev-list", "--left-right", "--count", f"{tracking}...HEAD")
            if ab and "\t" in ab:
                behind, ahead = ab.split("\t")
                ahead_behind = f"↑{ahead} ahead, ↓{behind} behind {tracking}"
            else:
                ahead_behind = ""

        lines.append(f"[{name}]  branch: {branch}  {ahead_behind}")
        lines.append(f"  last:   {last_commit}")
        if changed:
            lines.append(f"  dirty:  {len(changed)} file(s) changed")
            for c in changed[:5]:
                lines.append(f"    {c}")
            if len(changed) > 5:
                lines.append(f"    ... and {len(changed) - 5} more")
        else:
            lines.append("  clean")
        lines.append("")
    return "\n".join(lines).rstrip()


def tool_recent_commits(args: dict) -> str:
    days = int(args.get("days", 7))
    since = (datetime.now(tz=timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    all_entries: list[tuple[str, str, str, str]] = []  # (iso_date, repo, hash, subject)

    for name, path in REPOS.items():
        if not _repo_exists(path):
            continue
        out = _git(path, "log", f"--since={since}", "--format=%ci\t%h\t%s", "--all")
        if not out:
            continue
        for line in out.splitlines():
            parts = line.split("\t", 2)
            if len(parts) == 3:
                iso_date, h, subject = parts
                all_entries.append((iso_date, name, h, subject))

    if not all_entries:
        return f"No commits in the last {days} days across any repo."

    all_entries.sort(key=lambda x: x[0], reverse=True)
    lines = [f"Commits in the last {days} days (newest first):", ""]
    for iso_date, name, h, subject in all_entries:
        date_short = iso_date[:16]
        lines.append(f"  {date_short}  [{name}]  {h}  {subject}")
    return "\n".join(lines)


def tool_search_commits(args: dict) -> str:
    query = args.get("query", "").strip()
    if not query:
        return "Required argument: query"
    limit = int(args.get("limit", 20))
    results: list[tuple[str, str, str, str]] = []

    for name, path in REPOS.items():
        if not _repo_exists(path):
            continue
        out = _git(path, "log", "--all", f"--grep={query}", "-i",
                   f"-{limit}", "--format=%ci\t%h\t%s")
        if not out:
            continue
        for line in out.splitlines():
            parts = line.split("\t", 2)
            if len(parts) == 3:
                iso_date, h, subject = parts
                results.append((iso_date, name, h, subject))

    if not results:
        return f"No commits matching '{query}' found."

    results.sort(key=lambda x: x[0], reverse=True)
    lines = [f"Commits matching '{query}':", ""]
    for iso_date, name, h, subject in results[:limit]:
        date_short = iso_date[:10]
        lines.append(f"  {date_short}  [{name}]  {h}  {subject}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "repo_status",
        "description": (
            "Show the current state of all repos in the sf2 constellation "
            "(sf2, regista, v1): branch name, ahead/behind remote, last commit, "
            "and uncommitted file count. Use at session start to orient quickly."
        ),
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "recent_commits",
        "description": (
            "List commits across all repos (sf2, regista, v1) from the last N days, "
            "sorted newest-first. Useful for noticing cross-repo changes that might "
            "affect sf2 (e.g., a regista API change)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "How many days back to look (default 7)",
                    "default": 7,
                }
            },
            "required": [],
        },
    },
    {
        "name": "search_commits",
        "description": (
            "Search commit messages across all repos for a keyword or phrase. "
            "Useful for finding when a specific change (e.g., 'InMemorySubstrate', "
            "'gate_fail', 'BC-194') was introduced or fixed across the constellation."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search term (case-insensitive, matched against commit messages)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results per repo (default 20)",
                    "default": 20,
                },
            },
            "required": ["query"],
        },
    },
]

TOOL_FNS = {
    "repo_status": tool_repo_status,
    "recent_commits": tool_recent_commits,
    "search_commits": tool_search_commits,
}

# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def main() -> None:
    for raw_line in sys.stdin:
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        try:
            req = json.loads(raw_line)
        except json.JSONDecodeError:
            continue

        req_id = req.get("id")
        method = req.get("method", "")

        if method == "initialize":
            _send({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "git-constellation", "version": "1.0.0"},
                },
            })

        elif method == "notifications/initialized":
            pass

        elif method == "tools/list":
            _send({"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}})

        elif method == "tools/call":
            params = req.get("params", {})
            name = params.get("name", "")
            args = params.get("arguments", {})
            fn = TOOL_FNS.get(name)
            if fn is None:
                _send(_error_response(req_id, -32601, f"Unknown tool: {name}"))
            else:
                try:
                    text = fn(args)
                    _send(_ok(req_id, text))
                except Exception as exc:
                    _send(_ok(req_id, f"Error: {exc}"))

        elif method == "ping":
            _send({"jsonrpc": "2.0", "id": req_id, "result": {}})

        else:
            _send(_error_response(req_id, -32601, f"Method not found: {method}"))


if __name__ == "__main__":
    main()
