"""Tests for agent detection logic."""

from __future__ import annotations

from pathlib import Path

from git import Repo

from it2ag.detector import (
    AgentState,
    GitInfo,
    ProcessInfo,
    _comm_basename,
    _detect_claude_state,
    _detect_codex_state,
    _find_ancestor_pid,
    _get_descendants,
    _is_agent_process,
    _is_claude_process,
    _is_codex_process,
    get_git_info,
)


def _make_table(procs: list[tuple[int, int, str]]) -> dict[int, ProcessInfo]:
    return {pid: ProcessInfo(pid=pid, ppid=ppid, comm=comm) for pid, ppid, comm in procs}


class TestCommBasename:
    def test_simple(self) -> None:
        assert _comm_basename("claude") == "claude"

    def test_full_path(self) -> None:
        assert _comm_basename("/usr/local/bin/claude") == "claude"


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
        # Create an initial commit so HEAD and branch exist
        (repo_dir / "README.md").write_text("hello")
        repo.index.add(["README.md"])
        repo.index.commit("init")

        info = get_git_info(str(repo_dir))
        assert info.repo == "my-project"
        assert info.branch == "master" or info.branch == "main"
        assert info.root_repo == str(repo_dir)

    def test_worktree_uses_main_repo_name(self, tmp_path: Path) -> None:
        """A worktree should report the main repo's name, not the worktree dir name."""
        # Create main repo
        main_dir = tmp_path / "my-project"
        main_dir.mkdir()
        repo = Repo.init(main_dir)
        (main_dir / "README.md").write_text("hello")
        repo.index.add(["README.md"])
        repo.index.commit("init")

        # Create a branch and worktree
        repo.git.branch("feature-branch")
        wt_dir = tmp_path / "20260401_worktree_feature"
        repo.git.worktree("add", str(wt_dir), "feature-branch")

        info = get_git_info(str(wt_dir))
        assert info.repo == "my-project"  # main repo name, not worktree dir name
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
