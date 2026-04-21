# it2ag

iTerm2 agent monitor for [Claude Code](https://github.com/anthropics/claude-code) and [Codex](https://github.com/openai/codex).

Displays a real-time dashboard in iTerm2's Toolbelt sidebar showing all running AI coding agent sessions, their status (running/awaiting user/idle), git repo, and branch.

## Features

- **Agent detection** — Detects Claude Code and Codex processes via process tree inspection
- **Running/idle status** — Claude Code: `caffeinate` child process; Codex: per-PID IOKit power assertion (`pmset`) + `sandbox-exec`/`bwrap` fast path
- **Completion acknowledgement** — When Claude Code or Codex transitions from running to idle, the card switches to `awaiting user` until clicked
- **Git info** — Shows repo name and branch for each session
- **Repo grouping** — Groups sessions by root repository (worktree-aware via `git rev-parse --git-common-dir`)
- **Click to focus** — Click a session entry to switch to that iTerm2 pane and clear `awaiting user`
- **Search** — Filter sessions by name, repo, branch, or path
- **Auto-refresh** — Updates every 3 seconds
- **Toolbelt auto-open** — Automatically opens the Toolbelt panel if it's not already visible

## Requirements

- macOS
- [iTerm2](https://iterm2.com/) with Python API enabled (Settings > General > Magic > Enable Python API)
- [iTerm2 Shell Integration](https://iterm2.com/documentation-shell-integration.html) (for working directory and git info)
- [uv](https://docs.astral.sh/uv/)

## Installation

### Homebrew

```bash
brew tap mkusaka/tap
brew install mkusaka/tap/it2ag
```

### `uvx` from GitHub

Run directly from the git repo without cloning:

```bash
uvx --from git+https://github.com/mkusaka/it2ag.git it2ag
```

### Clone and run locally

```bash
git clone https://github.com/mkusaka/it2ag.git
cd it2ag
uv run it2ag
```

## Usage

```bash
# If installed via Homebrew or uvx
it2ag

# Or from the cloned repo
uv run it2ag
```

The Toolbelt panel opens automatically. Click any session to focus it, and click an `awaiting user` card to clear that completion marker.

### Options

```
--version      Show the installed version and exit
--port PORT    Port for the local web server (default: auto-select)
--install-autolaunch
               Install an iTerm2 AutoLaunch wrapper and exit
--force        Overwrite an existing AutoLaunch wrapper when used with
               --install-autolaunch
```

### Auto-launch on iTerm2 startup

Install the AutoLaunch wrapper with the same command you already use to run `it2ag`:

```bash
# If installed via Homebrew or uvx
it2ag --install-autolaunch

# Or from the cloned repo
uv run it2ag --install-autolaunch
```

This writes `~/Library/Application Support/iTerm2/Scripts/AutoLaunch/it2ag.py`.
If you run setup from a Homebrew-installed `it2ag`, the wrapper resolves
`it2ag` from `PATH` first, then falls back to common install locations such as
`/opt/homebrew/bin/it2ag` and `/usr/local/bin/it2ag`.

If you run setup from a cloned repo via `uv run it2ag --install-autolaunch`,
the wrapper becomes project-aware: it prefers `<repo>/.venv/bin/it2ag`, then
falls back to `uv --project <repo> run it2ag`.

If `~/Library/Application Support/iTerm2/Scripts/AutoLaunch/it2ag.py` already
exists and you want `it2ag` to replace it, rerun the command with `--force`.

## Release

1. Update `version` in `pyproject.toml` and `src/it2ag/__init__.py`.
2. Commit the release changes and push them to `main`.
3. Create and push a `vX.Y.Z` tag.
4. The `Release` workflow builds macOS app directories for Apple Silicon and Intel, publishes them to GitHub Releases, and dispatches a formula update to `mkusaka/homebrew-tap`.

## How it works

1. A local [aiohttp](https://docs.aiohttp.org/) web server serves an HTML dashboard
2. The dashboard is registered as an iTerm2 Toolbelt WebView tool via the [Python API](https://iterm2.com/python-api/)
3. Agent detection scans the process tree (`ps -eo pid,ppid,comm`) to find `claude`/`codex` processes and maps them to iTerm2 sessions
4. Running state detection:
   - **Claude Code**: checks for `caffeinate` child process (spawned during active turns)
   - **Codex**: parses `pmset -g assertions` for per-PID IOKit power assertions (`"Codex is running an active turn"`), with `sandbox-exec`/`bwrap` child check as a fast path. Works with all sandbox modes including `danger-full-access`
5. The dashboard keeps a small per-session transition cache so `running -> idle` is rendered as `awaiting user` until the card is clicked
6. Git info is resolved per-session using [GitPython](https://github.com/gitpython-developers/GitPython), with worktree grouping via `common_dir`

## Development

```bash
uv sync --group dev

# Build local app directory
./scripts/build-binary.sh

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
