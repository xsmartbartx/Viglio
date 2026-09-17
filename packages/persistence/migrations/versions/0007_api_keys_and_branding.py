"""API keys and branding profiles (docs/data-model.md, Phase 9).
`api_keys.key_hash` is unique and indexed — the lookup path at request
time; the plaintext key is never stored anywhere, only returned once at
creation (`create_api_key()`, `packages/identity`). `branding_profiles
.account_id` is unique — one profile per account, matching
`monitors.target_id`'s exact "one row per owner" precedent from Phase 8.

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-17 22:56:12.357776
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("prefix", sa.String(length=16), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], name=op.f("fk_api_keys_account_id_accounts")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_api_keys")),
    )
    op.create_index(op.f("ix_api_keys_account_id"), "api_keys", ["account_id"], unique=False)
    op.create_index(op.f("ix_api_keys_key_hash"), "api_keys", ["key_hash"], unique=True)

    op.create_table(
        "branding_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("logo_url", sa.String(length=500), nullable=True),
        sa.Column("primary_color", sa.String(length=16), nullable=True),
        sa.Column("footer_text", sa.String(length=500), nullable=True),
        sa.Column("custom_domain", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name=op.f("fk_branding_profiles_account_id_accounts"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_branding_profiles")),
    )
    op.create_index(
        op.f("ix_branding_profiles_account_id"), "branding_profiles", ["account_id"], unique=True
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_branding_profiles_account_id"), table_name="branding_profiles")
    op.drop_table("branding_profiles")
    op.drop_index(op.f("ix_api_keys_key_hash"), table_name="api_keys")
    op.drop_index(op.f("ix_api_keys_account_id"), table_name="api_keys")
    op.drop_table("api_keys")
