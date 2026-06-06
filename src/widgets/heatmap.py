"""Contribution heatmap widget - GitHub-style contribution graph."""

from __future__ import annotations

from datetime import date, timedelta

from textual.widgets import Static
from rich.text import Text
from rich.align import Align

from src.git_reader import GitStats


# Color levels for contribution cells (0-4)
CELL_COLORS = {
    0: "#161b22",  # empty - dark
    1: "#0e4429",  # level 1
    2: "#006d32",  # level 2
    3: "#26a641",  # level 3
    4: "#39d353",  # level 4 - brightest
}

MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
DAY_LABELS = ["Mon", "", "Wed", "", "Fri", "", ""]


def _level(count: int, thresholds: tuple[int, int, int] = (1, 3, 6, 10)) -> int:
    """Convert commit count to color level 0-4."""
    if count == 0:
        return 0
    if count < thresholds[0]:
        return 1
    if count < thresholds[1]:
        return 2
    if count < thresholds[2]:
        return 3
    return 4


def build_heatmap_text(stats: GitStats, weeks: int = 52) -> Text:
    """Build a Rich Text contribution heatmap (52 weeks x 7 days)."""
    today = date.today()
    # Find the Sunday of the current week
    end_date = today + timedelta(days=(6 - today.weekday()) % 7)
    start_date = end_date - timedelta(weeks=weeks - 1, days=end_date.weekday())
    # Adjust to start on Sunday
    start_date = start_date - timedelta(days=(start_date.weekday() + 1) % 7)

    # Build 7 rows x 52 cols grid
    grid: list[list[tuple[int, int]]] = []  # [(level, count), ...]
    for day_row in range(7):
        row = []
        for week_col in range(weeks):
            d = start_date + timedelta(weeks=week_col, days=day_row)
            count = stats.daily_counts.get(d, 0)
            row.append((_level(count), count))
        grid.append(row)

    # Build month labels
    month_positions: dict[int, str] = {}
    for week_col in range(weeks):
        d = start_date + timedelta(weeks=week_col)
        if d.month not in month_positions:
            month_positions[d.month] = MONTH_LABELS[d.month - 1]

    # Render as Rich Text with Unicode block characters
    text = Text()

    # Month header
    text.append("     ")  # space for day labels
    prev_month = -1
    for week_col in range(weeks):
        d = start_date + timedelta(weeks=week_col)
        if d.month != prev_month:
            label = MONTH_LABELS[d.month - 1]
            text.append(f"{label:<4}", style="dim")
            prev_month = d.month
        else:
            text.append("    ")

    text.append("\n")

    # Day rows
    for day_row in range(7):
        label = DAY_LABELS[day_row] if day_row < len(DAY_LABELS) else ""
        text.append(f"{label:<5}", style="dim")

        for week_col in range(weeks):
            level, count = grid[day_row][week_col]
            color = CELL_COLORS[level]
            # Use full block character
            text.append("\u2588\u2588", style=f"on {color}")
            # Tiny gap between weeks
            if week_col < weeks - 1:
                text.append(" ")

        text.append("\n")

    # Legend
    text.append("\n")
    text.append("     Less ", style="dim")
    for lvl in range(5):
        color = CELL_COLORS[lvl]
        text.append("\u2588\u2588", style=f"on {color}")
        text.append(" ")
    text.append(" More", style="dim")

    # Summary line
    total = sum(stats.daily_counts.values())
    streak = _current_streak(stats.daily_counts)
    text.append(f"\n     {total} contributions in the last year  ")
    text.append(f"Current streak: {streak} days", style="bold green")

    return text


def _current_streak(daily_counts: dict[date, int]) -> int:
    """Calculate current contribution streak."""
    today = date.today()
    streak = 0
    d = today
    while d in daily_counts and daily_counts[d] > 0:
        streak += 1
        d -= timedelta(days=1)
    # Check if today has no commits yet - start from yesterday
    if streak == 0:
        d = today - timedelta(days=1)
        while d in daily_counts and daily_counts[d] > 0:
            streak += 1
            d -= timedelta(days=1)
    return streak


class HeatmapWidget(Static):
    """A Textual widget that renders the contribution heatmap."""

    DEFAULT_CSS = """
    HeatmapWidget {
        height: auto;
        padding: 1 2;
        border: solid $primary;
        border-title-style: bold magenta;
    }
    """

    def __init__(self, stats: GitStats, **kwargs):
        super().__init__(**kwargs)
        self.stats = stats
        self.border_title = f"  Contribution Heatmap - {stats.repo_name}  "

    def on_mount(self) -> None:
        heatmap = build_heatmap_text(self.stats)
        self.update(Align.center(heatmap))
