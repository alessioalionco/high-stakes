"""Minimal HTTP client on top of the stdlib — D8: zero external dependencies.

Reimplements the slice of `requests` that the engine uses (Session.get/post, Response
with status_code/text/json/headers/iter_lines/close, RequestException) on top of
`urllib.request`. The interface is deliberately identical to `requests`': the
`ORClient(session=...)` injection point keeps working, and the retry body does not change.

Deliberate decisions:
- **non-2xx comes back as a Response, not as an exception.** urllib raises HTTPError; the
  retry needs to READ status_code and Retry-After to decide. Without that, a 429 would
  become a terminal error.
- **explicit `Accept-Encoding: identity`.** urllib does not decompress on its own; without
  the header, a provider that decided to gzip would hand unreadable bytes to the SSE parser.
- **no connection pooling.** Irrelevant at ~30 calls per run, and it makes the Session
  stateless — hence thread-safe by construction (dispatch is parallel).
"""
from __future__ import annotations

import json as _json
import ssl
import time
import urllib.error
import urllib.request

__all__ = ["DeadlineExceeded", "RequestException", "Response", "Session"]

# Read ceilings. An unbounded remote body is trivial DoS: a response with no newline
# made `readline()` buffer the entire stream (measured: 27 MB -> 294 MB of RSS), and
# dispatch runs 6-8 of these in parallel.
MAX_BODY_BYTES = 32 * 1024 * 1024
MAX_LINE_BYTES = 4 * 1024 * 1024


class RequestException(Exception):
    """Transport failure: DNS, connection refused, timeout. Transient -> retry."""


class DeadlineExceeded(Exception):
    """WALL-CLOCK deadline blown. Deliberately does NOT inherit from RequestException:
    the retry treats transport as transient, and retrying a blown deadline multiplied
    the wait by the number of attempts (4 × 1200s = 80 min) burning paid generations."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Follows NO redirect whatsoever.

    urllib's default handler re-sends ALL headers to the 3xx destination, including
    `Authorization: Bearer <key>` — and the destination can be another host. `requests`,
    which this module replaces, strips auth cross-host in `Session.rebuild_auth`;
    reimplementing without that guard leaked the API key to whoever controlled the
    redirect.

    The endpoints used here do not legitimately redirect, so the safe answer is not to
    follow: returning None makes urllib raise HTTPError, which becomes a 3xx Response —
    and the retry classifies it as a terminal error, which is what an unexpected 3xx is.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _build_opener() -> urllib.request.OpenerDirector:
    """Our OWN opener, not the global one.

    `urllib.request.urlopen` uses a process-wide opener that any code can swap with
    `install_opener()`. The money path cannot depend on that.
    """
    return urllib.request.build_opener(
        _NoRedirect(),
        urllib.request.HTTPSHandler(context=ssl.create_default_context()),
    )


class Response:
    """Lazy response: the body is only read when someone asks for it (.text/.iter_lines)."""

    def __init__(self, raw, status_code: int, headers, url: str, deadline: float | None = None):
        self._raw = raw
        self.status_code = status_code
        self.headers = headers
        self.url = url
        self._text: str | None = None
        # WALL-CLOCK deadline. The socket timeout is per-operation: a server that sends
        # a keep-alive every 2s holds the worker forever without ever blowing the
        # timeout.
        self._deadline = deadline

    def _check_deadline(self) -> None:
        if self._deadline is not None and time.monotonic() > self._deadline:
            self.close()
            raise DeadlineExceeded(
                f"wall-clock deadline blown while reading {self.url} — the socket was "
                "still alive, but the response did not complete in time")

    @property
    def text(self) -> str:
        if self._text is None:
            self._check_deadline()  # the retry reads .text on every 429/5xx/4xx
            try:
                body = self._raw.read(MAX_BODY_BYTES)
            except Exception:  # body already consumed/dead socket -> empty text, not a crash
                body = b""
            self._text = body.decode("utf-8", "replace")
        return self._text

    def json(self):
        return _json.loads(self.text)

    def raise_for_status(self) -> None:
        if not 200 <= self.status_code < 300:
            raise RequestException(
                f"HTTP {self.status_code} at {self.url}: {self.text[:300]}")

    def iter_lines(self):
        """Body lines without the terminator — same contract as requests.iter_lines().

        With a per-line ceiling and a wall-clock deadline: the two ways a misbehaving
        upstream can hold the process forever after the money has already been spent.
        """
        try:
            while True:
                self._check_deadline()
                line = self._raw.readline(MAX_LINE_BYTES)
                if not line:
                    break
                if len(line) >= MAX_LINE_BYTES and not line.endswith(b"\n"):
                    raise RequestException(
                        f"line longer than {MAX_LINE_BYTES} bytes with no terminator at "
                        f"{self.url} — body treated as malformed")
                yield line.rstrip(b"\r\n")
        finally:
            self.close()

    def close(self) -> None:
        try:
            self._raw.close()
        except Exception:
            pass


class Session:
    """Stateless by design (see the module docstring). `stream=` is accepted and
    ignored: urllib is already streaming — the body only leaves the socket when read."""

    def get(self, url: str, headers: dict | None = None, timeout: float | None = None,
            **_ignored) -> Response:
        return self._open("GET", url, headers=headers, timeout=timeout)

    def post(self, url: str, headers: dict | None = None, json: dict | None = None,
             timeout: float | None = None, **_ignored) -> Response:
        h = dict(headers or {})
        body = None
        if json is not None:
            body = _json.dumps(json).encode("utf-8")
            h.setdefault("Content-Type", "application/json")
        return self._open("POST", url, headers=h, timeout=timeout, body=body)

    _opener = None  # created on demand; one per process, ours, not the global one

    @classmethod
    def _get_opener(cls) -> urllib.request.OpenerDirector:
        if cls._opener is None:
            cls._opener = _build_opener()
        return cls._opener

    @classmethod
    def _open(cls, method: str, url: str, headers: dict | None = None,
              timeout: float | None = None, body: bytes | None = None) -> Response:
        h = dict(headers or {})
        h.setdefault("Accept-Encoding", "identity")
        req = urllib.request.Request(url, data=body, headers=h, method=method)
        deadline = (time.monotonic() + timeout) if timeout else None
        try:
            raw = cls._get_opener().open(req, timeout=timeout)
        except urllib.error.HTTPError as exc:
            # non-2xx: the retry needs the status and the Retry-After -> return a
            # Response. 3xx lands here because _NoRedirect refuses to follow (see its
            # docstring).
            return Response(exc, exc.code, exc.headers, url, deadline)
        except urllib.error.URLError as exc:
            raise RequestException(str(exc.reason)) from exc
        except OSError as exc:  # socket.timeout and friends (URLError already filtered above)
            raise RequestException(str(exc)) from exc
        return Response(raw, raw.status, raw.headers, url, deadline)
