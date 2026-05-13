"""
agents/__init__.py — Agent Package
====================================
Exports all portal agents and shared data classes.
"""

from backend.agents.base_agent import BaseAgent, JobListing, ApplicationResult
from backend.agents.indeed_agent import IndeedAgent
from backend.agents.dice_agent import DiceAgent
from backend.agents.linkedin_agent import LinkedInAgent

__all__ = [
    "BaseAgent",
    "JobListing",
    "ApplicationResult",
    "IndeedAgent",
    "DiceAgent",
    "LinkedInAgent",
]
