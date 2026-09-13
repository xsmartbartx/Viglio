"""The backend probe: detects backend-as-a-service credentials/endpoints
shipped to the client — docs/vision.md's flagship failure mode ("database
readable by anyone with the public anon key") — and makes ONE bounded,
read-only reachability request to each discovered backend.

**Security-critical invariant**: every discovered URL — a Supabase project,
a Firebase database, an S3/GCS bucket — is a target the scanner did NOT
receive from the user. It came from content a hostile or compromised page
controls. It goes through `validate_and_pin` exactly like the user's own
submitted URL, with zero exceptions. See
`packages/probes/tests/test_backend_probe_ssrf.py`, the build-blocking suite
proving a crafted "backend URL" pointing at internal address space is
denied, never fetched — the same standard as
`packages/security/tests/test_egress_guard.py`.

Detection is intentionally conservative for v1: one candidate key per
Supabase project URL found in the combined text (preferring a leaked
service-role key over an anon key if both appear), Firebase Realtime
Database URLs only (not Firestore, which needs a different, API-key-in-query
auth model out of scope here), and S3/GCS bucket public-listing checks.
"""

from __future__ import annotations

import base64
import json
import re
from urllib.parse import urlsplit

import httpx

from vigilo_core.evidence import (
    BackendObservation,
    BundleObservation,
    DetectedBackend,
    HttpObservation,
)
from vigilo_core.redact import redact
from vigilo_core.validation import ValidationError
from vigilo_probes.http_probe import build_pinned_url
from vigilo_security import EgressDenied
from vigilo_security.egress_guard import Resolver, validate_and_pin

_REQUEST_TIMEOUT = 10.0
_MAX_RESPONSE_BYTES = 64 * 1024
_USER_AGENT = "VigiloScanner/0.1 (+https://vigilo.io/scanner)"

_SUPABASE_URL_PATTERN = re.compile(r"https://([a-z0-9]{20})\.supabase\.co")
_JWT_PATTERN = re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")
_FIREBASE_DATABASE_URL_PATTERN = re.compile(
    r'databaseURL["\']?\s*[:=]\s*["\']([^"\']*firebaseio\.com[^"\']*)["\']'
)
_S3_VIRTUAL_HOSTED_PATTERN = re.compile(
    r"https://([a-z0-9.\-]+)\.s3(?:[.\-][a-z0-9\-]+)?\.amazonaws\.com"
)
_S3_PATH_STYLE_PATTERN = re.compile(
    r"https://s3(?:[.\-][a-z0-9\-]+)?\.amazonaws\.com/([a-z0-9.\-]+)"
)
_GCS_BUCKET_PATTERN = re.compile(r"https://storage\.googleapis\.com/([a-z0-9._\-]+)")


def _all_text(bundle_obs: BundleObservation | None, http: HttpObservation | None) -> str:
    parts = [http.body_excerpt] if http else []
    if bundle_obs:
        parts.extend(script.excerpt for script in bundle_obs.fetched_scripts)
    return "\n".join(parts)


def _decode_jwt_role(token: str) -> str | None:
    try:
        _, payload_b64, _ = token.split(".")
        padding = "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64 + padding))
    except Exception:  # noqa: BLE001 — a malformed JWT from hostile input is not a bug
        return None
    role = payload.get("role") if isinstance(payload, dict) else None
    return role if isinstance(role, str) else None


def _detect_supabase(text: str) -> list[tuple[str, str | None, str | None]]:
    """Returns (project_url, key, role) tuples, one per distinct project URL
    found. If multiple JWTs are present, a leaked service-role key takes
    priority over an anon key for surfacing — this is a v1 simplification,
    not per-project proximity pairing."""
    urls = {f"https://{ref}.supabase.co" for ref in _SUPABASE_URL_PATTERN.findall(text)}
    if not urls:
        return []

    candidates = [(token, _decode_jwt_role(token)) for token in set(_JWT_PATTERN.findall(text))]
    candidates = [(token, role) for token, role in candidates if role in ("anon", "service_role")]
    candidates.sort(key=lambda item: 0 if item[1] == "service_role" else 1)

    best_token, best_role = candidates[0] if candidates else (None, None)
    return [(url, best_token, best_role) for url in sorted(urls)]


def _detect_firebase(text: str) -> list[str]:
    return sorted(set(_FIREBASE_DATABASE_URL_PATTERN.findall(text)))


