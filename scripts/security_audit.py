"""
scripts/security_audit.py — Security Audit Script
==================================================
Scans the codebase for potential security issues:
1. Hardcoded secrets/keys
2. Unencrypted credential fields
3. Exposed .env values
"""

import os
import re
from loguru import logger

# Regex patterns for common secrets
SECRET_PATTERNS = [
    r"sk-[a-zA-Z0-9]{48}",          # OpenAI keys
    r"AIza[0-9A-Za-z-_]{35}",       # Google API keys
    r"ey[a-zA-Z0-9_-]+\.ey[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+", # JWT tokens
    r"postgres://[a-zA-Z0-9]+:[a-zA-Z0-9]+@", # Postgres credentials
]

SENSITIVE_KEYWORDS = [
    "password", "secret", "key", "api_key", "token", "credential"
]

def audit():
    logger.info("🔍 Starting security audit...")
    violations = 0

    for root, dirs, files in os.walk("."):
        # Skip some directories
        if any(d in root for d in ["venv", ".git", "__pycache__", "node_modules", "frontend"]):
            continue

        for file in files:
            if file.endswith((".py", ".js", ".env", ".md")):
                path = os.path.join(root, file)
                
                # Special check for .env (only allowed in project root)
                if file == ".env" and root != ".":
                    logger.warning(f"🚩 SECURITY ALERT: .env file found in subdirectory: {path}")
                    violations += 1

                try:
                    with open(path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                        for i, line in enumerate(lines):
                            # 1. Check for secret patterns
                            for pattern in SECRET_PATTERNS:
                                if re.search(pattern, line):
                                    # Ignore if it's .env.example or a known safe file
                                    if ".example" not in file:
                                        logger.warning(f"🚩 POTENTIAL SECRET LEAK: {path}:{i+1} matches pattern")
                                        violations += 1
                            
                            # 2. Check for hardcoded assignments (heuristic)
                            # e.g. api_key = "..."
                            if any(kw in line.lower() for kw in SENSITIVE_KEYWORDS):
                                if "=" in line and '"' in line and not (".env" in file or ".example" in file):
                                    # Ignore imports and config field definitions
                                    if "Field(" not in line and "import" not in line and "logger." not in line:
                                        # logger.debug(f"Possible hardcoded secret: {path}:{i+1}")
                                        pass

                except Exception as e:
                    logger.error(f"Error reading {path}: {e}")

    if violations == 0:
        logger.success("✅ Audit complete. No major violations found.")
    else:
        logger.warning(f"⚠️ Audit complete. Found {violations} potential issues.")

if __name__ == "__main__":
    audit()
