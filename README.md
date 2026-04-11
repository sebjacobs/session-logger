# session-logger

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
session-logs-data/
  logs/
    <project>/
      <branch>.md      ← one file per branch, append-only within a session
```

Each file is plain markdown — readable in any editor, diffable in git.

## Usage

```bash
# Write a checkpoint entry
session_logger.py write --project my-project --branch feature-xyz --type checkpoint --content "..."

# Write a finish entry
session_logger.py write --project my-project --branch feature-xyz --type finish --content "..." --next "next task description"

# Read the last entry for a branch
session_logger.py last --project my-project --branch feature-xyz

# Query entries
session_logger.py query --project my-project
session_logger.py query --since 2026-04-07
session_logger.py query --branch feature-xyz
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

## Why not JSONL?

Plain markdown was chosen over JSONL because:

- Readable without tooling — open the file in any editor during a session
- Diffable — git history is human-readable
- Compatible with the existing `SESSION.md` convention — same format, different location

Structured metadata (project, branch, type, timestamp) lives in the section heading, not in a separate schema.
