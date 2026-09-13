"""Vigilo integrations: all communication with named third-party providers
(docs/modules.md §7). One adapter per provider; business logic never talks
to a provider SDK directly.
"""

from __future__ import annotations

from vigilo_integrations.adapters import AdapterRequest, AdapterResponse, call
from vigilo_integrations.errors import MailDeliveryFailed, ObjectStoreError
from vigilo_integrations.mail import send_transactional_email
from vigilo_integrations.storage import get_evidence_bundle, put_evidence_bundle

__all__ = [
    "AdapterRequest",
    "AdapterResponse",
    "call",
    "MailDeliveryFailed",
    "ObjectStoreError",
    "send_transactional_email",
    "put_evidence_bundle",
    "get_evidence_bundle",
]
