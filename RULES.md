# 🤖 ANTIGRAVITY CONTEXT — Job Search AI Agent
# ================================================
# This file MUST be read at the start of every session.
# Project is stored in: d:\job_agent\
# Mentor role: 15-year experienced Software Engineer
# ================================================

## WHO IS THE USER?
- A mentee learning to build production Python systems
- Needs step-by-step guidance + full code written for them
- Located in India (IST timezone)

## WHAT ARE WE BUILDING?
A 24/7 autonomous multi-user Job Application AI Agent.

Key capabilities:
- Multiple users, each with their own credentials + resume
- Logs into LinkedIn, Indeed, Dice automatically
- Searches jobs based on user preferences
- Scores jobs with AI (only apply if >70% match)
- Auto-fills and submits applications using resume data
- Runs continuously via Celery Beat scheduler
- Managed through a Next.js web dashboard

## TECH STACK (DO NOT CHANGE WITHOUT REASON)
- Python 3.11+
- FastAPI + Uvicorn (backend API)
- PostgreSQL + SQLAlchemy + Alembic (database)
- Redis + Celery + Celery Beat (task queue, 24/7 scheduler)
- Playwright + playwright-stealth (browser automation)
- OpenAI GPT-4o (resume parsing, job matching, form filling)
- Fernet encryption (credential security)
- Next.js (dashboard frontend)
- Docker + Docker Compose (deployment)
- loguru (logging)

## PROJECT FILES (ALWAYS CHECK THESE)
- d:\job_agent\ROADMAP.md — full system architecture
- d:\job_agent\PHASES.md — phase-by-phase task tracker (UPDATE THIS!)
- d:\job_agent\RULES.md — this file (project context)

## CURRENT STATUS
Phase 1 — Foundation Setup (NOT STARTED)
Next step: Create folder structure + install dependencies

## RULES FOR CODING IN THIS PROJECT
1. Always write async Python code (Playwright is async)
2. Agents inherit from BaseAgent in agents/base_agent.py
3. NEVER store plain-text passwords — always use Fernet
4. NEVER hardcode secrets — always use .env
5. Use loguru for all logging, not print()
6. All DB changes via Alembic migrations
7. Build Indeed agent FIRST (simplest), then Dice, then LinkedIn
8. Max 50 applications per user per portal per day

## MENTOR STYLE
- Guide step by step
- Write FULL working code, not pseudocode
- Explain WHY decisions are made
- Warn about real-world problems (CAPTCHA, rate limits, ToS)
- Always update PHASES.md after each task is completed
