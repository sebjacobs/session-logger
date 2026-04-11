#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# ///
"""Migrate SESSION.md and session_log.md history into session-logger JSONL format.

Reads session notes from:
1. docs/session_log.md on main (the archive)
2. SESSION.md on main
3. SESSION.md on every local and remote branch (deduplicated)

Parses ## headings into structured entries and writes them to the session-logger
data repo as JSONL via session_logger.py.

Usage:
    migrate_session_md.py /path/to/project [--dry-run]
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


# Heading patterns found in the wild:
# ## 2026-04-02 (evening)
# ## 2026-04-02 (afternoon)
# ## 2026-03-31
# ## Session note — 2026-04-08
# ## Session note — 2026-04-04 (claude-rag install + easy-installer)
# ## 2026-04-06 | feature/rns-classification-3-llm
# ## 2026-04-10 (afternoon) | feature/rns-classification-3-llm
# ## 2026-04-11 10:45 | feature/rns-classification-3-llm
HEADING_RE = re.compile(
    r"^##\s+"
    r"(?:Session note\s*—?\s*)?"  # optional "Session note —" prefix
    r"(\d{4}-\d{2}-\d{2})"       # date
    r"(?:\s+(\d{2}:\d{2}))?"     # optional time HH:MM
    r"(?:\s*\(([^)]+)\))?"       # optional (morning/afternoon/evening/description)
    r"(?:\s*\|\s*(.+?))?"        # optional | branch-name
    r"\s*$",
    re.MULTILINE,
)

# Time-of-day to approximate timestamp
TIME_OF_DAY = {
    "morning": "09:00",
    "afternoon": "14:00",
    "evening": "19:00",
}


def parse_sections(text: str) -> list[dict]:
    """Parse markdown text into session entry dicts."""
    entries = []
    matches = list(HEADING_RE.finditer(text))

    for i, match in enumerate(matches):
        date_str = match.group(1)
        time_str = match.group(2)
        qualifier = match.group(3)
        branch = match.group(4)

        # Determine timestamp
        if time_str:
            timestamp = f"{date_str}T{time_str}:00"
        elif qualifier and qualifier.strip().lower() in TIME_OF_DAY:
            t = TIME_OF_DAY[qualifier.strip().lower()]
            timestamp = f"{date_str}T{t}:00"
        else:
            timestamp = f"{date_str}T12:00:00"

        # Extract content between this heading and the next
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()

        # Remove trailing --- separators
        content = re.sub(r"\n---\s*$", "", content).strip()

        if not content:
            continue

        # Extract "Next" / "Decisions for next session" as the next field
        next_task = None
        next_patterns = [
            r"\*\*Decisions for next session:\*\*\s*\n((?:[-\d].*\n?)+)",
            r"\*\*Next priorities?:\*\*\s*(.+?)(?:\n\n|\Z)",
            r"\*\*Next:\*\*\s*(.+?)(?:\n\n|\Z)",
        ]
        for pattern in next_patterns:
            m = re.search(pattern, content, re.DOTALL)
            if m:
                next_task = m.group(1).strip()
                break

        entry = {
            "timestamp": timestamp,
            "type": "finish",  # historical entries are retrospective summaries
            "content": content,
        }
        if next_task:
            entry["next"] = next_task
        if branch:
            entry["_branch"] = branch.strip()
        if qualifier and qualifier.strip().lower() not in TIME_OF_DAY:
            entry["_qualifier"] = qualifier.strip()

        entries.append(entry)

    return entries


def git_show(repo: Path, ref: str, path: str) -> str | None:
    """Read a file from a git ref."""
    result = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return result.stdout
    return None


def get_branches(repo: Path) -> list[str]:
    """Get all unique branch names (local + remote, deduplicated)."""
    result = subprocess.run(
        ["git", "branch", "-a", "--format=%(refname:short)"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    branches = set()
    for line in result.stdout.strip().splitlines():
        line = line.strip()
        # Normalise remote branches: origin/feature/x -> feature/x
        if line.startswith("origin/"):
            name = line[len("origin/"):]
            if name == "HEAD":
                continue
            branches.add(name)
        else:
            branches.add(line)
    return sorted(branches)


def content_hash(entry: dict) -> str:
    """Hash an entry's content for deduplication."""
    # Use date + first 200 chars of content as the dedup key
    key = entry["timestamp"][:10] + entry["content"][:200]
    return hashlib.md5(key.encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description="Migrate SESSION.md history to session-logger")
    parser.add_argument("project_path", help="Path to the project repo")
    parser.add_argument("--dry-run", action="store_true", help="Print entries without writing")
    parser.add_argument("--project-name", help="Override project name (default: repo directory name)")
    args = parser.parse_args()

    repo = Path(args.project_path).resolve()
    if not (repo / ".git").exists():
        print(f"Error: {repo} is not a git repo", file=sys.stderr)
        sys.exit(1)

    project_name = args.project_name or repo.name

    print(f"Migrating session history for: {project_name}")
    print(f"Repo: {repo}")
    print()

    # Collect all entries, tracking source for reporting
    all_entries: list[tuple[str, str, dict]] = []  # (source, branch, entry)
    seen_hashes: set[str] = set()

    # 1. Parse session_log.md from main
    session_log = git_show(repo, "main", "docs/session_log.md")
    if session_log:
        entries = parse_sections(session_log)
        for entry in entries:
            h = content_hash(entry)
            if h not in seen_hashes:
                seen_hashes.add(h)
                branch = entry.pop("_branch", "main")
                entry.pop("_qualifier", None)
                all_entries.append(("session_log.md", branch, entry))
        print(f"  session_log.md (main): {len(entries)} entries parsed, {sum(1 for s, _, _ in all_entries if s == 'session_log.md')} unique")

    # 2. Parse SESSION.md from every branch
    branches = get_branches(repo)
    for branch in branches:
        # Try local branch first, then remote
        for ref in [branch, f"origin/{branch}"]:
            text = git_show(repo, ref, "SESSION.md")
            if text:
                entries = parse_sections(text)
                added = 0
                for entry in entries:
                    h = content_hash(entry)
                    if h not in seen_hashes:
                        seen_hashes.add(h)
                        entry_branch = entry.pop("_branch", branch)
                        entry.pop("_qualifier", None)
                        all_entries.append((f"SESSION.md@{branch}", entry_branch, entry))
                        added += 1
                if added > 0:
                    print(f"  SESSION.md @ {branch}: {len(entries)} entries parsed, {added} new")
                break  # Don't read remote if local worked

    # Sort by timestamp
    all_entries.sort(key=lambda x: x[2]["timestamp"])

    print(f"\nTotal: {len(all_entries)} unique entries across {len(set(b for _, b, _ in all_entries))} branches")

    if args.dry_run:
        print("\n--- DRY RUN ---\n")
        for source, branch, entry in all_entries:
            print(f"[{branch}] {entry['timestamp']} | {entry['type']}")
            print(f"  Source: {source}")
            print(f"  Content: {entry['content'][:100]}...")
            if entry.get("next"):
                print(f"  Next: {entry['next'][:100]}...")
            print()
        return

    # Resolve data dir for idempotency check
    data_dir_str = os.environ.get("SESSION_LOGS_DATA", "")
    if not data_dir_str:
        print("Error: SESSION_LOGS_DATA not set", file=sys.stderr)
        sys.exit(1)
    data_dir = Path(data_dir_str)

    # Load existing entries for idempotency
    existing_hashes: set[str] = set()
    project_dir = data_dir / "logs" / project_name
    if project_dir.exists():
        for jpath in project_dir.glob("*.jsonl"):
            for line in jpath.read_text().splitlines():
                line = line.strip()
                if line:
                    existing = json.loads(line)
                    existing_hashes.add(content_hash(existing))

    # Filter out entries that already exist
    new_entries = [(s, b, e) for s, b, e in all_entries if content_hash(e) not in existing_hashes]

    if not new_entries:
        print("\nAll entries already migrated — nothing to do.")
        return

    print(f"\n{len(new_entries)} new entries to write ({len(all_entries) - len(new_entries)} already exist)")

    # Write entries via session_logger.py
    script = str(Path(__file__).parent.parent / "session_logger.py")
    print("\nWriting entries...")
    for source, branch, entry in new_entries:
        cmd = [
            sys.executable, script,
            "write",
            "--project", project_name,
            "--branch", branch,
            "--type", entry["type"],
            "--content", entry["content"],
        ]
        if entry.get("next"):
            cmd.extend(["--next", entry["next"]])

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  ERROR writing {branch} {entry['timestamp']}: {result.stderr}", file=sys.stderr)
        else:
            print(f"  {result.stdout.strip()}")

        # Fix the timestamp to match the original (session_logger.py uses now())
        safe_branch = branch.replace("/", "+")
        jpath = data_dir / "logs" / project_name / f"{safe_branch}.jsonl"
        if jpath.exists():
            lines = jpath.read_text().splitlines()
            if lines:
                last = json.loads(lines[-1])
                last["timestamp"] = entry["timestamp"]
                lines[-1] = json.dumps(last)
                jpath.write_text("\n".join(lines) + "\n")

    print(f"\nDone. Migrated {len(new_entries)} entries to session-logger.")
    print(f"Run: session_logger.py ls --project {project_name}")


if __name__ == "__main__":
    main()
