"""Properties verifier — hypothesis-generate inputs and check ``ensures``.

Only runs for pure, runnable callables (module functions / staticmethods /
classmethods with no impure declared effects). Effectful callables, instance
methods, and callables whose parameter types can't be mapped to a strategy are
skipped with a reason.
"""

from __future__ import annotations

import builtins as _builtins
import inspect
import types
import typing
from typing import Any, get_args, get_origin

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from hypothesis.errors import UnsatisfiedAssumption

from .._spec import SpecLevel
from .._discovery import SpecTarget
from ._result import CheckResult, Status

_BUILTINS_DICT = vars(_builtins)

_RUNNABLE = {SpecLevel.FUNCTION, SpecLevel.STATICMETHOD, SpecLevel.CLASSMETHOD}
_MAX_EXAMPLES = 50


class _Unsupported(Exception):
    def __init__(self, tp: Any) -> None:
        super().__init__(str(tp))
        self.tp = tp


def _strategy_for(tp: Any):
    if tp is int:
        return st.integers()
    if tp is bool:
        return st.booleans()
    if tp is float:
        return st.floats(allow_nan=False, allow_infinity=False)
    if tp is str:
        return st.text()
    if tp is bytes:
        return st.binary()
    if tp is type(None):
        return st.none()

    origin = get_origin(tp)
    args = get_args(tp)
    if origin is list:
        return st.lists(_strategy_for(args[0]) if args else st.integers())
    if origin is set:
        return st.sets(_strategy_for(args[0]) if args else st.integers())
    if origin is frozenset:
        return st.frozensets(_strategy_for(args[0]) if args else st.integers())
    if origin is tuple:
        if len(args) == 2 and args[1] is Ellipsis:
            return st.lists(_strategy_for(args[0])).map(tuple)
        return st.tuples(*[_strategy_for(a) for a in args])
    if origin is dict:
        k = _strategy_for(args[0]) if args else st.text()
        v = _strategy_for(args[1]) if len(args) > 1 else st.integers()
        return st.dictionaries(k, v)
    if origin is typing.Union or origin is types.UnionType:
        return st.one_of(*[_strategy_for(a) for a in args])
    raise _Unsupported(tp)


def _skip(name: str, reason: str) -> list[CheckResult]:
    return [CheckResult("properties", name, Status.SKIPPED, summary=reason)]


def verify_properties(target: SpecTarget) -> list[CheckResult]:
    sp = target.spec
    name = sp.target_name

    if not sp.ensures:
        return []
    if sp.level not in _RUNNABLE or target.invoke is None:
        return _skip(name, f"{sp.level.value} property tests need an instance (v0.2)")
    if not sp.is_verifiable_pure:
        return _skip(name, "effectful — property testing only runs on pure functions")
    if sp.is_async:
        return _skip(name, "async property testing deferred to v0.2")

    fn = target.invoke
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return _skip(name, "could not introspect signature")

    params = [
        p for p in sig.parameters.values()
        if p.name not in ("self", "cls")
    ]
    for p in params:
        if p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
            return _skip(name, "*args/**kwargs not supported for property testing")
        if p.kind is p.POSITIONAL_ONLY:
            return _skip(name, "positional-only parameters not supported")

    try:
        hints = typing.get_type_hints(fn)
    except Exception:
        return _skip(name, "could not resolve type hints")

    strategies = {}
    for p in params:
        if p.name not in hints:
            return _skip(name, f"parameter '{p.name}' has no type annotation")
        try:
            strategies[p.name] = _strategy_for(hints[p.name])
        except _Unsupported as u:
            return _skip(name, f"no strategy for type {u.tp!r} (parameter '{p.name}')")

    return [_run(target, strategies)]


def _run(target: SpecTarget, strategies: dict) -> CheckResult:
    sp = target.spec
    name = sp.target_name
    fn = target.invoke
    assert fn is not None  # guaranteed by verify_properties
    globalns = target.globalns
    failure: dict[str, Any] = {}

    arg_strategy = st.fixed_dictionaries(strategies) if strategies else st.just({})

    @settings(max_examples=_MAX_EXAMPLES, deadline=None,
              suppress_health_check=list(HealthCheck))
    @given(kwargs=arg_strategy)
    def run(kwargs: dict) -> None:
        for cond in sp.where:
            try:
                ok = bool(eval(cond, {"__builtins__": _BUILTINS_DICT, **globalns, **kwargs}))
            except Exception:
                ok = False
            if not ok:
                raise UnsatisfiedAssumption()
        try:
            result = fn(**kwargs)
        except Exception as exc:
            failure.update(kwargs=kwargs, result="<raised>", cond="(function call)", error=exc)
            raise AssertionError(
                f"function raised {type(exc).__name__}: {exc}"
            ) from exc
        env = {**kwargs, "result": result}
        for cond in sp.ensures:
            try:
                holds = bool(eval(cond, {"__builtins__": _BUILTINS_DICT, **globalns, **env}))
            except Exception as e:
                failure.update(kwargs=kwargs, result=result, cond=cond, error=e)
                raise AssertionError(
                    f"ensures {cond!r} raised {type(e).__name__}: {e}"
                ) from e
            if not holds:
                failure.update(kwargs=kwargs, result=result, cond=cond, error=None)
                raise AssertionError(f"ensures {cond!r} is False")

    try:
        run()
    except AssertionError:
        kwargs = failure.get("kwargs", {})
        call = ", ".join(f"{k}={v!r}" for k, v in kwargs.items())
        cond = failure.get("cond", "?")
        result = failure.get("result", "?")
        err = failure.get("error")
        if err:
            line = (
                f"function raised {type(err).__name__}: {err}"
                if cond == "(function call)"
                else f"ensures {cond!r} raised {type(err).__name__}: {err}"
            )
        else:
            line = f"ensures {cond!r} is False"
        detail = (
            f"{name}({call})\n"
            f"  returned: {result!r}\n"
            f"  {line}"
        )
        return CheckResult(
            "properties", name, Status.FAIL,
            summary=f"falsified: {line}", detail=detail,
        )
    except Exception as e:  # noqa: BLE001
        return CheckResult(
            "properties", name, Status.ERROR,
            summary=f"property run errored: {e}", detail=str(e),
        )
    return CheckResult(
        "properties", name, Status.PASS,
        summary=f"{len(sp.ensures)} ensures held over {_MAX_EXAMPLES} examples",
    )
