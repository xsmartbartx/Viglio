"""DEP category: dependency and supply-chain checks. 4 checks, v0.1 target
per docs/prooflight-vision-and-architecture.md §7.2. All operate on
`http.body_excerpt` markup directly — no script-content fetch needed for any
of these (unlike `cli.py`, which needs actual fetched JS content).
"""

from __future__ import annotations

import re

from vigilo_core.evidence import EvidenceBundle
from vigilo_core.models import CheckManifest, Confidence, Severity, Tier, Verdict
from vigilo_checks.registry import Check, CheckResult, requires

_SCRIPT_TAG_PATTERN = re.compile(r"<script\b([^>]*)\bsrc\s*=\s*[\"']([^\"']+)[\"']([^>]*)>", re.IGNORECASE)
_MAX_THIRD_PARTY_ORIGINS = 8
_OLD_LIBRARY_PATTERNS = {
    re.compile(r"jquery-1\.\d", re.IGNORECASE): "jQuery 1.x (EOL, multiple known XSS advisories)",
    re.compile(r"jquery-2\.\d", re.IGNORECASE): "jQuery 2.x (EOL)",
    re.compile(r"angular\.js/1\.[0-4]\b", re.IGNORECASE): "AngularJS < 1.5 (EOL, known prototype-pollution issues)",
    re.compile(r"bootstrap[/-]3\.\d", re.IGNORECASE): "Bootstrap 3.x (EOL)",
}
_JSDELIVR_UNPKG_PACKAGE_PATTERN = re.compile(
    r"https?://(?:cdn\.jsdelivr\.net/npm|unpkg\.com)/([^/\"'?#]+)", re.IGNORECASE
)


def _script_tags(body: str) -> list[tuple[str, str]]:
    """Returns (src, origin_or_'') pairs for every `<script src=...>` tag."""
    tags = []
    for match in _SCRIPT_TAG_PATTERN.finditer(body):
        src = match.group(2)
        tags.append((src, match.group(1) + match.group(3)))
    return tags


def _origin_of(src: str) -> str | None:
    match = re.match(r"https?://([^/]+)", src)
    return match.group(1) if match else None


# --- VG-DEP-001: cross-origin scripts use Subresource Integrity --------------


@requires("http")
def _sri_present_on_third_party_scripts(bundle: EvidenceBundle) -> CheckResult:
    offenders = []
    for src, attrs in _script_tags(bundle.http.body_excerpt):
        if not src.startswith("http"):
            continue  # same-origin relative script: SRI is nice-to-have, not required here
        if "integrity=" not in attrs.lower():
            offenders.append(src)
    if offenders:
        detail = f"third-party script(s) without Subresource Integrity: {', '.join(offenders)}"
        return CheckResult(Verdict.FAILED, detail, ", ".join(offenders))
    return CheckResult(Verdict.PASSED, "all third-party scripts declare Subresource Integrity")


CHECK_SRI_PRESENT = Check(
    manifest=CheckManifest(
        check_id="VG-DEP-001",
        category="DEP",
        title="Third-party scripts use Subresource Integrity",
        description="Without SRI, a compromised or MITM'd CDN can silently replace a third-party script with malicious code.",
        severity_default=Severity.MEDIUM,
        confidence=Confidence.CONFIRMED,
        weight=4,
        tier_required=Tier.PASSIVE,
        references=["https://developer.mozilla.org/en-US/docs/Web/Security/Subresource_Integrity"],
        remediation_template="Add an `integrity=\"sha384-...\"` attribute (and `crossorigin=\"anonymous\"`) to every cross-origin `<script>` tag.",
        false_positive_notes="Only scans the first 8KB of the homepage's HTML; scripts injected dynamically by other JS are not seen.",
        introduced_in="0.1",
    ),
    evaluate=_sri_present_on_third_party_scripts,
)


# --- VG-DEP-002: no known end-of-life library version detected --------------


@requires("http")
def _no_known_old_library(bundle: EvidenceBundle) -> CheckResult:
    for src, _attrs in _script_tags(bundle.http.body_excerpt):
        for pattern, label in _OLD_LIBRARY_PATTERNS.items():
            if pattern.search(src):
                return CheckResult(Verdict.FAILED, f"detected {label} via script URL {src}", src)
    return CheckResult(Verdict.PASSED, "no known end-of-life library version detected by filename")


