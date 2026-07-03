"""Import Python files by path so their specs register (used by CLI and plugin)."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Iterator

_SKIP_DIRS = {
    "__pycache__", ".git", ".venv", "venv", "node_modules",
    ".mypy_cache", ".pytest_cache", "build", "dist", ".tox", ".eggs",
}


def import_file(path: str | Path) -> ModuleType:
    """Import a single ``.py`` file as a uniquely-named module.

    Scope (v0.1): this loads files as standalone modules under a synthetic name,
    with the file's directory prepended to ``sys.path``. That is reliable for
    self-contained scripts and flat layouts, but **explicit relative imports**
    (``from . import x``) inside the target file are not resolved, since the file
    is not imported as part of its package. For package-aware verification,
    import the package normally and run the verifier against its modules.
    """
    p = Path(path).resolve()
    modname = "pyintent_target_" + re.sub(r"\W", "_", str(p.with_suffix("")))
    if modname in sys.modules:
        return sys.modules[modname]

    parent = str(p.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)

    spec = importlib.util.spec_from_file_location(modname, str(p))
    if spec is None or spec.loader is None:
        raise ImportError(f"could not create import spec for {p}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[modname] = module
    spec.loader.exec_module(module)
    return module


def iter_python_files(root: str | Path) -> Iterator[Path]:
    """Yield ``.py`` files under ``root`` (or just ``root`` if it is a file)."""
    p = Path(root)
    if p.is_file():
        if p.suffix == ".py":
            yield p
        return
    for child in sorted(p.rglob("*.py")):
        if any(part in _SKIP_DIRS for part in child.parts):
            continue
        yield child
