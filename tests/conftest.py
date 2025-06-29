# tests/conftest.py

"""
Global fixtures and configuration for the Pytest suite.

This file provides shared fixtures and helper functions that are
available to all test files in the project.
"""

import re

import pytest


@pytest.fixture(scope="session")
def strip_ansi_codes():
    """
    Returns a helper function to remove ANSI escape sequences from a string,
    which is useful for cleaning up terminal output for assertions.
    """
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    def _strip(text: str) -> str:
        return ansi_escape.sub("", text)

    return _strip
