"""Secret redaction. The single sanctioned way any secret-shaped string enters
persistent storage, per docs/modules.md §1: never the value, only a fingerprint.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class Fingerprint:
    """A non-reversible stand-in for a secret value.

    Carries just enough shape to be useful in a finding or a report — kind,
    a short prefix for recognition, and length — without ever reconstructing
    the original value. `digest` is a SHA-256 hash of the full value, used
    only for equality checks (e.g. "did this same secret reappear"), never
    displayed in full.
    """

    kind: str
    prefix: str
    length: int
    digest: str

    def __str__(self) -> str:
        return f"{self.kind}:{self.prefix}…(len={self.length},sha256={self.digest[:8]})"


def redact(value: str, kind: str = "secret") -> Fingerprint:
    """Fingerprint a secret-shaped string. Never returns or logs `value` itself."""
    if not isinstance(value, str) or value == "":
        raise ValueError("redact() requires a non-empty string")

    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    prefix = value[:4]
    return Fingerprint(kind=kind, prefix=prefix, length=len(value), digest=digest)
