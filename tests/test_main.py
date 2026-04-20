from __future__ import annotations

from unittest.mock import patch

import pytest

from it2ag import __version__
from it2ag.__main__ import main


class TestMain:
    def test_version_flag_prints_package_version(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as excinfo:
            main(["--version"])

        assert excinfo.value.code == 0
        captured = capsys.readouterr()
        assert captured.out == f"it2ag {__version__}\n"

    def test_port_argument_is_forwarded_to_iterm2_runner(self) -> None:
        with patch("it2ag.__main__.iterm2.run_forever") as mock_run_forever:
            main(["--port", "50123"])

        mock_run_forever.assert_called_once()
