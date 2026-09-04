import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.main import load_dotenv

load_dotenv()

def verify():
    print(f"GOOGLE_CLIENT_ID: {os.environ.get('GOOGLE_CLIENT_ID')}")
    print(f"GITHUB_CLIENT_ID: {os.environ.get('GITHUB_CLIENT_ID')}")
    print(f"SMTP_USER: {os.environ.get('SMTP_USER')}")

    # Check database initialization
    from app.database import init_database, get_session, UserRepository
    import asyncio

    async def check_db():
        try:
            await init_database()
            async with get_session() as session:
                repo = UserRepository(session)
                # Just a simple query to see if it works
                print("Database initialized and connected.")
        except Exception as e:
            print(f"Database error: {e}")

    asyncio.run(check_db())

if __name__ == "__main__":
    verify()
