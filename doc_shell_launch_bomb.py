#!/usr/bin/env python3
"""
Disposable bootstrap for a new doc_shell project.

  1. Self-destructs so git never tracks this file.
  2. Downloads launcher_common.py for shared initialization logic.
  3. Sparse-checkouts the doc_shell template from GitHub.
  4. Copies template files and replaces placeholder project names.
  5. Runs npm install.
  6. Full git initialization (init, submodules, commit, branches, GitHub).

The project name is derived from the folder name in three case styles:
  - snake_case  → Vite alias, TypeScript paths   (e.g. my_cool_docs)
  - kebab-case  → npm package name                (e.g. my-cool-docs)
  - Title Case  → site title in .astro pages      (e.g. My Cool Docs)

Usage:
  1. Copy this file into an empty project folder.
  2. Run:  python doc_shell_launch_bomb.py
  3. The script self-destructs, then scaffolds and initializes the project.

Requires: Python 3.8+, git on PATH, npm on PATH.  gh on PATH for GitHub.
"""
from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

COMMON_URL = (
    "https://raw.githubusercontent.com/rksilvergreen/launch_bomb/main/launcher_common.py"
)
DOC_SHELL_REPO = "https://github.com/rksilvergreen/doc_shell.git"
TEMPLATE_SUBDIR = "template"

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
# Name derivation
# ---------------------------------------------------------------------------

def _name_variants(folder_name: str) -> dict:
    """Split a folder name on _, -, or whitespace and produce three case styles."""
    parts = re.split(r"[_\-\s]+", folder_name.strip().lower())
    parts = [p for p in parts if p]
    return {
        "snake": "_".join(parts),
        "kebab": "-".join(parts),
        "title": " ".join(p.capitalize() for p in parts),
    }


# ---------------------------------------------------------------------------
# Template scaffolding
# ---------------------------------------------------------------------------

def _scaffold_template(root: Path, names: dict, *, common) -> None:
    """Sparse-checkout the doc_shell template and copy it into *root*."""
    tmp_parent = tempfile.mkdtemp(prefix="doc_shell_scaffold_")
    clone_dir = Path(tmp_parent) / "repo"

    try:
        print("\n=== Downloading doc_shell template ===\n", flush=True)
        common.run_cmd(
            ["git", "clone", "--filter=blob:none", "--sparse",
             DOC_SHELL_REPO, str(clone_dir)],
            cwd=root,
            capture=True,
        )
        common.run_cmd(
            ["git", "sparse-checkout", "set", TEMPLATE_SUBDIR],
            cwd=clone_dir,
            capture=True,
        )

        template_dir = clone_dir / TEMPLATE_SUBDIR
        if not template_dir.is_dir():
            sys.stderr.write(
                f"FATAL: template directory not found at {template_dir}\n"
            )
            sys.exit(1)

        print(f"  Copying template into {root} ...", flush=True)
        shutil.copytree(template_dir, root, dirs_exist_ok=True)

        print("  Replacing project-name placeholders ...", flush=True)
        _replace_in_tree(root, names)

    finally:
        shutil.rmtree(tmp_parent, ignore_errors=True)


def _replace_in_tree(root: Path, names: dict) -> None:
    """Replace placeholder names in every text file under *root*."""
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, ValueError):
            continue

        original = content
        content = content.replace("project-name", names["kebab"])
        content = content.replace("project_name", names["snake"])
        content = content.replace("Project Name", names["title"])

        if content != original:
            path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# npm install
# ---------------------------------------------------------------------------

def _npm_install(root: Path) -> None:
    print("\n=== Running npm install ===\n", flush=True)

    npm_cmd = shutil.which("npm")
    if npm_cmd is None:
        print(
            "WARNING: npm not found on PATH. Skipping npm install.\n"
            "  Run `npm install` manually to install dependencies.",
            flush=True,
        )
        return

    try:
        r = subprocess.run(
            [npm_cmd, "install"],
            cwd=str(root),
            text=True,
            check=False,
        )
        if r.returncode != 0:
            print(
                f"WARNING: npm install exited with code {r.returncode}.\n"
                "  Run `npm install` manually to install dependencies.",
                flush=True,
            )
    except OSError as exc:
        print(
            f"WARNING: npm install failed: {exc}\n"
            "  Run `npm install` manually to install dependencies.",
            flush=True,
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    _self_destruct()

    common = _load_common()
    root = Path.cwd().resolve()
    names = _name_variants(root.name)

    print(f"\n{'=' * 50}", flush=True)
    print(f"Setting up doc_shell project: {names['title']}", flush=True)
    print(f"{'=' * 50}\n", flush=True)

    common.preflight(root)

    # 1. Scaffold template files
    _scaffold_template(root, names, common=common)

    # 2. Install npm dependencies (before git init so package-lock.json is committed)
    _npm_install(root)

    # 3. Git init, submodules, commit, branches, GitHub
    github_ok = common.init_repo(root)

    print(f"\n{'=' * 50}", flush=True)
    print(f"doc_shell project ready: {root}", flush=True)
    print(f"  Project name   : {names['title']}", flush=True)
    print(f"  Default branch : {common.MAIN_BRANCH}", flush=True)
    print(f"  Current branch : {common.DEVELOP_BRANCH}", flush=True)
    print(f"  GitHub remote  : {'configured' if github_ok else 'not configured'}", flush=True)
    print(f"  Run `npm run dev` to start development.", flush=True)
    print(f"{'=' * 50}\n", flush=True)


if __name__ == "__main__":
    main()
