import json
import aiosqlite
from datetime import datetime, timezone
from typing import Optional

from .config import settings
from .models import UserProfile


async def get_profile(username: str) -> UserProfile:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        async with db.execute(
            "SELECT profile_json FROM user_profiles WHERE username = ?", (username,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return UserProfile(**json.loads(row[0]))
    return UserProfile(username=username)


async def save_profile(profile: UserProfile) -> None:
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO user_profiles (username, profile_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                profile_json = excluded.profile_json,
                updated_at   = excluded.updated_at
            """,
            (profile.username, json.dumps(profile.model_dump()), now),
        )
        await db.commit()
