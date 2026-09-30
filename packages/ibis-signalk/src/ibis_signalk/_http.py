from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

# The History API can be slow on wide time windows
DEFAULT_TIMEOUT = 120.0


def get_json(url: str, params: dict[str, str] | None = None, timeout: float = DEFAULT_TIMEOUT) -> Any:
    """GET a URL and decode its JSON body.

    Uses the standard library rather than httpx, and in a marimo WASM
    notebook the browser itself, so it has no dependencies to install there.
    """
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    if "pyodide" in sys.modules:
        return _browser_get_json(url)
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _browser_get_json(url: str) -> Any:
    """Synchronous GET through the browser, for Pyodide.

    marimo patches urllib to work in the browser, but its responses keep the
    server's `Transfer-Encoding: chunked` header for a body the browser has
    already de-chunked, which makes http.client fail with IncompleteRead.
    A synchronous XMLHttpRequest (allowed in the Web Worker Pyodide runs in)
    avoids that, and sends the SignalK login cookie for same-origin requests.
    """
    from js import XMLHttpRequest  # type: ignore[import-not-found]

    xhr = XMLHttpRequest.new()
    xhr.open("GET", url, False)
    xhr.setRequestHeader("Accept", "application/json")
    xhr.send(None)
    if not 200 <= xhr.status < 300:
        # The server's own message (e.g. why a request was rejected) is in the body
        detail = xhr.responseText if isinstance(xhr.responseText, str) else ""
        raise urllib.error.HTTPError(url, xhr.status, detail[:300], None, None)
    return json.loads(xhr.responseText)
