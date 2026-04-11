"""Tests for session_logger.py — derived from docs/specs/session_logger_cli/01_spec.md"""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "session_logger.py"


@pytest.fixture()
def data_dir(tmp_path):
    """Create a git-initialized data directory for session logs."""
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True, check=True)
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / ".gitkeep").touch()
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True, check=True)
    return tmp_path


def run_cli(*args: str, env_override: dict | None = None) -> subprocess.CompletedProcess:
    """Run session_logger.py with the given arguments."""
    import os

    env = {**os.environ, **(env_override or {})}
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env=env,
    )


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class TestConfiguration:
    def test_missing_env_var_exits_with_error(self):
        import os

        env = {k: v for k, v in os.environ.items() if k != "SESSION_LOGS_DATA"}
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "write", "--project", "p", "--branch", "b",
             "--type", "start", "--content", "x"],
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode == 1
        assert "SESSION_LOGS_DATA" in result.stderr

    def test_env_var_is_used(self, data_dir):
        result = run_cli(
            "write",
            "--project", "proj",
            "--branch", "main",
            "--type", "start",
            "--content", "Hello",
            env_override={"SESSION_LOGS_DATA": str(data_dir)},
        )
        assert result.returncode == 0
        assert (data_dir / "logs" / "proj" / "main.jsonl").exists()


# ---------------------------------------------------------------------------
# write command
# ---------------------------------------------------------------------------


class TestWrite:
    def test_creates_jsonl_file_and_directories(self, data_dir):
        result = run_cli(
            "write",
            "--project", "new-proj",
            "--branch", "feature-x",
            "--type", "start",
            "--content", "First entry",
            env_override={"SESSION_LOGS_DATA": str(data_dir)},
        )
        assert result.returncode == 0
        jsonl_file = data_dir / "logs" / "new-proj" / "feature-x.jsonl"
        assert jsonl_file.exists()
        entry = json.loads(jsonl_file.read_text().strip())
        assert entry["type"] == "start"
        assert entry["content"] == "First entry"

    def test_confirmation_message(self, data_dir):
        result = run_cli(
            "write",
            "--project", "proj",
            "--branch", "main",
            "--type", "checkpoint",
            "--content", "Some work",
            env_override={"SESSION_LOGS_DATA": str(data_dir)},
        )
        assert "Wrote checkpoint entry to logs/proj/main.jsonl" in result.stdout

    def test_jsonl_entry_has_iso_timestamp(self, data_dir):
        run_cli(
            "write",
            "--project", "proj",
            "--branch", "main",
            "--type", "start",
            "--content", "Check timestamp",
            env_override={"SESSION_LOGS_DATA": str(data_dir)},
        )
        entry = json.loads((data_dir / "logs" / "proj" / "main.jsonl").read_text().strip())
        assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", entry["timestamp"])

    def test_next_field_present_when_provided(self, data_dir):
        run_cli(
            "write",
            "--project", "proj",
            "--branch", "main",
            "--type", "finish",
            "--content", "Done for today",
            "--next", "Pick up testing",
            env_override={"SESSION_LOGS_DATA": str(data_dir)},
        )
        entry = json.loads((data_dir / "logs" / "proj" / "main.jsonl").read_text().strip())
        assert entry["next"] == "Pick up testing"

    def test_next_field_absent_when_not_provided(self, data_dir):
        run_cli(
            "write",
            "--project", "proj",
            "--branch", "main",
            "--type", "start",
            "--content", "Starting up",
            env_override={"SESSION_LOGS_DATA": str(data_dir)},
        )
        entry = json.loads((data_dir / "logs" / "proj" / "main.jsonl").read_text().strip())
        assert "next" not in entry

    def test_appends_to_existing_file(self, data_dir):
        for i in range(3):
            run_cli(
                "write",
                "--project", "proj",
                "--branch", "main",
                "--type", "checkpoint",
                "--content", f"Entry {i}",
                env_override={"SESSION_LOGS_DATA": str(data_dir)},
            )
        lines = (data_dir / "logs" / "proj" / "main.jsonl").read_text().strip().splitlines()
        assert len(lines) == 3
        assert json.loads(lines[0])["content"] == "Entry 0"
        assert json.loads(lines[2])["content"] == "Entry 2"

    def test_invalid_type_rejected(self, data_dir):
        result = run_cli(
            "write",
            "--project", "proj",
            "--branch", "main",
            "--type", "invalid",
            "--content", "Nope",
            env_override={"SESSION_LOGS_DATA": str(data_dir)},
        )
        assert result.returncode != 0

    def test_multiline_content(self, data_dir):
        run_cli(
            "write",
            "--project", "proj",
            "--branch", "main",
            "--type", "checkpoint",
            "--content", "Line one\nLine two\nLine three",
            env_override={"SESSION_LOGS_DATA": str(data_dir)},
        )
        entry = json.loads((data_dir / "logs" / "proj" / "main.jsonl").read_text().strip())
        assert entry["content"] == "Line one\nLine two\nLine three"

    def test_commits_to_data_repo(self, data_dir):
        run_cli(
            "write",
            "--project", "proj",
            "--branch", "main",
            "--type", "start",
            "--content", "Should be committed",
            env_override={"SESSION_LOGS_DATA": str(data_dir)},
        )
        result = subprocess.run(
            ["git", "log", "--oneline"],
            cwd=data_dir,
            capture_output=True,
            text=True,
        )
        assert "session: proj/main start" in result.stdout

    def test_commit_message_format(self, data_dir):
        run_cli(
            "write",
            "--project", "my-app",
            "--branch", "feature-x",
            "--type", "checkpoint",
            "--content", "Progress",
            env_override={"SESSION_LOGS_DATA": str(data_dir)},
        )
        result = subprocess.run(
            ["git", "log", "-1", "--format=%s"],
            cwd=data_dir,
            capture_output=True,
            text=True,
        )
        msg = result.stdout.strip()
        assert msg.startswith("session: my-app/feature-x checkpoint")


