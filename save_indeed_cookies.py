import asyncio
from playwright.async_api import async_playwright
import json
import os

# Your specific user ID
USER_ID = "fed31086-c7ba-4259-adb7-b732b36586fb"
PORTAL = "indeed"
COOKIE_DIR = "./cookies"
PROFILE_DIR = "./browser_profile"

async def main():
    os.makedirs(COOKIE_DIR, exist_ok=True)
    os.makedirs(PROFILE_DIR, exist_ok=True)
    cookie_file = f"{COOKIE_DIR}/{USER_ID}_{PORTAL}.json"
    
    print("Starting persistent interactive browser...")
    async with async_playwright() as p:
        # Launch using a persistent context. This makes it look like a real user profile
        # and helps bypass Cloudflare blocks.
        context = await p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=False,
            viewport={"width": 1280, "height": 800},
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
            ]
        )
        
        # In a persistent context, a page is already open by default
        page = context.pages[0]
        
        # Apply stealth scripts manually just in case
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        print("Navigating to Indeed...")
        await page.goto("https://secure.indeed.com/auth")
        
        print("\n=======================================================")
        print("ACTION REQUIRED:")
        print("1. Cloudflare shouldn't block you this time.")
        print("2. Log into Indeed, enter your OTP.")
        print("3. Once you are logged in and on the Indeed homepage,")
        print("   come back to this terminal and press ENTER.")
        print("=======================================================\n")
        
        await asyncio.to_thread(input, "Press ENTER here AFTER you are logged in... ")
        
        print("Saving cookies...")
        cookies = await context.cookies()
        with open(cookie_file, "w") as f:
            json.dump(cookies, f)
            
        print(f"SUCCESS! Cookies saved to {cookie_file}")
        
        await context.close()

if __name__ == "__main__":
    asyncio.run(main())
