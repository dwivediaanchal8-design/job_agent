"""
services/form_filler.py — Smart Form Filler (Phase 3)
======================================================
Maps standard job application form fields to resume data deterministically.
Uses GPT-4o for open-ended questions like "Why do you want to work here?"

Usage:
    filler = FormFiller(parsed_resume, user_data)
    value = filler.fill("First Name")              # → "Jane"
    answer = await filler.answer("Why this role?", job_description)
"""

from __future__ import annotations

import re
from typing import Optional
from loguru import logger


# ─── Standard Field Mappings ──────────────────────────────────────────────────

# (keyword_pattern → resolver_function_name)
_FIELD_MAP = [
    # Personal info
    (r"first.?name",                "first_name"),
    (r"last.?name|surname",         "last_name"),
    (r"full.?name",                 "full_name"),
    (r"email",                      "email"),
    (r"phone|mobile|telephone",     "phone"),
    (r"address|location|city",      "location"),
    (r"zip|postal",                 ""),  # leave blank
    # Professional
    (r"linkedin",                   "linkedin"),
    (r"portfolio|website|github",   "portfolio"),
    (r"current.?employer|company",  "current_employer"),
    (r"current.?title|current.?role", "current_title"),
    (r"years.?of.?exp|experience.?years", "years_experience"),
    (r"salary|compensation|pay",    "salary_expectation"),
    (r"start.?date|available",      "availability"),
    # Legal / status
    (r"authorized|work.?auth|eligible.?to.?work", "work_authorization"),
    (r"sponsor|visa.?sponsor",      "visa_sponsorship"),
    (r"relocat",                    "willing_to_relocate"),
    (r"remote|hybrid|on.?site",     "work_preference"),
]

_OPEN_QUESTION_PATTERNS = [
    r"why.*(want|interested|join|work|role|company|position)",
    r"tell us about yourself",
    r"describe yourself",
    r"biggest strength",
    r"greatest weakness",
    r"where do you see yourself",
    r"what.*(motivat|passion|drive)",
    r"why should we hire",
    r"what.*(bring|contribute|offer)",
    r"how.*(handle|deal|manage).*(conflict|pressure|stress|deadline)",
    r"cover letter",
    r"anything else",
    r"additional information",
]

_OPEN_QUESTION_SYSTEM = """
You are a professional job applicant named {name}. Answer the following job application
question in a concise, professional, and positive tone (2-4 sentences max).
Base your answer on the candidate's background: {background}
Current job being applied to: {job_context}
Do not mention AI or automation. Sound genuine and human. Return only the answer text.
"""


