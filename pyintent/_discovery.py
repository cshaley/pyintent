"""Find every spec attached to a module's functions, classes, and methods."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from types import ModuleType
from typing import Any

from ._module_spec import MODULE_ATTR
from ._spec import PyIntentSpec, SpecLevel, get_spec


@dataclass
class SpecTarget:
    """A discovered spec plus everything a verifier needs to act on it."""

    qualname: str
    spec: PyIntentSpec
    globalns: dict[str, Any]
    module_name: str
    filename: str | None = None
    invoke: Any | None = None  # the callable to execute, when runnable
    owner: type | None = None  # the owning class, for methods


def discover_in_module(module: ModuleType) -> list[SpecTarget]:
    targets: list[SpecTarget] = []
    globalns = vars(module)
    modname = getattr(module, "__name__", "<module>")
    filename = getattr(module, "__file__", None)

    mod_spec = globalns.get(MODULE_ATTR)
    if isinstance(mod_spec, PyIntentSpec):
        targets.append(
            SpecTarget(
                qualname=modname,
                spec=mod_spec,
                globalns=globalns,
                module_name=modname,
                filename=filename,
            )
        )

    for name, obj in list(globalns.items()):
        if inspect.isfunction(obj):
            sp = get_spec(obj)
            if sp is not None and getattr(obj, "__module__", None) == modname:
                targets.append(
                    SpecTarget(
                        qualname=obj.__qualname__,
                        spec=sp,
                        globalns=globalns,
                        module_name=modname,
                        filename=filename,
                        invoke=obj,
                    )
                )
        elif inspect.isclass(obj) and getattr(obj, "__module__", None) == modname:
            csp = get_spec(obj)
            if csp is not None:
                targets.append(
                    SpecTarget(
                        qualname=obj.__qualname__,
                        spec=csp,
                        globalns=globalns,
                        module_name=modname,
                        filename=filename,
                        owner=obj,
                    )
                )
            targets.extend(_discover_in_class(obj, globalns, modname, filename))

    return targets


def _discover_in_class(
    cls: type, globalns: dict[str, Any], modname: str, filename: str | None
) -> list[SpecTarget]:
    targets: list[SpecTarget] = []
    for name, member in list(vars(cls).items()):
        sp = get_spec(member)
        if sp is None:
            continue
        invoke: Any | None = None
        if sp.level is SpecLevel.CLASSMETHOD:
            invoke = getattr(cls, name)  # bound to cls
        elif sp.level is SpecLevel.STATICMETHOD:
            invoke = member.__func__
        elif sp.level is SpecLevel.PROPERTY:
            invoke = member.fget
        elif sp.level in (SpecLevel.METHOD, SpecLevel.ABSTRACT):
            invoke = member
        targets.append(
            SpecTarget(
                qualname=sp.target_name,
                spec=sp,
                globalns=globalns,
                module_name=modname,
                filename=filename,
                invoke=invoke,
                owner=cls,
            )
        )
    return targets
