"""Tests for the verifiers, the orchestrator, the CLI, and the pytest plugin."""

from __future__ import annotations

from click.testing import CliRunner

from pyintent.cli import main
from pyintent.verifier import run_all
from pyintent.verifier._result import Status
from pyintent.verifier.effects import verify_effects
from pyintent.verifier.examples import verify_examples
from pyintent.verifier.properties import verify_properties
from pyintent.verifier.types import verify_types


def _status_set(results):
    return {r.status for r in results}


# --------------------------------------------------------------------------- #
# examples
# --------------------------------------------------------------------------- #
def test_examples_pass_fail_raise_wildcard(make_module, target_for):
    mod = make_module(
        """
from pyintent import spec, pure
@spec(intent="add", effects=[pure],
      ex=["(1, 2) -> 3", "(2, 2) -> 5", "(1, 0) -> _"])
def add(a: int, b: int) -> int:
    return a + b

@spec(intent="boom", ex=["(0,) -> raises ZeroDivisionError", "(2,) -> raises ValueError"])
def recip(x: int) -> float:
    return 1 / x
"""
    )
    add = verify_examples(target_for(mod, "add"))
    assert add[0].status is Status.PASS              # 1+2 == 3
    assert add[1].status is Status.FAIL              # 2+2 != 5
    assert add[2].status is Status.PASS              # wildcard

    recip = verify_examples(target_for(mod, "recip"))
    assert recip[0].status is Status.PASS            # raises ZeroDivisionError
    assert recip[1].status is Status.FAIL            # expected ValueError, got none/other


def test_examples_skipped_for_instance_methods(make_module, target_for):
    mod = make_module(
        """
from pyintent import spec, pure
class C:
    @spec(intent="m", effects=[pure], ex=["(2,) -> 4"])
    def m(self, x: int) -> int:
        return x * 2
"""
    )
    res = verify_examples(target_for(mod, "C.m"))
    assert res and all(r.status is Status.SKIPPED for r in res)


# --------------------------------------------------------------------------- #
# properties
# --------------------------------------------------------------------------- #
def test_properties_pass_for_holding_invariant(make_module, target_for):
    mod = make_module(
        """
from pyintent import spec, pure
@spec(intent="abs", effects=[pure], ensures=["result >= 0"])
def myabs(x: int) -> int:
    return x if x >= 0 else -x
"""
    )
    res = verify_properties(target_for(mod, "myabs"))
    assert len(res) == 1 and res[0].status is Status.PASS


def test_properties_falsifies_bad_invariant(make_module, target_for):
    mod = make_module(
        """
from pyintent import spec, pure
@spec(intent="pos", effects=[pure], ensures=["result > 0"])
def identity(x: int) -> int:
    return x
"""
    )
    res = verify_properties(target_for(mod, "identity"))
    assert res[0].status is Status.FAIL


def test_properties_comprehension_in_ensures_pass(make_module, target_for):
    """Comprehensions/generators in ensures must not raise NameError."""
    mod = make_module(
        """
from __future__ import annotations
from typing import List
from pyintent import spec, pure
@spec(intent="positive elems", effects=[pure],
      ensures=["all(x > 0 for x in result)"])
def positives(xs: List[int]) -> List[int]:
    return [abs(x) + 1 for x in xs]
"""
    )
    res = verify_properties(target_for(mod, "positives"))
    assert len(res) == 1 and res[0].status is Status.PASS


def test_properties_comprehension_in_ensures_fail(make_module, target_for):
    """A falsified comprehension-based postcondition is reported as FAIL, not ERROR."""
    mod = make_module(
        """
from __future__ import annotations
from typing import List
from pyintent import spec, pure
@spec(intent="nonneg elems", effects=[pure],
      ensures=["all(x >= 0 for x in result)"])
def identity_list(xs: List[int]) -> List[int]:
    return list(xs)
"""
    )
    res = verify_properties(target_for(mod, "identity_list"))
    assert len(res) == 1 and res[0].status is Status.FAIL


