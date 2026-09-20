"""Pydantic shapes returned by the repository. `Target` is not redefined here
— it reuses `vigilo_core.models.Target`, extended in Phase 3 with `id`,
`project_id`, `verification_method`, `opt_out_flag` for exactly this purpose.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class Project(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class OwnershipProof(BaseModel):
    id: uuid.UUID
    target_id: uuid.UUID
    method: str
    nonce: str
    issued_at: datetime
    verified_at: datetime | None
    expires_at: datetime | None

    model_config = {"from_attributes": True}


class Suppression(BaseModel):
    id: uuid.UUID
    target_id: uuid.UUID
    fingerprint: str
    check_id: str
    reason: str
    expires_at: datetime | None
    created_by_account_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}
