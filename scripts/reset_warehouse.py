"""Irreversibly replace the configured database schema with the warehouse."""
from __future__ import annotations
import sys
from pathlib import Path
from sqlalchemy import MetaData,inspect,text
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from alembic import command
from alembic.config import Config
from backend_core.config import get_settings
from backend_core.db import Base,create_db_engine
import backend_core.domain  # noqa: F401

def main():
    settings=get_settings()
    if settings.db_name.lower() in {"mysql","information_schema","performance_schema","sys"}:
        raise RuntimeError("refusing to reset a system database")
    engine=create_db_engine(settings.database_url)
    before=inspect(engine).get_table_names()
    metadata=MetaData();metadata.reflect(bind=engine)
    with engine.begin() as connection:
        connection.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        metadata.drop_all(bind=connection)
        connection.execute(text("SET FOREIGN_KEY_CHECKS=1"))
        Base.metadata.create_all(bind=connection)
    engine.dispose()
    command.stamp(Config(str(ROOT/"alembic.ini")),"head")
    print(f"reset {settings.db_name}: removed {len(before)} tables, created {len(Base.metadata.tables)} warehouse tables")
if __name__=="__main__":main()
