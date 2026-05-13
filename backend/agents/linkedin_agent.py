"""
agents/linkedin_agent.py — LinkedIn Browser Agent
===================================================
Handles login, job search, and Easy Apply on LinkedIn.

MENTOR NOTE on LinkedIn (MOST COMPLEX PORTAL):
  LinkedIn is the hardest to automate because:
  1. Login uses hCaptcha (solved by our captcha_solver)
  2. "Easy Apply" opens a MODAL (not a new page) — we navigate steps inside it
  3. Some Easy Apply forms have 5+ steps with custom employer questions
  4. LinkedIn rate-limits aggressively: ~80 applications per day before soft-ban
  5. LinkedIn actively detects bots via behavioral analysis (mouse movements, timing)

  STRATEGY for avoiding detection:
  - playwright-stealth patches navigator.webdriver
  - Human-like delays between all actions (_human_delay)
  - Cookie persistence avoids repeated logins (the #1 bot signal)
  - Max 15-20 applications per session (not 80 at once)

  REAL WORLD WARNING:
    LinkedIn's ToS prohibits automation. Your account WILL be restricted
    if you apply to hundreds of jobs per day. Keep max_apps_per_day ≤ 40.
    The system enforces this via settings.max_applications_per_day.

Usage (via Celery task — you don't call this directly):
    async with LinkedInAgent(user_id="abc123") as agent:
        logged_in = await agent.login(username, password)
        jobs = await agent.search_jobs(["Software Engineer"], "Remote")
        for job in jobs:
            result = await agent.apply_job(job, user_data)
"""

import asyncio
from typing import Optional

from loguru import logger
from playwright.async_api import TimeoutError as PlaywrightTimeout

from backend.agents.base_agent import BaseAgent, JobListing, ApplicationResult
from backend.services.captcha_solver import captcha_solver


