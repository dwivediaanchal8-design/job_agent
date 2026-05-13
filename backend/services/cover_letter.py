"""
services/cover_letter.py — AI Cover Letter Generator (Phase 3)
==============================================================
Generates a personalized 3-paragraph cover letter per job using GPT-4o.
Caches letters in-memory per (user_id, job_url) to avoid duplicate API calls.

Usage:
    generator = CoverLetterGenerator()
    letter = await generator.generate(
        job_description="...",
        parsed_resume={...},
        company_name="Acme Corp",
        job_title="Software Engineer",
        user_id="uuid-string",     # for cache key
        job_url="https://..."       # for cache key
    )
"""

from __future__ import annotations

from typing import Optional
from loguru import logger


_COVER_LETTER_SYSTEM = """
You are a professional career coach helping a job applicant write a concise cover letter.
Write exactly 3 paragraphs:
  1. Opening: Express enthusiasm for the specific role and company. Mention the job title.
  2. Middle: Highlight 2-3 specific accomplishments from the candidate's background that
             directly match the job requirements. Be specific and quantified where possible.
  3. Closing: Reaffirm interest, mention willingness to discuss further, professional sign-off.

Style requirements:
- Professional but warm tone
- 150-250 words total
- No generic filler phrases like "I am writing to apply..."
- Do not mention AI or automation
- Address the letter to "Hiring Manager" unless a name is provided
- End with "Sincerely,\\n{name}"

Return ONLY the letter text. No subject line, no metadata.
"""

_COVER_LETTER_USER_TEMPLATE = """
Candidate Background:
Name: {name}
Skills: {skills}
Recent Experience: {experience}
Summary: {summary}

Job Details:
Company: {company}
Title: {job_title}
Description: {job_description}

Write the 3-paragraph cover letter now.
"""

_FALLBACK_TEMPLATE = """Dear Hiring Manager,

I am excited to apply for the {job_title} position at {company}. With {years} years of \
experience in {top_skills}, I am confident in my ability to make an immediate and meaningful \
contribution to your team.

Throughout my career, I have developed deep expertise in {skills_detail}. I thrive in \
collaborative environments and consistently deliver high-quality work. My background has \
prepared me well for the challenges and opportunities that this role presents.

I would welcome the opportunity to discuss how my skills and experience align with your \
team's goals. Thank you for your consideration — I look forward to speaking with you.

Sincerely,
{name}
"""


