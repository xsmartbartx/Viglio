"""Egress guard: SSRF and DNS-rebinding defense for outbound requests to scan
targets. This is the "component that touches the internet does nothing else"
boundary described in docs/architecture.md — everything here decides whether
a target is safe to connect to; it never itself makes the scanning request.

`packages/probes` (Phase 1) is the actual HTTP client. It must call
`validate_and_pin()` and connect to the returned `pinned_ip` literally,
never re-resolving the hostname between check and connect — that is what
defeats DNS rebinding.
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from ipaddress import IPv4Address, IPv6Address, ip_network

from vigilo_core.validation import validate_target_url
from vigilo_security.exceptions import EgressDenied

Resolver = Callable[[str], list[str]]
"""A resolver takes a hostname and returns the list of IP address strings it
resolves to. The default uses `socket.getaddrinfo`; tests inject a fake
resolver so the egress-guard suite never touches the network, per the
"no live third-party targets in CI" rule in docs/architecture.md §11."""

_CGNAT_RANGE = ip_network("100.64.0.0/10")


class DeniedReason(StrEnum):
    LOOPBACK = "loopback"
    UNSPECIFIED = "unspecified"
    LINK_LOCAL = "link_local"  # includes 169.254.169.254 cloud metadata
    CGNAT = "cgnat"
    MULTICAST = "multicast"
    RESERVED = "reserved"
    PRIVATE = "private"
    RESOLUTION_FAILED = "resolution_failed"


@dataclass(frozen=True)
class ValidatedConnection:
    """Result of a successful egress-guard check: the canonical origin that
    was requested, and the literal IP address the caller must connect to."""

    origin: str
    host: str
    pinned_ip: str
    port: int


def _default_resolver(hostname: str) -> list[str]:
    infos = socket.getaddrinfo(hostname, None)
    return [info[4][0] for info in infos]


def _classify(addr: IPv4Address | IPv6Address) -> DeniedReason | None:
    if isinstance(addr, IPv6Address) and addr.ipv4_mapped is not None:
        return _classify(addr.ipv4_mapped)

    if addr.is_loopback:
        return DeniedReason.LOOPBACK
    if addr.is_unspecified:
        return DeniedReason.UNSPECIFIED
    if addr.is_link_local:
        return DeniedReason.LINK_LOCAL
    if isinstance(addr, IPv4Address) and addr in _CGNAT_RANGE:
        return DeniedReason.CGNAT
    if addr.is_multicast:
        return DeniedReason.MULTICAST
    if addr.is_reserved:
        return DeniedReason.RESERVED
    if addr.is_private:
        return DeniedReason.PRIVATE
    return None


def validate_and_pin(url: str, resolver: Resolver | None = None) -> ValidatedConnection:
    """Validate a scan target URL and pin it to a single safe IP address.

    Raises `vigilo_core.validation.ValidationError` (code `TARGET_INVALID`)
    if the URL fails grammar validation, or `EgressDenied` (code
    `EGRESS_DENIED`) if any address it resolves to falls in a denied range.
    """
    resolve = resolver or _default_resolver

    origin = validate_target_url(url)
    scheme, _, rest = origin.partition("://")
    host, _, port_str = rest.partition(":")
    port = int(port_str) if port_str else (443 if scheme == "https" else 80)

    try:
        raw_addresses = resolve(host)
    except OSError as exc:
        raise EgressDenied(
            "DNS resolution failed", host=host, reason=DeniedReason.RESOLUTION_FAILED
        ) from exc

    if not raw_addresses:
        raise EgressDenied(
            "DNS resolution returned no addresses",
            host=host,
            reason=DeniedReason.RESOLUTION_FAILED,
        )

    for raw in raw_addresses:
        addr = ipaddress.ip_address(raw)
        reason = _classify(addr)
        if reason is not None:
            raise EgressDenied(
                "target resolves to a disallowed address range",
                host=host,
                resolved=raw,
                reason=reason,
            )

    return ValidatedConnection(origin=origin, host=host, pinned_ip=raw_addresses[0], port=port)


def revalidate_redirect(location: str, resolver: Resolver | None = None) -> ValidatedConnection:
    """Re-run the full egress check for a redirect hop.

    Phase 1 TODO: restrict redirects to the same registrable domain (needs a
    public-suffix-list dependency, out of scope for Phase 0). Every SSRF
    check below is still re-applied, so a redirect into internal address
    space is blocked even without that restriction.
    """
    return validate_and_pin(location, resolver=resolver)
