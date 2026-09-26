"""Bounded, quiet localhost receiver for explicit Desktop OAuth enrollment.

Importing this module performs no I/O. The injected browser opener is trusted:
its daemon thread may outlive a timeout if the OS opener hangs, but it cannot
retain the listening socket or receive the authorization result.
"""
from __future__ import annotations

import hmac
import math
import queue
import re
import secrets
import socket
import threading
import time
from urllib.parse import parse_qsl, urlsplit
import webbrowser

from .google_oauth import DesktopClient, authorization_url

_CALLBACK = "/oauth2/callback"
_MAX_ATTEMPTS = 32
_MAX_HEADER_BYTES = 16384
_REQUEST_SECONDS = 2.0
_POLL_SECONDS = 0.1


class LoopbackError(ValueError):
    """Only fixed public codes cross the enrollment boundary."""

    def __init__(self, code: str):
        allowed = {
            "loopback_invalid_timeout", "loopback_unavailable", "loopback_configuration",
            "loopback_browser_failed", "loopback_denied", "loopback_timeout",
            "loopback_invalid_attempts",
        }
        self.code = code if code in allowed else "loopback_unavailable"
        super().__init__(self.code)


def _read_request(peer: socket.socket, deadline: float) -> bytes | None:
    end = min(deadline, time.monotonic() + _REQUEST_SECONDS)
    data = bytearray()
    while len(data) < _MAX_HEADER_BYTES:
        remaining = end - time.monotonic()
        if remaining <= 0:
            return None
        peer.settimeout(remaining)
        try:
            block = peer.recv(min(4096, _MAX_HEADER_BYTES - len(data)))
        except (OSError, TimeoutError):
            return None
        if not block:
            return None
        data.extend(block)
        if b"\r\n\r\n" in data:
            return bytes(data)
    return None


def _callback_result(raw: bytes | None, host: str, state: str) -> tuple[str, str] | None:
    if raw is None:
        return None
    try:
        head, suffix = raw.split(b"\r\n\r\n", 1)
        if suffix:
            return None
        lines = head.decode("ascii").split("\r\n")
        method, target, version = lines[0].split(" ")
        if (method != "GET" or version != "HTTP/1.1" or "#" in target
                or any(ord(c) < 33 or ord(c) > 126 for c in target)):
            return None
        headers = {}
        for line in lines[1:]:
            key, value = line.split(":", 1)
            if not re.fullmatch(r"[A-Za-z0-9!#$%&'*+.^_`|~-]+", key):
                return None
            key = key.lower()
            if key in headers or any(ord(c) < 32 or ord(c) == 127 for c in value.strip()):
                return None
            headers[key] = value.strip()
        if (headers.get("host") != host or "transfer-encoding" in headers
                or headers.get("content-length", "0") != "0"):
            return None
        parts = urlsplit(target)
        if parts.scheme or parts.netloc or parts.path != _CALLBACK:
            return None
        if re.search(r"%(?![0-9a-fA-F]{2})", parts.query):
            return None
        pairs = parse_qsl(parts.query, keep_blank_values=True, strict_parsing=True,
                          encoding="utf-8", errors="strict", max_num_fields=16)
        params = dict(pairs)
        if len(params) != len(pairs):
            return None
        returned_state = params.get("state", "")
        if not hmac.compare_digest(returned_state.encode("utf-8"), state.encode("ascii")):
            return None
        # Google may append scope/authuser/prompt fields. They are not logged or
        # trusted for scopes; the token response is validated by the OAuth layer.
        if "error" in params:
            return ("denied", "") if params["error"] and "code" not in params else None
        code = params.get("code", "")
        if not code or len(code) > 4096 or any(ord(c) < 33 or ord(c) > 126 for c in code):
            return None
        return "code", code
    except (ValueError, UnicodeError):
        return None


def _respond(peer: socket.socket, accepted: bool, deadline: float) -> None:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return
    body = b"Authorization received. You may close this window." if accepted else b"Request not accepted."
    status = b"200 OK" if accepted else b"400 Bad Request"
    response = (b"HTTP/1.1 " + status + b"\r\nContent-Type: text/plain; charset=utf-8\r\n"
                b"Cache-Control: no-store\r\nReferrer-Policy: no-referrer\r\nConnection: close\r\n"
                b"Content-Length: " + str(len(body)).encode("ascii") + b"\r\n\r\n" + body)
    try:
        peer.settimeout(min(remaining, _POLL_SECONDS))
        peer.sendall(response)
    except OSError:
        pass


def get_authorization_code(
    client: DesktopClient, *, opener=None, timeout: float = 180,
) -> tuple[str, str, str]:
    """Return (code, exact redirect URI, PKCE verifier), without exchanging it.

    Invalid callbacks consume at most 32 attempts. Each accepted TCP connection
    has a two-second absolute header deadline, within the overall deadline.
    No callback values, browser URL, or raw exception text are emitted.
    """
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 600:
        raise LoopbackError("loopback_invalid_timeout")
    deadline = time.monotonic() + timeout
    state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(64)
    try:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    except OSError:
        raise LoopbackError("loopback_unavailable") from None
    with listener:
        try:
            listener.bind(("127.0.0.1", 0))
            listener.listen(8)
            host = f"127.0.0.1:{listener.getsockname()[1]}"
            redirect_uri = f"http://{host}{_CALLBACK}"
        except OSError:
            raise LoopbackError("loopback_unavailable") from None
        try:
            url = authorization_url(client, redirect_uri, state, verifier)
        except Exception:
            raise LoopbackError("loopback_configuration") from None
        if time.monotonic() >= deadline:
            raise LoopbackError("loopback_timeout")
        result: queue.SimpleQueue[bool] = queue.SimpleQueue()
        browser_open = opener if opener is not None else webbrowser.open

        def launch() -> None:
            try:
                opened = browser_open(url) if time.monotonic() < deadline else False
                result.put(opened is True)
            except Exception:
                result.put(False)

        try:
            threading.Thread(target=launch, daemon=True, name="c021-oauth-browser").start()
        except Exception:
            raise LoopbackError("loopback_browser_failed") from None
        attempts = 0
        while time.monotonic() < deadline:
            try:
                if not result.get_nowait():
                    raise LoopbackError("loopback_browser_failed")
            except queue.Empty:
                pass
            if attempts >= _MAX_ATTEMPTS:
                raise LoopbackError("loopback_invalid_attempts")
            listener.settimeout(min(_POLL_SECONDS, max(0.001, deadline - time.monotonic())))
            try:
                peer, address = listener.accept()
            except TimeoutError:
                continue
            except OSError:
                raise LoopbackError("loopback_unavailable") from None
            attempts += 1
            with peer:
                if address[0] != "127.0.0.1":
                    continue
                outcome = _callback_result(_read_request(peer, deadline), host, state)
                # Late data can never turn an expired enrollment into success.
                if time.monotonic() >= deadline:
                    break
                _respond(peer, outcome is not None and outcome[0] == "code", deadline)
                if outcome is not None:
                    if outcome[0] == "denied":
                        raise LoopbackError("loopback_denied")
                    return outcome[1], redirect_uri, verifier
        raise LoopbackError("loopback_timeout")
