"""Suppressions (docs/data-model.md, post-Phase-9). A target owner's
"known, accept it" decision on one finding, keyed by `(target_id,
fingerprint)` — the same finding-identity concept `detect_regression()`
already tracks across scans, never a FK to `findings.id` since every scan
creates a fresh set of finding rows.

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-20 14:02:05.788836
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "suppressions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("fingerprint", sa.String(length=128), nullable=False),
        sa.Column("check_id", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_account_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["created_by_account_id"],
            ["accounts.id"],
            name=op.f("fk_suppressions_created_by_account_id_accounts"),
        ),
        sa.ForeignKeyConstraint(
            ["target_id"], ["targets.id"], name=op.f("fk_suppressions_target_id_targets")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_suppressions")),
        sa.UniqueConstraint("target_id", "fingerprint", name=op.f("uq_suppressions_target_id")),
    )
    op.create_index(op.f("ix_suppressions_target_id"), "suppressions", ["target_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_suppressions_target_id"), table_name="suppressions")
    op.drop_table("suppressions")
