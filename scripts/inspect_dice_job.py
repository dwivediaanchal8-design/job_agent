import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://www.dice.com/job-detail/b800f6fd-95bd-45fb-ad65-54c5fa0d40a2", wait_until="networkidle")
        
        # Look for the apply button
        buttons = await page.evaluate("""() => {
            const els = Array.from(document.querySelectorAll('button, a, apply-button-wc'));
            return els.filter(el => el.innerText && (el.innerText.toLowerCase().includes('apply') || el.innerText.toLowerCase().includes('easy apply'))).map(el => el.outerHTML);
        }""")
        
        print("Found matching elements:")
        for b in buttons:
            print(b)
            print("---")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
