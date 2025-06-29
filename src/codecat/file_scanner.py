# src/codecat/file_scanner.py

"""
Handles the discovery of files to be aggregated.

This module uses an efficient directory traversal method (`os.walk`) to find
all relevant files in a project, applying inclusion and exclusion rules from
the application's configuration to build the final file list.
"""

import fnmatch
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import typer
from rich.status import Status
from typer import colors as typer_colors

# --- Internal Helper Functions for Pattern Matching ---


def _is_path_excluded_by_pattern(
    relative_path_str: str, patterns: List[str], case_sensitive: bool = False
) -> bool:
    """Determines if a given relative path string matches any exclusion glob patterns."""
    path_to_match = relative_path_str if case_sensitive else relative_path_str.lower()
    for pattern_item in patterns:
        pattern_to_match = pattern_item if case_sensitive else pattern_item.lower()
        if fnmatch.fnmatch(path_to_match, pattern_to_match):
            return True
        # Handle directory patterns like "build/" or "dist/*"
        if pattern_to_match.endswith(("/", "/*")):
            dir_pattern_prefix = pattern_to_match.rstrip("/*") + "/"
            if path_to_match.startswith(dir_pattern_prefix):
                return True
        # Handle simple directory names like "node_modules"
        elif path_to_match.startswith(pattern_to_match + "/"):
            return True
    return False


def _is_path_included_by_pattern(
    relative_path_str: str, patterns: List[str], case_sensitive: bool = False
) -> bool:
    """Checks if a given relative path string matches any of the inclusion glob patterns."""
    if not patterns:  # If no include patterns, everything is implicitly included
        return True

    path_to_match = relative_path_str if case_sensitive else relative_path_str.lower()
    for pattern_item in patterns:
        pattern_to_match = pattern_item if case_sensitive else pattern_item.lower()
        if fnmatch.fnmatch(path_to_match, pattern_to_match):
            return True
    return False


def _passes_file_specific_checks(
    abs_item_path: Path,
    exclude_files_abs: Set[Path],
    max_size_bytes: int,
    is_verbose: bool,
    project_root_path: Path,
) -> bool:
    """Performs checks specific to files: explicit exclusion by name and max size."""
    if abs_item_path in exclude_files_abs:
        if is_verbose:
            typer.secho(
                f"Skipping explicitly excluded file: {abs_item_path.relative_to(project_root_path)}",
                fg=typer_colors.YELLOW,
                err=True,
            )
        return False

    try:
        file_size = abs_item_path.stat().st_size
        if file_size > max_size_bytes:
            if is_verbose:
                typer.secho(
                    f"Skipping large file: {abs_item_path.relative_to(project_root_path)} ({file_size / 1024:.2f}KB > {max_size_bytes / 1024:.0f}KB)",
                    fg=typer_colors.YELLOW,
                    err=True,
                )
            return False
    except (FileNotFoundError, Exception) as e:
        if is_verbose:
            typer.secho(
                f"Warning: Could not get size for file {abs_item_path}: {e}",
                fg=typer_colors.RED,
                err=True,
            )
        return False
    return True


# --- Main Scanning Function ---


def scan_project(
    project_root_path: Path,
    config: Dict[str, Any],
    cli_project_path: Path,
    status_indicator: Optional[Status] = None,
) -> List[Path]:
    """
    Scans the project directory using os.walk for efficiency and returns a list of files.
    """
    included_files_set: Set[Path] = set()
    case_sensitive_matching = False

    exclude_dirs_set: Set[str] = set(config.get("exclude_dirs", []))
    exclude_files_abs: Set[Path] = {
        (cli_project_path / f).resolve() for f in config.get("exclude_files", [])
    }
    exclude_patterns: List[str] = config.get("exclude_patterns", [])
    include_patterns: List[str] = config.get("include_patterns", [])
    max_size_bytes: int = config.get("max_file_size_kb", 1024) * 1024
    is_verbose: bool = config.get("verbose", False)

    for dirpath, dirnames, filenames in os.walk(project_root_path, topdown=True):
        current_dir_path = Path(dirpath)
        if status_indicator:
            display_path = (
                current_dir_path.relative_to(cli_project_path)
                if current_dir_path.is_relative_to(cli_project_path)
                else current_dir_path
            )
            status_indicator.update(f"Scanning: [cyan]./{display_path}[/cyan]")

        # Prune directories to prevent os.walk from descending into them.
        dirs_to_keep = []
        for d in dirnames:
            dir_rel_path = (current_dir_path / d).relative_to(cli_project_path)
            dir_rel_path_str = str(dir_rel_path).replace(os.path.sep, "/")

            if d in exclude_dirs_set or dir_rel_path_str in exclude_dirs_set:
                continue

            if _is_path_excluded_by_pattern(
                dir_rel_path_str, exclude_patterns, case_sensitive_matching
            ):
                continue

            dirs_to_keep.append(d)
        dirnames[:] = dirs_to_keep

        # Process the files in the directories that were not pruned.
        for filename in filenames:
            file_path = current_dir_path / filename
            abs_file_path = file_path.resolve()

            relative_path_for_patterns = abs_file_path.relative_to(cli_project_path)
            relative_path_str = str(relative_path_for_patterns).replace(
                os.path.sep, "/"
            )

            if _is_path_excluded_by_pattern(
                relative_path_str, exclude_patterns, case_sensitive_matching
            ):
                continue

            if not _is_path_included_by_pattern(
                relative_path_str, include_patterns, case_sensitive_matching
            ):
                continue

            if not _passes_file_specific_checks(
                abs_file_path,
                exclude_files_abs,
                max_size_bytes,
                is_verbose,
                project_root_path,
            ):
                continue

            included_files_set.add(abs_file_path)
            if is_verbose:
                typer.secho(
                    f"Including file: {relative_path_str}",
                    fg=typer_colors.GREEN,
                    err=True,
                )

    return sorted(list(included_files_set))
