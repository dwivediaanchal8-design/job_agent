# 📋 Job Search AI Agent — Phase Tracker

> **Status**: 🟡 IN PROGRESS | **Current Phase**: PHASE 1  
> **Workspace**: `d:\job_agent\`  
> **Last Updated**: 2026-05-08

---

## 📊 Overall Progress

```
Phase 1 ████████████████████  [IN PROGRESS]  Foundation Setup
Phase 2 ░░░░░░░░░░░░░░░░░░░░  [LOCKED]       Browser Agents
Phase 3 ░░░░░░░░░░░░░░░░░░░░  [LOCKED]       AI Integration
Phase 4 ░░░░░░░░░░░░░░░░░░░░  [LOCKED]       Scheduler (24/7)
Phase 5 ░░░░░░░░░░░░░░░░░░░░  [LOCKED]       Dashboard UI
Phase 6 ░░░░░░░░░░░░░░░░░░░░  [LOCKED]       Testing & Polish
Phase 7 ░░░░░░░░░░░░░░░░░░░░  [LOCKED]       Docker Deployment
```

---

---

# 🟢 PHASE 1 — Backend Foundation
**Duration**: Week 1-2 | **Status**: IN PROGRESS (2026-05-08)  
**Goal**: A working API server with database, user management, and credential encryption.

## Tasks

### 1.1 — Project Setup
- [x] Create folder structure under `d:\job_agent\`
- [x] Create Python virtual environment (`venv/`)
- [x] Create `requirements.txt` with all dependencies
- [x] Create `.env.example` file with placeholder values → copy to `.env` and fill in
- [ ] Initialize git repository → run: `git init && git add . && git commit -m "Phase 1: Foundation"`
- [x] Create `.gitignore` (exclude `.env`, `__pycache__`, etc.)

### 1.2 — Database Setup
- [ ] Install PostgreSQL locally (or via Docker) → **YOU MUST DO THIS**
- [ ] Create database: `job_agent_db` → run: `createdb job_agent_db`
- [x] Create `backend/database.py` (SQLAlchemy async engine)
- [x] Create all models:
  - [x] `models/user.py` — users table
  - [x] `models/credential.py` — encrypted portal credentials
  - [x] `models/resume.py` — resume files + parsed JSON
  - [x] `models/job_preference.py` — search preferences
  - [x] `models/application.py` — application history
- [ ] Setup Alembic for migrations → next step after PostgreSQL is installed
- [ ] Run first migration — create all tables

### 1.3 — Security Layer
- [x] Create `services/credential_manager.py`
  - [x] `encrypt(plain_text) → encrypted_string`
  - [x] `decrypt(encrypted_string) → plain_text`
- [ ] Generate MASTER_KEY → run: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` → paste in `.env`
- [x] Create `backend/auth.py`
  - [x] `hash_password(plain)` using bcrypt
  - [x] `verify_password(plain, hashed)`
  - [x] `create_access_token(user_id, role)`
  - [x] `decode_access_token(token)`

### 1.4 — FastAPI Server
- [x] Create `backend/main.py` with FastAPI app
- [x] Configure CORS middleware
- [x] Add health check route: `GET /health`
- [x] Create all Pydantic schemas in `schemas/`
- [x] Build API routes:
  - [x] `POST /auth/register` — create admin account
  - [x] `POST /auth/login` — get JWT token
  - [x] `POST /users` — add a job-seeker user
  - [x] `GET /users` — list all users
  - [x] `POST /credentials` — save encrypted portal login
  - [x] `POST /resumes/upload` — upload PDF/DOCX
  - [x] `POST /preferences` — save job search preferences
  - [x] `GET /applications` — get application history

### 1.5 — Verify Phase 1
- [ ] Start server: `uvicorn backend.main:app --reload`
- [ ] Test all endpoints via FastAPI's auto docs: `http://localhost:8000/docs`
- [ ] Confirm credentials are stored encrypted in DB
- [ ] Confirm JWT authentication works

## ✅ Phase 1 Exit Criteria
> Phase 2 is LOCKED until ALL of these pass:
- API server starts without errors
- Can register a user and login with JWT
- Can save encrypted credentials to DB and decrypt them
- Can upload a resume file via API

---

---

# 🔒 PHASE 2 — Browser Agents (LOCKED)
**Duration**: Week 3-4 | **Unlock after**: Phase 1 complete  
**Goal**: Browser agents that can log into portals and find jobs.

