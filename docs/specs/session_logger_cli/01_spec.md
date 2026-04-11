# session_logger.py — CLI spec

## What

A single-file Python CLI that appends, reads, and queries session log entries. Entries are stored as JSONL — one JSON object per line.

## Storage

Each entry is a single JSON line appended to `$SESSION_LOGS_DATA/logs/<project>/<branch>.jsonl`:

```json
{"timestamp": "2026-04-11T10:30:00", "type": "checkpoint", "content": "...", "next": "..."}
```

Fields:
- `timestamp` — ISO 8601 datetime (local time, no timezone)
- `type` — one of: `start`, `checkpoint`, `break`, `finish`
- `content` — free text, may contain newlines
- `next` — optional, free text

## Commands

### `write`

Appends a JSON line to `$SESSION_LOGS_DATA/logs/<project>/<branch>.jsonl`.

```
session_logger.py write --project STR --branch STR --type TYPE --content STR [--next STR]
```

**Behaviour:**

- Creates `logs/<project>/` directory if it doesn't exist
- Appends a single JSON line to `<branch>.jsonl`
- `--type` must be one of: `start`, `checkpoint`, `break`, `finish`
- `--next` is optional; omitted from JSON when not provided
- Prints confirmation to stdout: `Wrote <type> entry to logs/<project>/<branch>.jsonl`

### `last`

Returns the final entry from a branch's log file.

```
session_logger.py last --project STR --branch STR
```

**Behaviour:**

- Reads the last line of `<branch>.jsonl`
- Renders it as formatted text to stdout
- Exits with code 1 and a message to stderr if the file doesn't exist or is empty

### `query`

Searches entries across projects and branches with optional filters.

```
session_logger.py query [--project STR] [--branch STR] [--since DATE] [--type TYPE]
```

**Behaviour:**

- With no filters, returns all entries from all JSONL files
- `--project` limits to files under `logs/<project>/`
- `--branch` combined with `--project` limits to a single file
- `--since YYYY-MM-DD` filters entries by date (inclusive)
- `--type` filters by entry type
- Each result is prefixed with `[<project>/<branch>.jsonl]` for provenance
- Results are separated by blank lines
- Exits with code 1 if no matching entries found

## Configuration

Resolved in order:
1. `SESSION_LOGS_DATA` environment variable
2. `~/.config/session-logger/config` (plain text, single line: path)
3. Error with clear message to stderr, exit code 1

## Constraints

- Single file, no external dependencies beyond Python 3.12 stdlib
- Uses `uv run` with inline script metadata
- Idempotent: running the same `write` twice produces two entries (append-only), but the tool itself has no side effects beyond file writes

## Future enhancements

- **Markdown view generation:** regenerate a human-readable `.md` file from the JSONL source on each write
- **Integration test fixture:** a dummy project + git data repo in `tests/fixtures/` for full round-trip testing (write → git commit → query) against a real git repo, rather than only testing file I/O in isolation
