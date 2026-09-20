"""EXP category (surface exposure): 12 checks — `VG-EXP-001` through `005`
passive (Phase 2), `VG-EXP-006` through `012` active-tier (Phase 6).

`VG-EXP-001..005`: presence of the four conventional `.well-known`-adjacent
files (explicitly in-scope per docs/vision.md's "GET on public .well-known
paths"), plus verbose error/debug-page detection on the homepage response
that's already been fetched — genuinely passive, no hidden-path guessing.

`VG-EXP-006..012`: "browsable directories, backup artefacts, debug and test
routes, reachable configuration and repository metadata paths" — per
docs/modules.md §3, that's the `paths` probe
(`packages/probes/src/vigilo_probes/paths_probe.py`), explicitly **Tier 1
(active) only**, since it means guessing at paths a normal visitor would
never request. Deferred from Phase 2 to Phase 6, once
`resolve_authorization()`/`verify_ownership()` existed to gate it — shipping
these against an unverified target would be blind hidden-path enumeration,
a direct violation of ADR-0003's passive-tier definition. All seven read
`bundle.paths`, populated only at `Tier.ACTIVE`
(`packages/probes/src/vigilo_probes/orchestrator.py`); each aggregates
every matching `DetectedPath` into one result, same multi-offender pattern
`dat.py`'s checks already use for `bundle.backends`.
"""

from __future__ import annotations

import re

from vigilo_checks.registry import Check, CheckResult, requires
from vigilo_core.evidence import DetectedPath, EvidenceBundle
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
    cwe_id=None,  # disclosure-channel presence, not a weakness
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
    cwe_id=None,  # info page, not a weakness
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
    cwe_id=None,  # info page, not a weakness
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
    cwe_id=None,  # info page, not a weakness
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
    cwe_id="CWE-209",
),
    evaluate=_no_verbose_error_page,
)


# --- VG-EXP-006: repository metadata not exposed (Tier 1) --------------------


def _offenders(bundle: EvidenceBundle, kind: str) -> list[DetectedPath]:
    return [p for p in bundle.paths.detected if p.kind == kind]


@requires("paths")
def _no_repo_metadata_exposed(bundle: EvidenceBundle) -> CheckResult:
    offenders = _offenders(bundle, "repo_metadata")
    if offenders:
        paths = ", ".join(o.path for o in offenders)
        return CheckResult(Verdict.FAILED, f"repository metadata is reachable: {paths}", paths)
    return CheckResult(Verdict.PASSED, "no repository metadata (.git/.svn/.hg) reachable")


CHECK_NO_REPO_METADATA_EXPOSED = Check(
    manifest=CheckManifest(
        check_id="VG-EXP-006",
        category="EXP",
        title="Repository metadata not exposed",
        description="A reachable .git/.svn/.hg directory can let an attacker reconstruct the full source tree, including commit history and anything ever committed, secrets included.",
        severity_default=Severity.CRITICAL,
        confidence=Confidence.CONFIRMED,
        weight=9,
        tier_required=Tier.ACTIVE,
        budget_cost=4,
        references=["https://cwe.mitre.org/data/definitions/527.html"],
        remediation_template="Block access to .git/.svn/.hg directories at the web server or CDN level; never deploy version-control metadata into the public web root.",
        introduced_in="0.1",
    cwe_id="CWE-527",  # matches existing reference
),
    evaluate=_no_repo_metadata_exposed,
)


# --- VG-EXP-007: no backup/archive files reachable (Tier 1) -------------------


@requires("paths")
def _no_backup_artefacts_exposed(bundle: EvidenceBundle) -> CheckResult:
    offenders = _offenders(bundle, "backup_artefact")
    if offenders:
        paths = ", ".join(o.path for o in offenders)
        return CheckResult(Verdict.FAILED, f"a backup or archive file is reachable: {paths}", paths)
    return CheckResult(Verdict.PASSED, "no backup or archive file reachable")


