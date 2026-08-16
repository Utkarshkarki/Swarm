import json
import aiosqlite
from datetime import datetime, timezone
from typing import Any, Dict, List

from .config import settings

#store sessions
#retrieve sessions
#show history

async def log_session(
    username: str,
    query: str,
    domains: List[str],
    round1: Dict[str, str],
    round2: Dict[str, str],
    output: Dict[str, Any],
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_cost: float = 0.0,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO sessions
                (username, query, domains_json, round1_json, round2_json, output_json, prompt_tokens, completion_tokens, total_cost, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                username,
                query,
                json.dumps(domains),
                json.dumps(round1),
                json.dumps(round2),
                json.dumps(output),
                prompt_tokens,
                completion_tokens,
                total_cost,
                now,
            ),
        )
        await db.commit()


async def get_history(username: str, limit: int = 20) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        async with db.execute(
            """
            SELECT id, username, query, output_json, prompt_tokens, completion_tokens, total_cost, created_at
            FROM sessions WHERE username = ?
            ORDER BY created_at DESC LIMIT ?
            """,
            (username, limit),
        ) as cursor:
            rows = await cursor.fetchall()
    return [
        {
            "id": r[0],
            "username": r[1],
            "query": r[2],
            "output": json.loads(r[3]),
            "prompt_tokens": r[4] or 0,
            "completion_tokens": r[5] or 0,
            "total_cost": r[6] or 0.0,
            "created_at": r[7],
        }
        for r in rows
    ]


async def get_all_history(limit: int = 50) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        async with db.execute(
            """
            SELECT id, username, query, output_json, prompt_tokens, completion_tokens, total_cost, created_at
            FROM sessions ORDER BY created_at DESC LIMIT ?
            """,
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
    return [
        {
            "id": r[0],
            "username": r[1],
            "query": r[2],
            "output": json.loads(r[3]),
            "prompt_tokens": r[4] or 0,
            "completion_tokens": r[5] or 0,
            "total_cost": r[6] or 0.0,
            "created_at": r[7],
        }
        for r in rows
    ]

