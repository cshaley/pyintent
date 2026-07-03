"""pyintent — verify that implementations satisfy intent specifications.

A pure verifier: it checks, it never generates. See ``pyintent prompt`` for the
full spec-authoring reference.
"""

from __future__ import annotations

from ._effects import (
    Effect,
    EffectKind,
    async_,
    io,
    network,
    pure,
    reads,
    throws,
    writes,
)
from ._errors import PyIntentError, PyIntentSpecError
from ._module_spec import module_spec, package_spec
from ._parser import Example
from ._perf import Perf
from ._spec import (
    Invariant,
    PyIntentSpec,
    SpecLevel,
    get_spec,
    spec,
)

__version__ = "0.1.0"

__all__ = [
    "spec",
    "get_spec",
    "module_spec",
    "package_spec",
    "Perf",
    "pure",
    "reads",
    "writes",
    "network",
    "io",
    "async_",
    "throws",
    "Effect",
    "EffectKind",
    "PyIntentSpec",
    "SpecLevel",
    "Invariant",
    "Example",
    "PyIntentError",
    "PyIntentSpecError",
    "__version__",
]
