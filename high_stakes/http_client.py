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
import ssl
import time
import urllib.error
import urllib.request

__all__ = ["DeadlineExceeded", "RequestException", "Response", "Session"]

# Tetos de leitura. Corpo remoto sem limite é DoS trivial: uma resposta sem newline
# fazia `readline()` bufferizar o stream inteiro (medido: 27 MB -> 294 MB de RSS), e o
# dispatch roda 6-8 dessas em paralelo.
MAX_BODY_BYTES = 32 * 1024 * 1024
MAX_LINE_BYTES = 4 * 1024 * 1024


class RequestException(Exception):
    """Falha de transporte: DNS, conexão recusada, timeout. Transiente -> retry."""


class DeadlineExceeded(Exception):
    """Prazo de PAREDE estourado. Deliberadamente NÃO herda de RequestException: o retry
    trata transporte como transiente, e retentar um prazo estourado multiplicava a espera
    pelo número de tentativas (4 × 1200s = 80 min) queimando gerações pagas."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Não segue redirect NENHUM.

    O handler padrão do urllib reenvia TODOS os headers ao destino do 3xx, inclusive
    `Authorization: Bearer <chave>` — e o destino pode ser outro host. O `requests`, que
    este módulo substitui, remove auth cross-host em `Session.rebuild_auth`; reimplementar
    sem essa trava vazava a chave de API para quem controlasse o redirect.

    Os endpoints usados aqui não redirecionam legitimamente, então a resposta segura é não
    seguir: devolver None faz o urllib levantar HTTPError, que vira uma Response 3xx — e o
    retry a classifica como erro terminal, que é o que um 3xx inesperado é.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _build_opener() -> urllib.request.OpenerDirector:
    """Opener PRÓPRIO, não o global.

    `urllib.request.urlopen` usa um opener de processo que qualquer código pode trocar com
    `install_opener()`. O caminho do dinheiro não pode depender disso.
    """
    return urllib.request.build_opener(
        _NoRedirect(),
        urllib.request.HTTPSHandler(context=ssl.create_default_context()),
    )


class Response:
    """Resposta preguiçosa: o corpo só é lido quando alguém pede (.text/.iter_lines)."""

    def __init__(self, raw, status_code: int, headers, url: str, deadline: float | None = None):
        self._raw = raw
        self.status_code = status_code
        self.headers = headers
        self.url = url
        self._text: str | None = None
        # Prazo de PAREDE. O timeout do socket é por-operação: um servidor que manda um
        # keep-alive a cada 2s segura o worker para sempre sem nunca estourar o timeout.
        self._deadline = deadline

    def _check_deadline(self) -> None:
        if self._deadline is not None and time.monotonic() > self._deadline:
            self.close()
            raise DeadlineExceeded(
                f"prazo de parede estourado lendo {self.url} — o socket seguia vivo, "
                "mas a resposta não completou a tempo")

    @property
    def text(self) -> str:
        if self._text is None:
            self._check_deadline()  # o retry lê .text em todo 429/5xx/4xx
            try:
                body = self._raw.read(MAX_BODY_BYTES)
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
        """Linhas do corpo sem o terminador — mesmo contrato do requests.iter_lines().

        Com teto por linha e prazo de parede: as duas formas de um upstream mal-comportado
        segurar o processo para sempre depois do dinheiro já gasto.
        """
        try:
            while True:
                self._check_deadline()
                line = self._raw.readline(MAX_LINE_BYTES)
                if not line:
                    break
                if len(line) >= MAX_LINE_BYTES and not line.endswith(b"\n"):
                    raise RequestException(
                        f"linha maior que {MAX_LINE_BYTES} bytes sem terminador em "
                        f"{self.url} — corpo tratado como malformado")
                yield line.rstrip(b"\r\n")
        finally:
            self.close()

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

    _opener = None  # criado sob demanda; um por processo, nosso, não o global

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
            # não-2xx: o retry precisa do status e do Retry-After -> devolve Response.
            # 3xx chega aqui porque _NoRedirect recusa seguir (ver docstring de lá).
            return Response(exc, exc.code, exc.headers, url, deadline)
        except urllib.error.URLError as exc:
            raise RequestException(str(exc.reason)) from exc
        except OSError as exc:  # socket.timeout e afins (URLError já filtrado acima)
            raise RequestException(str(exc)) from exc
        return Response(raw, raw.status, raw.headers, url, deadline)
