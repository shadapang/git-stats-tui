"""Tests for git_reader.py — core parsing and stats computation."""

from __future__ import annotations

import subprocess
from datetime import date
from pathlib import Path

import pytest

from src.git_reader import (
    GitStats,
    GitCommandError,
    LANG_MAP,
    _compute_derived_stats,
    compute_stats,
    filter_by_date,
    find_git_repos,
    read_commits,
)


# ---------------------------------------------------------------------------
# Helpers: create a temp git repo with known commits
# ---------------------------------------------------------------------------

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

    # Create files with known line counts
    (repo / "main.py").write_text("line1\nline2\nline3\nline4\nline5\n")
    (repo / "lib.py").write_text("a\nb\nc\n")
    (repo / "app.js").write_text("const x = 1;\nconst y = 2;\n")
    (repo / "README.md").write_text("# Hello\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial commit")

    # Second commit — modify main.py
    (repo / "main.py").write_text(
        "line1\nline2\nline3\nline4\nline5\nline6\nline7\n"
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "add more lines")

    # Third commit — add a Rust file
    (repo / "main.rs").write_text("fn main() {\n    println!();\n}\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "add rust file")

    # Create an untracked file (should not appear in stats)
    (repo / "untracked.py").write_text("should not count\n")

    # Create a branch
    _git(repo, "branch", "feature")

    return repo


# ---------------------------------------------------------------------------
# read_commits
# ---------------------------------------------------------------------------

class TestReadCommits:
    def test_returns_commits_newest_first(self, sample_repo: Path) -> None:
        commits = read_commits(sample_repo)
        assert len(commits) == 3
        # newest first
        assert commits[0].message == "add rust file"
        assert commits[2].message == "initial commit"

    def test_parses_numstat(self, sample_repo: Path) -> None:
        commits = read_commits(sample_repo)
        # Third commit added main.rs (3 lines)
        assert commits[0].insertions >= 3
        assert commits[0].files_changed >= 1

    def test_empty_repo(self, tmp_path: Path) -> None:
        repo = tmp_path / "empty"
        repo.mkdir()
        _git(repo, "init")
        commits = read_commits(repo)
        assert commits == []

    def test_max_commits_limit(self, sample_repo: Path) -> None:
        commits = read_commits(sample_repo, max_commits=1)
        assert len(commits) == 1


# ---------------------------------------------------------------------------
# compute_stats
# ---------------------------------------------------------------------------

class TestComputeStats:
    def test_total_commits(self, sample_repo: Path) -> None:
        stats = compute_stats(sample_repo)
        assert stats.total_commits == 3

    def test_total_authors(self, sample_repo: Path) -> None:
        stats = compute_stats(sample_repo)
        assert stats.total_authors == 1

    def test_branch_info(self, sample_repo: Path) -> None:
        stats = compute_stats(sample_repo)
        assert stats.current_branch == "master" or stats.current_branch == "main"
        assert stats.total_branches >= 2  # master + feature

    def test_daily_counts(self, sample_repo: Path) -> None:
        stats = compute_stats(sample_repo)
        assert len(stats.daily_counts) >= 1
        total_from_daily = sum(stats.daily_counts.values())
        assert total_from_daily == 3

    def test_hour_and_weekday_counts(self, sample_repo: Path) -> None:
        stats = compute_stats(sample_repo)
        assert sum(stats.hour_counts.values()) == 3
        assert sum(stats.weekday_counts.values()) == 3

    def test_language_counts_not_empty(self, sample_repo: Path) -> None:
        stats = compute_stats(sample_repo)
        assert len(stats.language_counts) > 0


# ---------------------------------------------------------------------------
# _compute_derived_stats
# ---------------------------------------------------------------------------

class TestComputeDerivedStats:
    def test_fills_all_counters(self, sample_repo: Path) -> None:
        commits = read_commits(sample_repo)
        stats = GitStats(repo_path=str(sample_repo), repo_name="test")
        _compute_derived_stats(commits, stats)
        assert stats.total_commits == 0  # _compute_derived_stats does not set total_commits
        assert stats.total_authors == 1
        assert stats.first_commit_date is not None
        assert stats.last_commit_date is not None

    def test_empty_commits(self, tmp_path: Path) -> None:
        stats = GitStats(repo_path=str(tmp_path), repo_name="empty")
        _compute_derived_stats([], stats)
        assert stats.daily_counts == {}
        assert stats.hour_counts.total() == 0


# ---------------------------------------------------------------------------
# find_git_repos
# ---------------------------------------------------------------------------

class TestFindGitRepos:
    def test_finds_nested_repo(self, sample_repo: Path) -> None:
        parent = sample_repo.parent
        repos = find_git_repos(parent, max_depth=3)
        assert sample_repo in repos

    def test_excludes_git_directory(self, sample_repo: Path) -> None:
        repos = find_git_repos(sample_repo, max_depth=1)
        # Should not find .git itself as a repo
        for r in repos:
            assert r.name != ".git"


# ---------------------------------------------------------------------------
# LANG_MAP coverage
# ---------------------------------------------------------------------------

class TestLangMap:
    def test_common_languages_present(self) -> None:
        for ext in [".py", ".js", ".ts", ".rs", ".go", ".java", ".rb", ".c", ".cpp"]:
            assert ext in LANG_MAP, f"Missing extension: {ext}"

    def test_values_are_strings(self) -> None:
        for ext, lang in LANG_MAP.items():
            assert isinstance(lang, str) and len(lang) > 0


# ---------------------------------------------------------------------------
# filter_by_date
# ---------------------------------------------------------------------------

class TestFilterByDate:
    def test_filters_commits_in_range(self, sample_repo: Path) -> None:
        stats = compute_stats(sample_repo)
        today = date.today()
        # All commits are from today, so filtering to today should keep all
        filtered = filter_by_date(stats, today, today)
        assert filtered.total_commits == stats.total_commits
        assert len(filtered.commits) == len(stats.commits)

    def test_filters_out_all_commits(self, sample_repo: Path) -> None:
        stats = compute_stats(sample_repo)
        # Use a date range far in the past — should filter out everything
        filtered = filter_by_date(stats, date(2000, 1, 1), date(2000, 12, 31))
        assert filtered.total_commits == 0
        assert filtered.commits == []

    def test_does_not_mutate_original(self, sample_repo: Path) -> None:
        stats = compute_stats(sample_repo)
        original_count = stats.total_commits
        original_len = len(stats.commits)
        # Filter to empty range
        filter_by_date(stats, date(2000, 1, 1), date(2000, 12, 31))
        # Original should be unchanged
        assert stats.total_commits == original_count
        assert len(stats.commits) == original_len

    def test_preserves_language_counts(self, sample_repo: Path) -> None:
        stats = compute_stats(sample_repo)
        today = date.today()
        filtered = filter_by_date(stats, today, today)
        assert filtered.language_counts == stats.language_counts

    def test_recomputes_derived_stats(self, sample_repo: Path) -> None:
        stats = compute_stats(sample_repo)
        # Filter to empty range
        filtered = filter_by_date(stats, date(2000, 1, 1), date(2000, 12, 31))
        assert filtered.daily_counts == {}
        assert filtered.hour_counts.total() == 0


# ---------------------------------------------------------------------------
# GitCommandError
# ---------------------------------------------------------------------------

class TestGitCommandError:
    def test_is_exception(self) -> None:
        err = GitCommandError(Path("/tmp/repo"), ("status",), 128, "not a git repository")
        assert isinstance(err, Exception)
        assert "status" in str(err)
        assert "128" in str(err)

    def test_attributes(self) -> None:
        err = GitCommandError(Path("/tmp/repo"), ("log",), 1, "error output")
        assert err.args_tuple == ("log",)
        assert err.returncode == 1
        assert err.stderr == "error output"
