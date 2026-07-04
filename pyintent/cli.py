"""``pyintent`` command-line interface.

Commands
--------
* ``pyintent init``                 write the agent guide into prompt files
* ``pyintent prompt``               print the agent guide to stdout
* ``pyintent check  PATH``          validate spec structure (imports modules,
  which runs top-level code, but never calls the spec'd functions)
* ``pyintent verify PATH [--json]`` run the verifiers

Exit codes: ``0`` all good, ``1`` verification/spec failures, ``2`` usage or
load error (could not import a target, malformed spec at import time).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import click

from ._config import exclude_patterns, is_excluded, load_config
from ._errors import PyIntentSpecError
from ._loader import import_file, iter_python_files
from ._module_spec import MODULE_ATTR
from ._spec import SpecLevel, get_spec
from . import prompt as _prompt
from .verifier import ALL_VERIFIERS, run_all
from .verifier._result import Status

_STATUS_STYLE = {
    Status.PASS: ("PASS", "green"),
    Status.FAIL: ("FAIL", "red"),
    Status.ERROR: ("ERR ", "red"),
    Status.SKIPPED: ("SKIP", "yellow"),
}


# --------------------------------------------------------------------------- #
# config
# --------------------------------------------------------------------------- #
def _project_config(target: Path) -> tuple[dict, Path]:
    """Load [tool.pyintent] for ``target``; return (config, exclude root).

    Exclude patterns are anchored at the directory of the pyproject.toml that
    defined them, so they mean the same thing no matter which subdirectory
    the command is pointed at.
    """
    start = target if target.is_dir() else target.parent
    cfg, cfg_dir = load_config(start)
    return cfg, (cfg_dir or start).resolve()


def _collect_modules(path: Path, exclude: list[str] | None = None,
                     exclude_root: Path | None = None):
    """Import every target file under ``path``. Returns (modules, load_errors).

    ``exclude`` only applies when walking a directory — a file the user names
    explicitly is always checked.
    """
    modules = []
    errors: list[tuple[Path, BaseException]] = []
    if not (exclude and path.is_dir() and exclude_root is not None):
        exclude = None
    for f in iter_python_files(path):
        if exclude and exclude_root is not None and is_excluded(f, exclude_root, exclude):
            continue
        try:
            modules.append((f, import_file(f)))
        except PyIntentSpecError as e:
            errors.append((f, e))
        except BaseException as e:  # noqa: BLE001 - report, keep going
            errors.append((f, e))
    return modules, errors


# --------------------------------------------------------------------------- #
# reporting
# --------------------------------------------------------------------------- #
def _display_target(target: str) -> str:
    """Shorten absolute paths for terminal display (results keep them intact)."""
    if not os.path.isabs(target):
        return target
    try:
        rel = os.path.relpath(target)
    except ValueError:  # pragma: no cover - different drive on Windows
        return target
    return rel if not rel.startswith(os.pardir) else target


def _print_results(results, *, show_detail=True) -> dict[Status, int]:
    counts: dict[Status, int] = {s: 0 for s in Status}
    for r in results:
        counts[r.status] += 1
        label, color = _STATUS_STYLE[r.status]
        tag = click.style(f"[{label}]", fg=color, bold=True)
        loc = click.style(_display_target(r.target), bold=True)
        extra = f"  {r.label}" if r.label else ""
        summ = f"  {r.summary}" if r.summary else ""
        click.echo(f"{tag} {r.verifier:<10} {loc}{extra}{summ}")
        if show_detail and r.status in (Status.FAIL, Status.ERROR) and r.detail:
            for line in r.detail.splitlines():
                click.echo(click.style("        " + line, fg="bright_black"))
    return counts


def _summary_line(counts: dict[Status, int]) -> str:
    parts = [
        click.style(f"{counts[Status.PASS]} passed", fg="green"),
        click.style(f"{counts[Status.FAIL]} failed", fg="red"),
        click.style(f"{counts[Status.ERROR]} errored", fg="red"),
        click.style(f"{counts[Status.SKIPPED]} skipped", fg="yellow"),
    ]
    return "  ".join(parts)


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #
@click.group()
@click.version_option(package_name="pyintent", message="%(version)s")
def main() -> None:
    """pyintent — verify that implementations satisfy their @spec intent."""


@main.command()
@click.option("--root", default=".", type=click.Path(file_okay=False),
              help="Project root to write prompt files into.")
def init(root: str) -> None:
    """Write the pyintent authoring guide into agent prompt files."""
    actions = _prompt.write_prompt_files(root)
    for rel, action in actions.items():
        click.echo(f"  {action:<9} {rel}")
    click.echo(click.style("pyintent guide written. Point your AI tools here.", fg="green"))


@main.command()
def prompt() -> None:
    """Print the pyintent authoring guide to stdout."""
    click.echo(_prompt.get_reference())


def _is_public(qualname: str) -> bool:
    """Public means no ``_``-prefixed segment anywhere in the dotted name."""
    return not any(part.startswith("_") for part in qualname.split("."))


def _iter_specs(module):
    """Yield (level, qualified_name, spec_or_None) for top-level defs in module."""
    import inspect

    modname = getattr(module, "__name__", "")
    for name, obj in vars(module).items():
        if name.startswith("__") and name.endswith("__"):
            continue
        if inspect.isfunction(obj) and getattr(obj, "__module__", None) == modname:
            yield SpecLevel.FUNCTION, name, get_spec(obj)
        elif inspect.isclass(obj) and getattr(obj, "__module__", None) == modname:
            yield SpecLevel.CLASS, name, get_spec(obj)
            for mname, mobj in vars(obj).items():
                if mname.startswith("__") and mname.endswith("__"):
                    continue
                inner = mobj
                if isinstance(mobj, (staticmethod, classmethod)):
                    inner = mobj.__func__
                elif isinstance(mobj, property):
                    inner = mobj.fget
                if inner is not None and (inspect.isfunction(inner)):
                    yield SpecLevel.METHOD, f"{name}.{mname}", get_spec(inner)


@main.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--require-specs", "require_specs", is_flag=True, default=False,
              help="Fail if public functions/methods lack a @spec.")
@click.option("--all", "require_all", is_flag=True, default=False,
              help="With --require-specs, also require class and module specs.")
def check(path: str, require_specs: bool, require_all: bool) -> None:
    """Validate spec structure by importing PATH (functions are not called)."""
    target = Path(path)
    cfg, exclude_root = _project_config(target)
    cfg_rs = cfg.get("require_specs")
    if not require_specs and cfg_rs:
        require_specs = True
        require_all = require_all or (cfg_rs == "all" or cfg_rs is True)

    level = "all" if (require_specs and require_all) else ("public" if require_specs else None)

    modules, errors = _collect_modules(target, exclude=exclude_patterns(cfg),
                                       exclude_root=exclude_root)

    if errors:
        for f, e in errors:
            kind = "spec error" if isinstance(e, PyIntentSpecError) else type(e).__name__
            click.echo(click.style(f"[{kind}] {f}: {e}", fg="red"))
        sys.exit(2)

    spec_count = 0
    missing: list[str] = []
    for f, module in modules:
        for lvl, qual, sp in _iter_specs(module):
            if sp is not None:
                spec_count += 1
            elif level:
                if lvl is SpecLevel.CLASS and level != "all":
                    continue
                if not _is_public(qual):
                    continue
                missing.append(f"{f}::{qual} ({lvl.value})")
        if level == "all" and getattr(module, MODULE_ATTR, None) is None:
            missing.append(f"{f}::<module> (module)")

    click.echo(f"Imported {len(modules)} file(s); found {spec_count} spec(s).")
    if missing:
        click.echo(click.style(f"{len(missing)} definition(s) missing a @spec:", fg="red"))
        for m in missing:
            click.echo(f"  - {m}")
        sys.exit(1)
    click.echo(click.style("All specs valid.", fg="green"))


@main.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON.")
@click.option("--only", type=click.Choice(ALL_VERIFIERS), multiple=True,
              help="Run only these verifiers (repeatable).")
def verify(path: str, as_json: bool, only: tuple[str, ...]) -> None:
    """Run pyintent verifiers over PATH and report pass/fail."""
    target = Path(path)
    which = set(only) if only else None
    cfg, exclude_root = _project_config(target)

    modules, errors = _collect_modules(target, exclude=exclude_patterns(cfg),
                                       exclude_root=exclude_root)
    if errors:
        if as_json:
            click.echo(json.dumps({
                "ok": False,
                "load_errors": [{"file": str(f), "error": str(e)} for f, e in errors],
            }, indent=2))
        else:
            for f, e in errors:
                click.echo(click.style(f"[load error] {f}: {e}", fg="red"))
        sys.exit(2)

    all_results = []
    for _f, module in modules:
        all_results.extend(run_all(module, which))

    if as_json:
        payload = {
            "ok": all(r.status is not Status.FAIL and r.status is not Status.ERROR
                      for r in all_results),
            "results": [r.to_dict() for r in all_results],
        }
        click.echo(json.dumps(payload, indent=2))
    else:
        counts = _print_results(all_results)
        click.echo("")
        click.echo(_summary_line(counts))

    failed = sum(1 for r in all_results if r.status in (Status.FAIL, Status.ERROR))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
