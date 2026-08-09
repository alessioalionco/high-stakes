"""naming.py — the engine's SINGLE filename-sanitization rule (zero dependencies).

Canonical source of SAFE_FILENAME used by cells (cell filenames) and evidence
(per-ask cache). Lives in a dependency-free module so every layer imports the
same rule instead of copying the regex.
"""
from __future__ import annotations

import re

SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._@-]+")