def test_properties_comprehension_references_param(make_module, target_for):
    """Comprehension body can reference both result and input parameters."""
    mod = make_module(
        """
from __future__ import annotations
from typing import List
from pyintent import spec, pure
@spec(intent="double each", effects=[pure],
      ensures=["all(r == 2 * x for r, x in zip(result, xs))"])
def double(xs: List[int]) -> List[int]:
    return [x * 2 for x in xs]
"""
    )
    res = verify_properties(target_for(mod, "double"))
    assert len(res) == 1 and res[0].status is Status.PASS


def test_properties_dict_key_postcondition_pass(make_module, target_for):
    """Bug #26: dict-keyed result in ensures evaluates correctly (PASS)."""
    mod = make_module(
        """
from pyintent import spec, pure
@spec(intent="wrap in dict", effects=[pure], ensures=["result['key'] == x"])
def wrap(x: int) -> dict:
    return {'key': x}
"""
    )
    res = verify_properties(target_for(mod, "wrap"))
    assert len(res) == 1 and res[0].status is Status.PASS


def test_properties_set_literal_postcondition_fail(make_module, target_for):
    """Bug #26: set-literal comparison in ensures evaluates correctly (FAIL)."""
    mod = make_module(
        """
from pyintent import spec, pure
@spec(intent="wrong set", effects=[pure], ensures=["result == {1, 2}"])
def f(x: int) -> set:
    return {x}
"""
    )
    res = verify_properties(target_for(mod, "f"))
    assert len(res) == 1 and res[0].status is Status.FAIL


def test_properties_postcondition_exception_is_fail_not_error(make_module, target_for):
    """Bug #27: unexpected exception in postcondition must be FAIL, not ERROR."""
    mod = make_module(
        """
from pyintent import spec, pure
@spec(intent="attr error", effects=[pure], ensures=["result.nonexistent == 1"])
def f(x: int) -> int:
    return x
"""
    )
    res = verify_properties(target_for(mod, "f"))
    assert len(res) == 1
    assert res[0].status is Status.FAIL
    assert res[0].status is not Status.ERROR


def test_properties_function_raises_is_fail_not_error(make_module, target_for):
    """Bug #27: function raising unexpectedly must be FAIL, not ERROR."""
    mod = make_module(
        """
from pyintent import spec, pure
@spec(intent="sometimes raises", effects=[pure], ensures=["result >= 0"])
def f(x: int) -> int:
    if x < 0:
        raise ValueError("negative input")
    return x
"""
    )
    res = verify_properties(target_for(mod, "f"))
    assert len(res) == 1
    assert res[0].status is Status.FAIL
    assert res[0].status is not Status.ERROR


def test_properties_skips_effectful(make_module, target_for):
    mod = make_module(
        """
from pyintent import spec, io
@spec(intent="io", effects=[io], ensures=["result == result"])
def f(x: int) -> int:
    return x
"""
    )
    res = verify_properties(target_for(mod, "f"))
    assert res[0].status is Status.SKIPPED


# --------------------------------------------------------------------------- #
# effects
# --------------------------------------------------------------------------- #
def test_effects_pure_pass_and_fail(make_module, target_for):
    mod = make_module(
        """
from pyintent import spec, pure
@spec(intent="clean", effects=[pure])
def clean(x: int) -> int:
    return x + 1

@spec(intent="dirty", effects=[pure])
def dirty(x: int) -> int:
    print(x)
    return x
"""
    )
    assert verify_effects(target_for(mod, "clean"))[0].status is Status.PASS
    dirty = verify_effects(target_for(mod, "dirty"))
    assert dirty[0].status is Status.FAIL


def test_effects_async_check(make_module, target_for):
    mod = make_module(
        """
from pyintent import spec, async_
@spec(intent="ok", effects=[async_])
async def good(x: int) -> int:
    return x

@spec(intent="bad", effects=[async_])
def bad(x: int) -> int:
    return x
"""
    )
    assert verify_effects(target_for(mod, "good"))[0].status is Status.PASS
    assert verify_effects(target_for(mod, "bad"))[0].status is Status.FAIL


