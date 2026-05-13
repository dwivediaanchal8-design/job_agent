"""
auth.py — Authentication Utilities
=====================================
Handles:
  - Password hashing (bcrypt via passlib)
  - JWT token creation and validation
  - FastAPI security dependency

MENTOR NOTE:
  Two separate security mechanisms here:
  1. bcrypt  → for admin/user ACCOUNT passwords (one-way, login only)
  2. Fernet  → for PORTAL passwords (two-way, must decrypt to use)
  Never mix these up!
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
import bcrypt
from loguru import logger

from backend.config import settings


# ─── Password Hashing ─────────────────────────────────────────────────────────
# Using bcrypt directly (passlib has a Python 3.13 compatibility issue)

def hash_password(plain_password: str) -> str:
    """Hash a plain-text password using bcrypt."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check if a plain password matches a stored bcrypt hash."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


# ─── JWT Token ────────────────────────────────────────────────────────────────
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def create_access_token(user_id: uuid.UUID, role: str) -> str:
    """
    Creates a signed JWT access token.

    Args:
        user_id: The user's UUID.
        role: 'admin' or 'job_seeker'.

    Returns:
        Signed JWT string.
    """
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_access_token_expire_minutes
    )
    payload = {
        "sub": str(user_id),      # Subject: user ID
        "role": role,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> dict:
    """
    Decodes and validates a JWT token.

    Returns:
        Decoded payload dict with 'sub' (user_id) and 'role'.

    Raises:
        HTTPException 401 if token is invalid or expired.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        return payload
    except JWTError as e:
        logger.warning(f"JWT validation failed: {e}")
        raise credentials_exception


# ─── FastAPI Dependencies ──────────────────────────────────────────────────────
async def get_current_user_id(token: str = Depends(oauth2_scheme)) -> uuid.UUID:
    """
    FastAPI dependency: extracts user_id from Bearer token.

    Usage:
        async def my_route(user_id: uuid.UUID = Depends(get_current_user_id)):
    """
    payload = decode_access_token(token)
    return uuid.UUID(payload["sub"])


async def require_admin(token: str = Depends(oauth2_scheme)) -> uuid.UUID:
    """
    FastAPI dependency: only allows admin users.

    Raises:
        HTTP 403 if user is not an admin.
    """
    payload = decode_access_token(token)
    if payload.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )
    return uuid.UUID(payload["sub"])
