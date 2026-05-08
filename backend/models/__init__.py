"""
models/__init__.py
==================
Import all models here so SQLAlchemy registers them
with the Base metadata for Alembic migrations.
"""

from backend.models.user import User
from backend.models.credential import Credential
from backend.models.resume import Resume
from backend.models.job_preference import JobPreference
from backend.models.application import Application

__all__ = ["User", "Credential", "Resume", "JobPreference", "Application"]
