"""Git data reader - parse local .git for statistics."""

from __future__ import annotations

import os
import subprocess
import json
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from pathlib import Path
from collections import Counter, defaultdict


@dataclass
class CommitInfo:
    hash: str
    author: str
    date: datetime
    message: str
    files_changed: int = 0
    insertions: int = 0
    deletions: int = 0


@dataclass
class GitStats:
    repo_path: str
    repo_name: str = ""
    commits: list[CommitInfo] = field(default_factory=list)
    # contribution heatmap: date -> commit count
    daily_counts: dict[date, int] = field(default_factory=dict)
    # language breakdown: ext -> line count (approximated by file count * avg)
    language_counts: Counter = field(default_factory=Counter)
    # commit hour distribution: hour(0-23) -> count
    hour_counts: Counter = field(default_factory=Counter)
    # commit weekday distribution: weekday(0=Mon..6=Sun) -> count
    weekday_counts: Counter = field(default_factory=Counter)
    # author breakdown
    author_counts: Counter = field(default_factory=Counter)
    # total stats
    total_commits: int = 0
    total_authors: int = 0
    first_commit_date: date | None = None
    last_commit_date: date | None = None
    # branch info
    current_branch: str = ""
    total_branches: int = 0


# Language mapping from file extensions
LANG_MAP: dict[str, str] = {
    ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript",
    ".jsx": "JavaScript", ".rs": "Rust", ".go": "Go", ".java": "Java",
    ".kt": "Kotlin", ".rb": "Ruby", ".php": "PHP", ".c": "C", ".cpp": "C++",
    ".h": "C/C++", ".hpp": "C++", ".cs": "C#", ".swift": "Swift",
    ".m": "Objective-C", ".scala": "Scala", ".r": "R", ".R": "R",
    ".lua": "Lua", ".perl": "Perl", ".pl": "Perl", ".sh": "Shell",
    ".bash": "Shell", ".zsh": "Shell", ".fish": "Shell",
    ".html": "HTML", ".css": "CSS", ".scss": "CSS", ".sass": "CSS",
    ".vue": "Vue", ".svelte": "Svelte",
    ".json": "JSON", ".yaml": "YAML", ".yml": "YAML", ".toml": "TOML",
    ".xml": "XML", ".sql": "SQL", ".md": "Markdown", ".rst": "reStructuredText",
    ".dockerfile": "Dockerfile", ".tf": "Terraform",
    ".dart": "Dart", ".ex": "Elixir", ".exs": "Elixir",
    ".erl": "Erlang", ".hs": "Haskell", ".ml": "OCaml",
    ".zig": "Zig", ".nim": "Nim", ".v": "V", ".wasm": "WebAssembly",
}


def find_git_repos(path: Path, max_depth: int = 3) -> list[Path]:
    """Find all git repos under a path."""
    repos = []
    for root, dirs, _ in os.walk(path):
        depth = len(Path(root).relative_to(path).parts)
        if depth > max_depth:
            dirs.clear()
            continue
        if ".git" in dirs:
            repos.append(Path(root))
            dirs.remove(".git")  # don't descend into .git
    return sorted(repos)


def _run_git(repo_path: Path, *args: str) -> str:
    """Run a git command and return stdout."""
    result = subprocess.run(
        ["git", *args],
        cwd=repo_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout.strip()


def read_commits(repo_path: Path, max_commits: int = 5000) -> list[CommitInfo]:
    """Read commit history from a git repo."""
    # Use --format with NUL separator for safe parsing
    fmt = "%x00%H%x00%an%x00%aI%x00%s"
    output = _run_git(
        repo_path,
        "log", f"--max-count={max_commits}",
        "--format=" + fmt,
        "--numstat",
    )
    if not output:
        return []

    commits = []
    lines = output.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.startswith("\0"):
            i += 1
            continue

        parts = line.strip("\0").split("\0")
        if len(parts) < 4:
            i += 1
            continue

        hash_val, author, date_str, message = parts[0], parts[1], parts[2], parts[3]
        try:
            dt = datetime.fromisoformat(date_str)
        except (ValueError, IndexError):
            i += 1
            continue

        # Read numstat lines until empty line
        files_changed = 0
        insertions = 0
        deletions = 0
        i += 1
        while i < len(lines) and lines[i].strip() and not lines[i].startswith("\0"):
            stat_parts = lines[i].split("\t")
            if len(stat_parts) >= 3:
                ins = stat_parts[0]
                dels = stat_parts[1]
                if ins != "-":
                    try:
                        insertions += int(ins)
                    except ValueError:
                        pass
                if dels != "-":
                    try:
                        deletions += int(dels)
                    except ValueError:
                        pass
                files_changed += 1
            i += 1

        commits.append(CommitInfo(
            hash=hash_val,
            author=author,
            date=dt,
            message=message,
            files_changed=files_changed,
            insertions=insertions,
            deletions=deletions,
        ))

    return commits


def read_language_breakdown(repo_path: Path) -> Counter:
    """Read language breakdown using git ls-files + file extension counting."""
    output = _run_git(repo_path, "ls-files")
    if not output:
        return Counter()

    lang_counter: Counter = Counter()
    for filepath in output.split("\n"):
        filepath = filepath.strip().strip('"').strip("'")
        if not filepath:
            continue
        ext = Path(filepath).suffix.lower()
        lang = LANG_MAP.get(ext)
        if lang:
            lang_counter[lang] += 1
        elif ext and not ext.startswith(".") and len(ext) <= 6:
            # Only count reasonable extensions (skip .gitignore etc.)
            lang_counter[f"Other({ext})"] += 1

    return lang_counter


def compute_stats(repo_path: Path, max_commits: int = 5000) -> GitStats:
    """Compute all git statistics for a repo."""
    stats = GitStats(
        repo_path=str(repo_path),
        repo_name=repo_path.name,
    )

    # Read commits
    commits = read_commits(repo_path, max_commits)
    stats.commits = commits
    stats.total_commits = len(commits)

    if not commits:
        return stats

    # Daily contribution counts
    daily: dict[date, int] = defaultdict(int)
    for c in commits:
        d = c.date.date()
        daily[d] += 1
    stats.daily_counts = dict(daily)

    # Hour distribution
    for c in commits:
        stats.hour_counts[c.date.hour] += 1

    # Weekday distribution
    for c in commits:
        stats.weekday_counts[c.date.weekday()] += 1

    # Author breakdown
    for c in commits:
        stats.author_counts[c.author] += 1
    stats.total_authors = len(stats.author_counts)

    # Date range
    stats.first_commit_date = commits[-1].date.date()  # oldest (log is newest-first)
    stats.last_commit_date = commits[0].date.date()

    # Language breakdown
    stats.language_counts = read_language_breakdown(repo_path)

    # Branch info
    branch = _run_git(repo_path, "rev-parse", "--abbrev-ref", "HEAD")
    stats.current_branch = branch or "unknown"

    branch_list = _run_git(repo_path, "branch", "-a", "--format=%(refname:short)")
    stats.total_branches = len([b for b in branch_list.split("\n") if b.strip()])

    return stats
