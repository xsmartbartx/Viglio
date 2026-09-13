"""The literal, testable form of the Phase 1 exit criterion: "a scan of a
local fixture target produces a byte-identical score twice in a row."
Determinism is a property of the pure checks+scoring layers over a fixed
EvidenceBundle, not of the network — so this test never touches probes at
all (docs/architecture.md §8).
"""

from pathlib import Path

from vigilo_cli.pipeline import evaluate
from vigilo_core.evidence import EvidenceBundle
from vigilo_core.models import Verdict

_FIXTURES_DIR = Path(__file__).resolve().parents[3] / "fixtures" / "golden-targets"


def _load(name: str) -> EvidenceBundle:
    path = _FIXTURES_DIR / name
    return EvidenceBundle.model_validate_json(path.read_text(encoding="utf-8"))


def test_good_config_scores_identically_across_two_runs():
    bundle = _load("good-config.json")

    findings_1, score_1 = evaluate(bundle)
    findings_2, score_2 = evaluate(bundle)

    assert score_1 == score_2
    assert findings_1 == findings_2


def test_bad_config_scores_identically_across_two_runs():
    bundle = _load("bad-config.json")

    _findings_1, score_1 = evaluate(bundle)
    _findings_2, score_2 = evaluate(bundle)

    assert score_1 == score_2


def test_good_config_scores_meaningfully_higher_than_bad_config():
    good_findings, good_score = evaluate(_load("good-config.json"))
    bad_findings, bad_score = evaluate(_load("bad-config.json"))

    assert good_score.value > bad_score.value
    assert good_score.grade == "A"
    assert bad_score.grade == "F"

    good_failed = [f for f in good_findings if f.verdict == Verdict.FAILED]
    bad_failed = [f for f in bad_findings if f.verdict == Verdict.FAILED]
    assert good_failed == []
    assert len(bad_failed) > len(good_failed)


def test_bad_config_has_at_least_one_evidence_backed_finding():
    """Mirrors the roadmap's other exit criterion in miniature: a bad
    fixture must produce at least one finding with real evidence attached,
    not just a lower number."""
    findings, _score = evaluate(_load("bad-config.json"))
    failed_with_evidence = [f for f in findings if f.verdict == Verdict.FAILED and f.evidence]
    assert failed_with_evidence
    assert any(f.check_id == "VG-HDR-011" for f in failed_with_evidence)  # X-Powered-By leak


def test_bad_config_demonstrates_the_flagship_dat_check_end_to_end():
    """DAT-001 (a leaked Supabase service-role key) is the product's
    flagship differentiator per docs/vision.md — worth its own explicit
    assertion, not just a count."""
    findings, _score = evaluate(_load("bad-config.json"))
    dat_001 = next(f for f in findings if f.check_id == "VG-DAT-001")
    assert dat_001.verdict == Verdict.FAILED
    assert dat_001.severity.value == "critical"
