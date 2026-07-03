"""Verifier orchestration.

``run_all`` discovers every spec in a module and runs the selected verifiers.
``types`` runs once per source file; the other verifiers run per callable.
"""

from __future__ import annotations

from types import ModuleType

from .._spec import SpecLevel
from .._discovery import SpecTarget, discover_in_module
from ._result import CheckResult, Status
from .effects import verify_effects
from .examples import verify_examples
from .properties import verify_properties
from .types import verify_types

ALL_VERIFIERS = ("examples", "properties", "types", "effects")

#: Levels with no executable verification in v0.1 (specs stored only).
_NON_EXECUTABLE = {SpecLevel.CLASS, SpecLevel.MODULE, SpecLevel.PACKAGE}


def run_targets(targets: list[SpecTarget], which: set[str] | None = None) -> list[CheckResult]:
    which = set(which) if which else set(ALL_VERIFIERS)
    results: list[CheckResult] = []

    for t in targets:
        if t.spec.level in _NON_EXECUTABLE:
            continue
        if "examples" in which:
            results.extend(verify_examples(t))
        if "properties" in which:
            results.extend(verify_properties(t))
        if "effects" in which:
            results.extend(verify_effects(t))

    if "types" in which:
        seen: set[str] = set()
        for t in targets:
            if t.filename and t.filename not in seen:
                seen.add(t.filename)
                results.extend(verify_types(t.filename))

    return results


def run_all(module: ModuleType, which: set[str] | None = None) -> list[CheckResult]:
    return run_targets(discover_in_module(module), which)


__all__ = [
    "ALL_VERIFIERS",
    "CheckResult",
    "Status",
    "SpecTarget",
    "run_all",
    "run_targets",
    "verify_examples",
    "verify_properties",
    "verify_effects",
    "verify_types",
]