CHECK_NO_BACKUP_ARTEFACTS_EXPOSED = Check(
    manifest=CheckManifest(
        check_id="VG-EXP-007",
        category="EXP",
        title="No backup or archive files reachable",
        description="A reachable database dump or site archive can hand over real user data and source code in one download.",
        severity_default=Severity.CRITICAL,
        confidence=Confidence.CONFIRMED,
        weight=9,
        tier_required=Tier.ACTIVE,
        budget_cost=5,
        references=["https://cwe.mitre.org/data/definitions/530.html"],
        remediation_template="Remove backup/archive files from the public web root; store backups outside any web-served directory.",
        introduced_in="0.1",
    cwe_id="CWE-530",  # matches existing reference
),
    evaluate=_no_backup_artefacts_exposed,
)


# --- VG-EXP-008: no exposed configuration files (Tier 1) ----------------------


@requires("paths")
def _no_exposed_config_files(bundle: EvidenceBundle) -> CheckResult:
    offenders = _offenders(bundle, "exposed_config")
    if offenders:
        paths = ", ".join(o.path for o in offenders)
        return CheckResult(Verdict.FAILED, f"a configuration file is reachable: {paths}", paths)
    return CheckResult(Verdict.PASSED, "no configuration file reachable")


CHECK_NO_EXPOSED_CONFIG_FILES = Check(
    manifest=CheckManifest(
        check_id="VG-EXP-008",
        category="EXP",
        title="No exposed configuration files",
        description="A reachable .env or app-config file routinely contains database credentials, API keys, and signing secrets in plain text.",
        severity_default=Severity.CRITICAL,
        confidence=Confidence.CONFIRMED,
        weight=9,
        tier_required=Tier.ACTIVE,
        budget_cost=4,
        references=["https://cwe.mitre.org/data/definitions/538.html"],
        remediation_template="Remove configuration files from the public web root; load secrets from environment variables or a secret manager instead.",
        introduced_in="0.1",
    cwe_id="CWE-538",  # matches existing reference
),
    evaluate=_no_exposed_config_files,
)


# --- VG-EXP-009: no debug routes reachable (Tier 1) ---------------------------


@requires("paths")
def _no_debug_routes_exposed(bundle: EvidenceBundle) -> CheckResult:
    offenders = _offenders(bundle, "debug_route")
    if offenders:
        paths = ", ".join(o.path for o in offenders)
        return CheckResult(Verdict.FAILED, f"a debug route is reachable: {paths}", paths)
    return CheckResult(Verdict.PASSED, "no debug route reachable")


CHECK_NO_DEBUG_ROUTES_EXPOSED = Check(
    manifest=CheckManifest(
        check_id="VG-EXP-009",
        category="EXP",
        title="No debug routes reachable",
        description="A reachable debug endpoint (framework debug console, phpinfo, an actuator health/env page) discloses internal versions, paths and sometimes configuration to any visitor.",
        severity_default=Severity.MEDIUM,
        confidence=Confidence.CONFIRMED,
        weight=5,
        tier_required=Tier.ACTIVE,
        budget_cost=5,
        references=["https://cwe.mitre.org/data/definitions/215.html"],
        remediation_template="Disable debug/diagnostic endpoints in production, or require authentication in front of them.",
        introduced_in="0.1",
    cwe_id="CWE-215",  # matches existing reference
),
    evaluate=_no_debug_routes_exposed,
)


# --- VG-EXP-010: no test/staging routes reachable (Tier 1) --------------------


@requires("paths")
def _no_test_routes_exposed(bundle: EvidenceBundle) -> CheckResult:
    offenders = _offenders(bundle, "test_route")
    if offenders:
        paths = ", ".join(o.path for o in offenders)
        return CheckResult(Verdict.FAILED, f"a test/staging route is reachable: {paths}", paths)
    return CheckResult(Verdict.PASSED, "no test/staging route reachable")


CHECK_NO_TEST_ROUTES_EXPOSED = Check(
    manifest=CheckManifest(
        check_id="VG-EXP-010",
        category="EXP",
        title="No test/staging routes reachable",
        description="Test or staging routes left in a production deployment are rarely hardened to the same standard as the rest of the app and widen the attack surface unnecessarily.",
        severity_default=Severity.LOW,
        confidence=Confidence.INDICATED,
        weight=3,
        tier_required=Tier.ACTIVE,
        budget_cost=4,
        references=["https://cwe.mitre.org/data/definitions/489.html"],
        remediation_template="Remove test/staging routes from the production build, or gate them behind authentication.",
        false_positive_notes="A reachable /test or /staging path is not always a real issue on its own — treat as a prompt to confirm it doesn't bypass normal authorization.",
        introduced_in="0.1",
    cwe_id="CWE-489",  # matches existing reference
),
    evaluate=_no_test_routes_exposed,
)


