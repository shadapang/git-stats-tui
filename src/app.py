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
    SUB_TITLE = "Git \u7edf\u8ba1\u4eea\u8868\u76d8"

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

    .filter-label {
        color: $text-primary;
        text-style: bold;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "\u9000\u51fa", show=True),
        Binding("r", "refresh", "\u5237\u65b0", show=True),
        Binding("f", "find_repos", "\u627e\u4ed3\u5e93", show=True),
        Binding("d", "toggle_date_filter", "\u65e5\u671f\u7b5b\u9009", show=True),
        Binding("s", "toggle_repo_switch", "\u5207\u4ed3\u5e93", show=True),
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
                yield Static("\u65e5\u671f\u8303\u56f4 (YYYY-MM-DD ~ YYYY-MM-DD): ", classes="filter-label")
                yield Input(placeholder="\u5982 2025-01-01 ~ 2025-12-31", id="date-input")
            # Repo switch bar (hidden by default)
            with Horizontal(id="repo-switch-bar"):
                yield Static("\u4ed3\u5e93\u8def\u5f84: ", classes="filter-label")
                yield Input(placeholder="\u8def\u5f84/\u5230/\u4ed3\u5e93 \u6216 #N \u9009\u5df2\u53d1\u73b0\u4ed3\u5e93", id="repo-input")
            yield Static(id="repo-info")
            with TabbedContent():
                with TabPane("\u70ed\u529b\u56fe", id="tab-heatmap"):
                    with VerticalScroll(classes="tab-content"):
                        yield Static(id="heatmap-content")
                with TabPane("\u8bed\u8a00\u5206\u5e03", id="tab-languages"):
                    with VerticalScroll(classes="tab-content"):
                        yield Static(id="lang-content")
                with TabPane("\u65f6\u95f4\u7ebf", id="tab-timeline"):
                    with VerticalScroll(classes="tab-content"):
                        yield Static(id="timeline-content")
                with TabPane("\u63d0\u4ea4\u8bb0\u5f55", id="tab-commits"):
                    with VerticalScroll(classes="tab-content"):
                        yield Static(id="commits-content")
                with TabPane("\u6982\u89c8", id="tab-overview"):
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
            self.notify("\u65e5\u671f\u7b5b\u9009\u5df2\u6e05\u9664")
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
                self.notify(f"\u5df2\u7b5b\u9009: {start} ~ {end}")
            else:
                self.notify("\u683c\u5f0f: YYYY-MM-DD ~ YYYY-MM-DD", severity="error")
        except (ValueError, IndexError):
            self.notify("\u65e5\u671f\u683c\u5f0f\u65e0\u6548", severity="error")

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
                self.notify(f"\u5df2\u5207\u6362\u5230: {self.repo_path.name}")
                return
            else:
                self.notify(f"\u65e0\u6548\u4ed3\u5e93\u5e8f\u53f7 (1-{len(self._discovered_repos)})", severity="error")
                return

        # Try as a path
        new_path = Path(value).resolve()
        if (new_path / ".git").exists():
            self.repo_path = new_path
            self._date_filter = None
            self._load_stats()
            self.notify(f"\u5df2\u5207\u6362\u5230: {self.repo_path.name}")
        else:
            self.notify(f"\u4e0d\u662f git \u4ed3\u5e93: {new_path}", severity="error")

    def _load_stats(self) -> None:
        """Load git stats and render all widgets."""
        try:
            self.stats = compute_stats(self.repo_path)
        except Exception as e:
            self.query_one("#repo-info", Static).update(
                f"[red]\u52a0\u8f7d\u4ed3\u5e93\u51fa\u9519: {e}[/]"
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
        info.append(f"\u5206\u652f ", style="dim")
        info.append(f"{s.current_branch}", style="cyan")
        info.append(f"  |  ", style="dim")
        info.append(f"{s.total_commits}", style="bold green")
        info.append(f" \u6b21\u63d0\u4ea4  ", style="dim")
        info.append(f"{s.total_authors}", style="bold yellow")
        info.append(f" \u4f4d\u4f5c\u8005  ", style="dim")
        info.append(f"{s.total_branches}", style="bold blue")
        info.append(f" \u4e2a\u5206\u652f", style="dim")
        if s.first_commit_date and s.last_commit_date:
            days = (s.last_commit_date - s.first_commit_date).days
            info.append(f"  |  ", style="dim")
            info.append(f"{days}", style="bold")
            info.append(f" \u5929\u6d3b\u8dc3", style="dim")
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
            title=f"\u6982\u89c8 - {s.repo_name}",
            show_header=False,
            border_style="dim",
            title_style="bold magenta",
        )
        table.add_column("\u6307\u6807", style="cyan", min_width=20)
        table.add_column("\u6570\u503c", style="bold", min_width=20)

        table.add_row("\u603b\u63d0\u4ea4\u6570", f"{s.total_commits:,}")
        table.add_row("\u603b\u4f5c\u8005\u6570", f"{s.total_authors:,}")
        table.add_row("\u5f53\u524d\u5206\u652f", s.current_branch)
        table.add_row("\u603b\u5206\u652f\u6570", str(s.total_branches))

        if s.first_commit_date and s.last_commit_date:
            table.add_row("\u9996\u6b21\u63d0\u4ea4", str(s.first_commit_date))
            table.add_row("\u6700\u65b0\u63d0\u4ea4", str(s.last_commit_date))
            days = (s.last_commit_date - s.first_commit_date).days
            table.add_row("\u6d3b\u8dc3\u5929\u6570", f"{days:,}")
            if days > 0:
                table.add_row("\u65e5\u5747\u63d0\u4ea4", f"{s.total_commits / days:.1f}")

        # Top language
        if s.language_counts:
            top_lang, top_count = s.language_counts.most_common(1)[0]
            table.add_row("\u4e3b\u529b\u8bed\u8a00", f"{top_lang} ({top_count} \u4e2a\u6587\u4ef6)")

        # Top author
        if s.author_counts:
            top_author, top_commits = s.author_counts.most_common(1)[0]
            table.add_row("\u6700\u6d3b\u8dc3\u4f5c\u8005", f"{top_author} ({top_commits} \u6b21\u63d0\u4ea4)")

        # Peak hour
        if s.hour_counts:
            peak_hour = s.hour_counts.most_common(1)[0][0]
            table.add_row("\u63d0\u4ea4\u9ad8\u5cf0\u65f6\u6bb5", f"{peak_hour:02d}:00")

        # Weekend vs weekday
        if s.weekday_counts:
            weekday_total = sum(s.weekday_counts.get(d, 0) for d in range(5))
            weekend_total = sum(s.weekday_counts.get(d, 0) for d in range(5, 7))
            table.add_row("\u5de5\u4f5c\u65e5\u63d0\u4ea4", f"{weekday_total:,}")
            table.add_row("\u5468\u672b\u63d0\u4ea4", f"{weekend_total:,}")
            if weekday_total > 0:
                ratio = weekend_total / weekday_total
                table.add_row("\u5468\u672b/\u5de5\u4f5c\u65e5\u6bd4", f"{ratio:.2f}")

        self.query_one("#overview-content", Static).update(table)

    def _render_commits(self) -> None:
        """Render the recent commits list."""
        if not self.stats or not self.stats.commits:
            self.query_one("#commits-content", Static).update("[dim]\u6682\u65e0\u63d0\u4ea4\u8bb0\u5f55[/]")
            return

        table = Table(
            title=f"\u63d0\u4ea4\u8bb0\u5f55  (\u5171 {self.stats.total_commits} \u6b21)",
            show_header=True,
            border_style="dim",
            title_style="bold magenta",
        )
        table.add_column("#", style="dim", width=5)
        table.add_column("\u65e5\u671f", style="cyan", width=20)
        table.add_column("\u4f5c\u8005", style="yellow", min_width=14)
        table.add_column("\u63d0\u4ea4\u4fe1\u606f", min_width=40)
        table.add_column("\u6587\u4ef6", justify="right", width=5)
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
            table.add_row("", "", "", f"... \u8fd8\u6709 {self.stats.total_commits - 100} \u6b21\u63d0\u4ea4", "", "")

        self.query_one("#commits-content", Static).update(table)

    def action_refresh(self) -> None:
        """Refresh stats."""
        self._load_stats()
        self.notify("\u5df2\u5237\u65b0!")

    def action_find_repos(self) -> None:
        """Find git repos under current directory."""
        repos = find_git_repos(self.repo_path.parent)
        if not repos:
            self.notify("\u672a\u627e\u5230 git \u4ed3\u5e93", severity="warning")
            return
        self._discovered_repos = repos
        # Show repo list as notification
        lines = [f"\u627e\u5230 {len(repos)} \u4e2a\u4ed3\u5e93\u3002\u6309 [bold]s[/] \u7136\u540e [bold]#N[/] \u5207\u6362:"]
        for i, r in enumerate(repos[:10], 1):
            lines.append(f"  #{i} {r.name}")
        if len(repos) > 10:
            lines.append(f"  ... \u8fd8\u6709 {len(repos) - 10} \u4e2a")
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
                hint = "\u5df2\u53d1\u73b0: " + ", ".join(
                    f"#{i+1}={r.name}" for i, r in enumerate(self._discovered_repos[:5])
                )
                self.notify(hint)


