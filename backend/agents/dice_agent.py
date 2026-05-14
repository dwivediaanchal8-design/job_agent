"""
agents/dice_agent.py — Dice.com Browser Agent
===============================================
Handles login, job search, and application on Dice.com.

MENTOR NOTE on Dice:
  Dice is a tech-focused job board. Key differences from Indeed:
  1. Login uses a popup/modal, not a dedicated page
  2. Search URL has different parameters (skill-based filters)
  3. "Easy Apply" on Dice submits your saved profile + resume in one click
  4. Most tech jobs (Python, Java, Cloud) are here — less competition than LinkedIn

  REAL WORLD WARNING:
    Dice uses Cloudflare protection. The stealth browser from BaseAgent
    handles this well. Do NOT run headless=True during development;
    keep headless=False so you can see Cloudflare challenges.

Usage (via Celery task — you don't call this directly):
    async with DiceAgent(user_id="abc123") as agent:
        logged_in = await agent.login(username, password)
        jobs = await agent.search_jobs(["Python", "AWS"], "Remote")
        for job in jobs:
            result = await agent.apply_job(job, user_data)
"""

import asyncio
from typing import Optional
from urllib.parse import urlencode

from loguru import logger
from playwright.async_api import TimeoutError as PlaywrightTimeout

from backend.agents.base_agent import BaseAgent, JobListing, ApplicationResult
from backend.services.captcha_solver import captcha_solver


