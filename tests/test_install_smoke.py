#!/usr/bin/env python3
"""test_install_smoke.py — the experience of whoever installs (this project's convention: PASS/exit≠0).

Simulates the stranger's machine: a working directory that is not the repo, none of the
product's variables in the environment, no API key. A unit test does not catch this class
of failure — it runs from inside the repo, with the author's environment already set up.

It also locks the cover promise: **zero external dependencies**. That is verified by AST
over the whole package, not by trust — it is the kind of rule that dies at the first
convenient `import requests`, and the failure would only show up on the installer's
machine.
"""
import ast
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "high_stakes"


def external_imports() -> set[str]:
    """Top-level modules imported by the package that are NOT in the stdlib."""
    ext: set[str] = set()
    for py in sorted(PKG.rglob("*.py")):
        tree = ast.parse(py.read_text(), filename=str(py))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    ext.add(a.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.level:  # relative (from .x import y) — belongs to the package
                    continue
                if node.module:
                    ext.add(node.module.split(".")[0])
    return {m for m in ext
            if m not in sys.stdlib_module_names and m != "high_stakes"}


def main() -> int:
    results: list[bool] = []

    def case(name, cond, detail=""):
        print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail and not cond else ""))
        results.append(bool(cond))

    # ---- stranger's environment: none of the product's variables, no key ----
    # NO PYTHONPATH: that was exactly the condition missing on the installer's machine.
    # Injecting it made the smoke pass 19/19 while `python3 -m high_stakes.paths` raised
    # ModuleNotFoundError from any real cwd — the test hid the very defect it existed to
    # catch. The commands now go through the launcher, as the adapter instructs.
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("HIGH_STAKES_")
           and k not in ("OPENROUTER_API_KEY", "PYTHONPATH")}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    LAUNCHER = str(ROOT / "bin" / "high-stakes")

    tmp = Path(tempfile.mkdtemp())  # a cwd that is NOT the repo
    try:
        def run(*args, cwd=tmp):
            """Invokes through the LAUNCHER — the real path of whoever installed the plugin."""
            return subprocess.run([LAUNCHER, *args], cwd=cwd, env=env,
                                  capture_output=True, text=True)

        def run_lib(*args, cwd=tmp):
            """Use as a LIBRARY (import in your own script): there, yes, PYTHONPATH."""
            e = dict(env); e["PYTHONPATH"] = str(ROOT)
            return subprocess.run([sys.executable, *args], cwd=cwd, env=e,
                                  capture_output=True, text=True)

        # ---- the cover promise ----
        ext = external_imports()
        case("ZERO external dependencies: every package import is stdlib or relative",
             not ext, f"external: {sorted(ext)}")
        case("version floor declared in pyproject matches the interpreter (tomllib ≥3.11)",
             sys.version_info >= (3, 11))
        case("pyproject declares dependencies = []",
             'dependencies = []' in (ROOT / "pyproject.toml").read_text())

        # ---- imports from outside the repo, with no env at all ----
        r = run_lib("-c", "import high_stakes.or_client, high_stakes.render_dossier, "
                          "high_stakes.qverify, high_stakes.quick_panel, high_stakes.config; print('ok')")
        case("as a library: imports from any directory with PYTHONPATH",
             r.returncode == 0 and "ok" in r.stdout, r.stderr[-200:])

        case("REGRESSION: the launcher exists and is executable",
             os.access(LAUNCHER, os.X_OK))
        # REGRESSION: `ln -s .../bin/high-stakes ~/.local/bin/` is the standard way to put
        # a launcher on the PATH. Without dereferencing the symlink, the dirname pointed at
        # the link's directory and reproduced the original ModuleNotFoundError.
        link = tmp / "link-high-stakes"
        os.symlink(LAUNCHER, link)
        r_link = subprocess.run([str(link), "paths", "core"], cwd=tmp, env=env,
                                capture_output=True, text=True)
        case("REGRESSION: the launcher works when invoked via SYMLINK",
             r_link.returncode == 0 and Path(r_link.stdout.strip()).is_dir(),
             r_link.stderr[-200:])
        # REGRESSION: the symlink-dereferencing loop had no iteration CAP. A cycle
        # (a -> b -> a) made it run forever and the user saw the command HANG, without a
        # single line of output — worse than an error, because there is nothing to report
        # and nothing to search for. Here the cycle is fed straight into the loop because,
        # invoked as `$0`, the kernel itself refuses the exec first (ELOOP): the actually
        # reachable path is an intermediate link this loop builds and the kernel never
        # walked.
        lines = Path(LAUNCHER).read_text().splitlines()
        start = next(i for i, l in enumerate(lines) if l.startswith("HOPS="))
        end = next(i for i, l in enumerate(lines) if i > start and l == "done")
        loop_body = "\n".join(lines[start:end + 1])
        cycle_a, cycle_b = tmp / "cycle_a", tmp / "cycle_b"
        os.symlink(cycle_b, cycle_a)
        os.symlink(cycle_a, cycle_b)
        script = tmp / "just_the_loop.sh"
        script.write_text(f'set -eu\nSRC="{cycle_a}"\n{loop_body}\necho "exited: $SRC"\n')
        r_cycle = subprocess.run(["sh", str(script)], cwd=tmp, capture_output=True,
                                 text=True, timeout=20)
        case("REGRESSION: a symlink cycle STOPS with an error, does not hang forever",
             r_cycle.returncode != 0 and "symlink" in r_cycle.stderr.lower(),
             (r_cycle.stderr or r_cycle.stdout)[-200:])

        # ---- the FIRST command the visitor runs has to exist ----
        # The README instructed `/plugin marketplace add`, and only `plugin.json` existed.
        # Without `marketplace.json` that command fails: the first thing anyone does after
        # reading the landing page is hit an error.
        #
        # SCOPE OF WHAT FOLLOWS — read before adding a case here. These are KNOWN-REGRESSION
        # invariants, NOT schema validation. The authority on the schema is the consumer's
        # own validator, `claude plugin validate <path> --strict`, and it runs in the private
        # repo's publish gate (it cannot run here: CI has no `claude` CLI, and this workflow
        # installs nothing on purpose). Re-implementing the schema here is what already
        # failed: the block below used to assert `"author" in man`, which is TRUE when
        # `author` is a string, and the plugin was uninstallable for every user while 304
        # tests stayed green. An earlier version of this comment claimed the schema had been
        # "checked against the official marketplace on disk" — the official corpus does use
        # `author: {name, email}`, and the type was never compared. Do not grow a second
        # source of truth here; add the regression you measured, and let the real validator
        # own the rest.
        import json as _json
        mkt_p = ROOT / ".claude-plugin" / "marketplace.json"
        case("marketplace.json exists (without it, `/plugin marketplace add` fails)",
             mkt_p.exists())
        if mkt_p.exists():
            mkt = _json.loads(mkt_p.read_text())
            plug = _json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
            missing = [c for c in ("name", "owner", "plugins") if c not in mkt]
            case("marketplace.json has the required fields", not missing,
                 f"missing: {missing}")

            # `owner` and `plugins` are TYPE-CHECKED before use, not after. A malformed
            # manifest used to raise instead of failing: `mkt.get("owner", {}).get("name")`
            # is an AttributeError when `owner` is a string, and `entries[0]` indexes a
            # string one character at a time. A crashing suite reports a traceback where
            # the diagnostic case should have been.
            owner = mkt.get("owner")
            case("owner is an object with a non-empty name (a string here fails install)",
                 isinstance(owner, dict) and isinstance(owner.get("name"), str)
                 and bool(owner["name"].strip()),
                 f"owner={owner!r}")
            entries = mkt.get("plugins")
            case("plugins is a list", isinstance(entries, list), f"plugins={type(entries).__name__}")
            entries = entries if isinstance(entries, list) else []
            case("at least one plugin is listed", bool(entries))
            if entries and isinstance(entries[0], dict):
                e0 = entries[0]
                case("the plugin entry has name and source",
                     "name" in e0 and "source" in e0)
                # the plugin IS this repo's root — if someone moves it to a subdirectory
                # without moving the files, the install downloads an empty plugin and
                # never warns.
                case("source points at the repo root",
                     e0.get("source") in ("./", "."), f"source={e0.get('source')!r}")
                case("REGRESSION: name and version do not diverge from plugin.json",
                     e0.get("name") == plug.get("name")
                     and e0.get("version") == plug.get("version"),
                     f"marketplace={e0.get('name')}/{e0.get('version')} "
                     f"plugin={plug.get('name')}/{plug.get('version')}")
                # and the README has to give the command that ACTUALLY installs this
                readme_txt = (ROOT / "README.md").read_text(encoding="utf-8")
                expected = f"/plugin install {e0.get('name')}@{mkt.get('name')}"
                case("the README's install command matches the manifest",
                     expected in readme_txt, f"expected '{expected}'")

        r_bare = subprocess.run([sys.executable, "-m", "high_stakes.paths", "core"],
                                cwd=tmp, env=env, capture_output=True, text=True)
        case("REGRESSION: `python3 -m high_stakes.X` WITHOUT PYTHONPATH fails — this is "
             "why the adapter documents the launcher, not the -m",
             r_bare.returncode != 0 and "ModuleNotFoundError" in r_bare.stderr)

        # ---- the commands the adapter calls ----
        r = run("paths", "core")
        case("`paths core` answers an existing path from outside the repo",
             r.returncode == 0 and Path(r.stdout.strip()).is_dir(), r.stderr[-200:])

        r = run("config")
        case("`config` runs without a created HOME and without a key, and WARNS the key is missing",
             r.returncode == 0 and "MISSING" in r.stdout, r.stderr[-200:])
        case("`config` falls back to the shipped boards when the user has none",
             "high-stakes/boards" in r.stdout.replace(os.sep, "/"), r.stdout[-200:])

        # ---- the gate and the render, end to end, over the example ----
        r = run("render_gate", str(ROOT / "examples" / "sample-dossier.md"))
        case("render gate exits 0 on the example dossier, run from outside the repo",
             r.returncode == 0, r.stdout[-300:])

        out_html = tmp / "output.html"
        r = run("render_dossier",
                str(ROOT / "examples" / "sample-dossier.md"), str(out_html))
        case("render produces HTML from outside the repo", r.returncode == 0 and out_html.exists(),
             r.stderr[-200:])
        if out_html.exists():
            h = out_html.read_text()
            case("generated HTML is single-file (embedded CSS, zero external references)",
                 "<style>" in h and "<link " not in h and 'src="http' not in h)
            case("REGRESSION: the CSS came from the package — render does not depend on examples/",
                 len(h) > 20000)

        # ---- a usage error must not be a stack trace ----
        r = run("render_gate")
        case("gate without an argument exits 2 with a usage message, not a stack trace",
             r.returncode == 2 and "Traceback" not in r.stderr)
        r = run("render_gate", str(tmp / "does-not-exist.md"))
        case("gate on a nonexistent file exits 1 with a message, not a stack trace",
             r.returncode == 1 and "Traceback" not in r.stderr)

        # ---- publication hygiene: the repo must not leak the machine or the origin ----
        # (the check for the company/employer NAME lives outside this repo, on purpose:
        # a test that searched for the name would have to contain the name.)
        SRC = [f for f in ROOT.rglob("*")
               if f.is_file() and ".git/" not in str(f)
               and f.suffix in {".py", ".md", ".toml", ".yaml", ".json", ".css"}]

        SELF = Path(__file__).resolve()  # the checker contains the needles: finding
        machine = [f.relative_to(ROOT) for f in SRC          # itself is a false positive
                   if f.resolve() != SELF
                   and any(s in f.read_text(errors="ignore")
                           for s in ("/Users/", "/home/", "C:\\Users"))]
        case("no absolute machine path in the repo", not machine, f"{machine}")

        import re as _re
        ALLOW = ("apache.org", "openrouter.ai", "github.com/alessioalionco",
                 "127.0.0.1", "localhost", "www.w3.org")
        urls = set()
        for f in SRC:
            if f.name.startswith("test_"):
                continue  # fixtures use made-up domains on purpose
            for u in _re.findall(r"https?://[\w./-]+", f.read_text(errors="ignore")):
                if not any(a in u for a in ALLOW):
                    urls.add(u)
        case("every published URL is on the allowlist", not urls, f"{sorted(urls)}")

        emails = set()
        for f in SRC:
            if f.name == "LICENSE":
                continue
            emails |= set(_re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", f.read_text(errors="ignore")))
        case("no e-mail embedded in the code or the docs", not emails, f"{sorted(emails)}")

        # ---- the plugin ----
        import json
        man = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
        case("the plugin manifest has the required fields",
             all(k in man for k in ("name", "description", "version", "author")))
        # REGRESSION (measured): `author` was the string "Alessio Alionco" and every
        # `/plugin install high-stakes@high-stakes` died on
        #   `author: Invalid input: expected object, received string`
        # The presence check above does not see it — `"author" in man` is True either way.
        # The schema wants an object; the official marketplace ships `{name, email}`.
        _author = man.get("author")
        case("plugin.json `author` is an object with a non-empty name, not a string",
             isinstance(_author, dict) and isinstance(_author.get("name"), str)
             and bool(_author["name"].strip()),
             f"author={_author!r} — a string here makes the plugin impossible to install")
        case("the plugin's skill exists at the path the harness looks for",
             (ROOT / "skills" / man["name"] / "SKILL.md").exists())
        case("the plugin version matches the package's",
             man["version"] in (ROOT / "pyproject.toml").read_text())

        print(f"{sum(results)}/{len(results)} tests ok")
        return 0 if all(results) else 1
    finally:
        __import__("shutil").rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
