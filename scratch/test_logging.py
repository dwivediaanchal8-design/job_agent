
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.config import settings
from loguru import logger

# Ensure log directory exists
os.makedirs(os.path.dirname(settings.log_file), exist_ok=True)

# Re-configure to match main.py
logger.remove()
logger.add(sys.stdout, level="INFO")
logger.add(settings.log_file, rotation="10 MB", level="DEBUG")

def test_logging():
    logger.info("PHASE 4 TEST: Logging system is active.")
    logger.debug("PHASE 4 TEST: Debug details are being recorded.")
    print(f"Log written to: {settings.log_file}")

if __name__ == "__main__":
    test_logging()
