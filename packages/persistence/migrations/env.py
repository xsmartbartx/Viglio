"""Alembic environment.

Populates `Base.metadata` by importing every persistence-backed module's
`orm.py` — a deliberate reach-across-packages pattern that does NOT make
`vigilo-persistence` depend on `vigilo-identity`/`vigilo-project`/
`vigilo-security`/`vigilo-orchestrator` in `pyproject.toml`. This works
because `uv sync --all-packages` puts every workspace member in one shared
venv, mirroring the existing precedent of `scripts/generate_check_catalog.py`
reaching into `vigilo_checks` without being declared as its dependency.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

import vigilo_orchestrator.orm  # noqa: E402,F401
from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Populate Base.metadata for autogenerate. Import order doesn't matter —
# SQLAlchemy resolves ForeignKey("table_name.column") string references
# lazily, so these only need to have been imported at all before
# `target_metadata` is read below.
import vigilo_identity.orm  # noqa: E402,F401
import vigilo_project.orm  # noqa: E402,F401
import vigilo_security.orm  # noqa: E402,F401
from vigilo_core.config import config as vigilo_config
from vigilo_persistence.base import Base

alembic_config = context.config

if alembic_config.config_file_name is not None:
    fileConfig(alembic_config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    url = vigilo_config().database_url
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url[len("postgresql://") :]
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        {"sqlalchemy.url": _database_url()},
        prefix="sqlalchemy.",
    )

    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
