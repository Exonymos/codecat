# src/codecat/config.py

"""
Handles loading and managing Codecat's configuration.

This module defines the default configuration, loads a user-provided JSON config,
and merges them with any command-line arguments to produce the final,
effective configuration used by the application.
"""

import copy
import json
from pathlib import Path
from typing import Any, Optional

import typer
from typer import colors as typer_colors

# Import constants for default config file names.
from codecat.constants import DEFAULT_CONFIG_FILENAME, DEFAULT_OUTPUT_FILENAME

# Default configuration for Codecat.
# Keys starting with "_" are treated as comments and ignored by the parser.
DEFAULT_CONFIG: dict[str, Any] = {
    "_comment_main": "This is the default configuration for Codecat. You can customize it for your project.",
    "output_file": DEFAULT_OUTPUT_FILENAME,
    "_comment_patterns": "Use glob patterns (like *.py, src/*) to control which files are included or excluded.",
    "include_patterns": [
        "*.py",
        "*.pyw",
        "*.java",
        "*.js",
        "*.ts",
        "*.html",
        "*.css",
        "*.scss",
        "*.go",
        "*.rs",
        "*.c",
        "*.cpp",
        "*.h",
        "*.hpp",
        "*.cs",
        "*.sh",
        "*.ps1",
        "*.rb",
        "*.php",
        "*.sql",
        "*.json",
        "*.xml",
        "*.yml",
        "*.yaml",
        "*.toml",
        "*.ini",
        "*.cfg",
        "*.md",
        "*.txt",
        "Dockerfile",
        ".dockerignore",
        ".gitignore",
        ".flake8",
    ],
    "exclude_patterns": [
        "__pycache__",
        "*.pyc",
        "*.pyo",
        "*.pyd",
        "*.so",
        "*.egg-info",
        "*.dist-info",
        "*.log",
        "*.tmp",
        "*.bak",
        "*.swp",
        "*.lock",
        ".DS_Store",
        "Thumbs.db",
        "venv",
        "venv*",
        ".venv",
        ".*env*",
    ],
    "_comment_dirs": "List specific directory names to exclude entirely from the scan.",
    "exclude_dirs": [
        ".git",
        ".hg",
        ".svn",
        ".vscode",
        ".idea",
        ".pytest_cache",
        "node_modules",
        "vendor",
        "target",
        "build",
        "dist",
        "docs",
        "site",
        "__pycache__",
        "tests",
        "test",
    ],
    "_comment_files": "List specific, exact file names to exclude.",
    "exclude_files": ["codecat_config.json", "codecat_output.md"],
    "_comment_settings": "General application settings.",
    "max_file_size_kb": 1024,
    "stop_on_error": False,
    "generate_header": True,
    "_comment_languages": "Map file extensions to language hints for Markdown code blocks.",
    "language_hints": {
        ".py": "python",
        ".pyw": "python",
        ".java": "java",
        ".js": "javascript",
        ".ts": "typescript",
        ".html": "html",
        ".css": "css",
        ".scss": "scss",
        ".go": "go",
        ".rs": "rust",
        ".c": "c",
        ".cpp": "cpp",
        ".h": "c",
        ".hpp": "cpp",
        ".cs": "csharp",
        ".sh": "bash",
        ".ps1": "powershell",
        ".rb": "ruby",
        ".php": "php",
        ".sql": "sql",
        ".json": "json",
        ".xml": "xml",
        ".yml": "yaml",
        ".yaml": "yaml",
        ".toml": "toml",
        ".ini": "ini",
        ".cfg": "ini",
        ".md": "markdown",
        ".txt": "text",
        ".dockerfile": "dockerfile",
        "dockerfile": "dockerfile",
        ".gitignore": "text",
        ".dockerignore": "text",
        ".flake8": "ini",
    },
}


def _load_user_config_from_file(
    config_path: Path,
) -> tuple[Optional[dict[str, Any]], bool]:
    """
    Loads and parses a user-defined JSON configuration file.

    Returns a tuple of (user_config_dict, loaded_successfully).
    If the file is missing or invalid, returns (None, False).
    """
    if config_path.exists() and config_path.is_file():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                # Remove comment keys before parsing.
                user_data = json.load(f)
                user_config = {
                    k: v for k, v in user_data.items() if not k.startswith("_")
                }
                return user_config, True
        except (json.JSONDecodeError, IOError) as e:
            typer.secho(
                f"Notice: Could not load or parse config '{config_path.resolve()}'. Error: {e}.",
                fg=typer_colors.YELLOW,
                err=True,
            )
            return None, False
    return None, False


def _apply_cli_overrides(
    config: dict[str, Any],
    output_file_name_override: Optional[str],
    include_patterns_override: Optional[list[str]],
    exclude_patterns_override: Optional[list[str]],
    no_header_override: Optional[bool],
) -> None:
    """
    Applies command-line argument overrides to the configuration dictionary.

    This ensures CLI flags always take precedence over config file or defaults.
    """
    if output_file_name_override is not None:
        config["output_file"] = output_file_name_override
    if include_patterns_override:
        config["include_patterns"] = include_patterns_override
    if exclude_patterns_override:
        config["exclude_patterns"] = exclude_patterns_override
    if no_header_override is True:
        config["generate_header"] = False


def load_config(
    project_path: Path,
    config_file_path_override: Optional[Path] = None,
    output_file_name_override: Optional[str] = None,
    include_patterns_override: Optional[list[str]] = None,
    exclude_patterns_override: Optional[list[str]] = None,
    no_header_override: Optional[bool] = None,
) -> tuple[dict[str, Any], bool, Path]:
    """
    Loads configuration by merging defaults, user file, and CLI overrides.

    Returns a tuple of (final_config_dict, user_config_loaded, config_path_used).
    """
    effective_config = copy.deepcopy(DEFAULT_CONFIG)

    # Determine which config file to load (CLI override or default location).
    actual_config_path_to_load = (
        config_file_path_override or project_path / DEFAULT_CONFIG_FILENAME
    )

    user_config_data, user_config_loaded = _load_user_config_from_file(
        actual_config_path_to_load
    )

    # If user config is loaded, update defaults with user values.
    if user_config_loaded and user_config_data:
        user_hints = user_config_data.pop("language_hints", None)
        if isinstance(user_hints, dict):
            effective_config["language_hints"].update(user_hints)

        for key, value in user_config_data.items():
            if key in effective_config:
                effective_config[key] = value

    # Apply any CLI argument overrides.
    _apply_cli_overrides(
        effective_config,
        output_file_name_override,
        include_patterns_override,
        exclude_patterns_override,
        no_header_override,
    )

    # Remove internal comment keys before returning config to the app.
    final_config = {k: v for k, v in effective_config.items() if not k.startswith("_")}

    return final_config, user_config_loaded, actual_config_path_to_load
