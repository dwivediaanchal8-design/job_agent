"""
services/job_matcher.py — AI Job Scorer (Phase 3)
==================================================
Scores a job posting against a user's parsed resume using:
  1. OpenAI text-embedding-3-small → cosine similarity (primary)
  2. Keyword overlap fallback (when OpenAI is unavailable)

Usage:
    matcher = JobMatcher()
    result = await matcher.score(job_description, parsed_resume)
    if result.should_apply:
        # proceed with application
        print(result.score, result.match_reasons)
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Optional
from loguru import logger


# ─── Result Dataclass ─────────────────────────────────────────────────────────

@dataclass
class JobMatchResult:
    """
    Result of scoring a job against a user's resume.

    Attributes:
        score           0–100 match score
        match_reasons   List of reasons why this is a good match
        missing_skills  Skills in the JD that the user lacks
        should_apply    True if score >= threshold
        method          'embedding' or 'keyword' (which scoring method was used)
    """
    score: int
    match_reasons: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    should_apply: bool = False
    method: str = "keyword"

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "match_reasons": self.match_reasons,
            "missing_skills": self.missing_skills,
            "should_apply": self.should_apply,
            "method": self.method,
        }


# ─── Job Matcher ─────────────────────────────────────────────────────────────

class JobMatcher:
    """
    Scores job postings against a user's parsed resume.
    Uses OpenAI embeddings for semantic similarity; falls back to keyword overlap.
    """

    def __init__(self, threshold: Optional[int] = None):
        """
        Args:
            threshold: Minimum score to set should_apply=True.
                       Defaults to settings.job_match_threshold (70).
        """
        self._threshold = threshold
        self._client = None

    # ── Public API ─────────────────────────────────────────────────────────────

    async def score(self, job_description: str, parsed_resume: dict) -> JobMatchResult:
        """
        Score a job description against a parsed resume.

        Args:
            job_description: Full text of the job posting.
            parsed_resume:   Output of ResumeParser.parse() — the parsed_json dict.

        Returns:
            JobMatchResult with score, reasons, and should_apply flag.
        """
        if not job_description or not parsed_resume:
            return JobMatchResult(score=0, should_apply=False)

        threshold = self._get_threshold()

        # Try embedding-based scoring first
        client = self._get_client()
        if client:
            result = await self._embedding_score(job_description, parsed_resume, client)
        else:
            result = self._keyword_score(job_description, parsed_resume)

        result.should_apply = result.score >= threshold
        logger.info(
            f"[JobMatcher] Score={result.score}/100 method={result.method} "
            f"should_apply={result.should_apply} threshold={threshold}"
        )
        return result

    # ── Embedding-Based Scoring ────────────────────────────────────────────────

    async def _embedding_score(
        self, job_description: str, parsed_resume: dict, client
    ) -> JobMatchResult:
        """
        Use OpenAI text-embedding-3-small to embed both texts,
        then compute cosine similarity scaled to 0–100.
        """
        try:
            from backend.services.openai_client import get_embedding_model
            embedding_model = get_embedding_model()

            # Build candidate text from resume
            candidate_text = self._build_candidate_text(parsed_resume)

            # Embed both in one batch call (efficient)
            response = await client.embeddings.create(
                model=embedding_model,
                input=[candidate_text, job_description[:8000]],
            )
            vec_candidate = response.data[0].embedding
            vec_job = response.data[1].embedding

            similarity = self._cosine_similarity(vec_candidate, vec_job)
            # similarity is -1 to 1; normalize to 0-100
            score = int(max(0, min(100, (similarity + 1) / 2 * 100)))

            # Also run keyword analysis for match_reasons + missing_skills
            keyword_result = self._keyword_score(job_description, parsed_resume)

            return JobMatchResult(
                score=score,
                match_reasons=keyword_result.match_reasons,
                missing_skills=keyword_result.missing_skills,
                method="embedding",
            )

        except Exception as e:
            logger.warning(f"[JobMatcher] Embedding failed: {e} — falling back to keyword")
            return self._keyword_score(job_description, parsed_resume)

    def _cosine_similarity(self, vec_a: list[float], vec_b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        mag_a = math.sqrt(sum(a * a for a in vec_a))
        mag_b = math.sqrt(sum(b * b for b in vec_b))
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)

    def _build_candidate_text(self, parsed_resume: dict) -> str:
        """Build a single text string from the resume for embedding."""
        parts = []
        if parsed_resume.get("summary"):
            parts.append(parsed_resume["summary"])
        if parsed_resume.get("skills"):
            parts.append("Skills: " + ", ".join(parsed_resume["skills"]))
        for exp in parsed_resume.get("experience", []):
            title = exp.get("title", "")
            company = exp.get("company", "")
            desc = exp.get("description", "")
            parts.append(f"{title} at {company}. {desc}")
        return "\n".join(parts)[:8000]

    # ── Keyword-Based Scoring ─────────────────────────────────────────────────

    def _keyword_score(self, job_description: str, parsed_resume: dict) -> JobMatchResult:
        """
        Score based on skill keyword overlap between JD and resume.
        This is fast, free, and works without OpenAI.

        Scoring formula:
            base = matched_skills / max(required_skills, 1) * 100
            bonus = min(20, years_experience / max_expected * 20)
            score = min(100, base * 0.8 + bonus * 0.2)
        """
        jd_lower = job_description.lower()
        resume_skills = [s.lower() for s in parsed_resume.get("skills", [])]
        years_exp = parsed_resume.get("total_years_experience", 0)

        # Extract skills mentioned in JD (from resume skill list)
        matched = [s for s in resume_skills if s in jd_lower]

        # Look for skills in JD that user doesn't have
        jd_words = set(re.findall(r"\b[a-z][a-z\+\#\.]{2,}\b", jd_lower))
        common_tech = {
            "python", "java", "javascript", "typescript", "react", "node", "sql",
            "aws", "docker", "kubernetes", "git", "django", "flask", "fastapi",
            "tensorflow", "pytorch", "machine learning", "deep learning", "nlp",
            "rest", "graphql", "mongodb", "postgresql", "redis", "celery",
            "html", "css", "vue", "angular", "spring", "golang", "rust", "c++",
            "azure", "gcp", "linux", "bash", "ci/cd", "agile", "scrum",
        }
        jd_tech = jd_words & common_tech
        missing = list(jd_tech - set(resume_skills))[:10]

        # Score calculation
        if resume_skills:
            match_ratio = len(matched) / max(len(jd_tech & set(resume_skills)) + len(jd_tech), 1)
            base_score = min(100, int(len(matched) / max(len(jd_tech), 1) * 100))
        else:
            base_score = 30  # No skills in resume = 30/100

        # Experience bonus (up to +20)
        exp_bonus = min(20, int(years_exp / 10 * 20))
        final_score = min(100, base_score + exp_bonus)

        # Build match reasons
        reasons = []
        if matched:
            reasons.append(f"Matched skills: {', '.join(matched[:5])}")
        if years_exp >= 1:
            reasons.append(f"{years_exp} years of relevant experience")
        if not reasons:
            reasons.append("Partial keyword match with job description")

        return JobMatchResult(
            score=final_score,
            match_reasons=reasons,
            missing_skills=missing,
            method="keyword",
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_client(self):
        """Get shared OpenAI/OpenRouter client."""
        if self._client:
            return self._client
        from backend.services.openai_client import get_client
        self._client = get_client()
        return self._client

    def _get_threshold(self) -> int:
        if self._threshold is not None:
            return self._threshold
        try:
            from backend.config import settings
            return settings.job_match_threshold
        except Exception:
            return 70


if __name__ == "__main__":
    import asyncio, json

    SAMPLE_RESUME = {
        "name": "Jane Doe",
        "skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "React", "AWS"],
        "total_years_experience": 4.5,
        "summary": "Full-stack software engineer with 4+ years building scalable web applications.",
        "experience": [
            {
                "title": "Software Engineer",
                "company": "Tech Corp",
                "description": "Built REST APIs with FastAPI and deployed on AWS EC2 using Docker.",
                "years": 2.5,
            }
        ],
    }

    SAMPLE_JOBS = [
        ("Strong match", "We need a Python developer with FastAPI, PostgreSQL, Docker, and AWS experience. React is a plus."),
        ("Weak match", "We're looking for a Java Spring Boot developer with Oracle database experience and .NET skills."),
        ("Partial match", "Full stack role: Python or Node.js, SQL database, and some cloud experience required."),
    ]

    async def main():
        matcher = JobMatcher(threshold=70)
        for label, jd in SAMPLE_JOBS:
            result = await matcher.score(jd, SAMPLE_RESUME)
            icon = "✅" if result.should_apply else "❌"
            print(f"\n{icon} [{label}] Score={result.score}/100 method={result.method}")
            print(f"   Match: {', '.join(result.match_reasons[:2])}")
            if result.missing_skills:
                print(f"   Missing: {', '.join(result.missing_skills[:3])}")

    asyncio.run(main())
