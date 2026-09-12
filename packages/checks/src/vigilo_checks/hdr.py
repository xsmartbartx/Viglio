"""HDR category: response header checks. 12 checks, v0.1 target per
docs/prooflight-vision-and-architecture.md §7.2.
"""

from __future__ import annotations

import re

from vigilo_checks.registry import Check, CheckResult, get_header, requires
from vigilo_core.evidence import EvidenceBundle
from vigilo_core.models import CheckManifest, Confidence, Severity, Tier, Verdict

_VERSION_PATTERN = re.compile(r"\d+\.\d+")
_SIX_MONTHS_SECONDS = 15_768_000


def _parse_hsts(value: str) -> dict[str, str | None]:
    """HSTS directives are `;`-separated `key=value` pairs or bare flags,
    e.g. `max-age=31536000; includeSubDomains` — distinct from CSP's grammar
    below, which is space-separated within each directive."""
    directives: dict[str, str | None] = {}
    for part in value.split(";"):
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            key, _, val = part.partition("=")
            directives[key.strip().lower()] = val.strip().strip('"')
        else:
            directives[part.lower()] = None
    return directives


def _parse_csp(value: str) -> dict[str, list[str]]:
    """CSP directives are `;`-separated `directive token token ...` groups,
    e.g. `default-src 'self'; script-src 'self' 'unsafe-inline'`."""
    directives: dict[str, list[str]] = {}
    for part in value.split(";"):
        tokens = part.strip().split()
        if not tokens:
            continue
        directives[tokens[0].lower()] = tokens[1:]
    return directives


# --- VG-HDR-001: HSTS present ------------------------------------------------


@requires("http")
def _hsts_present(bundle: EvidenceBundle) -> CheckResult:
    value = get_header(bundle.http.headers, "strict-transport-security")
    if value:
        return CheckResult(Verdict.PASSED, "Strict-Transport-Security header is present", value)
    return CheckResult(Verdict.FAILED, "Strict-Transport-Security header is missing")


CHECK_HSTS_PRESENT = Check(
    manifest=CheckManifest(
        check_id="VG-HDR-001",
        category="HDR",
        title="HSTS enforced",
        description="The response must include a Strict-Transport-Security header so browsers refuse plaintext HTTP for this origin after the first visit.",
        severity_default=Severity.HIGH,
        confidence=Confidence.CONFIRMED,
        weight=8,
        tier_required=Tier.PASSIVE,
        references=["https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Strict-Transport-Security"],
        remediation_template="Add a `Strict-Transport-Security: max-age=31536000; includeSubDomains` response header.",
        introduced_in="0.1",
    ),
    evaluate=_hsts_present,
)


# --- VG-HDR-002: HSTS max-age long enough ------------------------------------


@requires("http")
def _hsts_max_age(bundle: EvidenceBundle) -> CheckResult:
    value = get_header(bundle.http.headers, "strict-transport-security")
    if not value:
        return CheckResult(Verdict.INCONCLUSIVE, "no Strict-Transport-Security header to evaluate")

    directives = _parse_hsts(value)
    raw = directives.get("max-age")
    if raw is None:
        return CheckResult(Verdict.FAILED, "Strict-Transport-Security has no max-age directive")

    try:
        max_age = int(raw)
    except ValueError:
        return CheckResult(Verdict.FAILED, f"Strict-Transport-Security max-age is not numeric: {raw!r}")

    if max_age >= _SIX_MONTHS_SECONDS:
        return CheckResult(Verdict.PASSED, f"HSTS max-age is {max_age}s (>= 6 months)")
    return CheckResult(Verdict.FAILED, f"HSTS max-age is only {max_age}s (< 6 months)")


CHECK_HSTS_MAX_AGE = Check(
    manifest=CheckManifest(
        check_id="VG-HDR-002",
        category="HDR",
        title="HSTS max-age is long enough",
        description="An HSTS max-age shorter than 6 months gives only brief protection between deploys.",
        severity_default=Severity.MEDIUM,
        confidence=Confidence.CONFIRMED,
        weight=4,
        tier_required=Tier.PASSIVE,
        references=["https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Strict-Transport-Security"],
        remediation_template="Set `max-age=31536000` (one year) or more on the Strict-Transport-Security header.",
        introduced_in="0.1",
    ),
    evaluate=_hsts_max_age,
)


# --- VG-HDR-003: HSTS includeSubDomains --------------------------------------


