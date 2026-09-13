"""SES category: cookie and session-management checks. 6 checks, v0.1 target
per docs/prooflight-vision-and-architecture.md §7.2.
"""

from __future__ import annotations

import re

from vigilo_core.evidence import EvidenceBundle
from vigilo_core.models import CheckManifest, Confidence, Severity, Tier, Verdict
from vigilo_checks.registry import Check, CheckResult, requires

_SESSION_ID_IN_URL_PATTERN = re.compile(
    r'(?:href|src)\s*=\s*["\'][^"\']*[?&]'
    r"(?:PHPSESSID|JSESSIONID|sid|session_id|sessionid|auth_token)=",
    re.IGNORECASE,
)
_SESSION_NAME_PATTERN = re.compile(r"(session|sid|auth|token)", re.IGNORECASE)
_MAX_SESSION_COOKIE_AGE = 30 * 24 * 3600  # 30 days


# --- VG-SES-001: cookies use Secure ------------------------------------------


@requires("http")
def _cookies_secure(bundle: EvidenceBundle) -> CheckResult:
    cookies = bundle.http.cookies
    if not cookies:
        return CheckResult(Verdict.PASSED, "no cookies set")
    offenders = [c.name for c in cookies if not c.secure]
    if offenders:
        detail = f"cookie(s) missing Secure: {', '.join(offenders)}"
        return CheckResult(Verdict.FAILED, detail, ", ".join(offenders))
    return CheckResult(Verdict.PASSED, "all cookies set Secure")


CHECK_COOKIES_SECURE = Check(
    manifest=CheckManifest(
        check_id="VG-SES-001",
        category="SES",
        title="Cookies use the Secure attribute",
        description="A cookie without Secure can be sent over plaintext HTTP, exposing it to network eavesdroppers.",
        severity_default=Severity.HIGH,
        confidence=Confidence.CONFIRMED,
        weight=6,
        tier_required=Tier.PASSIVE,
        references=["https://developer.mozilla.org/en-US/docs/Web/HTTP/Cookies#restrict_access_to_cookies"],
        remediation_template="Add the `Secure` attribute to every cookie your application sets.",
        introduced_in="0.1",
    ),
    evaluate=_cookies_secure,
)


# --- VG-SES-002: cookies use HttpOnly -----------------------------------------


@requires("http")
def _cookies_http_only(bundle: EvidenceBundle) -> CheckResult:
    cookies = bundle.http.cookies
    if not cookies:
        return CheckResult(Verdict.PASSED, "no cookies set")
    offenders = [c.name for c in cookies if not c.http_only]
    if offenders:
        detail = f"cookie(s) missing HttpOnly: {', '.join(offenders)}"
        return CheckResult(Verdict.FAILED, detail, ", ".join(offenders))
    return CheckResult(Verdict.PASSED, "all cookies set HttpOnly")


CHECK_COOKIES_HTTP_ONLY = Check(
    manifest=CheckManifest(
        check_id="VG-SES-002",
        category="SES",
        title="Cookies use the HttpOnly attribute",
        description="A cookie without HttpOnly can be read by client-side JavaScript, making it a target for XSS-based theft.",
        severity_default=Severity.HIGH,
        confidence=Confidence.CONFIRMED,
        weight=6,
        tier_required=Tier.PASSIVE,
        references=["https://developer.mozilla.org/en-US/docs/Web/HTTP/Cookies#restrict_access_to_cookies"],
        remediation_template="Add the `HttpOnly` attribute to every cookie that doesn't need JavaScript access.",
        introduced_in="0.1",
    ),
    evaluate=_cookies_http_only,
)


# --- VG-SES-003: cookies set SameSite explicitly ------------------------------


@requires("http")
def _cookies_samesite_set(bundle: EvidenceBundle) -> CheckResult:
    cookies = bundle.http.cookies
    if not cookies:
        return CheckResult(Verdict.PASSED, "no cookies set")
    offenders = [c.name for c in cookies if not c.same_site]
    if offenders:
        detail = f"cookie(s) missing SameSite: {', '.join(offenders)}"
        return CheckResult(Verdict.FAILED, detail, ", ".join(offenders))
    return CheckResult(Verdict.PASSED, "all cookies set SameSite explicitly")


CHECK_COOKIES_SAMESITE_SET = Check(
    manifest=CheckManifest(
        check_id="VG-SES-003",
        category="SES",
        title="Cookies set SameSite explicitly",
        description="Without an explicit SameSite attribute, cross-site cookie behavior depends on browser defaults rather than an intentional choice.",
        severity_default=Severity.LOW,
        confidence=Confidence.CONFIRMED,
        weight=2,
        tier_required=Tier.PASSIVE,
        references=["https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Set-Cookie/SameSite"],
        remediation_template="Set `SameSite=Lax` (or `Strict`) explicitly on every cookie.",
        introduced_in="0.1",
    ),
    evaluate=_cookies_samesite_set,
)