# ---------------------------------------------------------------------------
# tail command
# ---------------------------------------------------------------------------


class TestTail:
    def test_returns_last_entry(self, data_dir):
        for entry_type in ("start", "checkpoint", "finish"):
            run_cli(
                "write",
                "--project", "proj",
                "--branch", "main",
                "--type", entry_type,
                "--content", f"Content for {entry_type}",
                env_override={"SESSION_LOGS_DATA": str(data_dir)},
            )
        result = run_cli(
            "tail", "--project", "proj", "--branch", "main",
            env_override={"SESSION_LOGS_DATA": str(data_dir)},
        )
        assert result.returncode == 0
        assert "| finish" in result.stdout
        assert "Content for finish" in result.stdout
        assert "Content for start" not in result.stdout

    def test_missing_file_exits_with_error(self, data_dir):
        result = run_cli(
            "tail", "--project", "nope", "--branch", "nope",
            env_override={"SESSION_LOGS_DATA": str(data_dir)},
        )
        assert result.returncode == 1
        assert "No log file" in result.stderr

    def test_renders_next_field(self, data_dir):
        run_cli(
            "write",
            "--project", "proj",
            "--branch", "main",
            "--type", "finish",
            "--content", "Wrapped up",
            "--next", "Continue tomorrow",
            env_override={"SESSION_LOGS_DATA": str(data_dir)},
        )
        result = run_cli(
            "tail", "--project", "proj", "--branch", "main",
            env_override={"SESSION_LOGS_DATA": str(data_dir)},
        )
        assert "**Next:** Continue tomorrow" in result.stdout

    def test_limit_returns_multiple_entries(self, data_dir):
        for i in range(5):
            run_cli(
                "write",
                "--project", "proj",
                "--branch", "main",
                "--type", "checkpoint",
                "--content", f"Entry {i}",
                env_override={"SESSION_LOGS_DATA": str(data_dir)},
            )
        result = run_cli(
            "tail", "--project", "proj", "--branch", "main",
            "--limit", "3",
            env_override={"SESSION_LOGS_DATA": str(data_dir)},
        )
        assert result.returncode == 0
        assert "Entry 2" in result.stdout
        assert "Entry 3" in result.stdout
        assert "Entry 4" in result.stdout
        assert "Entry 1" not in result.stdout
        assert "Entry 0" not in result.stdout

    def test_limit_exceeding_entry_count_returns_all(self, data_dir):
        run_cli(
            "write",
            "--project", "proj",
            "--branch", "main",
            "--type", "start",
            "--content", "Only entry",
            env_override={"SESSION_LOGS_DATA": str(data_dir)},
        )
        result = run_cli(
            "tail", "--project", "proj", "--branch", "main",
            "--limit", "10",
            env_override={"SESSION_LOGS_DATA": str(data_dir)},
        )
        assert result.returncode == 0
        assert "Only entry" in result.stdout

    def test_renders_timestamp_in_heading(self, data_dir):
        run_cli(
            "write",
            "--project", "proj",
            "--branch", "main",
            "--type", "start",
            "--content", "Hello",
            env_override={"SESSION_LOGS_DATA": str(data_dir)},
        )
        result = run_cli(
            "tail", "--project", "proj", "--branch", "main",
            env_override={"SESSION_LOGS_DATA": str(data_dir)},
        )
        assert re.search(r"^## \d{4}-\d{2}-\d{2} \d{2}:\d{2} \| start$", result.stdout, re.MULTILINE)


