# tests/test_file_processor.py

"""
Unit tests for the file_processor.py module.

These tests cover the main file processing logic, including:
- Text and binary file detection
- Encoding fallback and error handling
- File size and access error scenarios

All tests use pytest and temporary directories for isolation.
"""

from pathlib import Path
from typing import Any, Optional

import pytest

from codecat.file_processor import process_file


def get_test_config(overrides: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """
    Helper to create a base config for tests, with optional overrides.

    This ensures each test can customize config as needed without side effects.
    """
    config = {
        "verbose": True,
        "stop_on_error": False,
        "max_file_size_kb": 1024,
    }
    if overrides:
        config.update(overrides)
    return config


def test_process_file_empty(tmp_path: Path):
    """Test processing an empty file returns text_content with empty string."""
    test_file = tmp_path / "empty.txt"
    test_file.touch()
    config = get_test_config()
    result = process_file(test_file, tmp_path, config)
    assert result.status == "text_content"
    assert result.content == ""
    assert result.encoding_used is not None


def test_process_file_utf8(tmp_path: Path):
    """Test processing a standard UTF-8 file is decoded correctly."""
    content = "Hello, Codecat! 🐱"
    test_file = tmp_path / "utf8.txt"
    test_file.write_text(content, encoding="utf-8")
    config = get_test_config()
    result = process_file(test_file, tmp_path, config)
    assert result.status == "text_content"
    assert result.content == content
    assert result.encoding_used == "utf-8"


def test_process_file_cp1252_fallback(tmp_path: Path):
    """
    Test fallback to cp1252 encoding when UTF-8 fails.

    The Euro sign (0x80 in cp1252) is invalid in UTF-8, so this checks fallback logic.
    """
    content_bytes = b"Price: 10 \x80"
    expected_content_str = "Price: 10 €"
    test_file = tmp_path / "cp1252.txt"
    test_file.write_bytes(content_bytes)
    config = get_test_config()
    result = process_file(test_file, tmp_path, config)
    assert result.status == "text_content"
    assert result.content == expected_content_str
    assert result.encoding_used == "cp1252"


def test_process_file_binary_by_nulls(tmp_path: Path):
    """
    Test binary detection due to a high percentage of null bytes.

    Ensures files with >10% null bytes are flagged as binary.
    """
    binary_content = b"\x00" * 500 + b"some text" * 50
    test_file = tmp_path / "app.exe"
    test_file.write_bytes(binary_content)
    config = get_test_config()
    result = process_file(test_file, tmp_path, config)
    assert result.status == "binary_file"
    assert result.content is None


def test_process_file_os_error_no_stop(tmp_path: Path):
    """
    Test handling of an OSError when the file cannot be accessed.

    With stop_on_error = False, should return skipped_access_error.
    """
    non_existent_file = tmp_path / "i_do_not_exist.txt"
    config = get_test_config({"stop_on_error": False})
    result = process_file(non_existent_file, tmp_path, config)
    assert result.status == "skipped_access_error"
    assert result.error_message is not None
    assert "OS error accessing file" in result.error_message


def test_process_file_os_error_with_stop(tmp_path: Path):
    """
    Test that an OSError is raised when stop_on_error is True.

    This simulates strict error handling for file access issues.
    """
    non_existent_file = tmp_path / "i_do_not_exist_either.txt"
    config = get_test_config({"stop_on_error": True})
    with pytest.raises(OSError):
        process_file(non_existent_file, tmp_path, config)


def test_process_file_unsupported_encoding_no_stop(tmp_path: Path):
    """
    Test file with unsupported encoding, stop_on_error = False.

    Should return read_error and a helpful error message.
    """
    # The byte 0x9D is undefined in cp1252 and invalid in a UTF-8 sequence.
    # This guarantees failure for both our decoders.
    invalid_bytes = b"this is almost valid text but contains \x9d"
    test_file = tmp_path / "invalid_encoding.txt"
    test_file.write_bytes(invalid_bytes)

    config = get_test_config({"stop_on_error": False, "verbose": False})
    result = process_file(test_file, tmp_path, config)

    assert result.status == "read_error"
    assert result.error_message is not None
    assert "Failed to decode as text" in result.error_message


def test_process_file_unsupported_encoding_with_stop(tmp_path: Path):
    """
    Test file with unsupported encoding, stop_on_error = True.

    Should raise the UnicodeDecodeError from the last attempted decode.
    """
    invalid_bytes = b"this is almost valid text but contains \x9d"
    test_file = tmp_path / "invalid_encoding_stop.txt"
    test_file.write_bytes(invalid_bytes)

    config = get_test_config({"stop_on_error": True, "verbose": False})
    # Expecting the error from the last attempted decode to be propagated
    with pytest.raises(UnicodeDecodeError):
        process_file(test_file, tmp_path, config)
