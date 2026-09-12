from vigilo_core.evidence import HttpObservation
from vigilo_probes.seal import seal


def test_seal_produces_a_bundle_matching_compute_id():
    http = HttpObservation(url="https://example.com/", status_code=200)
    bundle = seal("https://example.com", http, None, None)

    from vigilo_core.evidence import EvidenceBundle

    assert bundle.bundle_id == EvidenceBundle.compute_id("https://example.com", http, None, None)
    assert bundle.target_origin == "https://example.com"
    assert bundle.captured_at is not None


def test_seal_of_identical_evidence_at_different_times_has_same_id():
    http = HttpObservation(url="https://example.com/", status_code=200)
    bundle_1 = seal("https://example.com", http, None, None)
    bundle_2 = seal("https://example.com", http, None, None)
    assert bundle_1.bundle_id == bundle_2.bundle_id