# ---------------------------------------------------------------------------
# Integration: write then tail
# ---------------------------------------------------------------------------


class TestWriteThenTail:
    def test_round_trip_single_entry(self, data_dir):
        run_cli(
            "write",
            "--project", "my-proj",
            "--branch", "feature-auth",
            "--type", "start",
            "--content", "Implementing auth flow",
            "--next", "Add token refresh",
            env_override={"SESSION_LOGS_DATA": str(data_dir)},
        )
        result = run_cli(
            "tail", "--project", "my-proj", "--branch", "feature-auth",
            env_override={"SESSION_LOGS_DATA": str(data_dir)},
        )
        assert result.returncode == 0
        assert "Implementing auth flow" in result.stdout
        assert "**Next:** Add token refresh" in result.stdout
        assert "| start" in result.stdout

    def test_round_trip_multiple_entries_returns_latest(self, data_dir):
        entries = [
            ("start", "Beginning work"),
            ("checkpoint", "Halfway through"),
            ("finish", "All done"),
        ]
        for entry_type, content in entries:
            run_cli(
                "write",
                "--project", "proj",
                "--branch", "main",
                "--type", entry_type,
                "--content", content,
                env_override={"SESSION_LOGS_DATA": str(data_dir)},
            )
        result = run_cli(
            "tail", "--project", "proj", "--branch", "main",
            env_override={"SESSION_LOGS_DATA": str(data_dir)},
        )
        assert "All done" in result.stdout
        assert "Beginning work" not in result.stdout
        assert "Halfway through" not in result.stdout


# ---------------------------------------------------------------------------
# ls command
# ---------------------------------------------------------------------------


class TestLs:
    def test_lists_projects(self, data_dir):
        for project in ("alpha", "beta", "gamma"):
            run_cli(
                "write",
                "--project", project,
                "--branch", "main",
                "--type", "start",
                "--content", "hello",
                env_override={"SESSION_LOGS_DATA": str(data_dir)},
            )
        result = run_cli(
            "ls",
            env_override={"SESSION_LOGS_DATA": str(data_dir)},
        )
        assert result.returncode == 0
        lines = result.stdout.strip().splitlines()
        assert lines == ["alpha", "beta", "gamma"]

    def test_lists_branches_for_project(self, data_dir):
        for branch in ("main", "feature-auth", "feature-ui"):
            run_cli(
                "write",
                "--project", "my-app",
                "--branch", branch,
                "--type", "start",
                "--content", "hello",
                env_override={"SESSION_LOGS_DATA": str(data_dir)},
            )
        result = run_cli(
            "ls", "--project", "my-app",
            env_override={"SESSION_LOGS_DATA": str(data_dir)},
        )
        assert result.returncode == 0
        assert "feature-auth" in result.stdout
        assert "feature-ui" in result.stdout
        assert "main" in result.stdout

    def test_branch_listing_shows_entry_count_and_date(self, data_dir):
        for i in range(3):
            run_cli(
                "write",
                "--project", "proj",
                "--branch", "main",
                "--type", "checkpoint",
                "--content", f"Entry {i}",
                env_override={"SESSION_LOGS_DATA": str(data_dir)},
            )
        result = run_cli(
            "ls", "--project", "proj",
            env_override={"SESSION_LOGS_DATA": str(data_dir)},
        )
        assert "3 entries" in result.stdout
        assert "last:" in result.stdout

    def test_no_projects_exits_with_error(self, tmp_path):
        (tmp_path / "logs").mkdir(parents=True)
        result = run_cli(
            "ls",
            env_override={"SESSION_LOGS_DATA": str(tmp_path)},
        )
        assert result.returncode == 1

    def test_unknown_project_exits_with_error(self, tmp_path):
        (tmp_path / "logs").mkdir(parents=True)
        result = run_cli(
            "ls", "--project", "nonexistent",
            env_override={"SESSION_LOGS_DATA": str(tmp_path)},
        )
        assert result.returncode == 1


# ---------------------------------------------------------------------------
# search command
# ---------------------------------------------------------------------------


