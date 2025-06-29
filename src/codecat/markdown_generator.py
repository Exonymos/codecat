# src/codecat/markdown_generator.py

"""
Handles the generation of the final Markdown output file.

This module takes the list of processed file data and compiles it into a
single, well-structured Markdown document, complete with headers,
fenced code blocks, and error notices.
"""

from pathlib import Path
from typing import Any, List

# Import the data structure representing processed file results.
from codecat.file_processor import ProcessedFileData


def _get_language_hint(file_path: Path, lang_map: dict[str, str]) -> str:
    """
    Determines the language hint for a Markdown code block based on the file's
    name or extension, falling back to "text" if no specific hint is found.
    """
    # Check for exact, case-insensitive filename matches first (e.g., "Dockerfile")
    if file_path.name.lower() in lang_map:
        return lang_map[file_path.name.lower()]
    # Then check for extension matches
    return lang_map.get(file_path.suffix.lower(), "text")


def _get_dynamic_fence(content: str) -> str:
    """
    Determines the appropriate backtick fence length for the content.

    This function starts with a standard 3-backtick fence and increases the
    length until it finds a sequence not present in the content. This ensures
    that code containing triple backticks can be safely embedded.
    """
    fence_len = 3
    while "`" * fence_len in content:
        fence_len += 1
    return "`" * fence_len


def generate_markdown(
    processed_files: List[ProcessedFileData],
    project_root_path: Path,
    config: dict[str, Any],
) -> str:
    """
    Generates a single Markdown string from a list of processed files.

    Each file is rendered as a distinct section with a header and either a
    fenced code block or an informational message about its status.
    """
    main_parts: List[str] = []
    lang_map = config.get("language_hints", {})

    if config.get("generate_header", True):
        project_path_str = str(project_root_path).replace("\\", "/")
        main_parts.append(f"# Codecat: Aggregated Code for '{project_root_path.name}'")
        main_parts.append(
            f"Generated from `{len(processed_files)}` files found in `{project_path_str}`.\n"
        )

    file_blocks: List[str] = []
    for file_data in processed_files:
        block_parts: List[str] = []
        relative_path_str = str(file_data.relative_path).replace("\\", "/")
        block_parts.append(f"## File: `{relative_path_str}`\n")

        if file_data.status == "text_content" and file_data.content is not None:
            if not file_data.content.strip():
                block_parts.append("_(File is empty)_")
            else:
                lang_hint = _get_language_hint(file_data.path, lang_map)
                fence = _get_dynamic_fence(file_data.content)
                block_parts.append(f"{fence}{lang_hint}\n{file_data.content}\n{fence}")
        elif file_data.status == "binary_file":
            block_parts.append(
                f"`[INFO] Binary file detected at '{relative_path_str}'. Content not included.`"
            )
        elif file_data.status in ["read_error", "skipped_access_error"]:
            error_msg = file_data.error_message or "An unknown error occurred."
            block_parts.append(
                f"`[WARNING] Could not process file '{relative_path_str}'. Error: {error_msg}`"
            )

        file_blocks.append("\n".join(block_parts))

    if file_blocks:
        main_parts.append("\n\n---\n\n".join(file_blocks))

    # Ensure the final output ends with a single newline for POSIX compliance.
    return "\n".join(main_parts).strip() + "\n"
