#!/usr/bin/env python3
"""
Disposable bootstrap for a new project.

  1. Self-destructs so git never tracks this file.
  2. Downloads launcher_common.py for shared initialization logic.
  3. git init --initial-branch=main
  4. Register cursor submodules (.cursor/rules/shared, .cursor/commands/shared)
  5. git add -A && git commit -m "Initial commit"
  6. Create develop branch, switch to it
  7. (Optional) gh repo create + push both branches with upstream tracking

Usage:
  1. Copy this file into an empty project folder.
  2. Run:  python launch_bomb.py
  3. The script self-destructs, then initializes the project.

Requires: Python 3.8+, git on PATH.  gh on PATH for GitHub integration.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

COMMON_URL = (
    "https://raw.githubusercontent.com/rksilvergreen/launch_bomb/main/launcher_common.py"
)

SELF = os.path.abspath(__file__)


# ---------------------------------------------------------------------------
# Bootstrap helpers
# ---------------------------------------------------------------------------

def _fetch(url: str) -> bytes:
    print(f"Fetching {url} ...", flush=True)
    try:
        with urllib.request.urlopen(url) as resp:
            return resp.read()
    except urllib.error.URLError as exc:
        sys.stderr.write(f"FATAL: Could not fetch {url}: {exc}\n")
        sys.exit(1)


def _load_common():
    """Download launcher_common.py and import it as a module."""
    content = _fetch(COMMON_URL)
    fd, tmp_path = tempfile.mkstemp(suffix="_launcher_common.py")
    try:
        os.write(fd, content)
        os.close(fd)
        spec = importlib.util.spec_from_file_location("launcher_common", tmp_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
    return mod


def _self_destruct() -> None:
    if os.path.exists(SELF):
        os.remove(SELF)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    _self_destruct()

    common = _load_common()
    root = Path.cwd().resolve()

    common.preflight(root)
    github_ok = common.init_repo(root)

    print(f"\n{'=' * 50}", flush=True)
    print(f"Project ready: {root}", flush=True)
    print(f"  Default branch : {common.MAIN_BRANCH}", flush=True)
    print(f"  Current branch : {common.DEVELOP_BRANCH}", flush=True)
    print(f"  GitHub remote  : {'configured' if github_ok else 'not configured'}", flush=True)
    print(f"{'=' * 50}\n", flush=True)


if __name__ == "__main__":
    main()
