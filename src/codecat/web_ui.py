# src/codecat/web_ui.py

"""
Provides an optional web-based GUI for Codecat.

Uses Python's built-in http.server to serve a single-page HTML/CSS/JS
application.  Receives configuration from the frontend and executes the
Codecat CLI via subprocess, streaming logs back in real time.

Architecture notes
------------------
- The handler class is created inside ``_make_handler`` so that
  ``project_path`` is captured by closure, avoiding shared class-level
  mutable state between requests.
- Pattern normalisation lives in one place (``_normalize_patterns``) and
  is reused by both POST handlers.
- The project path is injected into the HTML as a JSON-encoded ``<script>``
  block; no raw string substitution on user-controlled data is performed.
"""

import http.server
import json
import os
import socket
import socketserver
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path
from typing import Any

_HTML_HEAD: str = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Codecat Web UI</title>
  <style>
    :root {
      --bg:      #0d0f18;
      --surface: #171a28;
      --surf2:   #1e2235;
      --accent:  #6366f1;
      --acc-dim: #4f46e5;
      --text:    #dde1f0;
      --dim:     #8892b0;
      --border:  #2d3352;
      --ok:      #22c55e;
      --err:     #ef4444;
      --radius:  10px;
    }
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 2rem 1rem;
      line-height: 1.6;
    }
    #app {
      width: 100%;
      max-width: 860px;
      display: flex;
      flex-direction: column;
      gap: 1.5rem;
    }
    /* ---- header ---- */
    header {
      text-align: center;
      padding: 1.75rem 2rem;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
    }
    header h1 {
      font-size: clamp(1.6rem, 4vw, 2.2rem);
      font-weight: 700;
      color: #a5b4fc;
      margin-bottom: 0.35rem;
    }
    header p { color: var(--dim); font-size: 0.95rem; }
    .path-pill {
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      margin-top: 0.75rem;
      padding: 0.3rem 0.85rem;
      background: rgba(99,102,241,0.12);
      border: 1px solid rgba(99,102,241,0.3);
      border-radius: 999px;
      font-family: monospace;
      font-size: 0.82rem;
      color: #a5b4fc;
      word-break: break-all;
    }
    /* ---- card ---- */
    .card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 1.5rem 1.75rem;
    }
    .card h2 {
      font-size: 1.05rem;
      font-weight: 600;
      color: #fff;
      padding-bottom: 0.75rem;
      margin-bottom: 1.25rem;
      border-bottom: 1px solid var(--border);
    }
    /* ---- form ---- */
    .form-row { margin-bottom: 1.2rem; }
    label {
      display: block;
      font-size: 0.85rem;
      font-weight: 600;
      color: var(--dim);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 0.45rem;
    }
    input[type="text"], textarea {
      width: 100%;
      padding: 0.65rem 0.9rem;
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 7px;
      color: var(--text);
      font-family: inherit;
      font-size: 0.95rem;
      transition: border-color 0.15s;
      resize: vertical;
    }
    textarea { min-height: 88px; }
    input[type="text"]:focus,
    textarea:focus {
      outline: none;
      border-color: var(--accent);
      box-shadow: 0 0 0 3px rgba(99,102,241,0.2);
    }
    .check-row {
      display: flex;
      align-items: center;
      gap: 0.65rem;
      margin-bottom: 1rem;
    }
    .check-row input[type="checkbox"] {
      width: 1rem;
      height: 1rem;
      accent-color: var(--accent);
      cursor: pointer;
      flex-shrink: 0;
    }
    .check-row label {
      font-size: 0.93rem;
      font-weight: 500;
      color: var(--text);
      text-transform: none;
      letter-spacing: 0;
      margin: 0;
      cursor: pointer;
    }
    /* ---- buttons ---- */
    .btn-row {
      display: flex;
      flex-wrap: wrap;
      gap: 0.75rem;
      margin-top: 0.5rem;
    }
    button {
      padding: 0.6rem 1.2rem;
      border: none;
      border-radius: 7px;
      font-family: inherit;
      font-size: 0.93rem;
      font-weight: 600;
      cursor: pointer;
      transition: background-color 0.15s, opacity 0.15s;
    }
    button:disabled { opacity: 0.5; cursor: not-allowed; }
    .btn-primary { background: var(--accent); color: #fff; }
    .btn-primary:hover:not(:disabled) { background: var(--acc-dim); }
    .btn-secondary {
      background: var(--surf2);
      color: var(--text);
      border: 1px solid var(--border);
    }
    .btn-secondary:hover:not(:disabled) { background: #252a3e; }
    /* ---- status badge ---- */
    #statusBadge {
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      padding: 0.25rem 0.7rem;
      border-radius: 999px;
      font-size: 0.8rem;
      font-weight: 600;
      background: var(--surf2);
      color: var(--dim);
      border: 1px solid var(--border);
      user-select: none;
    }
    #statusBadge.running {
      background: rgba(99,102,241,0.15);
      color: #a5b4fc;
      border-color: rgba(99,102,241,0.35);
    }
    #statusBadge.success {
      background: rgba(34,197,94,0.12);
      color: var(--ok);
      border-color: rgba(34,197,94,0.3);
    }
    #statusBadge.error {
      background: rgba(239,68,68,0.12);
      color: var(--err);
      border-color: rgba(239,68,68,0.3);
    }
    .dot {
      width: 7px; height: 7px;
      border-radius: 50%;
      background: currentColor;
      flex-shrink: 0;
    }
    /* ---- terminal ---- */
    .term-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 0.75rem;
    }
    .term-header h2 { border: none; padding: 0; margin: 0; }
    #terminal {
      font-family: 'Consolas', 'Cascadia Code', 'Courier New', monospace;
      font-size: 0.82rem;
      line-height: 1.55;
      background: #080a11;
      color: #c8d3f5;
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 1rem;
      min-height: 160px;
      max-height: 420px;
      overflow-y: auto;
      white-space: pre-wrap;
      word-break: break-word;
    }
    /* ---- toast ---- */
    #toasts {
      position: fixed;
      bottom: 1.5rem;
      right: 1.5rem;
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
      z-index: 9999;
      pointer-events: none;
    }
    .toast {
      padding: 0.65rem 1.1rem;
      border-radius: 8px;
      font-size: 0.87rem;
      font-weight: 500;
      pointer-events: auto;
      max-width: 320px;
      animation: tin 0.22s ease;
    }
    .toast.ok   { background:#14532d; color:#bbf7d0; border:1px solid #166534; }
    .toast.err  { background:#450a0a; color:#fecaca; border:1px solid #7f1d1d; }
    .toast.info { background:#1e1b4b; color:#c7d2fe; border:1px solid #3730a3; }
    @keyframes tin {
      from { opacity:0; transform:translateX(18px); }
      to   { opacity:1; transform:translateX(0); }
    }
    @media (max-width: 600px) {
      .btn-row { flex-direction: column; }
      button { width: 100%; }
    }
  </style>
</head>
<body>
"""

_HTML_TAIL: str = """\
<div id="app">
  <header>
    <h1>&#x1F43E; Codecat Web UI</h1>
    <p>Configure and run Codecat from your browser.</p>
    <div class="path-pill" id="pathDisplay"></div>
  </header>

  <div class="card">
    <h2>&#x2699;&#xFE0F; Configuration</h2>

    <div class="form-row">
      <label for="outputFile">Output file name</label>
      <input type="text" id="outputFile" placeholder="codecat_output.md">
    </div>

    <div class="form-row">
      <label for="includePatterns">Include patterns</label>
      <textarea id="includePatterns"
        placeholder="*.py, *.js&#10;One pattern per line or comma-separated"
      ></textarea>
    </div>

    <div class="form-row">
      <label for="excludePatterns">Exclude patterns</label>
      <textarea id="excludePatterns"
        placeholder="*.pyc, *.log&#10;One pattern per line or comma-separated"
      ></textarea>
    </div>

    <div class="check-row">
      <input type="checkbox" id="noHeader">
      <label for="noHeader">
        No header &mdash; omit the generated Codecat header block
      </label>
    </div>

    <div class="check-row">
      <input type="checkbox" id="dryRun">
      <label for="dryRun">
        Dry run &mdash; scan and process but do not write the output file
      </label>
    </div>

    <div class="btn-row">
      <button class="btn-primary"    id="runBtn"      onclick="runCodecat()">
        &#x25B6; Run Codecat
      </button>
      <button class="btn-secondary"  id="loadBtn"     onclick="loadConfig()">
        &#x2193; Load Config
      </button>
      <button class="btn-secondary"  id="saveBtn"     onclick="saveConfig()">
        &#x2191; Save Config
      </button>
    </div>
  </div>

  <div class="card">
    <div class="term-header">
      <h2>&#x1F4DF; Output</h2>
      <span id="statusBadge"><span class="dot"></span>Idle</span>
    </div>
    <div id="terminal">Waiting for run\u2026</div>
  </div>
</div>

<div id="toasts"></div>

<script>

// Bootstrap

const PROJECT_PATH = window.CODECAT_PATH || '.';
let isRunning = false;

document.getElementById('pathDisplay').textContent = PROJECT_PATH;

// Load config on startup.

(async function init() { await loadConfig(true); })();

// Utilities

function parsePatterns(raw) {
  return raw.split(/[,\\n]+/)
    .map(function(s) { return s.trim(); })
    .filter(function(s) { return s.length > 0; });
}

function patternsToText(arr) {
  if (!Array.isArray(arr)) return '';
  return arr.join('\\n');
}

function setStatus(cls, text) {
  const b = document.getElementById('statusBadge');
  b.className = cls;
  b.innerHTML = '<span class="dot"></span>' + text;
}

function toast(msg, type) {
  const el = document.createElement('div');
  el.className = 'toast ' + (type || 'info');
  el.textContent = msg;
  document.getElementById('toasts').appendChild(el);
  setTimeout(function() { el.remove(); }, 3500);
}

function termAppend(text) {
  const t = document.getElementById('terminal');
  t.textContent += text;
  t.scrollTop = t.scrollHeight;
}

function termClear() {
  const t = document.getElementById('terminal');
  t.textContent = '';
  t.scrollTop = 0;
}

// Load Config

async function loadConfig(silent) {
  try {
    const res  = await fetch('/api/config');
    const data = await res.json();
    if (!data.success) {
      if (!silent) toast('No config file found', 'info');
      return;
    }
    const d = data.data;
    if (d.output_file != null) {
      document.getElementById('outputFile').value = d.output_file;
    }
    if (d.include_patterns != null) {
      document.getElementById('includePatterns').value =
        patternsToText(d.include_patterns);
    }
    if (d.exclude_patterns != null) {
      document.getElementById('excludePatterns').value =
        patternsToText(d.exclude_patterns);
    }
    if (d.generate_header != null) {
      document.getElementById('noHeader').checked = !d.generate_header;
    } else if (d.no_header != null) {
      document.getElementById('noHeader').checked = !!d.no_header;
    }
    if (!silent) toast('Config loaded', 'ok');
  } catch (err) {
    if (!silent) toast('Load error: ' + err.message, 'err');
  }
}

// Save Config

async function saveConfig() {
  const body = {
    outputFile: document.getElementById('outputFile').value.trim(),
    includes:   parsePatterns(document.getElementById('includePatterns').value),
    excludes:   parsePatterns(document.getElementById('excludePatterns').value),
    noHeader:   document.getElementById('noHeader').checked,
  };
  try {
    const res  = await fetch('/api/config', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(body),
    });
    const data = await res.json();
    if (data.success) {
      toast('Config saved', 'ok');
    } else {
      toast('Save failed: ' + data.error, 'err');
    }
  } catch (err) {
    toast('Save error: ' + err.message, 'err');
  }
}

// Run Codecat

async function runCodecat() {
  if (isRunning) return;
  isRunning = true;
  document.getElementById('runBtn').disabled = true;
  setStatus('running', 'Running\u2026');
  termClear();

  const body = {
    outputFile: document.getElementById('outputFile').value.trim(),
    includes:   parsePatterns(document.getElementById('includePatterns').value),
    excludes:   parsePatterns(document.getElementById('excludePatterns').value),
    noHeader:   document.getElementById('noHeader').checked,
    dryRun:     document.getElementById('dryRun').checked,
  };

  let succeeded = true;
  try {
    const res = await fetch('/api/run', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(body),
    });
    if (!res.body) throw new Error('No response body');

    const reader  = res.body.getReader();
    const decoder = new TextDecoder('utf-8');

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value, { stream: true });
      termAppend(chunk);
      if (/\\[ERROR\\]|Error:|error:/.test(chunk)) succeeded = false;
    }
  } catch (err) {
    termAppend('\\n[UI ERROR] ' + err.message + '\\n');
    succeeded = false;
  } finally {
    isRunning = false;
    document.getElementById('runBtn').disabled = false;
    setStatus(succeeded ? 'success' : 'error',
              succeeded ? 'Done'    : 'Finished with errors');
  }
}
</script>
</body>
</html>
"""


def _build_page(project_path: Path) -> bytes:
    """
    Assemble the full HTML page, injecting *project_path* as a safe
    JSON-encoded ``<script>`` block immediately after ``<head>``.

    Using ``json.dumps`` guarantees that backslashes, quotes, and
    every other special character in the path are correctly escaped.
    """
    path_json = json.dumps(str(project_path))
    inject = f"<script>window.CODECAT_PATH = {path_json};</script>\n"
    return (_HTML_HEAD + inject + _HTML_TAIL).encode("utf-8")


def _normalize_patterns(raw: list[Any]) -> list[str]:
    """
    Normalise a heterogeneous list of raw pattern values into a flat
    list of clean, non-empty strings.

    Each element is stringified, then split on commas and newlines.
    Whitespace is stripped and empty entries are dropped.

    This single implementation is shared by both POST handlers so that
    the normalisation logic never drifts out of sync.
    """
    result: list[str] = []
    for item in raw:
        for part in str(item).replace(",", "\n").split("\n"):
            cleaned = part.strip()
            if cleaned:
                result.append(cleaned)
    return result


# ---------------------------------------------------------------------------
# Module-level constant
# ---------------------------------------------------------------------------

_MAX_POST_BYTES: int = 64 * 1024  # 64 KB hard limit per request

# ---------------------------------------------------------------------------
# Handler helpers
#
# Every function that handles HTTP I/O accepts a plain
# ``http.server.BaseHTTPRequestHandler`` instance as its first argument.
# ---------------------------------------------------------------------------

_Handler = http.server.BaseHTTPRequestHandler  # local alias for type hints


def _send_head(
    h: _Handler,
    status: int,
    content_type: str,
    extra: dict[str, str] | None = None,
) -> None:
    """Send status line and common headers.  Always adds ``Connection: close``."""
    h.send_response(status)
    h.send_header("Content-Type", content_type)
    h.send_header("Connection", "close")
    if extra:
        for key, val in extra.items():
            h.send_header(key, val)
    h.end_headers()


def _send_json(
    h: _Handler,
    payload: dict[str, Any],
    status: int = 200,
) -> None:
    """Serialise *payload* as JSON and write it to the response."""
    body = json.dumps(payload).encode("utf-8")
    _send_head(
        h,
        status,
        "application/json; charset=utf-8",
        {"Content-Length": str(len(body))},
    )
    h.wfile.write(body)


def _read_post_body(h: _Handler) -> bytes | None:
    """
    Read the POST body up to ``_MAX_POST_BYTES``.

    Sends a 400 and returns ``None`` if the body is too large, allowing
    callers to return immediately without further processing.
    """
    try:
        length = int(h.headers.get("Content-Length", 0))
    except ValueError:
        length = 0
    if length > _MAX_POST_BYTES:
        _send_json(
            h,
            {"success": False, "error": "Request body exceeds 64 KB limit."},
            400,
        )
        return None
    return h.rfile.read(length)


def _handle_get(h: _Handler, project_path: Path) -> None:
    """Route GET requests to the appropriate sub-handler."""
    clean = h.path.split("?")[0]
    match clean:
        case "/" | "/index.html":
            page = _build_page(project_path)
            _send_head(
                h,
                200,
                "text/html; charset=utf-8",
                {"Content-Length": str(len(page))},
            )
            h.wfile.write(page)
        case "/api/config":
            _handle_get_config(h, project_path)
        case _:
            body = b"Not Found"
            _send_head(
                h,
                404,
                "text/plain; charset=utf-8",
                {"Content-Length": str(len(body))},
            )
            h.wfile.write(body)


def _handle_get_config(h: _Handler, project_path: Path) -> None:
    """Return the contents of ``.codecat_config.json`` as JSON."""
    config_file = project_path / ".codecat_config.json"
    if not config_file.is_file():
        _send_json(h, {"success": False, "error": "Config file not found."})
        return
    try:
        data = json.loads(config_file.read_text(encoding="utf-8"))
        _send_json(h, {"success": True, "data": data})
    except (json.JSONDecodeError, OSError) as exc:
        _send_json(h, {"success": False, "error": str(exc)})


def _handle_post(h: _Handler, project_path: Path) -> None:
    """Route POST requests to the appropriate sub-handler."""
    clean = h.path.split("?")[0]
    match clean:
        case "/api/config":
            _handle_post_config(h, project_path)
        case "/api/run":
            _handle_post_run(h, project_path)
        case _:
            body = b"Not Found"
            _send_head(
                h,
                404,
                "text/plain; charset=utf-8",
                {"Content-Length": str(len(body))},
            )
            h.wfile.write(body)


def _build_run_config(data: dict[str, Any]) -> dict[str, Any]:
    """
    Translate the frontend payload into a Codecat config dictionary.

    Extracted so that ``_handle_post_config`` and ``_handle_post_run``
    share the same mapping logic without duplicating it.
    """
    cfg: dict[str, Any] = {}

    output_file = str(data.get("outputFile", "")).strip()
    if output_file:
        cfg["output_file"] = output_file

    includes = _normalize_patterns(data.get("includes", []))
    excludes = _normalize_patterns(data.get("excludes", []))
    if includes:
        cfg["include_patterns"] = includes
    if excludes:
        cfg["exclude_patterns"] = excludes

    no_header = data.get("noHeader")
    if no_header is not None:
        cfg["generate_header"] = not bool(no_header)

    return cfg


def _handle_post_config(h: _Handler, project_path: Path) -> None:
    """Write frontend config payload to ``.codecat_config.json``."""
    raw = _read_post_body(h)
    if raw is None:
        return

    try:
        data: dict[str, Any] = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        _send_json(h, {"success": False, "error": f"Invalid JSON: {exc}"}, 400)
        return

    config = _build_run_config(data)
    try:
        config_path = project_path / ".codecat_config.json"
        config_path.write_text(json.dumps(config, indent=4), encoding="utf-8")
        _send_json(h, {"success": True})
    except OSError as exc:
        _send_json(h, {"success": False, "error": str(exc)})


def _build_subprocess_cmd(
    project_path: Path, tmp_config_path: Path, dry_run: bool
) -> list[str]:
    """
    Build the ``codecat run`` command list.

    Patterns are passed via a temp config file (``--config``) rather than
    as individual ``--include``/``--exclude`` arguments.
    """
    cmd = [
        sys.executable,
        "-m",
        "codecat",
        "run",
        str(project_path),
        "--config",
        str(tmp_config_path),
    ]
    if dry_run:
        cmd.append("--dry-run")
    return cmd


def _stream_subprocess(
    h: _Handler, cmd: list[str], project_path: Path
) -> None:  # pragma: no cover
    """
    Spawn *cmd* and stream its combined stdout/stderr to the response body.

    Handles ``BrokenPipeError`` / ``ConnectionResetError`` gracefully so
    that closing the browser tab mid-run does not produce a traceback.
    """
    env: dict[str, str] = {
        **os.environ,
        "NO_COLOR": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUNBUFFERED": "1",
    }
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            cwd=str(project_path),
            bufsize=1,
            shell=False,
        )
        if proc.stdout is not None:
            while True:
                line = proc.stdout.readline()
                if not line:
                    break
                try:
                    h.wfile.write(line.encode("utf-8"))
                    h.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    break  # user closed the browser tab mid-run
            proc.stdout.close()
        proc.wait()
    except Exception as exc:
        try:
            h.wfile.write(
                f"\n[SERVER ERROR] Could not run Codecat: {exc}\n".encode("utf-8")
            )
        except (BrokenPipeError, ConnectionResetError):  # pragma: no cover
            pass


def _handle_post_run(h: _Handler, project_path: Path) -> None:
    """Execute ``codecat run`` and stream its output back to the client."""
    import tempfile

    if not project_path.is_dir():
        _send_head(h, 400, "text/plain; charset=utf-8")
        h.wfile.write(
            f"Error: project path is not a valid directory: {project_path}\n".encode(
                "utf-8"
            )
        )
        return

    raw = _read_post_body(h)
    if raw is None:
        return

    try:
        data: dict[str, Any] = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        _send_head(h, 400, "text/plain; charset=utf-8")
        h.wfile.write(f"Error: invalid JSON body: {exc}\n".encode("utf-8"))
        return

    temp_cfg = _build_run_config(data)

    tmp_fd, tmp_path_str = tempfile.mkstemp(
        suffix=".json",
        prefix=".codecat_run_",
        dir=project_path,
    )
    tmp_config_path = Path(tmp_path_str)
    try:
        os.write(tmp_fd, json.dumps(temp_cfg).encode("utf-8"))
    finally:
        os.close(tmp_fd)

    cmd = _build_subprocess_cmd(project_path, tmp_config_path, bool(data.get("dryRun")))

    _send_head(h, 200, "text/plain; charset=utf-8", {"Cache-Control": "no-cache"})

    try:
        _stream_subprocess(h, cmd, project_path)  # pragma: no cover
    finally:
        try:
            tmp_config_path.unlink(missing_ok=True)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Request handler factory
# ---------------------------------------------------------------------------


def _make_handler(
    project_path: Path,
) -> type[http.server.BaseHTTPRequestHandler]:
    """
    Return a ``BaseHTTPRequestHandler`` subclass bound to *project_path*.

    All logic lives in the module-level ``_handle_*`` functions; this class
    is intentionally a thin delegation layer.  Using a factory keeps
    ``project_path`` out of shared class state so concurrent requests from
    different server instances cannot interfere with each other.
    """

    class _RequestHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            _handle_get(self, project_path)

        def do_POST(self) -> None:
            _handle_post(self, project_path)

        def log_message(self, fmt: str, *args: Any) -> None:
            pass  # suppress per-request log lines

    return _RequestHandler


# ---------------------------------------------------------------------------
# Port discovery
# ---------------------------------------------------------------------------


def _find_free_port(start: int, max_tries: int = 20) -> int:
    """
    Return the first TCP port in ``[start, start + max_tries)`` that is
    available on the loopback interface.

    Raises ``OSError`` if no free port is found within the range.
    """
    for candidate in range(start, start + max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", candidate))
                return candidate
            except OSError:
                continue
    raise OSError(
        f"Could not find a free port in range" f" {start}\u2013{start + max_tries - 1}."
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


class _ReuseAddrServer(socketserver.ThreadingTCPServer):
    """ThreadingTCPServer with address reuse enabled and daemon threads."""

    allow_reuse_address: bool = True
    daemon_threads: bool = True


def start_web_app(
    port: int = 8080, project_path: Path = Path(".")
) -> None:  # pragma: no cover
    """
    Start the Codecat web UI server and open it in the default browser.

    The server binds to ``127.0.0.1`` only and is never exposed to the
    network.  The function blocks until the user presses Ctrl+C.
    """
    resolved = project_path.resolve()
    actual_port = _find_free_port(port)

    server = _ReuseAddrServer(
        ("127.0.0.1", actual_port),
        _make_handler(resolved),
    )

    url = f"http://127.0.0.1:{actual_port}"
    print(f"Codecat Web UI  \u2192  {url}")
    print(f"Target directory:  {resolved}")
    print("Press Ctrl+C to stop.\n")

    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    webbrowser.open_new(url)

    try:
        while True:
            server_thread.join(1)
    except KeyboardInterrupt:
        print("\nShutting down\u2026")
        server.shutdown()
        server.server_close()
        sys.exit(0)
