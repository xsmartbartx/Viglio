"""Vigilo identity: accounts, tenancy (docs/modules.md §2a).

Owns the `Account` row — the tenant root every `Target` and `AuditEvent`
ultimately belongs to. Depends on core + persistence only.
"""

from __future__ import annotations

from vigilo_identity.models import Account
from vigilo_identity.repository import (
    get_account_by_clerk_id,
    get_account_by_email,
    get_account_by_id,
    get_or_create_account,
)

__all__ = [
    "Account",
    "get_account_by_id",
    "get_account_by_clerk_id",
    "get_account_by_email",
    "get_or_create_account",
]
