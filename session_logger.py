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


def cmd_ls(args: argparse.Namespace) -> None:
    """List projects or branches."""
    data_dir = get_data_dir()
    logs_dir = data_dir / "logs"

    if not logs_dir.exists():
        print("No logs directory found", file=sys.stderr)
        sys.exit(1)

    if args.project:
        # List branches for a project
        project_dir = logs_dir / args.project
        if not project_dir.exists():
            print(f"No logs for project {args.project}", file=sys.stderr)
            sys.exit(1)
        # Collect branch info and sort by last timestamp descending
        branch_info = []
        for path in project_dir.glob("*.jsonl"):
            branch = path.stem
            entries = read_entries(path)
            if entries:
                last_ts = entries[-1]["timestamp"]
                last_date = datetime.fromisoformat(last_ts).strftime("%Y-%m-%d")
                branch_info.append((branch, len(entries), last_date, last_ts))
            else:
                branch_info.append((branch, 0, None, ""))
        branch_info.sort(key=lambda x: x[3], reverse=True)
        for branch, count, last_date, _ in branch_info:
            if last_date:
                print(f"{branch}  ({count} entries, last: {last_date})")
            else:
                print(branch)
    else:
        # List projects with last activity, sorted by most recent first
        project_info = []
        for project_dir in logs_dir.iterdir():
            if not project_dir.is_dir():
                continue
            latest_ts = ""
            for path in project_dir.glob("*.jsonl"):
                entries = read_entries(path)
                if entries:
                    ts = entries[-1]["timestamp"]
                    if ts > latest_ts:
                        latest_ts = ts
            if latest_ts:
                last_date = datetime.fromisoformat(latest_ts).strftime("%Y-%m-%d")
                project_info.append((project_dir.name, last_date, latest_ts))
            else:
                project_info.append((project_dir.name, None, ""))
        if not project_info:
            print("No projects found", file=sys.stderr)
            sys.exit(1)
        project_info.sort(key=lambda x: x[2], reverse=True)
        for name, last_date, _ in project_info:
            if last_date:
                print(f"{name}  (last: {last_date})")
            else:
                print(name)


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

    # ls
    p_ls = subparsers.add_parser("ls", help="List projects or branches")
    p_ls.add_argument("--project", default=None, help="List branches for this project")

    args = parser.parse_args()

    match args.command:
        case "write":
            cmd_write(args)
        case "tail":
            cmd_tail(args)
        case "ls":
            cmd_ls(args)


if __name__ == "__main__":
    main()
