"""Shared fixtures for the pyintent test suite."""

from __future__ import annotations

import pytest

from pyintent._discovery import discover_in_module
from pyintent._loader import import_file

pytest_plugins = ["pytester"]


@pytest.fixture
def make_module(tmp_path):
    """Write Python source to a temp file and import it as a module."""
    counter = {"n": 0}

    def _make(code: str):
        counter["n"] += 1
        path = tmp_path / f"mod_{counter['n']}.py"
        path.write_text(code, encoding="utf-8")
        return import_file(path)

    return _make


@pytest.fixture
def target_for():
    """Return a helper that finds a discovered SpecTarget by name."""

    def _find(module, name):
        for t in discover_in_module(module):
            if t.spec.target_name == name:
                return t
        raise AssertionError(f"no spec target named {name!r} in {module.__name__}")

    return _find
