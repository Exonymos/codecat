# tests/test_file_scanner.py

"""
Verifies the core logic of discovering and filtering files.

These tests ensure that the file scanner correctly applies various
configuration options, such as include/exclude patterns, directory/file
exclusions, and file size limits.
"""

import copy
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from codecat.config import DEFAULT_CONFIG
from codecat.file_scanner import scan_project


def create_project_structure(base_path: Path, structure: Dict[str, Any]) -> None:
    """Recursively creates a directory and file structure for testing."""
    for name, content in structure.items():
        item_path = base_path / name
        if isinstance(content, dict):
            item_path.mkdir(parents=True, exist_ok=True)
            create_project_structure(item_path, content)
        elif isinstance(content, str):
            item_path.parent.mkdir(parents=True, exist_ok=True)
            item_path.write_text(content, encoding="utf-8")
        elif content is None:
            item_path.parent.mkdir(parents=True, exist_ok=True)
            item_path.touch()
        elif isinstance(content, tuple) and content[0].startswith("symlink"):
            target_path_abs = (base_path / content[1]).resolve()
            item_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.symlink(
                    target_path_abs,
                    item_path,
                    target_is_directory=content[0] == "symlink_dir",
                )
            except (OSError, AttributeError):  # pragma: no cover
                pass


def run_scan_with_config(
    tmp_path: Path,
    structure: Dict[str, Any],
    config_overrides: Dict[str, Any],
    scan_target_subdir: Optional[str] = None,
) -> List[str]:
    """
    A helper function to set up a project, run the scanner, and return relative paths.
    This simplifies writing individual test cases by handling the common boilerplate.
    """
    create_project_structure(tmp_path, structure)

    test_config = copy.deepcopy(DEFAULT_CONFIG)
    test_config.update(config_overrides)

    cli_project_path = tmp_path
    project_root_for_scan = (
        tmp_path / scan_target_subdir if scan_target_subdir else tmp_path
    )

    if not project_root_for_scan.exists():
        project_root_for_scan.mkdir(parents=True, exist_ok=True)

    found_paths_abs = scan_project(
        project_root_for_scan.resolve(), test_config, cli_project_path.resolve()
    )

    found_paths_rel = [
        str(p.relative_to(cli_project_path.resolve())).replace(os.path.sep, "/")
        for p in found_paths_abs
    ]
    return sorted(found_paths_rel)


def test_scanning_an_empty_project(tmp_path: Path):
    """Ensures that scanning an empty directory yields no files."""
    files = run_scan_with_config(tmp_path, {}, {})
    assert files == [], "Should find no files in an empty project"


def test_scanning_with_default_configuration(tmp_path: Path):
    """Ensures a simple project is scanned correctly with the default configuration."""
    structure = {
        "file1.py": "print('hello')",
        "file2.txt": "some text",
        "README.md": "# Test Readme",
        ".hiddenfile": "secret",
        "subdir": {"file3.py": "import os", "data.json": "{}"},
        ".venv": {"pyvenv.cfg": ""},
    }
    expected = sorted(
        [
            "README.md",
            "file1.py",
            "file2.txt",
            "subdir/data.json",
            "subdir/file3.py",
        ]
    )
    files = run_scan_with_config(tmp_path, structure, {})
    assert files == expected, "Mismatch in files found with default config"


def test_include_patterns_filter_correctly(tmp_path: Path):
    """Ensures that `include_patterns` correctly filter which files are kept."""
    structure = {"main.py": "", "utils.py": "", "script.sh": "", "notes.txt": ""}
    config_overrides = {"include_patterns": ["*.py", "*.txt"]}
    expected = sorted(["main.py", "utils.py", "notes.txt"])
    files = run_scan_with_config(tmp_path, structure, config_overrides)
    assert files == expected, "Include patterns (*.py, *.txt) did not work as expected"


def test_empty_include_patterns_includes_all_non_excluded_files(tmp_path: Path):
    """Ensures that an empty `include_patterns` list includes all files not otherwise excluded."""
    structure = {
        "file.py": "",
        "file.txt": "",
        "file.log": "log data",
        "image.jpg": None,
    }
    config_overrides = {
        "include_patterns": [],
        "exclude_patterns": ["*.log"],
    }
    expected = sorted(["file.py", "file.txt", "image.jpg"])
    files = run_scan_with_config(tmp_path, structure, config_overrides)
    assert (
        files == expected
    ), "Empty include_patterns did not include all non-excluded files"


def test_exclude_dirs_removes_entire_directories(tmp_path: Path):
    """Ensures that directories listed in `exclude_dirs` are completely ignored."""
    structure = {
        "src": {"main.py": ""},
        "docs": {"index.md": ""},
        "tests": {"test_main.py": ""},
    }
    files = run_scan_with_config(tmp_path, structure, {})
    assert files == ["src/main.py"], "Default exclude_dirs (docs, tests) failed"


