"""The HTTP probe: the only place in this package that makes a request.

Every request is pinned to the egress guard's validated IP
(`vigilo_security.egress_guard.validate_and_pin`) and every redirect hop is
revalidated the same way before being followed — see docs/security.md §1.
Connecting to a literal IP while still getting correct TLS SNI and
certificate-hostname verification against the real hostname is done via
httpx's `extensions={"sni_hostname": ...}`, its documented mechanism for
exactly this case.
"""

from __future__ import annotations

import time
from http.cookies import SimpleCookie
from urllib.parse import urljoin

import httpx
from vigilo_core.evidence import CookieObservation, HttpObservation
from vigilo_security.egress_guard import (
    Resolver,
    ValidatedConnection,
    revalidate_redirect,
    validate_and_pin,
)

_MAX_REDIRECTS = 5
_BODY_EXCERPT_CAP = 8 * 1024
_MAX_DOWNLOAD_BYTES = 2 * 1024 * 1024
_REQUEST_TIMEOUT = 15.0
_USER_AGENT = "VigiloScanner/0.1 (+https://vigilo.io/scanner)"


class TooManyRedirects(RuntimeError):
    pass


def _build_request_url(conn: ValidatedConnection) -> str:
    scheme = conn.origin.split("://", 1)[0]
    host = f"[{conn.pinned_ip}]" if ":" in conn.pinned_ip else conn.pinned_ip
    return f"{scheme}://{host}:{conn.port}/"


def _parse_set_cookie_headers(raw_headers: list[str]) -> list[CookieObservation]:
    cookies: list[CookieObservation] = []
    for header_value in raw_headers:
        jar: SimpleCookie = SimpleCookie()
        try:
            jar.load(header_value)
        except Exception:  # noqa: BLE001 — a malformed Set-Cookie header is hostile input, not a bug
            continue
        for name, morsel in jar.items():
            cookies.append(
                CookieObservation(
                    name=name,
                    secure=bool(morsel["secure"]),
                    http_only=bool(morsel["httponly"]),
                    same_site=morsel["samesite"] or None,
                )
            )
    return cookies


async def run_http(
    url: str,
    resolver: Resolver | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> HttpObservation:
    """Probe `url`, following redirects manually (revalidating each hop
    against the egress guard) up to `_MAX_REDIRECTS` hops.

    `transport` is exposed purely for testing — pass an `httpx.MockTransport`
    to exercise this function with zero real sockets. Production callers
    never pass it; the default is a real network transport.
    """
    conn = validate_and_pin(url, resolver=resolver)
    redirect_chain: list[str] = []
    start = time.monotonic()

    async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT, transport=transport) as client:
        for hop in range(_MAX_REDIRECTS + 1):
            request_url = _build_request_url(conn)
            async with client.stream(
                "GET",
                request_url,
                headers={"Host": conn.host, "User-Agent": _USER_AGENT},
                extensions={"sni_hostname": conn.host},
            ) as response:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        # Malformed redirect (3xx with no Location) — hostile or
                        # broken input either way. Record it as-is rather than
                        # crashing the probe over it.
                        headers = {k.lower(): v for k, v in response.headers.items()}
                        cookies = _parse_set_cookie_headers(response.headers.get_list("set-cookie"))
                        await response.aclose()
                        return HttpObservation(
                            url=f"{conn.origin}/",
                            status_code=response.status_code,
                            headers=headers,
                            cookies=cookies,
                            redirect_chain=redirect_chain,
                            elapsed_ms=(time.monotonic() - start) * 1000,
                        )
                    await response.aclose()
                    redirect_chain.append(conn.origin)
                    if hop == _MAX_REDIRECTS:
                        raise TooManyRedirects(f"exceeded {_MAX_REDIRECTS} redirects from {url}")
                    next_url = urljoin(f"{conn.origin}/", location)
                    conn = revalidate_redirect(next_url, resolver=resolver)
                    continue

                chunks = bytearray()
                async for chunk in response.aiter_bytes():
                    chunks.extend(chunk)
                    if len(chunks) >= _MAX_DOWNLOAD_BYTES:
                        break
                body = bytes(chunks)

                elapsed_ms = (time.monotonic() - start) * 1000
                headers = {k.lower(): v for k, v in response.headers.items()}
                cookies = _parse_set_cookie_headers(response.headers.get_list("set-cookie"))

                return HttpObservation(
                    url=f"{conn.origin}/",
                    status_code=response.status_code,
                    headers=headers,
                    cookies=cookies,
                    redirect_chain=redirect_chain,
                    body_excerpt=body[:_BODY_EXCERPT_CAP].decode("utf-8", errors="replace"),
                    body_size=len(body),
                    content_type=response.headers.get("content-type"),
                    elapsed_ms=elapsed_ms,
                )

    raise RuntimeError(f"no response obtained for {url}")  # unreachable: loop always returns or raises
