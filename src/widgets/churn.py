"""File churn widget - most frequently changed files."""

from __future__ import annotations

from rich.table import Table

from src.git_reader import GitStats


def build_churn_table(stats: GitStats, top_n: int = 20) -> Table:
    """Build a table of most frequently changed files."""
    if not stats.file_churn:
        table = Table(title="文件热度", show_header=True, border_style="dim")
        table.add_column("文件", style="cyan")
        table.add_column("修改次数", justify="right")
        table.add_row("暂无数据", "-")
        return table

    total_commits = stats.total_commits or 1
    top_files = stats.file_churn.most_common(top_n)
    max_count = top_files[0][1] if top_files else 1

    table = Table(
        title=f"文件热度  (共 {len(stats.file_churn)} 个文件被修改过)",
        show_header=True,
        border_style="dim",
        title_style="bold magenta",
    )
    table.add_column("#", style="dim", width=3)
    table.add_column("文件路径", style="cyan", min_width=30)
    table.add_column("修改次数", justify="right", width=8)
    table.add_column("占比", justify="right", width=6)
    table.add_column("热度", min_width=20)

    # Color gradient: red (most) -> yellow -> green (least)
    for i, (filepath, count) in enumerate(top_files, 1):
        pct = count / total_commits * 100
        bar_len = int(count / max_count * 20)
        # Color intensity based on rank
        if i <= 5:
            color = "red"
        elif i <= 10:
            color = "yellow"
        else:
            color = "green"
        bar_str = "█" * bar_len
        table.add_row(
            str(i),
            filepath,
            str(count),
            f"{pct:.1f}%",
            f"[{color}]{bar_str}[/]",
        )

    # Summary
    table.add_row("", "", "", "", "")
    table.add_row(
        "",
        f"[dim]Top 5 占总提交的 "
        f"{sum(c for _, c in top_files[:5]) / total_commits * 100:.1f}%[/]",
        "", "",
        "",
    )

    return table
