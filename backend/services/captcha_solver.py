"""
services/captcha_solver.py — CAPTCHA Detection & Solving
=========================================================
Handles CAPTCHA challenges encountered during browser automation.

MENTOR NOTE on CAPTCHAs:
  Job portals (especially LinkedIn and Indeed) use reCAPTCHA v2/v3
  and hCaptcha to block bots. We have two strategies:

  Strategy 1 (Primary): 2captcha.com API
    → Send the CAPTCHA challenge to a service with human solvers
    → They return a token in ~15-30 seconds
    → We inject the token into the page and submit

  Strategy 2 (Fallback): Pause and alert
    → If no 2captcha key is configured, log a warning
    → The task is marked as 'failed' with reason 'captcha_encountered'
    → Admin is notified (future: Slack/email notification)

  REAL WORLD WARNING:
    reCAPTCHA v3 gives a score (0.0=bot, 1.0=human). We can't solve
    it the same way. If v3 is blocking us, we may need residential
    proxies or a longer delay between actions.

Usage:
    from backend.services.captcha_solver import captcha_solver

    detected = await captcha_solver.detect_captcha(page)
    if detected:
        solved = await captcha_solver.solve_and_submit(page)
"""

import asyncio
from typing import Optional

from loguru import logger
from playwright.async_api import Page

from backend.config import settings


