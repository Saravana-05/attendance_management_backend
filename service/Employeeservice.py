"""
service/Employeeservice.py
──────────────────────────
Employee CRUD + SSE broker.
All SQL from queries/employee_queries.toml via EmployeeQ.
"""

import asyncio
import json
from typing import List

import asyncpg

from queries.loader import EmployeeQ
from service.db import get_pool


# ── SSE Broker (shared across modules via import) ─────────────────────────────

class SSEBroker:
    def __init__(self) -> None:
        self._clients: set[asyncio.Queue] = set()

    def add_client(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=50)
        self._clients.add(q)
        return q

    def remove_client(self, q: asyncio.Queue) -> None:
        self._clients.discard(q)

    async def publish(self, event_type: str, data: dict) -> None:
        payload = json.dumps({"type": event_type, "data": data}, default=str)
        dead = set()
        for q in self._clients:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                dead.add(q)
        for q in dead:
            self._clients.discard(q)


broker = SSEBroker()


# ── Helpers ───────────────────────────────────────────────────────────────────

def employee_row_to_dict(row: asyncpg.Record) -> dict:
    d = dict(row)
    if isinstance(d.get("encoding"), str):
        d["encoding"] = json.loads(d["encoding"])
    return d


# ── DB init ───────────────────────────────────────────────────────────────────

async def init_employee_db() -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(EmployeeQ.ddl.create_employees)


# ── CRUD ──────────────────────────────────────────────────────────────────────

async def add_employee(name: str, photo: str, encoding: List[float]) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            EmployeeQ.employee.insert,
            name, photo, json.dumps(encoding),
        )
    record = employee_row_to_dict(row)
    await broker.publish("employee_created", record)
    return record


async def get_all_employees() -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(EmployeeQ.employee.select_all)
    return [employee_row_to_dict(r) for r in rows]


async def delete_employee(employee_id: int) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(EmployeeQ.employee.delete, employee_id)
    deleted = result.startswith("DELETE") and int(result.split()[-1]) > 0
    if deleted:
        await broker.publish("employee_deleted", {"id": employee_id})
    return deleted