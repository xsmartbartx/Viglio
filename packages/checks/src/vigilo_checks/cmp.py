"""CMP category: compliance checks. 4 checks, v0.1 target per
docs/prooflight-vision-and-architecture.md §7.2.

All four are heuristic (`Confidence.INDICATED`) by necessity — consent and
data-sharing compliance cannot be fully assessed from one passive homepage
fetch, and docs/vision.md §6 names false positives here as a top risk. Each
check documents exactly what it can and can't see in `false_positive_notes`
rather than overclaiming precision.
"""

from __future__ import annotations

import re

from vigilo_checks.registry import Check, CheckResult, requires
from vigilo_core.evidence import EvidenceBundle
from vigilo_core.models import CheckManifest, Confidence, Severity, Tier, Verdict

_TRACKER_PATTERN = re.compile(
    r"google-analytics\.com|googletagmanager\.com|gtag\(|connect\.facebook\.net|fbq\("
    r"|hotjar\.com|analytics\.tiktok\.com|doubleclick\.net",
    re.IGNORECASE,
)
_CMP_LIBRARY_PATTERN = re.compile(
    r"cookiebot|onetrust|cookieconsent|usercentrics|termly|cookie-script|cookiehub"
    r"|data-cookieconsent|didomi|iubenda",
    re.IGNORECASE,
)
_GA_PATTERN = re.compile(r"google-analytics\.com|gtag\(|googletagmanager\.com", re.IGNORECASE)
_GA_CONSENT_MODE_PATTERN = re.compile(r"""gtag\(\s*['"]consent['"]\s*,\s*['"]default['"]""", re.IGNORECASE)
_PRECHECKED_MARKETING_CHECKBOX_PATTERN = re.compile(
    r'<input\b[^>]*type=["\']checkbox["\'][^>]*checked[^>]*>',
    re.IGNORECASE,
)
_MARKETING_CONTEXT_PATTERN = re.compile(r"marketing|newsletter|subscribe|promo", re.IGNORECASE)
_CONSENT_PRIVACY_PROXIMITY_WINDOW = 400


# --- VG-CMP-001: tracker present without a recognizable consent library -----


@requires("http")
def _tracker_without_consent_library(bundle: EvidenceBundle) -> CheckResult:
    body = bundle.http.body_excerpt
    if not _TRACKER_PATTERN.search(body):
        return CheckResult(Verdict.NOT_APPLICABLE, "no known analytics/ad-tech tracker detected")
    if _CMP_LIBRARY_PATTERN.search(body):
        return CheckResult(Verdict.PASSED, "tracker present alongside a recognizable consent-management library")
    return CheckResult(Verdict.FAILED, "a tracking/analytics script is present with no recognizable consent-management library")


CHECK_TRACKER_WITHOUT_CONSENT_LIBRARY = Check(
    manifest=CheckManifest(
        check_id="VG-CMP-001",
        category="CMP",
        title="Trackers are not loaded without a consent mechanism",
        description="Loading analytics or ad-tech scripts before obtaining consent is a common GDPR/ePrivacy Directive violation in the EU.",
        severity_default=Severity.MEDIUM,
        confidence=Confidence.INDICATED,
        weight=3,
        tier_required=Tier.PASSIVE,
        references=["https://gdpr.eu/cookies/"],
        remediation_template="Gate analytics/ad-tech script loading behind an explicit consent banner (or add a recognized CMP if one already exists but isn't detected).",
        false_positive_notes="Matches a fixed list of common tracker and CMP library signatures in the first 8KB of the homepage — a custom-built consent solution, or a CMP that defers script injection via a mechanism this regex can't see, will misfire as a failure.",
        introduced_in="0.1",
    ),
    evaluate=_tracker_without_consent_library,
)


# --- VG-CMP-002: Google Analytics uses consent mode ---------------------------


@requires("http")
def _ga_uses_consent_mode(bundle: EvidenceBundle) -> CheckResult:
    body = bundle.http.body_excerpt
    if not _GA_PATTERN.search(body):
        return CheckResult(Verdict.NOT_APPLICABLE, "Google Analytics not detected")
    if _GA_CONSENT_MODE_PATTERN.search(body):
        return CheckResult(Verdict.PASSED, "Google Analytics Consent Mode default-state call detected")
    return CheckResult(Verdict.FAILED, "Google Analytics detected without a Consent Mode default-state call")


