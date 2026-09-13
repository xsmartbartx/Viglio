"""EXP category (surface exposure): 5 checks — the passive subset.

The full v0.1 category (12 checks) includes "browsable directories, backup
artefacts, debug and test routes, reachable configuration and repository
metadata paths" — per docs/modules.md §3, that's the `paths` probe, which is
explicitly **Tier 1 (active) only**, since it means guessing at paths a
normal visitor would never request. Shipping those checks now, before
Phase 3's `resolve_authorization`/`verify_ownership` exist, would mean an
unauthenticated `vigilo scan` blindly probing hidden paths on a target
nobody has verified ownership of — a direct violation of ADR-0003.

What's genuinely passive and shipped here: presence of the four
conventional `.well-known`-adjacent files (explicitly in-scope per
docs/vision.md's "GET on public .well-known paths"), plus verbose
error/debug-page detection on the homepage response that's already been
fetched. The remaining 7 checks move to Phase 6 — see
docs/build-roadmap.md.
"""

from __future__ import annotations

import re

from vigilo_checks.registry import Check, CheckResult, requires
from vigilo_core.evidence import EvidenceBundle
from vigilo_core.models import CheckManifest, Confidence, Severity, Tier, Verdict

_VERBOSE_ERROR_PATTERN = re.compile(
    r"Traceback \(most recent call last\)"
    r"|Fatal error:.*\.php"
    r"|Warning:.*mysqli"
    r"|Server Error in '/' Application"
    r"|A PHP Error was encountered"
    r"|Whitelabel Error Page"
    r"|django\.core\.exceptions"
    r"|at [A-Za-z0-9_.$]+\s*\([^)]*\.js:\d+:\d+\)",
)


# --- VG-EXP-001: security.txt present -----------------------------------------


@requires("wellknown")
def _security_txt_present(bundle: EvidenceBundle) -> CheckResult:
    if bundle.wellknown.security_txt_present:
        return CheckResult(Verdict.PASSED, "/.well-known/security.txt is present")
    return CheckResult(Verdict.FAILED, "/.well-known/security.txt is missing")


CHECK_SECURITY_TXT_PRESENT = Check(
    manifest=CheckManifest(
        check_id="VG-EXP-001",
        category="EXP",
        title="security.txt is present",
        description="RFC 9116's security.txt gives security researchers a documented way to report vulnerabilities responsibly.",
        severity_default=Severity.LOW,
        confidence=Confidence.CONFIRMED,
        weight=1,
        tier_required=Tier.PASSIVE,
        references=["https://www.rfc-editor.org/rfc/rfc9116"],
        remediation_template="Publish a security.txt file at /.well-known/security.txt with a contact method for vulnerability reports.",
        introduced_in="0.1",
    ),
    evaluate=_security_txt_present,
)


# --- VG-EXP-002: robots.txt present -------------------------------------------


@requires("wellknown")
def _robots_txt_present(bundle: EvidenceBundle) -> CheckResult:
    if bundle.wellknown.robots_txt_present:
        return CheckResult(Verdict.PASSED, "/robots.txt is present")
    return CheckResult(Verdict.PASSED, "/robots.txt is absent (informational only)")


CHECK_ROBOTS_TXT_PRESENT = Check(
    manifest=CheckManifest(
        check_id="VG-EXP-002",
        category="EXP",
        title="robots.txt is present",
        description="Informational: robots.txt tells crawlers what they may index. Its absence is not a security issue, only noted for completeness.",
        severity_default=Severity.INFO,
        confidence=Confidence.CONFIRMED,
        weight=0,
        tier_required=Tier.PASSIVE,
        references=["https://developers.google.com/search/docs/crawling-indexing/robots/intro"],
        remediation_template="Add a robots.txt file if you want to guide crawler behavior; not required for security.",
        introduced_in="0.1",
    ),
    evaluate=_robots_txt_present,
)


