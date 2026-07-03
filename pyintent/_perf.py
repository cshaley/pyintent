"""Performance declaration for a spec.

In v0.1 ``Perf`` is *stored only* — pyintent records the declared complexity but
does not measure or verify it. Measurement is planned for v0.2.
"""

from __future__ import annotations

from ._errors import PyIntentSpecError

_ALLOWED = ("time", "space")


class Perf:
    """Declared algorithmic complexity, e.g. ``Perf(time="O(log n)", space="O(1)")``."""

    __slots__ = ("time", "space")

    def __init__(self, **kwargs: str) -> None:
        unknown = set(kwargs) - set(_ALLOWED)
        if unknown:
            raise PyIntentSpecError(
                f"Perf() got unexpected keyword(s): {', '.join(sorted(unknown))}. "
                f"Allowed: {', '.join(_ALLOWED)}"
            )
        time = kwargs.get("time")
        space = kwargs.get("space")
        if time is None and space is None:
            raise PyIntentSpecError("Perf() requires at least one of time= or space=")
        for name, val in (("time", time), ("space", space)):
            if val is not None and (not isinstance(val, str) or not val.strip()):
                raise PyIntentSpecError(
                    f"Perf {name}= must be a non-empty string, got {val!r}"
                )
        self.time = time
        self.space = space

    def __repr__(self) -> str:
        parts = []
        if self.time is not None:
            parts.append(f"time={self.time!r}")
        if self.space is not None:
            parts.append(f"space={self.space!r}")
        return f"Perf({', '.join(parts)})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Perf):
            return NotImplemented
        return self.time == other.time and self.space == other.space
