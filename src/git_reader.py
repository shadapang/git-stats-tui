"""Git data reader - parse local .git for statistics."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, date
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
    # language breakdown: ext -> line count
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


class GitCommandError(RuntimeError):
    """Raised when a git subprocess returns a non-zero exit code."""

    def __init__(self, repo_path: Path, args: tuple[str, ...], returncode: int, stderr: str) -> None:
        cmd = "git " + " ".join(args)
        super().__init__(f"git command failed (exit {returncode}): {cmd}\n  repo: {repo_path}\n  stderr: {stderr[:200]}")
        self.repo_path = repo_path
        self.args_tuple = args
        self.returncode = returncode
        self.stderr = stderr


def _run_git(repo_path: Path, *args: str, check: bool = True) -> str:
    """Run a git command and return stdout.

    Args:
        check: If True (default), raise GitCommandError on non-zero returncode.
               Set to False for commands where failure is expected (e.g. probing).
    """
    result = subprocess.run(
        ["git", *args],
        cwd=repo_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and result.returncode != 0:
        raise GitCommandError(repo_path, args, result.returncode, result.stderr)
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
        check=False,
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

        # Read numstat lines until empty line or next commit header
        files_changed = 0
        insertions = 0
        deletions = 0
        i += 1
        # Skip blank line between header and numstat (git adds one)
        if i < len(lines) and not lines[i].strip():
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


def _count_lines(filepath: Path) -> int:
    """Count lines in a file, returning 0 on any error."""
    try:
        with open(filepath, "rb") as f:
            # Fast line count: read in chunks and count newlines
            count = 0
            buf = bytearray(65536)
            while True:
                n = f.readinto(buf)
                if n == 0:
                    break
                count += buf[:n].count(b"\n")
            return count
    except (OSError, PermissionError):
        return 0


def read_language_breakdown(
    repo_path: Path, max_files: int = 2000, line_count_threshold: int = 500
) -> Counter:
    """Read language breakdown using git ls-files + line counts.

    Uses Python line counting (cross-platform, no xargs/wc dependency).
    When file count exceeds ``line_count_threshold``, falls back to fast
    file-count mode (skips per-file line reading for speed).
    """
    output = _run_git(repo_path, "ls-files")
    if not output:
        return Counter()

    files = [
        f.strip().strip('"').strip("'")
        for f in output.split("\n")
        if f.strip().strip('"').strip("'")
    ]
    if not files:
        return Counter()

    # Fast path: if too many files, just count files per language
    if len(files) > line_count_threshold:
        lang_counts: dict[str, int] = {}
        for filepath in files[:max_files]:
            ext = Path(filepath).suffix.lower()
            lang = LANG_MAP.get(ext)
            if not lang:
                if ext and not ext.startswith(".") and len(ext) <= 6:
                    lang = f"Other({ext})"
                else:
                    continue
            lang_counts[lang] = lang_counts.get(lang, 0) + 1
        return Counter(lang_counts)

    # Slow path: count lines per file
    lang_lines: dict[str, int] = {}
    for filepath in files[:max_files]:
        ext = Path(filepath).suffix.lower()
        lang = LANG_MAP.get(ext)
        if not lang:
            if ext and not ext.startswith(".") and len(ext) <= 6:
                lang = f"Other({ext})"
            else:
                continue

        full_path = repo_path / filepath
        line_count = _count_lines(full_path)
        if line_count > 0:
            lang_lines[lang] = lang_lines.get(lang, 0) + line_count
        else:
            # Fallback: count as 1 file (binary or empty)
            lang_lines[lang] = lang_lines.get(lang, 0) + 1

    return Counter(lang_lines)


def _compute_derived_stats(
    commits: list[CommitInfo],
    stats: GitStats,
) -> None:
    """Fill daily/hour/weekday/author counters and date range from commits.

    Mutates ``stats`` in place. Shared by ``compute_stats()`` and date-filter
    recompute in ``GitStatsApp._load_stats()``.
    """
    # Daily contribution counts
    daily: dict[date, int] = defaultdict(int)
    for c in commits:
        daily[c.date.date()] += 1
    stats.daily_counts = dict(daily)

    # Hour / weekday / author distributions
    for c in commits:
        stats.hour_counts[c.date.hour] += 1
        stats.weekday_counts[c.date.weekday()] += 1
        stats.author_counts[c.author] += 1
    stats.total_authors = len(stats.author_counts)

    # Date range (git log newest-first → last element is oldest)
    if commits:
        stats.first_commit_date = commits[-1].date.date()
        stats.last_commit_date = commits[0].date.date()


def filter_by_date(stats: GitStats, start: date, end: date) -> GitStats:
    """Return a new GitStats with commits filtered to [start, end].

    Pure function — does not mutate the input.  Derived counters
    (daily/hour/weekday/author) are recomputed from the filtered commits.
    ``language_counts`` and branch info are carried over unchanged.
    """
    filtered_commits = [
        c for c in stats.commits
        if start <= c.date.date() <= end
    ]
    new_stats = GitStats(
        repo_path=stats.repo_path,
        repo_name=stats.repo_name,
        commits=filtered_commits,
        total_commits=len(filtered_commits),
        language_counts=Counter(stats.language_counts),  # copy to avoid shared mutation
        current_branch=stats.current_branch,
        total_branches=stats.total_branches,
    )
    if filtered_commits:
        _compute_derived_stats(filtered_commits, new_stats)
    return new_stats


def compute_stats(repo_path: Path, max_commits: int = 5000) -> GitStats:
    """Compute all git statistics for a repo."""
    stats = GitStats(
        repo_path=str(repo_path),
        repo_name=repo_path.name,
    )

    commits = read_commits(repo_path, max_commits)
    stats.commits = commits
    stats.total_commits = len(commits)

    if not commits:
        return stats

    _compute_derived_stats(commits, stats)

    # Language breakdown
    stats.language_counts = read_language_breakdown(repo_path)

    # Branch info
    branch = _run_git(repo_path, "rev-parse", "--abbrev-ref", "HEAD")
    stats.current_branch = branch or "unknown"

    branch_list = _run_git(repo_path, "branch", "-a", "--format=%(refname:short)")
    stats.total_branches = len([b for b in branch_list.split("\n") if b.strip()])

    return stats
