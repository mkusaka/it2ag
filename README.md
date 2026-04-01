# it2ag

iTerm2 agent monitor for [Claude Code](https://github.com/anthropics/claude-code) and [Codex](https://github.com/openai/codex).

Displays a real-time dashboard in iTerm2's Toolbelt sidebar showing all running AI coding agent sessions, their status (running/idle), git repo, and branch.

## Features

- **Agent detection** — Detects Claude Code and Codex processes via process tree inspection
- **Running/idle status** — Claude Code: `caffeinate` child process; Codex: `sandbox-exec`/`bwrap` child or IOKit power assertion
- **Git info** — Shows repo name and branch for each session
- **Repo grouping** — Groups sessions by root repository (worktree-aware via `git rev-parse --git-common-dir`)
- **Click to focus** — Click a session entry to switch to that iTerm2 pane
- **Search** — Filter sessions by name, repo, branch, or path
- **Auto-refresh** — Updates every 3 seconds
- **Toolbelt auto-open** — Automatically opens the Toolbelt panel if it's not already visible

## Requirements

- macOS
- [iTerm2](https://iterm2.com/) with Python API enabled (Settings > General > Magic > Enable Python API)
- [iTerm2 Shell Integration](https://iterm2.com/documentation-shell-integration.html) (for working directory and git info)
- [uv](https://docs.astral.sh/uv/)

## Installation

```bash
git clone https://github.com/mkusaka/it2ag.git
cd it2ag
uv sync
```

## Usage

```bash
uv run it2ag
```

The Toolbelt panel opens automatically. Click any session to focus it.

### Options

```
--port PORT    Port for the local web server (default: 49152)
```

### Auto-launch on iTerm2 startup

Copy or symlink the script to iTerm2's AutoLaunch directory:

```bash
mkdir -p ~/Library/Application\ Support/iTerm2/Scripts/AutoLaunch
# Create a wrapper script
cat > ~/Library/Application\ Support/iTerm2/Scripts/AutoLaunch/it2ag.py << 'EOF'
import subprocess, sys, os
subprocess.Popen(
    [os.path.expanduser("~/.local/bin/uv"), "run", "--project",
     os.path.expanduser("~/src/github.com/mkusaka/it2ag"), "it2ag"],
)
EOF
```

## How it works

1. A local [aiohttp](https://docs.aiohttp.org/) web server serves an HTML dashboard
2. The dashboard is registered as an iTerm2 Toolbelt WebView tool via the [Python API](https://iterm2.com/python-api/)
3. Agent detection scans the process tree (`ps -eo pid,ppid,comm`) to find `claude`/`codex` processes and maps them to iTerm2 sessions
4. Git info is resolved per-session using `git rev-parse`, with worktree support via `--git-common-dir`

## Development

```bash
uv sync --group dev

# Lint
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/

# Type check
uv run mypy src/

# Test
uv run pytest -v
```

## License

GPL-2.0
