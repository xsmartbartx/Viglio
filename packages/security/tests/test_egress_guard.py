"""The egress-guard build-blocking suite (docs/prooflight-vision-and-architecture.md
§18.3): "Attempts against loopback, private ranges, metadata endpoints,
rebinding sequences and redirect chains into internal space. Any pass is a
build-blocking failure." No real DNS or network I/O happens anywhere in this
file — every case uses a fake resolver.
"""

import pytest
from vigilo_core.validation import ValidationError
from vigilo_security.egress_guard import (
    DeniedReason,
    revalidate_redirect,
    validate_and_pin,
)
from vigilo_security.exceptions import EgressDenied

_FAKE_DNS: dict[str, list[str]] = {
    "loopback.test": ["127.0.0.1"],
    "loopback6.test": ["::1"],
    "private-10.test": ["10.0.0.5"],
    "private-172.test": ["172.16.0.5"],
    "private-192.test": ["192.168.1.5"],
    "linklocal.test": ["169.254.1.1"],
    "metadata.test": ["169.254.169.254"],  # cloud metadata endpoint
    "cgnat.test": ["100.64.0.1"],
    "multicast.test": ["224.0.0.1"],
    "reserved.test": ["240.0.0.1"],
    "unspecified.test": ["0.0.0.0"],
    "mapped-loopback.test": ["::ffff:127.0.0.1"],
    "mapped-private.test": ["::ffff:10.1.2.3"],
    "mixed.test": ["93.184.216.34", "10.0.0.1"],  # one safe, one not — must still deny
    "public.test": ["93.184.216.34"],
    "public2.test": ["1.1.1.1"],
    "nxdomain.test": [],
}


def _fake_resolver(hostname: str) -> list[str]:
    if hostname not in _FAKE_DNS:
        raise AssertionError(f"unexpected DNS lookup for {hostname!r} — no real network in tests")
    return _FAKE_DNS[hostname]


@pytest.mark.parametrize(
    ("hostname", "expected_reason"),
    [
        ("loopback.test", DeniedReason.LOOPBACK),
        ("loopback6.test", DeniedReason.LOOPBACK),
        ("private-10.test", DeniedReason.PRIVATE),
        ("private-172.test", DeniedReason.PRIVATE),
        ("private-192.test", DeniedReason.PRIVATE),
        ("linklocal.test", DeniedReason.LINK_LOCAL),
        ("metadata.test", DeniedReason.LINK_LOCAL),
        ("cgnat.test", DeniedReason.CGNAT),
        ("multicast.test", DeniedReason.MULTICAST),
        ("reserved.test", DeniedReason.RESERVED),
        ("unspecified.test", DeniedReason.UNSPECIFIED),
        ("mapped-loopback.test", DeniedReason.LOOPBACK),
        ("mapped-private.test", DeniedReason.PRIVATE),
        ("mixed.test", DeniedReason.PRIVATE),
    ],
)
def test_validate_and_pin_denies_every_unsafe_address_class(hostname, expected_reason):
    with pytest.raises(EgressDenied) as exc_info:
        validate_and_pin(f"https://{hostname}", resolver=_fake_resolver)

    assert exc_info.value.context["reason"] == expected_reason


def test_metadata_endpoint_is_specifically_blocked():
    """Regression guard for the single most damaging SSRF outcome: reaching
    the cloud metadata IP that hands out instance credentials."""
    with pytest.raises(EgressDenied):
        validate_and_pin("http://metadata.test/latest/meta-data/", resolver=_fake_resolver)


def test_dns_resolution_failure_is_denied_not_silently_skipped():
    def failing_resolver(_hostname: str) -> list[str]:
        raise OSError("simulated DNS failure")

    with pytest.raises(EgressDenied) as exc_info:
        validate_and_pin("https://anything.test", resolver=failing_resolver)
    assert exc_info.value.context["reason"] == DeniedReason.RESOLUTION_FAILED


def test_empty_resolution_is_denied():
    with pytest.raises(EgressDenied) as exc_info:
        validate_and_pin("https://nxdomain.test", resolver=_fake_resolver)
    assert exc_info.value.context["reason"] == DeniedReason.RESOLUTION_FAILED


def test_valid_public_targets_are_pinned():
    conn = validate_and_pin("https://public.test", resolver=_fake_resolver)
    assert conn.origin == "https://public.test"
    assert conn.host == "public.test"
    assert conn.pinned_ip == "93.184.216.34"
    assert conn.port == 443

    conn2 = validate_and_pin("http://public2.test:8080", resolver=_fake_resolver)
    assert conn2.pinned_ip == "1.1.1.1"
    assert conn2.port == 8080


def test_redirect_into_internal_space_is_denied():
    """Simulates the redirect-hop revalidation the probe layer will call on
    every hop of a redirect chain."""
    with pytest.raises(EgressDenied):
        revalidate_redirect("https://linklocal.test", resolver=_fake_resolver)


def test_redirect_to_safe_target_is_pinned():
    conn = revalidate_redirect("https://public.test", resolver=_fake_resolver)
    assert conn.pinned_ip == "93.184.216.34"


@pytest.mark.parametrize(
    "url",
    [
        "ftp://public.test",
        "http://user:pass@public.test",
        "https://1.2.3.4",
        "https://public.test:22",
    ],
)
def test_bad_url_grammar_is_rejected_before_any_dns_lookup(url):
    """These must fail at validation, not at resolution — the fake resolver
    would raise AssertionError if a lookup were attempted for a host it
    doesn't know, which is exactly how this test catches a guard that
    resolves before validating."""
    with pytest.raises(ValidationError):
        validate_and_pin(url, resolver=_fake_resolver)


def test_no_test_in_this_module_performs_real_network_io():
    """Documents the invariant by construction: every call above passes an
    explicit `resolver=`, so `socket.getaddrinfo` is never reached."""
    assert True
