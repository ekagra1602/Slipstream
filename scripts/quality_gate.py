#!/usr/bin/env python3
"""Repository launch-quality gate.

Runs blocking syntax, lint, and test checks for the launch surface:
  - Python syntax compile checks
  - JavaScript syntax checks
  - Ruff lint checks
  - ESLint + Prettier checks
  - Pytest blocking subset
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent

PYTHON_DIRS = ("db", "dombot", "frontend", "scripts", "tests")
PYTEST_TARGETS = ("tests/test_db.py", "tests/test_domain_utils.py")
JS_LINT_SCRIPT = "lint:js"
JS_SYNTAX_SCRIPT = "check:js-syntax"
FORMAT_CHECK_SCRIPT = "format:check"


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def ok(message: str) -> None:
    print(f"[PASS] {message}")


def fail(message: str) -> None:
    print(f"[FAIL] {message}")


def list_python_files() -> list[str]:
    files: list[str] = []
    for directory in PYTHON_DIRS:
        root = REPO_ROOT / directory
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            files.append(str(path.relative_to(REPO_ROOT)))
    return sorted(files)


def run_command(name: str, cmd: list[str]) -> bool:
    print(f"$ {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=REPO_ROOT, check=False)
    if proc.returncode == 0:
        ok(name)
        return True
    fail(f"{name} (exit={proc.returncode})")
    return False


def ensure_tool(name: str, executable: str) -> bool:
    if shutil.which(executable):
        ok(f"{name} available")
        return True
    fail(f"{name} is required but not installed")
    return False


def main() -> int:
    failures = 0

    section("Prerequisites")
    if not ensure_tool("npm", "npm"):
        failures += 1

    section("Python syntax")
    py_files = list_python_files()
    if not py_files:
        fail("No Python files found for syntax checks")
        failures += 1
    else:
        if not run_command(
            "Python syntax compile",
            [sys.executable, "-m", "py_compile", *py_files],
        ):
            failures += 1

    section("JavaScript syntax")
    if not run_command("JavaScript syntax", ["npm", "run", JS_SYNTAX_SCRIPT]):
        failures += 1

    section("Python lint")
    if not run_command(
        "Ruff lint",
        [sys.executable, "-m", "ruff", "check", *PYTHON_DIRS],
    ):
        failures += 1

    section("JavaScript lint")
    if not run_command("ESLint", ["npm", "run", JS_LINT_SCRIPT]):
        failures += 1

    section("Formatting")
    if not run_command("Prettier check", ["npm", "run", FORMAT_CHECK_SCRIPT]):
        failures += 1

    section("Pytest")
    if not run_command(
        "Blocking pytest suite",
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-m",
            "not live_db and not ui_dependent",
            *PYTEST_TARGETS,
        ],
    ):
        failures += 1

    section("Summary")
    if failures:
        fail(f"Quality gate failed with {failures} failing step(s)")
        return 1

    ok("All quality checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
