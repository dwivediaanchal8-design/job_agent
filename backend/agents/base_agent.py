"""
agents/base_agent.py — Abstract Base Class for all Job Portal Agents
======================================================================
Every portal agent (Indeed, Dice, LinkedIn) inherits from this class.

MENTOR NOTE:
  Why an abstract base class?
  → Enforces a consistent interface across all agents.
  → Shared logic (cookies, screenshots, error handling) lives here ONCE.
  → When you add a new portal, you just implement 3 methods: login, search_jobs, apply_job.

Design decisions:
  - Playwright with playwright-stealth: makes the browser look human to anti-bot systems
  - headless=False during development (so you can SEE what's happening)
  - All methods are async (Playwright's API is fully async)
  - Tenacity retry decorator on flaky actions (network hiccups, slow pages)
  - All errors are caught and logged — agents must NEVER crash the Celery worker
"""

import asyncio
import json
import os
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger
from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)
from playwright_stealth import Stealth
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from backend.config import settings


# ─── Data Classes ─────────────────────────────────────────────────────────────

class JobListing:
    """
    Represents a single job found during a search.
    Agents return a list of these from search_jobs().
    """

    def __init__(
        self,
        title: str,
        company: str,
        job_url: str,
        description: str = "",
        location: str = "",
        is_easy_apply: bool = False,
        portal: str = "",
    ):
        self.title = title
        self.company = company
        self.job_url = job_url
        self.description = description
        self.location = location
        self.is_easy_apply = is_easy_apply
        self.portal = portal

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "company": self.company,
            "job_url": self.job_url,
            "description": self.description,
            "location": self.location,
            "is_easy_apply": self.is_easy_apply,
            "portal": self.portal,
        }

    def __repr__(self) -> str:
        return f"<JobListing '{self.title}' @ {self.company}>"


class ApplicationResult:
    """
    Represents the result of a single application attempt.
    Agents return this from apply_job().
    The Celery task saves this to the applications table.
    """

    def __init__(
        self,
        job: JobListing,
        status: str,  # 'applied' | 'failed' | 'skipped'
        failure_reason: str = "",
        match_score: Optional[float] = None,
    ):
        self.job = job
        self.status = status
        self.failure_reason = failure_reason
        self.match_score = match_score
        self.applied_at = datetime.utcnow()

    def to_dict(self) -> dict:
        return {
            **self.job.to_dict(),
            "status": self.status,
            "failure_reason": self.failure_reason,
            "match_score": self.match_score,
            "applied_at": self.applied_at.isoformat(),
        }

    def __repr__(self) -> str:
        return f"<ApplicationResult job='{self.job.title}' status={self.status}>"


# ─── Base Agent ───────────────────────────────────────────────────────────────

