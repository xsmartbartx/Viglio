"""Pydantic shape for an Account, returned by the repository — never the ORM
row itself, so callers outside this package never depend on SQLAlchemy.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class Account(BaseModel):
    id: uuid.UUID
    email: str
    status: str
    plan_id: str | None
    data_region: str | None
    clerk_user_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class Subscription(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    plan_id: str
    status: str
    provider: str
    provider_subscription_id: str
    current_period_end: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ApiKey(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    name: str
    prefix: str
    scopes: list[str]
    last_used_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class BrandingProfile(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    logo_url: str | None
    primary_color: str | None
    footer_text: str | None
    custom_domain: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
