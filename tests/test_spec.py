"""Tests for @spec decoration, effect/perf construction, and module specs."""

from __future__ import annotations

import pytest

from pyintent import (
    Perf,
    PyIntentSpecError,
    async_,
    get_spec,
    io,
    module_spec,
    network,
    package_spec,
    pure,
    reads,
    spec,
    throws,
    writes,
)


# --------------------------------------------------------------------------- #
# decoration
# --------------------------------------------------------------------------- #
def test_spec_attaches_and_returns_target_unchanged():
    @spec(intent="double", effects=[pure], ex=["(2,) -> 4"])
    def double(x: int) -> int:
        return x * 2

    assert double(3) == 6  # behaviour preserved
    sp = get_spec(double)
    assert sp is not None
    assert sp.intent == "double"


def test_get_spec_returns_none_without_decoration():
    def plain(x):
        return x

    assert get_spec(plain) is None


def test_empty_intent_rejected():
    with pytest.raises(PyIntentSpecError, match="intent="):
        @spec(intent="")
        def f():
            return 1


def test_where_must_be_list_of_strings():
    with pytest.raises(PyIntentSpecError):
        @spec(intent="x", where="n >= 0")  # type: ignore[arg-type]
        def f(n: int) -> int:
            return n


def test_effects_must_be_effect_objects():
    with pytest.raises(PyIntentSpecError, match="must be Effect objects"):
        @spec(intent="x", effects=["pure"])  # type: ignore[list-item]
        def f():
            return 1


def test_perf_must_be_perf_object():
    with pytest.raises(PyIntentSpecError, match="perf="):
        @spec(intent="x", perf="O(n)")  # type: ignore[arg-type]
        def f():
            return 1


def test_malformed_example_rejected_at_decoration():
    with pytest.raises(PyIntentSpecError):
        @spec(intent="x", ex=["(1) -> 2"])  # missing trailing comma
        def f(a: int) -> int:
            return a


def test_malformed_ensures_syntax_error_raises_spec_error():
    """Bug #35: syntactically invalid ensures raises PyIntentSpecError at decoration."""
    with pytest.raises(PyIntentSpecError, match="not a valid Python expression"):
        @spec(intent="x", ensures=["result =="])  # incomplete expression
        def f() -> int:
            return 1


def test_malformed_ensures_null_byte_raises_spec_error():
    """Bug #35: ensures with null byte raises PyIntentSpecError (not raw ValueError)."""
    with pytest.raises(PyIntentSpecError, match="not a valid Python expression"):
        @spec(intent="x", ensures=["result == \x00"])  # null byte
        def f() -> int:
            return 1


# --------------------------------------------------------------------------- #
# effects
# --------------------------------------------------------------------------- #
def test_effect_singletons_and_constructors():
    assert reads("db").kind.value == "reads"
    assert writes("cache").kind.value == "writes"
    assert network("api").kind.value == "network"
    assert pure.kind.value == "pure"
    assert io.kind.value == "io"
    assert async_.kind.value == "async"


def test_reads_requires_nonempty_resource():
    with pytest.raises(PyIntentSpecError):
        reads("")


def test_throws_requires_exception_types():
    with pytest.raises(PyIntentSpecError):
        throws()
    with pytest.raises(PyIntentSpecError):
        throws(int)  # not a BaseException subclass
    assert throws(ValueError, KeyError).kind.value == "throws"


# --------------------------------------------------------------------------- #
# perf
# --------------------------------------------------------------------------- #
def test_perf_requires_at_least_one_field():
    with pytest.raises(PyIntentSpecError):
        Perf()


def test_perf_accepts_time_and_space():
    p = Perf(time="O(n)", space="O(1)")
    assert p.time == "O(n)"
    assert p.space == "O(1)"


def test_perf_rejects_non_string():
    with pytest.raises(PyIntentSpecError):
        Perf(time=5)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# methods / classes / modules
# --------------------------------------------------------------------------- #
def test_spec_on_staticmethod_and_classmethod():
    class C:
        @spec(intent="s", effects=[pure], ex=["(2,) -> 4"])
        @staticmethod
        def s(x: int) -> int:
            return x * 2

        @spec(intent="c", effects=[pure], ex=["(3,) -> 3"])
        @classmethod
        def c(cls, x: int) -> int:
            return x

    assert C.s(2) == 4
    assert C.c(3) == 3
    assert get_spec(C.__dict__["s"].__func__) is not None


def test_module_and_package_spec():
    m = module_spec(intent="a module")
    p = package_spec(intent="a package")
    assert m.intent == "a module"
    assert p.intent == "a package"
