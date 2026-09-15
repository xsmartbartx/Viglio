"""Remediation cache (docs/data-model.md, Phase 5): caches Claude-generated
remediation prompts by `(fingerprint, registry_version)` so a repeat scan of
the same target skips the LLM call on a cache hit
(docs/adr/ADR-0004-llm-boundary.md). Only `source == "llm"` results are ever
cached — template fallback text is free to recompute.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-15 11:48:27.661667
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "remediation_cache",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("fingerprint", sa.String(length=128), nullable=False),
        sa.Column("check_id", sa.String(length=32), nullable=False),
        sa.Column("registry_version", sa.String(length=16), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("impact", sa.Text(), nullable=False),
        sa.Column("remediation_steps", sa.JSON(), nullable=False),
        sa.Column("agent_prompt", sa.Text(), nullable=False),
        sa.Column("estimated_effort", sa.String(length=16), nullable=True),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_remediation_cache")),
        sa.UniqueConstraint(
            "fingerprint", "registry_version", name=op.f("uq_remediation_cache_fingerprint")
        ),
    )
    op.create_index(
        op.f("ix_remediation_cache_check_id"), "remediation_cache", ["check_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_remediation_cache_check_id"), table_name="remediation_cache")
    op.drop_table("remediation_cache")
