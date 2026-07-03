"""Tests for the example-string parser (_parser.py)."""

from __future__ import annotations

import pytest

from pyintent import PyIntentSpecError
from pyintent._parser import (
    Raises,
    ReturnsValue,
    _Wildcard,
    parse_example,
)


def test_parses_args_and_return_value():
    ex = parse_example("(1, 2) -> 3")
    assert isinstance(ex.expected, ReturnsValue)
    assert ex.eval_args({}) == (1, 2)
    assert ex.expected.resolve({}) == 3


def test_no_arg_call():
    ex = parse_example("() -> 42")
    assert ex.eval_args({}) == ()
    assert ex.expected.resolve({}) == 42


def test_single_arg_requires_trailing_comma_ok():
    ex = parse_example("(5,) -> 25")
    assert ex.eval_args({}) == (5,)


def test_single_arg_without_comma_is_rejected():
    with pytest.raises(PyIntentSpecError, match="trailing comma"):
        parse_example("(5) -> 25")


def test_wildcard_expected():
    ex = parse_example("(1,) -> _")
    assert isinstance(ex.expected, _Wildcard)


def test_raises_expected():
    ex = parse_example("(0,) -> raises ValueError")
    assert isinstance(ex.expected, Raises)
    assert ex.expected.exc_name == "ValueError"
    assert ex.expected.resolve({}) is ValueError


def test_raises_dotted_name_resolves_from_globalns():
    import decimal

    ex = parse_example("(1,) -> raises decimal.InvalidOperation")
    assert ex.expected.resolve({"decimal": decimal}) is decimal.InvalidOperation


def test_missing_arrow_is_rejected():
    with pytest.raises(PyIntentSpecError, match="missing the '->'"):
        parse_example("(1, 2) 3")


def test_empty_args_is_rejected():
    with pytest.raises(PyIntentSpecError, match="no argument tuple"):
        parse_example(" -> 3")


def test_empty_expected_is_rejected():
    with pytest.raises(PyIntentSpecError, match="nothing after"):
        parse_example("(1,) -> ")


def test_raises_without_type_is_rejected():
    with pytest.raises(PyIntentSpecError, match="followed by an exception"):
        parse_example("(1,) -> raises")


def test_arrow_inside_string_is_not_a_separator():
    ex = parse_example("('a->b',) -> 'x->y'")
    assert ex.eval_args({}) == ("a->b",)
    assert ex.expected.resolve({}) == "x->y"


def test_expected_value_evaluated_in_globalns():
    ex = parse_example("(1,) -> SENTINEL")
    assert ex.expected.resolve({"SENTINEL": 99}) == 99


def test_non_string_entry_is_rejected():
    with pytest.raises(PyIntentSpecError, match="must be a string"):
        parse_example(123)  # type: ignore[arg-type]


def test_null_byte_in_args_is_rejected():
    """Bug #35: null byte in example args raises PyIntentSpecError (not raw ValueError)."""
    with pytest.raises(PyIntentSpecError):
        parse_example("(\x00,) -> 1")


def test_null_byte_in_expected_is_rejected():
    """Bug #35: null byte in expected value raises PyIntentSpecError (not raw ValueError)."""
    with pytest.raises(PyIntentSpecError):
        parse_example("(1,) -> \x00")