CHECK_NO_KNOWN_OLD_LIBRARY = Check(
    manifest=CheckManifest(
        check_id="VG-DEP-002",
        category="DEP",
        title="No known end-of-life JS library version",
        description="Very old major versions of common libraries have accumulated public advisories and no longer receive security patches.",
        severity_default=Severity.MEDIUM,
        confidence=Confidence.INDICATED,
        weight=3,
        tier_required=Tier.PASSIVE,
        references=["https://endoflife.date/"],
        remediation_template="Upgrade the flagged library to a currently-maintained major version.",
        false_positive_notes="Detects the version from the script's filename/URL only, against a small fixed table — a self-hosted, renamed, or bundled copy will not be detected.",
        introduced_in="0.1",
    ),
    evaluate=_no_known_old_library,
)


# --- VG-DEP-003: bounded number of distinct third-party script origins ------


@requires("http")
def _bounded_third_party_origins(bundle: EvidenceBundle) -> CheckResult:
    origins = set()
    for src, _attrs in _script_tags(bundle.http.body_excerpt):
        origin = _origin_of(src)
        if origin:
            origins.add(origin)
    if len(origins) > _MAX_THIRD_PARTY_ORIGINS:
        detail = f"{len(origins)} distinct third-party script origins found (threshold {_MAX_THIRD_PARTY_ORIGINS})"
        return CheckResult(Verdict.FAILED, detail, str(len(origins)))
    return CheckResult(Verdict.PASSED, f"{len(origins)} distinct third-party script origin(s)")


CHECK_BOUNDED_THIRD_PARTY_ORIGINS = Check(
    manifest=CheckManifest(
        check_id="VG-DEP-003",
        category="DEP",
        title="Bounded third-party script surface area",
        description="Every additional third-party script origin is another party that can serve malicious or compromised code into the page.",
        severity_default=Severity.LOW,
        confidence=Confidence.INDICATED,
        weight=1,
        tier_required=Tier.PASSIVE,
        references=["https://owasp.org/www-community/Third_Party_Javascript_Management"],
        remediation_template="Consolidate or self-host third-party scripts where practical; audit whether every included origin is still needed.",
        false_positive_notes="A high count is a supply-chain risk *signal*, not proof of a problem — some legitimate sites genuinely need many integrations.",
        introduced_in="0.1",
    ),
    evaluate=_bounded_third_party_origins,
)


# --- VG-DEP-004: no unpinned "latest" CDN script version --------------------


def _is_unpinned_cdn_package_ref(package_ref: str) -> bool:
    if "@" not in package_ref:
        return True
    _, _, version = package_ref.rpartition("@")
    return version.lower() == "latest"


@requires("http")
def _no_unpinned_cdn_version(bundle: EvidenceBundle) -> CheckResult:
    for src, _attrs in _script_tags(bundle.http.body_excerpt):
        match = _JSDELIVR_UNPKG_PACKAGE_PATTERN.search(src)
        if match and _is_unpinned_cdn_package_ref(match.group(1)):
            return CheckResult(Verdict.FAILED, f"script loaded without a pinned version: {src}", src)
    return CheckResult(Verdict.PASSED, "no unpinned CDN script version detected")


CHECK_NO_UNPINNED_CDN_VERSION = Check(
    manifest=CheckManifest(
        check_id="VG-DEP-004",
        category="DEP",
        title="No unpinned 'latest' CDN script version",
        description="A script loaded without a pinned version (e.g. an implicit '@latest' alias) can change unexpectedly, including via a compromised upstream release.",
        severity_default=Severity.MEDIUM,
        confidence=Confidence.INDICATED,
        weight=3,
        tier_required=Tier.PASSIVE,
        references=["https://slsa.dev/spec/v1.0/requirements"],
        remediation_template="Pin every CDN-loaded script to an exact version (e.g. `react@18.3.1`, not `react` or `react@latest`).",
        false_positive_notes="Only recognizes jsDelivr and unpkg URL shapes; other CDNs are not covered, and npm-scoped packages (`@scope/name`) are not correctly parsed (the '@' in the scope name is mistaken for a version separator).",
        introduced_in="0.1",
    ),
    evaluate=_no_unpinned_cdn_version,
)


CHECKS: list[Check] = [
    CHECK_SRI_PRESENT,
    CHECK_NO_KNOWN_OLD_LIBRARY,
    CHECK_BOUNDED_THIRD_PARTY_ORIGINS,
    CHECK_NO_UNPINNED_CDN_VERSION,
]
