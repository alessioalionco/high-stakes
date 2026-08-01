"""Cliente HTTP mínimo sobre a stdlib — D8: zero dependência externa.

Reimplementa a fatia de `requests` que o motor usa (Session.get/post, Response com
status_code/text/json/headers/iter_lines/close, RequestException) sobre `urllib.request`.
A interface é deliberadamente idêntica à do `requests`: o ponto de injeção
`ORClient(session=...)` continua valendo, e o corpo do retry não muda.

Decisões conscientes:
- **não-2xx volta como Response, não como exceção.** urllib levanta HTTPError; o retry
  precisa LER status_code e Retry-After pra decidir. Sem isso, 429 viraria erro terminal.
- **`Accept-Encoding: identity` explícito.** urllib não descomprime sozinho; sem o header,
  um provider que resolvesse gzipar entregaria bytes ilegíveis ao parser de SSE.
- **sem connection pooling.** Irrelevante em ~30 chamadas por run, e torna a Session
  stateless — logo thread-safe por construção (o dispatch é paralelo).
"""
from __future__ import annotations

import json as _json
import urllib.error
import urllib.request

__all__ = ["RequestException", "Response", "Session"]


class RequestException(Exception):
    """Falha de transporte: DNS, conexão recusada, timeout. Transiente -> retry."""


class Response:
    """Resposta preguiçosa: o corpo só é lido quando alguém pede (.text/.iter_lines)."""

    def __init__(self, raw, status_code: int, headers, url: str):
        self._raw = raw
        self.status_code = status_code
        self.headers = headers
        self.url = url
        self._text: str | None = None

    @property
    def text(self) -> str:
        if self._text is None:
            try:
                body = self._raw.read()
            except Exception:  # corpo já consumido/socket morto -> texto vazio, não crash
                body = b""
            self._text = body.decode("utf-8", "replace")
        return self._text

    def json(self):
        return _json.loads(self.text)

    def raise_for_status(self) -> None:
        if not 200 <= self.status_code < 300:
            raise RequestException(
                f"HTTP {self.status_code} em {self.url}: {self.text[:300]}")

    def iter_lines(self):
        """Linhas do corpo sem o terminador — mesmo contrato do requests.iter_lines()."""
        while True:
            line = self._raw.readline()
            if not line:
                break
            yield line.rstrip(b"\r\n")

    def close(self) -> None:
        try:
            self._raw.close()
        except Exception:
            pass


class Session:
    """Stateless por desenho (ver docstring do módulo). `stream=` é aceito e ignorado:
    urllib já é streaming — o corpo só sai do socket quando lido."""

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

    @staticmethod
    def _open(method: str, url: str, headers: dict | None = None,
              timeout: float | None = None, body: bytes | None = None) -> Response:
        h = dict(headers or {})
        h.setdefault("Accept-Encoding", "identity")
        req = urllib.request.Request(url, data=body, headers=h, method=method)
        try:
            raw = urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as exc:
            # não-2xx: o retry precisa do status e do Retry-After -> devolve Response
            return Response(exc, exc.code, exc.headers, url)
        except urllib.error.URLError as exc:
            raise RequestException(str(exc.reason)) from exc
        except OSError as exc:  # socket.timeout e afins (URLError já filtrado acima)
            raise RequestException(str(exc)) from exc
        return Response(raw, raw.status, raw.headers, url)
