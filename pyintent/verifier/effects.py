"""Effects verifier — shallow AST checks of declared effects.

In v0.1 three effects are checked:

* ``pure``    — no calls into known impure modules/builtins, no global/nonlocal writes
* ``async_``  — the function really is a coroutine
* ``throws``  — every explicitly raised exception type is declared. Raises
  that don't statically name an exception type — ``raise err`` through a
  variable, ``raise make_err()`` through a factory — are skipped and counted
  in the summary rather than reported as false positives.

All other effects are recorded as declaration-only. The purity check is
intentionally shallow (it does not follow calls into helpers) and reports the
specific offending lines.
"""

from __future__ import annotations

import ast
import builtins
import inspect
import textwrap
from typing import Any, Mapping

from .._effects import EffectKind
from .._discovery import SpecTarget
from ._result import CheckResult, Status

_IMPURE_BUILTINS = {"print", "open", "input", "exec", "eval", "breakpoint"}
_IMPURE_ROOTS = {
    "os", "sys", "random", "requests", "httpx", "socket",
    "subprocess", "urllib", "time", "shutil",
}


def _root_name(node: ast.AST) -> str | None:
    while isinstance(node, ast.Attribute):
        node = node.value
    if isinstance(node, ast.Name):
        return node.id
    return None


class _PurityVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.violations: list[tuple[int, str]] = []

    def visit_Global(self, node: ast.Global) -> None:
        self.violations.append((node.lineno, "global statement"))

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        self.violations.append((node.lineno, "nonlocal statement"))

    def visit_Call(self, node: ast.Call) -> None:
        f = node.func
        if isinstance(f, ast.Name) and f.id in _IMPURE_BUILTINS:
            self.violations.append((node.lineno, f"call to {f.id}()"))
        elif isinstance(f, ast.Attribute):
            root = _root_name(f)
            if root in _IMPURE_ROOTS:
                self.violations.append((node.lineno, f"call into '{root}'"))
        self.generic_visit(node)


class _RaiseCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        #: (lineno, name, is_call) — is_call means ``raise Name(...)`` (almost
        #: certainly a constructor); a non-call ``raise name`` may be a variable.
        self.raised: list[tuple[int, str, bool]] = []

    def visit_Raise(self, node: ast.Raise) -> None:
        exc = node.exc
        if exc is None:  # bare re-raise
            return
        is_call = isinstance(exc, ast.Call)
        target = exc.func if isinstance(exc, ast.Call) else exc
        if isinstance(target, ast.Name):
            self.raised.append((node.lineno, target.id, is_call))
        elif isinstance(target, ast.Attribute):
            self.raised.append((node.lineno, target.attr, is_call))
        self.generic_visit(node)


def _get_ast(target: SpecTarget) -> ast.AST | None:
    """Return the function's AST node with file-relative line numbers."""
    fn = target.invoke
    if fn is None:
        return None
    try:
        lines, firstline = inspect.getsourcelines(fn)
    except (OSError, TypeError):
        return None
    src = textwrap.dedent("".join(lines))
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            ast.increment_lineno(node, firstline - 1)
            return node
    return None


def verify_effects(target: SpecTarget) -> list[CheckResult]:
    sp = target.spec
    name = sp.target_name
    kinds = {e.kind for e in sp.effects}
    if not kinds:
        return []

    results: list[CheckResult] = []
    fn_ast = None
    if kinds & {EffectKind.PURE, EffectKind.THROWS}:
        fn_ast = _get_ast(target)

    if EffectKind.PURE in kinds:
        results.append(_check_pure(name, fn_ast))
    if EffectKind.ASYNC in kinds:
        results.append(_check_async(name, sp.is_async))
    if EffectKind.THROWS in kinds:
        results.append(_check_throws(name, sp, fn_ast, target.globalns))

    declared_only = kinds - {EffectKind.PURE, EffectKind.ASYNC, EffectKind.THROWS}
    if declared_only:
        labels = ", ".join(sorted(k.value for k in declared_only))
        results.append(
            CheckResult("effects", name, Status.SKIPPED,
                        summary=f"declaration-only in v0.1: {labels}")
        )
    return results


def _check_pure(name: str, fn_ast) -> CheckResult:
    if fn_ast is None:
        return CheckResult("effects", name, Status.SKIPPED,
                           summary="could not read source for purity check", label="pure")
    v = _PurityVisitor()
    v.visit(fn_ast)
    if not v.violations:
        return CheckResult("effects", name, Status.PASS,
                           summary="no impure calls found", label="pure")
    lines = "\n".join(f"  line {ln}: {what}" for ln, what in v.violations)
    detail = f"{name} is declared pure but performs side effects:\n{lines}"
    return CheckResult("effects", name, Status.FAIL,
                       summary=f"declared pure but has {len(v.violations)} side effect(s)",
                       detail=detail, label="pure")


def _check_async(name: str, is_async: bool) -> CheckResult:
    if is_async:
        return CheckResult("effects", name, Status.PASS,
                           summary="defined with async def", label="async")
    return CheckResult("effects", name, Status.FAIL,
                       summary="declared async_ but is not a coroutine function",
                       detail=f"{name} declares async_ but was not defined with 'async def'.",
                       label="async")


_UNRESOLVED = object()


def _should_check_raise(nm: str, is_call: bool, globalns: Mapping[str, Any]) -> bool:
    """Decide whether a raised name is statically checkable against throws(...).

    * The name resolves (module globals or builtins) to an exception class —
      check it.
    * The name resolves to something else — skip: it's a variable holding an
      exception (``raise err``) or a factory function (``raise make_err()``),
      neither of which names the exception type.
    * The name doesn't resolve: a *call* (``raise NotFound(...)``) is almost
      certainly a constructor (locally imported or locally defined class), so
      check it by name; a plain ``raise name`` is almost certainly a local
      variable, so skip it.
    """
    obj = globalns.get(nm, getattr(builtins, nm, _UNRESOLVED))
    if obj is _UNRESOLVED:
        return is_call
    return isinstance(obj, type) and issubclass(obj, BaseException)


def _check_throws(name: str, sp, fn_ast, globalns: Mapping[str, Any]) -> CheckResult:
    if fn_ast is None:
        return CheckResult("effects", name, Status.SKIPPED,
                           summary="could not read source for throws check", label="throws")
    declared = {e.__name__ for e in sp.thrown_exceptions}
    c = _RaiseCollector()
    c.visit(fn_ast)
    undeclared: list[tuple[int, str]] = []
    skipped = 0
    for ln, nm, is_call in c.raised:
        if nm in declared:
            continue
        if _should_check_raise(nm, is_call, globalns):
            undeclared.append((ln, nm))
        else:
            skipped += 1
    if not undeclared:
        summary = f"raises only declared: {', '.join(sorted(declared))}"
        if skipped:
            summary += f" ({skipped} unresolvable raise(s) not checked)"
        return CheckResult("effects", name, Status.PASS, summary=summary, label="throws")
    lines = "\n".join(
        f"  line {ln}: raises {nm} (not in throws(...))" for ln, nm in undeclared
    )
    detail = (
        f"{name} raises exception types not declared in throws(...):\n{lines}\n"
        f"  declared: {', '.join(sorted(declared)) or '(none)'}"
    )
    return CheckResult("effects", name, Status.FAIL,
                       summary=f"{len(undeclared)} undeclared raise(s)",
                       detail=detail, label="throws")
