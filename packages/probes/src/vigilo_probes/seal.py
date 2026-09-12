"""Sealing: turn the observations collected for one target into an
immutable, content-addressed EvidenceBundle."""

from __future__ import annotations

from datetime import UTC, datetime

from vigilo_core.evidence import EvidenceBundle, FingerprintObservation, HttpObservation, TlsObservation


def seal(
    target_origin: str,
    http: HttpObservation | None,
    tls: TlsObservation | None,
    fingerprint: FingerprintObservation | None,
) -> EvidenceBundle:
    bundle_id = EvidenceBundle.compute_id(target_origin, http, tls, fingerprint)
    return EvidenceBundle(
        bundle_id=bundle_id,
        target_origin=target_origin,
        captured_at=datetime.now(UTC),
        http=http,
        tls=tls,
        fingerprint=fingerprint,
    )
