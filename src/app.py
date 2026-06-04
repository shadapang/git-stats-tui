"""git-stats-tui main application - Textual TUI for local git statistics."""

from __future__ import annotations

import sys
from pathlib import Path
from datetime import date, timedelta

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, Footer, Static, TabbedContent, TabPane, Input
from textual.containers import VerticalScroll, Horizontal, Vertical, HorizontalGroup
from textual.events import Key
from rich.text import Text
from rich.table import Table
from rich.align import Align
from rich.console import Group

from src.git_reader import GitStats, compute_stats, find_git_repos
from src.widgets.heatmap import HeatmapWidget
from src.widgets.languages import LanguageWidget
from src.widgets.timeline import TimelineWidget


class GitStatsApp(App):
    """A beautiful TUI for local git statistics."""

    TITLE = "git-stats-tui"
    SUB_TITLE = "Local Git Statistics Dashboard"

    CSS = """
    Screen {
        layout: vertical;
    }

    #main-content {
        padding: 1 2;
    }

    .stats-header {
        padding: 1 2;
        background: $surface;
        border-bottom: solid $primary;
    }

    .stats-header Static {
        text-align: center;
    }

    TabbedContent {
        height: 1fr;
    }

    .tab-content {
        padding: 1 2;
    }

    #repo-info {
        padding: 0 2;
        height: auto;
        border-bottom: dashed $primary;
    }

    #date-filter-bar {
        height: auto;
        padding: 0 2;
        dock: top;
        background: $surface;
        display: none;
    }

    #date-input {
        width: 30;
    }

    #repo-switch-bar {
        height: auto;
        padding: 0 2;
        dock: top;
        background: $surface;
        display: none;
    }

    #repo-input {
        width: 60;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("f", "find_repos", "Find Repos", show=True),
        Binding("d", "toggle_date_filter", "Date Filter", show=True),
        Binding("s", "toggle_repo_switch", "Switch Repo", show=True),
    ]

    def __init__(self, repo_path: Path | None = None, **kwargs):
        super().__init__(**kwargs)
        self.repo_path = repo_path or Path.cwd()
        self.stats: GitStats | None = None
        self._date_filter: tuple[date, date] | None = None
        self._discovered_repos: list[Path] = []

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main-content"):
            # Date filter bar (hidden by default)
            with Horizontal(id="date-filter-bar"):
                yield Static("Date range (YYYY-MM-DD ~ YYYY-MM-DD): ", style="bold cyan")
                yield Input(placeholder="e.g. 2025-01-01 ~ 2025-12-31", id="date-input")
            # Repo switch bar (hidden by default)
            with Horizontal(id="repo-switch-bar"):
                yield Static("Repo path: ", style="bold cyan")
                yield Input(placeholder="path/to/repo or #N for discovered repo", id="repo-input")
            yield Static(id="repo-info")
            with TabbedContent():
                with TabPane("Heatmap", id="tab-heatmap"):
                    with VerticalScroll(classes="tab-content"):
                        yield Static(id="heatmap-content")
                with TabPane("Languages", id="tab-languages"):
                    with VerticalScroll(classes="tab-content"):
                        yield Static(id="lang-content")
                with TabPane("Timeline", id="tab-timeline"):
                    with VerticalScroll(classes="tab-content"):
                        yield Static(id="timeline-content")
                with TabPane("Commits", id="tab-commits"):
                    with VerticalScroll(classes="tab-content"):
                        yield Static(id="commits-content")
                with TabPane("Overview", id="tab-overview"):
                    with VerticalScroll(classes="tab-content"):
                        yield Static(id="overview-content")
        yield Footer()

    def on_mount(self) -> None:
        self._load_stats()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submissions."""
        if event.input.id == "date-input":
            self._apply_date_filter(event.value)
            self.query_one("#date-filter-bar").display = False
        elif event.input.id == "repo-input":
            self._apply_repo_switch(event.value)
            self.query_one("#repo-switch-bar").display = False

    def _apply_date_filter(self, value: str) -> None:
        """Apply date range filter from input."""
        value = value.strip()
        if not value:
            self._date_filter = None
            self._load_stats()
            self.notify("Date filter cleared")
            return

        try:
            # Parse "YYYY-MM-DD ~ YYYY-MM-DD" or "YYYY-MM-DD - YYYY-MM-DD"
            parts = value.replace("~", "-").split("-")
            parts = [p.strip() for p in parts if p.strip()]
            if len(parts) == 2:
                start = date.fromisoformat(parts[0])
                end = date.fromisoformat(parts[1])
                self._date_filter = (start, end)
                self._load_stats()
                self.notify(f"Filtered: {start} ~ {end}")
            else:
                self.notify("Format: YYYY-MM-DD ~ YYYY-MM-DD", severity="error")
        except (ValueError, IndexError):
            self.notify("Invalid date format", severity="error")

    def _apply_repo_switch(self, value: str) -> None:
        """Switch to a different repo."""
        value = value.strip()
        if not value:
            return

        # Check if it's a #N reference to discovered repos
        if value.startswith("#") and value[1:].isdigit():
            idx = int(value[1:]) - 1
            if 0 <= idx < len(self._discovered_repos):
                self.repo_path = self._discovered_repos[idx]
                self._date_filter = None
                self._load_stats()
                self.notify(f"Switched to: {self.repo_path.name}")
                return
            else:
                self.notify(f"Invalid repo index (1-{len(self._discovered_repos)})", severity="error")
                return

        # Try as a path
        new_path = Path(value).resolve()
        if (new_path / ".git").exists():
            self.repo_path = new_path
            self._date_filter = None
            self._load_stats()
            self.notify(f"Switched to: {self.repo_path.name}")
        else:
            self.notify(f"Not a git repo: {new_path}", severity="error")

    def _load_stats(self) -> None:
        """Load git stats and render all widgets."""
        try:
            self.stats = compute_stats(self.repo_path)
        except Exception as e:
            self.query_one("#repo-info", Static).update(
                f"[red]Error loading repo: {e}[/]"
            )
            return

        # Apply date filter if set
        if self._date_filter and self.stats:
            start, end = self._date_filter
            self.stats.commits = [
                c for c in self.stats.commits
                if start <= c.date.date() <= end
            ]
            self.stats.total_commits = len(self.stats.commits)
            # Recompute derived stats
            from collections import Counter, defaultdict
            daily: dict[date, int] = defaultdict(int)
            hour_counts: Counter = Counter()
            weekday_counts: Counter = Counter()
            author_counts: Counter = Counter()
            for c in self.stats.commits:
                daily[c.date.date()] += 1
                hour_counts[c.date.hour] += 1
                weekday_counts[c.date.weekday()] += 1
                author_counts[c.author] += 1
            self.stats.daily_counts = dict(daily)
            self.stats.hour_counts = hour_counts
            self.stats.weekday_counts = weekday_counts
            self.stats.author_counts = author_counts
            self.stats.total_authors = len(author_counts)
            if self.stats.commits:
                self.stats.first_commit_date = self.stats.commits[-1].date.date()
                self.stats.last_commit_date = self.stats.commits[0].date.date()

        self._render_repo_info()
        self._render_heatmap()
        self._render_languages()
        self._render_timeline()
        self._render_commits()
        self._render_overview()

    def _render_repo_info(self) -> None:
        """Render the repo info header."""
        if not self.stats:
            return
        s = self.stats
        info = Text()
        info.append(f"  {s.repo_name}  ", style="bold magenta")
        info.append(f"on ", style="dim")
        info.append(f"{s.current_branch}", style="cyan")
        info.append(f"  |  ", style="dim")
        info.append(f"{s.total_commits}", style="bold green")
        info.append(f" commits  ", style="dim")
        info.append(f"{s.total_authors}", style="bold yellow")
        info.append(f" authors  ", style="dim")
        info.append(f"{s.total_branches}", style="bold blue")
        info.append(f" branches", style="dim")
        if s.first_commit_date and s.last_commit_date:
            days = (s.last_commit_date - s.first_commit_date).days
            info.append(f"  |  ", style="dim")
            info.append(f"{days}", style="bold")
            info.append(f" days active", style="dim")
        self.query_one("#repo-info", Static).update(info)

    def _render_heatmap(self) -> None:
        """Render the contribution heatmap."""
        if not self.stats:
            return
        from src.widgets.heatmap import build_heatmap_text
        heatmap = build_heatmap_text(self.stats)
        self.query_one("#heatmap-content", Static).update(Align.center(heatmap))

    def _render_languages(self) -> None:
        """Render the language breakdown."""
        if not self.stats:
            return
        from src.widgets.languages import build_language_table
        table = build_language_table(self.stats)
        self.query_one("#lang-content", Static).update(table)

    def _render_timeline(self) -> None:
        """Render the commit timeline."""
        if not self.stats:
            return
        from src.widgets.timeline import build_hour_chart, build_weekday_chart, build_author_table
        hour = build_hour_chart(self.stats)
        weekday = build_weekday_chart(self.stats)
        authors = build_author_table(self.stats)
        self.query_one("#timeline-content", Static).update(Group(hour, weekday, authors))

    def _render_overview(self) -> None:
        """Render the overview tab with all key stats."""
        if not self.stats:
            return
        s = self.stats

        table = Table(
            title=f"Overview - {s.repo_name}",
            show_header=False,
            border_style="dim",
            title_style="bold magenta",
        )
        table.add_column("Metric", style="cyan", min_width=20)
        table.add_column("Value", style="bold", min_width=20)

        table.add_row("Total Commits", f"{s.total_commits:,}")
        table.add_row("Total Authors", f"{s.total_authors:,}")
        table.add_row("Current Branch", s.current_branch)
        table.add_row("Total Branches", str(s.total_branches))

        if s.first_commit_date and s.last_commit_date:
            table.add_row("First Commit", str(s.first_commit_date))
            table.add_row("Latest Commit", str(s.last_commit_date))
            days = (s.last_commit_date - s.first_commit_date).days
            table.add_row("Active Days", f"{days:,}")
            if days > 0:
                table.add_row("Avg Commits/Day", f"{s.total_commits / days:.1f}")

        # Top language
        if s.language_counts:
            top_lang, top_count = s.language_counts.most_common(1)[0]
            table.add_row("Top Language", f"{top_lang} ({top_count} files)")

        # Top author
        if s.author_counts:
            top_author, top_commits = s.author_counts.most_common(1)[0]
            table.add_row("Top Author", f"{top_author} ({top_commits} commits)")

        # Peak hour
        if s.hour_counts:
            peak_hour = s.hour_counts.most_common(1)[0][0]
            table.add_row("Peak Commit Hour", f"{peak_hour:02d}:00")

        # Weekend vs weekday
        if s.weekday_counts:
            weekday_total = sum(s.weekday_counts.get(d, 0) for d in range(5))
            weekend_total = sum(s.weekday_counts.get(d, 0) for d in range(5, 7))
            table.add_row("Weekday Commits", f"{weekday_total:,}")
            table.add_row("Weekend Commits", f"{weekend_total:,}")
            if weekday_total > 0:
                ratio = weekend_total / weekday_total
                table.add_row("Weekend/Weekday Ratio", f"{ratio:.2f}")

        self.query_one("#overview-content", Static).update(table)

    def _render_commits(self) -> None:
        """Render the recent commits list."""
        if not self.stats or not self.stats.commits:
            self.query_one("#commits-content", Static).update("[dim]No commits found[/]")
            return

        table = Table(
            title=f"Recent Commits  ({self.stats.total_commits} total)",
            show_header=True,
            border_style="dim",
            title_style="bold magenta",
        )
        table.add_column("#", style="dim", width=5)
        table.add_column("Date", style="cyan", width=20)
        table.add_column("Author", style="yellow", min_width=14)
        table.add_column("Message", min_width=40)
        table.add_column("Files", justify="right", width=5)
        table.add_column("+/-", width=10)

        for i, c in enumerate(self.stats.commits[:100], 1):
            date_str = c.date.strftime("%Y-%m-%d %H:%M")
            msg = c.message[:60] + ("..." if len(c.message) > 60 else "")
            delta = f"[green]+{c.insertions}[/]/[red]-{c.deletions}[/]"
            table.add_row(
                str(i),
                date_str,
                c.author,
                msg,
                str(c.files_changed),
                delta,
            )

        if self.stats.total_commits > 100:
            table.add_row("", "", "", f"... and {self.stats.total_commits - 100} more", "", "")

        self.query_one("#commits-content", Static).update(table)

    def action_refresh(self) -> None:
        """Refresh stats."""
        self._load_stats()
        self.notify("Stats refreshed!")

    def action_find_repos(self) -> None:
        """Find git repos under current directory."""
        repos = find_git_repos(self.repo_path.parent)
        if not repos:
            self.notify("No git repos found", severity="warning")
            return
        self._discovered_repos = repos
        # Show repo list as notification
        lines = [f"Found {len(repos)} repos. Press [bold]s[/] then [bold]#N[/] to switch:"]
        for i, r in enumerate(repos[:10], 1):
            lines.append(f"  #{i} {r.name}")
        if len(repos) > 10:
            lines.append(f"  ... and {len(repos) - 10} more")
        self.notify("\n".join(lines))

    def action_toggle_date_filter(self) -> None:
        """Toggle the date filter input bar."""
        bar = self.query_one("#date-filter-bar")
        bar.display = not bar.display
        if bar.display:
            self.query_one("#date-input", Input).focus()

    def action_toggle_repo_switch(self) -> None:
        """Toggle the repo switch input bar."""
        bar = self.query_one("#repo-switch-bar")
        bar.display = not bar.display
        if bar.display:
            # Auto-discover repos if not done yet
            if not self._discovered_repos:
                self._discovered_repos = find_git_repos(self.repo_path.parent, max_depth=2)
            self.query_one("#repo-input", Input).focus()
            if self._discovered_repos:
                hint = "Discovered: " + ", ".join(
                    f"#{i+1}={r.name}" for i, r in enumerate(self._discovered_repos[:5])
                )
                self.notify(hint)


def main():
    """Entry point for the CLI."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="git-stats",
        description="Beautiful terminal UI for local git statistics",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Path to git repository (default: current directory)",
    )
    parser.add_argument(
        "--find",
        action="store_true",
        help="Find all git repos under the given path",
    )
    args = parser.parse_args()

    repo_path = Path(args.path).resolve()

    if not repo_path.exists():
        print(f"Error: path does not exist: {repo_path}", file=sys.stderr)
        sys.exit(1)

    if args.find:
        repos = find_git_repos(repo_path)
        if not repos:
            print(f"No git repos found under {repo_path}")
            sys.exit(0)
        print(f"Found {len(repos)} git repos:")
        for r in repos:
            print(f"  {r}")
        sys.exit(0)

    if not (repo_path / ".git").exists():
        print(f"Error: not a git repository: {repo_path}", file=sys.stderr)
        print("Tip: use --find to discover git repos under a directory", file=sys.stderr)
        sys.exit(1)

    app = GitStatsApp(repo_path=repo_path)
    app.run()


if __name__ == "__main__":
    main()
