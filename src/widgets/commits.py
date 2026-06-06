"""Commits widget - recent commit list with insertions/deletions."""

from __future__ import annotations

from textual.widgets import Static
from rich.table import Table

from src.git_reader import GitStats


def build_commits_table(stats: GitStats, max_rows: int = 100) -> Table:
    """Build a Rich Table with recent commits."""
    if not stats.commits:
        # Return a minimal table with a message
        table = Table(title="\u63d0\u4ea4\u8bb0\u5f55", show_header=False, border_style="dim")
        table.add_column("msg", style="dim")
        table.add_row("\u6682\u65e0\u63d0\u4ea4\u8bb0\u5f55")
        return table

    table = Table(
        title=f"\u63d0\u4ea4\u8bb0\u5f55  (\u5171 {stats.total_commits} \u6b21)",
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

    for i, c in enumerate(stats.commits[:max_rows], 1):
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

    if stats.total_commits > max_rows:
        table.add_row("", "", "", f"... \u8fd8\u6709 {stats.total_commits - max_rows} \u6b21\u63d0\u4ea4", "", "")

    return table


class CommitsWidget(Static):
    """A Textual widget that renders the recent commits list."""

    DEFAULT_CSS = """
    CommitsWidget {
        height: auto;
        padding: 1 2;
    }
    """

    def __init__(self, stats: GitStats, **kwargs):
        super().__init__(**kwargs)
        self.stats = stats

    def on_mount(self) -> None:
        table = build_commits_table(self.stats)
        self.update(table)

    def update_stats(self, stats: GitStats) -> None:
        """Update with new stats."""
        self.stats = stats
        table = build_commits_table(stats)
        self.update(table)
