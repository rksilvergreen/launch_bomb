#!/usr/bin/env python3
"""
Shared project-initialization logic used by launch_bomb.py
and doc_shell_launch_bomb.py.

Provides helpers for running commands, git operations, GitHub integration,
and the full git-init → submodules → commit → branch → push workflow.

Requires: Python 3.8+, git on PATH.  gh on PATH for GitHub integration.
"""
from __future__ import annotations

import subprocess
import sys
import time
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

PUSH_MAX_ATTEMPTS = 5
PUSH_RETRY_DELAY_SECS = 3


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_cmd(
    cmd: List[str],
    *,
    cwd: Path,
    capture: bool = False,
    check: bool = True,
) -> subprocess.CompletedProcess:
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


def git(
    args: List[str],
    *,
    cwd: Path,
    capture: bool = False,
    check: bool = True,
) -> subprocess.CompletedProcess:
    return run_cmd(["git", *args], cwd=cwd, capture=capture, check=check)


def inside_git_work_tree(cwd: Path) -> bool:
    r = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    return r.returncode == 0 and r.stdout.strip().lower() == "true"


def gh_available() -> bool:
    try:
        r = subprocess.run(
            [GH_EXECUTABLE, "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
        return r.returncode == 0
    except OSError:
        return False


def gh_authenticated(cwd: Path) -> bool:
    try:
        r = subprocess.run(
            [GH_EXECUTABLE, "auth", "status"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=False,
        )
        return r.returncode == 0
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

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


def _gh_repo_create(*, cwd: Path, name: str, remote: str) -> bool:
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
        print(
            f"WARNING: gh repo create failed (exit {r.returncode}): {detail or 'no output'}",
            flush=True,
        )
        return False
    return True


def _push_with_retry(*, cwd: Path, remote: str, branch: str) -> None:
    cmd_label = f"git push -u {remote} {branch}"
    for attempt in range(1, PUSH_MAX_ATTEMPTS + 1):
        r = git(["push", "-u", remote, branch], cwd=cwd, capture=True, check=False)
        if r.returncode == 0:
            return
        if attempt < PUSH_MAX_ATTEMPTS:
            print(
                f"  push failed (attempt {attempt}/{PUSH_MAX_ATTEMPTS}), "
                f"retrying in {PUSH_RETRY_DELAY_SECS}s …",
                flush=True,
            )
            time.sleep(PUSH_RETRY_DELAY_SECS)
    detail = (r.stderr or r.stdout or "").strip()
    sys.stderr.write(f"FATAL: `{cmd_label}` failed after {PUSH_MAX_ATTEMPTS} attempts")
    if detail:
        sys.stderr.write(f": {detail}")
    sys.stderr.write("\n")
    sys.exit(r.returncode)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def preflight(root: Path) -> None:
    """Verify git is available and *root* is not already inside a git repo."""
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        sys.stderr.write("FATAL: git is not installed or not on PATH.\n")
        sys.exit(1)

    if inside_git_work_tree(root):
        sys.stderr.write(
            f"FATAL: A git repository already exists at {root}.\n"
            "       Remove .git or run from an empty directory.\n"
        )
        sys.exit(1)


def init_repo(root: Path) -> bool:
    """
    Full git initialization: init, submodules, initial commit, branches,
    and optional GitHub remote.

    Returns True if a GitHub remote was successfully created.
    Assumes preflight() has already passed.
    """
    repo_name = root.name

    # -- 1. git init ---------------------------------------------------------
    print(f"\n=== Initializing git repository in {root} ===\n", flush=True)
    git(["init", "--initial-branch", MAIN_BRANCH], cwd=root)

    # -- 2. submodules -------------------------------------------------------
    print("\n=== Adding Cursor submodules ===\n", flush=True)
    for name, url, path in SUBMODULES:
        if _submodule_path_registered(root, path):
            print(f"  skip {name}: already registered at {path}", flush=True)
            continue
        git(["submodule", "add", url, path], cwd=root)

    # -- 3. initial commit ---------------------------------------------------
    print("\n=== Creating initial commit ===\n", flush=True)
    git(["add", "-A"], cwd=root)
    r = git(["commit", "-m", INITIAL_COMMIT_MESSAGE], cwd=root, capture=True, check=False)
    if r.returncode != 0:
        git(["commit", "--allow-empty", "-m", INITIAL_COMMIT_MESSAGE], cwd=root)

    # -- 4. branches ---------------------------------------------------------
    print(f"\n=== Creating {DEVELOP_BRANCH} branch ===\n", flush=True)
    git(["branch", DEVELOP_BRANCH], cwd=root)
    git(["switch", DEVELOP_BRANCH], cwd=root)

    # -- 5. optional GitHub remote -------------------------------------------
    print("\n=== GitHub remote ===\n", flush=True)
    github_ok = False
    if not gh_available():
        print(
            "  gh CLI not found. Skipping GitHub repo creation.\n"
            "  Install https://cli.github.com or add the remote manually.",
            flush=True,
        )
    elif not gh_authenticated(root):
        print(
            "  gh is not authenticated (run `gh auth login`).\n"
            "  Skipping GitHub repo creation.",
            flush=True,
        )
    else:
        github_ok = _gh_repo_create(cwd=root, name=repo_name, remote=REMOTE_NAME)

    if github_ok:
        git(["switch", MAIN_BRANCH], cwd=root)
        _push_with_retry(cwd=root, remote=REMOTE_NAME, branch=MAIN_BRANCH)
        git(["switch", DEVELOP_BRANCH], cwd=root)
        _push_with_retry(cwd=root, remote=REMOTE_NAME, branch=DEVELOP_BRANCH)

    return github_ok
