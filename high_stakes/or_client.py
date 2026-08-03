"""
or_client.py — Shared OpenRouter client for the high-stakes engine.

ZERO external dependencies [D8]: stdlib only. HTTP transport comes from
`http_client.py` (urllib), with the `requests` interface preserved.

Responsibilities:
  - chat(model, messages, ...) -> dict with {text, usage, cost_usd, provider, raw}.
  - Cost via OpenRouter's `usage.cost` (captures sonar's internal search cost,
    which does NOT show up in the token-math). Fallback = catalog-snapshot pricing.
  - Budget cap reserve-then-reconcile [D1+D3]: pre-debits the ESTIMATED ceiling
    BEFORE dispatch; if reserved > cap -> raises BudgetExceeded before sending the
    request. After the response, reconciles reserved -> real cost. Holds across
    processes (in-flight reservations are persisted) and a run's cap only goes
    DOWN, never up.
    **Best-effort, not "hard"**: the estimate can underestimate the real cost, and
    what stops it is the reconcile — after the call has already been paid for.
  - Retry with backoff on 429/5xx, honors Retry-After.
  - catalog-snapshot on the 1st call (reproducibility).
  - Key read from .env (never hardcoded, never logged).

         budget ledger (thread-safe)
         ┌─────────────────────────────────────────────┐
   chat()│  reserve(est)  ──>  cap check  ──> dispatch   │
         │      │ (pre-debit)       │ raise       │      │
         │      │                   │ BudgetExc.  v      │
         │      └──── reconcile(est, real) <── response  │
         └─────────────────────────────────────────────┘
"""

from __future__ import annotations

import contextlib
import json
import math
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from .http_client import DeadlineExceeded, RequestException, Response, Session

try:  # POSIX (macOS/Linux). Without fcntl the lock degrades to a no-op — see _file_lock.
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None

OPENROUTER_BASE = "https://openrouter.ai/api/v1"
DEFAULT_CAP_USD = 15.0
DEFAULT_TIMEOUT = 300  # s; sonar-deep-research is slow. Per-call override.
MAX_RETRIES = 4

# Paths (lib-ready, 1A′-ii): ALL injectable by parameter — ledger_path
# (BudgetLedger), outputs_dir (ORClient), env_path (load_api_key). The WRITE
# default is CWD/outputs (this project's convention: `cd <experiment> && python3 run.py`
# -> ledger/catalog land IN the experiment). The engine NEVER writes inside itself.
_HERE = Path(__file__).resolve().parent
_ENV_PATH = _HERE.parent / ".env"  # install root (gitignored; read-only)


def _default_outputs() -> Path:
    return Path.cwd() / "outputs"


class BudgetExceeded(RuntimeError):
    """Raised BEFORE dispatch when the reservation would blow the cap."""


class LedgerCorrupted(RuntimeError):
    """Ledger exists and does not parse: spend unknown -> refuse dispatch (fail-closed)."""


class SchemaInvalid(ValueError):
    """The cell's JSON does not validate against the expected schema (terminal state)."""