@requires("http")
def _hsts_include_subdomains(bundle: EvidenceBundle) -> CheckResult:
    value = get_header(bundle.http.headers, "strict-transport-security")
    if not value:
        return CheckResult(Verdict.INCONCLUSIVE, "no Strict-Transport-Security header to evaluate")

    directives = _parse_hsts(value)
    if "includesubdomains" in directives:
        return CheckResult(Verdict.PASSED, "HSTS includes includeSubDomains")
    return CheckResult(Verdict.FAILED, "HSTS is missing includeSubDomains")


CHECK_HSTS_INCLUDE_SUBDOMAINS = Check(
    manifest=CheckManifest(
        check_id="VG-HDR-003",
        category="HDR",
        title="HSTS covers subdomains",
        description="Without includeSubDomains, a single insecure subdomain can still be attacked over plaintext HTTP.",
        severity_default=Severity.LOW,
        confidence=Confidence.CONFIRMED,
        weight=2,
        tier_required=Tier.PASSIVE,
        references=["https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Strict-Transport-Security"],
        remediation_template="Add `includeSubDomains` to the Strict-Transport-Security header.",
        introduced_in="0.1",
    ),
    evaluate=_hsts_include_subdomains,
)


# --- VG-HDR-004: CSP present --------------------------------------------------


@requires("http")
def _csp_present(bundle: EvidenceBundle) -> CheckResult:
    value = get_header(bundle.http.headers, "content-security-policy")
    if value:
        return CheckResult(Verdict.PASSED, "Content-Security-Policy header is present", value)
    return CheckResult(Verdict.FAILED, "Content-Security-Policy header is missing")


CHECK_CSP_PRESENT = Check(
    manifest=CheckManifest(
        check_id="VG-HDR-004",
        category="HDR",
        title="Content-Security-Policy present",
        description="A CSP restricts which origins can supply scripts, styles and other resources, containing the blast radius of an XSS bug.",
        severity_default=Severity.HIGH,
        confidence=Confidence.CONFIRMED,
        weight=7,
        tier_required=Tier.PASSIVE,
        references=["https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Security-Policy"],
        remediation_template="Add a Content-Security-Policy header starting from `default-src 'self'` and widening only as needed.",
        introduced_in="0.1",
    ),
    evaluate=_csp_present,
)


# --- VG-HDR-005: CSP does not allow unsafe-inline scripts --------------------


@requires("http")
def _csp_no_unsafe_inline(bundle: EvidenceBundle) -> CheckResult:
    value = get_header(bundle.http.headers, "content-security-policy")
    if not value:
        return CheckResult(Verdict.INCONCLUSIVE, "no Content-Security-Policy header to evaluate")

    directives = _parse_csp(value)
    relevant = directives.get("script-src") or directives.get("default-src") or []
    if any("unsafe-inline" in token for token in relevant):
        return CheckResult(Verdict.FAILED, "CSP allows 'unsafe-inline' script execution", value)
    return CheckResult(Verdict.PASSED, "CSP does not allow unsafe-inline scripts")


CHECK_CSP_NO_UNSAFE_INLINE = Check(
    manifest=CheckManifest(
        check_id="VG-HDR-005",
        category="HDR",
        title="CSP forbids unsafe-inline scripts",
        description="'unsafe-inline' in script-src/default-src defeats most of a CSP's XSS protection.",
        severity_default=Severity.MEDIUM,
        confidence=Confidence.INDICATED,
        weight=4,
        tier_required=Tier.PASSIVE,
        references=["https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Security-Policy/script-src"],
        remediation_template="Remove 'unsafe-inline' from script-src/default-src; use nonces or hashes for any inline scripts you need.",
        false_positive_notes="A CSP that relies entirely on 'strict-dynamic' with nonces may still list 'unsafe-inline' as a fallback for old browsers, which is intentional and not a real weakness.",
        introduced_in="0.1",
    ),
    evaluate=_csp_no_unsafe_inline,
)


# --- VG-HDR-006: X-Content-Type-Options: nosniff -----------------------------


@requires("http")
def _x_content_type_options(bundle: EvidenceBundle) -> CheckResult:
    value = get_header(bundle.http.headers, "x-content-type-options")
    if value and value.strip().lower() == "nosniff":
        return CheckResult(Verdict.PASSED, "X-Content-Type-Options: nosniff is set")
    if value:
        return CheckResult(Verdict.FAILED, f"X-Content-Type-Options has an unexpected value: {value}", value)
    return CheckResult(Verdict.FAILED, "X-Content-Type-Options header is missing")


