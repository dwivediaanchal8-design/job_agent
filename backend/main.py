"""
main.py — FastAPI Application Entry Point
==========================================
This is the main file. Run with:
    uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

Then open: http://localhost:8000/docs
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

# ─── Logging Configuration ──────────────────────────────────────────────────
from backend.config import settings
from backend.database import create_all_tables
import sys
logger.remove()
logger.add(sys.stdout, colorize=True, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>", level="INFO")
logger.add(settings.log_file, rotation="10 MB", retention="7 days", level="DEBUG", format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}")

# ─── Import all routers ───────────────────────────────────────────────────────
from backend.api.auth import router as auth_router
from backend.api.users import router as users_router
from backend.api.credentials import router as credentials_router
from backend.api.resumes import router as resumes_router
from backend.api.applications import router as applications_router
from backend.api.logs import router as logs_router
from backend.api.jobs import router as jobs_router


# ─── Startup & Shutdown ───────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs on startup and shutdown.
    Startup: create tables, ensure upload directory exists.
    Shutdown: cleanup connections.
    """
    # STARTUP
    logger.info(f"Starting {settings.app_name} in {settings.app_env} mode")

    # Ensure upload directory exists
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    logger.info(f"Upload directory: {settings.upload_dir}")

    # Create DB tables (safe to run multiple times — uses IF NOT EXISTS)
    await create_all_tables()

    logger.success("Application started successfully!")
    logger.info(f"API Docs: http://{settings.api_host}:{settings.api_port}/docs")

    yield  # App runs here

    # SHUTDOWN
    logger.info("👋 Application shutting down...")


# ─── Create FastAPI App ───────────────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    description="""
    ## Job Search AI Agent API

    Manage multiple users' automated job applications on LinkedIn, Indeed, and Dice.

    ### Features:
    - 👤 **User Management** — Add job seekers, manage their profiles
    - 🔑 **Credentials** — Securely store encrypted portal logins
    - 📄 **Resumes** — Upload and AI-parse PDF/DOCX resumes
    - ⚙️ **Preferences** — Set job search filters per user
    - 📊 **Applications** — Track all submissions and stats
    - 🤖 **24/7 Automation** — Celery workers apply continuously
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# ─── CORS Middleware ──────────────────────────────────────────────────────────
# Allows the Next.js dashboard (port 3000) to call this API (port 8000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",    # Next.js dev server
        "http://127.0.0.1:3000",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Security Headers Middleware ──────────────────────────────────────────────
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'"
    return response


# ─── Register Routers ─────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(credentials_router)
app.include_router(resumes_router)
app.include_router(applications_router)
app.include_router(logs_router)
app.include_router(jobs_router)


# ─── Health Check ─────────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health_check():
    """
    Health check endpoint.
    Returns status of API and its configuration.
    Used by monitoring tools and Docker health checks.
    """
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": "1.0.0",
        "environment": settings.app_env,
    }


@app.get("/", tags=["System"])
async def root():
    """Root endpoint — shows API info."""
    return {
        "message": f"Welcome to {settings.app_name}",
        "docs": "/docs",
        "health": "/health",
    }
