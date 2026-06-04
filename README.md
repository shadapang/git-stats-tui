# git-stats-tui

> Beautiful terminal UI for local git statistics — contribution heatmap, language breakdown, commit patterns

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![TUI](https://img.shields.io/badge/TUI-Textual-orange)

## Features

- **Contribution Heatmap** — GitHub-style 52-week heatmap, right in your terminal
- **Language Breakdown** — file count by language with colored bar chart
- **Commit Timeline** — commit patterns by hour of day and day of week
- **Top Contributors** — author breakdown with share percentages
- **Recent Commits** — scrollable commit list with insertions/deletions
- **Overview Dashboard** — all key stats at a glance
- **Date Range Filter** — press `d` to filter stats to a date range
- **Repo Switcher** — press `s` to switch to another repo without restarting
- **Keyboard Navigation** — tab between views, `r` to refresh, `q` to quit
- **Zero API Calls** — pure local `.git` parsing, works offline, works with any git host

## Quick Start

```bash
# Install
pip install git-stats-tui

# Run in any git repo
cd your-project
git-stats

# Or point to a specific repo
git-stats /path/to/repo

# Find all git repos under a directory
git-stats --find ~/projects
```

## Screenshots

> Coming soon — run it and take your own!

## Key Bindings

| Key | Action |
|-----|--------|
| `Tab` / `Shift+Tab` | Switch between tabs |
| `r` | Refresh stats |
| `f` | Find repos under current directory |
| `d` | Toggle date range filter (e.g. `2025-01-01 ~ 2025-12-31`) |
| `s` | Switch to another repo (path or `#N` for discovered repo) |
| `q` | Quit |

## Tabs

| Tab | Content |
|-----|---------|
| **Heatmap** | 52-week contribution graph + current streak |
| **Languages** | File count by language with bar chart |
| **Timeline** | Commits by hour, by weekday, top authors |
| **Commits** | Recent commits with date, author, message, +/- lines |
| **Overview** | Summary: total commits, authors, branches, peak hour, weekend ratio |

## How It Works

1. Reads `git log` with `--numstat` for commit history + file changes
2. Reads `git ls-files` for language breakdown by file extension
3. Aggregates into daily/hourly/weekly/author buckets
4. Renders with [Textual](https://textual.textualize.io/) TUI + [Rich](https://rich.readthedocs.io/)

No external API, no network, no token — pure local git.

## Development

```bash
# Clone
git clone https://github.com/yourname/git-stats-tui.git
cd git-stats-tui

# Install dev dependencies
pip install -e ".[dev]"

# Run
python -m src.app

# Lint
ruff check src/
```

## Publishing to GitHub

```bash
# 1. Initialize git repo
cd git-stats-tui
git init
git add .
git commit -m "feat: initial release - git-stats-tui v0.1.0"

# 2. Create GitHub repo (requires gh CLI)
gh repo create git-stats-tui --public --source=. --push

# 3. Add topics for discoverability
gh repo edit --add-topic python,git,terminal,tui,statistics,contribution-graph,textual

# 4. (Optional) Publish to PyPI
pip install build twine
python -m build
twine upload dist/*
```

## License

MIT
