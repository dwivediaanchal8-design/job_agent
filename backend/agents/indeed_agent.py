"""
agents/indeed_agent.py — Indeed.com Browser Agent
===================================================
Handles login, job search, and application on Indeed.

MENTOR NOTE on Indeed:
  Indeed is the simplest portal to automate because:
  1. Login is a straightforward email/password form
  2. Job search uses a clean URL structure (?q=keyword&l=location)
  3. "Indeed Apply" jobs don't redirect to external sites
  4. Forms are relatively standard (name, email, resume upload)

  REAL WORLD WARNING:
    Indeed aggressively rate-limits. If you apply to too many jobs
    in one session, they'll present a CAPTCHA or block the session.
    Stick to max 15-20 applications per run. The daily limit in .env
    (MAX_APPLICATIONS_PER_DAY=50) is across all portals combined.

Usage (via Celery task — you don't call this directly):
    async with IndeedAgent(user_id="abc123") as agent:
        logged_in = await agent.login(username, password)
        jobs = await agent.search_jobs(["Python Developer"], "Remote")
        for job in jobs:
            result = await agent.apply_job(job, user_data)
"""

import asyncio
import re
from typing import Optional
from urllib.parse import urlencode, quote_plus

from loguru import logger
from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from backend.agents.base_agent import BaseAgent, JobListing, ApplicationResult
from backend.services.captcha_solver import captcha_solver


