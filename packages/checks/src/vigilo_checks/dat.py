"""DAT category (data platform posture): 4 checks, v0.1 target per
docs/prooflight-vision-and-architecture.md §7.2 — docs/vision.md's flagship
failure mode: "database readable by anyone with the public anon key."

All four read `bundle.backends`, populated by
`packages/probes/backend_probe.py`. That probe already performed the one
bounded, egress-guarded reachability request per detected backend; these
checks are pure — they only interpret what `probe_indicates_open` and
`key_role` already say, never make a request themselves (docs/modules.md §4).
"""

from __future__ import annotations

from vigilo_checks.registry import Check, CheckResult, requires
from vigilo_core.evidence import EvidenceBundle
from vigilo_core.models import CheckManifest, Confidence, Severity, Tier, Verdict

# --- VG-DAT-001: no service-role/admin key exposed ---------------------------


@requires("backends")
def _no_service_role_key_exposed(bundle: EvidenceBundle) -> CheckResult:
    offenders = [b for b in bundle.backends.detected if b.key_role == "service_role"]
    if offenders:
        names = ", ".join(f"{b.provider}:{b.key_fingerprint}" for b in offenders)
        detail = f"a service-role/admin key was found exposed in the client bundle: {names}"
        return CheckResult(Verdict.FAILED, detail, names)
    return CheckResult(Verdict.PASSED, "no service-role/admin key found exposed in the client bundle")


CHECK_NO_SERVICE_ROLE_KEY_EXPOSED = Check(
    manifest=CheckManifest(
        check_id="VG-DAT-001",
        category="DAT",
        title="No backend service-role/admin key in client bundle",
        description="A service-role (or admin) key bypasses row-level security entirely — shipping it to the client hands every visitor full database access.",
        severity_default=Severity.CRITICAL,
        confidence=Confidence.CONFIRMED,
        weight=10,
        tier_required=Tier.PASSIVE,
        references=["https://supabase.com/docs/guides/api/api-keys"],
        remediation_template="Revoke the exposed service-role key immediately, rotate it, and ensure only the anon/publishable key is ever shipped to the client.",
        introduced_in="0.1",
    ),
    evaluate=_no_service_role_key_exposed,
)

# --- VG-DAT-002: Supabase schema is not publicly introspectable --------------


@requires("backends")
def _supabase_schema_not_introspectable(bundle: EvidenceBundle) -> CheckResult:
    offenders = [
        b
        for b in bundle.backends.detected
        if b.provider == "supabase" and b.key_role == "anon" and b.probe_indicates_open
    ]
    if offenders:
        urls = ", ".join(b.url for b in offenders)
        detail = f"a Supabase project's REST schema is publicly introspectable via its anon key: {urls}"
        return CheckResult(Verdict.FAILED, detail, urls)
    return CheckResult(Verdict.PASSED, "no publicly introspectable Supabase schema detected")


CHECK_SUPABASE_SCHEMA_NOT_INTROSPECTABLE = Check(
    manifest=CheckManifest(
        check_id="VG-DAT-002",
        category="DAT",
        title="Supabase REST schema is not publicly introspectable",
        description="An anon key that can retrieve the full PostgREST schema listing suggests row-level security has not been configured to restrict what the anon role can see.",
        severity_default=Severity.HIGH,
        confidence=Confidence.INDICATED,
        weight=7,
        tier_required=Tier.PASSIVE,
        references=["https://supabase.com/docs/guides/database/postgres/row-level-security"],
        remediation_template="Enable and configure row-level security policies on every table so the anon role only sees what it should.",
        false_positive_notes="Schema introspectability alone does not prove sensitive row data is exposed — it indicates the API surface is visible, which is the first step an attacker would take next.",
        introduced_in="0.1",
    ),
    evaluate=_supabase_schema_not_introspectable,
)

# --- VG-DAT-003: Firebase Realtime Database is not publicly readable ---------


@requires("backends")
def _firebase_not_publicly_readable(bundle: EvidenceBundle) -> CheckResult:
    offenders = [b for b in bundle.backends.detected if b.provider == "firebase" and b.probe_indicates_open]
    if offenders:
        urls = ", ".join(b.url for b in offenders)
        detail = f"a Firebase Realtime Database is publicly readable without authentication: {urls}"
        return CheckResult(Verdict.FAILED, detail, urls)
    return CheckResult(Verdict.PASSED, "no publicly readable Firebase Realtime Database detected")


CHECK_FIREBASE_NOT_PUBLICLY_READABLE = Check(
    manifest=CheckManifest(
        check_id="VG-DAT-003",
        category="DAT",
        title="Firebase Realtime Database is not publicly readable",
        description="Firebase's default security rules for a new project allow anyone to read and write the entire database — a common misconfiguration left over from initial setup.",
        severity_default=Severity.CRITICAL,
        confidence=Confidence.CONFIRMED,
        weight=10,
        tier_required=Tier.PASSIVE,
        references=["https://firebase.google.com/docs/database/security"],
        remediation_template="Set Firebase Realtime Database security rules to require authentication before any read or write.",
        introduced_in="0.1",
    ),
    evaluate=_firebase_not_publicly_readable,
)

# --- VG-DAT-004: no publicly listable object storage bucket ------------------


@requires("backends")
def _no_public_bucket_listing(bundle: EvidenceBundle) -> CheckResult:
    offenders = [
        b for b in bundle.backends.detected if b.provider in ("s3", "gcs") and b.probe_indicates_open
    ]
    if offenders:
        urls = ", ".join(f"{b.provider}:{b.url}" for b in offenders)
        detail = f"a publicly listable object storage bucket was found: {urls}"
        return CheckResult(Verdict.FAILED, detail, urls)
    return CheckResult(Verdict.PASSED, "no publicly listable object storage bucket detected")


CHECK_NO_PUBLIC_BUCKET_LISTING = Check(
    manifest=CheckManifest(
        check_id="VG-DAT-004",
        category="DAT",
        title="No publicly listable object storage bucket",
        description="A bucket that allows anonymous listing reveals its full object inventory — filenames often leak far more than the bucket owner intended, even before any object is fetched.",
        severity_default=Severity.HIGH,
        confidence=Confidence.CONFIRMED,
        weight=7,
        tier_required=Tier.PASSIVE,
        references=["https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-control-block-public-access.html"],
        remediation_template="Disable public listing on the bucket (S3 Block Public Access / GCS uniform bucket-level access) and grant object-level access only where actually needed.",
        introduced_in="0.1",
    ),
    evaluate=_no_public_bucket_listing,
)


CHECKS: list[Check] = [
    CHECK_NO_SERVICE_ROLE_KEY_EXPOSED,
    CHECK_SUPABASE_SCHEMA_NOT_INTROSPECTABLE,
    CHECK_FIREBASE_NOT_PUBLICLY_READABLE,
    CHECK_NO_PUBLIC_BUCKET_LISTING,
]
