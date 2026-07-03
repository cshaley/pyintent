"""Types verifier — run mypy over a file (optional).

Runs once per file, not per function. If mypy is not installed the check is
skipped (not failed), so mypy stays an optional dependency.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys

from ._result import CheckResult, Status

_MYPY_AVAILABLE: bool | None = None


def _mypy_available() -> bool:
    global _MYPY_AVAILABLE
    if _MYPY_AVAILABLE is None:
        _MYPY_AVAILABLE = importlib.util.find_spec("mypy") is not None
    return _MYPY_AVAILABLE


def verify_types(filename: str) -> list[CheckResult]:
    try:
        rel = os.path.relpath(filename)
        target = rel if len(rel) < len(filename) else filename
    except ValueError:  # pragma: no cover - different drive on Windows
        target = filename
    if not _mypy_available():
        return [CheckResult("types", target, Status.SKIPPED,
                            summary="mypy not installed (pip install pyintent[types])")]
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "mypy",
             "--no-error-summary", "--hide-error-context",
             "--no-color-output", "--follow-imports=silent",
             "--ignore-missing-imports", filename],
            capture_output=True, text=True, timeout=120,
        )
    except subprocess.TimeoutExpired:
        return [CheckResult("types", target, Status.ERROR, summary="mypy timed out")]
    except Exception as e:  # noqa: BLE001
        return [CheckResult("types", target, Status.ERROR, summary=f"mypy failed to run: {e}")]

    out = (proc.stdout + proc.stderr).strip()
    if proc.returncode == 0:
        return [CheckResult("types", target, Status.PASS, summary="mypy clean")]
    if proc.returncode == 1:
        return [CheckResult("types", target, Status.FAIL,
                            summary="mypy reported type errors", detail=out)]
    return [CheckResult("types", target, Status.ERROR,
                        summary="mypy usage error", detail=out)]
