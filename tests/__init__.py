"""Test package init — isolates every suite from the developer's own configuration.

WHY THIS FILE HAS CONTENT. `config.home()` resolves to `~/.high-stakes` when
`HIGH_STAKES_HOME` is unset, so any suite that reaches config — directly or through
`run_cells`, `pin_path()`, `boards_dir()` — reads whatever the person running the tests
happens to have configured. The suite then measures the machine, not the code.

This was not theoretical. The author configured his own instance for the first time
(dogfooding the published plugin) and five suites changed behaviour on the spot:
`test_install_smoke` and `test_quick_panel` went red because their "shipped default"
cases were resolving HIS boards and HIS pin, and `test_build_gate`, `test_cells` and
`test_flow_gate` went red because his `require_build_check = true` made the paid
dispatch path refuse inside the tests. Nothing about the engine had changed. Every one
of those cases had been passing for the wrong reason: the author had no config.

It is the same shape as the PYTHONPATH defect this suite already carries a comment
about — the test supplying the very condition whose absence it exists to detect.

Setting HIGH_STAKES_HOME to an empty directory makes "the user has no config" TRUE
instead of merely likely. A suite that wants to test configured behaviour writes a
config into a temp home of its own and points at it explicitly, which is the honest way
to say what it is measuring.

Deliberately does NOT override an explicit HIGH_STAKES_HOME: a maintainer debugging
against a real config can still set it, and then owns the result.
"""
import os
import tempfile

if not os.environ.get("HIGH_STAKES_HOME"):
    # Not cleaned up: a few KB in the OS temp dir, and the alternative (atexit) races
    # with subprocesses the suites spawn, which inherit this value.
    os.environ["HIGH_STAKES_HOME"] = tempfile.mkdtemp(prefix="high-stakes-tests-home-")
