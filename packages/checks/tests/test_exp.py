from datetime import UTC, datetime

from vigilo_checks import exp
from vigilo_core.evidence import (
    DetectedPath,
    EvidenceBundle,
    HttpObservation,
    PathObservation,
    WellKnownObservation,
)
from vigilo_core.models import Verdict


def _bundle(wellknown=None, http=None, paths=None) -> EvidenceBundle:
    return EvidenceBundle(
        bundle_id="test",
        target_origin="https://example.com",
        captured_at=datetime.now(UTC),
        wellknown=wellknown,
        http=http,
        paths=paths,
    )


def _detected(kind: str, path: str = "/hit") -> DetectedPath:
    return DetectedPath(path=path, kind=kind, status_code=200, indicator="test hit")


def test_wellknown_checks_are_inconclusive_without_wellknown_evidence():
    for check in (exp.CHECK_SECURITY_TXT_PRESENT, exp.CHECK_ROBOTS_TXT_PRESENT, exp.CHECK_SITEMAP_PRESENT, exp.CHECK_MANIFEST_PRESENT):
        result = check.evaluate(_bundle())
        assert result.verdict == Verdict.INCONCLUSIVE, check.manifest.check_id


def test_verbose_error_check_is_inconclusive_without_http_evidence():
    result = exp.CHECK_NO_VERBOSE_ERROR_PAGE.evaluate(_bundle())
    assert result.verdict == Verdict.INCONCLUSIVE


def test_security_txt_present():
    present = WellKnownObservation(security_txt_present=True)
    absent = WellKnownObservation(security_txt_present=False)

    assert exp.CHECK_SECURITY_TXT_PRESENT.evaluate(_bundle(present)).verdict == Verdict.PASSED
    assert exp.CHECK_SECURITY_TXT_PRESENT.evaluate(_bundle(absent)).verdict == Verdict.FAILED


def test_robots_txt_present_never_fails():
    """Purely informational (INFO severity) — absence is reported but never
    scored as a failure."""
    present = WellKnownObservation(robots_txt_present=True)
    absent = WellKnownObservation(robots_txt_present=False)

    assert exp.CHECK_ROBOTS_TXT_PRESENT.evaluate(_bundle(present)).verdict == Verdict.PASSED
    assert exp.CHECK_ROBOTS_TXT_PRESENT.evaluate(_bundle(absent)).verdict == Verdict.PASSED


def test_sitemap_present_never_fails():
    assert exp.CHECK_SITEMAP_PRESENT.evaluate(_bundle(WellKnownObservation(sitemap_present=True))).verdict == Verdict.PASSED
    assert exp.CHECK_SITEMAP_PRESENT.evaluate(_bundle(WellKnownObservation(sitemap_present=False))).verdict == Verdict.PASSED


def test_manifest_present_never_fails():
    assert exp.CHECK_MANIFEST_PRESENT.evaluate(_bundle(WellKnownObservation(manifest_present=True))).verdict == Verdict.PASSED
    assert exp.CHECK_MANIFEST_PRESENT.evaluate(_bundle(WellKnownObservation(manifest_present=False))).verdict == Verdict.PASSED


def test_no_verbose_error_page():
    clean = HttpObservation(url="https://example.com/", status_code=200, body_excerpt="<html>Hello</html>")
    django_leak = HttpObservation(
        url="https://example.com/",
        status_code=500,
        body_excerpt="django.core.exceptions.ImproperlyConfigured: ...",
    )
    python_leak = HttpObservation(
        url="https://example.com/",
        status_code=500,
        body_excerpt="Traceback (most recent call last):\n  File ...",
    )

    assert exp.CHECK_NO_VERBOSE_ERROR_PAGE.evaluate(_bundle(http=clean)).verdict == Verdict.PASSED
    assert exp.CHECK_NO_VERBOSE_ERROR_PAGE.evaluate(_bundle(http=django_leak)).verdict == Verdict.FAILED
    assert exp.CHECK_NO_VERBOSE_ERROR_PAGE.evaluate(_bundle(http=python_leak)).verdict == Verdict.FAILED


_ACTIVE_TIER_CHECKS = [
    (exp.CHECK_NO_REPO_METADATA_EXPOSED, "repo_metadata"),
    (exp.CHECK_NO_BACKUP_ARTEFACTS_EXPOSED, "backup_artefact"),
    (exp.CHECK_NO_EXPOSED_CONFIG_FILES, "exposed_config"),
    (exp.CHECK_NO_DEBUG_ROUTES_EXPOSED, "debug_route"),
    (exp.CHECK_NO_TEST_ROUTES_EXPOSED, "test_route"),
    (exp.CHECK_NO_DIRECTORY_LISTING_ENABLED, "directory_listing"),
    (exp.CHECK_NO_DEFAULT_ADMIN_PANEL_EXPOSED, "admin_panel"),
]


def test_active_tier_checks_are_inconclusive_without_paths_evidence():
    for check, _kind in _ACTIVE_TIER_CHECKS:
        result = check.evaluate(_bundle())
        assert result.verdict == Verdict.INCONCLUSIVE, check.manifest.check_id


def test_active_tier_checks_pass_when_nothing_of_their_kind_is_detected():
    empty = PathObservation(checked=["/x"], detected=[])
    for check, _kind in _ACTIVE_TIER_CHECKS:
        result = check.evaluate(_bundle(paths=empty))
        assert result.verdict == Verdict.PASSED, check.manifest.check_id


def test_active_tier_checks_fail_when_their_kind_is_detected():
    for check, kind in _ACTIVE_TIER_CHECKS:
        hit = PathObservation(checked=["/hit"], detected=[_detected(kind)])
        result = check.evaluate(_bundle(paths=hit))
        assert result.verdict == Verdict.FAILED, check.manifest.check_id


def test_active_tier_checks_ignore_hits_of_a_different_kind():
    # VG-EXP-006 only cares about "repo_metadata" hits, not e.g. "admin_panel"
    unrelated_hit = PathObservation(checked=["/admin/"], detected=[_detected("admin_panel")])
    result = exp.CHECK_NO_REPO_METADATA_EXPOSED.evaluate(_bundle(paths=unrelated_hit))
    assert result.verdict == Verdict.PASSED


def test_active_tier_checks_aggregate_multiple_offenders_of_the_same_kind():
    hits = PathObservation(
        checked=["/backup.zip", "/backup.sql"],
        detected=[
            _detected("backup_artefact", "/backup.zip"),
            _detected("backup_artefact", "/backup.sql"),
        ],
    )
    result = exp.CHECK_NO_BACKUP_ARTEFACTS_EXPOSED.evaluate(_bundle(paths=hits))
    assert result.verdict == Verdict.FAILED
    assert "/backup.zip" in result.detail
    assert "/backup.sql" in result.detail


def test_all_seven_active_tier_checks_are_tier_required_active():
    for check, _kind in _ACTIVE_TIER_CHECKS:
        assert check.manifest.tier_required.value == "active", check.manifest.check_id


def test_active_tier_check_ids_continue_from_006():
    ids = [check.manifest.check_id for check, _kind in _ACTIVE_TIER_CHECKS]
    assert ids == [
        "VG-EXP-006",
        "VG-EXP-007",
        "VG-EXP-008",
        "VG-EXP-009",
        "VG-EXP-010",
        "VG-EXP-011",
        "VG-EXP-012",
    ]
