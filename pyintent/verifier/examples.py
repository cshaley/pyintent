"""Examples verifier — run every ``ex`` case against the real implementation.

Runnable in v0.1 for module-level functions, ``@staticmethod`` and
``@classmethod``. Instance methods and properties need an instance and are
skipped with a clear reason (planned for v0.2).
"""

from __future__ import annotations

import asyncio
from typing import Any

from .._errors import PyIntentSpecError
from .._parser import Example, Raises, ReturnsValue, _Wildcard
from .._spec import SpecLevel
from .._discovery import SpecTarget
from ._result import CheckResult, Status

_RUNNABLE = {SpecLevel.FUNCTION, SpecLevel.STATICMETHOD, SpecLevel.CLASSMETHOD}


def _safe_eq(a: object, b: object) -> bool:
    try:
        return bool(a == b)
    except Exception:
        return repr(a) == repr(b)


def _call(fn: Any, args: tuple, is_async: bool) -> Any:
    if is_async:
        return asyncio.run(fn(*args))
    return fn(*args)


def _fmt_args(args: tuple) -> str:
    inner = ", ".join(repr(a) for a in args)
    if len(args) == 1:
        inner += ","
    return f"({inner})"


def verify_example_case(target: SpecTarget, ex: Example) -> CheckResult:
    """Run exactly one example case (the function executes once)."""
    sp = target.spec
    if sp.level not in _RUNNABLE or target.invoke is None:
        reason = f"{sp.level.value} examples require an instance (v0.2)"
        return CheckResult("examples", sp.target_name, Status.SKIPPED, summary=reason, label=ex.raw)
    return _run_one(target, ex)


def verify_examples(target: SpecTarget) -> list[CheckResult]:
    if not target.spec.examples:
        return []
    return [verify_example_case(target, ex) for ex in target.spec.examples]


def _run_one(target: SpecTarget, ex: Example) -> CheckResult:
    sp = target.spec
    name = sp.target_name
    globalns = target.globalns
    try:
        args = ex.eval_args(globalns)
    except PyIntentSpecError as e:
        return CheckResult("examples", name, Status.ERROR, summary=str(e), label=ex.raw)

    try:
        outcome = _call(target.invoke, args, sp.is_async)
    except BaseException as exc:  # noqa: BLE001 - we classify it below
        return _check_raised(name, ex, exc, args, globalns)
    return _check_returned(name, ex, outcome, args, globalns)


def _check_raised(name, ex: Example, exc, args, globalns) -> CheckResult:
    if isinstance(ex.expected, Raises):
        try:
            want = ex.expected.resolve(globalns)
        except PyIntentSpecError as e:
            return CheckResult("examples", name, Status.ERROR, summary=str(e), label=ex.raw)
        if isinstance(exc, want):
            return CheckResult("examples", name, Status.PASS, label=ex.raw)
        detail = (
            f"{name}{_fmt_args(args)}\n"
            f"  expected: raises {ex.expected.exc_name}\n"
            f"  actual:   raised {type(exc).__name__}: {exc}"
        )
        return CheckResult(
            "examples", name, Status.FAIL,
            summary=f"raised {type(exc).__name__}, expected {ex.expected.exc_name}",
            detail=detail, label=ex.raw,
        )

    expected_desc = (
        "_ (returns without raising)"
        if isinstance(ex.expected, _Wildcard)
        else ex.expected.value_src
    )
    detail = (
        f"{name}{_fmt_args(args)}\n"
        f"  expected: {expected_desc}\n"
        f"  actual:   raised {type(exc).__name__}: {exc}"
    )
    return CheckResult(
        "examples", name, Status.FAIL,
        summary=f"unexpected {type(exc).__name__}: {exc}",
        detail=detail, label=ex.raw,
    )


def _check_returned(name, ex: Example, outcome, args, globalns) -> CheckResult:
    if isinstance(ex.expected, _Wildcard):
        return CheckResult("examples", name, Status.PASS, label=ex.raw)

    if isinstance(ex.expected, Raises):
        detail = (
            f"{name}{_fmt_args(args)}\n"
            f"  expected: raises {ex.expected.exc_name}\n"
            f"  actual:   returned {outcome!r}"
        )
        return CheckResult(
            "examples", name, Status.FAIL,
            summary=f"returned {outcome!r}, expected raise {ex.expected.exc_name}",
            detail=detail, label=ex.raw,
        )

    assert isinstance(ex.expected, ReturnsValue)
    try:
        expected_value = ex.expected.resolve(globalns)
    except PyIntentSpecError as e:
        return CheckResult("examples", name, Status.ERROR, summary=str(e), label=ex.raw)

    if _safe_eq(outcome, expected_value):
        return CheckResult("examples", name, Status.PASS, label=ex.raw)
    detail = (
        f"{name}{_fmt_args(args)}\n"
        f"  expected: {expected_value!r}\n"
        f"  actual:   {outcome!r}"
    )
    return CheckResult(
        "examples", name, Status.FAIL,
        summary=f"returned {outcome!r}, expected {expected_value!r}",
        detail=detail, label=ex.raw,
    )
