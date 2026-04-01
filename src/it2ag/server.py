"""Web server and iTerm2 integration for the agent monitor."""

from __future__ import annotations

import os

import iterm2
import iterm2.app
import iterm2.connection
import iterm2.mainmenu
import iterm2.session
import iterm2.tool
from aiohttp import web

from it2ag.detector import AgentInfo, detect_agents, get_git_info
from it2ag.ui import AGENT_MONITOR_HTML

DEFAULT_PORT = 49152

_SHOW_TOOLBELT_ID = iterm2.mainmenu.MainMenu.Toolbelt.SHOW_TOOLBELT.value.identifier


class AgentMonitorServer:
    """Manages the aiohttp server and iTerm2 Toolbelt integration."""

    def __init__(self, connection: iterm2.connection.Connection, port: int = DEFAULT_PORT) -> None:
        self.connection = connection
        self.port = port

    async def start(self) -> None:
        app = web.Application()
        app.router.add_get("/", self._handle_index)
        app.router.add_get("/api/sessions", self._handle_sessions)
        app.router.add_get("/api/focus", self._handle_focus)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "localhost", self.port)
        await site.start()

        await iterm2.tool.async_register_web_view_tool(
            self.connection,
            display_name="it2ag",
            identifier="com.mkusaka.it2ag",
            reveal_if_already_registered=True,
            url=f"http://localhost:{self.port}/",
        )

        await self._ensure_toolbelt_visible()

    async def _ensure_toolbelt_visible(self) -> None:
        """Show the Toolbelt panel if it's not already visible."""
        if _SHOW_TOOLBELT_ID is None:
            return
        state = await iterm2.mainmenu.MainMenu.async_get_menu_item_state(
            self.connection,
            _SHOW_TOOLBELT_ID,
        )
        if not state.checked:
            await iterm2.mainmenu.MainMenu.async_select_menu_item(
                self.connection,
                _SHOW_TOOLBELT_ID,
            )

    async def _handle_index(self, request: web.Request) -> web.Response:
        return web.Response(text=AGENT_MONITOR_HTML, content_type="text/html")

    async def _handle_sessions(self, request: web.Request) -> web.Response:
        iterm2_app = await iterm2.app.async_get_app(self.connection)
        if iterm2_app is None:
            return web.json_response([])

        # Collect session PIDs for agent-session mapping
        session_map: dict[int, iterm2.session.Session] = {}
        sessions_info: list[dict[str, str | int]] = []

        for window in iterm2_app.terminal_windows:
            for tab in window.tabs:
                for session in tab.sessions:
                    pid: int | None = None
                    try:
                        pid = await session.async_get_variable("pid")
                    except Exception:
                        pid = None
                    if pid is not None:
                        session_map[pid] = session

        # Detect agents and map to sessions
        session_pids = set(session_map.keys())
        agents = detect_agents(session_pids) if session_pids else []
        agent_by_session_pid: dict[int, AgentInfo] = {}
        for detected in agents:
            if detected.session_pid is not None:
                agent_by_session_pid[detected.session_pid] = detected

        # Build response
        for pid, session in session_map.items():
            path = ""
            try:
                path = await session.async_get_variable("path") or ""
            except Exception:
                path = ""

            git = get_git_info(path) if path else None
            agent: AgentInfo | None = agent_by_session_pid.get(pid)
            home = os.path.expanduser("~")

            sessions_info.append(
                {
                    "id": session.session_id,
                    "name": session.name or "",
                    "path": path.replace(home, "~") if path else "",
                    "repo": git.repo if git else "",
                    "branch": git.branch if git else "",
                    "root_repo": git.root_repo.replace(home, "~") if git else "",
                    "agent_type": agent.agent_type.value if agent else "",
                    "agent_state": agent.state.value if agent else "",
                    "pid": pid,
                }
            )

        # Sort: agents first (running before idle), then non-agents
        sessions_info.sort(
            key=lambda s: (
                0 if s["agent_state"] == "running" else 1 if s["agent_state"] == "idle" else 2,
                s["name"],
            )
        )

        return web.json_response(sessions_info)

    async def _handle_focus(self, request: web.Request) -> web.Response:
        session_id = request.query.get("session", "")
        if not session_id:
            return web.Response(text="no session id", status=400)

        iterm2_app = await iterm2.app.async_get_app(self.connection)
        if iterm2_app is None:
            return web.Response(text="app not found", status=500)

        for window in iterm2_app.terminal_windows:
            for tab in window.tabs:
                for session in tab.sessions:
                    if session.session_id == session_id:
                        await session.async_activate()
                        return web.Response(text="ok")

        return web.Response(text="not found", status=404)
