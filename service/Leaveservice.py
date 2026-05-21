"""
service/Leaveservice.py
────────────────────────
Leave application logic.
All SQL from queries/leave_queries.toml via LeaveQ.
"""

from datetime import datetime
from typing import Optional

from queries.loader import LeaveQ
from service.db import get_pool
from service.Employeeservice import broker          # ← added


# ── Helpers ───────────────────────────────────────────────────────────────────

def _row_to_dict(d: dict) -> dict:
    return {
        "id":           d["id"],
        "employeeId":   d["employee_id"],
        "employeeName": d["employee_name"],
        "leaveType":    d["leave_type"],
        "fromDate":     d["from_date"].isoformat(),
        "toDate":       d["to_date"].isoformat(),
        "reason":       d.get("reason"),
        "createdAt":    d["created_at"].isoformat(),
    }


# ── DB init ───────────────────────────────────────────────────────────────────

async def init_leave_db() -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(LeaveQ.ddl.create_leave_requests)
        await conn.execute(LeaveQ.ddl.create_index_leave_emp)


# ── CRUD ──────────────────────────────────────────────────────────────────────

async def apply_leave(
    employee_id: int,
    employee_name: str,
    leave_type: str,
    from_date: str,
    to_date: str,
    reason: Optional[str],
) -> dict:
    fd = datetime.strptime(from_date, "%Y-%m-%d").date()
    td = datetime.strptime(to_date,   "%Y-%m-%d").date()
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            LeaveQ.leave.insert,
            employee_id, employee_name, leave_type, fd, td, reason,
        )
    record = _row_to_dict(dict(row))
    await broker.publish("leave_created", record)   # ← added
    return record


async def get_all_leaves() -> list[dict]:           # ← added
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(LeaveQ.leave.select_all)
    return [_row_to_dict(dict(r)) for r in rows]


async def get_leave_by_date(employee_id: int, date_str: str) -> Optional[dict]:
    d = datetime.strptime(date_str, "%Y-%m-%d").date()
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(LeaveQ.leave.select_by_employee_date, employee_id, d)
    if not row:
        return None
    return _row_to_dict(dict(row))