def test_effects_throws_check(make_module, target_for):
    mod = make_module(
        """
from pyintent import spec, throws
@spec(intent="ok", effects=[throws(ValueError)])
def good(x: int) -> int:
    if x < 0:
        raise ValueError("neg")
    return x

@spec(intent="bad", effects=[throws(ValueError)])
def bad(x: int) -> int:
    raise KeyError("nope")
"""
    )
    assert verify_effects(target_for(mod, "good"))[0].status is Status.PASS
    assert verify_effects(target_for(mod, "bad"))[0].status is Status.FAIL


def test_effects_throws_ignores_raised_variables(make_module, target_for):
    """`raise err` where err is a local variable is not statically resolvable
    and must not be reported as an undeclared raise."""
    mod = make_module(
        """
from pyintent import spec, throws
@spec(intent="raise via variable", effects=[throws(ValueError)])
def f(x: int) -> int:
    err = ValueError("bad")
    if x < 0:
        raise err
    return x
"""
    )
    res = verify_effects(target_for(mod, "f"))
    assert res[0].status is Status.PASS
    assert "not checked" in res[0].summary  # the skip is reported, not silent


def test_effects_throws_flags_locally_imported_constructor(make_module, target_for):
    """`raise NotFound(...)` where NotFound was imported inside the function is
    a constructor call and must still be flagged even though the name is not
    in module globals."""
    mod = make_module(
        """
from pyintent import spec, throws
@spec(intent="local import raise", effects=[throws(ValueError)])
def f(x: int) -> int:
    from decimal import InvalidOperation
    raise InvalidOperation("nope")
"""
    )
    res = verify_effects(target_for(mod, "f"))
    assert res[0].status is Status.FAIL
    assert "InvalidOperation" in res[0].detail


def test_effects_throws_skips_factory_calls(make_module, target_for):
    """`raise make_err()` calls a factory, not a constructor; the raised type
    can't be determined statically, so it is skipped (and counted)."""
    mod = make_module(
        """
from pyintent import spec, throws

def make_err():
    return ValueError("bad")

@spec(intent="factory raise", effects=[throws(ValueError)])
def f(x: int) -> int:
    if x < 0:
        raise make_err()
    return x
"""
    )
    res = verify_effects(target_for(mod, "f"))
    assert res[0].status is Status.PASS
    assert "not checked" in res[0].summary


def test_effects_throws_resolves_module_level_exceptions(make_module, target_for):
    """A bare name that resolves to an exception class in the module is checked."""
    mod = make_module(
        """
from pyintent import spec, throws

class AppError(Exception):
    pass

@spec(intent="undeclared custom raise", effects=[throws(ValueError)])
def f(x: int) -> int:
    raise AppError("nope")
"""
    )
    res = verify_effects(target_for(mod, "f"))
    assert res[0].status is Status.FAIL
    assert "AppError" in res[0].detail


def test_effects_line_numbers_are_file_relative(make_module, target_for):
    mod = make_module(
        """
# padding line 2
# padding line 3
from pyintent import spec, pure

@spec(intent="dirty", effects=[pure])
def dirty(x: int) -> int:
    print(x)
    return x
"""
    )
    res = verify_effects(target_for(mod, "dirty"))
    assert res[0].status is Status.FAIL
    assert "line 8:" in res[0].detail  # print(x) sits on line 8 of the file


# --------------------------------------------------------------------------- #
# types (mypy) — skipped gracefully if mypy is absent
# --------------------------------------------------------------------------- #
def test_types_pass_and_fail(tmp_path):
    clean = tmp_path / "clean.py"
    clean.write_text("def f(x: int) -> int:\n    return x + 1\n")
    res = verify_types(str(clean))
    assert res[0].status in (Status.PASS, Status.SKIPPED)

    broken = tmp_path / "broken.py"
    broken.write_text("def f(x: int) -> int:\n    return 'not an int'\n")
    res = verify_types(str(broken))
    assert res[0].status in (Status.FAIL, Status.SKIPPED)


