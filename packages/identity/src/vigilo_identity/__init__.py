"""Vigilo identity: accounts, tenancy (docs/modules.md §2a).

Owns the `Account` row — the tenant root every `Target` and `AuditEvent`
ultimately belongs to. Depends on core + persistence only.
"""

from __future__ import annotations

from vigilo_identity.models import Account, ApiKey, BrandingProfile, Subscription
from vigilo_identity.repository import (
    count_api_keys_for_account,
    create_api_key,
    get_account_by_clerk_id,
    get_account_by_email,
    get_account_by_id,
    get_api_key_by_hash,
    get_branding_profile,
    get_or_create_account,
    get_subscription_by_account,
    hash_api_key,
    list_api_keys_for_account,
    mark_api_key_used,
    revoke_api_key,
    upsert_branding_profile,
    upsert_subscription,
)

__all__ = [
    "Account",
    "Subscription",
    "ApiKey",
    "BrandingProfile",
    "get_account_by_id",
    "get_account_by_clerk_id",
    "get_account_by_email",
    "get_or_create_account",
    "get_subscription_by_account",
    "upsert_subscription",
    "hash_api_key",
    "create_api_key",
    "get_api_key_by_hash",
    "list_api_keys_for_account",
    "revoke_api_key",
    "mark_api_key_used",
    "count_api_keys_for_account",
    "get_branding_profile",
    "upsert_branding_profile",
]
