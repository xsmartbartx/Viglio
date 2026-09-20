"""detect_regression(): the phase's exit-criterion algorithm
(docs/prooflight-vision-and-architecture.md §10.2/§10.3). Pure — no
session, no I/O — matching `resolve_authorization`/`consume`'s established
pattern; the caller (`packages/orchestrator/jobs.py`'s `detect_regression_job`)
loads two scans' failed-finding sets plus a target's full failure history
and reduces them to this function's inputs.

**Transition rules** (vision doc's table, applied to the failed-fingerprint
set of scan N-1 vs. scan N):

- Absent in N-1, present in N, `check_id == VG-TLS-004` -> `cert_expiry`
  (packages/checks/src/vigilo_checks/tls.py's cert-expiring-soon check,
  MEDIUM severity — special-cased so it alerts regardless of the severity
  gate below; this reuses the check's already-persisted FAILED status,
  no new TLS-evidence fetch at diff time).
- Absent in N-1, present in N, fingerprint in `ever_failed_before_previous`
  -> `regressed` (it was previously seen failed, then resolved, now back).
- Absent in N-1, present in N, severity >= HIGH, otherwise -> `new_critical`/
  `new_high` (a fingerprint genuinely never seen failed on this target
  before).
- Absent in N-1, present in N, severity < HIGH, and not a regression ->
  no event (below the vision table's severity gate).
- Present in N-1, absent in N -> "resolved", tracked nowhere: no Alert
  type exists for it in the domain model and nothing in this phase's UI
  needs a fix-confirmation feed. A later phase can extend this without
  changing this function's shape.
- Registry MAJOR version changed between N-1 and N -> `baseline_reset`;
  every other comparison is skipped, matching the vision table's explicit
  "no alerts emitted" note.
- Score dropped >= 10 points -> only surfaced as `score_drop=True` if
  `had_pending_score_drop` (this is the *second* consecutive drop —
  hysteresis) or the current scan also produced a `new_critical`/
  `cert_expiry` event ("unless a critical is involved"); otherwise it's
  remembered via `pending_score_drop=True` for the next cycle and not
  alerted yet.
"""

from __future__ import annotations

from vigilo_core.models import Finding, Severity
from vigilo_monitoring.models import RegressionEvent, RegressionReport

_CERT_EXPIRY_CHECK_ID = "VG-TLS-004"
_HIGH_OR_ABOVE = frozenset({Severity.CRITICAL, Severity.HIGH})
_SCORE_DROP_THRESHOLD = 10.0


def _major(registry_version: str) -> str:
    return registry_version.split(".", 1)[0]


def detect_regression(
    previous_failed: dict[str, Finding],
    current_failed: dict[str, Finding],
    ever_failed_before_previous: frozenset[str],
    previous_registry_version: str,
    current_registry_version: str,
    previous_score: float,
    current_score: float,
    had_pending_score_drop: bool,
    suppressed_fingerprints: frozenset[str] = frozenset(),
) -> RegressionReport:
    """`suppressed_fingerprints` (post-Phase-9's suppression workflow,
    `packages/project`) skips a fingerprint's transition entirely — no
    `new_critical`/`new_high`/`regressed`/`cert_expiry` event, and it
    doesn't count toward `has_critical_event` for score-drop hysteresis
    either, since accepting a risk means exactly "stop treating this as
    urgent" (docs/build-roadmap.md's post-Phase-9 entry). The caller
    (`apps/scanner`'s `detect_regression_job`) fetches the set the same
    way it already fetches `ever_failed_before_previous`."""
    if _major(previous_registry_version) != _major(current_registry_version):
        return RegressionReport(
            events=[], score_drop=False, pending_score_drop=False, baseline_reset=True
        )

    events: list[RegressionEvent] = []
    for fingerprint, finding in current_failed.items():
        if fingerprint in previous_failed:
            continue  # still open, no transition
        if fingerprint in suppressed_fingerprints:
            continue  # accepted risk — no alert noise for something already accepted

        if finding.check_id == _CERT_EXPIRY_CHECK_ID:
            event_type = "cert_expiry"
        elif fingerprint in ever_failed_before_previous:
            event_type = "regressed"
        elif finding.severity in _HIGH_OR_ABOVE:
            event_type = "new_critical" if finding.severity == Severity.CRITICAL else "new_high"
        else:
            continue  # below the severity gate, no event

        events.append(
            RegressionEvent(
                event_type=event_type,
                fingerprint=fingerprint,
                check_id=finding.check_id,
                severity=finding.severity.value,
            )
        )

    has_critical_event = any(
        event.event_type in ("new_critical", "cert_expiry") for event in events
    )
    dropped = (previous_score - current_score) >= _SCORE_DROP_THRESHOLD
    score_drop = dropped and (had_pending_score_drop or has_critical_event)
    pending_score_drop = dropped and not score_drop

    return RegressionReport(
        events=events,
        score_drop=score_drop,
        pending_score_drop=pending_score_drop,
        baseline_reset=False,
    )