class LinkedInAgent(BaseAgent):
    """
    Browser agent for LinkedIn.com.
    Handles the full Easy Apply flow including multi-step modals.
    """

    PORTAL_NAME = "linkedin"
    BASE_URL = "https://www.linkedin.com"
    LOGIN_URL = "https://www.linkedin.com/login"
    JOBS_URL = "https://www.linkedin.com/jobs/search/"

    # ─── Login ────────────────────────────────────────────────────────────────

    async def login(self, username: str, password: str) -> bool:
        """
        Logs into LinkedIn with cookie persistence.

        LinkedIn's login process:
        1. Load the login page
        2. Fill email + password form
        3. Handle hCaptcha if triggered
        4. Save cookies on success (valid ~30 days)

        Returns:
            True if logged in successfully.
        """
        self._log_action("login", f"user={username}")

        # ── Try saved cookies first — LinkedIn cookies last ~30 days ──
        cookies_loaded = await self.load_cookies()
        if cookies_loaded:
            await self._page.goto(
                f"{self.BASE_URL}/feed/", wait_until="domcontentloaded"
            )
            await self._wait_for_page_load()
            await self._human_delay(2000, 3000)

            if await self._is_logged_in():
                self._log_action("login", "✅ Session restored via cookies")
                return True
            else:
                self._log_action("login", "⚠️ Cookies expired — fresh login")
                self.clear_cookies()

        # ── Fresh login ──
        try:
            await self._page.goto(self.LOGIN_URL, wait_until="domcontentloaded")
            await self._wait_for_page_load()
            await self._human_delay(1500, 2500)

            # Fill username (email)
            email_ok = await self._safe_type(
                "input#username, input[name='session_key']",
                username,
                delay=60,
            )
            if not email_ok:
                await self._screenshot("linkedin_email_not_found")
                return False

            await self._human_delay(800, 1200)

            # Fill password (use type for human-like input)
            pw_ok = await self._safe_type(
                "input#password, input[name='session_password']",
                password,
                delay=55,
            )
            if not pw_ok:
                await self._screenshot("linkedin_password_not_found")
                return False

            await self._human_delay(800, 1500)

            # Click Sign In
            await self._safe_click("button[type='submit'], button[aria-label='Sign in']")
            await self._wait_for_page_load(timeout=20000)
            await self._human_delay(3000, 4000)

            # Handle hCaptcha (LinkedIn uses this frequently)
            if await captcha_solver.detect_captcha(self._page):
                self._log_action("login", "⚠️ hCaptcha detected after login click")
                solved = await captcha_solver.solve_and_submit(self._page)
                if not solved:
                    await self._screenshot("linkedin_captcha_failed")
                    return False
                await self._wait_for_page_load(timeout=15000)
                await self._human_delay(3000, 4000)

            # Handle email verification checkpoint (LinkedIn sometimes does this)
            if "checkpoint" in self._page.url or "challenge" in self._page.url:
                self._log_action("login", "⚠️ LinkedIn security checkpoint — needs manual action")
                await self._screenshot("linkedin_checkpoint")
                logger.warning(
                    "[linkedin] Security checkpoint detected. "
                    "User may need to verify via email. "
                    "Marking login as failed."
                )
                return False

            if await self._is_logged_in():
                self._log_action("login", "✅ LinkedIn login successful")
                await self.save_cookies()
                return True
            else:
                await self._screenshot("linkedin_login_failed")
                logger.error(f"[linkedin] Login failed for {username}")
                return False

        except Exception as e:
            await self._screenshot("linkedin_login_exception")
            logger.error(f"[linkedin] Login exception: {e}")
            return False

    async def _is_logged_in(self) -> bool:
        """Checks if we're logged into LinkedIn."""
        try:
            indicators = [
                "a[href*='/in/'][class*='global-nav']",
                "div.global-nav__me",
                "img.global-nav__me-photo",
                "a[aria-label*='Home']",
            ]
            for sel in indicators:
                el = await self._page.query_selector(sel)
                if el:
                    return True

            # Also check if we're NOT on login page
            if "linkedin.com/login" in self._page.url:
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
        Searches LinkedIn Jobs and returns Easy Apply listings only.

        LinkedIn search URL filters used:
        - f_AL=true    → Easy Apply only
        - f_TPR=r259200 → Posted in last 3 days (3*24*3600 = 259200 seconds)
        - f_WT=2       → Remote jobs (1=On-site, 2=Remote, 3=Hybrid)

        Args:
            keywords: e.g. ["Python Developer", "Senior Backend Engineer"]
            location: e.g. "United States" or "Remote"
            max_results: Max listings to collect

        Returns:
            List of JobListing objects (Easy Apply only).
        """
        self._log_action("search_jobs", f"keywords={keywords} location={location}")

        jobs: list[JobListing] = []

        try:
            query = " ".join(keywords)
            from urllib.parse import urlencode
            params = {
                "keywords": query,
                "location": location,
                "f_AL": "true",        # Easy Apply only
                "f_TPR": "r259200",    # Last 3 days
                "sortBy": "DD",        # Date: newest first
            }
            search_url = f"{self.JOBS_URL}?{urlencode(params)}"

            self._log_action("search_jobs", f"URL: {search_url}")
            await self._page.goto(search_url, wait_until="domcontentloaded")
            await self._wait_for_page_load()
            await self._human_delay(2000, 3000)

            # Scroll down to trigger lazy loading of job cards
            await self._scroll_to_load_jobs()

            jobs = await self._extract_job_cards(max_results)
            self._log_action("search_jobs", f"✅ Found {len(jobs)} Easy Apply jobs")
            return jobs

        except Exception as e:
            await self._screenshot("linkedin_search_exception")
            logger.error(f"[linkedin] search_jobs exception: {e}")
            return []

    async def _scroll_to_load_jobs(self) -> None:
        """
        Scrolls the job list panel to trigger lazy-loading of more cards.
        LinkedIn loads jobs in batches of ~25 as you scroll.
        """
        try:
            list_panel = await self._page.query_selector(
                "div.jobs-search-results-list, ul.jobs-search__results-list"
            )
            if list_panel:
                # Scroll the list panel 3 times
                for _ in range(3):
                    await list_panel.evaluate("el => el.scrollTop += 800")
                    await asyncio.sleep(1)
        except Exception:
            # Fall back to page scroll
            for _ in range(3):
                await self._page.evaluate("window.scrollBy(0, 500)")
                await asyncio.sleep(0.8)

    async def _extract_job_cards(self, max_results: int) -> list[JobListing]:
        """Extracts job listings from LinkedIn search results."""
        jobs = []

        try:
            await self._page.wait_for_selector(
                "li.jobs-search-results__list-item, "
                "div.job-card-container",
                timeout=15000,
            )
        except PlaywrightTimeout:
            await self._screenshot("linkedin_no_cards")
            logger.warning("[linkedin] No job cards found")
            return []

        cards = await self._page.query_selector_all(
            "li.jobs-search-results__list-item, "
            "div.job-card-container--clickable"
        )

        self._log_action("_extract_job_cards", f"Raw card count: {len(cards)}")

        for card in cards[:max_results]:
            try:
                job = await self._parse_job_card(card)
                if job:
                    jobs.append(job)
            except Exception as e:
                logger.debug(f"[linkedin] Card parse error: {e}")
                continue

        return jobs

    async def _parse_job_card(self, card) -> Optional[JobListing]:
        """Parses a single LinkedIn job card element."""
        try:
            # Title
            title_el = await card.query_selector(
                "a.job-card-list__title, "
                "a[class*='job-card-container__link']"
            )
            if not title_el:
                return None
            title = (await title_el.inner_text()).strip()

            # URL
            href = await title_el.get_attribute("href")
            if not href:
                return None
            job_url = href if href.startswith("http") else f"{self.BASE_URL}{href}"
            # Clean up URL — remove query params after the job ID
            if "?" in job_url:
                job_url = job_url.split("?")[0]

            # Company
            company = ""
            company_el = await card.query_selector(
                "span.job-card-container__primary-description, "
                "a.job-card-container__company-name"
            )
            if company_el:
                company = (await company_el.inner_text()).strip()

            # Location
            location = ""
            location_el = await card.query_selector(
                "li.job-card-container__metadata-item, "
                "span[class*='job-card-container__metadata']"
            )
            if location_el:
                location = (await location_el.inner_text()).strip()

            # All results already filtered to Easy Apply by the search URL
            is_easy_apply = True

            return JobListing(
                title=title,
                company=company,
                job_url=job_url,
                location=location,
                is_easy_apply=is_easy_apply,
                portal=self.PORTAL_NAME,
            )

        except Exception as e:
            logger.debug(f"[linkedin] _parse_job_card: {e}")
            return None

    # ─── Apply to Job ─────────────────────────────────────────────────────────

    async def apply_job(
        self,
        job: JobListing,
        user_data: dict,
        dry_run: bool = False,
    ) -> ApplicationResult:
        """
        Applies to a LinkedIn job via Easy Apply modal.

        Flow:
        1. Navigate to job listing page
        2. Click "Easy Apply" button → modal opens
        3. Fill each step of the modal form
        4. Click "Submit application" on final step

        MENTOR NOTE on the Easy Apply Modal:
          The modal is a multi-step wizard. Each step has a "Next" button.
          The last step shows a "Submit application" button.
          We loop: fill fields → click Next → repeat until Submit appears.

        Returns:
            ApplicationResult with status 'applied', 'failed', or 'skipped'.
        """
        self._log_action("apply_job", f"'{job.title}' @ {job.company}")

        try:
            # Navigate to job page
            await self._page.goto(job.job_url, wait_until="domcontentloaded")
            await self._wait_for_page_load()
            await self._human_delay(2000, 3000)

            # Get job description
            desc_el = await self._page.query_selector(
                "div.jobs-description-content__text, "
                "div[class*='job-details-jobs-unified-top-card']"
            )
            if desc_el:
                job.description = (await desc_el.inner_text()).strip()[:3000]

            # Find and click Easy Apply button
            easy_apply_btn = await self._page.query_selector(
                "button.jobs-apply-button:has-text('Easy Apply'), "
                "button[aria-label*='Easy Apply']"
            )

            if not easy_apply_btn:
                self._log_action("apply_job", "⏭️ No Easy Apply button found — skipping")
                return ApplicationResult(
                    job=job,
                    status="skipped",
                    failure_reason="no_easy_apply_button",
                )

            await easy_apply_btn.click()
            await self._human_delay(2000, 3000)

            # Handle the Easy Apply modal
            result = await self._handle_easy_apply_modal(job, user_data, dry_run)
            return result

        except Exception as e:
            await self._screenshot("linkedin_apply_exception")
            logger.error(f"[linkedin] apply_job exception: {e}")
            return ApplicationResult(
                job=job,
                status="failed",
                failure_reason=f"exception: {str(e)[:200]}",
            )

    async def _handle_easy_apply_modal(
        self,
        job: JobListing,
        user_data: dict,
        dry_run: bool,
    ) -> ApplicationResult:
        """
        Navigates through all steps of LinkedIn's Easy Apply modal.

        Each step we:
        1. Fill any visible form fields (text, phone, dropdowns, checkboxes)
        2. Handle file upload (resume)
        3. Handle yes/no questions
        4. Click Next to advance
        5. Check if Submit button appeared (final step)

        MENTOR NOTE:
          The modal selector changes between job postings.
          We look for the modal container first, then operate within it.
          This prevents accidentally clicking page elements outside the modal.
        """
        max_steps = 10
        modal_selector = (
            "div.jobs-easy-apply-modal, "
            "div[data-test-modal-container], "
            "div.artdeco-modal__content"
        )

        # Wait for modal to appear
        try:
            await self._page.wait_for_selector(modal_selector, timeout=10000)
        except PlaywrightTimeout:
            await self._screenshot("linkedin_modal_not_opened")
            return ApplicationResult(
                job=job,
                status="failed",
                failure_reason="easy_apply_modal_did_not_open",
            )

        for step_num in range(1, max_steps + 1):
            self._log_action("_handle_easy_apply_modal", f"Modal step {step_num}")
            await self._human_delay(1000, 2000)

            # Get the modal element to scope our selectors
            modal = await self._page.query_selector(modal_selector)
            if not modal:
                break

            # ── Phase 3: Smart AI-powered Form Filling ──
            await self._smart_fill_form(user_data)

            # ── Fallbacks ──
            # Fill phone number if field is still empty
            phone = user_data.get("phone", "")
            if phone:
                await self._safe_fill(
                    "input[id*='phoneNumber'], input[aria-label*='Phone']", phone, timeout=3000
                )

            # Handle resume upload
            resume_path = user_data.get("resume_path", "")
            if resume_path:
                file_input = await self._page.query_selector("input[type='file']")
                if file_input:
                    await file_input.set_input_files(resume_path)
                    self._log_action("_handle_easy_apply_modal", "📎 Resume uploaded")
                    await self._human_delay(1000, 1500)

            # Handle dropdowns (fallback)
            await self._handle_modal_selects(user_data)

            # Handle Yes/No radio questions (specific to LinkedIn layout)
            await self._handle_modal_radio_questions()

            # ── Check for Submit button (final step) ──
            submit_btn = await self._page.query_selector(
                "button[aria-label='Submit application'], "
                "button:has-text('Submit application')"
            )
            if submit_btn:
                if dry_run:
                    self._log_action("_handle_easy_apply_modal", "🧪 DRY RUN — not submitting")
                    # Close modal
                    await self._safe_click("button[aria-label='Dismiss'], button:has-text('Cancel')", timeout=3000)
                    return ApplicationResult(job=job, status="applied")

                await submit_btn.click()
                await self._human_delay(2000, 3000)
                self._log_action("_handle_easy_apply_modal", "✅ Application submitted!")

                # Close the success modal
                await self._safe_click(
                    "button[aria-label='Dismiss'], "
                    "button:has-text('Done')",
                    timeout=5000,
                )
                return ApplicationResult(job=job, status="applied")

            # ── Click Next ──
            next_btn = await self._page.query_selector(
                "button[aria-label='Continue to next step'], "
                "button:has-text('Next'), "
                "button[aria-label='Review your application']"
            )
            if next_btn:
                await next_btn.click()
                await self._wait_for_page_load()
                await self._human_delay(1000, 2000)
            else:
                # No Next and no Submit — we're stuck
                await self._screenshot(f"linkedin_modal_stuck_step_{step_num}")
                # Try to close modal and return
                await self._safe_click("button[aria-label='Dismiss']", timeout=3000)
                return ApplicationResult(
                    job=job,
                    status="failed",
                    failure_reason=f"modal_stuck_at_step_{step_num}",
                )

        return ApplicationResult(
            job=job,
            status="failed",
            failure_reason="too_many_modal_steps",
        )

    async def _handle_modal_selects(self, user_data: dict) -> None:
        """
        Handles <select> dropdowns in the Easy Apply modal.
        Common dropdowns: country, years of experience, education level.
        """
        try:
            selects = await self._page.query_selector_all(
                "div.jobs-easy-apply-modal select, "
                "div.artdeco-modal select"
            )
            for sel_el in selects:
                label = await sel_el.get_attribute("aria-label") or ""
                label_lower = label.lower()

                if "country" in label_lower:
                    await sel_el.select_option(label="United States")
                elif "experience" in label_lower or "years" in label_lower:
                    exp = str(user_data.get("years_experience", "3"))
                    try:
                        await sel_el.select_option(value=exp)
                    except Exception:
                        # Try selecting by label text
                        await sel_el.select_option(label=f"{exp} years")
                elif "education" in label_lower:
                    await sel_el.select_option(label="Bachelor's Degree")

        except Exception as e:
            logger.debug(f"[linkedin] _handle_modal_selects: {e}")

    async def _handle_modal_radio_questions(self) -> None:
        """
        Handles Yes/No radio questions in the modal.
        Common questions: work authorization, sponsorship, relocation.
        """
        try:
            fieldsets = await self._page.query_selector_all(
                "fieldset.fb-text-selectable__list, "
                "div.jobs-easy-apply-form-element"
            )
            for fieldset in fieldsets:
                text = (await fieldset.inner_text()).lower()

                if "authorized" in text and "work" in text:
                    # Are you authorized to work? → Yes
                    yes = await fieldset.query_selector("label:has-text('Yes')")
                    if yes:
                        await yes.click()

                elif "sponsorship" in text or "visa" in text:
                    # Will you need sponsorship? → No
                    no = await fieldset.query_selector("label:has-text('No')")
                    if no:
                        await no.click()

                elif "commute" in text or "relocate" in text:
                    # Can you commute/relocate? → Yes
                    yes = await fieldset.query_selector("label:has-text('Yes')")
                    if yes:
                        await yes.click()

        except Exception as e:
            logger.debug(f"[linkedin] _handle_modal_radio_questions: {e}")

    async def _handle_modal_text_inputs(self, user_data: dict) -> None:
        """
        Handles any remaining text inputs in the modal that weren't covered
        by phone/email/name handlers.
        Common: LinkedIn profile URL, portfolio URL, salary expectations.
        """
        try:
            inputs = await self._page.query_selector_all(
                "div.jobs-easy-apply-modal input[type='text']:not([readonly]), "
                "div.artdeco-modal input[type='number']"
            )
            for inp in inputs:
                label = await inp.get_attribute("aria-label") or ""
                label_lower = label.lower()
                current_value = await inp.input_value()

                # Only fill if empty
                if current_value:
                    continue

                if "salary" in label_lower or "compensation" in label_lower:
                    # Leave salary blank (negotiate in interview)
                    pass
                elif "years" in label_lower or "experience" in label_lower:
                    await inp.fill(str(user_data.get("years_experience", "3")))
                elif "linkedin" in label_lower or "profile" in label_lower:
                    linkedin_url = user_data.get("linkedin_url", "")
                    if linkedin_url:
                        await inp.fill(linkedin_url)
                elif "website" in label_lower or "portfolio" in label_lower:
                    portfolio = user_data.get("portfolio_url", "")
                    if portfolio:
                        await inp.fill(portfolio)

        except Exception as e:
            logger.debug(f"[linkedin] _handle_modal_text_inputs: {e}")
