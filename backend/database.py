import os
import sqlite3

from sqlalchemy import create_engine
from sqlalchemy import inspect
from sqlalchemy.schema import CreateTable
from sqlalchemy.schema import CreateIndex
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable must be set")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def _remove_agent_organization_uniqueness() -> None:
    agent_table = Base.metadata.tables["organization_agents"]
    inspector = inspect(engine)
    unique_constraints = inspector.get_unique_constraints("organization_agents")
    unique_indexes = inspector.get_indexes("organization_agents")
    unique_names = {
        constraint.get("name")
        for constraint in unique_constraints
        if constraint.get("column_names") == ["organization_id"]
    }
    unique_names.update(
        index.get("name")
        for index in unique_indexes
        if index.get("unique")
        and index.get("column_names") == ["organization_id"]
    )
    unique_names.discard(None)
    if not unique_names:
        return

    if engine.dialect.name == "sqlite":
        raw_connection = engine.raw_connection()
        try:
            cursor = raw_connection.cursor()
            create_statement = str(CreateTable(agent_table).compile(dialect=engine.dialect))
            create_statement = create_statement.replace(
                "CREATE TABLE organization_agents (",
                "CREATE TABLE organization_agents_replacement (",
                1,
            )
            if "CREATE TABLE organization_agents_replacement (" not in create_statement:
                raise RuntimeError(
                    "Could not prepare SQLite agent table migration"
                )
            cursor.execute(create_statement)
            columns = {column["name"] for column in inspector.get_columns("organization_agents")}
            target_columns = [column.name for column in agent_table.columns if column.name in columns]
            quoted_columns = ", ".join(
                engine.dialect.identifier_preparer.quote(name) for name in target_columns
            )
            cursor.execute(
                "INSERT INTO organization_agents_replacement "
                f"({quoted_columns}) SELECT {quoted_columns} FROM organization_agents"
            )
            cursor.execute("DROP TABLE organization_agents")
            cursor.execute(
                "ALTER TABLE organization_agents_replacement RENAME TO organization_agents"
            )
            raw_connection.commit()
        except sqlite3.Error:
            raw_connection.rollback()
            raise
        finally:
            raw_connection.close()
        refreshed_indexes = {
            index["name"] for index in inspect(engine).get_indexes("organization_agents")
        }
        for index in agent_table.indexes:
            if index.name not in refreshed_indexes:
                with engine.begin() as connection:
                    connection.execute(CreateIndex(index))
        return

    for name in unique_names:
        quoted_name = engine.dialect.identifier_preparer.quote(name)
        if engine.dialect.name == "mysql":
            statement = f"ALTER TABLE organization_agents DROP INDEX {quoted_name}"
        else:
            statement = (
                "ALTER TABLE organization_agents "
                f"DROP CONSTRAINT {quoted_name}"
            )
        with engine.begin() as connection:
            connection.exec_driver_sql(statement)


def migrate_existing_schema() -> None:
    inspector = inspect(engine)
    if "organizations" in inspector.get_table_names():
        existing = {column["name"] for column in inspector.get_columns("organizations")}
        organization_table = Base.metadata.tables["organizations"]
        for column_name in ("join_pin_hash",):
            if column_name not in existing:
                column = organization_table.columns[column_name]
                column_type = column.type.compile(dialect=engine.dialect)
                quoted_column = engine.dialect.identifier_preparer.quote(column_name)
                with engine.begin() as connection:
                    connection.exec_driver_sql(
                        f"ALTER TABLE organizations ADD COLUMN {quoted_column} {column_type}"
                    )

    if "organization_members" in inspector.get_table_names():
        existing = {
            column["name"]
            for column in inspector.get_columns("organization_members")
        }
        member_table = Base.metadata.tables["organization_members"]
        for column_name in (
            "employee_id",
            "employee_salary",
            "employee_leaves",
            "designation",
        ):
            if column_name not in existing:
                column = member_table.columns[column_name]
                column_type = column.type.compile(dialect=engine.dialect)
                quoted_column = engine.dialect.identifier_preparer.quote(column_name)
                with engine.begin() as connection:
                    connection.exec_driver_sql(
                        "ALTER TABLE organization_members "
                        f"ADD COLUMN {quoted_column} {column_type}"
                    )

        existing_indexes = {
            index["name"] for index in inspect(engine).get_indexes("organization_members")
        }
        for index in member_table.indexes:
            if index.name not in existing_indexes:
                with engine.begin() as connection:
                    connection.execute(CreateIndex(index))

    if "organization_agents" in inspector.get_table_names():
        existing = {
            column["name"]
            for column in inspect(engine).get_columns("organization_agents")
        }
        if "agent_name" not in existing:
            column = Base.metadata.tables["organization_agents"].columns["agent_name"]
            column_type = column.type.compile(dialect=engine.dialect)
            quoted_column = engine.dialect.identifier_preparer.quote("agent_name")
            with engine.begin() as connection:
                connection.exec_driver_sql(
                    "ALTER TABLE organization_agents "
                    f"ADD COLUMN {quoted_column} {column_type} "
                    "NOT NULL DEFAULT 'Organization Assistant'"
                )
        _remove_agent_organization_uniqueness()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
