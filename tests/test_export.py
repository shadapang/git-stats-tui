"""Tests for --export json CLI functionality."""

from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.git_reader import compute_stats


def _git(repo_path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout.strip()


@pytest.fixture
def sample_repo(tmp_path: Path) -> Path:
    """Create a small git repo with known commits and files."""
    repo = tmp_path / "test_repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "tester@example.com")
    _git(repo, "config", "user.name", "Tester")

    (repo / "main.py").write_text("line1\nline2\nline3\n")
    (repo / "app.js").write_text("const x = 1;\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial commit")

    (repo / "main.py").write_text("line1\nline2\nline3\nline4\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "update main")

    return repo


# ---------------------------------------------------------------------------
# export_json helper (unit test)
# ---------------------------------------------------------------------------

class TestExportJsonUnit:
    def test_payload_structure(self, sample_repo: Path) -> None:
        """Verify the JSON payload has all expected top-level keys."""
        stats = compute_stats(sample_repo)
        # Build payload the same way app.py does
        payload = {
            "repo_name": stats.repo_name,
            "repo_path": str(stats.repo_path),
            "current_branch": stats.current_branch,
            "total_commits": stats.total_commits,
            "total_authors": stats.total_authors,
            "total_branches": stats.total_branches,
            "first_commit_date": str(stats.first_commit_date) if stats.first_commit_date else None,
            "last_commit_date": str(stats.last_commit_date) if stats.last_commit_date else None,
            "language_counts": dict(stats.language_counts),
            "author_counts": dict(stats.author_counts),
            "daily_counts": {str(k): v for k, v in stats.daily_counts.items()},
            "hour_counts": dict(stats.hour_counts),
            "weekday_counts": dict(stats.weekday_counts),
            "commits": [
                {
                    "hash": c.hash,
                    "author": c.author,
                    "date": c.date.isoformat(),
                    "message": c.message,
                    "files_changed": c.files_changed,
                    "insertions": c.insertions,
                    "deletions": c.deletions,
                }
                for c in stats.commits
            ],
        }
        # All expected keys present
        expected_keys = {
            "repo_name", "repo_path", "current_branch",
            "total_commits", "total_authors", "total_branches",
            "first_commit_date", "last_commit_date",
            "language_counts", "author_counts",
            "daily_counts", "hour_counts", "weekday_counts",
            "commits",
        }
        assert set(payload.keys()) == expected_keys

    def test_payload_is_json_serializable(self, sample_repo: Path) -> None:
        """Verify the payload can be serialized to valid JSON."""
        stats = compute_stats(sample_repo)
        payload = {
            "repo_name": stats.repo_name,
            "repo_path": str(stats.repo_path),
            "total_commits": stats.total_commits,
            "commits": [
                {"hash": c.hash, "date": c.date.isoformat(), "message": c.message}
                for c in stats.commits
            ],
        }
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        parsed = json.loads(text)
        assert parsed["total_commits"] == 2
        assert len(parsed["commits"]) == 2

    def test_commit_dates_are_iso_format(self, sample_repo: Path) -> None:
        """Verify commit dates in JSON are ISO 8601 strings."""
        stats = compute_stats(sample_repo)
        for c in stats.commits:
            iso = c.date.isoformat()
            # Should parse back without error
            from datetime import datetime
            datetime.fromisoformat(iso)


# ---------------------------------------------------------------------------
# CLI integration test (--export json) — in-process to avoid stale .pth issues
# ---------------------------------------------------------------------------

class TestExportJsonCLI:
    def test_cli_export_json(self, sample_repo: Path) -> None:
        """Call main() with --export json and capture stdout."""
        from src.app import main

        old_argv = sys.argv
        old_stdout = sys.stdout
        sys.argv = ["git-stats", "--export", "json", str(sample_repo)]
        buf = io.StringIO()
        sys.stdout = buf
        try:
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
        finally:
            sys.argv = old_argv
            sys.stdout = old_stdout

        output = buf.getvalue()
        data = json.loads(output)
        assert data["total_commits"] == 2
        assert data["repo_name"] == "test_repo"
        assert len(data["commits"]) == 2
        assert "language_counts" in data

    def test_cli_export_json_invalid_path(self) -> None:
        """Call main() with a non-existent path — should exit with error."""
        from src.app import main

        old_argv = sys.argv
        old_stderr = sys.stderr
        sys.argv = ["git-stats", "--export", "json", "/nonexistent/path"]
        buf = io.StringIO()
        sys.stderr = buf
        try:
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code != 0
        finally:
            sys.argv = old_argv
            sys.stderr = old_stderr
