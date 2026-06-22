"""Commit trend widget - weekly and monthly commit trends."""

from __future__ import annotations

from datetime import date, timedelta
from collections import defaultdict

from rich.table import Table
from rich.text import Text

from src.git_reader import GitStats


# Sparkline characters (8 levels from low to high)
SPARK_CHARS = " ▁▂▃▄▅▆█"


def _sparkline(values: list[int], width: int = 40) -> Text:
    """Build a sparkline from a list of values using Unicode block chars."""
    if not values or max(values) == 0:
        return Text("  (no data)", style="dim")

    max_val = max(values)
    text = Text()
    # Sample down to width if needed
    if len(values) > width:
        step = len(values) / width
        sampled = [values[int(i * step)] for i in range(width)]
    else:
        sampled = values

    for v in sampled:
        level = int(v / max_val * 7) if max_val > 0 else 0
        level = min(level, 7)
        ch = SPARK_CHARS[level]
        # Color based on level
        if level >= 5:
            style = "bold green"
        elif level >= 3:
            style = "green"
        elif level >= 1:
            style = "dim"
        else:
            style = "dim"
        text.append(ch, style=style)

    return text


def build_weekly_trend(stats: GitStats, weeks: int = 26) -> Table:
    """Build a weekly commit trend for the last N weeks."""
    today = date.today()
    # Find the Sunday of the current week
    current_week_sunday = today - timedelta(days=(today.weekday() + 1) % 7)
    # Go back (weeks - 1) weeks to get the start of the oldest week
    window_start = current_week_sunday - timedelta(weeks=weeks - 1)

    # Aggregate commits by week
    weekly: dict[date, int] = defaultdict(int)
    for c in stats.commits:
        d = c.date.date()
        # Find the start of the week (Sunday)
        week_start = d - timedelta(days=(d.weekday() + 1) % 7)
        if window_start <= week_start <= current_week_sunday:
            weekly[week_start] += 1

    # Build ordered list
    labels = []
    values = []
    for i in range(weeks):
        ws = window_start + timedelta(weeks=i)
        labels.append(ws.strftime("%m-%d"))
        values.append(weekly.get(ws, 0))

    total = sum(values)
    max_val = max(values) if values else 1

    table = Table(
        title=f"每周提交趋势  (近 {weeks} 周, 共 {total} 次)",
        show_header=False,
        border_style="dim",
        title_style="bold magenta",
    )
    table.add_column("周", style="dim", width=6)
    table.add_column("数量", justify="right", width=5)
    table.add_column("趋势", min_width=30)

    # Show every 4th label to avoid crowding
    for i in range(weeks):
        label = labels[i] if i % 4 == 0 else ""
        count = values[i]
        bar_len = int(count / max_val * 25) if max_val > 0 else 0
        bar = "█" * bar_len
        if count >= max_val * 0.8:
            bar_style = "bold green"
        elif count >= max_val * 0.5:
            bar_style = "green"
        elif count > 0:
            bar_style = "dim"
        else:
            bar_style = "dim"
        table.add_row(label, str(count), f"[{bar_style}]{bar}[/]")

    # Sparkline summary
    spark = _sparkline(values)
    table.add_row("", "", spark)

    return table


def build_monthly_trend(stats: GitStats, months: int = 12) -> Table:
    """Build a monthly commit trend for the last N months."""
    today = date.today()
    # Go back N months
    year = today.year
    month = today.month
    end_year, end_month = year, month

    monthly: dict[tuple[int, int], int] = defaultdict(int)
    for c in stats.commits:
        d = c.date.date()
        monthly[(d.year, d.month)] += 1

    # Build ordered list
    labels = []
    values = []
    for i in range(months - 1, -1, -1):
        m = month - i
        y = year
        while m <= 0:
            m += 12
            y -= 1
        labels.append(f"{y}-{m:02d}")
        values.append(monthly.get((y, m), 0))

    total = sum(values)
    max_val = max(values) if values else 1

    table = Table(
        title=f"每月提交趋势  (近 {months} 个月, 共 {total} 次)",
        show_header=False,
        border_style="dim",
        title_style="bold magenta",
    )
    table.add_column("月", style="dim", width=8)
    table.add_column("数量", justify="right", width=5)
    table.add_column("趋势", min_width=30)

    for i in range(months):
        count = values[i]
        bar_len = int(count / max_val * 25) if max_val > 0 else 0
        bar = "█" * bar_len
        if count >= max_val * 0.8:
            bar_style = "bold green"
        elif count >= max_val * 0.5:
            bar_style = "green"
        elif count > 0:
            bar_style = "dim"
        else:
            bar_style = "dim"
        table.add_row(labels[i], str(count), f"[{bar_style}]{bar}[/]")

    # Sparkline summary
    spark = _sparkline(values)
    table.add_row("", "", spark)

    return table
