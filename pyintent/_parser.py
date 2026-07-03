"""Parser for ``ex`` example strings.

Grammar (informal)::

    example  := args "->" expected
    args     := "(" python-tuple ")"          # literal tuple; () means no args
    expected := "_"                            # returns anything, raises nothing
              | "raises" dotted-name           # must raise this exception type
              | python-expression              # must == this value

The *format* is validated eagerly at decoration time (so a malformed ``ex``
fails at import). The actual values are evaluated lazily at verification time
against the target's module globals, so domain objects and enums resolve
correctly.

For methods, ``ex`` tuples exclude ``self`` / ``cls``. For properties, the
input tuple is empty: ``"() -> value"``.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any, Mapping

from ._errors import PyIntentSpecError


class _Wildcard:
    __slots__ = ()

    def __repr__(self) -> str:
        return "_"


#: Sentinel: the call must return *something* without raising.
WILDCARD = _Wildcard()


@dataclass(frozen=True)
class Raises:
    """Expected outcome: the call must raise ``exc_name``."""

    exc_name: str

    def resolve(self, globalns: Mapping[str, Any]) -> type[BaseException]:
        try:
            exc = eval(self.exc_name, dict(globalns))  # noqa: S307 - dev-authored
        except Exception as e:  # pragma: no cover - surfaced to user
            raise PyIntentSpecError(
                f"could not resolve exception {self.exc_name!r} in example: {e}"
            ) from e
        if not (isinstance(exc, type) and issubclass(exc, BaseException)):
            raise PyIntentSpecError(
                f"example 'raises {self.exc_name}' does not name an exception type"
            )
        return exc


@dataclass(frozen=True)
class ReturnsValue:
    """Expected outcome: the call must return a value equal to ``value_src``."""

    value_src: str

    def resolve(self, globalns: Mapping[str, Any]) -> Any:
        try:
            return eval(self.value_src, dict(globalns))  # noqa: S307 - dev-authored
        except Exception as e:  # pragma: no cover - surfaced to user
            raise PyIntentSpecError(
                f"could not evaluate expected value {self.value_src!r}: {e}"
            ) from e


Expected = _Wildcard | Raises | ReturnsValue


@dataclass(frozen=True)
class Example:
    """A single parsed ``ex`` case."""

    raw: str
    args_src: str
    expected: Expected

    def eval_args(self, globalns: Mapping[str, Any]) -> tuple[Any, ...]:
        try:
            value = eval(self.args_src, dict(globalns))  # noqa: S307 - dev-authored
        except Exception as e:  # pragma: no cover - surfaced to user
            raise PyIntentSpecError(
                f"could not evaluate example args {self.args_src!r}: {e}"
            ) from e
        if not isinstance(value, tuple):
            raise PyIntentSpecError(
                f"example args must evaluate to a tuple, got {type(value).__name__}"
            )
        return value


def _split_on_arrow(text: str) -> tuple[str, str]:
    """Split on the first top-level ``->`` outside of strings and brackets."""
    depth = 0
    quote: str | None = None
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if quote is not None:
            if c == "\\":
                i += 2
                continue
            if c == quote:
                quote = None
            i += 1
            continue
        if c in "\"'":
            quote = c
        elif c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif c == "-" and depth == 0 and i + 1 < n and text[i + 1] == ">":
            return text[:i], text[i + 2 :]
        i += 1
    raise PyIntentSpecError(
        f"example {text!r} is missing the '->' separator "
        f"(expected '(args) -> result')"
    )


def _validate_args_tuple(args_src: str, raw: str) -> str:
    args_src = args_src.strip()
    if not args_src:
        raise PyIntentSpecError(
            f"example {raw!r} has no argument tuple before '->' "
            f"(use '()' for no arguments)"
        )
    try:
        node = ast.parse(args_src, mode="eval")
    except (SyntaxError, ValueError) as e:
        msg = e.msg if isinstance(e, SyntaxError) else str(e)
        raise PyIntentSpecError(
            f"example args {args_src!r} are not valid Python: {msg}"
        ) from e
    if not isinstance(node.body, ast.Tuple):
        raise PyIntentSpecError(
            f"example args must be a tuple, got {args_src!r}. "
            f"For a single argument add a trailing comma, e.g. '(42,) -> ...'."
        )
    return args_src


def _parse_expected(expected_src: str, raw: str) -> Expected:
    expected_src = expected_src.strip()
    if not expected_src:
        raise PyIntentSpecError(
            f"example {raw!r} has nothing after '->' "
            f"(use '_' for 'returns without raising')"
        )
    if expected_src == "_":
        return WILDCARD
    if expected_src == "raises" or expected_src.startswith("raises "):
        exc_name = expected_src[len("raises") :].strip()
        if not exc_name:
            raise PyIntentSpecError(
                f"example {raw!r}: 'raises' must be followed by an exception type"
            )
        try:
            name_node = ast.parse(exc_name, mode="eval")
        except (SyntaxError, ValueError) as e:
            msg = e.msg if isinstance(e, SyntaxError) else str(e)
            raise PyIntentSpecError(
                f"example {raw!r}: invalid exception name {exc_name!r}: {msg}"
            ) from e
        if not isinstance(name_node.body, (ast.Name, ast.Attribute)):
            raise PyIntentSpecError(
                f"example {raw!r}: 'raises' must name an exception type, got {exc_name!r}"
            )
        return Raises(exc_name)
    try:
        ast.parse(expected_src, mode="eval")
    except (SyntaxError, ValueError) as e:
        msg = e.msg if isinstance(e, SyntaxError) else str(e)
        raise PyIntentSpecError(
            f"example {raw!r}: expected value {expected_src!r} is not valid Python: {msg}"
        ) from e
    return ReturnsValue(expected_src)


def parse_example(raw: str) -> Example:
    """Parse and format-validate one ``ex`` string. Raises ``PyIntentSpecError``."""
    if not isinstance(raw, str):
        raise PyIntentSpecError(
            f"each ex entry must be a string like '(1, 2) -> 3', got {raw!r}"
        )
    left, right = _split_on_arrow(raw)
    args_src = _validate_args_tuple(left, raw)
    expected = _parse_expected(right, raw)
    return Example(raw=raw, args_src=args_src, expected=expected)
