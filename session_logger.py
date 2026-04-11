#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# ///
"""Append-only session log tool for Claude Code sessions.

Writes session notes to a private data repo, keeping project repos clean.
Entries are stored as JSONL — one JSON object per line.
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ENTRY_TYPES = ("start", "checkpoint", "break", "finish")


def get_data_dir() -> Path:
    """Resolve the session logs data directory."""
    env = os.environ.get("SESSION_LOGS_DATA")
    if env:
        return Path(env)

    config_file = Path.home() / ".config" / "session-logger" / "config"
    if config_file.exists():
        return Path(config_file.read_text().strip())

    print(
        "Error: SESSION_LOGS_DATA is not set and no config found at "
        f"{config_file}",
        file=sys.stderr,
    )
    sys.exit(1)


def jsonl_path(data_dir: Path, project: str, branch: str) -> Path:
    """Return the path to a branch's JSONL log file."""
    return data_dir / "logs" / project / f"{branch}.jsonl"


def read_entries(path: Path) -> list[dict]:
    """Read all entries from a JSONL file."""
    if not path.exists():
        return []
    entries = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    return entries


def format_entry(entry: dict) -> str:
    """Format a single entry for display."""
    dt = datetime.fromisoformat(entry["timestamp"])
    heading = f"## {dt.strftime('%Y-%m-%d %H:%M')} | {entry['type']}"
    lines = [heading, "", entry["content"]]
    if entry.get("next"):
        lines.extend(["", f"**Next:** {entry['next']}"])
    return "\n".join(lines)


def cmd_write(args: argparse.Namespace) -> None:
    """Append an entry to the branch JSONL file."""
    data_dir = get_data_dir()
    path = jsonl_path(data_dir, args.project, args.branch)
    path.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "type": args.type,
        "content": args.content,
    }
    if args.next:
        entry["next"] = args.next

    with open(path, "a") as f:
        f.write(json.dumps(entry) + "\n")

    print(f"Wrote {args.type} entry to {path.relative_to(data_dir)}")


def cmd_tail(args: argparse.Namespace) -> None:
    """Print the last N entries from a branch log file."""
    data_dir = get_data_dir()
    path = jsonl_path(data_dir, args.project, args.branch)

    entries = read_entries(path)
    if not entries:
        print(f"No log file for {args.project}/{args.branch}", file=sys.stderr)
        sys.exit(1)

    tail = entries[-args.limit:]
    print("\n\n".join(format_entry(e) for e in tail))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Append-only session log tool for Claude Code sessions",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # write
    p_write = subparsers.add_parser("write", help="Append a session log entry")
    p_write.add_argument("--project", required=True)
    p_write.add_argument("--branch", required=True)
    p_write.add_argument("--type", required=True, choices=ENTRY_TYPES)
    p_write.add_argument("--content", required=True)
    p_write.add_argument("--next", default=None, help="Next task description")

    # last
    p_tail = subparsers.add_parser("tail", help="Show recent entries for a branch")
    p_tail.add_argument("--project", required=True)
    p_tail.add_argument("--branch", required=True)
    p_tail.add_argument("--limit", type=int, default=1, help="Number of entries to return (default: 1)")

    args = parser.parse_args()

    match args.command:
        case "write":
            cmd_write(args)
        case "tail":
            cmd_tail(args)


if __name__ == "__main__":
    main()
