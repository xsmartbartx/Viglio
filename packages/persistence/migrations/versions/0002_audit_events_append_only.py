"""audit events append only

Revision ID: afb3d369d97e
Revises: 0001
Create Date: 2026-09-13 19:19:37.085600
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = 'afb3d369d97e'
down_revision: str | None = '0001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
