"""git-stats-tui main application - Textual TUI for local git statistics."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from datetime import date

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, Footer, Static, TabbedContent, TabPane, Input
from textual.containers import VerticalScroll, Horizontal, Vertical
from rich.text import Text
from rich.align import Align
from rich.console import Group

from src.git_reader import GitStats, compute_stats, find_git_repos, filter_by_date
from src.widgets.heatmap import build_heatmap_text
from src.widgets.languages import build_language_table
from src.widgets.timeline import build_hour_chart, build_weekday_chart, build_author_table
from src.widgets.overview import build_overview_table
from src.widgets.commits import build_commits_table


class GitStatsApp(App):
    """A beautiful TUI for local git statistics."""

    TITLE = "git-stats-tui"
    SUB_TITLE = "Git 统计仪表盘"

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
        Binding("q", "quit", "退出", show=True),
        Binding("r", "refresh", "刷新", show=True),
        Binding("f", "find_repos", "找仓库", show=True),
        Binding("d", "toggle_date_filter", "日期筛选", show=True),
        Binding("s", "toggle_repo_switch", "切仓库", show=True),
    ]

    def __init__(self, repo_path: Path | None = None, since: date | None = None, until: date | None = None, **kwargs):
        super().__init__(**kwargs)
        self.repo_path = repo_path or Path.cwd()
        self.stats: GitStats | None = None
        self._date_filter: tuple[date, date] | None = None
        self._discovered_repos: list[Path] = []
        # Apply CLI --since/--until as initial date filter
        self._initial_since = since
        self._initial_until = until

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main-content"):
            # Date filter bar (hidden by default)
            with Horizontal(id="date-filter-bar"):
                yield Static("日期范围 (YYYY-MM-DD ~ YYYY-MM-DD): ", classes="filter-label")
                yield Input(placeholder="如 2025-01-01 ~ 2025-12-31", id="date-input")
            # Repo switch bar (hidden by default)
            with Horizontal(id="repo-switch-bar"):
                yield Static("仓库路径: ", classes="filter-label")
                yield Input(placeholder="路径/到/仓库 或 #N 选已发现仓库", id="repo-input")
            yield Static(id="repo-info")
            with TabbedContent():
                with TabPane("热力图", id="tab-heatmap"):
                    with VerticalScroll(classes="tab-content"):
                        yield Static(id="heatmap-content")
                with TabPane("语言分布", id="tab-languages"):
                    with VerticalScroll(classes="tab-content"):
                        yield Static(id="lang-content")
                with TabPane("时间线", id="tab-timeline"):
                    with VerticalScroll(classes="tab-content"):
                        yield Static(id="timeline-content")
                with TabPane("提交记录", id="tab-commits"):
                    with VerticalScroll(classes="tab-content"):
                        yield Static(id="commits-content")
                with TabPane("概览", id="tab-overview"):
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
            self.notify("日期筛选已清除")
            return

        try:
            # Parse "YYYY-MM-DD ~ YYYY-MM-DD" or "YYYY-MM-DD - YYYY-MM-DD"
            parts = re.split(r"\s*[~-]\s*", value)
            if len(parts) == 2:
                start = date.fromisoformat(parts[0])
                end = date.fromisoformat(parts[1])
                self._date_filter = (start, end)
                self._load_stats()
                self.notify(f"已筛选: {start} ~ {end}")
            else:
                self.notify("格式: YYYY-MM-DD ~ YYYY-MM-DD", severity="error")
        except (ValueError, IndexError):
            self.notify("日期格式无效", severity="error")

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
                self.notify(f"已切换到: {self.repo_path.name}")
                return
            else:
                self.notify(f"无效仓库序号 (1-{len(self._discovered_repos)})", severity="error")
                return

        # Try as a path
        new_path = Path(value).resolve()
        if (new_path / ".git").exists():
            self.repo_path = new_path
            self._date_filter = None
            self._load_stats()
            self.notify(f"已切换到: {self.repo_path.name}")
        else:
            self.notify(f"不是 git 仓库: {new_path}", severity="error")

    def _load_stats(self) -> None:
        """Load git stats and render all widgets."""
        try:
            self.stats = compute_stats(self.repo_path)
        except Exception as e:
            self.query_one("#repo-info", Static).update(
                f"[red]加载仓库出错: {e}[/]"
            )
            return

        # Apply CLI --since/--until as initial date filter (once)
        if self._initial_since or self._initial_until:
            if self.stats:
                start = self._initial_since or self.stats.first_commit_date or date.min
                end = self._initial_until or self.stats.last_commit_date or date.max
                self.stats = filter_by_date(self.stats, start, end)
                self._date_filter = (start, end)
            self._initial_since = None
            self._initial_until = None

        # Apply date filter if set (pure function — no mutation)
        if self._date_filter and self.stats:
            start, end = self._date_filter
            self.stats = filter_by_date(self.stats, start, end)

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
        info.append("分支 ", style="dim")
        info.append(f"{s.current_branch}", style="cyan")
        info.append("  |  ", style="dim")
        info.append(f"{s.total_commits}", style="bold green")
        info.append(" 次提交  ", style="dim")
        info.append(f"{s.total_authors}", style="bold yellow")
        info.append(" 位作者  ", style="dim")
        info.append(f"{s.total_branches}", style="bold blue")
        info.append(" 个分支", style="dim")
        if s.first_commit_date and s.last_commit_date:
            days = (s.last_commit_date - s.first_commit_date).days
            info.append("  |  ", style="dim")
            info.append(f"{days}", style="bold")
            info.append(" 天活跃", style="dim")
        self.query_one("#repo-info", Static).update(info)

    def _render_heatmap(self) -> None:
        """Render the contribution heatmap."""
        if not self.stats:
            return
        heatmap = build_heatmap_text(self.stats)
        self.query_one("#heatmap-content", Static).update(Align.center(heatmap))

    def _render_languages(self) -> None:
        """Render the language breakdown."""
        if not self.stats:
            return
        table = build_language_table(self.stats)
        self.query_one("#lang-content", Static).update(table)

    def _render_timeline(self) -> None:
        """Render the commit timeline."""
        if not self.stats:
            return
        hour = build_hour_chart(self.stats)
        weekday = build_weekday_chart(self.stats)
        authors = build_author_table(self.stats)
        self.query_one("#timeline-content", Static).update(Group(hour, weekday, authors))

    def _render_overview(self) -> None:
        """Render the overview tab with all key stats."""
        if not self.stats:
            return
        table = build_overview_table(self.stats)
        self.query_one("#overview-content", Static).update(table)

    def _render_commits(self) -> None:
        """Render the recent commits list."""
        if not self.stats:
            return
        table = build_commits_table(self.stats)
        self.query_one("#commits-content", Static).update(table)

    def action_refresh(self) -> None:
        """Refresh stats."""
        self._load_stats()
        self.notify("已刷新!")

    def action_find_repos(self) -> None:
        """Find git repos under current directory."""
        repos = find_git_repos(self.repo_path.parent)
        if not repos:
            self.notify("未找到 git 仓库", severity="warning")
            return
        self._discovered_repos = repos
        # Show repo list as notification
        lines = [f"找到 {len(repos)} 个仓库。按 [bold]s[/] 然后 [bold]#N[/] 切换:"]
        for i, r in enumerate(repos[:10], 1):
            lines.append(f"  #{i} {r.name}")
        if len(repos) > 10:
            lines.append(f"  ... 还有 {len(repos) - 10} 个")
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
                hint = "已发现: " + ", ".join(
                    f"#{i+1}={r.name}" for i, r in enumerate(self._discovered_repos[:5])
                )
                self.notify(hint)


def main():
    """Entry point for the CLI."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="git-stats",
        description="Git 统计可视化工具 - 终端界面",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="仓库路径 (默认: 当前目录)",
    )
    parser.add_argument(
        "--find",
        action="store_true",
        help="查找目录下所有 git 仓库",
    )
    parser.add_argument(
        "--export",
        choices=["json"],
        help="导出统计数据为 JSON 并输出到 stdout",
    )
    parser.add_argument(
        "--since",
        type=date.fromisoformat,
        metavar="YYYY-MM-DD",
        help="起始日期筛选 (含)",
    )
    parser.add_argument(
        "--until",
        type=date.fromisoformat,
        metavar="YYYY-MM-DD",
        help="截止日期筛选 (含)",
    )
    args = parser.parse_args()

    repo_path = Path(args.path).resolve()

    if not repo_path.exists():
        print(f"错误: 路径不存在: {repo_path}", file=sys.stderr)
        sys.exit(1)

    if args.find:
        repos = find_git_repos(repo_path)
        if not repos:
            print(f"未找到 git 仓库: {repo_path}")
            sys.exit(0)
        print(f"找到 {len(repos)} 个 git 仓库:")
        for r in repos:
            print(f"  {r}")
        sys.exit(0)

    if not (repo_path / ".git").exists():
        print(f"错误: 不是 git 仓库: {repo_path}", file=sys.stderr)
        print("提示: 用 --find 查找目录下的 git 仓库", file=sys.stderr)
        sys.exit(1)

    # --export json: compute stats and dump to stdout, no TUI
    if args.export == "json":
        import json
        stats = compute_stats(repo_path)
        if args.since or args.until:
            start = args.since or stats.first_commit_date or date.min
            end = args.until or stats.last_commit_date or date.max
            stats = filter_by_date(stats, start, end)
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
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        sys.exit(0)

    app = GitStatsApp(repo_path=repo_path, since=args.since, until=args.until)
    app.run()


if __name__ == "__main__":
    main()
