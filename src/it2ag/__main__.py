"""Entry point for it2ag - iTerm2 agent monitor."""

from __future__ import annotations

import argparse
import sys

import iterm2
import iterm2.connection

from it2ag.server import DEFAULT_PORT, AgentMonitorServer


async def _run(connection: iterm2.connection.Connection, port: int) -> None:
    server = AgentMonitorServer(connection, port=port)
    await server.start()
    print(f"it2ag: running (http://localhost:{port})")
    print("it2ag: Ctrl+C to stop")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="it2ag",
        description="iTerm2 agent monitor for Claude Code and Codex",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Port for the local web server (default: {DEFAULT_PORT})",
    )
    args = parser.parse_args()

    try:
        iterm2.run_forever(lambda conn: _run(conn, args.port))  # type: ignore[attr-defined]
    except KeyboardInterrupt:
        print("\nit2ag: stopped")
        sys.exit(0)


if __name__ == "__main__":
    main()