# --------------------------------------------------------------------------- #
# orchestrator
# --------------------------------------------------------------------------- #
def test_run_all_collects_every_verifier(make_module):
    mod = make_module(
        """
from pyintent import spec, pure
@spec(intent="add", effects=[pure], ensures=["result == a + b"],
      ex=["(1, 2) -> 3"])
def add(a: int, b: int) -> int:
    return a + b
"""
    )
    results = run_all(mod, which={"examples", "properties", "effects"})
    verifiers = {r.verifier for r in results}
    assert {"examples", "properties", "effects"} <= verifiers
    assert all(r.status is not Status.FAIL for r in results)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_prompt_and_version():
    runner = CliRunner()
    out = runner.invoke(main, ["prompt"])
    assert out.exit_code == 0 and "pyintent" in out.output


def test_cli_verify_exit_codes(tmp_path):
    good = tmp_path / "good.py"
    good.write_text(
        "from pyintent import spec, pure\n"
        "@spec(intent='id', effects=[pure], ex=['(1,) -> 1'])\n"
        "def f(x: int) -> int:\n    return x\n"
    )
    bad = tmp_path / "bad.py"
    bad.write_text(
        "from pyintent import spec, pure\n"
        "@spec(intent='id', effects=[pure], ex=['(1,) -> 2'])\n"
        "def f(x: int) -> int:\n    return x\n"
    )
    runner = CliRunner()
    assert runner.invoke(main, ["verify", str(good)]).exit_code == 0
    assert runner.invoke(main, ["verify", str(bad)]).exit_code == 1


def test_cli_check_require_specs(tmp_path):
    src = tmp_path / "m.py"
    src.write_text(
        "from pyintent import spec, pure\n"
        "@spec(intent='id', effects=[pure], ex=['(1,) -> 1'])\n"
        "def f(x: int) -> int:\n    return x\n"
        "def unspecced(y):\n    return y\n"
    )
    runner = CliRunner()
    clean = runner.invoke(main, ["check", str(src)])
    assert clean.exit_code == 0
    strict = runner.invoke(main, ["check", "--require-specs", str(src)])
    assert strict.exit_code == 1 and "unspecced" in strict.output


def test_cli_check_require_specs_skips_private(tmp_path):
    """--require-specs only demands specs on public names."""
    src = tmp_path / "m.py"
    src.write_text(
        "from pyintent import spec, pure\n"
        "@spec(intent='id', effects=[pure], ex=['(1,) -> 1'])\n"
        "def f(x: int) -> int:\n    return x\n"
        "def _helper(y):\n    return y\n"
    )
    runner = CliRunner()
    strict = runner.invoke(main, ["check", "--require-specs", str(src)])
    assert strict.exit_code == 0
    assert "_helper" not in strict.output


def test_cli_exclude_config_skips_files(tmp_path):
    """[tool.pyintent] exclude keeps matching files from being imported at all."""
    (tmp_path / "pyproject.toml").write_text(
        "[tool.pyintent]\nexclude = ['migrations']\n"
    )
    (tmp_path / "app.py").write_text(
        "from pyintent import spec, pure\n"
        "@spec(intent='id', effects=[pure], ex=['(1,) -> 1'])\n"
        "def f(x: int) -> int:\n    return x\n"
    )
    mig = tmp_path / "migrations"
    mig.mkdir()
    (mig / "m001.py").write_text("raise RuntimeError('must never be imported')\n")

    runner = CliRunner()
    result = runner.invoke(main, ["verify", "--only", "examples", str(tmp_path)])
    assert result.exit_code == 0
    assert "must never be imported" not in result.output


def test_cli_exclude_anchors_at_pyproject_dir(tmp_path):
    """Exclude patterns mean the same thing whichever subdirectory is targeted:
    they anchor at the pyproject.toml directory, not the CLI argument."""
    (tmp_path / "pyproject.toml").write_text(
        "[tool.pyintent]\nexclude = ['src/migrations']\n"
    )
    src = tmp_path / "src"
    mig = src / "migrations"
    mig.mkdir(parents=True)
    (src / "app.py").write_text(
        "from pyintent import spec, pure\n"
        "@spec(intent='id', effects=[pure], ex=['(1,) -> 1'])\n"
        "def f(x: int) -> int:\n    return x\n"
    )
    (mig / "m001.py").write_text("raise RuntimeError('must never be imported')\n")

    runner = CliRunner()
    result = runner.invoke(main, ["verify", "--only", "examples", str(src)])
    assert result.exit_code == 0
    assert "must never be imported" not in result.output


