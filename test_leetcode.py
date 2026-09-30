import asyncio
from playwright.async_api import async_playwright
import sys

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir="/tmp/playwright_chrome_profile",
            headless=True,
            args=["--no-sandbox"]
        )
        page = browser.pages[0] if browser.pages else await browser.new_page()
        
        await page.goto("https://leetcode.com/problems/two-sum/")
        await asyncio.sleep(5)
        await page.screenshot(path="leetcode_screenshot.png")
        print("Screenshot saved to leetcode_screenshot.png")
        
        # Dump buttons
        buttons = await page.query_selector_all("button")
        for btn in buttons:
            text = await btn.inner_text()
            data_e2e = await btn.get_attribute("data-e2e-locator")
            if text and ("Submit" in text or "Run" in text):
                print(f"Button: text='{text}', data-e2e='{data_e2e}'")
                
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
