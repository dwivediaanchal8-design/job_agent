# 🗺️ Job Search AI Agent — Master Roadmap

> **Version**: 1.0 | **Created**: 2026-05-08  
> **Workspace**: `d:\job_agent\`

---

## 🎯 Project Vision

A 24/7 autonomous AI agent that logs into LinkedIn, Indeed, and Dice for multiple users, finds matching jobs, and auto-applies using each user's resume and preferences.

---

## 🏛️ Architecture Summary

```
[Dashboard UI] → [FastAPI Backend] → [PostgreSQL + Redis]
                                           ↓
                                   [Celery Workers - 24/7]
                                           ↓
                    [LinkedIn Agent] [Indeed Agent] [Dice Agent]
                                    (Playwright)
                                           ↓
                              [GPT-4o AI Engine]
                     (Resume Parser + Job Matcher + Form Filler)
```

---

## 📦 Modules

| # | Module | Description |
|---|---|---|
| 1 | Backend Foundation | FastAPI + PostgreSQL + JWT Auth |
| 2 | Security Layer | Fernet encryption for credentials |
| 3 | Resume Intelligence | PDF/DOCX parsing → structured JSON via GPT-4o |
| 4 | Browser Agents | Playwright bots for each portal |
| 5 | AI Engine | Job matching, form filling, cover letters |
| 6 | Task Scheduler | Celery Beat — runs every 4 hours |
| 7 | Dashboard | Next.js — manage users, view stats |

---

## 🔒 Security Rules

- ALL portal passwords encrypted with Fernet (AES-128)
- JWT tokens for all API access
- Secrets in `.env` — never hardcoded
- Max 50 applications/day/user/portal
- Never log plain-text credentials

---

## 🔄 End-to-End Flow

```
1. Add user → save credentials (encrypted) → upload resume → set preferences
2. Celery Beat triggers every 4 hours
3. Agent launches browser → logs in → searches jobs
4. AI scores each job (0-100) → applies if score > 70%
5. Results saved to DB → visible in dashboard
```

---

## 💰 Monthly Costs

| Service | Cost |
|---|---|
| VPS (4 vCPU, 8GB) | $40 |
| OpenAI API | $20-50 |
| CAPTCHA (2captcha) | $5-20 |
| Proxies | $20-50 |
| **Total** | **~$85-160** |

---

## ✅ Definition of Done

- Multiple users manageable via dashboard
- Credentials and resumes stored securely
- Agent logs into all 3 portals successfully
- Jobs scored and applied to automatically
- Runs 24h without manual intervention
- Deployed via Docker on cloud server
