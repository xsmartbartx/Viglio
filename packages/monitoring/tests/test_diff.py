from __future__ import annotations

from vigilo_core.models import Confidence, Finding, Severity, Verdict
from vigilo_monitoring.diff import detect_regression

_REGISTRY_VERSION = "0.1"


def _finding(fingerprint: str, check_id: str = "VG-HDR-001", severity: Severity = Severity.HIGH) -> Finding:
    return Finding(
        check_id=check_id,
        verdict=Verdict.FAILED,
        severity=severity,
        confidence=Confidence.CONFIRMED,
        title="a failed check",
        summary="failed",
        fingerprint=fingerprint,
    )


def _detect(**overrides) -> object:
    defaults = dict(
        previous_failed={},
        current_failed={},
        ever_failed_before_previous=frozenset(),
        previous_registry_version=_REGISTRY_VERSION,
        current_registry_version=_REGISTRY_VERSION,
        previous_score=100.0,
        current_score=100.0,
        had_pending_score_drop=False,
    )
    defaults.update(overrides)
    return detect_regression(**defaults)


def test_a_fingerprint_never_seen_before_is_new_critical_or_new_high():
    finding = _finding("fp1", severity=Severity.HIGH)
    report = _detect(current_failed={"fp1": finding})

    assert len(report.events) == 1
    assert report.events[0].event_type == "new_high"
    assert report.events[0].fingerprint == "fp1"


def test_a_critical_severity_new_finding_is_new_critical():
    finding = _finding("fp1", severity=Severity.CRITICAL)
    report = _detect(current_failed={"fp1": finding})

    assert report.events[0].event_type == "new_critical"


def test_a_below_high_severity_new_finding_produces_no_event():
    finding = _finding("fp1", severity=Severity.MEDIUM)
    report = _detect(current_failed={"fp1": finding})

    assert report.events == []


def test_the_exit_criterion_a_reintroduced_misconfiguration_produces_exactly_one_regressed_alert():
    """docs/build-roadmap.md's Phase 8 exit criterion, verbatim: 'a
    deliberately reintroduced misconfiguration on a monitored fixture
    produces exactly one regressed alert — not zero, not four.'

    Sequence: scan 1 has finding X failed (first ever appearance) -> scan 2
    has X resolved (absent) -> scan 3 has X failed again (reintroduced).
    Comparing scan 2 -> scan 3 must yield exactly one `regressed` event,
    never `new_critical`/`new_high` (it's not the fingerprint's first
    appearance) and never more than one event.
    """
    finding = _finding("fp-x", severity=Severity.HIGH)

    # scan 1 -> scan 2: X was present in scan 1, absent in scan 2 (resolved).
    # "ever_failed_before_previous" for the scan-2-vs-scan-3 comparison must
    # include fp-x, since it failed in scan 1 (strictly before scan 2).
    report = _detect(
        previous_failed={},  # scan 2's failed set (absent)
        current_failed={"fp-x": finding},  # scan 3's failed set (present again)
        ever_failed_before_previous=frozenset({"fp-x"}),  # failed in scan 1
    )

    assert len(report.events) == 1
    assert report.events[0].event_type == "regressed"
    assert report.events[0].fingerprint == "fp-x"


def test_a_newly_failed_cert_expiry_check_is_cert_expiry_not_new_high():
    finding = _finding("fp-tls", check_id="VG-TLS-004", severity=Severity.MEDIUM)
    report = _detect(current_failed={"fp-tls": finding})

    assert len(report.events) == 1
    assert report.events[0].event_type == "cert_expiry"


def test_a_finding_that_stays_failed_across_two_scans_produces_no_event():
    finding = _finding("fp1")
    report = _detect(previous_failed={"fp1": finding}, current_failed={"fp1": finding})

    assert report.events == []


def test_a_resolved_finding_produces_no_event():
    finding = _finding("fp1")
    report = _detect(previous_failed={"fp1": finding}, current_failed={})

    assert report.events == []


def test_a_registry_major_version_change_produces_baseline_reset_and_no_events():
    finding = _finding("fp1")
    report = _detect(
        current_failed={"fp1": finding},
        previous_registry_version="0.5",
        current_registry_version="1.0",
        previous_score=90.0,
        current_score=50.0,
    )

    assert report.baseline_reset is True
    assert report.events == []
    assert report.score_drop is False


def test_a_first_time_score_drop_is_only_pending_not_alerted():
    report = _detect(previous_score=90.0, current_score=75.0)

    assert report.score_drop is False
    assert report.pending_score_drop is True


def test_a_second_consecutive_score_drop_is_confirmed_by_hysteresis():
    report = _detect(previous_score=75.0, current_score=60.0, had_pending_score_drop=True)

    assert report.score_drop is True
    assert report.pending_score_drop is False


def test_a_score_drop_alongside_a_critical_finding_is_confirmed_immediately():
    finding = _finding("fp1", severity=Severity.CRITICAL)
    report = _detect(
        current_failed={"fp1": finding},
        previous_score=90.0,
        current_score=70.0,
        had_pending_score_drop=False,
    )

    assert report.score_drop is True
    assert report.pending_score_drop is False


def test_a_score_recovery_clears_the_pending_drop_state():
    report = _detect(previous_score=75.0, current_score=90.0, had_pending_score_drop=True)

    assert report.score_drop is False
    assert report.pending_score_drop is False


def test_a_small_score_change_below_threshold_produces_no_drop_state():
    report = _detect(previous_score=90.0, current_score=85.0)

    assert report.score_drop is False
    assert report.pending_score_drop is False