class FormFiller:
    """
    Fills job application form fields from a parsed resume.

    Deterministic fields are resolved instantly (no API call).
    Open-ended questions use GPT-4o.
    """

    def __init__(self, parsed_resume: dict, user_data: Optional[dict] = None):
        """
        Args:
            parsed_resume: Output of ResumeParser — the parsed_json dict.
            user_data:     The full user_data dict from job_tasks._get_user_data().
        """
        self._resume = parsed_resume or {}
        self._user = user_data or {}
        self._client = None
        self._gpt_cache: dict[str, str] = {}

    # ── Public: Deterministic Field Filling ────────────────────────────────────

    def fill(self, field_label: str) -> str:
        """
        Map a form field label to resume data.

        Args:
            field_label: The visible text label of the form field.

        Returns:
            String value to type into the field, or "" if not found.
        """
        label_lower = field_label.lower().strip()

        # Try each pattern
        for pattern, resolver in _FIELD_MAP:
            if re.search(pattern, label_lower):
                if not resolver:
                    return ""
                method = getattr(self, f"_get_{resolver}", None)
                if method:
                    val = method()
                    logger.debug(f"[FormFiller] '{field_label}' → '{val}' (pattern: {pattern})")
                    return val

        logger.debug(f"[FormFiller] No mapping for field: '{field_label}'")
        return ""

    def is_open_question(self, field_label: str) -> bool:
        """Returns True if this field needs a GPT-generated answer."""
        label_lower = field_label.lower()
        return any(re.search(p, label_lower) for p in _OPEN_QUESTION_PATTERNS)

    # ── Public: GPT-4o Open Question Answering ─────────────────────────────────

    async def answer(self, question: str, job_description: str = "") -> str:
        """
        Generate a GPT-4o answer for an open-ended form question.

        Caches answers per question to avoid duplicate API calls.

        Args:
            question:        The question text from the form.
            job_description: Job description for context (optional).

        Returns:
            Answer string (2-4 sentences).
        """
        cache_key = question[:100]
        if cache_key in self._gpt_cache:
            return self._gpt_cache[cache_key]

        client = self._get_client()
        if client is None:
            fallback = self._generic_answer(question)
            self._gpt_cache[cache_key] = fallback
            return fallback

        try:
            background = self._build_background_summary()
            job_context = job_description[:500] if job_description else "a software engineering position"

            system_prompt = _OPEN_QUESTION_SYSTEM.format(
                name=self._resume.get("name", "the candidate"),
                background=background,
                job_context=job_context,
            )

            response = await self._client.chat.completions.create(
                model=self._model(),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": question},
                ],
                temperature=0.7,
                max_tokens=300,
            )
            answer = response.choices[0].message.content.strip()
            self._gpt_cache[cache_key] = answer
            logger.info(f"[FormFiller] GPT answered: '{question[:50]}...'")
            return answer

        except Exception as e:
            logger.error(f"[FormFiller] GPT answer failed: {e}")
            fallback = self._generic_answer(question)
            self._gpt_cache[cache_key] = fallback
            return fallback

    # ── Field Resolvers ───────────────────────────────────────────────────────

    def _get_first_name(self) -> str:
        name = self._resume.get("name", "")
        parts = name.strip().split()
        return parts[0] if parts else ""

    def _get_last_name(self) -> str:
        name = self._resume.get("name", "")
        parts = name.strip().split()
        return parts[-1] if len(parts) > 1 else ""

    def _get_full_name(self) -> str:
        return self._resume.get("name", "")

    def _get_email(self) -> str:
        return self._resume.get("email", self._user.get("email", ""))

    def _get_phone(self) -> str:
        return self._resume.get("phone", self._user.get("phone", ""))

    def _get_location(self) -> str:
        return self._resume.get("location", "")

    def _get_linkedin(self) -> str:
        return self._resume.get("linkedin_url", "")

    def _get_portfolio(self) -> str:
        return self._resume.get("portfolio_url", "")

    def _get_current_employer(self) -> str:
        exp = self._resume.get("experience", [])
        if exp:
            latest = exp[0]
            # Only return if currently working there
            end = latest.get("end_date", "").lower()
            if "present" in end or not end:
                return latest.get("company", "")
        return ""

    def _get_current_title(self) -> str:
        exp = self._resume.get("experience", [])
        if exp:
            latest = exp[0]
            end = latest.get("end_date", "").lower()
            if "present" in end or not end:
                return latest.get("title", "")
        return ""

    def _get_years_experience(self) -> str:
        years = self._resume.get("total_years_experience", 0)
        return str(int(years)) if years else "0"

    def _get_salary_expectation(self) -> str:
        return ""  # Leave blank — salary negotiation is user-specific

    def _get_availability(self) -> str:
        return "Immediately"

    def _get_work_authorization(self) -> str:
        return "Yes"  # Default — user should verify

    def _get_visa_sponsorship(self) -> str:
        return "No"  # Default — user should verify

    def _get_willing_to_relocate(self) -> str:
        return "Yes"

    def _get_work_preference(self) -> str:
        return "Hybrid"

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _build_background_summary(self) -> str:
        """Build a compact background summary for GPT context."""
        parts = []
        name = self._resume.get("name", "")
        if name:
            parts.append(f"Name: {name}")
        skills = self._resume.get("skills", [])
        if skills:
            parts.append(f"Skills: {', '.join(skills[:10])}")
        exp = self._resume.get("experience", [])
        if exp:
            latest = exp[0]
            parts.append(f"Current/recent role: {latest.get('title', '')} at {latest.get('company', '')}")
        years = self._resume.get("total_years_experience", 0)
        if years:
            parts.append(f"Total experience: {years} years")
        summary = self._resume.get("summary", "")
        if summary:
            parts.append(f"Summary: {summary[:200]}")
        return ". ".join(parts)

    def _generic_answer(self, question: str) -> str:
        """Fallback answers when GPT is unavailable."""
        q = question.lower()
        if "why" in q and ("company" in q or "role" in q or "work" in q):
            return (
                "I am excited about this opportunity because it aligns with my experience "
                "and career goals. I believe I can contribute meaningfully from day one "
                "while continuing to grow professionally."
            )
        if "strength" in q:
            return (
                "My greatest strength is my ability to quickly learn new technologies "
                "and apply them to solve real problems. I take pride in writing clean, "
                "maintainable code and collaborating effectively with cross-functional teams."
            )
        if "weakness" in q:
            return (
                "I sometimes spend extra time perfecting details, but I have learned to "
                "balance thoroughness with deadlines by setting clear time boundaries for myself."
            )
        if "yourself" in q or "about you" in q:
            name = self._resume.get("name", "I")
            years = self._resume.get("total_years_experience", 0)
            skills = self._resume.get("skills", [])[:3]
            skill_str = ", ".join(skills) if skills else "software development"
            return (
                f"{name} is a dedicated professional with {int(years)} years of experience "
                f"specializing in {skill_str}. I am passionate about building reliable solutions "
                "and am excited to bring my skills to this role."
            )
        return (
            "I am enthusiastic about this opportunity and confident that my background "
            "makes me a strong candidate. I look forward to contributing to the team."
        )

    def _get_client(self):
        if self._client:
            return self._client
        from backend.services.openai_client import get_client
        self._client = get_client()
        return self._client

    def _model(self) -> str:
        from backend.services.openai_client import get_model
        return get_model()


