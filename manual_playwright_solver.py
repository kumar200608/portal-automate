import asyncio
import getpass
import os
from playwright.async_api import async_playwright
from google import genai

# Setup your API key as GOOGLE_API_KEY environment variable
# export GOOGLE_API_KEY="your_api_key_here"

async def solve_with_gemini(problem_text: str, language: str = "Python 3") -> str:
    """Uses Gemini API to generate the solution code."""
    client = genai.Client()
    prompt = f"""
    You are an expert competitive programmer. 
    Solve the following programming problem in {language}.
    Provide ONLY the raw code as your response, without any markdown formatting like ```python or explanations.
    
    Problem Statement:
    {problem_text}
    """
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
    )
    return response.text.strip()

async def manual_playwright_solver():
    print("=== Manual Playwright Portal Solver ===")
    portal_url = input("Enter the portal URL: ")
    username = input("Enter your username/email: ")
    password = getpass.getpass("Enter your password: ")
    
    # Example generic CSS selectors (You will likely need to change these based on the portal)
    login_btn_selector = "text=Log in"
    user_input_selector = "input[type='text'], input[name='username'], input[type='email']"
    pass_input_selector = "input[type='password'], input[name='password']"
    submit_login_selector = "button[type='submit']"
    
    problem_desc_selector = ".problem-description, .question-content"
    code_editor_selector = ".monaco-editor, .CodeMirror, textarea"
    submit_code_selector = "text=Submit, button:has-text('Submit Code')"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            print(f"Navigating to {portal_url}...")
            await page.goto(portal_url)
            
            # Login Process
            print("Attempting to login...")
            if await page.locator(login_btn_selector).is_visible():
                await page.click(login_btn_selector)
            
            await page.fill(user_input_selector, username)
            await page.fill(pass_input_selector, password)
            await page.click(submit_login_selector)
            
            await page.wait_for_load_state('networkidle')
            print("Logged in successfully.")

            # Extract Problem Description
            print("Extracting problem description...")
            await page.wait_for_selector(problem_desc_selector)
            problem_text = await page.inner_text(problem_desc_selector)
            
            print(f"Problem extracted ({len(problem_text)} characters). Sending to Gemini...")
            
            # Generate Code
            solution_code = await solve_with_gemini(problem_text)
            print("Solution generated.")
            
            # Inject Code
            print("Pasting solution into the editor...")
            await page.wait_for_selector(code_editor_selector)
            
            # Note: For complex editors like Monaco (VS Code web) or CodeMirror, 
            # simple 'fill' might not work. We often need to click and type, or evaluate JS.
            await page.click(code_editor_selector)
            # Select all and delete existing code
            await page.keyboard.press("Control+A") 
            await page.keyboard.press("Meta+A") # For Mac
            await page.keyboard.press("Backspace")
            
            # Paste the generated code
            await page.keyboard.type(solution_code, delay=10) # Small delay to simulate typing
            
            # Submit Code
            print("Submitting the code...")
            await page.click(submit_code_selector)
            
            # Wait to view results
            print("Submitted! Waiting 15 seconds to view results...")
            await asyncio.sleep(15)
            
        except Exception as e:
            print(f"An error occurred: {e}")
            print("Note: You may need to update the CSS selectors in the script to match your specific portal.")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(manual_playwright_solver())
