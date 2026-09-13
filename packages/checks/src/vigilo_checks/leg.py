"""LEG category: legal-document checks. 4 checks, v0.1 target per
docs/prooflight-vision-and-architecture.md §7.2.

Fully passive: every check here looks only for a *link* to the relevant
document on the homepage — exactly what a visitor would see — never guesses
at a conventional path (that would be active-tier path enumeration, out of
scope until Phase 6). Detecting "does the homepage advertise a privacy
policy" is deliberately a lower bar than "does a compliant privacy policy
exist"; that's a documented limitation, not an oversight.
"""

from __future__ import annotations

import re

from vigilo_core.evidence import EvidenceBundle
from vigilo_core.models import CheckManifest, Confidence, Severity, Tier, Verdict
from vigilo_checks.registry import Check, CheckResult, requires


def _link_pattern(*keywords: str) -> re.Pattern[str]:
    """Matches either an `href` value containing one of `keywords` (e.g.
    `href="/privacy-policy"`) or an anchor's visible text containing one
    (e.g. `<a href="/legal">Privacy Policy</a>`)."""
    alternation = "|".join(keywords)
    href_form = rf'href\s*=\s*["\'][^"\']*(?:{alternation})[^"\']*["\']'
    text_form = rf"<a\b[^>]*>[^<]*(?:{alternation})[^<]*</a>"
    return re.compile(rf"(?:{href_form})|(?:{text_form})", re.IGNORECASE)


_PRIVACY_PATTERN = _link_pattern("privacy")
_TERMS_PATTERN = _link_pattern("terms", "tos")
_COOKIE_PATTERN = _link_pattern("cookie")
_CONTACT_PATTERN = re.compile(
    r'mailto:|href\s*=\s*["\'][^"\']*contact[^"\']*["\']|<a\b[^>]*>[^<]*contact[^<]*</a>',
    re.IGNORECASE,
)


def _has_link(body: str, pattern: re.Pattern[str]) -> bool:
    return bool(pattern.search(body))


# --- VG-LEG-001: privacy policy linked ---------------------------------------


@requires("http")
def _privacy_policy_linked(bundle: EvidenceBundle) -> CheckResult:
    if _has_link(bundle.http.body_excerpt, _PRIVACY_PATTERN):
        return CheckResult(Verdict.PASSED, "a privacy policy link was found on the homepage")
    return CheckResult(Verdict.FAILED, "no privacy policy link found on the homepage")


CHECK_PRIVACY_POLICY_LINKED = Check(
    manifest=CheckManifest(
        check_id="VG-LEG-001",
        category="LEG",
        title="Privacy policy is linked",
        description="A site processing personal data needs a discoverable privacy policy (GDPR Art. 13, CCPA §1798.130).",
        severity_default=Severity.MEDIUM,
        confidence=Confidence.INDICATED,
        weight=3,
        tier_required=Tier.PASSIVE,
        references=["https://gdpr-info.eu/art-13-gdpr/"],
        remediation_template="Add a visible link to a privacy policy in the site footer or navigation.",
        false_positive_notes="Detects a link whose href or text mentions 'privacy' — a policy linked only from a sub-page not reachable from the homepage will be missed.",
        introduced_in="0.1",
    ),
    evaluate=_privacy_policy_linked,
)


# --- VG-LEG-002: terms of service linked --------------------------------------


@requires("http")
def _terms_linked(bundle: EvidenceBundle) -> CheckResult:
    if _has_link(bundle.http.body_excerpt, _TERMS_PATTERN):
        return CheckResult(Verdict.PASSED, "a terms of service link was found on the homepage")
    return CheckResult(Verdict.FAILED, "no terms of service link found on the homepage")


CHECK_TERMS_LINKED = Check(
    manifest=CheckManifest(
        check_id="VG-LEG-002",
        category="LEG",
        title="Terms of service is linked",
        description="Terms of service establish the legal basis for the service relationship and are expected on any commercial site.",
        severity_default=Severity.LOW,
        confidence=Confidence.INDICATED,
        weight=2,
        tier_required=Tier.PASSIVE,
        references=["https://www.ftc.gov/business-guidance"],
        remediation_template="Add a visible link to your terms of service in the site footer or navigation.",
        false_positive_notes="Detects a link whose href or text mentions 'terms' or 'tos' — a policy linked only from a sub-page not reachable from the homepage will be missed.",
        introduced_in="0.1",
    ),
    evaluate=_terms_linked,
)


# --- VG-LEG-003: cookie policy linked ------------------------------------------


@requires("http")
def _cookie_policy_linked(bundle: EvidenceBundle) -> CheckResult:
    if _has_link(bundle.http.body_excerpt, _COOKIE_PATTERN):
        return CheckResult(Verdict.PASSED, "a cookie policy link was found on the homepage")
    return CheckResult(Verdict.FAILED, "no cookie policy link found on the homepage")


CHECK_COOKIE_POLICY_LINKED = Check(
    manifest=CheckManifest(
        check_id="VG-LEG-003",
        category="LEG",
        title="Cookie policy is linked",
        description="Sites using cookies for anything beyond strict necessity need a documented cookie policy under EU ePrivacy rules.",
        severity_default=Severity.LOW,
        confidence=Confidence.INDICATED,
        weight=2,
        tier_required=Tier.PASSIVE,
        references=["https://gdpr.eu/cookies/"],
        remediation_template="Add a visible link to a cookie policy, distinct from (or as a section of) the privacy policy.",
        false_positive_notes="A site that sets no non-essential cookies at all does not need one — this check does not currently correlate with actual cookie usage.",
        introduced_in="0.1",
    ),
    evaluate=_cookie_policy_linked,
)


# --- VG-LEG-004: contact information present ----------------------------------


@requires("http")
def _contact_info_present(bundle: EvidenceBundle) -> CheckResult:
    if _CONTACT_PATTERN.search(bundle.http.body_excerpt):
        return CheckResult(Verdict.PASSED, "contact information was found on the homepage")
    return CheckResult(Verdict.FAILED, "no contact information (mailto link or contact page) found")


CHECK_CONTACT_INFO_PRESENT = Check(
    manifest=CheckManifest(
        check_id="VG-LEG-004",
        category="LEG",
        title="Contact information is present",
        description="GDPR Art. 13(1)(a) requires the data controller's identity and contact details be made available to users.",
        severity_default=Severity.LOW,
        confidence=Confidence.INDICATED,
        weight=1,
        tier_required=Tier.PASSIVE,
        references=["https://gdpr-info.eu/art-13-gdpr/"],
        remediation_template="Add a mailto: link or a link to a contact page in the site footer or navigation.",
        false_positive_notes="Detects a mailto: link or a link mentioning 'contact' — a contact form embedded without either pattern will be missed.",
        introduced_in="0.1",
    ),
    evaluate=_contact_info_present,
)


CHECKS: list[Check] = [
    CHECK_PRIVACY_POLICY_LINKED,
    CHECK_TERMS_LINKED,
    CHECK_COOKIE_POLICY_LINKED,
    CHECK_CONTACT_INFO_PRESENT,
]
