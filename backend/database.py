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
                prompt_tokens INTEGER DEFAULT 0,
                completion_tokens INTEGER DEFAULT 0,
                total_cost REAL DEFAULT 0.0,
                created_at TEXT NOT NULL
            )
        """)
        # Safe migration for existing databases
        async with db.execute("PRAGMA table_info(sessions)") as cursor:
            columns = [row[1] for row in await cursor.fetchall()]
            if "prompt_tokens" not in columns:
                await db.execute("ALTER TABLE sessions ADD COLUMN prompt_tokens INTEGER DEFAULT 0")
            if "completion_tokens" not in columns:
                await db.execute("ALTER TABLE sessions ADD COLUMN completion_tokens INTEGER DEFAULT 0")
            if "total_cost" not in columns:
                await db.execute("ALTER TABLE sessions ADD COLUMN total_cost REAL DEFAULT 0.0")

        await db.commit()

