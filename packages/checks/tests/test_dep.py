from datetime import UTC, datetime

from vigilo_checks import dep
from vigilo_core.evidence import EvidenceBundle, HttpObservation
from vigilo_core.models import Verdict


def _bundle(http: HttpObservation | None) -> EvidenceBundle:
    return EvidenceBundle(
        bundle_id="test", target_origin="https://example.com", captured_at=datetime.now(UTC), http=http
    )


def _http(body: str = "") -> HttpObservation:
    return HttpObservation(url="https://example.com/", status_code=200, body_excerpt=body)


def _v(check, http):
    return check.evaluate(_bundle(http)).verdict


def test_all_dep_checks_are_inconclusive_without_http_evidence():
    for check in dep.CHECKS:
        assert _v(check, None) == Verdict.INCONCLUSIVE, check.manifest.check_id


def test_sri_present():
    with_sri = '<script src="https://cdn.example.com/lib.js" integrity="sha384-abc" crossorigin="anonymous"></script>'
    without_sri = '<script src="https://cdn.example.com/lib.js"></script>'
    same_origin = '<script src="/app.js"></script>'

    assert _v(dep.CHECK_SRI_PRESENT, _http(with_sri)) == Verdict.PASSED
    assert _v(dep.CHECK_SRI_PRESENT, _http(without_sri)) == Verdict.FAILED
    assert _v(dep.CHECK_SRI_PRESENT, _http(same_origin)) == Verdict.PASSED


def test_no_known_old_library():
    old = '<script src="https://cdn.example.com/jquery-1.12.4.min.js"></script>'
    modern = '<script src="https://cdn.example.com/jquery-3.7.1.min.js"></script>'

    assert _v(dep.CHECK_NO_KNOWN_OLD_LIBRARY, _http(old)) == Verdict.FAILED
    assert _v(dep.CHECK_NO_KNOWN_OLD_LIBRARY, _http(modern)) == Verdict.PASSED


def test_bounded_third_party_origins():
    few = "".join(f'<script src="https://origin{i}.example.com/a.js"></script>' for i in range(3))
    many = "".join(f'<script src="https://origin{i}.example.com/a.js"></script>' for i in range(10))

    assert _v(dep.CHECK_BOUNDED_THIRD_PARTY_ORIGINS, _http(few)) == Verdict.PASSED
    assert _v(dep.CHECK_BOUNDED_THIRD_PARTY_ORIGINS, _http(many)) == Verdict.FAILED


def test_no_unpinned_cdn_version():
    pinned = '<script src="https://cdn.jsdelivr.net/npm/react@18.3.1/index.js"></script>'
    unpinned = '<script src="https://cdn.jsdelivr.net/npm/react/index.js"></script>'
    explicit_latest = '<script src="https://unpkg.com/react@latest/index.js"></script>'

    assert _v(dep.CHECK_NO_UNPINNED_CDN_VERSION, _http(pinned)) == Verdict.PASSED
    assert _v(dep.CHECK_NO_UNPINNED_CDN_VERSION, _http(unpinned)) == Verdict.FAILED
    assert _v(dep.CHECK_NO_UNPINNED_CDN_VERSION, _http(explicit_latest)) == Verdict.FAILED
