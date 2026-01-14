"""Alembic environment configuration.

Loads database URL from environment and configures migration context.
Supports both PostgreSQL and SQLite (for local development/testing).
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

# Load environment variables from .env file if available
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

# Import all models to ensure they are registered with Base.metadata
from vozbot.storage.db.models import Base

# This is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Model's MetaData object for 'autogenerate' support
target_metadata = Base.metadata


def get_url() -> str:
    """Get database URL from environment.

    Falls back to SQLite for local development/testing if DATABASE_URL is not set.
    """
    url = os.environ.get("DATABASE_URL") or os.environ.get("DB_URL")

    if url:
        # Handle asyncpg URLs - convert to sync for Alembic
        if url.startswith("postgresql+asyncpg://"):
            url = url.replace("postgresql+asyncpg://", "postgresql://")
        # Handle Heroku-style postgres:// URLs (need postgresql://)
        elif url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url

    # Default to SQLite for local development
    return "sqlite:///./vozbot.db"


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine.
    By skipping the Engine creation we don't need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the script output.
    """
    url = get_url()

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine and associate a connection
    with the context.
    """
    url = get_url()

    # Use NullPool for SQLite to avoid threading issues
    poolclass = pool.NullPool

    connectable = create_engine(
        url,
        poolclass=poolclass,
    )

    with connectable.connect() as connection:
        # Enable batch mode for SQLite to support ALTER TABLE operations
        is_sqlite = url.startswith("sqlite")

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            render_as_batch=is_sqlite,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
