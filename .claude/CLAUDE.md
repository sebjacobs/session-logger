# session-logger

Append-only session log CLI for Claude Code. Keeps session notes out of project repos.

## Architecture

Two repos:
- **session-logger** (this repo, public) — CLI tool, skill templates, docs
- **Private data repo** (user-owned) — `logs/<project>/<branch>.jsonl`, one JSONL file per branch

`SESSION_LOGS_DATA` env var points at the data repo.

## CLI commands

```
session_logger.py write   --project --branch --type --content [--next]
session_logger.py tail    --project --branch [--limit N]
session_logger.py ls      [--project]
session_logger.py search  [term] [--project] [--branch] [--since] [--type]
```

Entry types: `start`, `checkpoint`, `break`, `finish`

## Development

- Python 3.12+, uses `uv` with inline script metadata (no requirements file)
- Tests: `uv run pytest tests/`
- Skill templates in `skills/` are reference copies — canonical versions live in `~/.claude/skills/`

## Git integration

- Every `write` auto-commits in the data repo
- `finish` type also pushes to remote