CHECK_X_CONTENT_TYPE_OPTIONS = Check(
    manifest=CheckManifest(
        check_id="VG-HDR-006",
        category="HDR",
        title="MIME-sniffing protection",
        description="Without nosniff, browsers may execute a response as a different content type than declared, enabling some XSS vectors.",
        severity_default=Severity.LOW,
        confidence=Confidence.CONFIRMED,
        weight=2,
        tier_required=Tier.PASSIVE,
        references=["https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/X-Content-Type-Options"],
        remediation_template="Add `X-Content-Type-Options: nosniff` to every response.",
        introduced_in="0.1",
    ),
    evaluate=_x_content_type_options,
)


# --- VG-HDR-007: clickjacking protection -------------------------------------


@requires("http")
def _clickjacking_protection(bundle: EvidenceBundle) -> CheckResult:
    xfo = get_header(bundle.http.headers, "x-frame-options")
    if xfo and xfo.strip().lower() in ("deny", "sameorigin"):
        return CheckResult(Verdict.PASSED, f"X-Frame-Options: {xfo}", xfo)

    csp = get_header(bundle.http.headers, "content-security-policy")
    if csp and "frame-ancestors" in _parse_csp(csp):
        return CheckResult(Verdict.PASSED, "CSP frame-ancestors restricts framing", csp)

    return CheckResult(Verdict.FAILED, "No X-Frame-Options or CSP frame-ancestors protection found")


CHECK_CLICKJACKING_PROTECTION = Check(
    manifest=CheckManifest(
        check_id="VG-HDR-007",
        category="HDR",
        title="Clickjacking protection",
        description="Without X-Frame-Options or a CSP frame-ancestors directive, the page can be embedded in a hostile iframe.",
        severity_default=Severity.MEDIUM,
        confidence=Confidence.CONFIRMED,
        weight=4,
        tier_required=Tier.PASSIVE,
        references=["https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/X-Frame-Options"],
        remediation_template="Add `X-Frame-Options: DENY` (or `SAMEORIGIN`), or a CSP `frame-ancestors` directive.",
        introduced_in="0.1",
    ),
    evaluate=_clickjacking_protection,
)


# --- VG-HDR-008: Referrer-Policy ----------------------------------------------


@requires("http")
def _referrer_policy(bundle: EvidenceBundle) -> CheckResult:
    value = get_header(bundle.http.headers, "referrer-policy")
    if not value:
        return CheckResult(Verdict.FAILED, "Referrer-Policy header is missing")
    if value.strip().lower() == "unsafe-url":
        return CheckResult(Verdict.FAILED, "Referrer-Policy is set to the unsafe-url value", value)
    return CheckResult(Verdict.PASSED, f"Referrer-Policy: {value}", value)


CHECK_REFERRER_POLICY = Check(
    manifest=CheckManifest(
        check_id="VG-HDR-008",
        category="HDR",
        title="Referrer-Policy is set and safe",
        description="A missing or unsafe-url Referrer-Policy can leak full URLs (sometimes containing tokens) to third-party destinations.",
        severity_default=Severity.LOW,
        confidence=Confidence.CONFIRMED,
        weight=2,
        tier_required=Tier.PASSIVE,
        references=["https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Referrer-Policy"],
        remediation_template="Add `Referrer-Policy: strict-origin-when-cross-origin` (or stricter).",
        introduced_in="0.1",
    ),
    evaluate=_referrer_policy,
)


# --- VG-HDR-009: Permissions-Policy -------------------------------------------


@requires("http")
def _permissions_policy(bundle: EvidenceBundle) -> CheckResult:
    value = get_header(bundle.http.headers, "permissions-policy")
    if value:
        return CheckResult(Verdict.PASSED, "Permissions-Policy header is present", value)
    return CheckResult(Verdict.FAILED, "Permissions-Policy header is missing")


CHECK_PERMISSIONS_POLICY = Check(
    manifest=CheckManifest(
        check_id="VG-HDR-009",
        category="HDR",
        title="Permissions-Policy present",
        description="Without a Permissions-Policy, embedded or compromised third-party scripts can access powerful browser features (camera, geolocation, etc.) by default.",
        severity_default=Severity.LOW,
        confidence=Confidence.CONFIRMED,
        weight=1,
        tier_required=Tier.PASSIVE,
        references=["https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Permissions-Policy"],
        remediation_template="Add a Permissions-Policy header disabling features the site doesn't use, e.g. `camera=(), microphone=(), geolocation=()`.",
        introduced_in="0.1",
    ),
    evaluate=_permissions_policy,
)


