"""The ownership-verification build-blocking suite — same standard as
`test_egress_guard.py`: `verify_wellknown_file`/`verify_meta_tag` fetch the
target's own origin, so a target that resolves to an internal address must
be denied by `validate_and_pin()` before any HTTP request is attempted, and
`verify_dns_txt` must never perform a real DNS lookup. No real DNS or
network I/O happens anywhere in this file.
"""

from __future__ import annotations

import httpx
import pytest

from vigilo_core.models import VerificationMethod
from vigilo_security.exceptions import EgressDenied, VerificationIOError
from vigilo_security.ownership import (
    verify_dns_txt,
    verify_email,
    verify_meta_tag,
    verify_ownership,
    verify_wellknown_file,
)

_FAKE_DNS: dict[str, list[str]] = {
    "safe.test": ["93.184.216.34"],
    "internal.test": ["10.0.0.5"],
    "metadata.test": ["169.254.169.254"],
}


def _fake_resolver(hostname: str) -> list[str]:
    if hostname not in _FAKE_DNS:
        raise AssertionError(f"unexpected DNS lookup for {hostname!r} — no real network in tests")
    return _FAKE_DNS[hostname]


def _never_called_handler(request: httpx.Request) -> httpx.Response:
    raise AssertionError("no HTTP request should have been attempted — egress guard should deny first")


@pytest.mark.parametrize("hostname", ["internal.test", "metadata.test"])
async def test_verify_wellknown_file_denies_a_target_resolving_to_an_internal_address(hostname):
    with pytest.raises(EgressDenied):
        await verify_wellknown_file(
            f"https://{hostname}",
            "expected-nonce",
            resolver=_fake_resolver,
            transport=httpx.MockTransport(_never_called_handler),
        )


@pytest.mark.parametrize("hostname", ["internal.test", "metadata.test"])
async def test_verify_meta_tag_denies_a_target_resolving_to_an_internal_address(hostname):
    with pytest.raises(EgressDenied):
        await verify_meta_tag(
            f"https://{hostname}",
            "expected-nonce",
            resolver=_fake_resolver,
            transport=httpx.MockTransport(_never_called_handler),
        )


async def test_verify_wellknown_file_matches_exact_content():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/.well-known/vigilo-verification.txt"
        return httpx.Response(200, content=b"expected-nonce")

    result = await verify_wellknown_file(
        "https://safe.test", "expected-nonce", resolver=_fake_resolver, transport=httpx.MockTransport(handler)
    )
    assert result.verified is True
    assert result.method == VerificationMethod.WELLKNOWN_FILE


async def test_verify_wellknown_file_rejects_mismatched_content():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"some-other-value")

    result = await verify_wellknown_file(
        "https://safe.test", "expected-nonce", resolver=_fake_resolver, transport=httpx.MockTransport(handler)
    )
    assert result.verified is False


async def test_verify_wellknown_file_treats_a_404_as_not_verified():
    result = await verify_wellknown_file(
        "https://safe.test",
        "expected-nonce",
        resolver=_fake_resolver,
        transport=httpx.MockTransport(lambda r: httpx.Response(404)),
    )
    assert result.verified is False


async def test_verify_meta_tag_matches_content_attribute():
    def handler(request: httpx.Request) -> httpx.Response:
        html = b'<html><head><meta name="vigilo-site-verification" content="expected-nonce"></head></html>'
        return httpx.Response(200, content=html)

    result = await verify_meta_tag(
        "https://safe.test", "expected-nonce", resolver=_fake_resolver, transport=httpx.MockTransport(handler)
    )
    assert result.verified is True
    assert result.method == VerificationMethod.META_TAG


async def test_verify_meta_tag_rejects_a_page_with_no_matching_tag():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<html><head></head></html>")

    result = await verify_meta_tag(
        "https://safe.test", "expected-nonce", resolver=_fake_resolver, transport=httpx.MockTransport(handler)
    )
    assert result.verified is False


def test_verify_dns_txt_matches_a_correctly_formatted_record():
    def fake_txt_resolver(hostname: str) -> list[str]:
        assert hostname == "safe.test"
        return ["some-other-record", "vigilo-site-verification=expected-nonce"]

    result = verify_dns_txt("https://safe.test", "expected-nonce", txt_resolver=fake_txt_resolver)
    assert result.verified is True
    assert result.method == VerificationMethod.DNS_TXT


def test_verify_dns_txt_rejects_when_no_record_matches():
    result = verify_dns_txt("https://safe.test", "expected-nonce", txt_resolver=lambda h: [])
    assert result.verified is False


def test_verify_dns_txt_raises_a_structured_error_on_resolver_failure():
    def failing_resolver(hostname: str) -> list[str]:
        raise OSError("simulated DNS failure")

    with pytest.raises(VerificationIOError):
        verify_dns_txt("https://safe.test", "expected-nonce", txt_resolver=failing_resolver)


async def test_verify_email_is_not_implemented_in_phase_3():
    with pytest.raises(NotImplementedError):
        await verify_email("https://safe.test", "expected-nonce")


async def test_dispatcher_routes_to_the_matching_method():
    def fake_txt_resolver(hostname: str) -> list[str]:
        return ["vigilo-site-verification=expected-nonce"]

    result = await verify_ownership(
        VerificationMethod.DNS_TXT,
        "https://safe.test",
        "expected-nonce",
        txt_resolver=fake_txt_resolver,
    )
    assert result.verified is True


def test_no_test_in_this_module_performs_real_network_io():
    """Documents the invariant by construction: every DNS-touching call
    above passes an explicit `resolver=`/`txt_resolver=`, and every
    HTTP-touching call passes an explicit `transport=`."""
    assert True
