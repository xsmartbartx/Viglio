"""CLI category (client-side exposure): 10 checks, v0.1 target per
docs/prooflight-vision-and-architecture.md §7.2. Every check here reads
`bundle.fetched_scripts` — actual fetched JS content, not just markup — the
one category that genuinely needs `packages/probes/bundle_probe.py`.

**Every matched secret is redacted via `vigilo_core.redact.redact()` before
it becomes a `CheckResult.matched_indicator`.** The raw value never appears
in a `CheckResult`, a `Finding`, or anywhere else downstream — see
`docs/security.md` §1's redaction chokepoint.
"""

from __future__ import annotations

import re

from vigilo_checks.registry import Check, CheckResult, requires
from vigilo_core.evidence import BundleObservation, EvidenceBundle
from vigilo_core.models import CheckManifest, Confidence, Severity, Tier, Verdict
from vigilo_core.redact import redact

_AWS_KEY_PATTERN = re.compile(r"AKIA[0-9A-Z]{16}")
_STRIPE_SECRET_KEY_PATTERN = re.compile(r"sk_live_[0-9a-zA-Z]{10,}")
_SLACK_TOKEN_PATTERN = re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,}")
_GITHUB_GITLAB_TOKEN_PATTERN = re.compile(
    r"(?:ghp|gho|ghu|ghs|ghr)_[0-9A-Za-z]{36}|glpat-[0-9A-Za-z_-]{20,}"
)
_PRIVATE_KEY_BLOCK_PATTERN = re.compile(
    r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"
)
_GENERIC_SECRET_PATTERN = re.compile(
    r'[A-Za-z0-9_]*(?:_KEY|_SECRET|_TOKEN)["\']?\s*[:=]\s*["\']([A-Za-z0-9+/=_-]{20,})["\']'
)
_SOURCE_MAP_COMMENT_PATTERN = re.compile(r"//[#@]\s*sourceMappingURL=")
_DEV_BUILD_MARKER_PATTERN = re.compile(
    r"Warning: ReactDOM|You are running React in development mode"
    r"|NODE_ENV[^\n]{0,20}!==?\s*['\"]production['\"]"
    r"|process\.env\.NODE_ENV\s*=\s*['\"]development['\"]",
)
_CONSOLE_CALL_PATTERN = re.compile(r"console\.(?:log|debug|warn)\s*\(")
_CONSOLE_CALL_THRESHOLD = 10
_INTERNAL_HOSTNAME_PATTERN = re.compile(
    r"https?://(?:localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3}"
    r"|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|[a-z0-9-]+\.local\b|staging\.[a-z0-9.-]+|internal\.[a-z0-9.-]+)",
    re.IGNORECASE,
)


def _all_script_text(bundle_obs: BundleObservation) -> str:
    return "\n".join(script.excerpt for script in bundle_obs.fetched_scripts)


def _find_and_fingerprint(pattern: re.Pattern[str], text: str, kind: str) -> str | None:
    match = pattern.search(text)
    if not match:
        return None
    return str(redact(match.group(0), kind=kind))


def _secret_check(pattern: re.Pattern[str], kind: str, label: str):
    article = "an" if label[0].lower() in "aeiou" else "a"

    @requires("bundle")
    def _check(bundle: EvidenceBundle) -> CheckResult:
        text = _all_script_text(bundle.bundle)
        fingerprint = _find_and_fingerprint(pattern, text, kind)
        if fingerprint:
            detail = f"{article} {label} pattern was found in a fetched script"
            return CheckResult(Verdict.FAILED, detail, fingerprint)
        return CheckResult(Verdict.PASSED, f"no {label} pattern found in fetched scripts")

    return _check


# --- VG-CLI-001: AWS access key ----------------------------------------------

_no_aws_key = _secret_check(_AWS_KEY_PATTERN, "aws_access_key", "AWS access key")

