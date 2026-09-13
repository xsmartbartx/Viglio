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