# --- VG-SES-004: SameSite=None cookies are also Secure ------------------------


@requires("http")
def _cookies_samesite_none_requires_secure(bundle: EvidenceBundle) -> CheckResult:
    offenders = [
        c.name
        for c in bundle.http.cookies
        if (c.same_site or "").lower() == "none" and not c.secure
    ]
    if offenders:
        detail = f"cookie(s) use SameSite=None without Secure: {', '.join(offenders)}"
        return CheckResult(Verdict.FAILED, detail, ", ".join(offenders))
    return CheckResult(Verdict.PASSED, "no SameSite=None cookie without Secure")


CHECK_COOKIES_SAMESITE_NONE_REQUIRES_SECURE = Check(
    manifest=CheckManifest(
        check_id="VG-SES-004",
        category="SES",
        title="SameSite=None cookies are also Secure",
        description="Modern browsers reject a SameSite=None cookie that isn't also Secure, silently breaking any cross-site functionality that depends on it.",
        severity_default=Severity.MEDIUM,
        confidence=Confidence.CONFIRMED,
        weight=3,
        tier_required=Tier.PASSIVE,
        references=["https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Set-Cookie/SameSite#none"],
        remediation_template="Add `Secure` to every cookie that sets `SameSite=None`.",
        introduced_in="0.1",
    ),
    evaluate=_cookies_samesite_none_requires_secure,
)


# --- VG-SES-005: no session identifier exposed in a linked URL ---------------


@requires("http")
def _no_session_id_in_url(bundle: EvidenceBundle) -> CheckResult:
    if _SESSION_ID_IN_URL_PATTERN.search(bundle.http.body_excerpt):
        detail = "a linked URL appears to carry a session identifier as a query parameter"
        return CheckResult(Verdict.FAILED, detail)
    return CheckResult(Verdict.PASSED, "no session-identifier-shaped URL parameters found")


CHECK_NO_SESSION_ID_IN_URL = Check(
    manifest=CheckManifest(
        check_id="VG-SES-005",
        category="SES",
        title="Session identifiers are not exposed in URLs",
        description="A session ID carried in a URL leaks into browser history, server access logs, and the Referer header sent to third parties.",
        severity_default=Severity.MEDIUM,
        confidence=Confidence.INDICATED,
        weight=3,
        tier_required=Tier.PASSIVE,
        references=["https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html"],
        remediation_template="Move session identifiers out of the URL and into a cookie or an Authorization header.",
        false_positive_notes="A regex over the first 8KB of the homepage body only, matching a fixed list of common session-parameter names.",
        introduced_in="0.1",
    ),
    evaluate=_no_session_id_in_url,
)


# --- VG-SES-006: session cookie lifetime is sane -----------------------------


@requires("http")
def _cookie_lifetime_sane(bundle: EvidenceBundle) -> CheckResult:
    offenders = [
        c.name
        for c in bundle.http.cookies
        if _SESSION_NAME_PATTERN.search(c.name)
        and c.max_age is not None
        and c.max_age > _MAX_SESSION_COOKIE_AGE
    ]
    if offenders:
        detail = f"session-like cookie(s) with an excessive lifetime: {', '.join(offenders)}"
        return CheckResult(Verdict.FAILED, detail, ", ".join(offenders))
    return CheckResult(Verdict.PASSED, "no session-like cookie has an excessive lifetime")


CHECK_COOKIE_LIFETIME_SANE = Check(
    manifest=CheckManifest(
        check_id="VG-SES-006",
        category="SES",
        title="Session cookie lifetime is sane",
        description="A session-shaped cookie with a very long Max-Age extends the window an attacker can reuse a stolen session token.",
        severity_default=Severity.LOW,
        confidence=Confidence.INDICATED,
        weight=2,
        tier_required=Tier.PASSIVE,
        references=["https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html"],
        remediation_template="Shorten the session cookie's Max-Age (or drop it so it expires with the browser session) and use refresh tokens for longer-lived sign-in.",
        false_positive_notes="Matches cookie names containing 'session', 'sid', 'auth' or 'token' — a cookie legitimately named this way for a non-session purpose (e.g. a long-lived CSRF token) may be a false positive.",
        introduced_in="0.1",
    ),
    evaluate=_cookie_lifetime_sane,
)


CHECKS: list[Check] = [
    CHECK_COOKIES_SECURE,
    CHECK_COOKIES_HTTP_ONLY,
    CHECK_COOKIES_SAMESITE_SET,
    CHECK_COOKIES_SAMESITE_NONE_REQUIRES_SECURE,
    CHECK_NO_SESSION_ID_IN_URL,
    CHECK_COOKIE_LIFETIME_SANE,
]