def load_api_key(env_path: Path | None = None) -> str:
    """Reads OPENROUTER_API_KEY from the local .env (KEY=value). Never logs the value."""
    env_path = env_path or _ENV_PATH
    env_key = os.environ.get("OPENROUTER_API_KEY")
    if env_key:
        return env_key.strip()
    if not env_path.exists():
        raise RuntimeError(
            f"no OPENROUTER_API_KEY in the env nor in {env_path}. "
            "Pull the key from the VPS into .env (gitignored)."
        )
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line.startswith("OPENROUTER_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError(f"OPENROUTER_API_KEY not found in {env_path}")


_WARNED_NO_FLOCK = False

# The reservation of an IN-FLIGHT call must not expire. The worst case is MAX_RETRIES
# attempts of `timeout` each (4 × 1200s = 4800s at the config default), so a 1h TTL
# pruned a live reservation and erased the other process's — two processes reserved the
# same money.
RESERVATION_TTL_S = 4 * 1200 * 2  # 2h40: worst-case ceiling, with slack


@contextlib.contextmanager
def _file_lock(path: Path):
    """EXCLUSIVE cross-process lock on the file `path`.

    Without fcntl (non-POSIX) it degrades to a no-op: the cap goes back to holding
    only per-process. It is an explicit warning, not a silent failure — the engine
    runs on macOS/Linux.
    """
    if fcntl is None:  # pragma: no cover
        global _WARNED_NO_FLOCK
        if not _WARNED_NO_FLOCK:
            _WARNED_NO_FLOCK = True
            print("[ledger] WARNING: fcntl unavailable on this platform — the cap does "
                  "NOT hold across processes. Run one process at a time.")
        yield
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    f = open(path, "a+")
    try:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(f, fcntl.LOCK_UN)
        finally:
            f.close()


class BudgetLedger:
    """Spend ledger with pessimistic reservation (reserve-then-reconcile), safe across
    THREADS (in-memory lock) and across PROCESSES (flock + read-modify-write).

    The cap is PER RUN, not per process. Keeping only `self._spent` in memory and
    overwriting the file on flush made two processes in the same run read `spent=0`,
    each spend the entire cap, and the last write win — cap breached 2x, silently. That
    is why every mutation re-reads the disk under lock, and RESERVATIONS are persisted
    too: an in-flight call in process A must be visible to process B's cap check before
    dispatch.
    """

    def __init__(self, cap_usd: float = DEFAULT_CAP_USD, persist: bool = True,
                 ledger_path: Path | None = None):
        # NaN and inf got through: `nan > cap` is False, so a ledger created with a NaN
        # cap reserved a thousand dollars without an error. 0 and negative were blocked
        # by ACCIDENT (the projection ends up > cap), which is the right thing for the
        # wrong reason — and a silent cap of 0 looks like "no budget", not "broken
        # config".
        if not isinstance(cap_usd, (int, float)) or isinstance(cap_usd, bool) \
                or not math.isfinite(cap_usd) or cap_usd <= 0:
            raise ValueError(
                f"invalid cap_usd: {cap_usd!r}. Must be a finite number > 0 — the cap "
                "is the only thing between a loop bug and your bill.")
        self.cap_usd = cap_usd
        # THE CAP IS NOT RUN STATE — the SPEND is. This used to be `min(this instance's
        # cap, cap on disk)` and the idea was wrong at both ends: a low-cap instance
        # that was REFUSED never got to persist the lower ceiling (so the min protected
        # nothing), and when it did persist, the ledger got pinned to the lowest
        # ceiling that ever passed through it — a $0.50 typo blocked a legitimate $50
        # run FOREVER, and the only way out was deleting the ledger, which deletes the
        # spend history with it. The min protected the ledger's owner from himself, and
        # charged dearly for it.
        #
        # What the per-run ceiling must guarantee is that the SPEND accumulates across
        # processes, and the ledger handles that on its own: each instance stops at ITS
        # OWN ceiling against the accumulated total. Two processes with different
        # ceilings is an operator fact, not an attack.
        self._cap_effective = cap_usd
        self._reserved = 0.0
        self._spent = 0.0
        self._calls = 0
        self._lock = threading.Lock()
        self._persist = persist
        self._ledger_path = ledger_path or (_default_outputs() / "cost-ledger.json")
        self._lock_path = self._ledger_path.with_name(self._ledger_path.name + ".lock")
        # this instance's identity in the shared file (owner of its reservations)
        self._owner = f"{os.getpid()}-{uuid.uuid4().hex[:8]}"
        if self._persist and self._ledger_path.exists():
            with _file_lock(self._lock_path):
                d = self._read_disk()
                self._spent = d["spent_usd"]
                self._calls = d["calls"]
                self._cap_effective = self._effective_cap(d)

    # ---- disk (ALWAYS called under _file_lock) ----
    def _read_disk(self) -> dict:
        """{spent_usd, calls, reservations} from disk, sanitized. An unreadable ledger
        does not abort the run: it warns and treats it as zeroed (the cap keeps holding
        from there on)."""
        def _reject_non_finite(name):
            # `json.loads` accepts the NaN/Infinity literals by default. A ledger with
            # NaN does not "look" corrupted: it loads, and from then on EVERY cap
            # comparison becomes a no-op (`nan > cap` is False). Refusing at parse time
            # is the first of the two nets; the second is the isfinite on each number,
            # below.
            raise ValueError(f"non-finite literal in ledger: {name}")

        try:
            raw = json.loads(self._ledger_path.read_text(),
                             parse_constant=_reject_non_finite)
        except (json.JSONDecodeError, OSError) as e:
            if self._ledger_path.exists() and self._ledger_path.stat().st_size > 0:
                # FAIL CLOSED. Treating an unreadable ledger as "zero spend" gave the
                # whole cap back — exactly the opposite of what reserve-then-reconcile
                # exists to guarantee. A file that exists and does not parse is suspect
                # state, not initial state.
                raise LedgerCorrupted(
                    f"unreadable ledger at {self._ledger_path} ({type(e).__name__}: {e}). "
                    "The accumulated spend is unknown, so no dispatch is safe. "
                    "Inspect the file and, if the spend is acceptable, delete it "
                    "explicitly to start over from zero.") from e
            raw = {}  # absent or empty = new run, legitimate
        except ValueError as e:
            # ValueError here is the non-finite literal (or invalid JSON that escaped
            # the branch above). Zeroing would give the whole cap back -> fail-closed.
            if self._ledger_path.exists() and self._ledger_path.stat().st_size > 0:
                raise LedgerCorrupted(
                    f"ledger at {self._ledger_path} has a non-finite number or invalid "
                    f"JSON ({e}). Spend unknown: no dispatch is safe."
                ) from e
            raw = {}
        if not isinstance(raw, dict):
            raise LedgerCorrupted(
                f"ledger at {self._ledger_path} is not a JSON object "
                f"({type(raw).__name__}) — unreadable state, fail-closed.")
        # ABSENT is a new run; PRESENT-AND-ROTTEN is corruption. The fail-closed path
        # only covered unreadable JSON, and this came in through the other door:
        # `{"spent_usd": "a lot"}` and `{"spent_usd": null}` parse as JSON, fell into
        # the `except`/the `or 0.0`, silently became 0.0 — and gave back the WHOLE CAP.
        # It is the same fail-open that LedgerCorrupted exists to close. Zero by
        # absence is legitimate; zero by "could not read the number" never is.
        _MISSING = object()

        def _number(key, conv):
            v = raw.get(key, _MISSING)
            if v is _MISSING:
                return conv(0)  # never written yet: new run
            # bool is a subclass of int in Python: `True` would silently become 1.0.
            if (isinstance(v, bool) or not isinstance(v, (int, float))
                    or not math.isfinite(v)):
                raise LedgerCorrupted(
                    f"ledger at {self._ledger_path} has {key}={v!r} "
                    f"({type(v).__name__}) where a number should be. The accumulated "
                    "spend is unknown, so no dispatch is safe. Inspect the file "
                    "and, if the spend is acceptable, delete it explicitly.")
            return conv(v)

        # negative is a different story: pre-fix ledgers carry the catalog's -1/-1
        # sentinel. It is a number, it was read, and the conservative call is to treat
        # it as zero — not as corruption.
        spent = max(0.0, _number("spent_usd", float))
        calls_raw = _number("calls", float)
        if calls_raw != int(calls_raw):
            raise LedgerCorrupted(
                f"ledger at {self._ledger_path} has calls={calls_raw!r}, which is not\n"
                "an integer. This code never writes a fraction there: the file was "
                "tampered with.")
        calls = max(0, int(calls_raw))
        res, now = {}, time.time()
        reservations_raw = raw.get("reservations", _MISSING)
        if reservations_raw is _MISSING:
            reservations_raw = {}  # never written: new run
        elif reservations_raw is None:
            # `null` used to be converted to {} ON PURPOSE by me, and that is
            # fail-open: an in-flight reservation is what keeps two processes from
            # spending the same money. Erasing them gives everything back to the cap.
            raise LedgerCorrupted(
                f"ledger at {self._ledger_path} has reservations=null. Unreadable "
                "in-flight reservation = no dispatch (erasing it would give the budget "
                "back to the cap).")
        if not isinstance(reservations_raw, dict):
            raise LedgerCorrupted(
                f"ledger at {self._ledger_path} has reservations="
                f"{type(reservations_raw).__name__} where an object should be. Another "
                "process's in-flight reservation is what keeps two runs from spending "
                "the same money; unreadable = no dispatch.")
        for k, v in reservations_raw.items():
            # a MALFORMED entry is corruption (it vanishes from the math and LOOSENS
            # the cap); a well-formed but EXPIRED entry is an orphan of a dead process,
            # and that one gets discarded.
            if not isinstance(v, dict) or "usd" not in v or "ts" not in v:
                raise LedgerCorrupted(
                    f"ledger at {self._ledger_path}: reservation {k!r} malformed ({v!r}). "
                    "Silently discarding it would give its budget back to the cap.")
            for field in ("usd", "ts"):
                x = v[field]
                if isinstance(x, bool) or not isinstance(x, (int, float)):
                    raise LedgerCorrupted(
                        f"ledger at {self._ledger_path}: reservation {k!r} has {field}="
                        f"{x!r} ({type(x).__name__}) where a number should be. A "
                        "convertible string does not count: whoever wrote this was not "
                        "this code.")
            try:
                usd, ts = float(v["usd"]), float(v["ts"])
            except (TypeError, ValueError) as e:
                raise LedgerCorrupted(
                    f"ledger at {self._ledger_path}: reservation {k!r} with an "
                    f"unreadable number ({v!r}).") from e
            if not (math.isfinite(usd) and math.isfinite(ts)):
                raise LedgerCorrupted(
                    f"ledger at {self._ledger_path}: reservation {k!r} with a "
                    f"non-finite value ({v!r}). A NaN reservation vanishes from the sum "
                    "and gives the in-flight money back to the cap.")
            if usd > 0 and now - ts < RESERVATION_TTL_S:  # discards dead-process orphans
                res[k] = {"usd": usd, "ts": ts}
        try:
            disk_cap = float(raw.get("cap_usd")) if raw.get("cap_usd") is not None else None
        except (TypeError, ValueError):
            disk_cap = None
        return {"spent_usd": spent, "calls": calls, "reservations": res,
                "cap_usd": disk_cap}

    def _effective_cap(self, disk: dict) -> float:
        """The LOWER of this instance's cap and what is already in the ledger.

        The cap was written to the file and never read back: two processes with
        different caps in the same run got an effective cap = the HIGHER one. Whoever
        opened with $5 thought the ceiling was $5 while the other spent $50 on the same
        ledger."""
        dc = disk.get("cap_usd")
        if dc is None or not math.isfinite(dc) or dc <= 0:
            return self.cap_usd
        if dc != self.cap_usd:
            # A WARNING, not a rule. See the note in __init__: turning this into `min`
            # poisoned the ledger irreversibly.
            print(f"[ledger] note: this ledger was previously opened with cap ${dc:.2f} "
                  f"and this instance asked for ${self.cap_usd:.2f}. The accumulated "
                  "SPEND is shared; each instance stops at its own ceiling.")
        return self.cap_usd

    def _write_disk(self, spent: float, calls: int, reservations: dict,
                    cap: float | None = None) -> None:
        """Writes the run state. `cap` is the EFFECTIVE ceiling — never `self.cap_usd`.

        Writing the instance's cap was the bug: the run's floor GOES UP. Process A with
        cap $5 pins the run's ceiling at $5; process B with cap $50 comes in, honors
        the $5 for itself (the min), but writes $50 — and the next process C reads $50
        as if it were the run's ceiling. The cap becomes per-process again, which is
        exactly what the per-run ceiling exists to prevent. A run's floor can only go
        DOWN.
        """
        payload = json.dumps({
            "spent_usd": round(spent, 6),
            "calls": calls,
            "cap_usd": self._cap_effective if cap is None else cap,
            "reservations": reservations,
        }, indent=2)
        self._ledger_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._ledger_path.with_name(f"{self._ledger_path.name}.{self._owner}.tmp")
        tmp.write_text(payload)
        os.replace(tmp, self._ledger_path)  # atomic write

    def _commit(self, delta_spent: float, delta_calls: int) -> None:
        """Read-modify-write under lock: adds THIS process's delta to what is on disk
        and adopts the result as truth. Called with self._lock already held."""
        with _file_lock(self._lock_path):
            d = self._read_disk()
            self._cap_effective = self._effective_cap(d)  # the run's floor only goes down
            # round HERE, not only at serialization: memory and disk must be the same
            # number, otherwise the spend another process reads diverges from the local
            # one by ~1e-8.
            spent = round(d["spent_usd"] + delta_spent, 6)
            calls = d["calls"] + delta_calls
            res = d["reservations"]
            if self._reserved > 0:
                res[self._owner] = {"usd": round(self._reserved, 6), "ts": time.time()}
            else:
                res.pop(self._owner, None)
            self._write_disk(spent, calls, res)
            self._spent, self._calls = spent, calls

    def reserve(self, est_usd: float) -> None:
        """Pre-debits `est_usd`. Raises BudgetExceeded BEFORE dispatch on overrun.

        Persistent: the check consults the DISK — the run's accumulated spend PLUS the
        in-flight reservations of OTHER processes. That is what makes the cap hold per
        run, not per process.
        """
        with self._lock:
            if not self._persist:
                projected = self._reserved + self._spent + est_usd
                if projected > self._cap_effective:
                    # `cap` only exists in the persistent branch below. Swapping both
                    # occurrences at once made this path raise UnboundLocalError instead
                    # of BudgetExceeded — and 247 green tests did not catch it, because
                    # none exercised persist=False above the cap.
                    raise BudgetExceeded(
                        f"reserving ${est_usd:.4f} would blow the cap "
                        f"(spent ${self._spent:.4f} + reserved ${self._reserved:.4f} "
                        f"+ est = ${projected:.4f} > ${self._cap_effective:.2f})"
                    )
                self._reserved += est_usd
                return
            with _file_lock(self._lock_path):
                d = self._read_disk()
                others = sum(v["usd"] for k, v in d["reservations"].items()
                             if k != self._owner)
                self._spent, self._calls = d["spent_usd"], d["calls"]
                cap = self._effective_cap(d)
                self._cap_effective = cap
                projected = d["spent_usd"] + others + self._reserved + est_usd
                if projected > cap:
                    raise BudgetExceeded(
                        f"reserving ${est_usd:.4f} would blow the cap "
                        f"(spent ${d['spent_usd']:.4f} + reserved ${self._reserved:.4f} "
                        f"+ other processes ${others:.4f} "
                        f"+ est = ${projected:.4f} > ${cap:.2f})"
                    )
                self._reserved += est_usd
                d["reservations"][self._owner] = {
                    "usd": round(self._reserved, 6), "ts": time.time()}
                self._write_disk(d["spent_usd"], d["calls"], d["reservations"], cap)

    def reconcile(self, est_usd: float, real_usd: float) -> None:
        """Releases the reservation and books the real cost. If the accumulated REAL
        spend exceeds the cap, it RECORDS (flush) and raises BudgetExceeded — stopping
        the next dispatches (the reservation estimate can underestimate the real
        cost)."""
        # Same class as the catalog's -1/-1 sentinel: a negative REAL cost coming from
        # the provider would deflate the spend and inflate the cap. Never legitimate.
        if not math.isfinite(real_usd) or real_usd < 0:
            # Same family as the negative sentinel, and worse: `nan > cap` is False, so
            # a NaN cost does not deflate — it TURNS OFF the ceiling, and the spend
            # becomes NaN forever. Conservative in both cases: the reservation stands.
            real_usd = est_usd  # conservative: keeps the reservation as spend
        with self._lock:
            self._reserved = max(0.0, self._reserved - est_usd)
            if self._persist:
                self._commit(real_usd, 1)
            else:
                self._spent += real_usd
                self._calls += 1
            if self._spent > self._cap_effective:
                raise BudgetExceeded(
                    f"accumulated REAL cost ${self._spent:.4f} exceeded the cap "
                    f"${self._cap_effective:.2f} — stopping further dispatches"
                )

    def charge_extra(self, usd: float) -> None:
        """Books spend WITHOUT touching the reservation: earlier attempts of a retry
        that already ran at the provider. The retry re-dispatches up to MAX_RETRIES full
        generations, and the ledger booked ONE — an undercount of up to 4x, invisible
        to the cap."""
        if usd <= 0:
            return
        with self._lock:
            if self._persist:
                self._commit(usd, 0)
            else:
                self._spent += usd

    def charge_failure(self, est_usd: float, extra_usd: float = 0.0) -> None:
        """Call failed post-dispatch: books the ESTIMATE as spend
        (conservative — a dropped stream may have been billed). No cap-raise here
        (the original error propagates); the cap catches it at the next
        reserve/reconcile.

        `extra_usd` is the EARLIER generations that already ran at the provider. They
        go in HERE, in the same commit, and not in a separate `charge_extra` call: two
        writes were two lock windows, and between them the ledger on disk showed LOWER
        spend than the real one — another process read that number and reserved on top
        of it. Each write was atomic; what was not atomic was the MATH."""
        total = est_usd + max(0.0, extra_usd)
        with self._lock:
            self._reserved = max(0.0, self._reserved - est_usd)
            if self._persist:
                self._commit(total, 1)
            else:
                self._spent += total
                self._calls += 1

    def release(self, est_usd: float) -> None:
        """Releases the reservation without charging (the call was NEVER dispatched)."""
        with self._lock:
            self._reserved = max(0.0, self._reserved - est_usd)
            if self._persist:  # vanishes from disk: other processes recover the budget
                self._commit(0.0, 0)

    @property
    def spent(self) -> float:
        with self._lock:
            return self._spent

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "spent_usd": round(self._spent, 6),
                "reserved_usd": round(self._reserved, 6),
                "calls": self._calls,
                "cap_usd": self._cap_effective,
                "cap_requested_usd": self.cap_usd,
            }