class CoverLetterGenerator:
    """
    Generates personalized cover letters for each job application.
    Uses GPT-4o with in-memory caching to avoid repeated API calls.
    """

    def __init__(self):
        self._client = None
        # Cache: (user_id, job_url) → letter_text
        self._cache: dict[tuple[str, str], str] = {}

    # ── Public API ─────────────────────────────────────────────────────────────

    async def generate(
        self,
        job_description: str,
        parsed_resume: dict,
        company_name: str = "",
        job_title: str = "",
        user_id: str = "",
        job_url: str = "",
    ) -> str:
        """
        Generate a personalized cover letter.

        Args:
            job_description: Full text of the job posting.
            parsed_resume:   Output of ResumeParser — the parsed_json dict.
            company_name:    Name of the hiring company.
            job_title:       Title of the job being applied for.
            user_id:         Used for cache key.
            job_url:         Used for cache key.

        Returns:
            Cover letter text (3 paragraphs, 150-250 words).
        """
        # Check cache
        cache_key = (user_id, job_url or company_name + job_title)
        if cache_key in self._cache:
            logger.debug(f"[CoverLetter] Cache hit for {company_name} — {job_title}")
            return self._cache[cache_key]

        # Check if cover letters are enabled
        if not self._is_enabled():
            return ""

        client = self._get_client()
        if client is None:
            letter = self._fallback_letter(parsed_resume, company_name, job_title)
        else:
            letter = await self._call_gpt(
                job_description, parsed_resume, company_name, job_title
            )

        self._cache[cache_key] = letter
        logger.info(
            f"[CoverLetter] Generated {len(letter)} char letter for "
            f"'{job_title}' at '{company_name}'"
        )
        return letter

    def clear_cache(self):
        """Clear the in-memory letter cache."""
        self._cache.clear()

    # ── GPT Generation ────────────────────────────────────────────────────────

    async def _call_gpt(
        self,
        job_description: str,
        parsed_resume: dict,
        company_name: str,
        job_title: str,
    ) -> str:
        """Call GPT-4o to generate the cover letter."""
        try:
            name = parsed_resume.get("name", "the candidate")
            skills = ", ".join(parsed_resume.get("skills", [])[:8])
            summary = parsed_resume.get("summary", "")[:300]

            # Build experience summary (latest 2 roles)
            exp_parts = []
            for e in parsed_resume.get("experience", [])[:2]:
                title = e.get("title", "")
                company = e.get("company", "")
                desc = e.get("description", "")[:150]
                exp_parts.append(f"{title} at {company}: {desc}")
            experience = ". ".join(exp_parts) or "See resume"

            user_prompt = _COVER_LETTER_USER_TEMPLATE.format(
                name=name,
                skills=skills,
                experience=experience,
                summary=summary,
                company=company_name or "the company",
                job_title=job_title or "the position",
                job_description=job_description[:2000],
            )

            system = _COVER_LETTER_SYSTEM.format(name=name)

            response = await self._client.chat.completions.create(
                model=self._model(),
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=500,
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"[CoverLetter] GPT call failed: {e}")
            return self._fallback_letter(parsed_resume, company_name, job_title)

    def _fallback_letter(
        self, parsed_resume: dict, company_name: str, job_title: str
    ) -> str:
        """Generate a template-based cover letter when GPT is unavailable."""
        name = parsed_resume.get("name", "Applicant")
        years = int(parsed_resume.get("total_years_experience", 0))
        skills = parsed_resume.get("skills", [])
        top_skills = ", ".join(skills[:3]) if skills else "software development"
        skills_detail = ", ".join(skills[:5]) if skills else "relevant technical skills"

        return _FALLBACK_TEMPLATE.format(
            job_title=job_title or "this position",
            company=company_name or "your organization",
            years=years,
            top_skills=top_skills,
            skills_detail=skills_detail,
            name=name,
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _is_enabled(self) -> bool:
        """Check if cover letter generation is enabled in config."""
        try:
            from backend.config import settings
            return getattr(settings, "cover_letter_enabled", True)
        except Exception:
            return True

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
        "skills": ["Python", "FastAPI", "React", "PostgreSQL", "Docker", "AWS"],
        "total_years_experience": 4.5,
        "summary": "Full-stack engineer with 4+ years building scalable web applications.",
        "experience": [
            {
                "title": "Software Engineer",
                "company": "Tech Corp",
                "description": "Built high-throughput REST APIs with FastAPI serving 1M+ daily users. Reduced deployment time by 40% using Docker and CI/CD pipelines.",
                "years": 2.5,
                "end_date": "Present",
            }
        ],
    }

    JD = """
    We are looking for a Software Engineer to join our backend team.
    You will build APIs, work with PostgreSQL, deploy on AWS, and collaborate
    with our frontend team on React-based features.
    Required: Python, REST APIs, SQL, cloud experience.
    """

    async def main():
        gen = CoverLetterGenerator()
        print("=== Generating cover letter (fallback mode) ===\n")
        letter = await gen.generate(
            job_description=JD,
            parsed_resume=SAMPLE_RESUME,
            company_name="Acme Corp",
            job_title="Software Engineer",
            user_id="test-user",
            job_url="https://acme.com/jobs/123",
        )
        print(letter)
        print(f"\n[{len(letter.split())} words]")

    asyncio.run(main())
