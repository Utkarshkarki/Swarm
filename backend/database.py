import aiosqlite
from .config import settings


async def init_db() -> None:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_profiles (
                username TEXT PRIMARY KEY,
                profile_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                query TEXT NOT NULL,
                domains_json TEXT,
                round1_json TEXT,
                round2_json TEXT,
                output_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        await db.commit()
