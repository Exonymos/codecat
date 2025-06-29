# src/codecat/file_processor.py

"""
Handles the processing of individual files.

This module is responsible for reading a file's content, determining if it's
a text or binary file, and handling any read or decoding errors. It is
designed to be called from a worker thread.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Optional

FileStatus = Literal[
    "text_content", "binary_file", "read_error", "skipped_access_error"
]


@dataclass
class ProcessedFileData:
    """A simple data structure to hold the result of processing a single file."""

    path: Path
    relative_path: Path
    status: FileStatus
    content: Optional[str] = None
    error_message: Optional[str] = None
    encoding_used: Optional[str] = None


# --- Constants ---
TEXT_ENCODINGS_TO_TRY: list[str] = ["utf-8", "cp1252"]
BINARY_DETECTION_CHUNK_SIZE: int = 4096
NULL_BYTE_THRESHOLD_PERCENT: float = 10.0


# --- Helper Functions ---


def _is_likely_binary_by_nulls(chunk: bytes) -> bool:
    """
    Checks if a chunk of bytes has a high percentage of null bytes,
    which is a strong indicator of a binary file.
    """
    if not chunk:
        return False
    null_bytes = chunk.count(b"\x00")
    return (
        len(chunk) > 0 and (null_bytes / len(chunk)) * 100 > NULL_BYTE_THRESHOLD_PERCENT
    )


def _try_decode_bytes(
    file_bytes: bytes,
) -> tuple[Optional[str], Optional[str], Optional[UnicodeDecodeError]]:
    """
    Attempts to decode a byte string using a list of common text encodings.
    Also normalizes line endings to LF ('\\n') for consistent processing.

    Returns:
        A tuple of (content, encoding, None) on success, or
        (None, None, last_decode_error) on failure.
    """
    last_decode_error: Optional[UnicodeDecodeError] = None
    for enc in TEXT_ENCODINGS_TO_TRY:
        try:
            decoded_content = file_bytes.decode(enc, errors="strict")
            # Normalize all line endings (\r\n, \r, \n) to a single \n.
            # This prevents issues when writing the final markdown file.
            normalized_content = "\n".join(decoded_content.splitlines())
            return normalized_content, enc, None
        except UnicodeDecodeError as e:
            last_decode_error = e
    return None, None, last_decode_error


def _handle_decode_failure(
    file_path: Path,
    relative_p: Path,
    decode_error: Optional[UnicodeDecodeError],
    config: dict[str, Any],
) -> ProcessedFileData:
    """Creates the ProcessedFileData for a file that failed all decoding attempts."""
    stop_on_error = config.get("stop_on_error", False)

    if stop_on_error and decode_error:
        raise decode_error

    encodings_tried_str = ", ".join(TEXT_ENCODINGS_TO_TRY)
    error_message = f"Failed to decode as text using [{encodings_tried_str}]."
    if decode_error:
        error_message += (
            f" Last error ({type(decode_error).__name__}): {str(decode_error)}"
        )

    return ProcessedFileData(
        path=file_path,
        relative_path=relative_p,
        status="read_error",
        error_message=error_message,
    )


# --- Main Processing Function ---


def process_file(
    file_path: Path,
    cli_project_path: Path,
    config: dict[str, Any],
) -> ProcessedFileData:
    """
    Processes a single file: reads its content, detects if it's binary, or handles errors.

    This function is designed to be a self-contained worker that does not perform
    any direct console output. It returns a structured result for the main thread to handle.
    """
    stop_on_error = config.get("stop_on_error", False)

    try:
        relative_p = file_path.relative_to(cli_project_path)
    except ValueError:  # pragma: no cover
        relative_p = Path(file_path.name)

    # 1. Read file bytes, handling OS errors
    try:
        file_bytes = file_path.read_bytes()
    except OSError as e:
        err_msg = f"OS error accessing file: {type(e).__name__}: {e}"
        if stop_on_error:
            raise
        return ProcessedFileData(
            path=file_path,
            relative_path=relative_p,
            status="skipped_access_error",
            error_message=err_msg,
        )

    # 2. Handle empty file
    if not file_bytes:
        return ProcessedFileData(
            path=file_path,
            relative_path=relative_p,
            status="text_content",
            content="",
            encoding_used=TEXT_ENCODINGS_TO_TRY[0],
        )

    # 3. Strong binary check
    if _is_likely_binary_by_nulls(file_bytes[:BINARY_DETECTION_CHUNK_SIZE]):
        return ProcessedFileData(
            path=file_path, relative_path=relative_p, status="binary_file"
        )

    # 4. Attempt to decode as text
    content_str, encoding_used, decode_error = _try_decode_bytes(file_bytes)

    if content_str is not None and encoding_used is not None:
        return ProcessedFileData(
            path=file_path,
            relative_path=relative_p,
            status="text_content",
            content=content_str,
            encoding_used=encoding_used,
        )

    # 5. Handle decode failure
    return _handle_decode_failure(file_path, relative_p, decode_error, config)
