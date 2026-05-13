
import asyncio
import sys

# Set encoding to utf-8 for windows console
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from backend.services.job_matcher import JobMatcher

async def test_job_matching():
    resume = {
        "name": "Aanchal Dwivedi",
        "skills": ["Python", "NumPy", "Pandas", "Matplotlib", "SQL", "PyCharm", "Jupyter Notebook"],
        "total_years_experience": 0,
        "summary": "Enthusiastic B.Tech student with knowledge in Python and data analysis."
    }
    
    samples = [
        {
            "title": "Python Developer Intern",
            "desc": "Looking for a Python intern familiar with NumPy, Pandas and SQL. Knowledge of data visualization is a plus."
        },
        {
            "title": "Data Analyst Trainee",
            "desc": "Entry level data analyst role. Must know Python, Matplotlib and be able to work with large datasets using Pandas."
        },
        {
            "title": "Senior Java Developer",
            "desc": "10+ years experience in Java, Spring Boot, Microservices. Experience with AWS and Kubernetes required."
        },
        {
            "title": "Marketing Manager",
            "desc": "Lead our marketing team. Experience in SEO, SEM and social media campaigns required."
        },
        {
            "title": "Backend Intern (Python/Django)",
            "desc": "Build APIs using Python and Django. SQL knowledge is required."
        }
    ]
    
    matcher = JobMatcher(threshold=60)
    print(f"--- Job Matching Test (Threshold: 60) ---")
    
    for i, job in enumerate(samples, 1):
        result = await matcher.score(job['desc'], resume)
        status = "APPLY" if result.should_apply else "SKIP"
        print(f"Sample {i}: {job['title']}")
        print(f"  Score: {result.score}/100")
        print(f"  Decision: {status}")
        print(f"  Method: {result.method}")
        print("-" * 30)

if __name__ == "__main__":
    asyncio.run(test_job_matching())
