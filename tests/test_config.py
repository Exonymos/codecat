# tests/test_config.py

"""
Verifies the configuration loading and merging logic.

These tests ensure that Codecat correctly loads the default configuration,
replaces it with a user-provided config file, and applies command-line
overrides, including handling various error conditions.
"""

import json
from pathlib import Path

from codecat.config import load_config


def test_loading_with_no_user_config(tmp_path: Path):
    """Ensures that the default config is loaded when no user config exists."""
    config, loaded, _ = load_config(tmp_path)
    assert not loaded
    assert config["output_file"] == "codecat_output.md"
    assert "*.py" in config["include_patterns"]


def test_loading_a_valid_user_config(tmp_path: Path):
    """Ensures a user's config file correctly overrides default settings."""
    user_config_data = {
        "output_file": "my_custom_output.md",
        "exclude_dirs": [".git", "my_special_dir"],
    }
    user_config_path = tmp_path / ".codecat_config.json"
    user_config_path.write_text(json.dumps(user_config_data))

    config, loaded, _ = load_config(tmp_path)
    assert loaded
    assert config["output_file"] == "my_custom_output.md"
    assert "my_special_dir" in config["exclude_dirs"]
    assert ".hg" not in config["exclude_dirs"]


def test_cli_overrides_take_precedence(tmp_path: Path):
    """Ensures that CLI flags always have the final say over any config file."""
    user_config_data = {"output_file": "from_file.md"}
    user_config_path = tmp_path / ".codecat_config.json"
    user_config_path.write_text(json.dumps(user_config_data))

    config, _, _ = load_config(
        project_path=tmp_path, output_file_name_override="from_cli.md"
    )
    assert config["output_file"] == "from_cli.md"


def test_cli_overrides_for_include_and_exclude_patterns(tmp_path: Path):
    """Ensures that include/exclude patterns from the CLI override the config file."""
    user_config_data = {
        "include_patterns": ["*.html"],
        "exclude_patterns": ["*.css"],
    }
    user_config_path = tmp_path / ".codecat_config.json"
    user_config_path.write_text(json.dumps(user_config_data))

    config, _, _ = load_config(
        project_path=tmp_path,
        include_patterns_override=["*.js"],
        exclude_patterns_override=["*.map"],
    )
    assert config["include_patterns"] == ["*.js"]
    assert config["exclude_patterns"] == ["*.map"]


def test_handling_a_malformed_json_config(tmp_path: Path, capsys):
    """Ensures a corrupt config file is handled gracefully without crashing."""
    user_config_path = tmp_path / ".codecat_config.json"
    user_config_path.write_text("{ 'malformed': json, }")  # Invalid JSON

    config, loaded, _ = load_config(tmp_path)
    assert not loaded
    assert config["output_file"] == "codecat_output.md"  # Falls back to default

    captured = capsys.readouterr()
    assert "Notice: Could not load or parse config" in captured.err


def test_merging_language_hints(tmp_path: Path):
    """Ensures that language hints from user config are merged, not replaced."""
    user_config_data = {
        "language_hints": {
            ".py": "python3",  # Override an existing hint
            ".custom": "customlang",  # Add a new hint
        }
    }
    user_config_path = tmp_path / ".codecat_config.json"
    user_config_path.write_text(json.dumps(user_config_data))

    config, _, _ = load_config(tmp_path)
    hints = config["language_hints"]
    assert hints[".py"] == "python3"  # Check override
    assert hints[".custom"] == "customlang"  # Check addition
    assert hints[".js"] == "javascript"  # Check that default hints are preserved
