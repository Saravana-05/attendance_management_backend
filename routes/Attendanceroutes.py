"""
routes/Attendanceroutes.py
──────────────────────────
FastAPI router for attendance check-in / check-out, daily summary,
and weekly hours endpoints.
"""

from fastapi import APIRouter, HTTPException, Query

from domain.Attendancedomain import AttendanceIn, LogoutIn
from service.Attendanceservice import (
    checkin, checkout,
    list_attendance, get_today_record, delete_attendance_record,
    get_daily_summary, get_weekly_hours,
)

router = APIRouter()


# ── Attendance ────────────────────────────────────────────────────────────────

@router.post("/attendance", status_code=201)
async def create_attendance(body: AttendanceIn):
    return await checkin(body.employeeId, body.employeeName, body.loginPhoto)


@router.post("/attendance/logout")
async def record_logout(body: LogoutIn):
    record = await checkout(body.attendanceId, body.logoutPhoto)
    if record is None:
        raise HTTPException(status_code=404, detail="Attendance record not found")
    if isinstance(record, dict) and record.get("error") == "active_break":
        raise HTTPException(status_code=409, detail=record["message"])
    return record


@router.get("/attendance")
async def get_attendance(date: str = Query(None)):
    return await list_attendance(date)


@router.get("/attendance/today/{employee_id}")
async def get_today(employee_id: int):
    record = await get_today_record(employee_id)
    if record is None:
        raise HTTPException(status_code=404, detail="No record today")
    return record


@router.delete("/attendance/{attendance_id}", status_code=204)
async def remove_attendance(attendance_id: int):
    deleted = await delete_attendance_record(attendance_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Record not found")


# ── Daily Summary ─────────────────────────────────────────────────────────────

@router.get("/attendance/daily")
async def daily_summary(date: str = Query(..., description="YYYY-MM-DD")):
    return await get_daily_summary(date)


# ── Weekly Hours ──────────────────────────────────────────────────────────────

@router.get("/attendance/weekly")
async def weekly_hours(
    week_start: str = Query(
        None,
        description="Monday of the target week YYYY-MM-DD. Defaults to current week.",
    )
):
    return await get_weekly_hours(week_start)