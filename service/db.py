"""
service/db.py
─────────────
Shared asyncpg connection pool used by all service modules.
Runs the shared SQL schema once on first pool creation.
Import get_pool / close_pool from here — never create a second pool.
"""

import os
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL: str = os.environ["DATABASE_URL"]

_pool: asyncpg.Pool | None = None

# Place attendance_schema.sql in the backend/ root (one level above service/)
SCHEMA_FILE = Path(__file__).parent.parent / "attendance_schema.sql"


async def _init_schema(pool: asyncpg.Pool) -> None:
    """Create all tables and indexes from the central SQL file."""
    schema = SCHEMA_FILE.read_text(encoding="utf-8")
    async with pool.acquire() as conn:
        await conn.execute(schema)


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
        await _init_schema(_pool)   # runs once when the pool is first created
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None