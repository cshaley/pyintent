"""Module- and package-level specs.

Assign the result to ``__pyintent__`` in a module (or a package ``__init__.py``)::

    from pyintent import module_spec, reads

    __pyintent__ = module_spec(
        intent     = "Order persistence and retrieval.",
        invariants = ["every public function validates its inputs"],
        effects    = [reads("db")],
    )
"""

from __future__ import annotations

from ._effects import Effect
from ._errors import PyIntentSpecError
from ._spec import (
    PyIntentSpec,
    SpecLevel,
    _reject_disallowed,
    _require_intent,
    _validate_effects,
    _validate_invariants,
)

MODULE_ATTR = "__pyintent__"


def module_spec(
    *,
    intent: str,
    invariants: list[str] | None = None,
    effects: list[Effect] | None = None,
) -> PyIntentSpec:
    """Build a module-level spec. Assign it to ``__pyintent__``."""
    intent = _require_intent(intent)
    return PyIntentSpec(
        level=SpecLevel.MODULE,
        intent=intent,
        target_name="<module>",
        invariants=_validate_invariants(invariants),
        effects=_validate_effects(effects),
    )


def package_spec(
    *,
    intent: str,
    modules: list[str] | None = None,
    invariants: list[str] | None = None,
    effects: list[Effect] | None = None,
) -> PyIntentSpec:
    """Build a package-level spec. Assign it to ``__pyintent__`` in ``__init__.py``."""
    intent = _require_intent(intent)
    if modules is not None:
        if not isinstance(modules, (list, tuple)) or not all(
            isinstance(m, str) and m.strip() for m in modules
        ):
            raise PyIntentSpecError("modules= must be a list of non-empty module-name strings")
    return PyIntentSpec(
        level=SpecLevel.PACKAGE,
        intent=intent,
        target_name="<package>",
        invariants=_validate_invariants(invariants),
        effects=_validate_effects(effects),
        modules=list(modules) if modules else [],
    )
