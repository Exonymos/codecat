# tests/test_markdown_generator.py

"""
Verifies the functionality of the Markdown generation module.

These tests ensure the final Markdown output has the correct structure,
code block fencing, header options, and handles edge cases like
empty or special content.
"""

from pathlib import Path

import pytest

from codecat.config import DEFAULT_CONFIG
from codecat.file_processor import ProcessedFileData
from codecat.markdown_generator import _get_dynamic_fence, generate_markdown


@pytest.fixture
def sample_processed_files() -> list[ProcessedFileData]:
    """Provides a list of sample ProcessedFileData objects for testing."""
    base_path = Path("/fake/project")
    return [
        ProcessedFileData(
            path=base_path / "src/main.py",
            relative_path=Path("src/main.py"),
            status="text_content",
            content="print('Hello, World!')",
            encoding_used="utf-8",
        ),
        ProcessedFileData(
            path=base_path / "README.md",
            relative_path=Path("README.md"),
            status="text_content",
            content="This is a test.\nIt contains ``` some backticks ```.",
            encoding_used="utf-8",
        ),
        ProcessedFileData(
            path=base_path / "data/logo.png",
            relative_path=Path("data/logo.png"),
            status="binary_file",
        ),
        ProcessedFileData(
            path=base_path / "config.ini",
            relative_path=Path("config.ini"),
            status="read_error",
            error_message="Failed to decode.",
        ),
        ProcessedFileData(
            path=base_path / "empty.txt",
            relative_path=Path("empty.txt"),
            status="text_content",
            content="",
            encoding_used="utf-8",
        ),
    ]


def test_markdown_structure_and_cleanliness(sample_processed_files):
    """
    Ensures the overall structure of the generated markdown is correct,
    with proper headers, separators, and no extra newlines.
    """
    config = DEFAULT_CONFIG.copy()
    project_root = Path("/fake/project")
    result = generate_markdown(sample_processed_files, project_root, config)

    assert result.startswith("# Codecat: Aggregated Code for 'project'")
    assert result.count("\n\n---\n\n") == len(sample_processed_files) - 1

    first_file_section = (
        "## File: `src/main.py`\n\n```python\nprint('Hello, World!')\n```"
    )
    assert first_file_section in result

    # Verify that info/warning blocks for non-text files are present
    assert "`[INFO] Binary file detected" in result
    assert "`[WARNING] Could not process file" in result

    last_file_section = "## File: `empty.txt`\n\n_(File is empty)_\n"
    assert result.endswith(last_file_section)


def test_markdown_generation_without_header(sample_processed_files):
    """Ensures the --no-header config option correctly omits the main header."""
    config = DEFAULT_CONFIG.copy()
    config["generate_header"] = False
    project_root = Path("/fake/project")
    result = generate_markdown(sample_processed_files, project_root, config)

    assert not result.startswith("# Codecat")
    assert result.startswith("## File: `src/main.py`")


def test_dynamic_fence_logic():
    """
    Ensures the dynamic fence logic correctly increases backtick fence length
    to safely enclose content that already contains backticks.
    """
    assert _get_dynamic_fence("some code") == "```"
    assert _get_dynamic_fence("some ``` code") == "````"
    assert _get_dynamic_fence("some ``` and ```` code") == "`````"
    assert _get_dynamic_fence("```\n````\n`````") == "``````"


def test_language_hint_by_full_filename():
    """Ensures language hints can be matched by full filename (e.g., Dockerfile)."""
    dockerfile_data = [
        ProcessedFileData(
            path=Path("/fake/project/Dockerfile"),
            relative_path=Path("Dockerfile"),
            status="text_content",
            content="FROM python:3.11",
        )
    ]
    config = DEFAULT_CONFIG.copy()
    result = generate_markdown(dockerfile_data, Path("/fake/project"), config)
    assert "```dockerfile\nFROM python:3.11\n```" in result


def test_markdown_generation_with_no_files():
    """
    Ensures that markdown generation with an empty file list produces
    only the main header with a zero file count.
    """
    config = DEFAULT_CONFIG.copy()
    project_root = Path("/fake/project")
    result = generate_markdown([], project_root, config)

    expected_output = (
        "# Codecat: Aggregated Code for 'project'\n"
        "Generated from `0` files found in `/fake/project`.\n"
    )
    assert result == expected_output
