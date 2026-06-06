"""Language breakdown widget - bar chart of languages by file count."""

from __future__ import annotations

from rich.table import Table

from src.git_reader import GitStats


# Distinct colors for top languages
LANG_COLORS = [
    "#3572A5",  # blue (Python)
    "#F1E05A",  # yellow (JS)
    "#2B7489",  # teal (TS)
    "#DEA584",  # orange (Rust)
    "#00ADD8",  # cyan (Go)
    "#B07219",  # brown (Java)
    "#701516",  # red (Ruby)
    "#4F5D95",  # purple (PHP)
    "#555555",  # gray (C)
    "#f34b7d",  # pink (C++)
    "#178600",  # green (C#)
    "#FA7343",  # orange (Swift)
    "#A97BFF",  # violet (Kotlin)
    "#6E4C7E",  # purple (Elixir)
    "#DB5856",  # red (Dart)
]


def build_language_table(stats: GitStats, top_n: int = 12) -> Table:
    """Build a Rich Table showing language breakdown."""
    lang_counts = stats.language_counts
    if not lang_counts:
        table = Table(title="Language Breakdown", show_header=True, border_style="dim")
        table.add_column("Language", style="cyan")
        table.add_column("Files", justify="right")
        table.add_row("No files found", "-")
        return table

    total = sum(lang_counts.values())
    top_langs = lang_counts.most_common(top_n)

    table = Table(
        title=f"Language Breakdown  ({total:,} lines)",
        show_header=True,
        border_style="dim",
        title_style="bold magenta",
    )
    table.add_column("Language", style="cyan", min_width=14)
    table.add_column("Lines", justify="right", width=8)
    table.add_column("Share", justify="right", width=6)
    table.add_column("Bar", min_width=20)

    max_count = top_langs[0][1] if top_langs else 1

    for i, (lang, count) in enumerate(top_langs):
        pct = count / total * 100
        bar_width = int(count / max_count * 20)
        color = LANG_COLORS[i % len(LANG_COLORS)]
        bar_str = "\u2588" * bar_width
        table.add_row(
            lang,
            str(count),
            f"{pct:.1f}%",
            f"[{color}]{bar_str}[/]",
        )

    # Other
    if len(lang_counts) > top_n:
        other_count = total - sum(c for _, c in top_langs)
        pct = other_count / total * 100
        table.add_row(
            f"Other ({len(lang_counts) - top_n})",
            str(other_count),
            f"{pct:.1f}%",
            f"[dim]{'?' * int(other_count / max_count * 20)}[/]",
        )

    return table



