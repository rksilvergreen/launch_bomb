#!/usr/bin/env python3
"""
Initialize a new project directory with Git, Cursor submodules, and optional GitHub remote.

Sequence:
  1. git init --initial-branch=main
  2. Register cursor submodules (.cursor/rules/shared, .cursor/commands/shared)
  3. git add -A && git commit -m "Initial commit"
  4. Create develop branch, switch to it
  5. (Optional) gh repo create + push both branches with upstream tracking

Requires: Python 3.7+, git on PATH.  gh on PATH for GitHub integration.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

MAIN_BRANCH = "main"
DEVELOP_BRANCH = "develop"
INITIAL_COMMIT_MESSAGE = "Initial commit"
REMOTE_NAME = "origin"
GH_EXECUTABLE = "gh"

SUBMODULES: List[Tuple[str, str, str]] = [
    (
        "cursor_rules",
        "https://github.com/rksilvergreen/cursor_rules.git",
        ".cursor/rules/shared",
    ),
    (
        "cursor_commands",
        "https://github.com/rksilvergreen/cursor_commands.git",
        ".cursor/commands/shared",
    ),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(cmd: List[str], *, cwd: Path, capture: bool = False, check: bool = True) -> subprocess.CompletedProcess:
    label = " ".join(cmd)
    print(f"+ {label}", flush=True)
    result = subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=capture,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        detail = ""
        if capture:
            detail = (result.stderr or result.stdout or "").strip()
        sys.stderr.write(f"FATAL: `{label}` exited {result.returncode}")
        if detail:
            sys.stderr.write(f": {detail}")
        sys.stderr.write("\n")
        sys.exit(result.returncode)
    return result


def _git(args: List[str], *, cwd: Path, capture: bool = False, check: bool = True) -> subprocess.CompletedProcess:
    return _run(["git", *args], cwd=cwd, capture=capture, check=check)


def _inside_git_work_tree(cwd: Path) -> bool:
    r = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    return r.returncode == 0 and r.stdout.strip().lower() == "true"


def _normalize(p: str) -> str:
    return p.replace("\\", "/")


def _submodule_path_registered(root: Path, rel_path: str) -> bool:
    want = _normalize(rel_path)
    r = subprocess.run(
        ["git", "config", "-f", ".gitmodules", "--get-regexp", r"^submodule\..*\.path$"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    if r.returncode != 0:
        return False
    for line in r.stdout.splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2 and _normalize(parts[1].strip()) == want:
            return True
    return False


def _gh_available() -> bool:
    try:
        r = subprocess.run(
            [GH_EXECUTABLE, "--version"],
            capture_output=True, text=True, check=False,
        )
        return r.returncode == 0
    except OSError:
        return False


def _gh_authenticated(cwd: Path) -> bool:
    try:
        r = subprocess.run(
            [GH_EXECUTABLE, "auth", "status"],
            cwd=str(cwd),
            capture_output=True, text=True, check=False,
        )
        return r.returncode == 0
    except OSError:
        return False


def _gh_repo_create(*, cwd: Path, name: str, remote: str) -> bool:
    """Create a private GitHub repo via gh.  Returns True on success."""
    cmd = [
        GH_EXECUTABLE, "repo", "create", name,
        "--source", str(cwd),
        "--remote", remote,
        "--private",
    ]
    print(f"+ {' '.join(cmd)}", flush=True)
    r = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=False)
    if r.returncode != 0:
        detail = (r.stderr or r.stdout or "").strip()
        print(f"WARNING: gh repo create failed (exit {r.returncode}): {detail or 'no output'}", flush=True)
        return False
    return True


# ---------------------------------------------------------------------------
# Main workflow
# ---------------------------------------------------------------------------

def main() -> None:
    root = Path.cwd().resolve()
    repo_name = root.name

    # -- pre-flight: git must be available -----------------------------------
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        sys.stderr.write("FATAL: git is not installed or not on PATH.\n")
        sys.exit(1)

    # -- refuse to run inside an existing repo -------------------------------
    if _inside_git_work_tree(root):
        sys.stderr.write(
            f"FATAL: A git repository already exists at {root}.\n"
            "       Remove .git or run from an empty directory.\n"
        )
        sys.exit(1)

    # -- 1. git init ---------------------------------------------------------
    print(f"\n=== Initializing git repository in {root} ===\n", flush=True)
    _git(["init", "--initial-branch", MAIN_BRANCH], cwd=root)

    # -- 2. submodules (before first commit) ---------------------------------
    print(f"\n=== Adding Cursor submodules ===\n", flush=True)
    for name, url, path in SUBMODULES:
        if _submodule_path_registered(root, path):
            print(f"  skip {name}: already registered at {path}", flush=True)
            continue
        _git(["submodule", "add", url, path], cwd=root)

    # -- 3. initial commit ---------------------------------------------------
    print(f"\n=== Creating initial commit ===\n", flush=True)
    _git(["add", "-A"], cwd=root)
    r = _git(["commit", "-m", INITIAL_COMMIT_MESSAGE], cwd=root, capture=True, check=False)
    if r.returncode != 0:
        _git(["commit", "--allow-empty", "-m", INITIAL_COMMIT_MESSAGE], cwd=root)

    # -- 4. branches ---------------------------------------------------------
    print(f"\n=== Creating {DEVELOP_BRANCH} branch ===\n", flush=True)
    _git(["branch", DEVELOP_BRANCH], cwd=root)
    _git(["switch", DEVELOP_BRANCH], cwd=root)

    # -- 5. optional GitHub remote -------------------------------------------
    print(f"\n=== GitHub remote ===\n", flush=True)
    github_ok = False
    if not _gh_available():
        print(
            "  gh CLI not found. Skipping GitHub repo creation.\n"
            "  Install https://cli.github.com or add the remote manually.",
            flush=True,
        )
    elif not _gh_authenticated(root):
        print(
            "  gh is not authenticated (run `gh auth login`).\n"
            "  Skipping GitHub repo creation.",
            flush=True,
        )
    else:
        github_ok = _gh_repo_create(cwd=root, name=repo_name, remote=REMOTE_NAME)

    if github_ok:
        _git(["switch", MAIN_BRANCH], cwd=root)
        _git(["push", "-u", REMOTE_NAME, MAIN_BRANCH], cwd=root)
        _git(["switch", DEVELOP_BRANCH], cwd=root)
        _git(["push", "-u", REMOTE_NAME, DEVELOP_BRANCH], cwd=root)

    # -- done ----------------------------------------------------------------
    print(f"\n{'=' * 50}", flush=True)
    print(f"Project ready: {root}", flush=True)
    print(f"  Default branch : {MAIN_BRANCH}", flush=True)
    print(f"  Current branch : {DEVELOP_BRANCH}", flush=True)
    print(f"  GitHub remote  : {'configured' if github_ok else 'not configured'}", flush=True)
    print(f"{'=' * 50}\n", flush=True)


if __name__ == "__main__":
    main()
