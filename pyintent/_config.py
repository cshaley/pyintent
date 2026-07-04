"""Load ``[tool.pyintent]`` config and apply its ``exclude`` patterns.

Shared by the CLI and the pytest plugin so both honour the same settings.
"""

from __future__ import annotations

import fnmatch
from pathlib import Path


def load_config(start: Path) -> tuple[dict, Path | None]:
    """Walk up from ``start`` to the nearest pyproject.toml.

    Returns ``(config, config_dir)`` where ``config`` is the
    ``[tool.pyintent]`` table (or ``{}``) and ``config_dir`` is the directory
    containing the pyproject.toml that supplied it (or ``None``).
    """
    try:
        import tomllib
    except ModuleNotFoundError:  # pragma: no cover - py3.10
        try:
            import tomli as tomllib  # type: ignore[no-redef,import-not-found]
        except ModuleNotFoundError:
            return {}, None
    for directory in [start, *start.parents]:
        cfg = directory / "pyproject.toml"
        if cfg.is_file():
            try:
                data = tomllib.loads(cfg.read_text(encoding="utf-8"))
            except Exception:
                return {}, None
            return data.get("tool", {}).get("pyintent", {}) or {}, directory
    return {}, None


def exclude_patterns(cfg: dict) -> list[str]:
    raw = cfg.get("exclude") or []
    if not isinstance(raw, (list, tuple)):
        return []
    return [p for p in raw if isinstance(p, str) and p.strip()]


def is_excluded(f: Path, root_resolved: Path, patterns: list[str]) -> bool:
    """True if ``f`` matches any exclude pattern.

    Patterns are matched against the path relative to ``root_resolved``
    (normally the directory of the pyproject.toml that defined them). A
    pattern can name any path segment (``"migrations"``), a relative path
    prefix (``"src/migrations"``), or a glob of either (``"*_pb2.py"``).
    A file that resolves outside ``root_resolved`` is matched by its
    basename only, so generic patterns can't accidentally hit ancestor
    directory names.
    """
    if not patterns:
        return False
    try:
        rel = f.resolve().relative_to(root_resolved)
    except ValueError:
        rel = Path(f.name)
    parts = rel.parts
    # Every path prefix: "src", "src/migrations", "src/migrations/m001.py"
    prefixes = ["/".join(parts[: i + 1]) for i in range(len(parts))]
    candidates = (*parts, *prefixes)
    return any(fnmatch.fnmatch(c, pat) for pat in patterns for c in candidates)
