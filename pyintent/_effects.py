"""Effect declarations for a spec.

An effect describes how a function interacts with the world. Effects are plain
immutable value objects, validated at construction time. In v0.1 only ``pure``,
``async_`` and ``throws`` are *verified* (see ``verifier/effects.py``); the rest
are declaration-only and recorded for documentation and future versions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ._errors import PyIntentSpecError


class EffectKind(Enum):
    PURE = "pure"
    READS = "reads"
    WRITES = "writes"
    NETWORK = "network"
    IO = "io"
    ASYNC = "async"
    THROWS = "throws"


@dataclass(frozen=True)
class Effect:
    """A single declared effect. Construct via the helpers below, not directly."""

    kind: EffectKind
    resource: str | None = None
    exceptions: tuple[type[BaseException], ...] = field(default=())

    def __repr__(self) -> str:
        if self.kind in (EffectKind.READS, EffectKind.WRITES, EffectKind.NETWORK):
            return f"{self.kind.value}({self.resource!r})"
        if self.kind is EffectKind.THROWS:
            names = ", ".join(e.__name__ for e in self.exceptions)
            return f"throws({names})"
        return self.kind.value


def _require_resource(fn_name: str, resource: object) -> str:
    if not isinstance(resource, str) or not resource.strip():
        raise PyIntentSpecError(
            f"{fn_name}() requires a non-empty string naming the resource, "
            f"e.g. {fn_name}('db'); got {resource!r}"
        )
    return resource


#: The function has no observable side effects and is deterministic.
#: **Actively verified** by the effects verifier via AST analysis.
#: Calls to impure builtins (``print``, ``open``, ``input``, …) or modules
#: (``os``, ``sys``, ``random``, ``requests``, …) and ``global``/``nonlocal``
#: writes are reported as violations.
pure = Effect(EffectKind.PURE)

#: The function performs filesystem / stdout / stdin style I/O.
#: Declaration-only in v0.1 — recorded for documentation, not yet enforced.
io = Effect(EffectKind.IO)

#: The function is a coroutine defined with ``async def``.
#: **Actively verified**: the effects verifier checks that the function really
#: is a coroutine function.
async_ = Effect(EffectKind.ASYNC)


def reads(resource: str) -> Effect:
    """Declare that the function reads from a named resource.

    This effect is **declaration-only** in v0.1 — it is recorded for
    documentation but not actively verified.

    Parameters
    ----------
    resource:
        Non-empty string naming the resource, e.g. ``"db"``, ``"config"``.

    Examples
    --------
    ::

        @spec(intent="fetch user", effects=[reads("db")])
        def get_user(user_id: int) -> User: ...
    """
    return Effect(EffectKind.READS, resource=_require_resource("reads", resource))


def writes(resource: str) -> Effect:
    """Declare that the function writes to a named resource.

    This effect is **declaration-only** in v0.1 — it is recorded for
    documentation but not actively verified.

    Parameters
    ----------
    resource:
        Non-empty string naming the resource, e.g. ``"db"``, ``"cache"``.

    Examples
    --------
    ::

        @spec(intent="save user", effects=[writes("db")])
        def save_user(user: User) -> None: ...
    """
    return Effect(EffectKind.WRITES, resource=_require_resource("writes", resource))


def network(service: str) -> Effect:
    """Declare that the function calls an external network service.

    This effect is **declaration-only** in v0.1 — it is recorded for
    documentation but not actively verified.

    Parameters
    ----------
    service:
        Non-empty string naming the service, e.g. ``"stripe"``, ``"sendgrid"``.

    Examples
    --------
    ::

        @spec(intent="charge card", effects=[network("stripe")])
        def charge(amount: int) -> str: ...
    """
    return Effect(EffectKind.NETWORK, resource=_require_resource("network", service))


def throws(*exceptions: type[BaseException]) -> Effect:
    """Declare the exception types the function may raise as part of its contract.

    **Actively verified** by the effects verifier: the AST is checked to ensure
    every explicitly raised exception type is listed here.

    Parameters
    ----------
    *exceptions:
        One or more exception classes (subclasses of :class:`BaseException`).

    Raises
    ------
    PyIntentSpecError
        If no arguments are given, or any argument is not an exception class.

    Examples
    --------
    ::

        @spec(intent="parse int", effects=[throws(ValueError)])
        def parse_int(s: str) -> int:
            return int(s)
    """
    if not exceptions:
        raise PyIntentSpecError(
            "throws() requires at least one exception type, e.g. throws(ValueError)"
        )
    for exc in exceptions:
        if not (isinstance(exc, type) and issubclass(exc, BaseException)):
            raise PyIntentSpecError(
                f"throws() arguments must be exception classes, got {exc!r}"
            )
    return Effect(EffectKind.THROWS, exceptions=tuple(exceptions))
