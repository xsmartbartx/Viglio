"""Evidence bundle types: the full sealed observation set a check runs
against (docs/modules.md §4: "Checks may not perform I/O. A check is a pure
function.") — as opposed to `models.Evidence`, which is the small, redacted
excerpt attached to one finding after the fact.

`Checks` may depend on Core only (docs/modules.md §4, enforced by
packages/checks/tests/test_import_boundary.py), so this type — which Checks
consume directly — lives here rather than in `packages/probes`, even though
Probes is what actually populates it.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime

from pydantic import BaseModel, Field


class CookieObservation(BaseModel):
    """Cookie flags only — never the value (docs/modules.md §3: probes never
    persist anything secret-shaped unredacted)."""

    name: str
    secure: bool
    http_only: bool
    same_site: str | None = None


class HttpObservation(BaseModel):
    """One HTTP probe's result. `body_excerpt` is capped at 8KB per
    docs/prooflight-vision-and-architecture.md §8.2."""

    url: str
    status_code: int
    headers: dict[str, str] = Field(default_factory=dict)
    cookies: list[CookieObservation] = Field(default_factory=list)
    redirect_chain: list[str] = Field(default_factory=list)
    body_excerpt: str = ""
    body_size: int = 0
    content_type: str | None = None
    elapsed_ms: float = 0.0


class TlsObservation(BaseModel):
    """A TLS handshake attempt. Cert-detail fields are `None` whenever the
    handshake didn't verify, so a check that needs them goes `inconclusive`
    rather than guessing (docs/prooflight-vision-and-architecture.md §16.3)."""

    attempted: bool
    verified: bool = False
    verify_error: str | None = None
    protocol_version: str | None = None
    cipher_name: str | None = None
    cert_subject: str | None = None
    cert_issuer: str | None = None
    not_before: datetime | None = None
    not_after: datetime | None = None
    days_until_expiry: int | None = None


class FingerprintObservation(BaseModel):
    """Signals derived from an already-captured HttpObservation — no new
    network I/O. Free-form strings rather than an enum since the signal set
    grows every phase; Phase 2's `bundle`/`render` probes will add more."""

    hosting_signals: list[str] = Field(default_factory=list)
    framework_signals: list[str] = Field(default_factory=list)


class EvidenceBundle(BaseModel):
    """The immutable, content-addressed evidence set one scan produces.

    `bundle_id` hashes everything except `captured_at`, so two scans that
    observe identical content always produce the same id regardless of when
    they ran (docs/architecture.md §8: "Evidence bundles are content-addressed
    and immutable.").
    """

    bundle_id: str
    target_origin: str
    captured_at: datetime
    http: HttpObservation | None = None
    tls: TlsObservation | None = None
    fingerprint: FingerprintObservation | None = None

    @staticmethod
    def compute_id(
        target_origin: str,
        http: HttpObservation | None,
        tls: TlsObservation | None,
        fingerprint: FingerprintObservation | None,
    ) -> str:
        payload = {
            "target_origin": target_origin,
            "http": http.model_dump(mode="json") if http else None,
            "tls": tls.model_dump(mode="json") if tls else None,
            "fingerprint": fingerprint.model_dump(mode="json") if fingerprint else None,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
