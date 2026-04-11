"""Tests for session_logger.py — derived from docs/specs/session_logger_cli/01_spec.md"""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "session_logger.py"


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

    def test_env_var_is_used(self, tmp_path):
        result = run_cli(
            "write",
            "--project", "proj",
            "--branch", "main",
            "--type", "start",
            "--content", "Hello",
            env_override={"SESSION_LOGS_DATA": str(tmp_path)},
        )
        assert result.returncode == 0
        assert (tmp_path / "logs" / "proj" / "main.jsonl").exists()


# ---------------------------------------------------------------------------
# write command
# ---------------------------------------------------------------------------


class TestWrite:
    def test_creates_jsonl_file_and_directories(self, tmp_path):
        result = run_cli(
            "write",
            "--project", "new-proj",
            "--branch", "feature-x",
            "--type", "start",
            "--content", "First entry",
            env_override={"SESSION_LOGS_DATA": str(tmp_path)},
        )
        assert result.returncode == 0
        jsonl_file = tmp_path / "logs" / "new-proj" / "feature-x.jsonl"
        assert jsonl_file.exists()
        entry = json.loads(jsonl_file.read_text().strip())
        assert entry["type"] == "start"
        assert entry["content"] == "First entry"

    def test_confirmation_message(self, tmp_path):
        result = run_cli(
            "write",
            "--project", "proj",
            "--branch", "main",
            "--type", "checkpoint",
            "--content", "Some work",
            env_override={"SESSION_LOGS_DATA": str(tmp_path)},
        )
        assert "Wrote checkpoint entry to logs/proj/main.jsonl" in result.stdout

    def test_jsonl_entry_has_iso_timestamp(self, tmp_path):
        run_cli(
            "write",
            "--project", "proj",
            "--branch", "main",
            "--type", "start",
            "--content", "Check timestamp",
            env_override={"SESSION_LOGS_DATA": str(tmp_path)},
        )
        entry = json.loads((tmp_path / "logs" / "proj" / "main.jsonl").read_text().strip())
        assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", entry["timestamp"])

    def test_next_field_present_when_provided(self, tmp_path):
        run_cli(
            "write",
            "--project", "proj",
            "--branch", "main",
            "--type", "finish",
            "--content", "Done for today",
            "--next", "Pick up testing",
            env_override={"SESSION_LOGS_DATA": str(tmp_path)},
        )
        entry = json.loads((tmp_path / "logs" / "proj" / "main.jsonl").read_text().strip())
        assert entry["next"] == "Pick up testing"

    def test_next_field_absent_when_not_provided(self, tmp_path):
        run_cli(
            "write",
            "--project", "proj",
            "--branch", "main",
            "--type", "start",
            "--content", "Starting up",
            env_override={"SESSION_LOGS_DATA": str(tmp_path)},
        )
        entry = json.loads((tmp_path / "logs" / "proj" / "main.jsonl").read_text().strip())
        assert "next" not in entry

    def test_appends_to_existing_file(self, tmp_path):
        for i in range(3):
            run_cli(
                "write",
                "--project", "proj",
                "--branch", "main",
                "--type", "checkpoint",
                "--content", f"Entry {i}",
                env_override={"SESSION_LOGS_DATA": str(tmp_path)},
            )
        lines = (tmp_path / "logs" / "proj" / "main.jsonl").read_text().strip().splitlines()
        assert len(lines) == 3
        assert json.loads(lines[0])["content"] == "Entry 0"
        assert json.loads(lines[2])["content"] == "Entry 2"

    def test_invalid_type_rejected(self, tmp_path):
        result = run_cli(
            "write",
            "--project", "proj",
            "--branch", "main",
            "--type", "invalid",
            "--content", "Nope",
            env_override={"SESSION_LOGS_DATA": str(tmp_path)},
        )
        assert result.returncode != 0

    def test_multiline_content(self, tmp_path):
        run_cli(
            "write",
            "--project", "proj",
            "--branch", "main",
            "--type", "checkpoint",
            "--content", "Line one\nLine two\nLine three",
            env_override={"SESSION_LOGS_DATA": str(tmp_path)},
        )
        entry = json.loads((tmp_path / "logs" / "proj" / "main.jsonl").read_text().strip())
        assert entry["content"] == "Line one\nLine two\nLine three"
