"""Commit timeline widget - commit patterns by hour and weekday."""

from __future__ import annotations

from rich.table import Table

from src.git_reader import GitStats


HOUR_LABELS = [f"{h:02d}" for h in range(24)]
WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def build_hour_chart(stats: GitStats) -> Table:
    """Build a bar chart of commits by hour of day."""
    hour_counts = stats.hour_counts
    if not hour_counts:
        table = Table(title="Commits by Hour", show_header=True, border_style="dim")
        table.add_column("Hour", style="cyan")
        table.add_column("Commits", justify="right")
        table.add_row("No data", "-")
        return table

    max_count = max(hour_counts.values()) if hour_counts else 1
    total = sum(hour_counts.values())

    table = Table(
        title=f"Commits by Hour  ({total} total)",
        show_header=True,
        border_style="dim",
        title_style="bold magenta",
    )
    table.add_column("Hour", style="cyan", width=4)
    table.add_column("Commits", justify="right", width=7)
    table.add_column("Bar", min_width=30)

    for h in range(24):
        count = hour_counts.get(h, 0)
        bar_len = int(count / max_count * 30) if max_count > 0 else 0
        # Color: work hours (9-18) = green, off hours = dim
        if 9 <= h <= 18:
            bar_color = "green"
        elif 7 <= h <= 20:
            bar_color = "yellow"
        else:
            bar_color = "red"
        bar_str = "\u2588" * bar_len
        table.add_row(
            f"{h:02d}",
            str(count),
            f"[{bar_color}]{bar_str}[/]",
        )

    return table


def build_weekday_chart(stats: GitStats) -> Table:
    """Build a bar chart of commits by day of week."""
    weekday_counts = stats.weekday_counts
    if not weekday_counts:
        table = Table(title="Commits by Weekday", show_header=True, border_style="dim")
        table.add_column("Day", style="cyan")
        table.add_column("Commits", justify="right")
        table.add_row("No data", "-")
        return table

    max_count = max(weekday_counts.values()) if weekday_counts else 1
    total = sum(weekday_counts.values())

    table = Table(
        title=f"Commits by Weekday  ({total} total)",
        show_header=True,
        border_style="dim",
        title_style="bold magenta",
    )
    table.add_column("Day", style="cyan", width=4)
    table.add_column("Commits", justify="right", width=7)
    table.add_column("Bar", min_width=30)

    for wd in range(7):
        count = weekday_counts.get(wd, 0)
        bar_len = int(count / max_count * 30) if max_count > 0 else 0
        # Weekend = yellow, weekday = green
        bar_color = "yellow" if wd >= 5 else "green"
        bar_str = "\u2588" * bar_len
        table.add_row(
            WEEKDAY_LABELS[wd],
            str(count),
            f"[{bar_color}]{bar_str}[/]",
        )

    return table


def build_author_table(stats: GitStats, top_n: int = 10) -> Table:
    """Build a table of top contributors."""
    if not stats.author_counts:
        table = Table(title="Top Contributors", show_header=True, border_style="dim")
        table.add_column("Author", style="cyan")
        table.add_column("Commits", justify="right")
        table.add_row("No data", "-")
        return table

    total = sum(stats.author_counts.values())
    top_authors = stats.author_counts.most_common(top_n)
    max_count = top_authors[0][1] if top_authors else 1

    table = Table(
        title=f"Top Contributors  ({stats.total_authors} authors)",
        show_header=True,
        border_style="dim",
        title_style="bold magenta",
    )
    table.add_column("#", style="dim", width=3)
    table.add_column("Author", style="cyan", min_width=16)
    table.add_column("Commits", justify="right", width=7)
    table.add_column("Share", justify="right", width=6)
    table.add_column("Bar", min_width=20)

    for i, (author, count) in enumerate(top_authors, 1):
        pct = count / total * 100
        bar_len = int(count / max_count * 20)
        bar_str = "\u2588" * bar_len
        table.add_row(
            str(i),
            author,
            str(count),
            f"{pct:.1f}%",
            f"[green]{bar_str}[/]",
        )

    return table



