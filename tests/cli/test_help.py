"""Regression tests for the CLI entrypoint."""

import subprocess
import sys
import textwrap
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class CliHelpTests(unittest.TestCase):
    def test_help_works_without_polygon_url(self) -> None:
        script = textwrap.dedent(
            """
            import os
            from unittest.mock import patch

            from typer.testing import CliRunner

            with patch("dotenv.load_dotenv", return_value=None):
                with patch.dict(os.environ, {}, clear=True):
                    import src.cli as cli

                    result = CliRunner().invoke(cli.app, ["--help"])

            print(result.output, end="")
            raise SystemExit(result.exit_code)
            """
        )

        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("Usage", result.stdout)


if __name__ == "__main__":
    unittest.main()
