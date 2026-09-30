import asyncio
import os
import json
import urllib.request
import ssl
from playwright.async_api import async_playwright
from dotenv import load_dotenv

load_dotenv()

import re

async def generate_solution_with_groq(problem_text: str, starter_code: str, previous_error: str = None, previous_code: str = None) -> str:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("Missing API key. Please run: export GOOGLE_API_KEY='gsk_...'")
        return ""
        
    if previous_error and previous_code:
        prompt = f"""
        You are an expert competitive programmer. 
        I tried solving the following LeetCode problem with this Python code:
        
        {previous_code}
        
        However, the submission failed with the following result/error:
        {previous_error}
        
        Please provide the corrected Python code.
        You MUST complete the starter code template exactly in the language provided.
        Provide ONLY the raw code. Do not include markdown code blocks.
        Do not explain the code. Just provide the raw completed code.
        
        Problem Statement:
        {problem_text}
        
        Starter Code:
        {starter_code}
        """
    else:
        prompt = f"""
        You are an expert competitive programmer. 
        Solve the following LeetCode problem.
        I will provide the problem statement and the starter code template.
        You MUST complete the starter code template exactly in the language provided.
        Provide ONLY the raw code. Do not include markdown code blocks.
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
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    import time
    for attempt in range(5):
        try:
            resp = urllib.request.urlopen(req, context=ctx)
            response_data = json.loads(resp.read())
            code = response_data['choices'][0]['message']['content']
            # Robustly strip markdown code blocks
            code = re.sub(r"^```[a-zA-Z0-9]*\n?", "", code.strip())
            code = re.sub(r"\n?```$", "", code)
            return code.strip()
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait_time = 15 * (attempt + 1)
                print(f"Rate limited by Groq (429). Waiting {wait_time} seconds before retrying...")
                time.sleep(wait_time)
            else:
                print(f"Failed to generate code: HTTP Error {e.code}: {e.reason}")
                return ""
        except Exception as e:
            print(f"Failed to generate code: {e}")
            return ""
            
    print("Failed to get code from Groq after multiple retries due to rate limits.")
    return ""

import sys
is_mac = sys.platform == "darwin"
modifier = "Meta" if is_mac else "Control"

async def solve_current_problem(page, context):
    print(f"\n--- Solving Problem: {page.url} ---")
    try:
        # Wait for description to load
        print("Waiting for problem description to load...")
        desc_element = await page.wait_for_selector('div[data-track-load="description_content"]', timeout=30000)
        problem_text = await desc_element.inner_text()
        print(f"Extracted {len(problem_text)} characters from description.")
        
        # Click on editor to focus and extract the starter code template
        print("Extracting starter code template...")
        try:
            await page.evaluate("document.querySelector('.monaco-editor').scrollIntoView()")
        except:
            pass
        await page.click('.monaco-editor', force=True)
        await asyncio.sleep(0.5)
        await page.keyboard.press(f"{modifier}+A")
        await page.keyboard.press(f"{modifier}+C")
        
        # Read the starter code from clipboard
        await context.grant_permissions(['clipboard-read', 'clipboard-write'])
        starter_code = await page.evaluate("async () => await navigator.clipboard.readText()")
        print(f"Extracted starter code ({len(starter_code)} chars). Asking Groq for the solution...")
        
        # Generate code
        previous_code = None
        previous_error = None
        
        for attempt in range(3):
            if attempt > 0:
                print(f"\n--- Self-Correction Attempt {attempt} ---")
                
            code = await generate_solution_with_groq(problem_text, starter_code, previous_error, previous_code)
            if not code:
                print("Failed to get code from Groq.")
                return False
                
            print("Code generated successfully! Injecting into editor...")
            
            # Delete the existing code
            try:
                await page.evaluate("document.querySelector('.monaco-editor').scrollIntoView()")
            except:
                pass
            await page.click('.monaco-editor', force=True)
            await asyncio.sleep(0.5)
            await page.keyboard.press(f"{modifier}+A")
            await page.keyboard.press("Backspace")
            
            # Paste code
            print("Pasting code...")
            await context.grant_permissions(['clipboard-read', 'clipboard-write'])
            await page.evaluate("async (text) => { await navigator.clipboard.writeText(text); }", code)
            await page.keyboard.press(f"{modifier}+V")
            
            await asyncio.sleep(2)  # Give the editor and UI a moment to process the paste
            
            # Submit
            print("Submitting code...")
            try:
                # Force click the actual submit button (green button with cloud icon)
                submit_btn = page.locator('button:has-text("Submit")')
                await submit_btn.first.click(force=True)
            except Exception as e:
                # Fallback to keyboard shortcut
                print("Button click failed, using keyboard shortcut...")
                try:
                    await page.evaluate("document.querySelector('.monaco-editor').scrollIntoView()")
                except:
                    pass
                await page.click('.monaco-editor', force=True)
                await page.keyboard.press(f"{modifier}+Enter")
            
            print("Waiting for result (Acceptance)...")
            # Wait up to 25 seconds for the result
            try:
                # Look for the submission result element specifically
                result_element = await page.wait_for_selector(
                    '[data-e2e-locator="submission-result"], [data-e2e-locator="console-result"]', 
                    timeout=25000
                )
                
                if result_element:
                    result_text = await result_element.inner_text()
                    # Use in to do partial matching instead of strict equality
                    if "Accepted" in result_text:
                        print("✅ Problem Solved Successfully!")
                        return True
                    else:
                        print(f"❌ Submission failed. Result: {result_text}")
                        # Prepare for next attempt
                        previous_code = code
                        previous_error = result_text
                        await asyncio.sleep(2)
                        continue
            except:
                print("❌ Did not see a submission result in time. Moving on anyway.")
                try:
                    await page.screenshot(path="timeout_screenshot.png")
                    print("Saved a screenshot to 'timeout_screenshot.png' in this folder. Please stop the script (Ctrl+C) and open that image!")
                except:
                    pass
                return False
                
        print("❌ Failed after 3 self-correction attempts. Moving on.")
        return False
            
    except Exception as e:
        print(f"Error solving problem: {e}")
        return False


async def get_unsolved_problems(page, count: int):
    print(f"Extracting up to {count} problems from the problem set...")
    
    problems = []
    
    while len(problems) < count:
        try:
            # Wait for the problem links to appear
            selector = 'a[href^="/problems/"]'
            await page.wait_for_selector(selector, timeout=10000)
            
            # Get all problem links on the page
            links = await page.query_selector_all(selector)
            
            for link in links:
                href = await link.get_attribute('href')
                if href and "/problems/" in href and "/solution" not in href:
                    # Clean the URL to strictly prevent duplicates
                    full_url = f"https://leetcode.com{href}"
                    full_url = full_url.split("?")[0] # Remove any ?envType parameters
                    full_url = full_url.rstrip('/')   # Remove trailing slashes
                    
                    if full_url not in problems:
                        problems.append(full_url)
                        
                    if len(problems) >= count:
                        break
        except:
            print("Could not find any problem links on this page.")
            break
            
        if len(problems) >= count:
            break
            
        # If we need more problems, try to click the "Next" page button
        try:
            # Scroll to bottom of the page to ensure the pagination is rendered
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1)
            
            # The next button on LeetCode typically uses aria-label
            next_btn = await page.query_selector('nav button[aria-label="next"], button[aria-label="Next"]')
            if next_btn:
                # Check if it's disabled (we are on the last page)
                is_disabled = await next_btn.get_attribute('disabled')
                if is_disabled is not None:
                    print("Reached the last page of problems.")
                    break
                    
                print(f"Gathered {len(problems)} problems so far. Clicking 'Next Page' for more...")
                await next_btn.click(force=True)
                await asyncio.sleep(4) # Wait for table to load
            else:
                print("Could not find a Next Page button. Stopping extraction here.")
                break
        except Exception as e:
            print("Could not navigate to next page.")
            break
            
    return problems


async def main():
    print("=== LeetCode Autonomous Batch Solver ===")
    
    # 1. Get User Input
    try:
        skip_count = int(input("Enter number of problems to SKIP (e.g., 500): ").strip())
        count = int(input("Enter number of problems to solve: ").strip())
    except:
        skip_count = 0
        count = 1
        print(f"Invalid input. Defaulting to skip 0, solve {count} problem.")
    
    profile_dir = os.path.join(os.getcwd(), "chrome_profile")
    
    async with async_playwright() as p:
        try:
            print("\nLaunching browser...")
            context = await p.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                headless=False,
                channel="chrome",
                args=['--disable-blink-features=AutomationControlled']
            )
            
            page = context.pages[0] if context.pages else await context.new_page()
            
            print("Navigating to LeetCode Problemset...")
            await page.goto("https://leetcode.com/problemset/", timeout=0, wait_until="domcontentloaded")
            
            # Wait for user to log in and apply filters
            print("\n*** ACTION REQUIRED ***")
            print("1. Please log in to LeetCode if you are not already logged in.")
            print("2. Use the LeetCode website to MANUALLY apply any filters you want (e.g. Medium, Todo).")
            print("3. When you see the problems you want to solve on the screen, press ENTER here!")
            input("\nPress ENTER in this terminal when you are ready to start solving...")
            
            print(f"\n--- Starting Batch Solving (Skipping first {skip_count} problems) ---")
            
            # Extract enough problems to skip the first ones and still have enough to solve
            total_to_extract = skip_count + count
            problem_urls = await get_unsolved_problems(page, total_to_extract)
            
            # Slice off the skipped problems
            problem_urls = problem_urls[skip_count:]
            
            print(f"Found {len(problem_urls)} problems to solve:")
            for url in problem_urls:
                print(f"- {url}")
                
            for url in problem_urls:
                await page.goto(url, timeout=0, wait_until="domcontentloaded")
                # Wait a moment for page to stabilize
                await asyncio.sleep(3)
                await solve_current_problem(page, context)
                
            print("\n=== Batch Processing Complete! ===")
            await asyncio.sleep(10) # Wait a bit before closing
            
        except Exception as e:
            print(f"Critical Error: {e}")
        finally:
            if 'context' in locals():
                await context.close()

if __name__ == "__main__":
    asyncio.run(main())