if __name__ == "__main__":
    import asyncio

    SAMPLE_RESUME = {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "phone": "+1-555-123-4567",
        "location": "San Francisco, CA",
        "linkedin_url": "https://linkedin.com/in/janedoe",
        "portfolio_url": "https://github.com/janedoe",
        "skills": ["Python", "FastAPI", "React", "AWS", "Docker"],
        "total_years_experience": 4.5,
        "summary": "Full-stack engineer with 4+ years building scalable web apps.",
        "experience": [
            {
                "title": "Software Engineer",
                "company": "Tech Corp",
                "end_date": "Present",
                "description": "Built APIs with FastAPI.",
                "years": 2.5,
            }
        ],
    }

    async def main():
        filler = FormFiller(SAMPLE_RESUME)
        test_fields = [
            "First Name", "Last Name", "Email Address", "Phone Number",
            "LinkedIn URL", "Current Employer", "Years of Experience",
            "Will you require visa sponsorship?",
        ]
        print("=== Deterministic Field Mapping ===")
        for f in test_fields:
            val = filler.fill(f)
            print(f"  {f:35s} → '{val}'")

        print("\n=== Open Question Detection ===")
        questions = [
            "Why do you want to work here?",
            "Tell us about yourself",
            "What is your years of experience?",
        ]
        for q in questions:
            is_open = filler.is_open_question(q)
            print(f"  {'OPEN' if is_open else 'FIELD':6s} | {q}")

        print("\n=== GPT Answer (fallback) ===")
        ans = await filler.answer("Why do you want to work here?", "Software Engineer role at Acme")
        print(f"  {ans}")

    asyncio.run(main())
