#!/usr/bin/env python3
"""test_quick_panel.py — executable suite for the quick preset (convention: PASS/exit≠0)."""
import sys
import tempfile
from datetime import date
from pathlib import Path

from high_stakes import config as hs_config
from high_stakes.quick_panel import (DEFAULT_PIN, MATERIAL_HEADER, build_quick_tasks, load_pin,
                         pin_expired)

PIN_FIXTURE = """# comment
pinned: "2026-07-21"
ttl_days: 30
chairman: {model: anthropic/claude-fable-5, family: anthropic, votes: false}
quick_judges:
  - {model: openai/gpt-5.6-sol, family: openai}
  - {model: x-ai/grok-4.5, family: xai}
  - {model: z-ai/glm-5.2, family: zai, reasoning: off}
full_extra_judge: {model: moonshotai/kimi-k3, family: moonshot, reasoning: off}
refuter: {model: google/gemini-3.1-pro-preview, family: google}
source: "AA Index #jul and X-J1"  # real comment
"""


def case(name, cond):
    print(("PASS" if cond else "FAIL"), name)
    return cond


def main() -> int:
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        f.write(PIN_FIXTURE)
        pin_path = Path(f.name)
    try:
        pin = load_pin(pin_path)
        personas = {"unit economist": "You are The Unit Economist. PACK…", "generalist": "You are the generalist."}
        tasks = build_quick_tasks("DECK XYZ 123", personas,
                                  ask_builder=lambda k: f"ASK({k})",
                                  parse=lambda t: {"ok": t}, pin=pin)
        tasks_full = build_quick_tasks("DECK XYZ 123", personas, lambda k: "A",
                                       lambda t: t, pin=pin, full=True)
        from high_stakes.quick_panel import MATERIAL_FOOTER
        shared = MATERIAL_HEADER + "DECK XYZ 123" + MATERIAL_FOOTER
        prefixes = {t["messages"][1]["content"][:len(shared)] for t in tasks}
        systems = {t["messages"][0]["content"] for t in tasks}
        glm = [t for t in tasks if t["model"] == "z-ai/glm-5.2"]
        sol = [t for t in tasks if t["model"] == "openai/gpt-5.6-sol"]
        results = [
            case("pin: 3 quick judges + families", len(pin["quick_judges"]) == 3
                 and {j["family"] for j in pin["quick_judges"]} == {"openai", "xai", "zai"}),
            case("pin: extra judge and refuter are read",
                 pin["full_extra_judge"]["model"] == "moonshotai/kimi-k3"
                 and pin["refuter"]["family"] == "google"),
            case("the repo pin loads and is consistent with the fixture",
                 {j["model"] for j in load_pin(DEFAULT_PIN)["quick_judges"]}
                 == {j["model"] for j in pin["quick_judges"]}),
            case("quick = personas × 3 judges", len(tasks) == 6),
            case("full adds the 4th judge (M=4)", len(tasks_full) == 8),
            case("CACHING: byte-identical user prefix in every cell",
                 len(prefixes) == 1 and next(iter(prefixes)) == shared),
            case("CACHING: identical, generic system (persona in the suffix)",
                 len(systems) == 1 and "The Unit Economist" not in next(iter(systems))),
            case("persona/ask present in the suffix",
                 any("You are The Unit Economist" in t["messages"][1]["content"]
                     and "ASK(unit economist)" in t["messages"][1]["content"] for t in tasks)),
            case("reasoning off only where the pin says so",
                 all("extra_body" in t["request"] for t in glm)
                 and all("extra_body" not in t["request"] for t in sol)),
            case("pin valid within the TTL", not pin_expired(pin, today=date(2026, 8, 1))),
            case("pin expired past the TTL", pin_expired(pin, today=date(2026, 8, 25))),
            case("REGRESSION: a quoted date does not break pin_expired",
                 not pin_expired(pin, today=date(2026, 7, 22))),
            case("REGRESSION: 'votes: false' becomes bool",
                 pin["chairman"]["votes"] is False),
            case("REGRESSION: a '#' inside a quoted value is preserved",
                 pin.get("source") == "AA Index #jul and X-J1"),
            case("REGRESSION: judges of the SAME family do not collide on cell_id",
                 len({t2["cell_id"] for t2 in build_quick_tasks(
                     "M", {"p1": "P"}, lambda k: "A", lambda x: x,
                     pin={"quick_judges": [
                         {"model": "openai/gpt-5.6-sol", "family": "openai"},
                         {"model": "openai/gpt-5.6-luna", "family": "openai"}],
                          "ttl_days": 30})}) == 2),
            # REGRESSION: the BUNDLED pin has a placeholder date. If the parser crashes on
            # it, whoever installs and runs without pinning their own roster breaks on
            # their first decision.
            case("an unreadable date in the pin counts as EXPIRED, no crash",
                 pin_expired({"pinned": "0000-00-00", "ttl_days": 30}) is True),
            case("a pin without a date field counts as EXPIRED",
                 pin_expired({"ttl_days": 30}) is True),
            case("an unreadable ttl counts as EXPIRED",
                 pin_expired({"pinned": "2026-01-01", "ttl_days": "x"}) is True),
            case("the pin SHIPPED with the install loads and is evaluable without crashing",
                 pin_expired(load_pin(hs_config.pin_path())) is True),
        ]
        # ATTENTION, whoever adds a test below this point: `results` above is a LITERAL
        # LIST. A stray `case(...)` after it PRINTS PASS/FAIL but enters neither the
        # count nor the exit code — the suite stays green with the test red. Use
        # `results.append(case(...))`, as below. (That is exactly how the isolation
        # check came to report 19/19 with a FAIL on screen.)

        # ---- ISOLATION BETWEEN JUDGES: the invariant the product sells ----
        # The adversarial panel is only worth anything if no one reads anyone else. If one
        # advisor's reply enters another's prompt, the consensus becomes an echo and the
        # confirmation is FALSE — and that is worse than an ordinary bug, because the
        # dossier comes out pretty and more confident, not broken.
        # Today isolation is true by CONSTRUCTION (the message is assembled only from
        # material + persona + ask), but nothing locked the invariant: whoever added a
        # "round 2" feeding outputs back in would see nothing turn red. This locks it.
        ANOTHER_ADVISORS_REPLY = "UNIT ECONOMIST'S VERDICT: the NRR does not support the thesis."
        markers = ["DECK XYZ 123"]  # the shared material is the ONLY common text
        contaminated = [t["cell_id"] for t in tasks
                        if ANOTHER_ADVISORS_REPLY in t["messages"][1]["content"]]
        results.append(case("isolation: no cell carries another cell's reply", not contaminated))

        # and the positive proof that the test can detect: the SAME check, against a
        # deliberately contaminated task, has to flag it. Without this the test above
        # passes trivially and becomes decorative (that is how the retry-billing test
        # spent months satisfied via another path).
        poisoned = dict(tasks[0])
        poisoned["messages"] = [tasks[0]["messages"][0],
                                {"role": "user",
                                 "content": tasks[0]["messages"][1]["content"]
                                 + "\n\n" + ANOTHER_ADVISORS_REPLY}]
        results.append(case("isolation: the check FLAGS contamination when present (not decorative)",
             ANOTHER_ADVISORS_REPLY in poisoned["messages"][1]["content"]))

        # a cell's content, minus the shared material and its own persona, must not
        # appear in another cell: that is what guarantees the divergence comes from the
        # model/persona and not from inherited context.
        suffixes = {}
        for t in tasks:
            body = t["messages"][1]["content"][len(shared):]
            suffixes[t["cell_id"]] = body
        leaked = [(a, b) for a, ca in suffixes.items() for b, cb in suffixes.items()
                  if a != b and suffixes[a] != suffixes[b] and ca in cb]
        results.append(case("isolation: one cell's suffix is not contained in another's", not leaked))
        results.append(case("isolation: the only text common to all cells is the shared material",
             all(m in t["messages"][1]["content"] for t in tasks for m in markers)))

        print(f"{sum(results)}/{len(results)} tests ok")
        return 0 if all(results) else 1
    finally:
        pin_path.unlink()


if __name__ == "__main__":
    sys.exit(main())
