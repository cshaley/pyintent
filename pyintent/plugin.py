"""pytest plugin — surface pyintent checks as ordinary pytest items.

Registered via the ``pytest11`` entry point but **opt-in**: it does nothing
unless you enable it with ``--pyintent`` on the command line or ``pyintent =
true`` under ``[tool.pytest.ini_options]`` (or ``[pytest]``). This keeps a mere
install of pyintent from changing how unrelated ``pytest`` runs behave —
without the opt-in, pyintent never imports your application files.

When enabled, for every non-test ``.py`` file that contains specs it collects:

* one item per ``ex`` case,
* one item per function with ``ensures`` (property test),
* one item per file for the type check.

Effects/perf are intentionally **not** pytest items (run ``pyintent verify``
for those). Test files are left to pytest's own collector to avoid importing a
module twice.
"""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path

import pytest

from ._discovery import discover_in_module
from ._loader import import_file
from .verifier._result import Status
from .verifier.examples import verify_example_case
from .verifier.properties import verify_properties
from .verifier.types import verify_types


def pytest_addoption(parser) -> None:
    group = parser.getgroup("pyintent")
    group.addoption(
        "--pyintent", action="store_true", default=False,
        help="Collect pyintent @spec checks (examples/properties/types) as pytest items.",
    )
    parser.addini(
        "pyintent", "Collect pyintent @spec checks as pytest items.",
        type="bool", default=False,
    )


def _enabled(config) -> bool:
    try:
        if config.getoption("--pyintent"):
            return True
    except (ValueError, KeyError):
        pass
    return bool(config.getini("pyintent"))


def _pkg_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def _looks_like_specs(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    if "pyintent" not in text:
        return False
    return "@spec(" in text or "module_spec(" in text or "package_spec(" in text


def pytest_collect_file(file_path: Path, parent):  # type: ignore[override]
    if not _enabled(parent.config):
        return None
    if file_path.suffix != ".py":
        return None

    # Never collect pyintent's own source or installed third-party code.
    resolved = str(file_path.resolve())
    if resolved.startswith(_pkg_dir()) or "site-packages" in resolved:
        return None

    # Leave files matching pytest's own python_files patterns to pytest.
    patterns = parent.config.getini("python_files") or ["test_*.py", "*_test.py"]
    if any(fnmatch.fnmatch(file_path.name, pat) for pat in patterns):
        return None

    if not _looks_like_specs(file_path):
        return None

    return PyIntentFile.from_parent(parent, path=file_path)


class _CheckFailure(Exception):
    """Carries a failing/erroring CheckResult to repr_failure."""

    def __init__(self, result) -> None:
        super().__init__(result.summary)
        self.result = result


class PyIntentFile(pytest.File):
    def collect(self):
        try:
            module = import_file(self.path)
        except Exception as exc:  # noqa: BLE001
            raise self.CollectError(f"pyintent: failed to import {self.path}: {exc}") from exc

        targets = discover_in_module(module)
        for t in targets:
            sp = t.spec
            base = sp.target_name
            for ex in sp.examples:
                yield PyIntentItem.from_parent(
                    self, name=f"{base}::ex[{ex.raw}]",
                    thunk=lambda t=t, ex=ex: verify_example_case(t, ex),
                )
            if sp.ensures:
                yield PyIntentItem.from_parent(
                    self, name=f"{base}::properties",
                    thunk=lambda t=t: _first(verify_properties(t)),
                )

        yield PyIntentItem.from_parent(
            self, name=f"{self.path.stem}::types",
            thunk=lambda: _first(verify_types(str(self.path))),
        )


def _first(results):
    from .verifier._result import CheckResult
    if results:
        return results[0]
    return CheckResult("", "", Status.SKIPPED, summary="nothing to check")


class PyIntentItem(pytest.Item):
    def __init__(self, *, name, parent, thunk):
        super().__init__(name, parent)
        self._thunk = thunk

    def runtest(self) -> None:
        result = self._thunk()
        if result.status is Status.SKIPPED:
            pytest.skip(result.summary or "skipped")
        if result.status in (Status.FAIL, Status.ERROR):
            raise _CheckFailure(result)

    def repr_failure(self, excinfo, style=None):  # type: ignore[override]
        if isinstance(excinfo.value, _CheckFailure):
            r = excinfo.value.result
            return r.detail or r.summary or "pyintent check failed"
        return super().repr_failure(excinfo)

    def reportinfo(self):
        return self.path, 0, self.name
