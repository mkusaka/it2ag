"""Agent process detection for Claude Code and Codex."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from git import InvalidGitRepositoryError, Repo


class AgentType(Enum):
    CLAUDE = "claude"
    CODEX = "codex"


class AgentState(Enum):
    RUNNING = "running"
    IDLE = "idle"


@dataclass
class ProcessInfo:
    pid: int
    ppid: int
    comm: str


@dataclass
class AgentInfo:
    agent_type: AgentType
    state: AgentState
    pid: int
    session_pid: int | None = None


def _build_process_table() -> dict[int, ProcessInfo]:
    """Build a process table from ps output."""
    result = subprocess.run(
        ["ps", "-eo", "pid,ppid,comm"],
        capture_output=True,
        text=True,
        timeout=5,
    )
    if result.returncode != 0:
        return {}

    table: dict[int, ProcessInfo] = {}
    for line in result.stdout.strip().splitlines()[1:]:  # skip header
        parts = line.split(None, 2)
        if len(parts) < 3:
            continue
        try:
            pid = int(parts[0])
            ppid = int(parts[1])
            comm = parts[2].strip()
            table[pid] = ProcessInfo(pid=pid, ppid=ppid, comm=comm)
        except ValueError:
            continue
    return table


def _get_children(table: dict[int, ProcessInfo], pid: int) -> list[ProcessInfo]:
    """Get all direct children of a process."""
    return [p for p in table.values() if p.ppid == pid]


def _get_descendants(table: dict[int, ProcessInfo], pid: int) -> list[ProcessInfo]:
    """Get all descendants of a process (BFS)."""
    descendants: list[ProcessInfo] = []
    queue = [pid]
    visited: set[int] = {pid}
    while queue:
        current = queue.pop(0)
        for child in _get_children(table, current):
            if child.pid not in visited:
                visited.add(child.pid)
                descendants.append(child)
                queue.append(child.pid)
    return descendants


def _find_ancestor_pid(
    table: dict[int, ProcessInfo], pid: int, target_pids: set[int]
) -> int | None:
    """Walk up the process tree to find if any target_pid is an ancestor."""
    visited: set[int] = set()
    current = pid
    while current > 1 and current not in visited:
        visited.add(current)
        if current in target_pids:
            return current
        proc = table.get(current)
        if proc is None:
            break
        current = proc.ppid
    return None


def _comm_basename(comm: str) -> str:
    """Extract the basename from a comm string (may be a full path)."""
    return os.path.basename(comm)


def _is_claude_process(comm: str) -> bool:
    name = _comm_basename(comm)
    return name == "claude"


def _is_codex_process(comm: str) -> bool:
    name = _comm_basename(comm)
    return name == "codex"


def _is_agent_process(comm: str) -> bool:
    return _is_claude_process(comm) or _is_codex_process(comm)


def _detect_claude_state(table: dict[int, ProcessInfo], pid: int) -> AgentState:
    """Claude Code spawns caffeinate when running a turn."""
    descendants = _get_descendants(table, pid)
    for d in descendants:
        if _comm_basename(d.comm) == "caffeinate":
            return AgentState.RUNNING
    return AgentState.IDLE


def _detect_codex_state(table: dict[int, ProcessInfo], pid: int) -> AgentState:
    """Codex spawns sandbox-exec (macOS) when executing commands."""
    descendants = _get_descendants(table, pid)
    for d in descendants:
        name = _comm_basename(d.comm)
        if name in ("sandbox-exec", "bwrap", "codex-linux-sandbox"):
            return AgentState.RUNNING
    # Fallback: check IOKit power assertions
    if _check_codex_power_assertion():
        return AgentState.RUNNING
    return AgentState.IDLE


def _check_codex_power_assertion() -> bool:
    """Check macOS IOKit power assertions for active Codex turn."""
    try:
        result = subprocess.run(
            ["pmset", "-g", "assertions"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        return "Codex is running an active turn" in result.stdout
    except Exception:
        return False


def detect_agents(session_pids: set[int] | None = None) -> list[AgentInfo]:
    """Detect all running Claude Code and Codex agents.

    Args:
        session_pids: If provided, only return agents that are descendants
                      of these PIDs (iTerm2 session shell PIDs).
    """
    table = _build_process_table()
    agents: list[AgentInfo] = []

    for proc in table.values():
        if not _is_agent_process(proc.comm):
            continue

        if _is_claude_process(proc.comm):
            agent_type = AgentType.CLAUDE
            state = _detect_claude_state(table, proc.pid)
        else:
            agent_type = AgentType.CODEX
            state = _detect_codex_state(table, proc.pid)

        session_pid: int | None = None
        if session_pids:
            session_pid = _find_ancestor_pid(table, proc.pid, session_pids)
            if session_pid is None:
                continue  # not in any known session

        agents.append(
            AgentInfo(
                agent_type=agent_type,
                state=state,
                pid=proc.pid,
                session_pid=session_pid,
            )
        )

    return agents


@dataclass
class GitInfo:
    repo: str
    branch: str
    root_repo: str


def get_git_info(path: str) -> GitInfo:
    """Get git repo name, branch, and root repo path for a directory.

    For worktrees, root_repo points to the main repository's toplevel,
    so sessions in different worktrees of the same repo get grouped together.
    """
    empty = GitInfo(repo="", branch="", root_repo="")
    if not path or not os.path.isdir(path):
        return empty
    try:
        repo = Repo(path, search_parent_directories=True)
    except (InvalidGitRepositoryError, Exception):
        return empty

    try:
        toplevel = str(repo.working_tree_dir or "")
        repo_name = os.path.basename(toplevel) if toplevel else ""

        branch = ""
        if not repo.head.is_detached:
            branch = repo.active_branch.name

        # Resolve root repo for worktree grouping.
        # repo.common_dir points to the shared .git dir (same for all worktrees).
        # For normal repos: /path/to/repo/.git
        # For worktrees: /path/to/main-repo/.git (the main repo's git dir)
        root_repo = toplevel
        common_dir = Path(repo.common_dir).resolve()
        if common_dir != Path(repo.git_dir).resolve():
            # This is a worktree; common_dir is the main repo's .git
            root_repo = str(common_dir.parent)

        return GitInfo(repo=repo_name, branch=branch, root_repo=root_repo)
    except Exception:
        return empty
