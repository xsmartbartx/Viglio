"""AccountRow — the tenant root (docs/prooflight-vision-and-architecture.md §6.1).

`clerk_user_id` is a deliberate addition beyond the domain-model table: the
mapping from Clerk's user id to a local `Account` row. It is nullable because
a free scan creates an `Account(status="anonymous")` from an email address
alone, before anyone has signed in — see `get_or_create_account`.

`SubscriptionRow` (Phase 7) lives here, not in a new `packages/billing`
table — `packages/billing` stays ORM-free by design
(docs/modules.md §11's "core only" dependency, enforced by its own
`test_import_boundary.py`), and `Subscription` is account-scoped exactly
like `AccountRow.plan_id`, the field every subscription write cascades
into (`upsert_subscription()`, `repository.py`).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from vigilo_persistence.base import Base


class AccountRow(Base):
    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="anonymous")
    plan_id: Mapped[str | None] = mapped_column(String(64), default=None)
    data_region: Mapped[str | None] = mapped_column(String(32), default=None)
    clerk_user_id: Mapped[str | None] = mapped_column(String(128), unique=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SubscriptionRow(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"), index=True)
    plan_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))
    provider: Mapped[str] = mapped_column(String(32))
    # Not unique on account_id alone — a provider issues a new subscription
    # id on plan change/renewal, so an account can accumulate more than one
    # row over time; upsert_subscription() keys its upsert on this field,
    # get_subscription_by_account() picks the most recent.
    provider_subscription_id: Mapped[str] = mapped_column(String(128), unique=True)
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
