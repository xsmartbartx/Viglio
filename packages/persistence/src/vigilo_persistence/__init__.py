"""Vigilo persistence: the shared SQLAlchemy primitives every persistence-backed
module builds on (docs/modules.md §1a).

This is deliberately not part of `vigilo_core` — ADR-0001 rule 1 states Core has
"no database access," and that stays literally true: Core depends on nothing,
and this package depends only on Core. `identity`, `project`, `security` and
`orchestrator` each own their own ORM models (`orm.py`) and import `Base` from
here so every table lands in one `MetaData`, but this package itself defines no
domain tables.
"""

from __future__ import annotations

from vigilo_persistence.base import Base
from vigilo_persistence.engine import get_engine
from vigilo_persistence.session import get_sessionmaker, session_scope

__all__ = ["Base", "get_engine", "get_sessionmaker", "session_scope"]
