"""Tests for agent detection logic."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from git import Repo

from it2ag.detector import (
    AgentState,
    AgentType,
    GitInfo,
    ProcessInfo,
    _comm_basename,
    _detect_claude_state,
    _detect_codex_state,
    _find_ancestor_pid,
    _get_children,
    _get_descendants,
    _is_agent_process,
    _is_claude_process,
    _is_codex_process,
    detect_agents,
    get_git_info,
)


def _make_table(procs: list[tuple[int, int, str]]) -> dict[int, ProcessInfo]:
    return {pid: ProcessInfo(pid=pid, ppid=ppid, comm=comm) for pid, ppid, comm in procs}


class TestCommBasename:
    def test_simple(self) -> None:
        assert _comm_basename("claude") == "claude"

    def test_full_path(self) -> None:
        assert _comm_basename("/usr/local/bin/claude") == "claude"

    def test_nested_path(self) -> None:
        assert _comm_basename("/a/b/c/codex") == "codex"

    def test_just_slash(self) -> None:
        assert _comm_basename("/") == ""


class TestIsAgentProcess:
    def test_claude(self) -> None:
        assert _is_claude_process("claude")
        assert _is_claude_process("/usr/local/bin/claude")

    def test_codex(self) -> None:
        assert _is_codex_process("codex")
        assert _is_codex_process("/home/user/.local/bin/codex")

    def test_not_agent(self) -> None:
        assert not _is_agent_process("bash")
        assert not _is_agent_process("node")

    def test_partial_name_not_matched(self) -> None:
        assert not _is_claude_process("claude-helper")
        assert not _is_codex_process("codex-sandbox")

    def test_is_agent_matches_either(self) -> None:
        assert _is_agent_process("claude")
        assert _is_agent_process("codex")
        assert not _is_agent_process("vim")


class TestGetChildren:
    def test_direct_children(self) -> None:
        table = _make_table(
            [
                (1, 0, "init"),
                (10, 1, "bash"),
                (20, 1, "zsh"),
                (30, 10, "claude"),
            ]
        )
        children = _get_children(table, 1)
        pids = {c.pid for c in children}
        assert pids == {10, 20}

    def test_no_children(self) -> None:
        table = _make_table([(10, 1, "bash")])
        children = _get_children(table, 10)
        assert children == []


class TestDescendants:
    def test_finds_children(self) -> None:
        table = _make_table(
            [
                (1, 0, "init"),
                (10, 1, "bash"),
                (20, 10, "claude"),
                (30, 20, "caffeinate"),
                (40, 20, "node"),
            ]
        )
        desc = _get_descendants(table, 20)
        pids = {d.pid for d in desc}
        assert pids == {30, 40}

    def test_deep_tree(self) -> None:
        table = _make_table(
            [
                (1, 0, "init"),
                (10, 1, "bash"),
                (20, 10, "codex"),
                (30, 20, "sandbox-exec"),
                (40, 30, "bash"),
                (50, 40, "python"),
            ]
        )
        desc = _get_descendants(table, 20)
        pids = {d.pid for d in desc}
        assert pids == {30, 40, 50}

    def test_no_descendants(self) -> None:
        table = _make_table([(20, 10, "claude")])
        desc = _get_descendants(table, 20)
        assert desc == []

    def test_nonexistent_pid(self) -> None:
        table = _make_table([(20, 10, "claude")])
        desc = _get_descendants(table, 999)
        assert desc == []


class TestFindAncestor:
    def test_finds_ancestor(self) -> None:
        table = _make_table(
            [
                (1, 0, "init"),
                (10, 1, "bash"),
                (20, 10, "claude"),
            ]
        )
        assert _find_ancestor_pid(table, 20, {10}) == 10

    def test_no_match(self) -> None:
        table = _make_table(
            [
                (1, 0, "init"),
                (10, 1, "bash"),
                (20, 10, "claude"),
            ]
        )
        assert _find_ancestor_pid(table, 20, {99}) is None

    def test_self_is_target(self) -> None:
        table = _make_table(
            [
                (10, 1, "bash"),
                (20, 10, "claude"),
            ]
        )
        assert _find_ancestor_pid(table, 10, {10}) == 10

    def test_deep_ancestor(self) -> None:
        table = _make_table(
            [
                (1, 0, "init"),
                (10, 1, "bash"),
                (20, 10, "zsh"),
                (30, 20, "node"),
                (40, 30, "claude"),
            ]
        )
        assert _find_ancestor_pid(table, 40, {10}) == 10


class TestDetectClaudeState:
    def test_running_with_caffeinate(self) -> None:
        table = _make_table(
            [
                (20, 10, "claude"),
                (30, 20, "caffeinate"),
            ]
        )
        assert _detect_claude_state(table, 20) == AgentState.RUNNING

    def test_idle_without_caffeinate(self) -> None:
        table = _make_table(
            [
                (20, 10, "claude"),
            ]
        )
        assert _detect_claude_state(table, 20) == AgentState.IDLE

    def test_running_with_deep_caffeinate(self) -> None:
        table = _make_table(
            [
                (20, 10, "claude"),
                (30, 20, "node"),
                (40, 30, "caffeinate"),
            ]
        )
        assert _detect_claude_state(table, 20) == AgentState.RUNNING

    def test_idle_with_unrelated_children(self) -> None:
        table = _make_table(
            [
                (20, 10, "claude"),
                (30, 20, "node"),
                (40, 20, "python"),
            ]
        )
        assert _detect_claude_state(table, 20) == AgentState.IDLE


class TestDetectCodexState:
    def test_running_with_sandbox(self) -> None:
        table = _make_table(
            [
                (20, 10, "codex"),
                (30, 20, "sandbox-exec"),
            ]
        )
        assert _detect_codex_state(table, 20) == AgentState.RUNNING

    def test_running_with_bwrap(self) -> None:
        table = _make_table(
            [
                (20, 10, "codex"),
                (30, 20, "bwrap"),
            ]
        )
        assert _detect_codex_state(table, 20) == AgentState.RUNNING

    def test_running_with_shell_command(self) -> None:
        """Codex can run commands without sandbox-exec."""
        table = _make_table(
            [
                (20, 10, "codex"),
                (30, 20, "npm"),  # MCP background
                (40, 20, "sleep"),  # actual command
            ]
        )
        assert _detect_codex_state(table, 20) == AgentState.RUNNING

    def test_running_with_any_non_background_child(self) -> None:
        table = _make_table(
            [
                (20, 10, "codex"),
                (30, 20, "npm"),
                (40, 20, "python"),
            ]
        )
        assert _detect_codex_state(table, 20) == AgentState.RUNNING

    def test_idle_without_children(self) -> None:
        table = _make_table(
            [
                (20, 10, "codex"),
            ]
        )
        assert _detect_codex_state(table, 20) == AgentState.IDLE

    def test_idle_with_only_mcp_children(self) -> None:
        table = _make_table(
            [
                (20, 10, "codex"),
                (30, 20, "npm"),
                (40, 20, "npm"),
                (50, 20, "/path/to/mcp-server-darwin-arm64"),
            ]
        )
        assert _detect_codex_state(table, 20) == AgentState.IDLE

    def test_idle_with_node_children(self) -> None:
        table = _make_table(
            [
                (20, 10, "codex"),
                (30, 20, "node"),
            ]
        )
        assert _detect_codex_state(table, 20) == AgentState.IDLE

    def test_idle_with_pencil_mcp(self) -> None:
        table = _make_table(
            [
                (20, 10, "codex"),
                (30, 20, "/Applications/Pencil.app/Contents/Resources/out/mcp-server-darwin-arm64"),
                (40, 20, "npm"),
            ]
        )
        assert _detect_codex_state(table, 20) == AgentState.IDLE


class TestDetectAgents:
    @patch("it2ag.detector._build_process_table")
    def test_finds_claude_and_codex(self, mock_table: object) -> None:
        mock_table.return_value = _make_table(  # type: ignore[union-attr]
            [
                (1, 0, "init"),
                (10, 1, "bash"),
                (20, 10, "claude"),
                (30, 20, "caffeinate"),
                (40, 1, "zsh"),
                (50, 40, "codex"),
                (60, 50, "sandbox-exec"),
            ]
        )
        agents = detect_agents()
        assert len(agents) == 2
        claude_agents = [a for a in agents if a.agent_type == AgentType.CLAUDE]
        codex_agents = [a for a in agents if a.agent_type == AgentType.CODEX]
        assert len(claude_agents) == 1
        assert claude_agents[0].state == AgentState.RUNNING
        assert len(codex_agents) == 1
        assert codex_agents[0].state == AgentState.RUNNING

    @patch("it2ag.detector._build_process_table")
    def test_filters_by_session_pids(self, mock_table: object) -> None:
        mock_table.return_value = _make_table(  # type: ignore[union-attr]
            [
                (1, 0, "init"),
                (10, 1, "bash"),
                (20, 10, "claude"),
                (40, 1, "zsh"),
                (50, 40, "codex"),
            ]
        )
        # Only session with pid=10, so codex (under pid=40) should be excluded
        agents = detect_agents(session_pids={10})
        assert len(agents) == 1
        assert agents[0].agent_type == AgentType.CLAUDE
        assert agents[0].session_pid == 10

    @patch("it2ag.detector._build_process_table")
    def test_no_agents(self, mock_table: object) -> None:
        mock_table.return_value = _make_table(  # type: ignore[union-attr]
            [
                (1, 0, "init"),
                (10, 1, "bash"),
                (20, 10, "vim"),
            ]
        )
        agents = detect_agents()
        assert agents == []


class TestGetGitInfo:
    def test_non_git_dir(self) -> None:
        info = get_git_info("/tmp")
        assert info.repo == ""
        assert info.branch == ""
        assert info.root_repo == ""

    def test_empty_path(self) -> None:
        info = get_git_info("")
        assert info == GitInfo(repo="", branch="", root_repo="")

    def test_nonexistent_path(self) -> None:
        info = get_git_info("/nonexistent/path/that/does/not/exist")
        assert info.repo == ""

    def test_normal_repo(self, tmp_path: Path) -> None:
        """A normal git repo should return repo name, branch, and root_repo == toplevel."""
        repo_dir = tmp_path / "my-project"
        repo_dir.mkdir()
        repo = Repo.init(repo_dir)
        (repo_dir / "README.md").write_text("hello")
        repo.index.add(["README.md"])
        repo.index.commit("init")

        info = get_git_info(str(repo_dir))
        assert info.repo == "my-project"
        assert info.branch in ("master", "main")
        assert info.root_repo == str(repo_dir)

    def test_worktree_uses_main_repo_name(self, tmp_path: Path) -> None:
        """A worktree should report the main repo's name, not the worktree dir name."""
        main_dir = tmp_path / "my-project"
        main_dir.mkdir()
        repo = Repo.init(main_dir)
        (main_dir / "README.md").write_text("hello")
        repo.index.add(["README.md"])
        repo.index.commit("init")

        repo.git.branch("feature-branch")
        wt_dir = tmp_path / "20260401_worktree_feature"
        repo.git.worktree("add", str(wt_dir), "feature-branch")

        info = get_git_info(str(wt_dir))
        assert info.repo == "my-project"
        assert info.branch == "feature-branch"
        assert info.root_repo == str(main_dir)

    def test_subdirectory_of_repo(self, tmp_path: Path) -> None:
        """get_git_info from a subdirectory should still find the repo."""
        repo_dir = tmp_path / "my-project"
        sub_dir = repo_dir / "src" / "app"
        sub_dir.mkdir(parents=True)
        repo = Repo.init(repo_dir)
        (repo_dir / "README.md").write_text("hello")
        repo.index.add(["README.md"])
        repo.index.commit("init")

        info = get_git_info(str(sub_dir))
        assert info.repo == "my-project"

    def test_detached_head(self, tmp_path: Path) -> None:
        """Detached HEAD should return empty branch."""
        repo_dir = tmp_path / "my-project"
        repo_dir.mkdir()
        repo = Repo.init(repo_dir)
        (repo_dir / "README.md").write_text("hello")
        repo.index.add(["README.md"])
        commit = repo.index.commit("init")

        repo.head.reference = commit  # type: ignore[assignment]
        repo.head.reset(index=True, working_tree=True)

        info = get_git_info(str(repo_dir))
        assert info.repo == "my-project"
        assert info.branch == ""
