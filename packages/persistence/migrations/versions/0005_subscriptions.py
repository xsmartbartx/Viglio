"""Subscriptions (docs/data-model.md, Phase 7): merchant-of-record
subscription state, owned by `packages/identity` (account-scoped, cascades
`accounts.plan_id` — `packages/billing` itself stays ORM-free by design,
docs/modules.md §11). Not unique on `account_id` alone — a provider issues
a new `provider_subscription_id` on plan change/renewal, so rows accumulate
over time rather than being updated in place.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-16 16:43:41.715520
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_subscription_id", sa.String(length=128), nullable=False),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], name=op.f("fk_subscriptions_account_id_accounts")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_subscriptions")),
        sa.UniqueConstraint(
            "provider_subscription_id", name=op.f("uq_subscriptions_provider_subscription_id")
        ),
    )
    op.create_index(
        op.f("ix_subscriptions_account_id"), "subscriptions", ["account_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_subscriptions_account_id"), table_name="subscriptions")
    op.drop_table("subscriptions")
