"""The TLS probe: one handshake against a pinned IP, stdlib only.

Uses `ssl.create_default_context()` defaults (`CERT_REQUIRED`,
`check_hostname=True`), so a *successful* handshake already proves both
chain trust and hostname match — "does it verify" is one fact, not two.
Cert-detail fields are only populated on success: extracting them from an
unverified connection would need the `cryptography` package to parse the
raw DER certificate (`getpeercert()` returns an empty dict without
validation), which is out of scope for Phase 1 — see docs/security.md.
"""

from __future__ import annotations

import socket
import ssl
from datetime import UTC, datetime

from vigilo_core.evidence import TlsObservation

_HANDSHAKE_TIMEOUT = 10.0
_CERT_TIME_FORMAT = "%b %d %H:%M:%S %Y %Z"


def _parse_cert_time(value: str) -> datetime:
    return datetime.strptime(value, _CERT_TIME_FORMAT).replace(tzinfo=UTC)


def _name_to_str(name_tuples: tuple) -> str:
    parts = [f"{k}={v}" for rdn in name_tuples for k, v in rdn]
    return ", ".join(parts)


def run_tls(host: str, pinned_ip: str, port: int) -> TlsObservation:
    """Attempt one TLS handshake to `pinned_ip:port` with SNI/hostname
    verification against `host`. Never raises for TLS-level failures — those
    are recorded in the observation so checks can go `inconclusive` rather
    than crash the scan."""
    context = ssl.create_default_context()

    try:
        with socket.create_connection((pinned_ip, port), timeout=_HANDSHAKE_TIMEOUT) as sock:
            with context.wrap_socket(sock, server_hostname=host) as tls_sock:
                cert = tls_sock.getpeercert()
                cipher = tls_sock.cipher()
                protocol_version = tls_sock.version()
    except ssl.SSLCertVerificationError as exc:
        return TlsObservation(attempted=True, verified=False, verify_error=str(exc))
    except (ssl.SSLError, OSError) as exc:
        return TlsObservation(attempted=True, verified=False, verify_error=f"{type(exc).__name__}: {exc}")

    not_before = _parse_cert_time(cert["notBefore"]) if cert.get("notBefore") else None
    not_after = _parse_cert_time(cert["notAfter"]) if cert.get("notAfter") else None
    days_until_expiry = (not_after - datetime.now(UTC)).days if not_after else None

    return TlsObservation(
        attempted=True,
        verified=True,
        protocol_version=protocol_version,
        cipher_name=cipher[0] if cipher else None,
        cert_subject=_name_to_str(cert.get("subject", ())),
        cert_issuer=_name_to_str(cert.get("issuer", ())),
        not_before=not_before,
        not_after=not_after,
        days_until_expiry=days_until_expiry,
    )
