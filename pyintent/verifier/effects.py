"""Effects verifier — shallow AST checks of declared effects.

In v0.1 three effects are checked:

* ``pure``    — no calls into known impure modules/builtins, no global/nonlocal writes
* ``async_``  — the function really is a coroutine
* ``throws``  — every explicitly raised exception type is declared

All other effects are recorded as declaration-only. The purity check is
intentionally shallow (it does not follow calls into helpers) and reports the
specific offending lines.
"""

from __future__ import annotations

import ast
import inspect
import textwrap

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
        self.raised: list[tuple[int, str]] = []

    def visit_Raise(self, node: ast.Raise) -> None:
        exc = node.exc
        if exc is None:  # bare re-raise
            return
        target = exc.func if isinstance(exc, ast.Call) else exc
        name = None
        if isinstance(target, ast.Name):
            name = target.id
        elif isinstance(target, ast.Attribute):
            name = target.attr
        if name:
            self.raised.append((node.lineno, name))
        self.generic_visit(node)


def _get_ast(target: SpecTarget) -> ast.AST | None:
    fn = target.invoke
    if fn is None:
        return None
    try:
        src = textwrap.dedent(inspect.getsource(fn))
    except (OSError, TypeError):
        return None
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
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
        results.append(_check_throws(name, sp, fn_ast))

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
        return CheckResult("effects", name, Status.PASS, summary="pure", label="pure")
    lines = "\n".join(f"  line {ln}: {what}" for ln, what in v.violations)
    detail = f"{name} is declared pure but performs side effects:\n{lines}"
    return CheckResult("effects", name, Status.FAIL,
                       summary=f"declared pure but has {len(v.violations)} side effect(s)",
                       detail=detail, label="pure")


def _check_async(name: str, is_async: bool) -> CheckResult:
    if is_async:
        return CheckResult("effects", name, Status.PASS, summary="async", label="async")
    return CheckResult("effects", name, Status.FAIL,
                       summary="declared async_ but is not a coroutine function",
                       detail=f"{name} declares async_ but was not defined with 'async def'.",
                       label="async")


def _check_throws(name: str, sp, fn_ast) -> CheckResult:
    if fn_ast is None:
        return CheckResult("effects", name, Status.SKIPPED,
                           summary="could not read source for throws check", label="throws")
    declared = {e.__name__ for e in sp.thrown_exceptions}
    c = _RaiseCollector()
    c.visit(fn_ast)
    undeclared = [(ln, nm) for ln, nm in c.raised if nm not in declared]
    if not undeclared:
        return CheckResult("effects", name, Status.PASS,
                           summary=f"raises only declared: {', '.join(sorted(declared))}",
                           label="throws")
    lines = "\n".join(f"  line {ln}: raises {nm} (not in throws(...))" for ln, nm in undeclared)
    detail = (
        f"{name} raises exception types not declared in throws(...):\n{lines}\n"
        f"  declared: {', '.join(sorted(declared)) or '(none)'}"
    )
    return CheckResult("effects", name, Status.FAIL,
                       summary=f"{len(undeclared)} undeclared raise(s)",
                       detail=detail, label="throws")
