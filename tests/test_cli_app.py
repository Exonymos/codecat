# tests/test_cli_app.py

"""
Verifies the behavior of the Codecat command-line interface.

These tests use Typer's CliRunner to invoke the application's commands
and assert that the output, exit codes, and generated files are correct.
"""

import re
from pathlib import Path

from typer.testing import CliRunner

from codecat import __version__
from codecat.cli_app import app
from codecat.constants import DEFAULT_CONFIG_FILENAME

# Use a test runner with a fixed terminal size for predictable UI output.
runner = CliRunner(env={"TERM": "xterm-256color", "COLUMNS": "130"})


def test_version_flag_works_correctly(strip_ansi_codes):
    """Ensures the --version flag displays the correct version and exits cleanly."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    clean_output = strip_ansi_codes(result.stderr)
    assert f"Codecat CLI Version: {__version__}" in clean_output


def test_generate_config_creates_file(tmp_path: Path, strip_ansi_codes):
    """Ensures `generate-config` creates a default config file in the target directory."""
    result = runner.invoke(app, ["generate-config", "--output-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert "Successfully generated config file" in strip_ansi_codes(result.stderr)
    assert (tmp_path / DEFAULT_CONFIG_FILENAME).exists()


def test_generate_config_aborts_if_user_says_no_to_overwrite(
    tmp_path: Path, strip_ansi_codes
):
    """Ensures `generate-config` aborts if the file exists and the user declines to overwrite."""
    config_file = tmp_path / DEFAULT_CONFIG_FILENAME
    config_file.write_text("original content")

    result = runner.invoke(
        app, ["generate-config", "--output-dir", str(tmp_path)], input="n\n"
    )
    assert result.exit_code != 0
    assert "aborted by user" in strip_ansi_codes(result.stderr)
    assert config_file.read_text() == "original content"


def test_generate_config_handles_io_error(tmp_path: Path, mocker, strip_ansi_codes):
    """Ensures `generate-config` handles I/O errors during file writing."""
    mocker.patch("builtins.open", side_effect=IOError("Disk full"))
    result = runner.invoke(
        app, ["generate-config", "--output-dir", str(tmp_path)], input="y\n"
    )
    assert result.exit_code != 0
    assert "Error writing config file" in strip_ansi_codes(result.stderr)


def test_run_command_creates_output_file(tmp_path: Path):
    """Ensures the basic `run` command creates the expected output file."""
    (tmp_path / "test_file.py").write_text("print('Hello, Codecat!')")

    result = runner.invoke(app, ["run", str(tmp_path), "--silent"])
    assert (
        result.exit_code == 0
    ), f"Run command failed: {result.stdout or result.stderr}"

    output_file = tmp_path / "codecat_output.md"
    assert output_file.exists(), "Output markdown file was not created."
    content = output_file.read_text(encoding="utf-8")
    assert "## File: `test_file.py`" in content
    assert "print('Hello, Codecat!')" in content


def test_run_command_with_verbose_output_for_skipped_files(
    tmp_path: Path, strip_ansi_codes
):
    """Ensures the `run` command with --verbose prints logs for skipped files."""
    (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00")
    (tmp_path / "main.py").write_text("pass")

    result = runner.invoke(
        app,
        ["run", str(tmp_path), "--verbose", "--include", "*.png", "--include", "*.py"],
    )
    assert result.exit_code == 0

    clean_output = strip_ansi_codes(result.stderr)
    assert "! Skipped (binary): image.png" in clean_output
    assert "✔ Read: main.py" in clean_output


def test_run_command_handles_write_error(tmp_path: Path, mocker, strip_ansi_codes):
    """Ensures the `run` command handles I/O errors during output file writing."""
    (tmp_path / "test_file.py").write_text("pass")
    mocker.patch("pathlib.Path.write_text", side_effect=IOError("Permission denied"))

    result = runner.invoke(app, ["run", str(tmp_path)])
    assert result.exit_code != 0
    assert "Error writing to output file" in strip_ansi_codes(result.stderr)


def test_dry_run_prevents_file_creation(tmp_path: Path, strip_ansi_codes):
    """Ensures that --dry-run scans and processes but does not write an output file."""
    (tmp_path / "test_file.py").write_text("pass")

    result = runner.invoke(app, ["run", str(tmp_path), "--dry-run"])
    assert result.exit_code == 0

    output_file = tmp_path / "codecat_output.md"
    assert not output_file.exists()

    clean_output = strip_ansi_codes(result.stderr)
    assert "--dry-run enabled" in clean_output


def test_no_header_flag_omits_main_header(tmp_path: Path):
    """Ensures that --no-header omits the main Codecat header from the output file."""
    (tmp_path / "test_file.py").write_text("pass")

    result = runner.invoke(app, ["run", str(tmp_path), "--no-header", "--silent"])
    assert result.exit_code == 0

    output_file = tmp_path / "codecat_output.md"
    assert output_file.exists()
    content = output_file.read_text()

    assert "Codecat: Aggregated Code" not in content
    assert "## File: `test_file.py`" in content


def test_stats_command_produces_correct_output(tmp_path: Path, strip_ansi_codes):
    """Ensures the `stats` command displays correct file and line count statistics."""
    (tmp_path / "main.py").write_text("line1\nline2")
    (tmp_path / "utils.py").write_text("line1\nline2\nline3")
    (tmp_path / "README.md").write_text("# Readme")

    result = runner.invoke(app, ["stats", str(tmp_path)])
    assert result.exit_code == 0

    clean_output = strip_ansi_codes(result.stderr)
    assert "File Type Statistics" in clean_output
    assert "python" in clean_output
    assert "markdown" in clean_output

    assert re.search(r"python\s+│\s+2\s+│\s+5\s+│", clean_output)
    assert re.search(r"markdown\s+│\s+1\s+│\s+1\s+│", clean_output)
    assert re.search(r"Total\s+│\s+3\s+│\s+6\s+│", clean_output)


def test_run_command_with_no_matching_files(tmp_path: Path, strip_ansi_codes):
    """Ensures the run command exits gracefully when no files match the criteria."""
    (tmp_path / "file.log").write_text("some log")
    result = runner.invoke(app, ["run", str(tmp_path)])
    assert result.exit_code == 0
    clean_output = strip_ansi_codes(result.stderr)
    assert "No files found" in clean_output
