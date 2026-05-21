"""
service/Attendanceservice.py
────────────────────────────
Attendance check-in / check-out, daily summary, weekly hours.
All SQL from queries/attendance_queries.toml and queries/leave_queries.toml.
"""

from datetime import date, datetime, timedelta

import asyncpg

from queries.loader import AttendanceQ, BreakQ, EmployeeQ, LeaveQ
from service.db import get_pool
from service.Employeeservice import broker
from service.Breakservice import fetch_breaks, now_time_str, _attendance_row_to_dict


# ── DB init ───────────────────────────────────────────────────────────────────

async def init_attendance_db() -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(AttendanceQ.ddl.create_attendance)
        await conn.execute(AttendanceQ.ddl.create_index_emp_date)
        await conn.execute(AttendanceQ.ddl.create_index_date)
        await conn.execute(AttendanceQ.ddl.migrate_photos)


# ── Helpers ───────────────────────────────────────────────────────────────────

def today_str() -> date:
    return date.today()


def _to_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    return datetime.strptime(value, "%Y-%m-%d").date()


def _parse_time(time_str: str | None) -> datetime | None:
    if not time_str:
        return None
    for fmt in ("%I:%M:%S %p", "%I:%M %p", "%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(time_str.strip(), fmt)
        except ValueError:
            continue
    return None


def calc_hours(login: str | None, logout: str | None) -> float | None:
    t1 = _parse_time(login)
    t2 = _parse_time(logout)
    if t1 is None or t2 is None:
        return None
    diff = (t2 - t1).total_seconds() / 3600
    return round(diff, 2) if diff >= 0 else None


def calc_break_minutes(breaks: list[dict]) -> float:
    total = 0.0
    for b in breaks:
        t1 = _parse_time(b.get("breakStart"))
        t2 = _parse_time(b.get("breakEnd"))
        if t1 and t2:
            mins = (t2 - t1).total_seconds() / 60
            if mins > 0:
                total += mins
    return round(total, 2)


async def _get_leave_dates_for_employees(
    conn: asyncpg.Connection,
    employee_ids: list[int],
    from_date: date,
    to_date: date,
) -> dict[int, set[str]]:
    if not employee_ids:
        return {}
    rows = await conn.fetch(
        LeaveQ.leave.select_overlapping_by_employees,
        employee_ids, to_date, from_date,
    )
    result: dict[int, set[str]] = {}
    for row in rows:
        eid = row["employee_id"]
        cur = max(row["from_date"], from_date)
        end = min(row["to_date"],   to_date)
        while cur <= end:
            result.setdefault(eid, set()).add(cur.isoformat())
            cur = date.fromordinal(cur.toordinal() + 1)
    return result


# ── Check-in / Check-out ──────────────────────────────────────────────────────

async def checkin(employee_id: int, employee_name: str, login_photo: str | None = None) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            AttendanceQ.attendance.select_by_employee_and_date,
            employee_id, today_str(),
        )
        if existing:
            breaks = await fetch_breaks(conn, existing["id"])
            record = _attendance_row_to_dict(existing, breaks)
            record["alreadyIn"] = True
            await broker.publish("attendance_updated", record)
            return record

        row = await conn.fetchrow(
            AttendanceQ.attendance.insert,
            employee_id, employee_name, today_str(), now_time_str(), login_photo,
        )
        record = _attendance_row_to_dict(row, [])
        record["alreadyIn"] = False

    await broker.publish("attendance_created", record)
    return record