def test_exclude_patterns_for_directories(tmp_path: Path):
    """Ensures `exclude_patterns` can remove entire directories."""
    structure = {
        "main.py": "",
        "node_modules": {"package": {"index.js": ""}},
        "src": {"app.py": "", "vendor": {"lib.js": ""}},
    }
    config_overrides = {
        "exclude_dirs": [],
        "exclude_patterns": ["node_modules", "src/vendor/*"],
        "include_patterns": ["*.py", "*.js"],
    }
    expected = sorted(["main.py", "src/app.py"])
    files = run_scan_with_config(tmp_path, structure, config_overrides)
    assert files == expected, "exclude_patterns for directories failed"


def test_specific_file_exclusion(tmp_path: Path):
    """Ensures `exclude_files` removes files with exact path matches."""
    structure = {
        "config.py": "",
        "main.py": "",
        "utils": {"helpers.py": "", "deprecated.py": ""},
    }
    config_overrides = {
        "exclude_files": ["utils/deprecated.py"],
        "include_patterns": ["*.py"],
    }
    expected = sorted(["config.py", "main.py", "utils/helpers.py"])
    files = run_scan_with_config(tmp_path, structure, config_overrides)
    assert files == expected, "exclude_files did not exclude the specified file"


def test_max_file_size_limit(tmp_path: Path):
    """Ensures `max_file_size_kb` correctly excludes files that are too large."""
    structure = {
        "small.txt": "a" * 500,
        "exact.txt": "b" * 1024,
        "large.txt": "c" * 1500,
        "empty.txt": None,
    }
    config_overrides = {"max_file_size_kb": 1, "include_patterns": ["*.txt"]}
    expected = sorted(["empty.txt", "exact.txt", "small.txt"])
    files = run_scan_with_config(tmp_path, structure, config_overrides)
    assert files == expected, "max_file_size_kb filter failed"


def test_exclude_pattern_overrides_include_pattern(tmp_path: Path):
    """Ensures that an `exclude_patterns` rule takes precedence over an `include_patterns` rule."""
    structure = {
        "feature.py": "",
        "feature_test.py": "",
        "another.py": "",
    }
    config_overrides = {
        "include_patterns": ["*.py"],
        "exclude_patterns": ["*_test.py"],
    }
    expected = sorted(["another.py", "feature.py"])
    files = run_scan_with_config(tmp_path, structure, config_overrides)
    assert files == expected, "Exclude pattern did not override include pattern"


def test_scanning_a_subdirectory(tmp_path: Path):
    """Ensures scanning a specific subdirectory works correctly while applying root-level rules."""
    structure = {
        "file_in_root.txt": "root content",
        "target_dir": {
            "sub_file1.py": "py content",
            "sub_file2.txt": "text content",
            "deep_subdir": {"another.py": ""},
            "excluded_by_name_in_sub": {"test.py": ""},
        },
        "other_dir": {"other_file.py": ""},
    }
    config_overrides = {
        "include_patterns": ["*.py", "*.txt"],
        "exclude_dirs": ["target_dir/excluded_by_name_in_sub"],
    }
    expected = sorted(
        [
            "target_dir/sub_file1.py",
            "target_dir/sub_file2.txt",
            "target_dir/deep_subdir/another.py",
        ]
    )
    files = run_scan_with_config(
        tmp_path, structure, config_overrides, scan_target_subdir="target_dir"
    )
    assert files == expected, "Scanning a subdirectory with relative excludes failed"


def test_verbose_output_for_skipped_items(tmp_path: Path, capsys, strip_ansi_codes):
    """Ensures that verbose mode correctly logs the reasons for skipping files and dirs."""
    structure = {
        "large_file.txt": "a" * 2048,
        "explicitly_excluded.txt": "content",
        "docs": {"guide.md": "content"},
    }
    config_overrides = {
        "verbose": True,
        "max_file_size_kb": 1,
        "exclude_files": ["explicitly_excluded.txt"],
        "exclude_dirs": ["docs"],
        "include_patterns": ["*.txt", "*.md"],
    }
    run_scan_with_config(tmp_path, structure, config_overrides)
    captured = capsys.readouterr()
    stderr = strip_ansi_codes(captured.err)
    assert "Skipping large file: large_file.txt" in stderr
    assert "Skipping explicitly excluded file: explicitly_excluded.txt" in stderr


def test_scanner_handles_stat_error_gracefully(tmp_path: Path, mocker):
    """Ensures the scanner does not crash if a file is deleted during the scan."""
    (tmp_path / "stable.txt").write_text("I exist")
    (tmp_path / "unstable.txt").write_text("I will disappear")

    # Mock Path.stat to raise an error for the 'unstable.txt' file
    original_stat = Path.stat

    def mock_stat(self, *args, **kwargs):
        if self.name == "unstable.txt":
            raise FileNotFoundError("File disappeared")
        return original_stat(self, *args, **kwargs)

    mocker.patch("pathlib.Path.stat", mock_stat)

    config_overrides = {"include_patterns": ["*.txt"], "verbose": True}
    found_files = run_scan_with_config(tmp_path, {}, config_overrides)

    assert "stable.txt" in found_files
    assert "unstable.txt" not in found_files