def _detect_s3_buckets(text: str) -> list[str]:
    buckets = set(_S3_VIRTUAL_HOSTED_PATTERN.findall(text)) | set(
        _S3_PATH_STYLE_PATTERN.findall(text)
    )
    return sorted(buckets)


def _detect_gcs_buckets(text: str) -> list[str]:
    return sorted(set(_GCS_BUCKET_PATTERN.findall(text)))


async def _probe_url(
    client: httpx.AsyncClient,
    url: str,
    resolver: Resolver | None,
    extra_headers: dict[str, str],
) -> tuple[int | None, str | None, str]:
    """Returns (status_code, error, body). Never raises for a target the
    egress guard denies — that's recorded as the error, same contract as
    every other probe in this package."""
    try:
        conn = validate_and_pin(url, resolver=resolver)
    except (ValidationError, EgressDenied) as exc:
        return None, f"{exc.code.value}: {exc.message}", ""

    parts = urlsplit(url)
    path = parts.path or "/"
    request_url = build_pinned_url(conn, f"{path}?{parts.query}" if parts.query else path)

    try:
        async with client.stream(
            "GET",
            request_url,
            headers={"Host": conn.host, "User-Agent": _USER_AGENT, **extra_headers},
            extensions={"sni_hostname": conn.host},
        ) as response:
            chunks = bytearray()
            async for chunk in response.aiter_bytes():
                chunks.extend(chunk)
                if len(chunks) >= _MAX_RESPONSE_BYTES:
                    break
            return response.status_code, None, bytes(chunks).decode("utf-8", errors="replace")
    except httpx.HTTPError as exc:
        return None, str(exc), ""


async def run_backend_checks(
    bundle_obs: BundleObservation | None,
    http: HttpObservation | None,
    resolver: Resolver | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> BackendObservation:
    text = _all_text(bundle_obs, http)
    detected: list[DetectedBackend] = []

    async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT, transport=transport) as client:
        for project_url, key, role in _detect_supabase(text):
            key_fingerprint = str(redact(key, kind="supabase_key")) if key else None

            if role == "service_role":
                # A service-role key leaking to the client is unambiguous on
                # its own — no live probe needed or wanted.
                detected.append(
                    DetectedBackend(
                        provider="supabase",
                        url=project_url,
                        key_role=role,
                        key_fingerprint=key_fingerprint,
                        probe_attempted=False,
                    )
                )
                continue

            headers = {"apikey": key} if key else {}
            rest_url = f"{project_url}/rest/v1/"
            status, error, body = await _probe_url(client, rest_url, resolver, headers)
            indicates_open = status == 200 and ('"paths"' in body or '"definitions"' in body)
            detected.append(
                DetectedBackend(
                    provider="supabase",
                    url=project_url,
                    key_role=role,
                    key_fingerprint=key_fingerprint,
                    probe_attempted=True,
                    probe_status_code=status,
                    probe_indicates_open=indicates_open,
                    probe_error=error,
                )
            )

        for database_url in _detect_firebase(text):
            probe_url = f"{database_url.rstrip('/')}/.json"
            status, error, body = await _probe_url(client, probe_url, resolver, {})
            stripped = body.strip()
            indicates_open = (
                status == 200 and stripped not in ("null", "") and '"error"' not in stripped[:200]
            )
            detected.append(
                DetectedBackend(
                    provider="firebase",
                    url=database_url,
                    probe_attempted=True,
                    probe_status_code=status,
                    probe_indicates_open=indicates_open,
                    probe_error=error,
                )
            )

        for bucket in _detect_s3_buckets(text):
            bucket_root = f"https://{bucket}.s3.amazonaws.com"
            listing_url = f"{bucket_root}/?list-type=2"
            status, error, _body = await _probe_url(client, listing_url, resolver, {})
            detected.append(
                DetectedBackend(
                    provider="s3",
                    url=bucket_root,
                    probe_attempted=True,
                    probe_status_code=status,
                    probe_indicates_open=status == 200,
                    probe_error=error,
                )
            )

        for bucket in _detect_gcs_buckets(text):
            listing_url = f"https://storage.googleapis.com/storage/v1/b/{bucket}/o"
            status, error, _body = await _probe_url(client, listing_url, resolver, {})
            detected.append(
                DetectedBackend(
                    provider="gcs",
                    url=f"https://storage.googleapis.com/{bucket}",
                    probe_attempted=True,
                    probe_status_code=status,
                    probe_indicates_open=status == 200,
                    probe_error=error,
                )
            )

    return BackendObservation(detected=detected)
