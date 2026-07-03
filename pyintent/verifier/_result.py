"""The result type produced by every verifier."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Status(Enum):
    PASS = "pass"
    FAIL = "fail"
    SKIPPED = "skipped"
    ERROR = "error"  # the verifier could not run (e.g. bad spec value)


@dataclass
class CheckResult:
    verifier: str  # "examples" | "properties" | "types" | "effects"
    target: str  # qualname of the spec'd thing
    status: Status
    summary: str = ""  # one-line outcome
    detail: str = ""  # full, paste-ready detail for a repair prompt
    label: str = ""  # sub-identifier, e.g. the ex case raw string

    @property
    def ok(self) -> bool:
        return self.status in (Status.PASS, Status.SKIPPED)

    @property
    def name(self) -> str:
        base = f"{self.target}::{self.verifier}"
        return f"{base}[{self.label}]" if self.label else base

    def to_dict(self) -> dict:
        return {
            "verifier": self.verifier,
            "target": self.target,
            "status": self.status.value,
            "summary": self.summary,
            "detail": self.detail,
            "label": self.label,
        }