async def checkout(attendance_id: int, logout_photo: str | None = None) -> dict | None:
    """Refuses to logout while a break is still active."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        active = await conn.fetchval(BreakQ.breaks.select_active_id, attendance_id)
        if active is not None:
            return {"error": "active_break", "message": "End the active break before logging out."}

        row = await conn.fetchrow(
            AttendanceQ.attendance.update_logout,
            now_time_str(), logout_photo, attendance_id,
        )
        if row is None:
            return None
        breaks = await fetch_breaks(conn, attendance_id)
        record = _attendance_row_to_dict(row, breaks)

    await broker.publish("attendance_updated", record)
    return record


# ── Queries ───────────────────────────────────────────────────────────────────

async def list_attendance(date_filter: str | date | None) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        if date_filter:
            rows = await conn.fetch(
                AttendanceQ.attendance.select_by_date, _to_date(date_filter)
            )
        else:
            rows = await conn.fetch(AttendanceQ.attendance.select_all)
        records = []
        for r in rows:
            breaks = await fetch_breaks(conn, r["id"])
            records.append(_attendance_row_to_dict(r, breaks))
    return records


async def get_today_record(employee_id: int) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            AttendanceQ.attendance.select_by_employee_and_date,
            employee_id, today_str(),
        )
        if row is None:
            return None
        breaks = await fetch_breaks(conn, row["id"])
    return _attendance_row_to_dict(row, breaks)


async def delete_attendance_record(attendance_id: int) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(AttendanceQ.attendance.delete, attendance_id)
    deleted = result.startswith("DELETE") and int(result.split()[-1]) > 0
    if deleted:
        await broker.publish("attendance_deleted", {"id": attendance_id})
    return deleted


# ── Daily Summary ─────────────────────────────────────────────────────────────

async def get_daily_summary(date_str: str | date) -> list[dict]:
    target_date = _to_date(date_str)
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            AttendanceQ.attendance.select_by_date_ordered_by_name, target_date
        )
        result = []
        present_ids: set[int] = set()

        for row in rows:
            breaks = await fetch_breaks(conn, row["id"])
            rec = _attendance_row_to_dict(row, breaks)
            gross = calc_hours(rec["loginTime"], rec["logoutTime"])
            break_mins = calc_break_minutes(breaks)
            net = round(gross - (break_mins / 60), 2) if gross is not None else None
            rec["grossHours"]   = gross
            rec["breakMinutes"] = break_mins
            rec["hoursWorked"]  = net
            rec["onLeave"]      = False
            result.append(rec)
            present_ids.add(row["employee_id"])

        all_employees = await conn.fetch(EmployeeQ.employee.select_all_name_id)
        absent_ids = [e["id"] for e in all_employees if e["id"] not in present_ids]
        leave_map = await _get_leave_dates_for_employees(
            conn, absent_ids, target_date, target_date
        )
        target_str = target_date.isoformat()

        for emp in all_employees:
            if emp["id"] in present_ids:
                continue
            result.append({
                "id":           f"absent-{emp['id']}",
                "employeeId":   emp["id"],
                "employeeName": emp["name"],
                "loginTime":    None,
                "logoutTime":   None,
                "loginPhoto":   None,
                "logoutPhoto":  None,
                "breaks":       [],
                "onBreak":      False,
                "grossHours":   None,
                "breakMinutes": 0,
                "hoursWorked":  None,
                "onLeave":      target_str in leave_map.get(emp["id"], set()),
            })
    return result


# ── Weekly Hours ──────────────────────────────────────────────────────────────

async def get_weekly_hours(week_start: str | None) -> dict:
    if week_start:
        try:
            monday = datetime.strptime(week_start, "%Y-%m-%d").date()
        except ValueError:
            monday = date.today()
    else:
        today = date.today()
        monday = today - timedelta(days=today.weekday())

    sunday = monday + timedelta(days=6)
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            AttendanceQ.attendance.select_by_date_range, monday, sunday
        )
        per_row_breaks: dict[int, list[dict]] = {}
        for r in rows:
            per_row_breaks[r["id"]] = await fetch_breaks(conn, r["id"])

        all_employees = await conn.fetch(EmployeeQ.employee.select_all_name_id)
        all_ids = [e["id"] for e in all_employees]
        leave_map = await _get_leave_dates_for_employees(conn, all_ids, monday, sunday)

    emp_map: dict[int, dict] = {
        emp["id"]: {
            "employeeId":     emp["id"],
            "employeeName":   emp["name"],
            "days":           {},
            "daysPresent":    0,
            "totalHours":     0.0,
            "totalBreakMins": 0.0,
        }
        for emp in all_employees
    }

    for row in rows:
        breaks = per_row_breaks.get(row["id"], [])
        rec = _attendance_row_to_dict(row, breaks)
        eid = rec["employeeId"]
        gross = calc_hours(rec["loginTime"], rec["logoutTime"])
        break_mins = calc_break_minutes(breaks)
        net = round(gross - (break_mins / 60), 2) if gross is not None else None
        emp_map[eid]["days"][rec["date"]] = {
            "loginTime":    rec["loginTime"],
            "logoutTime":   rec["logoutTime"],
            "grossHours":   gross,
            "breakMinutes": break_mins,
            "hoursWorked":  net,
            "breaks":       breaks,
            "onLeave":      False,
        }
        emp_map[eid]["daysPresent"] += 1
        if net is not None:
            emp_map[eid]["totalHours"] = round(emp_map[eid]["totalHours"] + net, 2)
        emp_map[eid]["totalBreakMins"] = round(
            emp_map[eid]["totalBreakMins"] + break_mins, 2
        )

    friday = monday + timedelta(days=4)
    cur = monday
    while cur <= friday:
        ds = cur.isoformat()
        for eid, emp in emp_map.items():
            if ds not in emp["days"] and ds in leave_map.get(eid, set()):
                emp["days"][ds] = {"onLeave": True}
        cur = date.fromordinal(cur.toordinal() + 1)

    return {
        "weekStart": monday.isoformat(),
        "weekEnd":   sunday.isoformat(),
        "employees": list(emp_map.values()),
    }