# session-logger — spec

## What and why

Claude Code sessions currently write `SESSION.md` into the project repo. This requires a cleanup ceremony at merge time: append notes to `docs/session_log.md`, reset `SESSION.md` to main's version, verify it's not in the diff. Easy to forget, noisy in PR history, and history is lost when branches are deleted.

`session-logger` moves session notes out of project repos entirely — into a private data repo owned by the user. The tooling (this repo) is open-source and reusable by anyone with a Claude Code workflow.

## Goals

- Session notes never appear in project git history
- No merge-time cleanup steps
- Notes are human-readable markdown (no tooling required to read them)
- Notes are queryable across projects and branches
- Tooling is open-source; data stays private
- Works with the existing Claude Code skill workflow (`/start`, `/save`, `/finish`, `/break`)

## Out of scope

- GUI or web interface
- Real-time collaboration
- Encryption at rest (private git repo provides sufficient access control)
- Migration tooling for existing `SESSION.md` / `docs/session_log.md` history

## Architecture

### Two repos

**`session-logger`** (public, this repo)
- `session_logger.py` — CLI tool: `write`, `tail`, `ls`, `search`
- `skills/` — reference Claude Code skill templates
- `docs/` — spec, design notes

**`<your-private-data-repo>`** (private, user-owned)
- `logs/<project>/<branch>.jsonl` — one file per branch, append-only

### Configuration

```bash
export SESSION_LOGS_DATA=~/path/to/private/data-repo
```

Resolved in order: env var → `~/.config/session-logger/config` → error.

### CLI

```
session_logger.py write   --project STR --branch STR --type TYPE --content STR [--next STR]
session_logger.py tail    --project STR --branch STR [--limit N]
session_logger.py ls      [--project STR]
session_logger.py search  [TERM] [--project STR] [--branch STR] [--since DATE] [--type TYPE]
```

Types: `start`, `checkpoint`, `break`, `finish`

### Entry format

Stored as JSONL in `logs/<project>/<branch>.jsonl`, one JSON object per line:

```json
{"timestamp": "2026-04-11T10:30:00", "type": "checkpoint", "content": "...", "next": "..."}
```

`tail` returns the last N entries, rendered as markdown.
`search` filters entries by content, type, and date across projects and branches.

### Git integration

After every `write`, the skill:
1. `cd $SESSION_LOGS_DATA && git add logs/<project>/<branch>.jsonl`
2. `git commit -m "session: <project>/<branch> <type> <timestamp>"`
3. `git push` (at `finish` only — checkpoints commit locally, push at finish)

## Skill integration points

| Skill | Change |
|---|---|
| `start-session` | Run `session_logger.py tail` to restore context; create file if missing |
| `save-session` | Run `session_logger.py write --type checkpoint`; git commit in data repo |
| `finish-session` | Run `session_logger.py write --type finish`; git commit + push in data repo; remove SESSION.md cleanup block |
| `break-session` | Run `session_logger.py write --type break`; git commit in data repo |

## Acceptance criteria

- `write` appends a correctly-formatted JSONL entry to the right file, creating dirs as needed
- `tail` returns the last N entries, rendered as markdown
- `search --since` returns matching entries from all files after the given date
- Missing `SESSION_LOGS_DATA` raises a clear error
- All operations are idempotent on the data repo (no duplicate entries from retries)
- Skills updated in dotfiles; SESSION.md removed from project `.gitignore` and git tracking
