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

    args = parser.parse_args()

    match args.command:
        case "write":
            cmd_write(args)


if __name__ == "__main__":
    main()
