# Job Search Pipeline Integration Guide

This document outlines how the entire job search and application pipeline is integrated, from the frontend command center to the AI-powered agents.

## 🏗️ System Architecture

1.  **Frontend (Next.js)**: A premium dashboard that provides real-time monitoring and a "Command Center" to manually trigger job runs.
2.  **API Gateway (FastAPI)**: Routes requests to the database and dispatches background tasks to Celery.
3.  **Task Queue (Celery + Redis)**: Manages asynchronous job agents to prevent blocking the web server.
4.  **AI Services**:
    *   **Resume Parser**: Extracts structured data from PDF/DOCX resumes.
    *   **Job Matcher**: Scores jobs against your profile using GPT-4o.
    *   **Form Filler**: Intelligently maps your data to complex application forms.
    *   **Cover Letter Generator**: Creates tailored cover letters for every application.
5.  **Browser Agents (Playwright)**: Automates the actual browser interaction on LinkedIn, Indeed, and Dice.

## 🚀 How to Apply for a Job

### 1. Automatic Mode (Default)
The system is configured to run automatically every 4 hours via Celery Beat. It will:
*   Fetch your active preferences.
*   Search for new jobs on your configured portals.
*   Filter jobs based on your AI match score.
*   Apply to high-score jobs automatically.

### 2. Manual Command (New)
You can now trigger an immediate "Search & Apply" pulse from the Dashboard:
1.  Navigate to the **Dashboard**.
2.  Locate the **Manual Command** panel on the right sidebar.
3.  Select the **Target User** and **Job Portal** (Dice, Indeed, or LinkedIn).
4.  Toggle **Dry Run** (Simulation) if you want to test without actually submitting.
5.  Click **Execute Pipeline**.

## 📁 Integrated Info File

The system uses a unified user profile for all applications. All integrated information is stored in the database but can be managed via the UI:
*   **Credentials**: Encrypted portal logins (`/credentials`).
*   **Preferences**: Keywords, locations, and portal settings (`/preferences`).
*   **Resume**: Parsed and structured experience data (`/resumes`).

## 🛠️ Deployment & Execution

To run the full integrated pipeline:

```powershell
# 1. Start the Backend API
uvicorn backend.main:app --reload

# 2. Start the Celery Worker
celery -A backend.tasks.celery_app worker --loglevel=info -P solo

# 3. Start the Frontend
cd frontend
npm run dev
```

The system is now fully integrated and ready to apply to the workplace on your behalf!
