from datetime import UTC, datetime

from vigilo_checks import REGISTRY
from vigilo_checks.registry import CheckResult, get_header, requires
from vigilo_core.evidence import EvidenceBundle, HttpObservation
from vigilo_core.models import Verdict


def test_registry_has_sixty_four_checks_with_unique_ids():
    assert len(REGISTRY) == 64
    ids = [c.manifest.check_id for c in REGISTRY]
    assert len(ids) == len(set(ids))


def test_get_header_is_case_insensitive():
    headers = {"strict-transport-security": "max-age=1"}
    assert get_header(headers, "Strict-Transport-Security") == "max-age=1"
    assert get_header(headers, "STRICT-TRANSPORT-SECURITY") == "max-age=1"
    assert get_header(headers, "x-missing") is None


def test_requires_decorator_short_circuits_to_inconclusive():
    @requires("http")
    def _impl(bundle: EvidenceBundle) -> CheckResult:
        raise AssertionError("should not be called when http is None")

    bundle = EvidenceBundle(bundle_id="t", target_origin="https://x.test", captured_at=datetime.now(UTC), http=None)
    result = _impl(bundle)
    assert result.verdict == Verdict.INCONCLUSIVE


def test_requires_decorator_calls_through_when_evidence_present():
    calls = []

    @requires("http")
    def _impl(bundle: EvidenceBundle) -> CheckResult:
        calls.append(bundle)
        return CheckResult(Verdict.PASSED, "ok")

    bundle = EvidenceBundle(
        bundle_id="t",
        target_origin="https://x.test",
        captured_at=datetime.now(UTC),
        http=HttpObservation(url="https://x.test/", status_code=200),
    )
    result = _impl(bundle)
    assert result.verdict == Verdict.PASSED
    assert calls == [bundle]