class DiceAgent(BaseAgent):
    """
    Browser agent for Dice.com.
    Focused on tech jobs: Python, Java, DevOps, Cloud, Data Engineering.
    """

    PORTAL_NAME = "dice"
    BASE_URL = "https://www.dice.com"
    LOGIN_URL = "https://www.dice.com/dashboard/login"

    # ─── Overrides ────────────────────────────────────────────────────────────
    
    async def _wait_for_page_load(self, timeout: int = 30000) -> None:
        """
        Wait for network idle and also handle Dice-specific popups like cookie banners.
        """
        try:
            await super()._wait_for_page_load(timeout)
        except:
            pass # Continue even if networkidle fails
        
        # Use JS to find and click buttons by text (more robust than CSS)
        await self._page.evaluate("""() => {
            const buttonText = ['Allow all', 'Accept All', 'Accept', 'OK', 'Close', 'No thanks'];
            const buttons = Array.from(document.querySelectorAll('button, a, span'));
            for (const text of buttonText) {
                const btn = buttons.find(b => b.innerText && b.innerText.trim() === text);
                if (btn) {
                    btn.click();
                    console.log('Clicked: ' + text);
                }
            }
        }""")
        await self._human_delay(500, 1000)

    # ─── Login ────────────────────────────────────────────────────────────────

    async def login(self, username: str, password: str) -> bool:
        """
        Logs into Dice.com.

        MENTOR NOTE:
          Dice's login form is inside a React SPA.
          The page loads blank first, then React renders the form.
          We must wait for the form to appear, not just for DOM content loaded.

        Returns:
            True if login succeeded.
        """
        self._log_action("login", f"user={username}")

        # ── Try saved cookies first ──
        cookies_loaded = await self.load_cookies()
        if cookies_loaded:
            await self._page.goto(self.BASE_URL, wait_until="domcontentloaded")
            await self._wait_for_page_load()
            if await self._is_logged_in():
                self._log_action("login", "✅ Restored session via cookies")
                return True
            else:
                self._log_action("login", "⚠️ Cookies expired — fresh login")
                self.clear_cookies()

        # ── Fresh login ──
        try:
            await self._page.goto(self.LOGIN_URL, wait_until="domcontentloaded")
            await self._wait_for_page_load()
            await self._human_delay(2000, 3000)  # Wait for React to render

            # ── Handle Cookie Consent ──
            try:
                # Try clicking it
                await self._safe_click("button:has-text('Allow all')", timeout=3000)
                # If still there, hide it via JS so it doesn't block clicks
                await self._page.evaluate("""() => {
                    const banner = document.querySelector('#onetrust-banner-sdk') || 
                                   document.querySelector('.onetrust-pc-dark-filter');
                    if (banner) banner.style.display = 'none';
                    const pc = document.querySelector('#onetrust-pc-sdk');
                    if (pc) pc.style.display = 'none';
                }""")
            except Exception:
                pass

            # Check for CAPTCHA (Cloudflare)
            if await captcha_solver.detect_captcha(self._page):
                self._log_action("login", "⚠️ Cloudflare/CAPTCHA detected")
                solved = await captcha_solver.solve_and_submit(self._page)
                if not solved:
                    return False

            # Fill email
            email_ok = await self._safe_fill(
                "input[placeholder*='Email'], "
                "input[placeholder*='yourdomain.com'], "
                "input[type='email'], "
                "input[name='email'], "
                "input#email",
                username,
            )
            if not email_ok:
                await self._screenshot("dice_email_not_found")
                logger.error("[dice] Email field not found")
                return False

            await self._human_delay(500, 1000)

            # Click Continue
            await self._safe_click(
                "button[type='submit'], "
                "button:has-text('Continue with email')"
            )
            await self._wait_for_page_load()
            await self._human_delay(1000, 2000)

            # Fill password
            pw_ok = await self._safe_fill(
                "input[placeholder*='Password'], "
                "input[type='password'], "
                "input#password",
                password,
            )
            if not pw_ok:
                await self._screenshot("dice_password_not_found")
                logger.error("[dice] Password field not found")
                return False

            await self._human_delay(500, 1000)

            # Click Sign In
            await self._safe_click(
                "button[type='submit'], "
                "button:has-text('Sign In'), "
                "button:has-text('Log In')"
            )
            await self._wait_for_page_load(timeout=30000)
            await self._human_delay(5000, 7000) # Give more time for dashboard to load

            # Check if we are stuck on login page with an error
            error_el = await self._page.query_selector(".alert-danger, [data-cy='login-error']")
            if error_el:
                error_text = await error_el.inner_text()
                logger.error(f"[dice] Login error visible: {error_text}")

            if await self._is_logged_in():
                self._log_action("login", "✅ Login successful")
                await self.save_cookies()
                return True
            else:
                await self._screenshot("dice_login_failed")
                logger.error(f"[dice] Login failed for {username}")
                return False

        except Exception as e:
            await self._screenshot("dice_login_exception")
            logger.error(f"[dice] Login exception: {e}")
            return False

    async def _is_logged_in(self) -> bool:
        """Checks if we are logged into Dice."""
        try:
            # Dice shows user avatar/profile link when logged in
            indicators = [
                "a[href='/dashboard/profile']",
                "button[aria-label*='Profile']",
                "dhi-profile-bubble",
                "a[href*='/candidate/']",
                "button:has-text('Logout')",
                "a:has-text('Logout')",
                "dhi-user-menu",
            ]
            
            # Add dynamic name check if available
            name = self.user_data.get('name')
            if name:
                indicators.append(f"button:has-text('{name}')")
                indicators.append(f"span:has-text('{name}')")
            for sel in indicators:
                el = await self._page.query_selector(sel)
                if el:
                    return True

            # Check URL
            url = self._page.url.lower()
            if "/dashboard" in url and "login" not in url:
                return True
            if "dice.com/home" in url:
                return True

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
        Searches for jobs on Dice.com.

        Dice search URL format:
        /jobs#?q=KEYWORD&location=LOCATION&radius=30&radiusUnit=mi&page=1&pageSize=20

        Args:
            keywords: Tech skills/titles e.g. ["Python Developer", "AWS"]
            location: e.g. "Remote" or "New York, NY"
            max_results: How many listings to collect

        Returns:
            List of JobListing objects.
        """
        self._log_action("search_jobs", f"keywords={keywords} location={location}")

        jobs: list[JobListing] = []

        try:
            query = " ".join(keywords)
            params = {
                "q": query,
                "location": location,
                "radius": "30",
                "radiusUnit": "mi",
                "page": "1",
                "pageSize": "20",
                "filters.postedDate": "THREE_DAYS",
                "filters.employmentType": "FULLTIME",
            }
            search_url = f"{self.BASE_URL}/jobs?{urlencode(params)}"

            self._log_action("search_jobs", f"URL: {search_url}")
            await self._page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
            await self._wait_for_page_load()
            await self._human_delay(2000, 3000)

            jobs = await self._extract_job_cards(max_results)
            self._log_action("search_jobs", f"✅ Found {len(jobs)} jobs")
            return jobs

        except Exception as e:
            await self._screenshot("dice_search_exception")
            logger.error(f"[dice] search_jobs exception: {e}")
    async def _extract_job_cards(self, max_results: int) -> list[JobListing]:
        """Extracts job listings from Dice search results."""
        jobs = []

        try:
            # Debug info
            logger.debug(f"[dice] Current URL: {self._page.url}")
            logger.debug(f"[dice] Total frames: {len(self._page.frames)}")
            
            # Hide cookie banner
            await self._page.evaluate("document.querySelectorAll('#onetrust-banner-sdk, .onetrust-pc-dark-filter, #onetrust-pc-sdk').forEach(el => el.remove())")
            
            # Try to find ANY link
            all_links = self._page.locator("a")
            link_count = await all_links.count()
            logger.debug(f"[dice] Total 'a' tags on page: {link_count}")
            
            # Wait for job titles - [data-cy] is most reliable on Dice
            title_locator = self._page.locator(
                "[data-cy='card-title-link'], "
                "a[data-testid='job-search-job-detail-link'], "
                "a[data-testid='job-search-job-card-link'], "
                "a.card-title-link, "
                ".card-title-link"
            )
            
            try:
                await title_locator.first.wait_for(state="attached", timeout=15000)
            except Exception:
                await self._screenshot("dice_no_titles_timeout")
                logger.warning(f"[dice] No job titles found via data-cy. Trying fallback text search.")
                fallback_locator = self._page.locator("a:has-text('Analyst'), a:has-text('Developer'), a:has-text('Engineer')")
                if await fallback_locator.count() > 0:
                    title_locator = fallback_locator
                else:
                    return []

            count = await title_locator.count()
            self._log_action("_extract_job_cards", f"Found {count} job titles")

            title_locs = await title_locator.all()
            for loc in title_locs[:max_results]:
                try:
                    # Use evaluate to get all info at once - more robust and faster
                    card_info = await loc.evaluate("""(el) => {
                        const card = el.closest('dhi-search-card, [data-cy="card"], .card, dhi-job-search-card, div.search-card, [data-testid="job-card"]') || el.parentElement.parentElement.parentElement;
                        
                        const titleEl = card.querySelector('[data-cy="card-title-link"], [data-testid="job-search-job-detail-link"], a.card-title-link') || el;
                        const companyEl = card.querySelector('[data-cy="search-result-company-name"], .employer-name, a[href*="/company/"], a[href*="/company-profile/"], [data-testid="job-card-company-name"]');
                        const locationEl = card.querySelector('[data-cy="search-result-location"], .location, span.job-location, [data-testid="job-card-location"]');
                        
                        return {
                            title: titleEl.innerText?.trim() || el.innerText?.trim() || '',
                            company: companyEl?.innerText?.trim() || '',
                            location: locationEl?.innerText?.trim() || '',
                            href: titleEl.getAttribute('href') || el.getAttribute('href'),
                            is_easy_apply: !!card.querySelector('dhi-easy-apply-label, .easy-apply, [data-cy="easy-apply-label"]') || card.innerText.includes('Easy Apply')
                        };
                    }""")

                    if not card_info['href']:
                        continue
                        
                    title = card_info['title']
                    job_url = card_info['href'] if card_info['href'].startswith("http") else f"{self.BASE_URL}{card_info['href']}"

                    # If title is still empty, try to get it from the locator directly as fallback
                    if not title:
                        title = (await loc.inner_text()).strip()
                    
                    if not title:
                        continue

                    jobs.append(JobListing(
                        title=title,
                        company=card_info['company'],
                        job_url=job_url,
                        location=card_info['location'],
                        is_easy_apply=card_info['is_easy_apply'],
                        portal=self.PORTAL_NAME
                    ))
                except Exception as e:
                    logger.debug(f"[dice] Card parse error: {e}")
                    continue

            return jobs

        except Exception as e:
            await self._screenshot("dice_extract_exception")
            logger.error(f"[dice] _extract_job_cards exception: {e}")
            return []

    async def _parse_job_card(self, title_loc) -> Optional[JobListing]:
        # Deprecated: Logic moved into _extract_job_cards for efficiency
        return None

    async def get_job_description(self, job_url: str) -> str:
        """
        Opens a job listing page and extracts the full description text.
        Used to get description for AI matching (Phase 3).
        """
        try:
            await self._page.goto(job_url, wait_until="networkidle", timeout=30000)
            await self._wait_for_page_load()

            # Wait for any common content indicator
            try:
                await self._page.wait_for_selector("text=Summary, text=Description, text=Responsibilities", timeout=10000)
            except:
                pass

            # Use JS for extreme resilience in extraction
            desc_text = await self._page.evaluate("""() => {
                // 1. Try common containers
                const selectors = [
                    '[data-cy="jobDescription"]', 
                    '[data-cy="job-description"]', 
                    '#jobDescription', 
                    'section#jobDescription',
                    '.job-description', 
                    '.job-details',
                    '.description'
                ];
                for (const sel of selectors) {
                    const el = document.querySelector(sel);
                    if (el && el.innerText.trim().length > 200) return el.innerText.trim();
                }
                
                // 2. Fallback: find the largest text container that looks like a description
                const containers = Array.from(document.querySelectorAll('div, section, article'));
                const bestMatch = containers
                    .filter(c => (c.innerText.includes('Summary') || c.innerText.includes('Responsibilities')) && c.innerText.length > 300)
                    .sort((a, b) => b.innerText.length - a.innerText.length)[0];
                
                if (bestMatch) return bestMatch.innerText.trim();
                
                // 3. Last resort: just get the main content area text
                const main = document.querySelector('main') || document.body;
                return main.innerText.trim();
            }""")

            if desc_text and len(desc_text) > 100:
                return desc_text

        except Exception as e:
            await self._screenshot("dice_job_desc_failed")
            logger.debug(f"[dice] Could not get job description: {e}")

        return ""

    # ─── Apply to Job ─────────────────────────────────────────────────────────

    async def apply_job(
        self,
        job: JobListing,
        user_data: dict,
        dry_run: bool = False,
    ) -> ApplicationResult:
        """
        Applies to a Dice job.

        For Easy Apply jobs: one-click apply using saved Dice profile.
        For external jobs: skipped (would redirect off Dice).

        Returns:
            ApplicationResult with status 'applied', 'failed', or 'skipped'.
        """
        self._log_action("apply_job", f"'{job.title}' @ {job.company}")

        try:
            await self._page.goto(job.job_url, wait_until="domcontentloaded")
            await self._wait_for_page_load()
            await self._human_delay(1500, 2500)

            # Get description
            desc_el = await self._page.query_selector(
                "div.job-description, "
                "section[data-cy='jobDescription'], "
                "section[data-cy='job-description'], "
                "div#jobDescription"
            )
            if desc_el:
                job.description = (await desc_el.inner_text()).strip()[:3000]

            # Look for Easy Apply / internal Apply button
            easy_apply_btn = await self._page.query_selector(
                "button:has-text('Easy Apply'), "
                "button:has-text('Apply Now'), "
                "a:has-text('Apply Now'), "
                "a[data-testid='apply-button'], "
                "button[data-testid='apply-button'], "
                "apply-button-wc button[mode='primary']"
            )

            if easy_apply_btn:
                href = await easy_apply_btn.get_attribute("href")
                # If it's a relative link or points to dice.com, it's internal
                if href and not href.startswith("/") and "dice.com" not in href:
                    return ApplicationResult(
                        job=job,
                        status="skipped",
                        failure_reason="external_application_site",
                    )
                return await self._do_easy_apply(job, user_data, dry_run, easy_apply_btn)

            await self._screenshot("dice_apply_button_not_found")
            return ApplicationResult(
                job=job,
                status="failed",
                failure_reason="apply_button_not_found",
            )

        except Exception as e:
            await self._screenshot("dice_apply_exception")
            logger.error(f"[dice] apply_job exception: {e}")
            return ApplicationResult(
                job=job,
                status="failed",
                failure_reason=f"exception: {str(e)[:200]}",
            )

    async def _do_easy_apply(
        self,
        job: JobListing,
        user_data: dict,
        dry_run: bool,
        button,
    ) -> ApplicationResult:
        """
        Handles Dice's Easy Apply flow.
        Dice Easy Apply uses your saved profile — minimal form filling needed.
        """
        self._log_action("_do_easy_apply", f"'{job.title}'")

        try:
            if dry_run:
                self._log_action("_do_easy_apply", "🧪 DRY RUN — not clicking Easy Apply")
                return ApplicationResult(job=job, status="applied")

            await button.click()
            await self._wait_for_page_load()
            await self._human_delay(2000, 3000)

            # ── Phase 3: Smart AI-powered Form Filling ──
            # Some Dice Easy Apply jobs have a small modal with extra questions
            await self._smart_fill_form(user_data)

            # Dice Easy Apply often shows a confirmation modal
            confirm_btn = await self._page.query_selector(
                "button:has-text('Apply'), "
                "button:has-text('Submit Application'), "
                "button[data-cy='apply-button']"
            )
            if confirm_btn:
                await confirm_btn.click()
                await self._wait_for_page_load()
                await self._human_delay(1500, 2000)

            # Check for success message
            success_el = await self._page.query_selector(
                "h2:has-text('Application Submitted'), "
                "div:has-text('applied successfully'), "
                "dhi-application-confirmation"
            )

            if success_el or dry_run:
                self._log_action("_do_easy_apply", "✅ Easy Apply submitted")
                return ApplicationResult(job=job, status="applied")
            else:
                await self._screenshot("dice_easy_apply_no_confirm")
                return ApplicationResult(
                    job=job,
                    status="failed",
                    failure_reason="no_confirmation_after_easy_apply",
                )

        except Exception as e:
            logger.error(f"[dice] Easy Apply exception: {e}")
            return ApplicationResult(
                job=job,
                status="failed",
                failure_reason=f"easy_apply_exception: {str(e)[:200]}",
            )
