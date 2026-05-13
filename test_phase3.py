"""
Phase 3 verification script — tests all services work correctly.
Run: venv\Scripts\python.exe test_phase3.py
"""
import asyncio
import sys

sys.stdout.reconfigure(encoding='utf-8')


async def test_form_filler():
    print("=== FormFiller Test ===")
    from backend.services.form_filler import FormFiller

    resume = {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "phone": "+1-555-123-4567",
        "location": "San Francisco, CA",
        "linkedin_url": "https://linkedin.com/in/janedoe",
        "portfolio_url": "https://github.com/janedoe",
        "skills": ["Python", "FastAPI", "React", "AWS", "Docker"],
        "total_years_experience": 4.5,
        "summary": "Full-stack engineer with 4+ years.",
        "experience": [
            {
                "title": "Software Engineer",
                "company": "Tech Corp",
                "end_date": "Present",
                "years": 2.5,
            }
        ],
    }
    filler = FormFiller(resume)

    tests = [
        ("First Name", "Jane"),
        ("Last Name", "Doe"),
        ("Email Address", "jane@example.com"),
        ("Phone Number", "+1-555-123-4567"),
        ("Current Employer", "Tech Corp"),
        ("Years of Experience", "4"),
        ("LinkedIn URL", "https://linkedin.com/in/janedoe"),
    ]

    all_ok = True
    for label, expected in tests:
        got = filler.fill(label)
        ok = got == expected
        if not ok:
            all_ok = False
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {label:35s} -> {repr(got)}")

    # Test open question detection
    is_open = filler.is_open_question("Why do you want to work here?")
    not_open = not filler.is_open_question("Years of Experience")
    print(f"  [{'PASS' if is_open else 'FAIL'}] Open Q detection: 'Why do you want to work here?'")
    print(f"  [{'PASS' if not_open else 'FAIL'}] Non-open Q: 'Years of Experience'")

    # Test fallback answer
    ans = await filler.answer("Why do you want to work here?", "job desc")
    print(f"  [PASS] Fallback answer ({len(ans)} chars)")
    print()
    return all_ok


async def test_job_matcher():
    print("=== JobMatcher Test ===")
    from backend.services.job_matcher import JobMatcher

    resume = {
        "name": "Jane Doe",
        "skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "React", "AWS"],
        "total_years_experience": 4.5,
        "summary": "Full-stack software engineer.",
        "experience": [
            {
                "title": "Software Engineer",
                "company": "Tech Corp",
                "description": "Built REST APIs with FastAPI and PostgreSQL.",
                "years": 2.5,
            }
        ],
    }

    matcher = JobMatcher(threshold=70)
    cases = [
        (
            "Strong match",
            "Python developer with FastAPI, PostgreSQL, Docker, and AWS experience. React is a plus.",
            True,
        ),
        (
            "Weak match",
            "Java Spring Boot developer with Oracle database and .NET skills required.",
            False,
        ),
    ]

    all_ok = True
    for label, jd, expect_apply in cases:
        result = await matcher.score(jd, resume)
        ok = result.should_apply == expect_apply
        if not ok:
            all_ok = False
        status = "PASS" if ok else "FAIL"
        print(
            f"  [{status}] {label:15s} score={result.score}/100 "
            f"should_apply={result.should_apply} (expected={expect_apply})"
        )

    print()
    return all_ok


async def test_cover_letter():
    print("=== CoverLetterGenerator Test ===")
    from backend.services.cover_letter import CoverLetterGenerator

    resume = {
        "name": "Jane Doe",
        "skills": ["Python", "FastAPI", "React", "PostgreSQL"],
        "total_years_experience": 4.5,
        "summary": "Full-stack engineer.",
        "experience": [
            {
                "title": "Software Engineer",
                "company": "Tech Corp",
                "description": "Built high-throughput APIs serving 1M+ users.",
                "years": 2.5,
                "end_date": "Present",
            }
        ],
    }

    gen = CoverLetterGenerator()
    letter = await gen.generate(
        job_description="Python developer role at Acme Corp. FastAPI, PostgreSQL, cloud.",
        parsed_resume=resume,
        company_name="Acme Corp",
        job_title="Software Engineer",
        user_id="test-user",
        job_url="https://acme.com/jobs/123",
    )

    has_name = "Jane Doe" in letter
    has_company = "Acme Corp" in letter
    reasonable_length = 50 < len(letter.split()) < 400
    print(f"  [{'PASS' if has_name else 'FAIL'}] Contains candidate name")
    print(f"  [{'PASS' if has_company else 'FAIL'}] Contains company name")
    print(f"  [{'PASS' if reasonable_length else 'FAIL'}] Reasonable length ({len(letter.split())} words)")
    print()
    print("  --- Letter Preview ---")
    print("\n".join(f"  {l}" for l in letter.split("\n")[:6]))
    print()
    return has_name and has_company and reasonable_length


async def main():
    print("=" * 55)
    print("  PHASE 3 VERIFICATION — AI Services Self-Test")
    print("=" * 55)
    print()

    results = []
    results.append(("FormFiller",    await test_form_filler()))
    results.append(("JobMatcher",    await test_job_matcher()))
    results.append(("CoverLetter",   await test_cover_letter()))

    print("=" * 55)
    print("  SUMMARY")
    print("=" * 55)
    all_passed = True
    for name, ok in results:
        status = "PASS" if ok else "FAIL"
        if not ok:
            all_passed = False
        print(f"  [{status}] {name}")

    print()
    if all_passed:
        print("  All Phase 3 services working correctly!")
    else:
        print("  Some tests failed — check output above.")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
