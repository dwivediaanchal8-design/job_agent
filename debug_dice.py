import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        print("Navigating to Dice...")
        await page.goto("https://www.dice.com/jobs?q=Data+Analyst&location=Remote")
        await page.wait_for_timeout(5000)
        
        print("Extracting elements...")
        # Get all tags
        tags = await page.evaluate("""() => {
            const counts = {};
            document.querySelectorAll('*').forEach(el => {
                const tag = el.tagName.toLowerCase();
                counts[tag] = (counts[tag] || 0) + 1;
            });
            return counts;
        }""")
        print(f"Tag counts: {tags}")
        
        # Check for card title links
        links = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('a')).filter(a => a.className.includes('card-title-link')).map(a => ({
                text: a.innerText,
                class: a.className,
                html: a.outerHTML.substring(0, 100)
            }));
        }""")
        print(f"Found {len(links)} card-title-link elements in main document")
        
        # Check iframes
        iframes = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('iframe')).map(f => ({
                src: f.src,
                id: f.id,
                name: f.name
            }));
        }""")
        print(f"Found {len(iframes)} iframes:")
        for f in iframes:
            print(f"  - {f['src']}")

        # Save content
        content = await page.content()
        with open("dice_debug.html", "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Saved {len(content)} bytes to dice_debug.html")
        
        # Check if the string exists in raw content
        if "card-title-link" in content:
            print("SUCCESS: 'card-title-link' found in raw HTML!")
        else:
            print("FAILURE: 'card-title-link' NOT found in raw HTML.")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