CHECK_NO_AWS_KEY = Check(
    manifest=CheckManifest(
        check_id="VG-CLI-001",
        category="CLI",
        title="No AWS access key in client bundle",
        description="An AWS access key ID shipped to the client can be paired with a leaked or brute-forced secret key to access AWS resources directly.",
        severity_default=Severity.CRITICAL,
        confidence=Confidence.CONFIRMED,
        weight=9,
        tier_required=Tier.PASSIVE,
        references=["https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_access-keys.html"],
        remediation_template="Revoke the exposed AWS key immediately and remove it from client-side code; use a scoped backend proxy or STS temporary credentials instead.",
        introduced_in="0.1",
    cwe_id="CWE-798",
),
    evaluate=_no_aws_key,
)

# --- VG-CLI-002: Stripe (or similar) live secret key -------------------------

_no_stripe_secret = _secret_check(_STRIPE_SECRET_KEY_PATTERN, "payment_secret_key", "live payment secret key")

CHECK_NO_STRIPE_SECRET_KEY = Check(
    manifest=CheckManifest(
        check_id="VG-CLI-002",
        category="CLI",
        title="No live payment secret key in client bundle",
        description="A payment provider's live *secret* key (as opposed to its publishable key) grants full account access if shipped to the client.",
        severity_default=Severity.CRITICAL,
        confidence=Confidence.CONFIRMED,
        weight=10,
        tier_required=Tier.PASSIVE,
        references=["https://docs.stripe.com/keys#safe-keys"],
        remediation_template="Revoke the exposed key immediately; only ever use the publishable key client-side, and move secret-key calls to your backend.",
        introduced_in="0.1",
    cwe_id="CWE-798",
),
    evaluate=_no_stripe_secret,
)

# --- VG-CLI-003: Slack token --------------------------------------------------

_no_slack_token = _secret_check(_SLACK_TOKEN_PATTERN, "slack_token", "Slack token")

CHECK_NO_SLACK_TOKEN = Check(
    manifest=CheckManifest(
        check_id="VG-CLI-003",
        category="CLI",
        title="No Slack token in client bundle",
        description="A leaked Slack token can be used to read or post to the workspace's channels, depending on its scopes.",
        severity_default=Severity.HIGH,
        confidence=Confidence.CONFIRMED,
        weight=7,
        tier_required=Tier.PASSIVE,
        references=["https://api.slack.com/authentication/token-types"],
        remediation_template="Revoke the exposed Slack token and move any Slack API calls to a backend service.",
        introduced_in="0.1",
    cwe_id="CWE-798",
),
    evaluate=_no_slack_token,
)

# --- VG-CLI-004: GitHub/GitLab personal access token -------------------------

_no_github_gitlab_token = _secret_check(_GITHUB_GITLAB_TOKEN_PATTERN, "vcs_token", "GitHub/GitLab access token")

CHECK_NO_GITHUB_GITLAB_TOKEN = Check(
    manifest=CheckManifest(
        check_id="VG-CLI-004",
        category="CLI",
        title="No GitHub/GitLab token in client bundle",
        description="A leaked source-control access token can expose private repositories or allow unauthorized commits, depending on its scopes.",
        severity_default=Severity.CRITICAL,
        confidence=Confidence.CONFIRMED,
        weight=9,
        tier_required=Tier.PASSIVE,
        references=["https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/about-authentication-to-github"],
        remediation_template="Revoke the exposed token immediately and audit recent repository activity for unauthorized access.",
        introduced_in="0.1",
    cwe_id="CWE-798",
),
    evaluate=_no_github_gitlab_token,
)

# --- VG-CLI-005: embedded private key block ----------------------------------

_no_private_key_block = _secret_check(_PRIVATE_KEY_BLOCK_PATTERN, "private_key", "private key block")

CHECK_NO_PRIVATE_KEY_BLOCK = Check(
    manifest=CheckManifest(
        check_id="VG-CLI-005",
        category="CLI",
        title="No private key embedded in client bundle",
        description="A PEM-format private key shipped to every visitor's browser is a critical compromise of whatever system that key authenticates.",
        severity_default=Severity.CRITICAL,
        confidence=Confidence.CONFIRMED,
        weight=10,
        tier_required=Tier.PASSIVE,
        references=["https://owasp.org/www-community/vulnerabilities/Use_of_hard-coded_password"],
        remediation_template="Rotate the exposed key immediately and remove it from any client-shipped code.",
        introduced_in="0.1",
    cwe_id="CWE-321",
),
    evaluate=_no_private_key_block,
)