CHECK_GA_USES_CONSENT_MODE = Check(
    manifest=CheckManifest(
        check_id="VG-CMP-002",
        category="CMP",
        title="Google Analytics uses Consent Mode",
        description="Google's Consent Mode lets analytics start in a denied-by-default state until the visitor consents — its absence alongside GA usually means analytics fires unconditionally.",
        severity_default=Severity.LOW,
        confidence=Confidence.INDICATED,
        weight=2,
        tier_required=Tier.PASSIVE,
        references=["https://developers.google.com/tag-platform/security/guides/consent"],
        remediation_template="Add a `gtag('consent', 'default', {...})` call before the GA tag loads, denying analytics/ad storage until consent is granted.",
        false_positive_notes="Only recognizes the literal `gtag('consent','default'` call pattern; consent mode configured through Google Tag Manager's UI without this literal string will misfire as a failure.",
        introduced_in="0.1",
    ),
    evaluate=_ga_uses_consent_mode,
)


# --- VG-CMP-003: no pre-checked marketing-consent checkbox --------------------


@requires("http")
def _no_prechecked_marketing_checkbox(bundle: EvidenceBundle) -> CheckResult:
    body = bundle.http.body_excerpt
    for match in _PRECHECKED_MARKETING_CHECKBOX_PATTERN.finditer(body):
        window = body[max(0, match.start() - 150) : match.end() + 150]
        if _MARKETING_CONTEXT_PATTERN.search(window):
            return CheckResult(Verdict.FAILED, "a pre-checked checkbox was found near marketing-consent-related text")
    return CheckResult(Verdict.PASSED, "no pre-checked marketing-consent checkbox detected")


CHECK_NO_PRECHECKED_MARKETING_CHECKBOX = Check(
    manifest=CheckManifest(
        check_id="VG-CMP-003",
        category="CMP",
        title="No pre-checked marketing consent checkbox",
        description="GDPR Art. 4(11)/7 requires consent to be freely given by a clear affirmative act — a pre-ticked box does not qualify.",
        severity_default=Severity.MEDIUM,
        confidence=Confidence.INDICATED,
        weight=2,
        tier_required=Tier.PASSIVE,
        references=["https://gdpr-info.eu/art-4-gdpr/"],
        remediation_template="Remove the `checked` attribute from marketing/newsletter opt-in checkboxes; require an explicit user action.",
        false_positive_notes="A narrow text-proximity heuristic (150 characters either side of the checkbox) — a checkbox whose marketing context is conveyed only via CSS/JS rather than nearby text will be missed, and an unrelated pre-checked box near marketing copy could misfire.",
        introduced_in="0.1",
    ),
    evaluate=_no_prechecked_marketing_checkbox,
)


# --- VG-CMP-004: consent notice references the privacy policy ---------------


@requires("http")
def _consent_notice_references_privacy_policy(bundle: EvidenceBundle) -> CheckResult:
    body = bundle.http.body_excerpt
    cookie_match = re.search(r"cookie", body, re.IGNORECASE)
    if not cookie_match:
        return CheckResult(Verdict.NOT_APPLICABLE, "no cookie/consent notice text detected")
    window_start = max(0, cookie_match.start() - _CONSENT_PRIVACY_PROXIMITY_WINDOW)
    window_end = cookie_match.end() + _CONSENT_PRIVACY_PROXIMITY_WINDOW
    window = body[window_start:window_end]
    if re.search(r"privacy", window, re.IGNORECASE):
        return CheckResult(Verdict.PASSED, "a privacy-policy reference was found near cookie/consent text")
    return CheckResult(Verdict.FAILED, "cookie/consent text was found with no nearby privacy-policy reference")


CHECK_CONSENT_NOTICE_REFERENCES_PRIVACY_POLICY = Check(
    manifest=CheckManifest(
        check_id="VG-CMP-004",
        category="CMP",
        title="Consent notice references the privacy policy",
        description="A cookie/consent notice should point the visitor to the privacy policy for the full detail on what is collected and why.",
        severity_default=Severity.LOW,
        confidence=Confidence.INDICATED,
        weight=1,
        tier_required=Tier.PASSIVE,
        references=["https://gdpr.eu/cookies/"],
        remediation_template="Add a link to the privacy policy directly within the cookie/consent banner text.",
        false_positive_notes="A ~800-character text-proximity heuristic around the word 'cookie' — a consent banner injected far from any mention of 'cookie' in the raw HTML (e.g. built entirely by JS with generic wording) will misfire as a failure.",
        introduced_in="0.1",
    ),
    evaluate=_consent_notice_references_privacy_policy,
)


CHECKS: list[Check] = [
    CHECK_TRACKER_WITHOUT_CONSENT_LIBRARY,
    CHECK_GA_USES_CONSENT_MODE,
    CHECK_NO_PRECHECKED_MARKETING_CHECKBOX,
    CHECK_CONSENT_NOTICE_REFERENCES_PRIVACY_POLICY,
]