class ORClient:
    """OpenRouter client with cap, retry, and cost computed via usage.cost."""

    def __init__(
        self,
        ledger: BudgetLedger | None = None,
        cap_usd: float = DEFAULT_CAP_USD,
        api_key: str | None = None,
        session: Session | None = None,
        outputs_dir: Path | None = None,
    ):
        self._outputs = outputs_dir or _default_outputs()
        self.ledger = ledger or BudgetLedger(
            cap_usd=cap_usd, ledger_path=self._outputs / "cost-ledger.json")
        self._api_key = api_key or load_api_key()
        self._session = session or Session()
        self._catalog: dict[str, dict] | None = None
        self._catalog_lock = threading.Lock()  # thread-safe check-then-set

    # ---- catalog (pricing fallback + snapshot for reproducibility) ----
    def catalog(self) -> dict[str, dict]:
        with self._catalog_lock:
            if self._catalog is not None:
                return self._catalog
            resp = self._session.get(f"{OPENROUTER_BASE}/models", timeout=30)
            resp.raise_for_status()
            data = resp.json().get("data", [])
            self._catalog = {m["id"]: m for m in data}
            self._outputs.mkdir(parents=True, exist_ok=True)
            (self._outputs / "catalog-snapshot.json").write_text(
                json.dumps(
                    {
                        mid: {
                            "pricing": m.get("pricing", {}),
                            "context_length": m.get("context_length"),
                            "created": m.get("created"),
                        }
                        for mid, m in self._catalog.items()
                    },
                    indent=2,
                )
            )
            return self._catalog

    def _price(self, model: str) -> tuple[float, float]:
        """(in_$/tok, out_$/tok) from the catalog. (0,0) if unknown."""
        m = self.catalog().get(model, {})
        p = m.get("pricing", {})
        return float(p.get("prompt", 0) or 0), float(p.get("completion", 0) or 0)

    def _estimate(self, model: str, messages: list[dict], max_tokens: int) -> float:
        """Pessimistic cost ceiling for the reservation: prompt_tokens*in + max_tokens*out.

        FAIL-CLOSED: a model without pricing in the catalog -> raise (refuse dispatch).
        An arbitrary floor ($0.01) would underestimate expensive models and breach the
        cap.
        """
        m = self.catalog().get(model)
        pricing = (m or {}).get("pricing") or {}
        if m is None or ("prompt" not in pricing and "completion" not in pricing):
            raise RuntimeError(
                f"model {model!r} has no pricing in the OpenRouter catalog — "
                "refusing dispatch (fail-closed; without an estimate there is no cap)."
            )
        in_price, out_price = self._price(model)
        if not (math.isfinite(in_price) and math.isfinite(out_price)):
            # The catalog comes from the provider. "nan"/"Infinity" become float
            # without complaint, and then the whole estimate is non-finite: the
            # reservation passes (nan > cap is False) and the cap stops existing for
            # that call.
            raise RuntimeError(
                f"model {model!r} has non-finite pricing in the catalog "
                f"(prompt={in_price}, completion={out_price}) — refusing dispatch.")
        if in_price < 0 or out_price < 0:
            # Catalog sentinel (e.g. openrouter/fusion publishes -1/-1): a negative
            # estimate becomes a negative reservation -> the cap stops existing and
            # charge_failure writes negative spend (failure mode already observed).
            # Zero price is legitimate (:free models); negative never is.
            raise RuntimeError(
                f"model {model!r} has sentinel/negative pricing in the catalog "
                f"(prompt={in_price}, completion={out_price}) — refusing dispatch "
                "(fail-closed; a negative estimate would turn off the cap)."
            )
        # ~4 chars/token (rough estimate, conservative-high on out via max_tokens).
        prompt_chars = sum(len(str(msg.get("content", ""))) for msg in messages)
        prompt_tokens = prompt_chars / 4
        return prompt_tokens * in_price + max_tokens * out_price

    # ---- the call ----
    def chat(
        self,
        model: str,
        messages: list[dict],
        *,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        response_format: dict | None = None,
        extra_body: dict | None = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> dict[str, Any]:
        """One completion. Returns {text, usage, cost_usd, provider, raw}.

        Reserve-then-reconcile cap: reserves the estimated ceiling BEFORE sending.
        """
        # extra_body is applied AFTER the estimate, so a key that changes WHAT gets
        # dispatched makes the engine reserve the price of one call and fire another:
        # the cap is breached by an arbitrary factor, with no error at all. `cells.py`
        # forwards the `request` that came from the task, so this is reachable via
        # ordinary data, not just malice.
        #
        # This used to be a DENYLIST of 5 keys, and a denylist is the wrong choice
        # here: it protects against what someone remembered to list. It let through
        # `models` (fallback list — CHANGES which model bills), `provider` (route and
        # price), `route`, `n` (multiplies the generation and the bill) and
        # `max_completion_tokens`. An allowlist inverts the default: a new provider key
        # arrives BLOCKED and someone decides, instead of arriving allowed and nobody
        # finding out.
        _ALLOWED = {
            # sampling and format — change neither which model runs nor how many
            # generations come out
            "temperature", "top_p", "top_k", "min_p", "top_a", "seed", "stop",
            "frequency_penalty", "presence_penalty", "repetition_penalty", "logit_bias",
            "response_format", "structured_outputs",
            # tool calling
            "tools", "tool_choice", "parallel_tool_calls",
            # reasoning: what the roster uses to turn off reasoning on expensive models
            "reasoning", "include_reasoning",
            # metadata that does not affect cost
            "user", "metadata", "transforms",
            # `plugins` does NOT go in: it is how OpenRouter enables paid add-ons (web
            # search, for example), and the add-on fee is not in `_estimate`. The
            # caller would reserve only the token cost and find out the rest on the
            # bill.
        }
        if extra_body:
            disallowed = sorted(set(extra_body) - _ALLOWED)
            if disallowed:
                raise ValueError(
                    f"extra_body does not allow {disallowed}. The estimate that "
                    "reserves the budget runs BEFORE dispatch, so a key that swaps the "
                    "model, route, provider or number of generations breaches the cap "
                    f"silently. Allowed: {sorted(_ALLOWED)}. If the key really is "
                    "harmless, add it to the allowlist along with the reason.")
        # The reservation TTL assumes a ceiling on per-attempt duration. `timeout` is a
        # free parameter and `cells.py` forwards the task's `request`, so a timeout
        # larger than the assumption lets the reservation EXPIRE with the call still
        # alive — and then another process spends the same money.
        if timeout * MAX_RETRIES > RESERVATION_TTL_S:
            raise ValueError(
                f"timeout={timeout}s x {MAX_RETRIES} attempts exceeds the reservation "
                f"TTL ({RESERVATION_TTL_S}s): the reservation would expire with the "
                "call in flight and another process could spend the same budget. Raise "
                "RESERVATION_TTL_S along with it if the timeout needs to be larger.")
        est = self._estimate(model, messages, max_tokens)
        self.ledger.reserve(est)  # may raise BudgetExceeded -> does not fire

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,  # streaming: non-streamed deep-research blows the gateway (502)
            "usage": {"include": True},  # asks for the real cost (includes sonar search)
        }
        if response_format:
            payload["response_format"] = response_format
        if extra_body:
            payload.update(extra_body)

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/alessioalionco/high-stakes",
            "X-Title": "high-stakes",
        }

        counter: dict = {"generated": 0}
        try:
            data, generated = self._post_with_retry(headers, payload, timeout, counter)
        except Exception:
            # CONSERVATIVE: dropped streams may have been billed upstream —
            # books the ESTIMATE as spend instead of releasing the reservation.
            print(f"[ledger] call {model} failed post-dispatch — estimate "
                  f"${est:.4f} booked as spend (conservative).")
            # ONE estimate per CHARGEABLE attempt — no more, no less. Chargeable is the
            # one that produced content or died in an unknown state; the clean refusal
            # (429/5xx in the header) is not. If NONE was chargeable, the provider
            # refused everything and there is nothing to pay: release the reservation
            # and be done. Charging "one just in case" there inflated the ledger with
            # no real cent behind it, and an inflated ledger makes the engine stop
            # early and refuse legitimate calls.
            # All in one commit: with two writes, between them the disk shows lower
            # spend than the real one and another process reserves on top of that.
            chargeable = counter.get("generated", 0)
            if chargeable:
                print(f"[ledger] {chargeable} chargeable attempt(s) — "
                      f"${est * chargeable:.4f} in total.")
                self.ledger.charge_failure(est, extra_usd=est * (chargeable - 1))
            else:
                print(f"[ledger] the provider refused every attempt (nothing generated) "
                      f"— releasing the ${est:.4f} reservation.")
                self.ledger.release(est)
            raise

        usage = data.get("usage", {}) or {}
        cost = usage.get("cost")
        if cost is None:
            # fallback: catalog token-math (misses sonar search, but it's what there is)
            in_price, out_price = self._price(model)
            cost = (
                usage.get("prompt_tokens", 0) * in_price
                + usage.get("completion_tokens", 0) * out_price
            )
        cost = float(cost or 0.0)
        if not math.isfinite(cost):
            # `usage.cost` comes from the provider. Non-finite here poisons the whole
            # ledger.
            print(f"[ledger] non-finite cost ({cost}) reported for {model} — "
                  f"using the estimate ${est:.4f} (conservative).")
            cost = est
        if generated:
            # earlier attempts ran at the provider: one estimate each, otherwise the
            # real spend ends up to 4x above what the ledger knows.
            print(f"[ledger] {generated} earlier attempt(s) already generated — "
                  f"charging ${est * generated:.4f} on top of the final cost.")
            self.ledger.charge_extra(est * generated)
        choice = (data.get("choices") or [{}])[0]
        text = (choice.get("message") or {}).get("content") or ""
        result = {
            "text": text,
            "usage": usage,
            "cost_usd": cost,
            "provider": data.get("provider"),
            "model": data.get("model", model),
            "raw": data,
        }

        # The reconcile is the point where the REAL cost can blow the cap — and it
        # raises. The response above HAS ALREADY BEEN PAID FOR: letting the exception
        # bubble up bare throws away text that cost money, and the run that reprocesses
        # it will pay again. The cap still interrupts (which is right: the money is
        # gone), but the result travels along so the caller can save it.
        try:
            self.ledger.reconcile(est, cost)
        except BudgetExceeded as e:
            # The attribute name `response` is a cross-file API (read by
            # cells.py via getattr(e, "response", None)).
            e.response = result
            raise

        return result

    class _Retriable(RuntimeError):
        """Transient error (429/5xx, including error-in-200-body) -> retry.

        `refusal` says whether the upstream EXPLICITLY refused (429 in the body) — not
        whether it generated. The difference matters: there was once a `generated`
        field here decided by the error code, and it was wrong in both directions. The
        right accounting combines this with what was measured on the wire:
          · explicit refusal → chargeable only if CONTENT came before it;
          · any other ending (truncated, server error) → chargeable if ANY byte
            came, because a chunk truncated mid-JSON does not become text but means
            the provider was already generating.
        """

        def __init__(self, msg: str, refusal: bool = False):
            super().__init__(msg)
            self.refusal = refusal

    def _post_with_retry(
        self, headers: dict, payload: dict, timeout: int,
        counter: dict | None = None,
    ) -> tuple[dict, int]:
        """Returns (response, no. of EARLIER attempts that already generated upstream).

        `counter` is a MUTABLE mirror of `generated` for the caller. The counter used
        to live only in here: when the retry ran out, it died with the exception
        (became text in the message) and `chat`'s failure path charged ONE estimate,
        when the provider had generated and billed up to MAX_RETRIES times.
        `charge_extra` was unreachable exactly in the branch where the undercount is
        largest.
        """
        counter = {} if counter is None else counter
        counter.setdefault("generated", 0)
        last_exc: Exception | None = None
        # CHARGEABLE = the attempt produced content (the provider generated, hence
        # billed) OR ended in an AMBIGUOUS state (transport dropped with the stream
        # open, server 5xx). Only the explicit refusal is NOT chargeable: 429 is the
        # provider saying it did not do it. The old rule looked at the error CODE and
        # was wrong in both directions: a stream that dies after 3 chunks did not count
        # (undercount), and an empty stream that ends without [DONE] counted
        # (overcount).
        generated = 0
        for attempt in range(MAX_RETRIES):
            try:
                resp = self._session.post(
                    f"{OPENROUTER_BASE}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=timeout,
                    stream=True,
                )
            except RequestException as exc:
                last_exc = exc
                self._sleep_backoff(attempt, None)
                continue

            if resp.status_code == 429 or 500 <= resp.status_code < 600:
                # `.text` reads the body, which with stream=True is still open: if the
                # read blew the deadline (DeadlineExceeded) or the socket dropped, the
                # exception rose from INSIDE the retriable branch and the retry never
                # happened — the engine gave up on a call the provider told it to
                # repeat. The body here is only for the error message; it is not worth
                # the run.
                try:
                    detail = resp.text[:300]
                except Exception as e:  # noqa: BLE001 — unreadable body is not terminal
                    detail = f"(unreadable body: {type(e).__name__})"
                last_exc = RuntimeError(f"OpenRouter {resp.status_code}: {detail}")
                # 429 and 5xx are NOT the same thing for billing, and treating them
                # alike was a mistake of mine that a regression caught:
                #   429 = the provider SAYS it refused. Nothing generated, nothing
                #         billed.
                #   5xx = server error. It may have generated and failed to
                #         deliver; the state is AMBIGUOUS. Conservative is to charge.
                if resp.status_code != 429:
                    generated += 1
                    counter["generated"] = generated
                retry_after = resp.headers.get("Retry-After")
                resp.close()  # stream=True: close the socket before retrying
                self._sleep_backoff(attempt, retry_after)
                continue
            if resp.status_code != 200:
                # non-retriable 4xx (400/401/403/404) -> terminal error. Same care as
                # the branch above: an unreadable body must not swap the real error for
                # a DeadlineExceeded that hides the status that caused the stop.
                try:
                    detail = resp.text[:500]
                except Exception as e:  # noqa: BLE001
                    detail = f"(unreadable body: {type(e).__name__})"
                raise RuntimeError(
                    f"OpenRouter {resp.status_code} (terminal): {detail}"
                )

            progress = {"bytes": 0, "content": 0}
            try:
                return self._consume_stream(resp, progress), generated
            except (RequestException, OSError) as exc:
                # Transport dropped with the stream already open (RST, read timeout,
                # IncompleteRead). It is the DOMINANT failure in a 300-1200s call, and
                # it used to escape the loop: 1 attempt out of MAX_RETRIES, billed as a
                # failure. UNKNOWN state: the provider may have generated everything
                # and only the return got lost. Conservative is to charge.
                generated += 1
                counter["generated"] = generated
                last_exc = exc
                resp.close()
                self._sleep_backoff(attempt, None)
                continue
            except ORClient._Retriable as exc:
                # error-in-200-body or truncated stream. What decides is what was
                # PRODUCED, not the code: a 429-in-body can arrive after content (it
                # was billed), and an empty stream can end without [DONE] with nothing
                # having been generated (it was not).
                chargeable = (progress["content"] > 0 if exc.refusal
                              else progress["bytes"] > 0)
                if chargeable:
                    generated += 1
                    counter["generated"] = generated
                last_exc = exc
                resp.close()  # stream open -> close before retrying
                self._sleep_backoff(attempt, None)
                continue

        raise RuntimeError(
            f"OpenRouter failed after {MAX_RETRIES} attempts ({generated} already "
            f"generated and billed by the provider): {last_exc}")

    @staticmethod
    def _consume_stream(resp: Response, progress: dict | None = None) -> dict:
        """Accumulates SSE -> dict {choices, usage, provider, citations}.

        OpenRouter embeds upstream errors in a 200 body (`error` field with `code`).
        Classify: code 429/5xx -> _Retriable; otherwise terminal.

        `progress["bytes"]` counts what has already come ON THE WIRE, and is updated on
        every line — including when this function raises. It is the only way the retry
        loop can know whether that attempt was billed up above: the error code does not
        say (a 429-in-body can arrive AFTER content, and an empty stream can end
        without [DONE] with nothing having been generated).

        It counts BYTES received, not parsed content: a chunk truncated mid-JSON turns
        into no text at all, but the bytes were on the wire — the provider generated
        and billed. Measuring by the parse undercounted exactly the most common
        streaming failure.
        """
        progress = {} if progress is None else progress
        progress.setdefault("bytes", 0)     # did anything come on the wire?
        progress.setdefault("content", 0)   # did TEXT come, and not just an error message?
        saw_done = False
        content_parts: list[str] = []
        usage: dict = {}
        provider: str | None = None
        model_id: str | None = None
        citations: list = []
        annotations: list = []
        for raw_line in resp.iter_lines():
            progress["bytes"] += len(raw_line or b"")
            if not raw_line:
                continue
            line = raw_line.decode("utf-8", "replace")
            if line.startswith(": "):  # SSE keep-alive comment
                continue
            if not line.startswith("data: "):
                continue
            data_str = line[6:].strip()
            if data_str == "[DONE]":
                saw_done = True
                break
            try:
                obj = json.loads(data_str)
            except json.JSONDecodeError:
                continue
            err = obj.get("error")
            if err:
                code = err.get("code")
                msg = err.get("message", "")
                if code == 429 or (isinstance(code, int) and 500 <= code < 600):
                    # 429 = refusal (nothing generated, nothing billed there). 5xx =
                    # the provider started and died: conservative is to assume it
                    # generated and billed.
                    raise ORClient._Retriable(f"upstream {code}: {msg}",
                                              refusal=(code == 429))
                raise RuntimeError(f"OpenRouter error-in-body {code} (terminal): {msg}")
            provider = obj.get("provider", provider)
            model_id = obj.get("model", model_id)
            nu = obj.get("usage")
            # do not let a usage chunk WITHOUT cost overwrite one that already has cost
            if nu and (nu.get("cost") is not None or usage.get("cost") is None):
                usage = nu
            if obj.get("citations"):
                citations = obj["citations"]
            for ch in obj.get("choices", []):
                delta = ch.get("delta") or {}
                if delta.get("content"):
                    content_parts.append(delta["content"])
                    progress["content"] += len(delta["content"])
                for ann in delta.get("annotations") or []:
                    annotations.append(ann)
        # A stream that ends WITHOUT the [DONE] was truncated — the connection dropped,
        # the provider died midway. `readline()` returns EOF instead of raising, so the
        # partial response passed as complete: text cut mid-word became an "ok" cell
        # and nobody saw it. Truncation is transient -> back to the retry.
        if not saw_done:
            raise ORClient._Retriable(
                f"truncated stream: ended without [DONE] after {len(content_parts)} "
                "chunks (connection dropped mid-response)")

        message = {"content": "".join(content_parts)}
        if annotations:
            message["annotations"] = annotations
        return {
            "choices": [{"message": message}],
            "usage": usage,
            "provider": provider,
            "model": model_id,
            "citations": citations,
        }

    @staticmethod
    def _sleep_backoff(attempt: int, retry_after: str | None) -> None:
        if retry_after:
            try:
                time.sleep(min(float(retry_after), 30))
                return
            except ValueError:
                pass
        time.sleep(min(2 ** attempt, 30))


# ---- helper for Step 1 and manual smoke-tests ----
def _cli_smoke() -> None:
    """`python3 or_client.py` -> 1 cheap smoke call (GLM, ~$0.0001)."""
    client = ORClient(cap_usd=1.0)
    out = client.chat(
        "z-ai/glm-5.2",
        [{"role": "user", "content": "Reply with only the word: ok"}],
        max_tokens=16,
        extra_body={"reasoning": {"enabled": False}},
    )
    print("text:", repr(out["text"]))
    print("provider:", out["provider"])
    print("cost_usd:", out["cost_usd"])
    print("ledger:", client.ledger.snapshot())


if __name__ == "__main__":
    _cli_smoke()
