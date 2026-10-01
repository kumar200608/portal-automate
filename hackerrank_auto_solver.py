import asyncio
import os
import json
import urllib.request
import ssl
import sys
import time
import re
from playwright.async_api import async_playwright
from dotenv import load_dotenv

load_dotenv()

is_mac = sys.platform == "darwin"
modifier = "Meta" if is_mac else "Control"

async def generate_solution_with_groq(problem_text: str, starter_code: str, previous_error: str = None, previous_code: str = None) -> str:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("Missing API key. Please run: export GROQ_API_KEY='gsk_...'")
        return ""
        
    if previous_error and previous_code:
        prompt = f"""
        You are an expert Python competitive programmer. 
        I tried solving the following HackerRank Python problem with this code:
        
        {previous_code}
        
        However, the submission failed with the following result/error:
        {previous_error}
        
        Please provide the corrected Python 3 code.
        You MUST complete the starter code template exactly in the language provided.
        Provide ONLY the raw code. Do not include markdown code blocks.
        Do not explain the code. Just provide the raw completed code.
        CRITICAL: Do NOT use any non-ASCII characters (like °). If you need special characters, use chr(176) or similar.
        
        Problem Statement:
        {problem_text}
        
        Starter Code:
        {starter_code}
        """
    else:
        prompt = f"""
        You are an expert Python competitive programmer. 
        Solve the following HackerRank Python problem.
        I will provide the problem statement and the starter code template.
        You MUST complete the starter code template exactly in the language provided (Python 3).
        Provide ONLY the raw code. Do not include markdown code blocks.
        Do not explain the code. Just provide the raw completed code.
        CRITICAL: Do NOT use any non-ASCII characters (like °). If you need special characters, use chr(176) or similar.
        
        Problem Statement:
        {problem_text}
        
        Starter Code:
        {starter_code}
        """
    
    data = {
        "model": "openai/gpt-oss-120b",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0
    }
    
    req = urllib.request.Request(
        'https://api.groq.com/openai/v1/chat/completions',
        data=json.dumps(data).encode('utf-8'),
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
        }
    )
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    for attempt in range(5):
        try:
            resp = urllib.request.urlopen(req, context=ctx)
            response_data = json.loads(resp.read())
            if 'choices' in response_data and len(response_data['choices']) > 0:
                code = response_data['choices'][0]['message']['content']
                # Robustly strip markdown code blocks
                code = re.sub(r"^```[a-zA-Z0-9]*\n?", "", code.strip())
                code = re.sub(r"\n?```$", "", code)
                return code.strip()
            else:
                print(f"Unexpected Groq response format: {response_data}")
                return ""
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait_time = 15 * (attempt + 1)
                print(f"Rate limited by Groq (429). Waiting {wait_time} seconds before retrying...")
                time.sleep(wait_time)
            else:
                print(f"Failed to generate code: HTTP Error {e.code}: {e.reason}")
                try:
                    print(e.read().decode())
                except:
                    pass
                return ""
        except Exception as e:
            print(f"Failed to generate code: {e}")
            return ""
            
    print("Failed to get code from Groq after multiple retries due to rate limits.")
    return ""