# --- VG-CLI-006: generic high-entropy secret near a key/secret/token name ----

_no_generic_secret = _secret_check(_GENERIC_SECRET_PATTERN, "generic_secret", "generic API key/secret")

CHECK_NO_GENERIC_SECRET = Check(
    manifest=CheckManifest(
        check_id="VG-CLI-006",
        category="CLI",
        title="No generic high-entropy secret in client bundle",
        description="A long opaque string assigned to an identifier named like a key, secret or token is very often a credential that shouldn't be client-side, even when it doesn't match a known provider's format.",
        severity_default=Severity.MEDIUM,
        confidence=Confidence.INDICATED,
        weight=4,
        tier_required=Tier.PASSIVE,
        references=["https://owasp.org/www-community/vulnerabilities/Use_of_hard-coded_password"],
        remediation_template="Confirm whether the flagged value is a real secret; if so, revoke and move it server-side. If it's a public identifier (e.g. a publishable key), consider renaming the variable to avoid this pattern.",
        false_positive_notes="Matches any 20+ character opaque value assigned to a *_KEY/*_SECRET/*_TOKEN-named identifier — publishable/public keys that happen to be named this way will misfire as a failure.",
        introduced_in="0.1",
    cwe_id="CWE-798",
),
    evaluate=_no_generic_secret,
)

# --- VG-CLI-007: source map comment present ----------------------------------


@requires("bundle")
def _no_source_map_comment(bundle: EvidenceBundle) -> CheckResult:
    text = _all_script_text(bundle.bundle)
    if _SOURCE_MAP_COMMENT_PATTERN.search(text):
        return CheckResult(Verdict.FAILED, "a sourceMappingURL comment was found in a fetched script")
    return CheckResult(Verdict.PASSED, "no sourceMappingURL comment found in fetched scripts")


CHECK_NO_SOURCE_MAP_COMMENT = Check(
    manifest=CheckManifest(
        check_id="VG-CLI-007",
        category="CLI",
        title="No source map reference shipped to production",
        description="A sourceMappingURL comment (or a reachable .map file) hands an attacker your original, unminified source and file/variable names.",
        severity_default=Severity.LOW,
        confidence=Confidence.CONFIRMED,
        weight=2,
        tier_required=Tier.PASSIVE,
        references=["https://developer.chrome.com/docs/devtools/javascript/source-maps"],
        remediation_template="Disable source map generation for production builds, or serve them only to authenticated internal users.",
        false_positive_notes="Detects only the in-file comment referencing a source map; it does not verify the map file itself is actually reachable.",
        introduced_in="0.1",
    cwe_id="CWE-540",
),
    evaluate=_no_source_map_comment,
)

# --- VG-CLI-008: development-mode build marker -------------------------------


@requires("bundle")
def _no_dev_build_marker(bundle: EvidenceBundle) -> CheckResult:
    text = _all_script_text(bundle.bundle)
    if _DEV_BUILD_MARKER_PATTERN.search(text):
        return CheckResult(Verdict.FAILED, "a development-mode build marker was found in a fetched script")
    return CheckResult(Verdict.PASSED, "no development-mode build marker found")


CHECK_NO_DEV_BUILD_MARKER = Check(
    manifest=CheckManifest(
        check_id="VG-CLI-008",
        category="CLI",
        title="No development-mode build shipped to production",
        description="A development build is larger, slower, and often more verbose about internal errors than a production build — it should never be what visitors actually receive.",
        severity_default=Severity.LOW,
        confidence=Confidence.INDICATED,
        weight=2,
        tier_required=Tier.PASSIVE,
        references=["https://react.dev/reference/react-dom/client/hydrateRoot#minifying-and-avoiding-development-builds-in-production"],
        remediation_template="Ensure the production build pipeline sets NODE_ENV=production (or the framework's equivalent) before deployment.",
        false_positive_notes="Matches a small, React-centric set of known development-build string signatures; other frameworks' dev-mode markers are not covered.",
        introduced_in="0.1",
    cwe_id="CWE-489",
),
    evaluate=_no_dev_build_marker,
)