## Tasks

### 2.1 — Base Agent
- [ ] Create `agents/base_agent.py`
  - [ ] `launch()` — start Playwright + stealth
  - [ ] `login(username, password)` — abstract method
  - [ ] `search_jobs(keywords, location)` — abstract method
  - [ ] `apply_job(job_url, user_data)` — abstract method
  - [ ] `save_cookies()` / `load_cookies()` — session persistence
  - [ ] `close()` — cleanup

### 2.2 — Indeed Agent (Start Here — Simplest)
- [ ] Create `agents/indeed_agent.py`
- [ ] Implement `login()` for Indeed
- [ ] Implement `search_jobs()` — use Indeed search URL
- [ ] Extract job listings (title, company, URL, description)
- [ ] Implement `apply_job()` for "Indeed Apply" jobs
- [ ] Handle multi-step forms
- [ ] Handle resume upload step

### 2.3 — Dice Agent
- [ ] Create `agents/dice_agent.py`
- [ ] Implement login, search, apply flow
- [ ] Focus on tech job filters

### 2.4 — LinkedIn Agent (Most Complex)
- [ ] Create `agents/linkedin_agent.py`
- [ ] Implement login with cookie persistence
- [ ] Search jobs using LinkedIn filters
- [ ] Implement "Easy Apply" flow
- [ ] Handle multi-page Easy Apply forms
- [ ] Handle "More Information Required" popups

### 2.5 — CAPTCHA Handling
- [ ] Sign up for 2captcha.com
- [ ] Add API key to `.env`
- [ ] Create `services/captcha_solver.py`
  - [ ] Detect CAPTCHA on page
  - [ ] Send to 2captcha API
  - [ ] Wait for solution → submit

### 2.6 — Verify Phase 2
- [ ] Run Indeed agent manually for 1 test user
- [ ] Confirm it logs in successfully
- [ ] Confirm it finds at least 10 job listings
- [ ] Confirm it applies to 1 job (test mode)

## ✅ Phase 2 Exit Criteria
- Indeed agent completes full search + apply cycle
- All agents handle errors without crashing
- Cookies saved/loaded to skip repeated logins

---

---

# 🔒 PHASE 3 — AI Integration (LOCKED)
**Duration**: Week 5-6 | **Unlock after**: Phase 2 complete  
**Goal**: Make the agent intelligent — parse resumes, score jobs, fill forms.

## Tasks

### 3.1 — Resume Parser
- [ ] Create `services/resume_parser.py`
- [ ] Implement PDF parsing with PyMuPDF
- [ ] Implement DOCX parsing with python-docx
- [ ] Call GPT-4o to extract structured JSON:
  ```json
  {
    "name": "...",
    "email": "...",
    "phone": "...",
    "skills": [...],
    "experience": [...],
    "education": [...],
    "summary": "..."
  }
  ```
- [ ] Store parsed JSON in `resumes.parsed_json`

### 3.2 — Job Matcher
- [ ] Create `services/job_matcher.py`
- [ ] Get job description text from agent
- [ ] Use OpenAI embeddings to create vectors
- [ ] Calculate cosine similarity with user skill vector
- [ ] Return score 0-100 + match reasons
- [ ] Only apply if score > 70

### 3.3 — Form Filler
- [ ] Create `services/form_filler.py`
- [ ] Detect form field types (text, dropdown, checkbox, upload)
- [ ] Map standard fields to resume data:
  - `"First Name"` → `resume.name.split()[0]`
  - `"Current Employer"` → latest experience company
  - `"Years of Experience"` → calculated from dates
- [ ] Use GPT-4o for open-ended questions:
  - `"Why do you want to work here?"`
  - `"Describe yourself in 3 words"`
  - `"What is your biggest strength?"`

### 3.4 — Cover Letter Generator
- [ ] Generate personalized cover letter per job
- [ ] Input: job description + user profile
- [ ] Output: 3-paragraph professional letter

### 3.5 — Verify Phase 3
- [ ] Parse a real PDF resume → confirm extracted skills match
- [ ] Test job scoring on 5 sample job descriptions
- [ ] Confirm form filler correctly maps basic fields

## ✅ Phase 3 Exit Criteria
- Resume parsing produces accurate JSON
- Job scoring correctly filters irrelevant jobs
- Form filler handles standard fields without errors