class BaseAgent(ABC):
    """
    Abstract base class for all job portal agents.

    Subclasses MUST implement:
        - login(username, password)
        - search_jobs(keywords, location)
        - apply_job(job, user_data)

    Shared behavior provided here:
        - launch() / close() — browser lifecycle
        - save_cookies() / load_cookies() — session persistence
        - _safe_click() / _safe_type() / _safe_fill() — reliable page interactions
        - _screenshot() — debug screenshots on errors
        - _wait_for_page_load() — smart page load waiting
    """

    # Class-level portal name — subclasses override this
    PORTAL_NAME: str = "base"

    # Screenshots directory
    SCREENSHOTS_DIR: Path = Path("./screenshots")

    def __init__(self, user_id: str, headless: bool = True):
        """
        Args:
            user_id: The UUID of the job-seeker this agent is running for.
                     Used for logging and cookie file naming.
            headless: Run browser hidden (True for production, False for debugging).
        """
        self.user_id = user_id
        self.headless = headless

        # Playwright instances — set by launch()
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

        # Cookie file path: cookies/<user_id>/<portal>.json
        self._cookies_dir = Path("./cookies") / str(user_id)
        self._cookies_file = self._cookies_dir / f"{self.PORTAL_NAME}.json"

        # Ensure directories exist
        self._cookies_dir.mkdir(parents=True, exist_ok=True)
        self.SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"[{self.PORTAL_NAME}] Agent initialized for user={user_id} "
            f"headless={headless}"
        )

    # ─── Browser Lifecycle ────────────────────────────────────────────────────

    async def launch(self) -> None:
        """
        Starts Playwright + a Chromium browser with stealth mode.

        MENTOR NOTE on Stealth:
          Without playwright-stealth, sites detect automation via:
          - navigator.webdriver = true
          - Missing browser plugins
          - Inconsistent screen dimensions
          Stealth patches all of these to make the browser look human.
        """
        logger.info(f"[{self.PORTAL_NAME}] Launching browser...")

        self._playwright = await async_playwright().start()

        # Launch Chromium browser
        # args: disable automation flags that sites detect
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--window-size=1920,1080",
            ],
        )

        # Create a context (like an incognito window) with realistic settings
        self._context = await self._browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="en-US",
            timezone_id="America/New_York",
        )

        # Open the main page and apply stealth patches
        self._page = await self._context.new_page()
        await Stealth().apply_stealth_async(self._page)

        logger.success(f"[{self.PORTAL_NAME}] Browser launched successfully.")

    async def close(self) -> None:
        """
        Gracefully shuts down the browser and Playwright.
        Always call this when done — prevents zombie browser processes.
        """
        logger.info(f"[{self.PORTAL_NAME}] Closing browser...")

        try:
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception as e:
            logger.warning(f"[{self.PORTAL_NAME}] Error during browser close: {e}")

        logger.info(f"[{self.PORTAL_NAME}] Browser closed.")

    # ─── Cookie Persistence ───────────────────────────────────────────────────

    async def save_cookies(self) -> None:
        """
        Saves browser cookies to a JSON file.
        On next run, load_cookies() restores them → skips login page.

        MENTOR NOTE:
          Cookies contain the session token. By saving them, the agent
          appears to the portal as a user who is already logged in.
          This reduces login attempts (which portals monitor for bots).
        """
        if not self._context:
            logger.warning(f"[{self.PORTAL_NAME}] No context to save cookies from.")
            return

        cookies = await self._context.cookies()
        with open(self._cookies_file, "w") as f:
            json.dump(cookies, f, indent=2)

        logger.info(
            f"[{self.PORTAL_NAME}] Saved {len(cookies)} cookies → {self._cookies_file}"
        )

    async def load_cookies(self) -> bool:
        """
        Loads cookies from file and injects them into the browser context.

        Returns:
            True if cookies were loaded, False if no cookie file exists.
        """
        if not self._cookies_file.exists():
            logger.info(f"[{self.PORTAL_NAME}] No saved cookies found. Will login fresh.")
            return False

        if not self._context:
            logger.warning(f"[{self.PORTAL_NAME}] No context to load cookies into.")
            return False

        try:
            with open(self._cookies_file, "r") as f:
                cookies = json.load(f)

            await self._context.add_cookies(cookies)
            logger.success(
                f"[{self.PORTAL_NAME}] Loaded {len(cookies)} cookies from file."
            )
            return True

        except Exception as e:
            logger.warning(f"[{self.PORTAL_NAME}] Failed to load cookies: {e}")
            return False

    def clear_cookies(self) -> None:
        """Deletes saved cookies. Call when login fails with saved cookies."""
        if self._cookies_file.exists():
            self._cookies_file.unlink()
            logger.info(f"[{self.PORTAL_NAME}] Cleared stale cookies.")

    # ─── Abstract Methods — Subclasses MUST implement these ───────────────────

    @abstractmethod
    async def login(self, username: str, password: str) -> bool:
        """
        Log into the job portal.

        Args:
            username: Plain-text username/email (decrypted from DB).
            password: Plain-text password (decrypted from DB).

        Returns:
            True if login succeeded, False if it failed.
        """
        ...

    @abstractmethod
    async def search_jobs(
        self,
        keywords: list[str],
        location: str,
        max_results: int = 25,
    ) -> list[JobListing]:
        """
        Search for jobs on the portal.

        Args:
            keywords: Job title keywords e.g. ["Python Developer", "Backend Engineer"]
            location: Location string e.g. "Remote" or "New York, NY"
            max_results: Max number of job listings to return.

        Returns:
            List of JobListing objects found.
        """
        ...

    @abstractmethod
    async def apply_job(
        self,
        job: JobListing,
        user_data: dict,
        dry_run: bool = False,
    ) -> ApplicationResult:
        """
        Apply to a single job listing.

        Args:
            job: The JobListing to apply to.
            user_data: Dict with user's resume data, name, email, phone, etc.
            dry_run: If True, go through all steps but don't click final submit.
                     Use for testing without actually applying.

        Returns:
            ApplicationResult with status 'applied', 'failed', or 'skipped'.
        """
        ...

    # ─── Safe Page Interaction Helpers ────────────────────────────────────────

    async def _safe_click(self, selector: str, timeout: int = 10000) -> bool:
        """
        Click an element safely.
        Waits for it to be visible before clicking.
        Returns False instead of crashing if element not found.

        Args:
            selector: CSS or text selector.
            timeout: Max wait in milliseconds.
        """
        try:
            await self._page.wait_for_selector(selector, timeout=timeout, state="visible")
            await self._page.click(selector)
            return True
        except Exception as e:
            logger.warning(f"[{self.PORTAL_NAME}] _safe_click failed for '{selector}': {e}")
            return False

    async def _safe_fill(self, selector: str, value: str, timeout: int = 10000) -> bool:
        """
        Fill a form field safely.
        Clears the field first, then types the value.

        Args:
            selector: CSS or text selector for the input field.
            value: The text to type.
            timeout: Max wait in milliseconds.
        """
        try:
            await self._page.wait_for_selector(selector, timeout=timeout, state="visible")
            await self._page.fill(selector, "")   # Clear first
            await self._page.fill(selector, value)
            return True
        except Exception as e:
            logger.warning(f"[{self.PORTAL_NAME}] _safe_fill failed for '{selector}': {e}")
            return False

    async def _safe_type(
        self, selector: str, value: str, delay: int = 50, timeout: int = 10000
    ) -> bool:
        """
        Type into a field character by character (more human-like than fill).
        Use for login forms where rapid fill() might trigger bot detection.

        Args:
            delay: Milliseconds between keystrokes (default 50ms looks human).
        """
        try:
            await self._page.wait_for_selector(selector, timeout=timeout, state="visible")
            await self._page.click(selector)
            await self._page.type(selector, value, delay=delay)
            return True
        except Exception as e:
            logger.warning(f"[{self.PORTAL_NAME}] _safe_type failed for '{selector}': {e}")
            return False

    async def _smart_fill_form(self, user_data: dict) -> int:
        """
        Phase 3: Intelligent form filling using FormFiller.
        Iterates over all visible inputs/selects on the current page,
        extracts their labels, and fills them with AI-mapped data.

        Returns:
            Number of fields successfully filled.
        """
        filler = user_data.get("form_filler")
        if not filler:
            logger.warning(f"[{self.PORTAL_NAME}] No FormFiller in user_data")
            return 0

        filled_count = 0
        fields = await self._get_form_fields()

        for field in fields:
            label = await self._extract_label(field)
            if not label:
                continue

            # ── 1. Check if it's an open-ended question (GPT needed) ──
            if filler.is_open_question(label):
                # Only fill if empty
                val = await field.input_value()
                if not val:
                    self._log_action("_smart_fill_form", f"🤖 Answering open Q: '{label[:40]}...'")
                    jd = user_data.get("job_description", "")
                    ans = await filler.answer(label, jd)
                    await field.fill(ans)
                    filled_count += 1
                    await self._human_delay(500, 1000)
                continue

            # ── 2. Check if it's a standard field ──
            value = filler.fill(label)
            if value:
                # Check current value
                curr = await field.input_value()
                if not curr:
                    self._log_action("_smart_fill_form", f"✨ Filling field: '{label}' → '{value}'")
                    # Handle selects differently
                    tag = await field.evaluate("el => el.tagName.toLowerCase()")
                    if tag == "select":
                        await field.select_option(label=value)
                    else:
                        await field.fill(value)
                    filled_count += 1
                    await self._human_delay(300, 600)

        return filled_count

    async def _get_form_fields(self):
        """Finds all interactive form fields on the page."""
        return await self._page.query_selector_all(
            "input:not([type='hidden']):not([type='submit']):not([type='checkbox']):not([type='radio']), "
            "select, textarea"
        )

    async def _extract_label(self, element) -> str:
        """
        Tries multiple strategies to find a text label for an input element.
        """
        try:
            # 1. aria-label
            label = await element.get_attribute("aria-label")
            if label: return label.strip()

            # 2. placeholder
            label = await element.get_attribute("placeholder")
            if label: return label.strip()

            # 3. <label> tag with 'for' attribute
            elem_id = await element.get_attribute("id")
            if elem_id:
                label_el = await self._page.query_selector(f"label[for='{elem_id}']")
                if label_el:
                    text = await label_el.inner_text()
                    if text: return text.strip()

            # 4. Parent <label> wrapper
            label_text = await element.evaluate("""el => {
                let parent = el.closest('label');
                if (parent) return parent.innerText;
                return '';
            }""")
            if label_text: return label_text.strip()

            # 5. Preceding sibling or nearby text (common in custom forms)
            nearby_text = await element.evaluate("""el => {
                let prev = el.previousElementSibling;
                if (prev && prev.innerText) return prev.innerText;
                let parent = el.parentElement;
                if (parent && parent.innerText) {
                    // Filter out the element's own text if it's a select/textarea
                    return parent.innerText.split('\\n')[0];
                }
                return '';
            }""")
            return nearby_text.strip()

        except Exception:
            return ""

    async def _wait_for_page_load(self, timeout: int = 30000) -> None:
        """
        Waits for network to be idle (no pending requests).
        Better than fixed sleep() — adapts to actual page load time.
        """
        try:
            await self._page.wait_for_load_state("networkidle", timeout=timeout)
        except Exception:
            # If networkidle times out, at least wait for domcontentloaded
            try:
                await self._page.wait_for_load_state("domcontentloaded", timeout=5000)
            except Exception:
                pass

    async def _human_delay(self, min_ms: int = 500, max_ms: int = 1500) -> None:
        """
        Wait a random amount of time between actions.
        Makes the agent's behavior look more human.

        MENTOR NOTE:
          Always randomize delays. Fixed delays like time.sleep(1) are
          a red flag for anti-bot systems that analyze timing patterns.
        """
        import random
        delay = random.randint(min_ms, max_ms) / 1000
        await asyncio.sleep(delay)

    # ─── Debug Helpers ────────────────────────────────────────────────────────

    async def _screenshot(self, name: str) -> str:
        """
        Takes a screenshot for debugging.
        Saved to ./screenshots/<portal>_<name>_<timestamp>.png

        Returns the file path of the saved screenshot.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = self.SCREENSHOTS_DIR / f"{self.PORTAL_NAME}_{name}_{timestamp}.png"

        try:
            await self._page.screenshot(path=str(filename), full_page=True)
            logger.debug(f"[{self.PORTAL_NAME}] Screenshot saved: {filename}")
        except Exception as e:
            logger.warning(f"[{self.PORTAL_NAME}] Screenshot failed: {e}")

        return str(filename)

    async def _get_page_text(self) -> str:
        """Returns all visible text on the current page (for AI analysis)."""
        try:
            return await self._page.inner_text("body")
        except Exception:
            return ""

    def _log_action(self, action: str, detail: str = "") -> None:
        """Standardized log format: [portal] [user_id] action — detail"""
        logger.info(
            f"[{self.PORTAL_NAME}] [user={self.user_id[:8]}...] {action}"
            + (f" — {detail}" if detail else "")
        )

    # ─── Context Manager Support ──────────────────────────────────────────────
    # Allows using: async with IndeedAgent(user_id) as agent:
    #                   await agent.search_jobs(...)

    async def __aenter__(self):
        await self.launch()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
