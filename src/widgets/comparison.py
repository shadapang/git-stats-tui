"""Repo comparison widget - side-by-side comparison of two repos."""

from __future__ import annotations

from rich.table import Table

from src.git_reader import GitStats


def build_comparison_table(stats_a: GitStats, stats_b: GitStats) -> Table:
    """Build a side-by-side comparison table of two repos."""
    a, b = stats_a, stats_b

    table = Table(
        title=f"仓库对比: {a.repo_name} vs {b.repo_name}",
        show_header=True,
        border_style="dim",
        title_style="bold magenta",
    )
    table.add_column("指标", style="cyan", min_width=18)
    table.add_column(a.repo_name, justify="right", min_width=18)
    table.add_column(b.repo_name, justify="right", min_width=18)
    table.add_column("差异", justify="right", min_width=12)

    def _diff(va: int, vb: int) -> str:
        d = vb - va
        if d > 0:
            return f"[green]+{d:,}[/]"
        elif d < 0:
            return f"[red]{d:,}[/]"
        return "[dim]0[/]"

    def _diff_pct(va: int, vb: int) -> str:
        if va == 0:
            return "[dim]-[/]"
        d = (vb - va) / va * 100
        if d > 0:
            return f"[green]+{d:.1f}%[/]"
        elif d < 0:
            return f"[red]{d:.1f}%[/]"
        return "[dim]0%[/]"

    # Basic stats
    table.add_row("总提交数", f"{a.total_commits:,}", f"{b.total_commits:,}",
                   _diff(a.total_commits, b.total_commits))
    table.add_row("作者数", f"{a.total_authors:,}", f"{b.total_authors:,}",
                   _diff(a.total_authors, b.total_authors))
    table.add_row("分支数", f"{a.total_branches}", f"{b.total_branches}",
                   _diff(a.total_branches, b.total_branches))

    # Date range
    a_days = (a.last_commit_date - a.first_commit_date).days if a.first_commit_date and a.last_commit_date else 0
    b_days = (b.last_commit_date - b.first_commit_date).days if b.first_commit_date and b.last_commit_date else 0
    table.add_row("活跃天数", f"{a_days:,}", f"{b_days:,}", _diff(a_days, b_days))

    # Daily average
    a_avg = a.total_commits / a_days if a_days > 0 else 0
    b_avg = b.total_commits / b_days if b_days > 0 else 0
    table.add_row("日均提交", f"{a_avg:.1f}", f"{b_avg:.1f}",
                   _diff_pct(int(a_avg * 10), int(b_avg * 10)))

    # Top language
    a_lang = a.language_counts.most_common(1)[0][0] if a.language_counts else "-"
    b_lang = b.language_counts.most_common(1)[0][0] if b.language_counts else "-"
    table.add_row("主力语言", a_lang, b_lang, "")

    # Top author
    a_author = a.author_counts.most_common(1)[0][0] if a.author_counts else "-"
    b_author = b.author_counts.most_common(1)[0][0] if b.author_counts else "-"
    table.add_row("最活跃作者", a_author, b_author, "")

    # Peak hour
    a_peak = f"{a.hour_counts.most_common(1)[0][0]:02d}:00" if a.hour_counts else "-"
    b_peak = f"{b.hour_counts.most_common(1)[0][0]:02d}:00" if b.hour_counts else "-"
    table.add_row("提交高峰", a_peak, b_peak, "")

    # Weekend ratio
    if a.weekday_counts and b.weekday_counts:
        a_wd = sum(a.weekday_counts.get(d, 0) for d in range(5))
        a_we = sum(a.weekday_counts.get(d, 0) for d in range(5, 7))
        b_wd = sum(b.weekday_counts.get(d, 0) for d in range(5))
        b_we = sum(b.weekday_counts.get(d, 0) for d in range(5, 7))
        a_ratio = f"{a_we / a_wd:.2f}" if a_wd > 0 else "-"
        b_ratio = f"{b_we / b_wd:.2f}" if b_wd > 0 else "-"
        table.add_row("周末/工作日比", a_ratio, b_ratio, "")

    return table


def build_language_comparison(stats_a: GitStats, stats_b: GitStats, top_n: int = 8) -> Table:
    """Build a language breakdown comparison table."""
    a, b = stats_a, stats_b

    a_total = sum(a.language_counts.values()) or 1
    b_total = sum(b.language_counts.values()) or 1

    # Merge top languages from both repos
    all_langs = set(a.language_counts.keys()) | set(b.language_counts.keys())
    # Sort by combined count
    ranked = sorted(all_langs, key=lambda l: a.language_counts.get(l, 0) + b.language_counts.get(l, 0), reverse=True)

    table = Table(
        title="语言分布对比",
        show_header=True,
        border_style="dim",
        title_style="bold magenta",
    )
    table.add_column("语言", style="cyan", min_width=14)
    table.add_column(f"{a.repo_name} 行数", justify="right", width=10)
    table.add_column(f"{a.repo_name} 占比", justify="right", width=7)
    table.add_column(f"{b.repo_name} 行数", justify="right", width=10)
    table.add_column(f"{b.repo_name} 占比", justify="right", width=7)

    for lang in ranked[:top_n]:
        a_count = a.language_counts.get(lang, 0)
        b_count = b.language_counts.get(lang, 0)
        a_pct = a_count / a_total * 100
        b_pct = b_count / b_total * 100
        table.add_row(
            lang,
            f"{a_count:,}",
            f"{a_pct:.1f}%",
            f"{b_count:,}",
            f"{b_pct:.1f}%",
        )

    return table
