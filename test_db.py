import asyncio
import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()

async def test_connection():
    url = os.getenv("DATABASE_URL")
    print(f"Testing URL: {url.split('@')[1] if '@' in url else url}")  # Hide password

    try:
        conn = await asyncpg.connect(url)
        print("✅ Connection successful!")
        await conn.close()
    except Exception as e:
        print(f"❌ Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_connection())
