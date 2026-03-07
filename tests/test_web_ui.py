# tests/test_web_ui.py

"""
Tests for the web_ui module.

Structure
---------
Unit tests  — pure functions that need no network:
    _normalize_patterns, _build_page, _find_free_port, _build_run_config,
    _build_subprocess_cmd

Integration tests — spin up a real server on a random available port and
    issue real HTTP requests with http.client.  No subprocess is spawned for
    ``/api/run``; only the error-path (invalid JSON, bad project path) is
    covered to keep the test suite fast and hermetic.
"""

import http.client
import json
import socket
import sys
import threading
from pathlib import Path

import pytest

from codecat.web_ui import (
    _build_page,
    _build_run_config,
    _build_subprocess_cmd,
    _find_free_port,
    _make_handler,
    _normalize_patterns,
    _ReuseAddrServer,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _free_port() -> int:
    """Return an available loopback port for test servers."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def server(tmp_path: Path):
    """
    Spin up a real ThreadingTCPServer bound to a random port and yield
    ``(host, port, project_path)``.  The server is shut down after the test.
    """
    port = _free_port()
    httpd = _ReuseAddrServer(("127.0.0.1", port), _make_handler(tmp_path))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield "127.0.0.1", port, tmp_path
    httpd.shutdown()
    httpd.server_close()


def _get(host: str, port: int, path: str) -> tuple[int, bytes]:
    conn = http.client.HTTPConnection(host, port, timeout=5)
    conn.request("GET", path)
    resp = conn.getresponse()
    return resp.status, resp.read()


def _post(
    host: str, port: int, path: str, body: bytes, content_type: str = "application/json"
) -> tuple[int, bytes]:
    conn = http.client.HTTPConnection(host, port, timeout=5)
    conn.request(
        "POST",
        path,
        body=body,
        headers={"Content-Type": content_type, "Content-Length": str(len(body))},
    )
    resp = conn.getresponse()
    return resp.status, resp.read()


# ---------------------------------------------------------------------------
# Unit tests — _normalize_patterns
# ---------------------------------------------------------------------------


class TestNormalizePatterns:
    def test_empty_list(self):
        assert _normalize_patterns([]) == []

    def test_simple_strings(self):
        assert _normalize_patterns(["*.py", "*.js"]) == ["*.py", "*.js"]

    def test_comma_separated(self):
        assert _normalize_patterns(["*.py, *.js"]) == ["*.py", "*.js"]

    def test_newline_separated(self):
        assert _normalize_patterns(["*.py\n*.js"]) == ["*.py", "*.js"]

    def test_mixed_separators(self):
        result = _normalize_patterns(["*.py,*.js\n*.ts"])
        assert result == ["*.py", "*.js", "*.ts"]

    def test_strips_whitespace(self):
        assert _normalize_patterns(["  *.py  ", " *.js "]) == ["*.py", "*.js"]

    def test_drops_empty_entries(self):
        assert _normalize_patterns(["*.py", "", "  ", "*.js"]) == ["*.py", "*.js"]

    def test_non_string_items_are_coerced(self):
        # The frontend may pass integers or None in rare cases.
        result = _normalize_patterns([123, None])
        assert result == ["123", "None"]

    def test_glob_patterns_preserved(self):
        patterns = [".github/*", "src/**/*.py"]
        assert _normalize_patterns(patterns) == patterns

    def test_multiline_textarea_input(self):
        """Simulates a raw textarea value sent from the frontend."""
        raw = ".github/*\nsrc/codecat/*.py\ntests/*.py"
        assert _normalize_patterns([raw]) == [
            ".github/*",
            "src/codecat/*.py",
            "tests/*.py",
        ]


# ---------------------------------------------------------------------------
# Unit tests — _build_page
# ---------------------------------------------------------------------------


class TestBuildPage:
    def test_returns_bytes(self, tmp_path: Path):
        assert isinstance(_build_page(tmp_path), bytes)

    def test_contains_doctype(self, tmp_path: Path):
        assert b"<!DOCTYPE html>" in _build_page(tmp_path)

    def test_path_is_json_encoded(self, tmp_path: Path):
        page = _build_page(tmp_path).decode("utf-8")
        path_json = json.dumps(str(tmp_path))
        assert f"window.CODECAT_PATH = {path_json};" in page

    def test_backslash_path_is_safe(self):
        """Windows paths contain backslashes; json.dumps must escape them."""
        win_path = Path("C:\\Users\\joy\\my project\\codecat")
        page = _build_page(win_path).decode("utf-8")
        # The JSON encoding should use \\ for each backslash.
        assert "C:\\\\Users\\\\joy" in page

    def test_path_with_special_chars(self):
        """Paths that contain braces/quotes must not break the JS block."""
        tricky = Path('/tmp/proj{"key":"val"}')
        page = _build_page(tricky).decode("utf-8")
        # json.dumps escapes the inner quotes; the page must still be valid
        assert "window.CODECAT_PATH" in page
        assert "<script>" in page

    def test_no_external_resources(self, tmp_path: Path):
        page = _build_page(tmp_path).decode("utf-8")
        for cdn in ("googleapis.com", "cdnjs.cloudflare", "jsdelivr", "unpkg.com"):
            assert cdn not in page

    def test_charset_and_viewport_meta(self, tmp_path: Path):
        page = _build_page(tmp_path).decode("utf-8")
        assert 'charset="UTF-8"' in page
        assert 'name="viewport"' in page


# ---------------------------------------------------------------------------
# Unit tests — _find_free_port
# ---------------------------------------------------------------------------


class TestFindFreePort:
    def test_returns_usable_port(self):
        port = _find_free_port(9000)
        assert 9000 <= port < 9020
        # Verify the port is actually bindable.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", port))

    def test_skips_occupied_port(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
            occupied.bind(("127.0.0.1", 0))
            occupied.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            start = occupied.getsockname()[1]
            # The scanner must skip `start` and return the next free port.
            result = _find_free_port(start)
            assert result != start

    def test_raises_when_range_exhausted(self):
        sockets: list[socket.socket] = []
        try:
            # Occupy 5 consecutive ports.
            first_port = _free_port()
            for offset in range(5):
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    s.bind(("127.0.0.1", first_port + offset))
                    sockets.append(s)
                except OSError:
                    pass
            with pytest.raises(OSError, match="Could not find a free port"):
                _find_free_port(first_port, max_tries=len(sockets))
        finally:
            for s in sockets:
                s.close()


# ---------------------------------------------------------------------------
# Unit tests — _build_run_config
# ---------------------------------------------------------------------------


class TestBuildRunConfig:
    def test_empty_payload(self):
        assert _build_run_config({}) == {}

    def test_output_file(self):
        cfg = _build_run_config({"outputFile": "out.md"})
        assert cfg["output_file"] == "out.md"

    def test_empty_output_file_not_included(self):
        cfg = _build_run_config({"outputFile": "  "})
        assert "output_file" not in cfg

    def test_includes_and_excludes(self):
        cfg = _build_run_config({"includes": ["*.py", "*.js"], "excludes": ["*.pyc"]})
        assert cfg["include_patterns"] == ["*.py", "*.js"]
        assert cfg["exclude_patterns"] == ["*.pyc"]

    def test_no_header_true_sets_generate_header_false(self):
        cfg = _build_run_config({"noHeader": True})
        assert cfg["generate_header"] is False

    def test_no_header_false_sets_generate_header_true(self):
        cfg = _build_run_config({"noHeader": False})
        assert cfg["generate_header"] is True

    def test_no_header_absent_not_included(self):
        cfg = _build_run_config({})
        assert "generate_header" not in cfg

    def test_empty_patterns_not_included(self):
        cfg = _build_run_config({"includes": [], "excludes": []})
        assert "include_patterns" not in cfg
        assert "exclude_patterns" not in cfg

    def test_glob_patterns_preserved_intact(self):
        cfg = _build_run_config({"includes": [".github/*", "src/**/*.py"]})
        assert cfg["include_patterns"] == [".github/*", "src/**/*.py"]


# ---------------------------------------------------------------------------
# Unit tests — _build_subprocess_cmd
# ---------------------------------------------------------------------------


class TestBuildSubprocessCmd:
    def test_basic_structure(self, tmp_path: Path):
        cfg = tmp_path / "run.json"
        cmd = _build_subprocess_cmd(tmp_path, cfg, dry_run=False)
        assert cmd[0] == sys.executable
        assert cmd[1:4] == ["-m", "codecat", "run"]
        assert str(tmp_path) in cmd
        assert "--config" in cmd
        assert str(cfg) in cmd

    def test_dry_run_flag(self, tmp_path: Path):
        cfg = tmp_path / "run.json"
        cmd = _build_subprocess_cmd(tmp_path, cfg, dry_run=True)
        assert "--dry-run" in cmd

    def test_no_dry_run_flag_by_default(self, tmp_path: Path):
        cfg = tmp_path / "run.json"
        cmd = _build_subprocess_cmd(tmp_path, cfg, dry_run=False)
        assert "--dry-run" not in cmd

    def test_no_include_exclude_on_cmd_line(self, tmp_path: Path):
        cfg = tmp_path / "run.json"
        cmd = _build_subprocess_cmd(tmp_path, cfg, dry_run=False)
        assert "--include" not in cmd
        assert "--exclude" not in cmd

    def test_shell_false_safe(self, tmp_path: Path):
        """Verify cmd is a plain list (no shell-expansion risk)."""
        cfg = tmp_path / "run.json"
        cmd = _build_subprocess_cmd(tmp_path, cfg, dry_run=False)
        assert isinstance(cmd, list)
        assert all(isinstance(part, str) for part in cmd)


# ---------------------------------------------------------------------------
# Integration tests — HTTP server
# ---------------------------------------------------------------------------


class TestHTTPServer:
    def test_get_root_returns_200(self, server):
        host, port, _ = server
        status, body = _get(host, port, "/")
        assert status == 200
        assert b"<!DOCTYPE html>" in body

    def test_get_root_contains_project_path(self, server):
        host, port, project_path = server
        status, body = _get(host, port, "/")
        assert status == 200
        path_json = json.dumps(str(project_path))
        assert path_json.encode() in body

    def test_get_index_html_alias(self, server):
        host, port, _ = server
        status, _ = _get(host, port, "/index.html")
        assert status == 200

    def test_get_unknown_path_returns_404(self, server):
        host, port, _ = server
        status, body = _get(host, port, "/does/not/exist")
        assert status == 404
        assert b"Not Found" in body

    def test_get_config_missing_file(self, server):
        host, port, _ = server
        status, body = _get(host, port, "/api/config")
        assert status == 200
        data = json.loads(body)
        assert data["success"] is False
        assert "not found" in data["error"].lower()

    def test_get_config_existing_file(self, server):
        host, port, project_path = server
        cfg = {"output_file": "my_output.md", "include_patterns": ["*.py"]}
        (project_path / ".codecat_config.json").write_text(
            json.dumps(cfg), encoding="utf-8"
        )
        status, body = _get(host, port, "/api/config")
        assert status == 200
        data = json.loads(body)
        assert data["success"] is True
        assert data["data"]["output_file"] == "my_output.md"

    def test_get_config_query_string_ignored(self, server):
        """Query strings must not affect routing."""
        host, port, _ = server
        status, _ = _get(host, port, "/api/config?foo=bar")
        assert status == 200

    def test_post_config_saves_file(self, server):
        host, port, project_path = server
        payload = json.dumps(
            {
                "outputFile": "saved.md",
                "includes": ["*.py"],
                "excludes": ["*.pyc"],
                "noHeader": True,
            }
        ).encode()
        status, body = _post(host, port, "/api/config", payload)
        assert status == 200
        data = json.loads(body)
        assert data["success"] is True

        saved = json.loads(
            (project_path / ".codecat_config.json").read_text(encoding="utf-8")
        )
        assert saved["output_file"] == "saved.md"
        assert saved["include_patterns"] == ["*.py"]
        assert saved["exclude_patterns"] == ["*.pyc"]
        assert saved["generate_header"] is False

    def test_post_config_glob_patterns_preserved(self, server):
        """Glob patterns with wildcards must be stored verbatim."""
        host, port, project_path = server
        payload = json.dumps(
            {"includes": [".github/*", "src/**/*.py"], "excludes": []}
        ).encode()
        _post(host, port, "/api/config", payload)
        saved = json.loads(
            (project_path / ".codecat_config.json").read_text(encoding="utf-8")
        )
        assert saved["include_patterns"] == [".github/*", "src/**/*.py"]

    def test_post_config_invalid_json_returns_400(self, server):
        host, port, _ = server
        status, body = _post(
            host, port, "/api/config", b"not json at all", "application/json"
        )
        assert status == 400
        data = json.loads(body)
        assert data["success"] is False

    def test_post_config_body_too_large_returns_400(self, server):
        host, port, _ = server
        big = json.dumps({"outputFile": "x" * (65 * 1024)}).encode()
        status, body = _post(host, port, "/api/config", big)
        assert status == 400
        data = json.loads(body)
        assert "64 KB" in data["error"]

    def test_post_unknown_path_returns_404(self, server):
        host, port, _ = server
        status, body = _post(host, port, "/api/unknown", b"{}")
        assert status == 404
        assert b"Not Found" in body

    def test_post_run_invalid_json_returns_400(self, server):
        host, port, _ = server
        status, body = _post(host, port, "/api/run", b"{{bad json}}")
        assert status == 400
        assert b"Error" in body

    def test_post_run_body_too_large_returns_400(self, server):
        host, port, _ = server
        big = b"x" * (65 * 1024)
        status, body = _post(host, port, "/api/run", big)
        assert status == 400
        data = json.loads(body)
        assert "64 KB" in data["error"]
