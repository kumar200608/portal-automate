import asyncio
import os
import json
import urllib.request
from playwright.async_api import async_playwright
from dotenv import load_dotenv

load_dotenv()

async def generate_solution_with_groq(problem_text: str, starter_code: str) -> str:
    api_key = os.getenv("GOOGLE_API_KEY") # You put your Groq key here
    if not api_key:
        print("Missing API key. Please run: export GOOGLE_API_KEY='gsk_...'")
        return ""
        
    prompt = f"""
    You are an expert competitive programmer. 
    Solve the following LeetCode problem.
    I will provide the problem statement and the starter code template.
    You MUST complete the starter code template in the SAME programming language it is written in.
    Provide ONLY the raw code. Do not include markdown code blocks (e.g. no ```cpp or ```java).
    Do not explain the code. Just provide the raw completed code.
    
    Problem Statement:
    {problem_text}
    
    Starter Code:
    {starter_code}
    """
    
    data = {
        "model": "qwen/qwen3.8-27b",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0
    }
    
    req = urllib.request.Request(
        'https://api.groq.com/openai/v1/chat/completions',
        data=json.dumps(data).encode('utf-8'),
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
    )
    
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    try:
        resp = urllib.request.urlopen(req, context=ctx)
        response_data = json.loads(resp.read())
        code = response_data['choices'][0]['message']['content']
        # Clean up in case it output markdown
        if code.startswith("```python"):
            code = code[9:]
        if code.startswith("```"):
            code = code[3:]
        if code.endswith("```"):
            code = code[:-3]
        return code.strip()
    except urllib.error.HTTPError as e:
        print(f"Failed to generate code: HTTP Error {e.code}: {e.reason}")
        print(f"Error details: {e.read().decode('utf-8')}")
        return ""
    except Exception as e:
        print(f"Failed to generate code: {e}")
        return ""

async def main():
    print("=== LeetCode Direct Solver ===")
    
    # We will use a local folder for the Chrome profile so you stay logged in 
    # without interfering with your main Chrome browser!
    profile_dir = os.path.join(os.getcwd(), "chrome_profile")
    
    async with async_playwright() as p:
        try:
            print("Launching browser...")
            # Launch persistent context
            context = await p.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                headless=False,
                channel="chrome", # Use actual chrome
                args=['--disable-blink-features=AutomationControlled']
            )
            
            page = context.pages[0] if context.pages else await context.new_page()
            
            print("Navigating to LeetCode...")
            await page.goto("https://leetcode.com/problemset/")
            
            print("\n*** IMPORTANT ***")
            print("If you are not logged in, please log in now in the browser window.")
            print("Then, click on ANY unsolved problem to open the code editor.")
            print("Waiting until you are on a problem page...\n")
            
            # Wait for the user to navigate to a problem page manually
            while "leetcode.com/problems/" not in page.url:
                await asyncio.sleep(2)
                
            print(f"Detected problem page: {page.url}")
            print("Waiting for problem description to load...")
            
            # Extract problem description
            desc_element = await page.wait_for_selector('div[data-track-load="description_content"]', timeout=30000)
            problem_text = await desc_element.inner_text()
            print(f"Extracted {len(problem_text)} characters from description.")
            
            # Click on editor to focus and extract the starter code template
            print("Extracting starter code template...")
            await page.click('.monaco-editor')
            await asyncio.sleep(0.5)
            await page.keyboard.press("Meta+A")
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Meta+C")
            await page.keyboard.press("Control+C")
            
            # Read the starter code from clipboard
            await context.grant_permissions(['clipboard-read', 'clipboard-write'])
            starter_code = await page.evaluate("async () => await navigator.clipboard.readText()")
            print(f"Extracted starter code ({len(starter_code)} chars). Asking Groq to solve in the matching language...")
            
            # Generate code
            code = await generate_solution_with_groq(problem_text, starter_code)
            if not code:
                print("Failed to get code from Groq.")
                return
                
            print("Code generated successfully! Injecting into editor...")
            
            # Delete the existing code
            await page.keyboard.press("Backspace")
            
            # Type code using clipboard to avoid Monaco auto-indentation double-spacing
            print("Pasting code...")
            # Use real clipboard paste
            await context.grant_permissions(['clipboard-read', 'clipboard-write'])
            await page.evaluate("async (text) => { await navigator.clipboard.writeText(text); }", code)
            await page.keyboard.press("Meta+V")
            
            await asyncio.sleep(1)
            
            # Submit
            print("Clicking submit...")
            # Try specific LeetCode submit button selectors
            submit_selectors = [
                '[data-e2e-locator="console-submit-button"]',
                'button:has-text("Submit")'
            ]
            
            clicked = False
            for selector in submit_selectors:
                try:
                    submit_btn = await page.wait_for_selector(selector, timeout=2000)
                    if submit_btn:
                        await submit_btn.click()
                        clicked = True
                        break
                except:
                    continue
                    
            if not clicked:
                print("Could not find Submit button! You may need to click it manually.")
            
            print("Taking debug screenshot...")
            await asyncio.sleep(2)
            await page.screenshot(path="debug_screenshot.png")
            
            print("Done! Check your browser for the result.")
            
            # Keep browser open for a few seconds to see result
            await asyncio.sleep(10)
            
        except Exception as e:
            print(f"Error: {e}")
        finally:
            # Need to close the context to free the profile lock
            if 'context' in locals():
                await context.close()

if __name__ == "__main__":
    asyncio.run(main())
