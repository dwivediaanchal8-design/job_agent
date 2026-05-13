
import asyncio
import os
import json
from backend.services.resume_parser import ResumeParser

async def test_real_resume():
    resume_path = "Aanchal_Resume.docx"
    if not os.path.exists(resume_path):
        print(f"File {resume_path} not found!")
        return

    print(f"--- Parsing {resume_path} ---")
    parser = ResumeParser()
    raw_text, parsed_json = await parser.parse(resume_path, "docx")
    
    print("\n--- Parsed JSON ---")
    print(json.dumps(parsed_json, indent=2))
    
    print("\n--- Verification ---")
    print(f"Name: {parsed_json.get('name')}")
    print(f"Email: {parsed_json.get('email')}")
    print(f"Skills Count: {len(parsed_json.get('skills', []))}")
    print(f"Experience Count: {len(parsed_json.get('experience', []))}")
    print(f"Total Years: {parsed_json.get('total_years_experience')}")

if __name__ == "__main__":
    asyncio.run(test_real_resume())
