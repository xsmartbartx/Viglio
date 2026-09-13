"""audit events append only

Enforces ADR-0003's append-only guarantee at the database level: "the audit
trail's append-only guarantee needs to be a database property (no
UPDATE/DELETE grants on that table)." A trigger, not a `REVOKE` grant —
the docker-compose Postgres has one owning role (`vigilo`) that created the
table, and Postgres table owners bypass `REVOKE`; making `REVOKE` actually
work would need a second, non-owner DB role and a second `DATABASE_URL`
across dev/CI/prod, which is real infra churn this phase doesn't need. A
trigger enforces the guarantee regardless of which role runs the statement.

Never actually run `alembic downgrade` past this revision against a
production `audit_events` table with real rows in it — the guarantee this
migration exists to add would simply disappear.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-13 19:19:37.085600
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CREATE_FUNCTION = """
CREATE FUNCTION audit_events_no_update_delete() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_events is append-only: % is not permitted', TG_OP;
END;
$$ LANGUAGE plpgsql;
"""

_CREATE_TRIGGER = """
CREATE TRIGGER audit_events_append_only
BEFORE UPDATE OR DELETE ON audit_events
FOR EACH ROW EXECUTE FUNCTION audit_events_no_update_delete();
"""

# TRUNCATE bypasses row-level BEFORE DELETE triggers entirely (Postgres only
# fires row-level triggers for row-by-row DML) — found by manually exercising
# this migration during Phase 3 development, where `TRUNCATE audit_events`
# silently succeeded despite the trigger above. A statement-level TRUNCATE
# trigger closes that gap; ADR-0003 says "no UPDATE/DELETE grants" but the
# intent — nothing can erase a written decision — clearly extends to this.
_CREATE_TRUNCATE_TRIGGER = """
CREATE TRIGGER audit_events_no_truncate
BEFORE TRUNCATE ON audit_events
FOR EACH STATEMENT EXECUTE FUNCTION audit_events_no_update_delete();
"""

_DROP_TRIGGER = "DROP TRIGGER audit_events_append_only ON audit_events;"
_DROP_TRUNCATE_TRIGGER = "DROP TRIGGER audit_events_no_truncate ON audit_events;"
_DROP_FUNCTION = "DROP FUNCTION audit_events_no_update_delete();"


def upgrade() -> None:
    op.execute(_CREATE_FUNCTION)
    op.execute(_CREATE_TRIGGER)
    op.execute(_CREATE_TRUNCATE_TRIGGER)


def downgrade() -> None:
    op.execute(_DROP_TRUNCATE_TRIGGER)
    op.execute(_DROP_TRIGGER)
    op.execute(_DROP_FUNCTION)
