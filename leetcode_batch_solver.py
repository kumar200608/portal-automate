import asyncio
import os
from dotenv import load_dotenv
from browser_use.llm import ChatGroq
from browser_use import Agent

# Load environment variables
load_dotenv()

async def main():
    print("=== LeetCode Batch Solver Agent ===")
    
    # Check for API key
    if not os.getenv("GROQ_API_KEY"):
        print("Please set your GROQ_API_KEY environment variable. e.g. export GROQ_API_KEY='your_key'")
        return

    # Setup the LLM using Groq
    llm = ChatGroq(model="qwen/qwen3.8-27b")

    # Provided Credentials
    import getpass
    email = "kumaraids2006@gmail.com"
    password = getpass.getpass("Enter your password: ")

    # Define the precise task for the agent
    task_description = f"""
    You are an automated competitive programming solver. Your goal is to solve 10 unsolved problems on LeetCode.
    
    1. Navigate to https://leetcode.com/login/
    2. Log in using the email '{email}' and password '{password}'. 
       NOTE: If there is a CAPTCHA or Cloudflare challenge, you might need to pause or wait for the user to solve it.
    3. Once logged in successfully, go to https://leetcode.com/problemset/
    4. Find an unsolved problem (one without a green checkmark next to it). Click on it to open the problem page.
    5. Read the programming problem description carefully.
    6. Write optimal Python 3 code to solve the problem.
    7. Ensure the code editor language is set to Python 3. Clear the editor and type/paste your solution.
    8. Click the 'Submit' button.
    9. Read the results. If it fails, try to fix it. If it is Accepted, navigate back to https://leetcode.com/problemset/
    10. Repeat steps 4-9 until you have successfully submitted and solved 10 problems.
    """

    print("\nStarting the autonomous agent... (A browser window will open)")
    print("NOTE: LeetCode has strong bot-protection. If a CAPTCHA appears, please solve it manually in the opened browser window.")
    
    agent = Agent(
        task=task_description,
        llm=llm,
        use_vision=True, 
    )

    try:
        result = await agent.run()
        print("\n=== Agent Finished ===")
        print("Final Result:")
        print(result)
    except Exception as e:
        print(f"\nAn error occurred while running the agent: {e}")

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
