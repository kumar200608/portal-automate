import asyncio
import os
import getpass
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from browser_use import Agent

# Load environment variables from .env file
load_dotenv()

async def main():
    print("=== Programming Portal Solver Agent ===")
    
    # Check for API key
    if not os.getenv("GOOGLE_API_KEY"):
        print("Please set your GOOGLE_API_KEY environment variable or in a .env file.")
        api_key = getpass.getpass("Enter your Google Gemini API Key: ")
        os.environ["GOOGLE_API_KEY"] = api_key

    # Setup the LLM using Gemini (you can change model as needed)
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")

    # Get portal and login details from the user
    portal_url = input("Enter the portal URL (e.g., LeetCode, HackerRank problem link): ")
    username = input("Enter your username/email: ")
    password = getpass.getpass("Enter your password: ")
    programming_language = input("Enter the programming language to solve in (default: Python 3): ")
    
    if not programming_language.strip():
        programming_language = "Python 3"

    # Define the precise task for the agent
    task_description = f"""
    1. Navigate to {portal_url}.
    2. Look for a login button or form. Log in using the username: '{username}' and password: '{password}'. 
       WARNING: Do not reveal or type the password anywhere other than the password field.
    3. Once logged in, navigate to the problem description if you are not already there.
    4. Read the programming problem description, constraints, and examples carefully.
    5. Write optimal {programming_language} code to solve the problem.
    6. Locate the code editor on the page. Ensure the selected language in the editor is {programming_language}.
    7. Clear any existing code and paste/type your {programming_language} solution into the editor.
    8. Click the 'Run', 'Test', or 'Submit' button to evaluate the code.
    9. Read the results (success, failure, compilation error) and report back. 
       If it fails, try to fix the code once and resubmit.
    """

    print("\nStarting the autonomous agent... (This will open a browser window)")
    
    # Initialize the browser-use agent
    agent = Agent(
        task=task_description,
        llm=llm,
        use_vision=True, # Allow the agent to see the screen if the model supports it
    )

    try:
        # Run the agent
        result = await agent.run()
        print("\n=== Agent Finished ===")
        print("Final Result:")
        print(result)
    except Exception as e:
        print(f"\nAn error occurred while running the agent: {e}")

if __name__ == "__main__":
    # Required for Windows if using certain event loops, but safe cross-platform
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