class TestSearch:
    @pytest.fixture()
    def populated_data(self, data_dir):
        """Create a data dir with entries across multiple projects/branches."""
        run_cli(
            "write", "--project", "proj-a", "--branch", "main",
            "--type", "start", "--content", "Implementing auth flow",
            env_override={"SESSION_LOGS_DATA": str(data_dir)},
        )
        run_cli(
            "write", "--project", "proj-a", "--branch", "main",
            "--type", "checkpoint", "--content", "Added token refresh logic",
            env_override={"SESSION_LOGS_DATA": str(data_dir)},
        )
        run_cli(
            "write", "--project", "proj-a", "--branch", "feature",
            "--type", "start", "--content", "Setting up database migrations",
            env_override={"SESSION_LOGS_DATA": str(data_dir)},
        )
        run_cli(
            "write", "--project", "proj-b", "--branch", "main",
            "--type", "finish", "--content", "Deployed auth service",
            "--next", "Monitor error rates",
            env_override={"SESSION_LOGS_DATA": str(data_dir)},
        )
        return data_dir

    def test_search_by_term(self, populated_data):
        result = run_cli(
            "search", "auth",
            env_override={"SESSION_LOGS_DATA": str(populated_data)},
        )
        assert result.returncode == 0
        assert "auth flow" in result.stdout
        assert "auth service" in result.stdout
        assert "database migrations" not in result.stdout

    def test_search_is_case_insensitive(self, populated_data):
        result = run_cli(
            "search", "AUTH",
            env_override={"SESSION_LOGS_DATA": str(populated_data)},
        )
        assert result.returncode == 0
        assert "auth flow" in result.stdout

    def test_search_includes_next_field(self, populated_data):
        result = run_cli(
            "search", "error rates",
            env_override={"SESSION_LOGS_DATA": str(populated_data)},
        )
        assert result.returncode == 0
        assert "Deployed auth service" in result.stdout

    def test_search_scoped_by_project(self, populated_data):
        result = run_cli(
            "search", "auth", "--project", "proj-a",
            env_override={"SESSION_LOGS_DATA": str(populated_data)},
        )
        assert result.returncode == 0
        assert "auth flow" in result.stdout
        assert "auth service" not in result.stdout  # proj-b entry excluded

    def test_search_scoped_by_project_and_branch(self, populated_data):
        result = run_cli(
            "search", "auth", "--project", "proj-a", "--branch", "main",
            env_override={"SESSION_LOGS_DATA": str(populated_data)},
        )
        assert result.returncode == 0
        assert "auth flow" in result.stdout
        assert "database migrations" not in result.stdout

    def test_search_scoped_by_type(self, populated_data):
        result = run_cli(
            "search", "auth", "--type", "finish",
            env_override={"SESSION_LOGS_DATA": str(populated_data)},
        )
        assert result.returncode == 0
        assert "Deployed auth service" in result.stdout
        assert "auth flow" not in result.stdout

    def test_search_scoped_by_since(self, data_dir):
        (data_dir / "logs" / "proj").mkdir(parents=True)
        jsonl_file = data_dir / "logs" / "proj" / "main.jsonl"
        old = json.dumps({"timestamp": "2026-01-01T10:00:00", "type": "start", "content": "Old auth work"})
        recent = json.dumps({"timestamp": "2026-04-10T10:00:00", "type": "checkpoint", "content": "Recent auth work"})
        jsonl_file.write_text(f"{old}\n{recent}\n")

        result = run_cli(
            "search", "auth", "--since", "2026-04-01",
            env_override={"SESSION_LOGS_DATA": str(data_dir)},
        )
        assert result.returncode == 0
        assert "Recent auth work" in result.stdout
        assert "Old auth work" not in result.stdout

    def test_search_without_term_returns_all(self, populated_data):
        """search with no term but metadata filters still works."""
        result = run_cli(
            "search", "--type", "finish",
            env_override={"SESSION_LOGS_DATA": str(populated_data)},
        )
        assert result.returncode == 0
        assert "Deployed auth service" in result.stdout

    def test_search_provenance_prefix(self, populated_data):
        result = run_cli(
            "search", "database",
            env_override={"SESSION_LOGS_DATA": str(populated_data)},
        )
        assert "[proj-a/feature.jsonl]" in result.stdout

    def test_search_no_results(self, populated_data):
        result = run_cli(
            "search", "nonexistent term",
            env_override={"SESSION_LOGS_DATA": str(populated_data)},
        )
        assert result.returncode == 1