async def solve_current_problem(page, context):
    print(f"\n--- Solving Problem: {page.url} ---")
    try:
        # Wait for description to load
        print("Waiting for problem description to load...")
        # HackerRank descriptions are usually in .challenge-body-html
        desc_element = await page.wait_for_selector('.challenge-body-html', timeout=30000)
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
        try:
            await page.click('.view-lines', force=True)
        except:
            pass
        await asyncio.sleep(0.2)
        await page.keyboard.press(f"{modifier}+a")
        await page.keyboard.press(f"{modifier}+c")
        
        # Read the starter code from clipboard
        await context.grant_permissions(['clipboard-read', 'clipboard-write'])
        starter_code = await page.evaluate("async () => await navigator.clipboard.readText()")
        print(f"Extracted starter code ({len(starter_code)} chars). Asking Groq for the solution...")
        
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
            
            # The most reliable way to set Monaco editor value is to aggressively update ALL models
            success = await page.evaluate('''async (codeText) => { 
                try {
                    let updated = false;
                    if (window.monaco && window.monaco.editor) {
                        // 1. Update all active editor instances
                        let editors = window.monaco.editor.getEditors();
                        if (editors && editors.length > 0) {
                            for (let e of editors) {
                                e.setValue(codeText);
                                updated = true;
                            }
                        }
                        
                        // 2. Update all underlying models just to be absolutely sure
                        let models = window.monaco.editor.getModels();
                        if (models && models.length > 0) {
                            for (let m of models) {
                                m.setValue(codeText);
                                updated = true;
                            }
                        }
                    }
                    return updated;
                } catch(e) {
                    return false;
                }
            }''', code)
            
            if not success:
                print("Monaco API failed, falling back to keyboard paste...")
                # Fallback pasting
                try:
                    await page.click('.monaco-editor', force=True)
                    await asyncio.sleep(0.5)
                    await page.click('.view-lines', force=True)
                except Exception:
                    pass
                
                await asyncio.sleep(0.5)
                # First delete using standard shortcuts
                await page.keyboard.press(f"{modifier}+a")
                await asyncio.sleep(0.2)
                await page.keyboard.press("Backspace")
                await asyncio.sleep(0.2)
                
                # Next, try to completely clear it via JavaScript clipboard
                # just in case the above still didn't delete it
                await page.evaluate('''async (codeText) => {
                    await navigator.clipboard.writeText(codeText);
                }''', code)
                
                # Use insert_text as primary injection method since it's robust against clipboard issues
                await page.keyboard.insert_text(code)
                await asyncio.sleep(1) 
                
                # As a final measure, press paste just in case insert_text fails on Monaco
                await page.keyboard.press(f"{modifier}+v")
                await asyncio.sleep(1) 
            
            print("Submitting code...")
            try:
                # HackerRank Submit Code button
                submit_btn = page.locator('button:has-text("Submit Code")')
                await submit_btn.first.click(force=True)
            except Exception as e:
                print("Button click failed, using keyboard shortcut...")
                await page.click('.monaco-editor', force=True)
                await page.keyboard.press(f"{modifier}+Enter")
            
            print("Waiting for result (Acceptance)...")
            
            # HackerRank has a compilation/running phase, so we wait longer
            start_time = time.time()
            success = False
            while time.time() - start_time < 30:
                await asyncio.sleep(2)
                
                # HackerRank results typically appear with this class
                response_el = await page.query_selector('.challenge-response')
                if response_el:
                    response_text = await response_el.inner_text()
                    
                    if "Congratulations" in response_text or "Accepted" in response_text or "Success" in response_text:
                        print("✅ Problem Solved Successfully!")
                        return True
                    
                    # Check for actual failure states (ignore "Started", "Running Testcases", etc)
                    failure_keywords = ["Wrong Answer", "Runtime Error", "Compilation error", "Terminated due to timeout", "Failed"]
                    if any(keyword in response_text for keyword in failure_keywords):
                        error_text = response_text
                        # Try to get compiler message or testcase output
                        compile_message = await page.query_selector('.compiler-message')
                        if compile_message:
                            error_text += "\n" + await compile_message.inner_text()
                            
                        print(f"❌ Submission failed. Result: {error_text}")
                        previous_code = code
                        previous_error = error_text
                        break # Break out of inner while to retry attempt
                    # If it's none of the above, it's probably still running ("Started", "Running", etc), so we just keep waiting in the loop!
            else:
                print("❌ Did not see a submission result in time. Moving on anyway.")
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
            # HackerRank challenges link
            selector = 'a[href*="/challenges/"]'
            await page.wait_for_selector(selector, timeout=10000)
            
            links = await page.query_selector_all(selector)
            
            for link in links:
                href = await link.get_attribute('href')
                if href and "/challenges/" in href and "/problem" in href:
                    full_url = f"https://www.hackerrank.com{href}"
                    full_url = full_url.split("?")[0] 
                    if full_url not in problems:
                        problems.append(full_url)
                        
                    if len(problems) >= count:
                        break
        except:
            print("Could not find any problem links on this page.")
            break
            
        if len(problems) >= count:
            break
            
        try:
            # Scroll to bottom
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1)
            
            # Next button typically in pagination
            next_btn = await page.query_selector('a[data-attr1="Right"], a[data-attr8="Right"], .pagination li:last-child a')
            if next_btn:
                # check if disabled
                is_disabled = await page.evaluate("(el) => el.parentElement && el.parentElement.classList.contains('disabled')", next_btn)
                if is_disabled:
                    print("Reached the last page of problems.")
                    break
                    
                print(f"Gathered {len(problems)} problems so far. Clicking 'Next Page' for more...")
                await next_btn.click(force=True)
                await asyncio.sleep(4) 
            else:
                print("Could not find a Next Page button. Stopping extraction here.")
                break
        except Exception as e:
            print(f"Could not navigate to next page: {e}")
            break
            
    return problems


async def main():
    print("=== HackerRank Autonomous Batch Solver ===")
    
    try:
        skip_count = int(input("Enter number of problems to SKIP (e.g., 0): ").strip())
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
            
            print("Navigating to HackerRank Login...")
            await page.goto("https://www.hackerrank.com/auth/login", timeout=0, wait_until="domcontentloaded")
            
            # Automatic login if not logged in
            try:
                username_input = await page.wait_for_selector('input[name="username"]', timeout=5000)
                if username_input:
                    print("Logging in automatically...")
                    await username_input.fill("kumaraids2006")
                    await page.fill('input[name="password"]', "Kumar123@#")
                    await page.click('button[data-analytics="LoginPassword"]')
                    await page.wait_for_navigation(timeout=15000)
            except:
                print("Already logged in or login fields not found.")
            
            print("Navigating to HackerRank Python Domain...")
            await page.goto("https://www.hackerrank.com/domains/python", timeout=0, wait_until="domcontentloaded")
            
            # Wait for user to log in and apply filters
            print("\n*** ACTION REQUIRED ***")
            print("1. Use the HackerRank website to MANUALLY apply any filters you want (e.g. Unsolved, Advanced).")
            print("2. When you see the problems you want to solve on the screen, press ENTER here!")
            input("\nPress ENTER in this terminal when you are ready to start solving...")
            
            print(f"\n--- Starting Batch Solving (Skipping first {skip_count} problems) ---")
            
            total_to_extract = skip_count + count
            problem_urls = await get_unsolved_problems(page, total_to_extract)
            
            problem_urls = problem_urls[skip_count:]
            
            print(f"Found {len(problem_urls)} problems to solve:")
            for url in problem_urls:
                print(f"- {url}")
                
            for url in problem_urls:
                await page.goto(url, timeout=0, wait_until="domcontentloaded")
                await asyncio.sleep(3)
                await solve_current_problem(page, context)
                
            print("\n=== Batch Processing Complete! ===")
            await asyncio.sleep(10)
            
        except Exception as e:
            print(f"Critical Error: {e}")
        finally:
            if 'context' in locals():
                await context.close()

if __name__ == "__main__":
    asyncio.run(main())
