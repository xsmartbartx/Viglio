"""The single declarative base every ORM model in Vigilo registers against.

A shared `MetaData` with a fixed naming convention means Alembic autogenerate
produces stable constraint names (`ck_accounts_status`, not
`ck_accounts_a1b2c3`) regardless of which module's `orm.py` defined the table.
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