def main():
    """Entry point for the CLI."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="git-stats",
        description="Git \u7edf\u8ba1\u53ef\u89c6\u5316\u5de5\u5177 - \u7ec8\u7aef\u754c\u9762",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="\u4ed3\u5e93\u8def\u5f84 (\u9ed8\u8ba4: \u5f53\u524d\u76ee\u5f55)",
    )
    parser.add_argument(
        "--find",
        action="store_true",
        help="\u67e5\u627e\u76ee\u5f55\u4e0b\u6240\u6709 git \u4ed3\u5e93",
    )
    args = parser.parse_args()

    repo_path = Path(args.path).resolve()

    if not repo_path.exists():
        print(f"\u9519\u8bef: \u8def\u5f84\u4e0d\u5b58\u5728: {repo_path}", file=sys.stderr)
        sys.exit(1)

    if args.find:
        repos = find_git_repos(repo_path)
        if not repos:
            print(f"\u672a\u627e\u5230 git \u4ed3\u5e93: {repo_path}")
            sys.exit(0)
        print(f"\u627e\u5230 {len(repos)} \u4e2a git \u4ed3\u5e93:")
        for r in repos:
            print(f"  {r}")
        sys.exit(0)

    if not (repo_path / ".git").exists():
        print(f"\u9519\u8bef: \u4e0d\u662f git \u4ed3\u5e93: {repo_path}", file=sys.stderr)
        print("\u63d0\u793a: \u7528 --find \u67e5\u627e\u76ee\u5f55\u4e0b\u7684 git \u4ed3\u5e93", file=sys.stderr)
        sys.exit(1)

    app = GitStatsApp(repo_path=repo_path)
    app.run()


if __name__ == "__main__":
    main()
