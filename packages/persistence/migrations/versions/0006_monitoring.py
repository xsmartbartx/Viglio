"""Monitoring (docs/data-model.md, Phase 8): scheduled re-scans and the
alerts scan diffing produces. `monitors.target_id` is unique — one monitor
per target, matching `create_monitor()`'s idempotent-by-target upsert.
`alerts.target_id` is denormalized alongside `monitor_id` so alert history
stays queryable even if the owning monitor is later deleted, the same
"redundant FK for a different query shape" precedent `scans.target_id`
already sets alongside `scan_jobs.target_id`.

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-16 17:59:22.668852
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "monitors",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("cadence_hours", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("quiet_start_utc", sa.Integer(), nullable=True),
        sa.Column("quiet_end_utc", sa.Integer(), nullable=True),
        sa.Column("pending_score_drop", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], name=op.f("fk_monitors_account_id_accounts")
        ),
        sa.ForeignKeyConstraint(
            ["target_id"], ["targets.id"], name=op.f("fk_monitors_target_id_targets")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_monitors")),
    )
    op.create_index(
        op.f("ix_monitors_account_id"), "monitors", ["account_id"], unique=False
    )
    op.create_index(
        op.f("ix_monitors_next_run_at"), "monitors", ["next_run_at"], unique=False
    )
    op.create_index(
        op.f("ix_monitors_target_id"), "monitors", ["target_id"], unique=True
    )

    op.create_table(
        "alerts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("monitor_id", sa.Uuid(), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("scan_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=True),
        sa.Column("fingerprint", sa.String(length=128), nullable=True),
        sa.Column("dedupe_key", sa.String(length=200), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["monitor_id"], ["monitors.id"], name=op.f("fk_alerts_monitor_id_monitors")
        ),
        sa.ForeignKeyConstraint(["scan_id"], ["scans.id"], name=op.f("fk_alerts_scan_id_scans")),
        sa.ForeignKeyConstraint(
            ["target_id"], ["targets.id"], name=op.f("fk_alerts_target_id_targets")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_alerts")),
    )
    op.create_index(op.f("ix_alerts_monitor_id"), "alerts", ["monitor_id"], unique=False)
    op.create_index(op.f("ix_alerts_scan_id"), "alerts", ["scan_id"], unique=False)
    op.create_index(op.f("ix_alerts_target_id"), "alerts", ["target_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_alerts_target_id"), table_name="alerts")
    op.drop_index(op.f("ix_alerts_scan_id"), table_name="alerts")
    op.drop_index(op.f("ix_alerts_monitor_id"), table_name="alerts")
    op.drop_table("alerts")
    op.drop_index(op.f("ix_monitors_target_id"), table_name="monitors")
    op.drop_index(op.f("ix_monitors_next_run_at"), table_name="monitors")
    op.drop_index(op.f("ix_monitors_account_id"), table_name="monitors")
    op.drop_table("monitors")
