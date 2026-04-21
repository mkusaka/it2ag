"""Entry point for it2ag - iTerm2 agent monitor."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

import iterm2
import iterm2.connection

from it2ag import __version__
from it2ag.autolaunch import install_autolaunch
from it2ag.server import DEFAULT_PORT, AgentMonitorServer


async def _run(connection: iterm2.connection.Connection, port: int) -> None:
    server = AgentMonitorServer(connection, port=port)
    await server.start()
    print(f"it2ag: running ({server.url})")
    print("it2ag: Ctrl+C to stop")


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="it2ag",
        description="iTerm2 agent monitor for Claude Code and Codex",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help="Port for the local web server (default: auto-select)",
    )
    parser.add_argument(
        "--install-autolaunch",
        action="store_true",
        help="Install an iTerm2 AutoLaunch wrapper and exit",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing AutoLaunch wrapper when used with --install-autolaunch",
    )
    args = parser.parse_args(argv)

    if args.force and not args.install_autolaunch:
        parser.error("--force can only be used with --install-autolaunch")

    if args.install_autolaunch:
        result = install_autolaunch(force=args.force)
        action = "installed" if result.changed else "already installed"
        print(f"it2ag: AutoLaunch wrapper {action} at {result.path} (mode: {result.mode})")
        return

    try:
        iterm2.run_forever(lambda conn: _run(conn, args.port))
    except KeyboardInterrupt:
        print("\nit2ag: stopped")
        sys.exit(0)


if __name__ == "__main__":
    main()
