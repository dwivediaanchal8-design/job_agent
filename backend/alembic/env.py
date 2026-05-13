"""
backend/alembic/env.py — Alembic Migration Environment
========================================================
Configured to:
  - Read DATABASE_URL_SYNC from .env
  - Import all our SQLAlchemy models so Alembic sees the schema
  - Support both online (connected) and offline (SQL script) migrations
"""

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool
from alembic import context

# ─── Add project root to Python path ──────────────────────────────────────────
# This allows "from backend.xxx import yyy" to work inside Alembic
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# ─── Load .env variables ──────────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# ─── Import our Base and ALL models (so Alembic sees the tables) ───────────────
from backend.database import Base
from backend.models import User, Credential, Resume, JobPreference, Application  # noqa

# ─── Alembic Config ───────────────────────────────────────────────────────────
config = context.config

# Set the database URL from environment (overrides alembic.ini)
# Note: configparser uses % for interpolation, so we must escape it as %%
db_url = os.environ.get("DATABASE_URL_SYNC")
if not db_url:
    raise ValueError("DATABASE_URL_SYNC not set in .env")
# Escape % signs so configparser doesn't misinterpret them
db_url_escaped = db_url.replace("%", "%%")
config.set_main_option("sqlalchemy.url", db_url_escaped)

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Use our Base.metadata so Alembic can auto-detect schema changes
target_metadata = Base.metadata


# ─── Offline Migration (generates SQL file without DB connection) ──────────────
def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


# ─── Online Migration (connects to DB and runs directly) ──────────────────────
def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
