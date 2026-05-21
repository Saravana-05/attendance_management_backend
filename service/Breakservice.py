"""
service/Breakservice.py
────────────────────────
Break start / end logic.
All SQL from queries/break_queries.toml via BreakQ.
"""

from datetime import datetime

import asyncpg

from queries.loader import BreakQ, AttendanceQ
from service.db import get_pool
from service.Employeeservice import broker


# ── Helpers ───────────────────────────────────────────────────────────────────

def now_time_str() -> str:
    return datetime.now().strftime("%I:%M:%S %p")


def break_row_to_dict(row: asyncpg.Record) -> dict:
    d = dict(row)
    return {
        "id":           d["id"],
        "attendanceId": d["attendance_id"],
        "breakStart":   d["break_start"],
        "breakEnd":     d.get("break_end"),
    }


async def fetch_breaks(conn: asyncpg.Connection, attendance_id: int) -> list[dict]:
    rows = await conn.fetch(BreakQ.breaks.select_all_by_attendance, attendance_id)
    return [break_row_to_dict(r) for r in rows]


# ── DB init ───────────────────────────────────────────────────────────────────

async def init_break_db() -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(BreakQ.ddl.create_attendance_breaks)
        await conn.execute(BreakQ.ddl.create_index_breaks_attendance)
        await conn.execute(BreakQ.ddl.create_index_breaks_active)


# ── Helpers shared with attendance service ────────────────────────────────────

def _attendance_row_to_dict(row: asyncpg.Record, breaks: list[dict]) -> dict:
    from datetime import date
    d = dict(row)
    on_break = any(b.get("breakEnd") is None for b in breaks)
    return {
        "id":           d["id"],
        "employeeId":   d["employee_id"],
        "employeeName": d["employee_name"],
        "date":         d["date"].isoformat() if isinstance(d["date"], date) else d["date"],
        "loginTime":    d.get("login_time"),
        "logoutTime":   d.get("logout_time"),
        "loginPhoto":   d.get("login_photo"),
        "logoutPhoto":  d.get("logout_photo"),
        "breaks":       breaks,
        "onBreak":      on_break,
    }


# ── GET all breaks (for initialSync seed) ─────────────────────────────────────

async def get_all_breaks() -> list[dict]:                       # ← added
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT * FROM attendance_breaks ORDER BY attendance_id, id
        """)
    return [break_row_to_dict(r) for r in rows]


# ── Business logic ────────────────────────────────────────────────────────────

async def start_break(attendance_id: int) -> dict | None:
    """Start a new break. Refuses if already logged out or break already active."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        att = await conn.fetchrow(AttendanceQ.attendance.select_by_id, attendance_id)
        if att is None:
            return None

        if att["logout_time"]:
            return {"error": "already_logged_out", "message": "Already logged out for the day."}

        active = await conn.fetchval(BreakQ.breaks.select_active_id, attendance_id)
        if active is not None:
            return {"error": "break_in_progress", "message": "A break is already in progress."}

        await conn.execute(BreakQ.breaks.insert, attendance_id, now_time_str())

        # fetch the break row we just inserted
        new_break_row = await conn.fetchrow("""
            SELECT * FROM attendance_breaks
            WHERE attendance_id=$1 AND break_end IS NULL
            ORDER BY id DESC LIMIT 1
        """, attendance_id)

        breaks = await fetch_breaks(conn, attendance_id)
        att_record = _attendance_row_to_dict(att, breaks)

    # publish both: attendance (existing consumers) + break (new store)
    await broker.publish("attendance_updated", att_record)
    await broker.publish("break_created", break_row_to_dict(new_break_row))  # ← added
    return att_record


async def end_break(attendance_id: int) -> dict | None:
    """End the currently active break."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        att = await conn.fetchrow(AttendanceQ.attendance.select_by_id, attendance_id)
        if att is None:
            return None

        active = await conn.fetchrow(BreakQ.breaks.select_latest_active, attendance_id)
        if active is None:
            return {"error": "no_active_break", "message": "No active break to end."}

        await conn.execute(BreakQ.breaks.update_end, now_time_str(), active["id"])

        # fetch the updated break row
        updated_break_row = await conn.fetchrow("""
            SELECT * FROM attendance_breaks WHERE id=$1
        """, active["id"])

        breaks = await fetch_breaks(conn, attendance_id)
        att_record = _attendance_row_to_dict(att, breaks)

    # publish both: attendance (existing consumers) + break (new store)
    await broker.publish("attendance_updated", att_record)
    await broker.publish("break_updated", break_row_to_dict(updated_break_row))  # ← added
    return att_record