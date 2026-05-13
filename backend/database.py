"""
database.py — Database Engine & Session Factory
================================================
Uses SQLAlchemy with async support for PostgreSQL.

Two session types:
  AsyncSession     — for FastAPI routes (async/await)
  SyncSessionFactory — for Celery tasks (sync workers can't use async)
"""

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from loguru import logger

from backend.config import settings


# ─── Async Engine ─────────────────────────────────────────────────────────────
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,          # Log all SQL in dev mode
    pool_size=10,                  # Connection pool size
    max_overflow=20,               # Extra connections if pool is full
    pool_pre_ping=True,            # Test connections before use
)


# ─── Session Factory ───────────────────────────────────────────────────────────
AsyncSessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,        # Keep objects usable after commit
    autoflush=False,
    autocommit=False,
)


# ─── Sync Engine (for Celery workers) ────────────────────────────────────────
# MENTOR NOTE:
#   Celery workers are synchronous. We create a separate sync SQLAlchemy engine
#   pointing to the same database but using the sync driver (psycopg2, not asyncpg).
#   database_url_sync = postgresql+psycopg2://... (set in .env)

sync_engine = create_engine(
    settings.database_url_sync,
    echo=settings.debug,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)

SyncSessionFactory = sessionmaker(
    bind=sync_engine,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


@contextmanager
def get_sync_session():
    """
    Context manager that yields a sync SQLAlchemy session.
    Use ONLY in Celery tasks (not FastAPI routes).

    Usage:
        with get_sync_session() as db:
            user = db.execute(select(User)).scalar_one()
    """
    session: Session = SyncSessionFactory()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Sync DB error, rolling back: {e}")
        raise
    finally:
        session.close()


# ─── Base Model Class ──────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    """
    All ORM models inherit from this class.
    Provides the metadata registry for Alembic migrations.
    """
    pass


# ─── Dependency (use in FastAPI routes) ───────────────────────────────────────
async def get_db() -> AsyncSession:
    """
    FastAPI dependency that yields a database session.

    Usage in routes:
        async def my_route(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database error, rolling back: {e}")
            raise
        finally:
            await session.close()


# ─── Startup: Create tables if not exist ──────────────────────────────────────
async def create_all_tables():
    """
    Creates all tables defined in ORM models.
    Called on app startup. Does NOT replace Alembic migrations in production.
    """
    from backend.models import (  # noqa: F401 — import triggers registration
        user, credential, resume, job_preference, application
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("All database tables created/verified.")
