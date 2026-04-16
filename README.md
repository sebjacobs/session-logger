# session-logger

> **Archived — superseded by [jotter](https://github.com/sebjacobs/jotter).**

Append-only session log tooling for Claude Code sessions. Keeps session notes out of project repos — no cleanup commits, no merge-time ceremony.

## The problem

The conventional approach of committing `SESSION.md` to a feature branch creates friction:

- Session note commits need a `session:` prefix and must be squashed/removed before merge
- `git checkout main -- SESSION.md` cleanup is easy to forget
- Session history is scattered across branches and lost when branches are deleted
- Notes can't be queried across projects

## Design

Two repos, cleanly separated:

| Repo | Visibility | Contains |
|---|---|---|
| `session-logger` (this repo) | Public | Tooling, skill templates, docs |
| Your private data repo | Private | The actual session note files |

Session notes live in a private repo you own. The tooling in this repo reads and writes to it. Point the tool at your data repo via an env var:

```bash
export SESSION_LOGS_DATA=~/path/to/your/private/session-logs-data
```

## Data layout

```
session-logger-data/
  logs/
    <project>/
      <branch>.jsonl   ← one file per branch, one JSON object per line
```

Each file is JSONL — one JSON object per line with `timestamp`, `type`, `content`, and optional `next` fields. Displayed as markdown by the CLI.

## Usage

```bash
# Write a checkpoint entry
session_logger.py write --project my-project --branch feature-xyz --type checkpoint --content "..."

# Write a finish entry with handover prompt
session_logger.py write --project my-project --branch feature-xyz --type finish --content "..." --next "next task description"

# Show the last 3 entries for a branch
session_logger.py tail --project my-project --branch feature-xyz --limit 3

# List all projects (sorted by most recent activity)
session_logger.py ls

# List branches for a project
session_logger.py ls --project my-project

# Search entries by content
session_logger.py search "auth middleware" --project my-project
session_logger.py search --since 2026-04-07 --type finish
```

## Entry format

Each entry is appended as a markdown section:

```markdown
## 2026-04-11 10:30 | checkpoint

...content...

**Next:** next task description
```

## Integration with Claude Code skills

See `skills/` for reference skill templates that integrate with `start-session`, `save-session`, `finish-session`, and `break-session`.

Skills call `session_logger.py` directly. The data repo is auto-committed and pushed at `/finish` and `/save`.

## Setup

1. Clone this repo
2. Create a private `session-logs-data` repo
3. Set `SESSION_LOGS_DATA` in your shell profile
4. Copy the skill templates into your `~/.claude/skills/` (or symlink them)
5. Add `SESSION.md` to `.gitignore` in your projects

## Storage format

Entries are stored as JSONL — one JSON object per line:

```json
{"timestamp": "2026-04-11T10:30:00", "type": "checkpoint", "content": "...", "next": "..."}
```

JSONL was chosen over plain markdown because it's trivially parseable for querying and search, while the CLI renders entries as readable markdown for display. The data files are still diffable in git and easy to inspect with standard tools (`jq`, `grep`).