# --- VG-HDR-010: Server header doesn't leak a version ------------------------


@requires("http")
def _server_header_no_version(bundle: EvidenceBundle) -> CheckResult:
    value = get_header(bundle.http.headers, "server")
    if not value:
        return CheckResult(Verdict.PASSED, "No Server header to leak a version from")
    if _VERSION_PATTERN.search(value):
        return CheckResult(Verdict.FAILED, f"Server header discloses a version number: {value}", value)
    return CheckResult(Verdict.PASSED, f"Server header does not disclose a version: {value}", value)


CHECK_SERVER_NO_VERSION = Check(
    manifest=CheckManifest(
        check_id="VG-HDR-010",
        category="HDR",
        title="Server header doesn't disclose a version",
        description="A Server header with a specific version number helps an attacker match it against known vulnerabilities for that exact release.",
        severity_default=Severity.INFO,
        confidence=Confidence.INDICATED,
        weight=1,
        tier_required=Tier.PASSIVE,
        references=["https://owasp.org/www-project-web-security-testing-guide/"],
        remediation_template="Configure the server/proxy to omit or generalize the Server header (no version number).",
        false_positive_notes="Some CDNs include a version-shaped string that is actually a static product identifier, not a real version signal.",
        introduced_in="0.1",
    ),
    evaluate=_server_header_no_version,
)


# --- VG-HDR-011: X-Powered-By absent ------------------------------------------


@requires("http")
def _x_powered_by_absent(bundle: EvidenceBundle) -> CheckResult:
    value = get_header(bundle.http.headers, "x-powered-by")
    if value:
        return CheckResult(Verdict.FAILED, f"X-Powered-By discloses the backend: {value}", value)
    return CheckResult(Verdict.PASSED, "X-Powered-By header is absent")


CHECK_X_POWERED_BY_ABSENT = Check(
    manifest=CheckManifest(
        check_id="VG-HDR-011",
        category="HDR",
        title="X-Powered-By is absent",
        description="X-Powered-By discloses the backend framework/language, narrowing an attacker's search for a matching exploit.",
        severity_default=Severity.INFO,
        confidence=Confidence.CONFIRMED,
        weight=1,
        tier_required=Tier.PASSIVE,
        references=["https://owasp.org/www-project-secure-headers/"],
        remediation_template="Disable the X-Powered-By header in your framework's configuration.",
        introduced_in="0.1",
    ),
    evaluate=_x_powered_by_absent,
)


# --- VG-HDR-012: Content-Type present -----------------------------------------


@requires("http")
def _content_type_present(bundle: EvidenceBundle) -> CheckResult:
    if bundle.http.content_type:
        return CheckResult(Verdict.PASSED, f"Content-Type: {bundle.http.content_type}")
    return CheckResult(Verdict.FAILED, "Response has no Content-Type header")


CHECK_CONTENT_TYPE_PRESENT = Check(
    manifest=CheckManifest(
        check_id="VG-HDR-012",
        category="HDR",
        title="Content-Type is present",
        description="A missing Content-Type leaves the response's interpretation up to the browser's own sniffing heuristics, which is unpredictable and sometimes exploitable.",
        severity_default=Severity.LOW,
        confidence=Confidence.CONFIRMED,
        weight=1,
        tier_required=Tier.PASSIVE,
        references=["https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Type"],
        remediation_template="Set an explicit Content-Type header on every response.",
        introduced_in="0.1",
    ),
    evaluate=_content_type_present,
)


CHECKS: list[Check] = [
    CHECK_HSTS_PRESENT,
    CHECK_HSTS_MAX_AGE,
    CHECK_HSTS_INCLUDE_SUBDOMAINS,
    CHECK_CSP_PRESENT,
    CHECK_CSP_NO_UNSAFE_INLINE,
    CHECK_X_CONTENT_TYPE_OPTIONS,
    CHECK_CLICKJACKING_PROTECTION,
    CHECK_REFERRER_POLICY,
    CHECK_PERMISSIONS_POLICY,
    CHECK_SERVER_NO_VERSION,
    CHECK_X_POWERED_BY_ABSENT,
    CHECK_CONTENT_TYPE_PRESENT,
]
