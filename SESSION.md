## 2026-04-11 | main

### What this is

`session-logger` is a tool to replace the `SESSION.md`-in-project-repo convention used in Claude Code sessions. The core problem: session notes committed to feature branches require a messy cleanup ceremony at merge time (prefix commits, manual resets, easy to forget, history lost on branch delete).

### Design decisions made

- **Two repos:** `session-logger` (public, tooling) + user-owned private data repo (session notes)
- **Plain markdown over JSONL** — human-readable without tooling, compatible with existing SESSION.md format. Structured metadata (project, branch, type, timestamp) lives in section headings.
- **`SESSION_LOGS_DATA` env var** points the tool at the private data repo — configurable, works for anyone cloning the public tool
- **Per-project/per-branch files:** `logs/<project>/<branch>.md` in the data repo
- **No symlink in worktree** — SESSION.md is a nice-to-have; skills write directly to the data repo

### Data repo layout

```
session-logs-data/          ← private repo, user-owned
  logs/
    <project>/
      <branch>.md           ← one file per branch, append-only
```

### Entry format

```markdown
## YYYY-MM-DD HH:MM | <type>

<content>

**Next:** <next>
```

Types: `start`, `checkpoint`, `break`, `finish`

### CLI design

```bash
session_logger.py write  --project STR --branch STR --type TYPE --content STR [--next STR]
session_logger.py last   --project STR --branch STR
session_logger.py query  [--project STR] [--branch STR] [--since DATE] [--type TYPE]
```

### Git integration (in skills)

- Every `write` → `git add` + `git commit` in the data repo
- `finish` only → `git push`
- Checkpoints commit locally, push at finish

### What's done

- [x] Repo created at `~/Tech/Projects/personal/session-logger`
- [x] README.md written
- [x] `docs/spec.md` written — full design, acceptance criteria, skill integration table
- [x] Initial commit on `main`

### What's next

1. **Create GitHub repos** — `session-logger` (public) + private data repo, add remotes
2. **Build `session_logger.py`** — `write`, `last`, `query` with `SESSION_LOGS_DATA` env var
3. **Write skill templates** in `skills/` — one per skill (`start-session`, `save-session`, `finish-session`, `break-session`)
4. **Update dotfiles** — replace SESSION.md writes in skills with `session_logger.py` calls; update global CLAUDE.md to remove SESSION.md cleanup conventions
5. **Update `2026-stock-research`** — add `SESSION.md` to `.gitignore`, `git rm --cached SESSION.md`, update project CLAUDE.md
6. **Bootstrap the data repo** — create `~/Tech/Projects/personal/session-logs-data/`, `git init`, connect to private GitHub remote, set `SESSION_LOGS_DATA` in shell profile

### Handover prompt

> We're building `session-logger` — a tool to replace the SESSION.md-in-project-repo convention. The problem: session notes committed to feature branches require a messy cleanup ceremony at merge time. The solution: a CLI tool that writes session notes to a separate private git repo, leaving project repos clean.
>
> The repo is at `~/Tech/Projects/personal/session-logger`. README and spec are committed to `main`. Read `docs/spec.md` for the full design.
>
> Next task: build `session_logger.py` with `write`, `last`, and `query` commands. It should read `SESSION_LOGS_DATA` from the environment, write to `$SESSION_LOGS_DATA/logs/<project>/<branch>.md`, and append entries in the markdown format defined in the spec. Use `uv` with inline script metadata. Start with `write` and `last` — `query` can follow.
