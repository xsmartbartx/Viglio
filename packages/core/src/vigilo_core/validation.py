"""Schema-first validation primitives.

`validate()` is the generic Pydantic-backed entry point every module uses
(docs/modules.md §1). `validate_target_url()` implements the scan-target URL
grammar from docs/prooflight-vision-and-architecture.md §16.1 — it belongs in
Core (a pure validation concern) even though `packages/security`'s egress
guard is its main consumer today.
"""

from __future__ import annotations

import ipaddress
from typing import Any, TypeVar
from urllib.parse import urlsplit

from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from vigilo_core.errors import ErrorCode, StructuredError

_ALLOWED_SCHEMES = frozenset({"http", "https"})
_ALLOWED_PORTS = frozenset({80, 443, 8080, 8443})
_DEFAULT_PORTS = {"http": 80, "https": 443}
_MAX_URL_LENGTH = 255

ModelT = TypeVar("ModelT", bound=BaseModel)


class ValidationError(StructuredError):
    """Raised when a payload or target URL fails schema/grammar validation."""


def validate(model: type[ModelT], payload: dict[str, Any]) -> ModelT:
    """Validate `payload` against a Pydantic model, converting Pydantic's own
    ValidationError into a StructuredError so every module raises the same
    error shape."""
    if not (isinstance(model, type) and issubclass(model, BaseModel)):
        raise TypeError("validate() requires a pydantic BaseModel subclass")

    try:
        return model.model_validate(payload)
    except PydanticValidationError as exc:
        raise ValidationError(
            ErrorCode.VALIDATION_ERROR,
            f"{model.__name__} failed validation",
            errors=[
                {"loc": e["loc"], "type": e["type"], "msg": e["msg"]} for e in exc.errors()
            ],
        ) from exc


def validate_target_url(raw: str) -> str:
    """Validate a scan target URL and return its canonical origin
    (`scheme://host[:port]`, lowercased, IDN-normalized to punycode, default
    ports stripped, path/query discarded). Raises ValidationError with code
    TARGET_INVALID on any grammar violation.

    Rules (docs/prooflight-vision-and-architecture.md §16.1):
    http/https only; no userinfo; no fragment; length <= 255; port from a
    fixed allowlist; hostname must not be a raw IP literal.
    """
    if not isinstance(raw, str) or not raw:
        raise ValidationError(ErrorCode.TARGET_INVALID, "target URL must be a non-empty string")

    if len(raw) > _MAX_URL_LENGTH:
        raise ValidationError(
            ErrorCode.TARGET_INVALID,
            f"target URL exceeds {_MAX_URL_LENGTH} characters",
            length=len(raw),
        )

    parts = urlsplit(raw)

    scheme = parts.scheme.lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise ValidationError(
            ErrorCode.TARGET_INVALID, "scheme must be http or https", scheme=parts.scheme
        )

    if parts.username or parts.password:
        raise ValidationError(
            ErrorCode.TARGET_INVALID, "userinfo is not permitted in a target URL"
        )

    if parts.fragment:
        raise ValidationError(
            ErrorCode.TARGET_INVALID, "fragment is not permitted in a target URL"
        )

    hostname = parts.hostname
    if not hostname:
        raise ValidationError(ErrorCode.TARGET_INVALID, "target URL has no host")

    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        raise ValidationError(
            ErrorCode.TARGET_INVALID, "raw IP literal hosts are not permitted", host=hostname
        )

    try:
        hostname_ascii = hostname.encode("idna").decode("ascii") if hostname else hostname
    except UnicodeError as exc:
        raise ValidationError(
            ErrorCode.TARGET_INVALID, "host is not a valid hostname", host=hostname
        ) from exc

    try:
        port = parts.port
    except ValueError as exc:
        raise ValidationError(ErrorCode.TARGET_INVALID, "port is not a valid integer") from exc

    if port is not None and port not in _ALLOWED_PORTS:
        raise ValidationError(
            ErrorCode.TARGET_INVALID,
            "port is not on the allowed list",
            port=port,
            allowed=sorted(_ALLOWED_PORTS),
        )

    default_port = _DEFAULT_PORTS[scheme]
    canonical_port = "" if port in (None, default_port) else f":{port}"
    return f"{scheme}://{hostname_ascii.lower()}{canonical_port}"