# --- VG-EXP-003: sitemap.xml present -------------------------------------------


@requires("wellknown")
def _sitemap_present(bundle: EvidenceBundle) -> CheckResult:
    if bundle.wellknown.sitemap_present:
        return CheckResult(Verdict.PASSED, "/sitemap.xml is present")
    return CheckResult(Verdict.PASSED, "/sitemap.xml is absent (informational only)")


CHECK_SITEMAP_PRESENT = Check(
    manifest=CheckManifest(
        check_id="VG-EXP-003",
        category="EXP",
        title="sitemap.xml is present",
        description="Informational: a sitemap helps search engines find your pages. Its absence is not a security issue, only noted for completeness.",
        severity_default=Severity.INFO,
        confidence=Confidence.CONFIRMED,
        weight=0,
        tier_required=Tier.PASSIVE,
        references=["https://developers.google.com/search/docs/crawling-indexing/sitemaps/overview"],
        remediation_template="Add a sitemap.xml if you want to help search engines index your pages; not required for security.",
        introduced_in="0.1",
    ),
    evaluate=_sitemap_present,
)


# --- VG-EXP-004: web app manifest present --------------------------------------


@requires("wellknown")
def _manifest_present(bundle: EvidenceBundle) -> CheckResult:
    if bundle.wellknown.manifest_present:
        return CheckResult(Verdict.PASSED, "/manifest.json is present")
    return CheckResult(Verdict.PASSED, "/manifest.json is absent (informational only)")


CHECK_MANIFEST_PRESENT = Check(
    manifest=CheckManifest(
        check_id="VG-EXP-004",
        category="EXP",
        title="Web app manifest is present",
        description="Informational: a manifest.json enables PWA install prompts and theming. Its absence is not a security issue, only noted for completeness.",
        severity_default=Severity.INFO,
        confidence=Confidence.CONFIRMED,
        weight=0,
        tier_required=Tier.PASSIVE,
        references=["https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Manifest"],
        remediation_template="Add a manifest.json if you want PWA install support; not required for security.",
        introduced_in="0.1",
    ),
    evaluate=_manifest_present,
)


# --- VG-EXP-005: no verbose error/debug-page leakage --------------------------


@requires("http")
def _no_verbose_error_page(bundle: EvidenceBundle) -> CheckResult:
    if _VERBOSE_ERROR_PATTERN.search(bundle.http.body_excerpt):
        return CheckResult(Verdict.FAILED, "the homepage response contains a verbose error/stack-trace signature")
    return CheckResult(Verdict.PASSED, "no verbose error/debug-page signature found on the homepage")


CHECK_NO_VERBOSE_ERROR_PAGE = Check(
    manifest=CheckManifest(
        check_id="VG-EXP-005",
        category="EXP",
        title="No verbose error page on the homepage",
        description="A stack trace or framework debug page leaks internal file paths, library versions, and sometimes configuration values to any visitor.",
        severity_default=Severity.HIGH,
        confidence=Confidence.CONFIRMED,
        weight=6,
        tier_required=Tier.PASSIVE,
        references=["https://owasp.org/www-project-top-ten/2017/A6_2017-Security_Misconfiguration"],
        remediation_template="Disable debug mode in production and configure a generic error page for unhandled exceptions.",
        false_positive_notes="Matches distinctive framework debug-page and stack-trace signatures (Django, Flask/Werkzeug, PHP, Rails, ASP.NET, raw Node stack frames) within the first 8KB of the homepage body only.",
        introduced_in="0.1",
    ),
    evaluate=_no_verbose_error_page,
)


CHECKS: list[Check] = [
    CHECK_SECURITY_TXT_PRESENT,
    CHECK_ROBOTS_TXT_PRESENT,
    CHECK_SITEMAP_PRESENT,
    CHECK_MANIFEST_PRESENT,
    CHECK_NO_VERBOSE_ERROR_PAGE,
]
