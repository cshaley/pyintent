"""The ``@spec`` decorator and its data model.

``@spec`` attaches a :class:`PyIntentSpec` to the target as ``__pyintent_spec__``
and returns the target **unchanged** — there is zero runtime overhead. All
validation happens eagerly at decoration time so a malformed spec fails on import.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from ._effects import Effect, EffectKind
from ._errors import PyIntentSpecError
from ._parser import Example, parse_example
from ._perf import Perf

SPEC_ATTR = "__pyintent_spec__"

_IMPURE_KINDS = {
    EffectKind.READS,
    EffectKind.WRITES,
    EffectKind.NETWORK,
    EffectKind.IO,
    EffectKind.ASYNC,
}


class SpecLevel(Enum):
    FUNCTION = "function"
    METHOD = "method"
    CLASSMETHOD = "classmethod"
    STATICMETHOD = "staticmethod"
    PROPERTY = "property"
    ABSTRACT = "abstract method"
    CLASS = "class"
    MODULE = "module"
    PACKAGE = "package"


#: Callable levels that accept call-time conditions and examples.
_CALLABLE_LEVELS = {
    SpecLevel.FUNCTION,
    SpecLevel.METHOD,
    SpecLevel.CLASSMETHOD,
    SpecLevel.STATICMETHOD,
    SpecLevel.ABSTRACT,
    SpecLevel.PROPERTY,
}

#: Which kwargs each level accepts (``intent`` is always required, handled apart).
_ALLOWED_FIELDS: dict[SpecLevel, set[str]] = {
    SpecLevel.FUNCTION: {"where", "ensures", "effects", "perf", "ex"},
    SpecLevel.METHOD: {"where", "ensures", "effects", "perf", "ex"},
    SpecLevel.CLASSMETHOD: {"where", "ensures", "effects", "perf", "ex"},
    SpecLevel.STATICMETHOD: {"where", "ensures", "effects", "perf", "ex"},
    SpecLevel.ABSTRACT: {"where", "ensures", "effects", "perf", "ex"},
    SpecLevel.PROPERTY: {"ensures", "effects", "perf", "ex"},
    SpecLevel.CLASS: {"effects", "invariants"},
    SpecLevel.MODULE: {"effects", "invariants"},
    SpecLevel.PACKAGE: {"effects", "invariants", "modules"},
}


@dataclass(frozen=True)
class Invariant:
    """A class/module/package invariant.

    ``is_expr`` is True when the text compiles as a Python expression (and is
    therefore checkable); otherwise it is treated as natural-language docs.
    """

    text: str
    is_expr: bool


@dataclass
class PyIntentSpec:
    level: SpecLevel
    intent: str
    target_name: str
    is_async: bool = False
    where: list[str] = field(default_factory=list)
    ensures: list[str] = field(default_factory=list)
    effects: list[Effect] = field(default_factory=list)
    perf: Perf | None = None
    examples: list[Example] = field(default_factory=list)
    invariants: list[Invariant] = field(default_factory=list)
    modules: list[str] = field(default_factory=list)

    @property
    def declares_pure(self) -> bool:
        return any(e.kind is EffectKind.PURE for e in self.effects)

    @property
    def is_verifiable_pure(self) -> bool:
        """True when property-based testing is safe (no impure declared effects)."""
        return not ({e.kind for e in self.effects} & _IMPURE_KINDS)

    @property
    def thrown_exceptions(self) -> tuple[type[BaseException], ...]:
        result: list[type[BaseException]] = []
        for e in self.effects:
            if e.kind is EffectKind.THROWS:
                result.extend(e.exceptions)
        return tuple(result)


# --------------------------------------------------------------------------- #
# Validation helpers
# --------------------------------------------------------------------------- #
def _require_intent(intent: object) -> str:
    if not isinstance(intent, str) or not intent.strip():
        raise PyIntentSpecError("intent= is required and must be a non-empty string")
    return intent


def _validate_conditions(name: str, conditions: object) -> list[str]:
    if conditions is None:
        return []
    if not isinstance(conditions, (list, tuple)):
        raise PyIntentSpecError(f"{name}= must be a list of strings")
    result: list[str] = []
    for c in conditions:
        if not isinstance(c, str) or not c.strip():
            raise PyIntentSpecError(f"each {name} entry must be a non-empty string, got {c!r}")
        try:
            compile(c, f"<{name}>", "eval")
        except (SyntaxError, ValueError) as e:
            msg = e.msg if isinstance(e, SyntaxError) else str(e)
            raise PyIntentSpecError(
                f"{name} condition {c!r} is not a valid Python expression: {msg}"
            ) from e
        result.append(c)
    return result


def _validate_effects(effects: object) -> list[Effect]:
    if effects is None:
        return []
    if not isinstance(effects, (list, tuple)):
        raise PyIntentSpecError("effects= must be a list of Effect objects")
    for e in effects:
        if not isinstance(e, Effect):
            raise PyIntentSpecError(
                f"effects must be Effect objects (pure, reads(...), writes(...), "
                f"network(...), io, async_, throws(...)); got {e!r}"
            )
    return list(effects)


def _validate_perf(perf: object) -> Perf | None:
    if perf is None:
        return None
    if not isinstance(perf, Perf):
        raise PyIntentSpecError("perf= must be a Perf object, e.g. Perf(time='O(n)')")
    return perf


def _validate_examples(ex: object) -> list[Example]:
    if ex is None:
        return []
    if not isinstance(ex, (list, tuple)):
        raise PyIntentSpecError("ex= must be a list of example strings")
    return [parse_example(e) for e in ex]


def parse_invariant(text: object) -> Invariant:
    if not isinstance(text, str) or not text.strip():
        raise PyIntentSpecError("each invariant must be a non-empty string")
    try:
        compile(text, "<invariant>", "eval")
        is_expr = True
    except SyntaxError:
        is_expr = False
    return Invariant(text=text, is_expr=is_expr)


def _validate_invariants(invariants: object) -> list[Invariant]:
    if invariants is None:
        return []
    if not isinstance(invariants, (list, tuple)):
        raise PyIntentSpecError("invariants= must be a list of strings")
    return [parse_invariant(i) for i in invariants]


def _reject_disallowed(level: SpecLevel, provided: dict[str, Any]) -> None:
    allowed = _ALLOWED_FIELDS[level]
    for name, value in provided.items():
        if value and name not in allowed:
            allowed_list = ", ".join(sorted(allowed)) or "(none)"
            raise PyIntentSpecError(
                f"{name}= is not valid on a {level.value} spec. "
                f"Allowed fields: intent, {allowed_list}."
            )


# --------------------------------------------------------------------------- #
# Target introspection
# --------------------------------------------------------------------------- #
def _underlying(target: Any) -> Any:
    if isinstance(target, (classmethod, staticmethod)):
        return target.__func__
    if isinstance(target, property):
        return target.fget
    return target


def _detect_level(target: Any) -> SpecLevel:
    if isinstance(target, classmethod):
        return SpecLevel.CLASSMETHOD
    if isinstance(target, staticmethod):
        return SpecLevel.STATICMETHOD
    if isinstance(target, property):
        return SpecLevel.PROPERTY
    if isinstance(target, type):
        return SpecLevel.CLASS
    if getattr(target, "__isabstractmethod__", False):
        return SpecLevel.ABSTRACT
    if inspect.isfunction(target):
        qualname = getattr(target, "__qualname__", "")
        if "." in qualname:
            parent = qualname.rsplit(".", 1)[0]
            if not parent.endswith("<locals>"):
                return SpecLevel.METHOD
        return SpecLevel.FUNCTION
    raise PyIntentSpecError(
        f"@spec can only decorate functions, methods, or classes; got {target!r}"
    )


def _target_name(target: Any, underlying: Any) -> str:
    if isinstance(target, type):
        return target.__qualname__
    name = getattr(underlying, "__qualname__", None) or getattr(underlying, "__name__", None)
    return name or repr(target)


def _attach(target: Any, underlying: Any, ps: PyIntentSpec) -> None:
    holder = underlying if underlying is not None else target
    try:
        setattr(holder, SPEC_ATTR, ps)
    except (AttributeError, TypeError) as e:  # pragma: no cover
        raise PyIntentSpecError(
            f"could not attach spec to {ps.target_name}: {e}"
        ) from e


# --------------------------------------------------------------------------- #
# The decorator
# --------------------------------------------------------------------------- #
def spec(
    *,
    intent: str,
    where: list[str] | None = None,
    ensures: list[str] | None = None,
    effects: list[Effect] | None = None,
    perf: Perf | None = None,
    ex: list[str] | None = None,
    invariants: list[str] | None = None,
) -> Callable[[Any], Any]:
    """Attach an intent specification to a function, method, or class.

    ``@spec`` must be the **outermost** decorator. It returns the target
    **unchanged** — there is zero runtime overhead. All validation happens
    eagerly at decoration time so a malformed spec fails on import.

    Parameters
    ----------
    intent:
        Required. One-line description of what the target does and why.
    where:
        Preconditions — Python expression strings evaluated over the input
        parameters.  Example: ``["n >= 0", "isinstance(n, int)"]``.
    ensures:
        Postconditions — Python expression strings evaluated over input
        parameters and ``result`` (the return value).
        Example: ``["result >= 0", "result == abs(x)"]``.
    effects:
        Declared side-effects.  Use the helpers: ``pure``, ``reads(...)``,
        ``writes(...)``, ``network(...)``, ``io``, ``async_``,
        ``throws(...)``.  Example: ``[reads("db"), throws(NotFoundError)]``.
    perf:
        Advisory complexity declaration.  Example: ``Perf(time="O(n log n)")``.
        Recorded but not measured in v0.1.
    ex:
        Runnable examples in ``"(args) -> expected"`` format.
        Example: ``["(1, 2) -> 3", "(0,) -> raises ValueError", "() -> _"]``.
        Values are evaluated in the target module's global namespace.
    invariants:
        Class/module-level invariants (plain text or Python expressions).
        Valid only on class, module, and package specs.

    Returns
    -------
    Callable[[Any], Any]
        A decorator that attaches the spec and returns the target unchanged.

    Raises
    ------
    PyIntentSpecError
        If ``intent`` is empty, any expression is syntactically invalid, an
        unsupported field is used for the target level, or an ``ex`` entry
        is malformed.

    See Also
    --------
    ``pyintent prompt`` : print the full spec-authoring reference guide.
    ``get_spec``        : retrieve a spec attached to a target.
    """
    intent = _require_intent(intent)

    def decorate(target: Any) -> Any:
        level = _detect_level(target)
        underlying = _underlying(target)
        if underlying is None:
            raise PyIntentSpecError(
                "@spec on a property requires a getter (the property has no fget)"
            )

        _reject_disallowed(
            level,
            {
                "where": where,
                "ensures": ensures,
                "perf": perf,
                "ex": ex,
                "invariants": invariants,
            },
        )

        is_async = bool(
            inspect.iscoroutinefunction(underlying)
            or inspect.isasyncgenfunction(underlying)
        )

        ps = PyIntentSpec(
            level=level,
            intent=intent,
            target_name=_target_name(target, underlying),
            is_async=is_async,
            where=_validate_conditions("where", where),
            ensures=_validate_conditions("ensures", ensures),
            effects=_validate_effects(effects),
            perf=_validate_perf(perf),
            examples=_validate_examples(ex),
            invariants=_validate_invariants(invariants),
        )
        _attach(target, underlying, ps)
        return target

    return decorate


def get_spec(obj: Any) -> PyIntentSpec | None:
    """Return the :class:`PyIntentSpec` attached to ``obj``, or ``None``.

    Works for functions, methods, classmethods, staticmethods, properties,
    and classes decorated with :func:`spec`.

    Parameters
    ----------
    obj:
        Any Python object that may have a spec attached.

    Returns
    -------
    PyIntentSpec | None
        The attached spec, or ``None`` if ``obj`` was not decorated with
        ``@spec``.
    """
    underlying = _underlying(obj)
    return getattr(underlying, SPEC_ATTR, None)