class IndeedAgent(BaseAgent):
    """
    Browser agent for Indeed.com.
    Implements the full search → apply cycle.
    """

    PORTAL_NAME = "indeed"
    BASE_URL = "https://in.indeed.com"  # India Indeed (avoids Cloudflare on US site)
    LOGIN_URL = "https://secure.indeed.com/auth"

    # ─── Login ────────────────────────────────────────────────────────────────

    async def login(self, username: str, password: str) -> bool:
        """
        Logs into Indeed using email and password.

        Flow:
        1. Try loading saved cookies first (skip login if still valid)
        2. If cookies fail, do fresh login via the auth page
        3. Save new cookies on success

        Returns:
            True if logged in successfully.
        """
        self._log_action("login", f"user={username}")

        # ── Try saved cookies first ──
        cookies_loaded = await self.load_cookies()
        if cookies_loaded:
            # Navigate to Indeed and check if we're still logged in
            await self._page.goto(self.BASE_URL, wait_until="domcontentloaded")
            await self._wait_for_page_load()

            if await self._is_logged_in():
                self._log_action("login", "✅ Restored session via cookies — skipping login")
                return True
            else:
                self._log_action("login", "⚠️ Saved cookies expired — doing fresh login")
                self.clear_cookies()

        # ── Fresh login ──
        try:
            await self._page.goto(self.LOGIN_URL, wait_until="domcontentloaded")
            await self._wait_for_page_load()
            await self._human_delay(1000, 2000)

            # Check for CAPTCHA before starting
            if await captcha_solver.detect_captcha(self._page):
                self._log_action("login", "⚠️ CAPTCHA on login page — attempting to solve")
                solved = await captcha_solver.solve_and_submit(self._page)
                if not solved:
                    logger.error(f"[indeed] Login blocked by unsolved CAPTCHA")
                    return False

            # Step 1: Enter email
            email_filled = await self._safe_fill(
                "input[name='__email'], input[type='email'], #ifl-InputFormField-3",
                username,
            )
            if not email_filled:
                # Try alternate selector
                email_filled = await self._safe_fill("input[type='email']", username)

            if not email_filled:
                await self._screenshot("login_email_field_not_found")
                logger.error("[indeed] Could not find email field on login page")
                return False

            await self._human_delay(500, 1000)

            # Click Continue / Next button
            await self._safe_click(
                "button[type='submit'], button:has-text('Continue'), "
                "div[data-testid='login-submit-button']"
            )
            await self._wait_for_page_load()
            await self._human_delay(1000, 2000)

            # Step 2: Enter password
            password_filled = await self._safe_fill(
                "input[name='password'], input[type='password']",
                password,
            )
            if not password_filled:
                await self._screenshot("login_password_field_not_found")
                logger.error("[indeed] Could not find password field")
                return False

            await self._human_delay(500, 1000)

            # Click Sign In
            await self._safe_click(
                "button[type='submit'], button:has-text('Sign in'), "
                "div[data-testid='login-submit-button']"
            )
            await self._wait_for_page_load(timeout=15000)
            await self._human_delay(2000, 3000)

            # Check for CAPTCHA after login attempt
            if await captcha_solver.detect_captcha(self._page):
                self._log_action("login", "⚠️ CAPTCHA after password — attempting to solve")
                solved = await captcha_solver.solve_and_submit(self._page)
                if not solved:
                    await self._screenshot("login_captcha_unsolved")
                    return False
                await self._wait_for_page_load()

            # Verify login success
            if await self._is_logged_in():
                self._log_action("login", "✅ Login successful")
                await self.save_cookies()
                return True
            else:
                await self._screenshot("login_failed")
                logger.error(
                    f"[indeed] Login failed — check credentials for {username}. "
                    "URL: " + self._page.url
                )
                return False

        except Exception as e:
            await self._screenshot("login_exception")
            logger.error(f"[indeed] Login exception: {e}")
            return False

    async def _is_logged_in(self) -> bool:
        """
        Checks if the current page shows a logged-in user.
        Indeed shows user navigation links when logged in.
        """
        try:
            # Look for user account nav elements that only appear when logged in
            indicators = [
                "a[href*='/settings/account']",
                "a[href*='/profile']",
                "div[data-gnav-element-name='AccountMenu']",
                "a[aria-label*='Profile']",
                "span[class*='gnav-UserName']",
            ]
            for selector in indicators:
                el = await self._page.query_selector(selector)
                if el:
                    return True

            # Also check if URL is NOT the login/auth page
            current_url = self._page.url
            if "secure.indeed.com/auth" in current_url:
                return False

            return False

        except Exception:
            return False

    # ─── Job Search ───────────────────────────────────────────────────────────

    async def search_jobs(
        self,
        keywords: list[str],
        location: str,
        max_results: int = 25,
    ) -> list[JobListing]:
        """
        Searches for jobs on Indeed and returns a list of listings.

        Strategy:
        - Build search URL with keywords joined by " OR "
        - Scrape the results page for job cards
        - Extract title, company, location, URL from each card
        - Filter to "Indeed Apply" jobs (can apply in-portal)

        Args:
            keywords: e.g. ["Python Developer", "Backend Engineer"]
            location: e.g. "Remote" or "New York, NY"
            max_results: Max listings to return per search (default 25)

        Returns:
            List of JobListing objects.
        """
        self._log_action("search_jobs", f"keywords={keywords} location={location}")

        jobs: list[JobListing] = []

        try:
            # Build the search URL — keep it simple to avoid Cloudflare
            query = " ".join(keywords)
            params = {
                "q": query,
                "l": location,
                "sort": "date",
                "limit": "25",
            }
            search_url = f"{self.BASE_URL}/jobs?{urlencode(params)}"

            self._log_action("search_jobs", f"URL: {search_url}")
            await self._page.goto(search_url, wait_until="domcontentloaded")
            await self._wait_for_page_load()
            await self._human_delay(1500, 2500)

            # Check for CAPTCHA on search page
            if await captcha_solver.detect_captcha(self._page):
                self._log_action("search_jobs", "⚠️ CAPTCHA on search page")
                solved = await captcha_solver.solve_and_submit(self._page)
                if not solved:
                    logger.error("[indeed] Search blocked by CAPTCHA")
                    return []
                await self._wait_for_page_load()

            # Extract job cards from the results page
            jobs = await self._extract_job_cards(max_results)

            self._log_action("search_jobs", f"✅ Found {len(jobs)} job listings")
            return jobs

        except Exception as e:
            await self._screenshot("search_exception")
            logger.error(f"[indeed] search_jobs exception: {e}")
            return []

    async def _extract_job_cards(self, max_results: int) -> list[JobListing]:
        """
        Extracts job card data from the Indeed search results page.

        MENTOR NOTE on selectors:
          Indeed changes CSS class names frequently (minified names like "css-1m4cuuf").
          We use data-testid and aria attributes which are more stable.
          If selectors break, open Indeed in Chrome DevTools and inspect the job cards.
        """
        jobs = []

        try:
            # Wait for job cards to load
            await self._page.wait_for_selector(
                "div[data-testid='slider_container'], "
                "div.job_seen_beacon, "
                "li[class*='JobComponent']",
                timeout=15000,
            )
        except PlaywrightTimeout:
            await self._screenshot("no_job_cards_found")
            logger.warning("[indeed] No job cards found on page")
            return []

        # Get all job card elements
        job_cards = await self._page.query_selector_all(
            "div[data-testid='slider_container'], div.job_seen_beacon"
        )

        self._log_action("_extract_job_cards", f"Raw card count: {len(job_cards)}")

        for card in job_cards[:max_results]:
            try:
                job = await self._parse_job_card(card)
                if job:
                    jobs.append(job)
            except Exception as e:
                logger.warning(f"[indeed] Failed to parse job card: {e}")
                continue

        return jobs

    async def _parse_job_card(self, card) -> Optional[JobListing]:
        """
        Parses a single job card element into a JobListing object.
        Returns None if essential data (title, company, URL) is missing.
        """
        try:
            # ── Title ──
            title_el = await card.query_selector(
                "h2[data-testid='jobTitle'] a, "
                "h2.jobTitle a, "
                "a[data-jk]"
            )
            if not title_el:
                return None
            title = (await title_el.inner_text()).strip()

            # ── Job URL ──
            href = await title_el.get_attribute("href")
            if not href:
                return None
            # Indeed hrefs can be relative (/pagead/clk?...) or absolute
            job_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"

            # ── Company ──
            company = ""
            company_el = await card.query_selector(
                "[data-testid='company-name'], "
                "span[class*='companyName'], "
                ".company"
            )
            if company_el:
                company = (await company_el.inner_text()).strip()

            # ── Location ──
            location = ""
            location_el = await card.query_selector(
                "[data-testid='text-location'], "
                "div[class*='companyLocation']"
            )
            if location_el:
                location = (await location_el.inner_text()).strip()

            # ── Is "Indeed Apply" / "Easily apply" ──
            is_easy_apply = False
            easy_apply_indicators = [
                "span[class*='indeedApply']",
                "button[aria-label*='Indeed Apply']",
                "span:has-text('Indeed Apply')",
                "span:has-text('Easily apply')",
                "div:has-text('Easily apply')",
                "[data-testid*='indeedApply']",
            ]
            for selector in easy_apply_indicators:
                el = await card.query_selector(selector)
                if el:
                    is_easy_apply = True
                    break

            return JobListing(
                title=title,
                company=company,
                job_url=job_url,
                location=location,
                is_easy_apply=is_easy_apply,
                portal=self.PORTAL_NAME,
            )

        except Exception as e:
            logger.debug(f"[indeed] _parse_job_card error: {e}")
            return None

    async def get_job_description(self, job_url: str) -> str:
        """
        Opens a job listing page and extracts the full description text.
        Used to get description for AI matching (Phase 3).
        """
        try:
            await self._page.goto(job_url, wait_until="domcontentloaded")
            await self._wait_for_page_load()

            desc_el = await self._page.query_selector(
                "div#jobDescriptionText, "
                "div[data-testid='jobsearch-JobComponent-description']"
            )
            if desc_el:
                return (await desc_el.inner_text()).strip()

        except Exception as e:
            logger.debug(f"[indeed] Could not get job description: {e}")

        return ""

    # ─── Apply to Job ─────────────────────────────────────────────────────────

    async def apply_job(
        self,
        job: JobListing,
        user_data: dict,
        dry_run: bool = False,
    ) -> ApplicationResult:
        """
        Applies to a single Indeed job listing.

        Flow:
        1. Navigate to the job URL
        2. Click "Apply Now" / "Indeed Apply" button
        3. Fill in the application form (multi-step)
        4. Upload resume if prompted
        5. Submit (unless dry_run=True)

        Args:
            job: The JobListing to apply to.
            user_data: Dict containing:
                - name: Full name
                - email: Email address
                - phone: Phone number
                - resume_path: Path to resume PDF file
                - years_experience: Total years of experience
            dry_run: If True, go through all steps but don't click final Submit.

        Returns:
            ApplicationResult with status 'applied', 'failed', or 'skipped'.
        """
        self._log_action("apply_job", f"job='{job.title}' @ {job.company}")

        # Skip non-Indeed-Apply jobs (they redirect to external sites)
        if not job.is_easy_apply:
            self._log_action("apply_job", f"⏭️ Skipping — not an Indeed Apply job")
            return ApplicationResult(
                job=job,
                status="skipped",
                failure_reason="not_indeed_apply",
            )

        try:
            # Step 1: Navigate to the job listing page
            await self._page.goto(job.job_url, wait_until="domcontentloaded")
            await self._wait_for_page_load()
            await self._human_delay(1000, 2000)

            # Fetch description while we're on the page
            desc_el = await self._page.query_selector(
                "div#jobDescriptionText, "
                "div[data-testid='jobsearch-JobComponent-description']"
            )
            if desc_el:
                job.description = (await desc_el.inner_text()).strip()[:3000]

            # Step 2: Click the Apply button
            apply_clicked = await self._safe_click(
                "button[id*='indeedApplyButton'], "
                "button:has-text('Apply now'), "
                "span[id*='applyButtonLinkContainer'] button, "
                "a[data-jk][class*='apply']"
            )

            if not apply_clicked:
                await self._screenshot("apply_button_not_found")
                return ApplicationResult(
                    job=job,
                    status="failed",
                    failure_reason="apply_button_not_found",
                )

            await self._wait_for_page_load()
            await self._human_delay(2000, 3000)

            # Check if we got redirected to an external site
            if self.BASE_URL not in self._page.url and "indeed.com" not in self._page.url:
                self._log_action("apply_job", "⏭️ Redirected to external site — skipping")
                return ApplicationResult(
                    job=job,
                    status="skipped",
                    failure_reason="redirected_to_external_site",
                )

            # Step 3: Fill the multi-step application form
            result = await self._fill_application_form(job, user_data, dry_run)
            return result

        except Exception as e:
            await self._screenshot("apply_exception")
            logger.error(f"[indeed] apply_job exception for '{job.title}': {e}")
            return ApplicationResult(
                job=job,
                status="failed",
                failure_reason=f"exception: {str(e)[:200]}",
            )

    async def _fill_application_form(
        self,
        job: JobListing,
        user_data: dict,
        dry_run: bool,
    ) -> ApplicationResult:
        """
        Fills the Indeed multi-step application form.

        Indeed applications typically have 3-5 steps:
          Step 1: Contact info (name, email, phone, location)
          Step 2: Resume upload or select existing
          Step 3: Work experience questions
          Step 4: Additional questions (custom per employer)
          Step 5: Review and Submit

        We loop through steps until we hit the Submit button.
        """
        self._log_action("_fill_application_form", "Starting form fill...")
        max_steps = 10  # Safety limit — no job has more than 10 steps

        for step_num in range(1, max_steps + 1):
            self._log_action("_fill_application_form", f"Processing step {step_num}")
            await self._human_delay(1000, 1500)

            # Check for CAPTCHA on the form
            if await captcha_solver.detect_captcha(self._page):
                self._log_action("_fill_application_form", "⚠️ CAPTCHA on form")
                solved = await captcha_solver.solve_and_submit(self._page)
                if not solved:
                    return ApplicationResult(
                        job=job,
                        status="failed",
                        failure_reason="captcha_on_form",
                    )

            # ── Phase 3: Smart AI-powered Form Filling ──
            await self._smart_fill_form(user_data)

            # ── Fallback: Fill contact info fields (if smart fill missed any) ──
            await self._fill_contact_fields(user_data)

            # ── Handle resume upload step ──
            await self._handle_resume_upload(user_data.get("resume_path", ""))

            # ── Handle yes/no work authorization questions ──
            await self._handle_work_auth_questions()

            # ── Handle experience/salary fields (fallback) ──
            await self._handle_experience_fields(user_data)

            # ── Check if Submit button is visible (final step) ──
            submit_btn = await self._page.query_selector(
                "button[aria-label='Submit your application'], "
                "button:has-text('Submit'), "
                "button[data-testid='IndeedApplyButton']"
            )
            if submit_btn:
                if dry_run:
                    self._log_action("_fill_application_form", "🧪 DRY RUN — not submitting")
                    return ApplicationResult(job=job, status="applied")
                else:
                    await submit_btn.click()
                    await self._wait_for_page_load()
                    await self._human_delay(2000, 3000)
                    self._log_action("_fill_application_form", "✅ Application submitted!")
                    return ApplicationResult(job=job, status="applied")

            # ── Click Continue / Next to go to next step ──
            next_clicked = await self._safe_click(
                "button:has-text('Continue'), "
                "button:has-text('Next'), "
                "button[aria-label='Continue to next step']"
            )
            if not next_clicked:
                await self._screenshot(f"form_stuck_step_{step_num}")
                return ApplicationResult(
                    job=job,
                    status="failed",
                    failure_reason=f"form_stuck_at_step_{step_num}_no_next_button",
                )

            await self._wait_for_page_load()

        return ApplicationResult(
            job=job,
            status="failed",
            failure_reason="too_many_form_steps",
        )

    async def _fill_contact_fields(self, user_data: dict) -> None:
        """Fills name, email, phone fields if they appear on the current step."""
        name = user_data.get("name", "")
        email = user_data.get("email", "")
        phone = user_data.get("phone", "")
        city = user_data.get("city", "")

        # Full name or first/last name fields
        if name:
            parts = name.split(" ", 1)
            first_name = parts[0]
            last_name = parts[1] if len(parts) > 1 else ""

            await self._safe_fill("input[id*='firstName'], input[name*='firstName']", first_name)
            await self._safe_fill("input[id*='lastName'], input[name*='lastName']", last_name)
            await self._safe_fill("input[name='fullName'], input[aria-label*='Full name']", name)

        if email:
            await self._safe_fill("input[type='email'], input[name='email']", email)

        if phone:
            await self._safe_fill(
                "input[type='tel'], input[name='phone'], input[aria-label*='phone']", phone
            )

        if city:
            await self._safe_fill(
                "input[aria-label*='City'], input[name*='location']", city
            )

    async def _handle_resume_upload(self, resume_path: str) -> None:
        """
        Uploads a resume file if the current step has a file upload field.

        MENTOR NOTE:
          Playwright handles file uploads natively with set_input_files().
          We find the hidden <input type="file"> and set the file path directly.
          No need to click or interact with the file dialog.
        """
        if not resume_path:
            return

        try:
            file_input = await self._page.query_selector("input[type='file']")
            if file_input:
                await file_input.set_input_files(resume_path)
                self._log_action("_handle_resume_upload", f"✅ Uploaded: {resume_path}")
                await self._human_delay(1000, 2000)

                # Click Upload button if present
                await self._safe_click(
                    "button:has-text('Upload'), button[aria-label*='Upload']", timeout=3000
                )
        except Exception as e:
            logger.warning(f"[indeed] Resume upload failed: {e}")

    async def _handle_work_auth_questions(self) -> None:
        """
        Handles common Yes/No questions about work authorization.
        Defaults to 'Yes' for:
          - "Are you authorized to work in the US?"
          - "Will you now or in the future require sponsorship?"
            → We answer 'No' (most common for already-authorized candidates)
        """
        try:
            # Find all radio button questions on the page
            questions = await self._page.query_selector_all(
                "div[data-testid='MultiLineRadioInput'], "
                "fieldset[class*='radio']"
            )

            for question_div in questions:
                question_text = (await question_div.inner_text()).lower()

                if "authorized to work" in question_text or "legally authorized" in question_text:
                    # Click Yes
                    yes_radio = await question_div.query_selector(
                        "input[value='Yes'], label:has-text('Yes')"
                    )
                    if yes_radio:
                        await yes_radio.click()

                elif "sponsorship" in question_text or "require visa" in question_text:
                    # Click No (we don't need sponsorship)
                    no_radio = await question_div.query_selector(
                        "input[value='No'], label:has-text('No')"
                    )
                    if no_radio:
                        await no_radio.click()

        except Exception as e:
            logger.debug(f"[indeed] work_auth_questions: {e}")

    async def _handle_experience_fields(self, user_data: dict) -> None:
        """Fills years of experience fields if present on current step."""
        years_exp = str(user_data.get("years_experience", "3"))

        try:
            exp_inputs = await self._page.query_selector_all(
                "input[aria-label*='years'], "
                "input[aria-label*='experience'], "
                "input[name*='yearsOfExperience']"
            )
            for inp in exp_inputs:
                await inp.fill(years_exp)
        except Exception as e:
            logger.debug(f"[indeed] experience_fields: {e}")
