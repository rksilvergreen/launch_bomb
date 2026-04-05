#!/usr/bin/env python3
"""
Disposable bootstrap: fetches project_launcher.py from the launch_bomb repo,
deletes itself so git never tracks it, then runs the launcher.

Usage:
  1. Copy this file into an empty project folder.
  2. Run:  python launch_bomb.py
  3. The script self-destructs before the launcher runs.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

LAUNCHER_URL = (
    "https://raw.githubusercontent.com/rksilvergreen/launch_bomb/main/project_launcher.py"
)

SELF = os.path.abspath(__file__)


def _fetch(url: str) -> bytes:
    print(f"Fetching {url} ...", flush=True)
    try:
        with urllib.request.urlopen(url) as resp:
            return resp.read()
    except urllib.error.URLError as exc:
        sys.stderr.write(f"FATAL: Could not fetch launcher script: {exc}\n")
        sys.exit(1)


def main() -> None:
    content = _fetch(LAUNCHER_URL)

    if os.path.exists(SELF):
        os.remove(SELF)

    fd, tmp_path = tempfile.mkstemp(suffix=".py")
    try:
        os.write(fd, content)
        os.close(fd)

        result = subprocess.run([sys.executable, tmp_path])
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