# --- VG-CLI-009: bounded console.log/debug/warn usage ------------------------


@requires("bundle")
def _bounded_console_calls(bundle: EvidenceBundle) -> CheckResult:
    text = _all_script_text(bundle.bundle)
    count = len(_CONSOLE_CALL_PATTERN.findall(text))
    if count > _CONSOLE_CALL_THRESHOLD:
        detail = f"{count} console.log/debug/warn call(s) found in fetched scripts (threshold {_CONSOLE_CALL_THRESHOLD})"
        return CheckResult(Verdict.FAILED, detail, str(count))
    return CheckResult(Verdict.PASSED, f"{count} console.log/debug/warn call(s) found")


CHECK_BOUNDED_CONSOLE_CALLS = Check(
    manifest=CheckManifest(
        check_id="VG-CLI-009",
        category="CLI",
        title="Bounded console logging in production",
        description="Excessive console.log/debug/warn calls in shipped code often leak internal state, API responses, or debugging notes to anyone with devtools open.",
        severity_default=Severity.INFO,
        confidence=Confidence.INDICATED,
        weight=1,
        tier_required=Tier.PASSIVE,
        references=["https://owasp.org/www-project-web-security-testing-guide/"],
        remediation_template="Strip debug console calls from the production build (most bundlers support this via a build plugin or a linter rule).",
        false_positive_notes="Counts raw occurrences of the call syntax across fetched scripts, including inside third-party libraries the site didn't author.",
        introduced_in="0.1",
    cwe_id="CWE-215",
),
    evaluate=_bounded_console_calls,
)

# --- VG-CLI-010: no hardcoded internal/staging hostname ----------------------


@requires("bundle")
def _no_hardcoded_internal_hostname(bundle: EvidenceBundle) -> CheckResult:
    text = _all_script_text(bundle.bundle)
    match = _INTERNAL_HOSTNAME_PATTERN.search(text)
    if match:
        return CheckResult(Verdict.FAILED, f"an internal/staging hostname was found in a fetched script: {match.group(0)}", match.group(0))
    return CheckResult(Verdict.PASSED, "no hardcoded internal/staging hostname found")


CHECK_NO_HARDCODED_INTERNAL_HOSTNAME = Check(
    manifest=CheckManifest(
        check_id="VG-CLI-010",
        category="CLI",
        title="No hardcoded internal/staging hostname in client bundle",
        description="A hardcoded reference to localhost, a private IP range, or a staging/internal hostname can leak infrastructure details and sometimes an unauthenticated fallback endpoint.",
        severity_default=Severity.LOW,
        confidence=Confidence.INDICATED,
        weight=2,
        tier_required=Tier.PASSIVE,
        references=["https://owasp.org/www-project-web-security-testing-guide/"],
        remediation_template="Remove hardcoded internal/staging URLs from production code; use environment-specific configuration instead.",
        false_positive_notes="A private IP or 'staging.'/'internal.' hostname committed intentionally for a documented local-dev fallback will misfire as a failure.",
        introduced_in="0.1",
    cwe_id="CWE-200",
),
    evaluate=_no_hardcoded_internal_hostname,
)


CHECKS: list[Check] = [
    CHECK_NO_AWS_KEY,
    CHECK_NO_STRIPE_SECRET_KEY,
    CHECK_NO_SLACK_TOKEN,
    CHECK_NO_GITHUB_GITLAB_TOKEN,
    CHECK_NO_PRIVATE_KEY_BLOCK,
    CHECK_NO_GENERIC_SECRET,
    CHECK_NO_SOURCE_MAP_COMMENT,
    CHECK_NO_DEV_BUILD_MARKER,
    CHECK_BOUNDED_CONSOLE_CALLS,
    CHECK_NO_HARDCODED_INTERNAL_HOSTNAME,
]