def test_cli_exclude_does_not_apply_to_explicit_file(tmp_path):
    """A file the user names explicitly is always checked, even if a pattern
    matches it — otherwise verify would report a silent empty success."""
    (tmp_path / "pyproject.toml").write_text(
        "[tool.pyintent]\nexclude = ['app.py']\n"
    )
    target = tmp_path / "app.py"
    target.write_text(
        "from pyintent import spec, pure\n"
        "@spec(intent='id', effects=[pure], ex=['(1,) -> 2'])\n"
        "def f(x: int) -> int:\n    return x\n"
    )
    runner = CliRunner()
    result = runner.invoke(main, ["verify", "--only", "examples", str(target)])
    assert result.exit_code == 1  # the failing example ran; not silently skipped


def test_plugin_respects_exclude_config(pytester):
    """pytest --pyintent must not collect files that [tool.pyintent] excludes."""
    pytester.makepyprojecttoml(
        """
        [tool.pyintent]
        exclude = ["migrations"]
        """
    )
    mig = pytester.path / "migrations"
    mig.mkdir()
    (mig / "m001.py").write_text(
        "from pyintent import spec, pure\n"
        "raise RuntimeError('must never be imported')\n"
    )
    pytester.makepyfile(
        orders="""
from pyintent import spec, pure
@spec(intent="add", effects=[pure], ex=["(1, 2) -> 3"])
def add(a: int, b: int) -> int:
    return a + b
"""
    )
    result = pytester.runpytest_subprocess("--pyintent")
    outcomes = result.parseoutcomes()
    assert outcomes.get("errors", 0) == 0
    assert outcomes.get("passed", 0) >= 1


# --------------------------------------------------------------------------- #
# pytest plugin (via pytester subprocess so the installed plugin auto-loads)
# --------------------------------------------------------------------------- #
def test_plugin_collects_and_reports(pytester):
    pytester.makepyfile(
        orders="""
from pyintent import spec, pure
@spec(intent="add", effects=[pure], ex=["(1, 2) -> 3", "(2, 2) -> 5"])
def add(a: int, b: int) -> int:
    return a + b
"""
    )
    result = pytester.runpytest_subprocess("--pyintent", "orders.py")
    outcomes = result.parseoutcomes()
    assert outcomes.get("failed") == 1      # the (2, 2) -> 5 case
    assert outcomes.get("passed", 0) >= 1   # the (1, 2) -> 3 case (+ types)


def test_plugin_is_opt_in(pytester):
    """Without --pyintent (or the ini opt-in) the plugin collects nothing."""
    pytester.makepyfile(
        orders="""
from pyintent import spec, pure
@spec(intent="add", effects=[pure], ex=["(1, 2) -> 3", "(2, 2) -> 5"])
def add(a: int, b: int) -> int:
    return a + b
"""
    )
    result = pytester.runpytest_subprocess("orders.py")
    outcomes = result.parseoutcomes()
    assert outcomes.get("failed", 0) == 0
    assert outcomes.get("passed", 0) == 0


def test_plugin_ini_opt_in(pytester):
    pytester.makepyfile(
        orders="""
from pyintent import spec, pure
@spec(intent="add", effects=[pure], ex=["(1, 2) -> 3", "(2, 2) -> 5"])
def add(a: int, b: int) -> int:
    return a + b
"""
    )
    pytester.makeini("[pytest]\npyintent = true\n")
    result = pytester.runpytest_subprocess("orders.py")
    outcomes = result.parseoutcomes()
    assert outcomes.get("failed") == 1
    assert outcomes.get("passed", 0) >= 1
