"""Overview widget - summary of all key stats."""

from __future__ import annotations

from textual.widgets import Static
from rich.table import Table

from src.git_reader import GitStats


def build_overview_table(stats: GitStats) -> Table:
    """Build a Rich Table with all key stats at a glance."""
    s = stats
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

    return table


class OverviewWidget(Static):
    """A Textual widget that renders the overview summary."""

    DEFAULT_CSS = """
    OverviewWidget {
        height: auto;
        padding: 1 2;
    }
    """

    def __init__(self, stats: GitStats, **kwargs):
        super().__init__(**kwargs)
        self.stats = stats

    def on_mount(self) -> None:
        table = build_overview_table(self.stats)
        self.update(table)

    def update_stats(self, stats: GitStats) -> None:
        """Update with new stats."""
        self.stats = stats
        table = build_overview_table(stats)
        self.update(table)
