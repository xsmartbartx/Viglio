"""TLS category: transport checks. 8 checks, v0.1 target per
docs/prooflight-vision-and-architecture.md §7.2.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from vigilo_core.evidence import EvidenceBundle
from vigilo_core.models import CheckManifest, Confidence, Severity, Tier, Verdict
from vigilo_checks.registry import Check, CheckResult, requires

_WEAK_PROTOCOLS = {"SSLv2", "SSLv3", "TLSv1", "TLSv1.1"}
_WEAK_CIPHER_MARKERS = ("RC4", "3DES", "NULL", "EXPORT", "MD5")
_MIXED_CONTENT_PATTERN = re.compile(r'(?:src|href)\s*=\s*["\']http://', re.IGNORECASE)
_CA_BROWSER_FORUM_MAX_VALIDITY_DAYS = 398


# --- VG-TLS-001: HTTPS enforced -----------------------------------------------


@requires("http")
def _https_enforced(bundle: EvidenceBundle) -> CheckResult:
    if bundle.http.url.startswith("https://"):
        return CheckResult(Verdict.PASSED, f"Final response served over HTTPS: {bundle.http.url}")
    return CheckResult(Verdict.FAILED, f"Final response served over plaintext HTTP: {bundle.http.url}")


CHECK_HTTPS_ENFORCED = Check(
    manifest=CheckManifest(
        check_id="VG-TLS-001",
        category="TLS",
        title="HTTPS is enforced",
        description="The site must be reachable over HTTPS, either directly or via an HTTP-to-HTTPS redirect, not served in plaintext.",
        severity_default=Severity.CRITICAL,
        confidence=Confidence.CONFIRMED,
        weight=10,
        tier_required=Tier.PASSIVE,
        references=["https://developer.mozilla.org/en-US/docs/Web/Security/Transport_Layer_Security"],
        remediation_template="Terminate TLS at your host/CDN and redirect all HTTP traffic to HTTPS.",
        introduced_in="0.1",
    ),
    evaluate=_https_enforced,
)


# --- VG-TLS-002: handshake verifies -------------------------------------------


@requires("tls")
def _handshake_verifies(bundle: EvidenceBundle) -> CheckResult:
    tls = bundle.tls
    if tls.verified:
        return CheckResult(Verdict.PASSED, f"TLS handshake verified ({tls.protocol_version})")
    return CheckResult(Verdict.FAILED, f"TLS handshake did not verify: {tls.verify_error}")


CHECK_HANDSHAKE_VERIFIES = Check(
    manifest=CheckManifest(
        check_id="VG-TLS-002",
        category="TLS",
        title="TLS certificate chain verifies",
        description="The certificate must chain to a trusted CA and match the requested hostname — this single check covers both trust and hostname validation, since a default TLS context enforces both together.",
        severity_default=Severity.CRITICAL,
        confidence=Confidence.CONFIRMED,
        weight=10,
        tier_required=Tier.PASSIVE,
        references=["https://developer.mozilla.org/en-US/docs/Web/Security/Transport_Layer_Security"],
        remediation_template="Install a certificate from a publicly trusted CA that covers this exact hostname (or its wildcard).",
        introduced_in="0.1",
    ),
    evaluate=_handshake_verifies,
)


# --- VG-TLS-003: certificate not expired --------------------------------------


@requires("tls")
def _cert_not_expired(bundle: EvidenceBundle) -> CheckResult:
    not_after = bundle.tls.not_after
    if not_after is None:
        return CheckResult(Verdict.INCONCLUSIVE, "no certificate expiry evidence available")
    if not_after > datetime.now(UTC):
        return CheckResult(Verdict.PASSED, f"Certificate valid until {not_after.isoformat()}")
    return CheckResult(Verdict.FAILED, f"Certificate expired on {not_after.isoformat()}")


CHECK_CERT_NOT_EXPIRED = Check(
    manifest=CheckManifest(
        check_id="VG-TLS-003",
        category="TLS",
        title="Certificate is not expired",
        description="An expired certificate breaks TLS for every visitor and every browser will refuse the connection.",
        severity_default=Severity.CRITICAL,
        confidence=Confidence.CONFIRMED,
        weight=10,
        tier_required=Tier.PASSIVE,
        references=["https://developer.mozilla.org/en-US/docs/Web/Security/Transport_Layer_Security"],
        remediation_template="Renew the TLS certificate immediately.",
        introduced_in="0.1",
    ),
    evaluate=_cert_not_expired,
)


# --- VG-TLS-004: certificate not expiring within 14 days ----------------------


@requires("tls")
def _cert_not_expiring_soon(bundle: EvidenceBundle) -> CheckResult:
    days = bundle.tls.days_until_expiry
    if days is None:
        return CheckResult(Verdict.INCONCLUSIVE, "no certificate expiry evidence available")
    if days <= 14:
        return CheckResult(Verdict.FAILED, f"Certificate expires in {days} day(s)")
    return CheckResult(Verdict.PASSED, f"Certificate has {days} days of validity remaining")


CHECK_CERT_NOT_EXPIRING_SOON = Check(
    manifest=CheckManifest(
        check_id="VG-TLS-004",
        category="TLS",
        title="Certificate is not about to expire",
        description="An early warning before a certificate lapses, since auto-renewal failures are a common cause of production outages.",
        severity_default=Severity.MEDIUM,
        confidence=Confidence.CONFIRMED,
        weight=3,
        tier_required=Tier.PASSIVE,
        references=["https://developer.mozilla.org/en-US/docs/Web/Security/Transport_Layer_Security"],
        remediation_template="Renew the certificate now, or fix whatever is blocking auto-renewal (ACME/Let's Encrypt renewal job, DNS validation, etc.).",
        introduced_in="0.1",
    ),
    evaluate=_cert_not_expiring_soon,
)


# --- VG-TLS-005: modern protocol version --------------------------------------


@requires("tls")
def _protocol_version_modern(bundle: EvidenceBundle) -> CheckResult:
    version = bundle.tls.protocol_version
    if version is None:
        return CheckResult(Verdict.INCONCLUSIVE, "no negotiated protocol version available")
    if version in _WEAK_PROTOCOLS:
        return CheckResult(Verdict.FAILED, f"Negotiated outdated protocol {version}", version)
    return CheckResult(Verdict.PASSED, f"Negotiated protocol {version}", version)


CHECK_PROTOCOL_VERSION_MODERN = Check(
    manifest=CheckManifest(
        check_id="VG-TLS-005",
        category="TLS",
        title="TLS protocol version is 1.2 or higher",
        description="TLS 1.0 and 1.1 have known weaknesses and are deprecated by every major browser and RFC 8996.",
        severity_default=Severity.HIGH,
        confidence=Confidence.CONFIRMED,
        weight=6,
        tier_required=Tier.PASSIVE,
        references=["https://www.rfc-editor.org/rfc/rfc8996"],
        remediation_template="Disable TLS 1.0/1.1 in your server or load balancer's TLS configuration; require TLS 1.2 or 1.3.",
        introduced_in="0.1",
    ),
    evaluate=_protocol_version_modern,
)


# --- VG-TLS-006: no mixed content ----------------------------------------------


@requires("http")
def _no_mixed_content(bundle: EvidenceBundle) -> CheckResult:
    if not bundle.http.url.startswith("https://"):
        return CheckResult(Verdict.NOT_APPLICABLE, "page is not served over HTTPS")
    if _MIXED_CONTENT_PATTERN.search(bundle.http.body_excerpt):
        return CheckResult(Verdict.FAILED, "page references http:// resources while served over https")
    return CheckResult(Verdict.PASSED, "no obvious mixed-content references found")


CHECK_NO_MIXED_CONTENT = Check(
    manifest=CheckManifest(
        check_id="VG-TLS-006",
        category="TLS",
        title="No mixed content",
        description="An HTTPS page that loads http:// subresources lets a network attacker tamper with those resources even though the page itself is encrypted.",
        severity_default=Severity.MEDIUM,
        confidence=Confidence.INDICATED,
        weight=3,
        tier_required=Tier.PASSIVE,
        references=["https://developer.mozilla.org/en-US/docs/Web/Security/Mixed_content"],
        remediation_template="Change every http:// resource reference to https:// (or a protocol-relative/relative URL).",
        false_positive_notes="This is a regex over the first 8KB of the HTML body only — resources referenced from JS or below that cutoff are not seen.",
        introduced_in="0.1",
    ),
    evaluate=_no_mixed_content,
)


# --- VG-TLS-007: certificate validity window within CA/Browser Forum baseline -


@requires("tls")
def _cert_validity_window(bundle: EvidenceBundle) -> CheckResult:
    tls = bundle.tls
    if tls.not_before is None or tls.not_after is None:
        return CheckResult(Verdict.INCONCLUSIVE, "no certificate validity window evidence available")
    days = (tls.not_after - tls.not_before).days
    if days <= _CA_BROWSER_FORUM_MAX_VALIDITY_DAYS:
        return CheckResult(Verdict.PASSED, f"certificate validity window is {days} days")
    return CheckResult(
        Verdict.FAILED,
        f"certificate validity window is {days} days "
        f"(exceeds the {_CA_BROWSER_FORUM_MAX_VALIDITY_DAYS}-day CA/Browser Forum baseline)",
    )


CHECK_CERT_VALIDITY_WINDOW = Check(
    manifest=CheckManifest(
        check_id="VG-TLS-007",
        category="TLS",
        title="Certificate validity window follows the CA/Browser Forum baseline",
        description="Certificates issued for longer than 398 days violate the CA/Browser Forum Baseline Requirements and browsers may reject them outright.",
        severity_default=Severity.LOW,
        confidence=Confidence.CONFIRMED,
        weight=2,
        tier_required=Tier.PASSIVE,
        references=["https://cabforum.org/baseline-requirements/"],
        remediation_template="Reissue the certificate with a validity period of 398 days or fewer.",
        introduced_in="0.1",
    ),
    evaluate=_cert_validity_window,
)


# --- VG-TLS-008: no legacy-weak cipher negotiated ------------------------------


@requires("tls")
def _no_weak_cipher(bundle: EvidenceBundle) -> CheckResult:
    cipher = bundle.tls.cipher_name
    if cipher is None:
        return CheckResult(Verdict.INCONCLUSIVE, "no negotiated cipher evidence available")
    upper = cipher.upper()
    if any(marker in upper for marker in _WEAK_CIPHER_MARKERS):
        return CheckResult(Verdict.FAILED, f"Negotiated a legacy-weak cipher: {cipher}", cipher)
    return CheckResult(Verdict.PASSED, f"Negotiated cipher: {cipher}", cipher)


CHECK_NO_WEAK_CIPHER = Check(
    manifest=CheckManifest(
        check_id="VG-TLS-008",
        category="TLS",
        title="No legacy-weak cipher negotiated",
        description="RC4, 3DES, NULL, export-grade and MD5-based ciphers are all broken or badly weakened and should never be negotiable.",
        severity_default=Severity.HIGH,
        confidence=Confidence.CONFIRMED,
        weight=5,
        tier_required=Tier.PASSIVE,
        references=["https://developer.mozilla.org/en-US/docs/Web/Security/Transport_Layer_Security"],
        remediation_template="Remove legacy cipher suites (RC4, 3DES, NULL, EXPORT, MD5-based) from your server's TLS configuration.",
        introduced_in="0.1",
    ),
    evaluate=_no_weak_cipher,
)


CHECKS: list[Check] = [
    CHECK_HTTPS_ENFORCED,
    CHECK_HANDSHAKE_VERIFIES,
    CHECK_CERT_NOT_EXPIRED,
    CHECK_CERT_NOT_EXPIRING_SOON,
    CHECK_PROTOCOL_VERSION_MODERN,
    CHECK_NO_MIXED_CONTENT,
    CHECK_CERT_VALIDITY_WINDOW,
    CHECK_NO_WEAK_CIPHER,
]
