"""Vigilo core: foundational primitives shared by every other module.

No business logic. No network. No database access. No knowledge of any
specific check, probe or provider. See docs/modules.md §1.
"""

from vigilo_core.config import Config, config
from vigilo_core.errors import ErrorCode, StructuredError, error
from vigilo_core.evidence import (
    CookieObservation,
    EvidenceBundle,
    FingerprintObservation,
    HttpObservation,
    TlsObservation,
)
from vigilo_core.logging import LogEvent, log
from vigilo_core.redact import Fingerprint, redact
from vigilo_core.validation import ValidationError, validate, validate_target_url

__all__ = [
    "Config",
    "config",
    "ErrorCode",
    "StructuredError",
    "error",
    "CookieObservation",
    "EvidenceBundle",
    "FingerprintObservation",
    "HttpObservation",
    "TlsObservation",
    "LogEvent",
    "log",
    "Fingerprint",
    "redact",
    "ValidationError",
    "validate",
    "validate_target_url",
]