---

---

# 🔒 PHASE 4 — Scheduler / 24-7 Engine (LOCKED)
**Duration**: Week 7 | **Unlock after**: Phase 3 complete  
**Goal**: Run the entire pipeline automatically, forever.

## Tasks

### 4.1 — Celery Setup
- [ ] Install Redis (via Docker)
- [ ] Create `tasks/celery_app.py`
  - [ ] Configure broker: `redis://localhost:6379/0`
  - [ ] Configure result backend
  - [ ] Configure Celery Beat schedule

### 4.2 — Task Definitions
- [ ] Create `tasks/job_tasks.py`
  - [ ] `run_job_agent(user_id, portal)` — main task
  - [ ] `run_all_users()` — dispatches tasks for all active users
  - [ ] `generate_daily_report()` — summary task

### 4.3 — Schedule Configuration
- [ ] Run agent every 4 hours for all users
- [ ] Run daily report at midnight
- [ ] Add retry logic (max 3 retries on failure)
- [ ] Add task timeout (max 2 hours per user/portal)

### 4.4 — Logging
- [ ] Install loguru
- [ ] Log all agent actions to file + DB
- [ ] Log format: `[timestamp] [user_id] [portal] [action] [result]`

### 4.5 — Verify Phase 4
- [ ] Start Celery worker + beat
- [ ] Confirm tasks are scheduled and running
- [ ] Confirm system runs for 24 hours without crash
- [ ] Review logs for errors

## ✅ Phase 4 Exit Criteria
- System runs 24h without manual intervention
- All task failures are logged and retried automatically
- Daily report generated with correct counts

---

---

# 🔒 PHASE 5 — Dashboard UI (LOCKED)
**Duration**: Week 8 | **Unlock after**: Phase 4 complete  
**Goal**: A beautiful web interface to manage and monitor the system.

## Tasks

### 5.1 — Next.js Setup
- [ ] Initialize Next.js project in `frontend/`
- [ ] Install Axios for API calls
- [ ] Install Chart.js for stats charts
- [ ] Set up API base URL from env

### 5.2 — Pages
- [ ] `/` — Dashboard: stats cards (applications today, success rate, active users)
- [ ] `/users` — User list, add user form, activate/deactivate toggle
- [ ] `/users/[id]` — Upload resume, set credentials, set preferences
- [ ] `/applications` — Table with filters (user, portal, status, date)
- [ ] `/logs` — Real-time agent log stream

### 5.3 — Verify Phase 5
- [ ] Can add a new user end-to-end from dashboard
- [ ] Application history shows correctly
- [ ] Stats update after agent runs

## ✅ Phase 5 Exit Criteria
- All pages functional and connected to API
- Dashboard shows real-time data

---

---

# 🔒 PHASE 6 — Testing & Polish (LOCKED)
**Duration**: Week 9  
**Goal**: Make it reliable for real use.

## Tasks
- [ ] Write integration tests for all API endpoints
- [ ] Test agents with real accounts on all 3 portals
- [ ] Add error alerting (email/Slack notification on failure)
- [ ] Add rate limiting enforcement
- [ ] Add user pause/resume controls
- [ ] Performance test: 10 users running simultaneously
- [ ] Security audit: check for exposed credentials

---

---

# 🔒 PHASE 7 — Docker Deployment (LOCKED)
**Duration**: Week 9  
**Goal**: Deploy to a cloud server, run forever.

## Tasks
- [ ] Create `Dockerfile` for backend
- [ ] Create `Dockerfile` for frontend
- [ ] Create `docker-compose.yml` with all services
- [ ] Set up environment variables on server
- [ ] Deploy to DigitalOcean / AWS EC2
- [ ] Set up Nginx reverse proxy
- [ ] Configure SSL (Let's Encrypt)
- [ ] Set up monitoring (UptimeRobot)
- [ ] Verify 24/7 operation post-deploy

---

---

## 📝 Session Log

| Date | Phase | What Was Done |
|---|---|---|
| 2026-05-08 | Planning | Created ROADMAP.md, RULES.md, PHASES.md |
| 2026-05-08 | Phase 1 | Built all backend code: models, schemas, API routes, auth, security, Celery tasks |
| 2026-05-08 | Phase 1 | Created venv, installed all pip dependencies |

> Update this table after every coding session.
