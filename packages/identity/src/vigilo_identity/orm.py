"""AccountRow — the tenant root (docs/prooflight-vision-and-architecture.md §6.1).

`clerk_user_id` is a deliberate addition beyond the domain-model table: the
mapping from Clerk's user id to a local `Account` row. It is nullable because
a free scan creates an `Account(status="anonymous")` from an email address
alone, before anyone has signed in — see `get_or_create_account`.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
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