class CaptchaSolver:
    """
    Detects and solves CAPTCHAs encountered during browser automation.
    Uses the 2captcha.com API for solving.
    """

    # CSS selectors that indicate a CAPTCHA is present
    CAPTCHA_SELECTORS = [
        # reCAPTCHA v2 (the checkbox "I'm not a robot")
        "iframe[src*='recaptcha']",
        "div.g-recaptcha",
        "#recaptcha",

        # hCaptcha (used by LinkedIn)
        "iframe[src*='hcaptcha']",
        "div.h-captcha",

        # Generic CAPTCHA indicators
        "div[class*='captcha']",
        "div[id*='captcha']",
        "form[action*='captcha']",
    ]

    # Text phrases that indicate a CAPTCHA challenge page
    CAPTCHA_TEXT_INDICATORS = [
        "verify you're not a robot",
        "verify you are human",
        "complete the security check",
        "security verification",
        "prove you're not a robot",
        "i'm not a robot",
    ]

    def __init__(self):
        self.api_key = settings.twocaptcha_api_key
        self._has_api_key = bool(self.api_key and self.api_key.strip())

        if self._has_api_key:
            try:
                from twocaptcha import TwoCaptcha
                self._solver = TwoCaptcha(self.api_key)
                logger.info("CaptchaSolver initialized with 2captcha API key.")
            except ImportError:
                logger.warning(
                    "2captcha-python not installed. "
                    "Run: pip install 2captcha-python"
                )
                self._solver = None
                self._has_api_key = False
        else:
            self._solver = None
            logger.warning(
                "No TWOCAPTCHA_API_KEY in .env. "
                "CAPTCHA solving is DISABLED. "
                "Agent will pause and mark job as failed if CAPTCHA is hit. "
                "Sign up at 2captcha.com to enable solving."
            )

    # ─── Detection ────────────────────────────────────────────────────────────

    async def detect_captcha(self, page: Page) -> str | None:
        """
        Checks if the current page has a CAPTCHA challenge.

        Returns:
            'recaptcha' | 'hcaptcha' | 'unknown' if CAPTCHA detected,
            None if no CAPTCHA found.

        MENTOR NOTE:
          We check both DOM elements (CSS selectors) AND page text.
          Text check catches CAPTCHA challenges that redirect to a new page.
        """
        # Check for iframe-based CAPTCHAs
        for selector in self.CAPTCHA_SELECTORS:
            try:
                element = await page.query_selector(selector)
                if element:
                    captcha_type = self._identify_type(selector)
                    logger.warning(
                        f"CaptchaSolver: Detected {captcha_type} via selector '{selector}'"
                    )
                    return captcha_type
            except Exception:
                continue

        # Check page text for CAPTCHA-related phrases
        try:
            page_text = (await page.inner_text("body")).lower()
            for phrase in self.CAPTCHA_TEXT_INDICATORS:
                if phrase in page_text:
                    logger.warning(
                        f"CaptchaSolver: Detected CAPTCHA via text match: '{phrase}'"
                    )
                    return "unknown"
        except Exception:
            pass

        return None  # No CAPTCHA detected

    def _identify_type(self, selector: str) -> str:
        """Returns 'recaptcha', 'hcaptcha', or 'unknown' based on selector."""
        if "recaptcha" in selector:
            return "recaptcha"
        if "hcaptcha" in selector:
            return "hcaptcha"
        return "unknown"

    # ─── Solving ──────────────────────────────────────────────────────────────

    async def solve_and_submit(self, page: Page) -> bool:
        """
        Main entry point: detects CAPTCHA type and solves it.

        Args:
            page: The current Playwright page.

        Returns:
            True if CAPTCHA was solved and submitted, False otherwise.

        MENTOR NOTE:
          The flow for solving reCAPTCHA v2:
          1. Find the sitekey from the page HTML
          2. Send URL + sitekey to 2captcha → they return a g-recaptcha-response token
          3. Inject the token into the hidden textarea on the page
          4. Trigger the form submit callback
          This works because the validation server only checks the token, not how it was entered.
        """
        if not self._has_api_key:
            logger.error(
                "CaptchaSolver: Cannot solve CAPTCHA — no 2captcha API key configured. "
                "Set TWOCAPTCHA_API_KEY in .env"
            )
            return False

        captcha_type = await self.detect_captcha(page)
        if not captcha_type:
            logger.info("CaptchaSolver: No CAPTCHA detected, nothing to solve.")
            return True

        current_url = page.url
        logger.info(f"CaptchaSolver: Attempting to solve {captcha_type} on {current_url}")

        try:
            if captcha_type == "recaptcha":
                return await self._solve_recaptcha(page, current_url)
            elif captcha_type == "hcaptcha":
                return await self._solve_hcaptcha(page, current_url)
            else:
                logger.warning(
                    f"CaptchaSolver: Unknown CAPTCHA type '{captcha_type}'. "
                    "Cannot solve automatically."
                )
                return False

        except Exception as e:
            logger.error(f"CaptchaSolver: Exception during solving: {e}")
            return False

    async def _solve_recaptcha(self, page: Page, url: str) -> bool:
        """
        Solves reCAPTCHA v2 using 2captcha API.

        Steps:
        1. Extract sitekey from the page
        2. Send to 2captcha
        3. Inject token + trigger callback
        """
        # Step 1: Extract the sitekey from the reCAPTCHA iframe or div
        sitekey = await self._extract_recaptcha_sitekey(page)
        if not sitekey:
            logger.error("CaptchaSolver: Could not extract reCAPTCHA sitekey.")
            return False

        logger.info(f"CaptchaSolver: Got reCAPTCHA sitekey: {sitekey[:20]}...")

        # Step 2: Send to 2captcha and wait for solution
        # This typically takes 15-45 seconds (a human is solving it)
        logger.info("CaptchaSolver: Sending to 2captcha API... (waiting up to 90s)")
        try:
            result = await asyncio.to_thread(
                self._solver.recaptcha,
                sitekey=sitekey,
                url=url,
            )
            token = result["code"]
            logger.success(f"CaptchaSolver: Got reCAPTCHA solution token: {token[:20]}...")
        except Exception as e:
            logger.error(f"CaptchaSolver: 2captcha API error: {e}")
            return False

        # Step 3: Inject token into the page and trigger callback
        return await self._inject_recaptcha_token(page, token)

    async def _solve_hcaptcha(self, page: Page, url: str) -> bool:
        """
        Solves hCaptcha using 2captcha API.
        hCaptcha is used by LinkedIn and some Indeed pages.
        """
        # Extract hCaptcha sitekey
        sitekey = await page.evaluate(
            "document.querySelector('[data-sitekey]')?.getAttribute('data-sitekey')"
        )
        if not sitekey:
            logger.error("CaptchaSolver: Could not extract hCaptcha sitekey.")
            return False

        logger.info(f"CaptchaSolver: Got hCaptcha sitekey: {sitekey[:20]}...")

        try:
            result = await asyncio.to_thread(
                self._solver.hcaptcha,
                sitekey=sitekey,
                url=url,
            )
            token = result["code"]
            logger.success(f"CaptchaSolver: Got hCaptcha solution token: {token[:20]}...")
        except Exception as e:
            logger.error(f"CaptchaSolver: 2captcha hCaptcha API error: {e}")
            return False

        # Inject hCaptcha response token
        await page.evaluate(
            f"""
            document.querySelector('[name="h-captcha-response"]').value = '{token}';
            document.querySelector('[name="g-recaptcha-response"]') &&
                (document.querySelector('[name="g-recaptcha-response"]').value = '{token}');
            """
        )
        logger.success("CaptchaSolver: hCaptcha token injected.")
        return True

    async def _extract_recaptcha_sitekey(self, page: Page) -> Optional[str]:
        """
        Extracts the reCAPTCHA sitekey from the page.
        Tries multiple methods because portals embed it differently.
        """
        # Method 1: data-sitekey attribute on div
        sitekey = await page.evaluate(
            "document.querySelector('.g-recaptcha, [data-sitekey]')?.getAttribute('data-sitekey')"
        )
        if sitekey:
            return sitekey

        # Method 2: sitekey in iframe src URL
        try:
            iframe = await page.query_selector("iframe[src*='recaptcha']")
            if iframe:
                src = await iframe.get_attribute("src")
                if src and "k=" in src:
                    # Extract k parameter: ...&k=SITEKEY&...
                    key = src.split("k=")[1].split("&")[0]
                    return key
        except Exception:
            pass

        # Method 3: Extract from page source
        try:
            content = await page.content()
            if "grecaptcha.render" in content:
                import re
                match = re.search(r"'sitekey'\s*:\s*'([^']+)'", content)
                if match:
                    return match.group(1)
        except Exception:
            pass

        return None

    async def _inject_recaptcha_token(self, page: Page, token: str) -> bool:
        """
        Injects the solved reCAPTCHA token into the page and triggers submission.

        MENTOR NOTE:
          The reCAPTCHA widget has a hidden textarea with the token.
          The validation script watches this textarea.
          We inject the token → trigger the change event → the form unlocks.
        """
        try:
            await page.evaluate(
                f"""
                // Set the token in the hidden textarea
                document.getElementById('g-recaptcha-response').innerHTML = '{token}';

                // Trigger the reCAPTCHA callback if available
                if (typeof ___grecaptcha_cfg !== 'undefined') {{
                    Object.entries(___grecaptcha_cfg.clients).forEach(([key, client]) => {{
                        const callback = client?.callback;
                        if (callback && typeof callback === 'function') {{
                            callback('{token}');
                        }}
                    }});
                }}
                """
            )
            logger.success("CaptchaSolver: reCAPTCHA token injected and callback triggered.")

            # Wait a moment for the page to process the token
            await asyncio.sleep(2)
            return True

        except Exception as e:
            logger.error(f"CaptchaSolver: Failed to inject reCAPTCHA token: {e}")
            return False


# ─── Singleton Instance ───────────────────────────────────────────────────────
# Import this throughout the app — don't create new instances
captcha_solver = CaptchaSolver()
