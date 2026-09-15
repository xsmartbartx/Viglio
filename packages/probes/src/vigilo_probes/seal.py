"""Sealing: turn the observations collected for one target into an
immutable, content-addressed EvidenceBundle."""

from __future__ import annotations

from datetime import UTC, datetime

from vigilo_core.evidence import (
    BackendObservation,
    BundleObservation,
    EvidenceBundle,
    FingerprintObservation,
    HttpObservation,
    PathObservation,
    TlsObservation,
    WellKnownObservation,
)


def seal(
    target_origin: str,
    http: HttpObservation | None,
    tls: TlsObservation | None,
    fingerprint: FingerprintObservation | None,
    bundle: BundleObservation | None = None,
    wellknown: WellKnownObservation | None = None,
    backends: BackendObservation | None = None,
    paths: PathObservation | None = None,
) -> EvidenceBundle:
    bundle_id = EvidenceBundle.compute_id(
        target_origin, http, tls, fingerprint, bundle, wellknown, backends, paths
    )
    return EvidenceBundle(
        bundle_id=bundle_id,
        target_origin=target_origin,
        captured_at=datetime.now(UTC),
        http=http,
        tls=tls,
        fingerprint=fingerprint,
        bundle=bundle,
        wellknown=wellknown,
        backends=backends,
        paths=paths,
    )
