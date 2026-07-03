"""Exception types raised by pyintent."""

from __future__ import annotations


class PyIntentError(Exception):
    """Base class for every error pyintent raises."""


class PyIntentSpecError(PyIntentError):
    """A spec is malformed.

    Raised eagerly at decoration / construction time (never during verification)
    so that a bad spec fails as soon as the module is imported.
    """
