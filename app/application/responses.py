"""
Response envelope, per docs/contracts/response-model.md.

Every command handler returns a plain dict shaped like this module's
`ok()`/`fail()` output -- never a bare domain object and never a raised
exception for expected failure modes (only for genuine bugs).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ErrorPayload:
    code: str
    message: str


@dataclass(frozen=True)
class Envelope:
    success: bool
    data: Any | None
    error: ErrorPayload | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": asdict(self.error) if self.error is not None else None,
        }


def ok(data: Any) -> dict[str, Any]:
    """Build a success envelope, per docs/contracts/response-model.md."""
    return Envelope(success=True, data=data, error=None).to_dict()


def fail(code: str, message: str) -> dict[str, Any]:
    """Build a failure envelope, per docs/contracts/response-model.md."""
    return Envelope(success=False, data=None, error=ErrorPayload(code, message)).to_dict()
