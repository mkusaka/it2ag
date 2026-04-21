from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from it2ag import __version__
from it2ag.__main__ import main
from it2ag.autolaunch import AutoLaunchInstallResult
from it2ag.server import DEFAULT_PORT


class TestMain:
    def test_version_flag_prints_package_version(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as excinfo:
            main(["--version"])

        assert excinfo.value.code == 0
        captured = capsys.readouterr()
        assert captured.out == f"it2ag {__version__}\n"

    def test_default_port_is_forwarded_to_runner(self) -> None:
        with (
            patch("it2ag.__main__._run", new_callable=AsyncMock) as mock_run,
            patch("it2ag.__main__.iterm2.run_forever") as mock_run_forever,
        ):
            main([])
            callback = mock_run_forever.call_args.args[0]
            asyncio.run(callback("connection"))

        mock_run.assert_awaited_once_with("connection", DEFAULT_PORT)

    def test_port_argument_is_forwarded_to_runner(self) -> None:
        with (
            patch("it2ag.__main__._run", new_callable=AsyncMock) as mock_run,
            patch("it2ag.__main__.iterm2.run_forever") as mock_run_forever,
        ):
            main(["--port", "50123"])
            callback = mock_run_forever.call_args.args[0]
            asyncio.run(callback("connection"))

        mock_run.assert_awaited_once_with("connection", 50123)

    def test_install_autolaunch_flag_installs_wrapper_and_skips_runner(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        result = AutoLaunchInstallResult(path=Path("/tmp/it2ag.py"), changed=True, mode="binary")
        with (
            patch("it2ag.__main__.install_autolaunch", return_value=result) as mock_install,
            patch("it2ag.__main__.iterm2.run_forever") as mock_run_forever,
        ):
            main(["--install-autolaunch"])

        mock_install.assert_called_once_with(force=False)
        mock_run_forever.assert_not_called()
        captured = capsys.readouterr()
        assert "AutoLaunch wrapper installed" in captured.out
        assert "mode: binary" in captured.out

    def test_force_requires_install_autolaunch(self) -> None:
        with pytest.raises(SystemExit) as excinfo:
            main(["--force"])

        assert excinfo.value.code == 2