# --- VG-EXP-011: no directory listing enabled (Tier 1) ------------------------


@requires("paths")
def _no_directory_listing_enabled(bundle: EvidenceBundle) -> CheckResult:
    offenders = _offenders(bundle, "directory_listing")
    if offenders:
        paths = ", ".join(o.path for o in offenders)
        return CheckResult(Verdict.FAILED, f"directory listing is enabled: {paths}", paths)
    return CheckResult(Verdict.PASSED, "no directory listing detected on checked paths")


CHECK_NO_DIRECTORY_LISTING_ENABLED = Check(
    manifest=CheckManifest(
        check_id="VG-EXP-011",
        category="EXP",
        title="No directory listing enabled",
        description="An auto-generated directory index reveals the full file inventory of a folder, including files never linked from the site itself.",
        severity_default=Severity.MEDIUM,
        confidence=Confidence.INDICATED,
        weight=5,
        tier_required=Tier.ACTIVE,
        budget_cost=4,
        references=["https://cwe.mitre.org/data/definitions/548.html"],
        remediation_template="Disable directory listing (autoindex) on the web server for every publicly reachable directory.",
        false_positive_notes="Detection matches common autoindex title/heading patterns (Apache/nginx); a custom directory-browsing UI could evade or false-positive this heuristic.",
        introduced_in="0.1",
    cwe_id="CWE-548",  # matches existing reference
),
    evaluate=_no_directory_listing_enabled,
)


# --- VG-EXP-012: no default admin panel paths exposed (Tier 1) ----------------


@requires("paths")
def _no_default_admin_panel_exposed(bundle: EvidenceBundle) -> CheckResult:
    offenders = _offenders(bundle, "admin_panel")
    if offenders:
        paths = ", ".join(o.path for o in offenders)
        return CheckResult(Verdict.FAILED, f"a default admin panel path is reachable: {paths}", paths)
    return CheckResult(Verdict.PASSED, "no default admin panel path reachable")


CHECK_NO_DEFAULT_ADMIN_PANEL_EXPOSED = Check(
    manifest=CheckManifest(
        check_id="VG-EXP-012",
        category="EXP",
        title="No default admin panel paths exposed",
        description="A reachable default admin path (e.g. a CMS's stock /wp-admin/) is the first thing an automated attacker tries, and widens the attack surface even when properly authenticated.",
        severity_default=Severity.LOW,
        confidence=Confidence.INDICATED,
        weight=2,
        tier_required=Tier.ACTIVE,
        budget_cost=3,
        references=["https://owasp.org/Top10/A05_2021-Security_Misconfiguration/"],
        remediation_template="Move the admin panel off its default path, restrict it by IP allowlist, or require a second factor in front of it.",
        false_positive_notes="Reachability alone is not proof of weak access control — a properly authenticated admin panel at a default path is lower risk than this check's severity implies on its own; treat as a hardening prompt, not confirmed compromise.",
        introduced_in="0.1",
    cwe_id="CWE-1188",
),
    evaluate=_no_default_admin_panel_exposed,
)


CHECKS: list[Check] = [
    CHECK_SECURITY_TXT_PRESENT,
    CHECK_ROBOTS_TXT_PRESENT,
    CHECK_SITEMAP_PRESENT,
    CHECK_MANIFEST_PRESENT,
    CHECK_NO_VERBOSE_ERROR_PAGE,
    CHECK_NO_REPO_METADATA_EXPOSED,
    CHECK_NO_BACKUP_ARTEFACTS_EXPOSED,
    CHECK_NO_EXPOSED_CONFIG_FILES,
    CHECK_NO_DEBUG_ROUTES_EXPOSED,
    CHECK_NO_TEST_ROUTES_EXPOSED,
    CHECK_NO_DIRECTORY_LISTING_ENABLED,
    CHECK_NO_DEFAULT_ADMIN_PANEL_EXPOSED,
]
