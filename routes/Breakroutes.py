"""
routes/Breakroutes.py
──────────────────────
FastAPI router for break start / end endpoints.
"""

from fastapi import APIRouter, HTTPException

from domain.Breakdomain import BreakStartIn, BreakEndIn
from service.Breakservice import start_break, end_break, get_all_breaks

router = APIRouter()


@router.get("/breaks")                                          # ← added (needed for initialSync)
async def list_breaks():
    return await get_all_breaks()


@router.post("/attendance/break/start")
async def break_start(body: BreakStartIn):
    record = await start_break(body.attendanceId)
    if record is None:
        raise HTTPException(status_code=404, detail="Attendance record not found")
    if isinstance(record, dict) and record.get("error"):
        raise HTTPException(status_code=409, detail=record["message"])
    return record


@router.post("/attendance/break/end")
async def break_end(body: BreakEndIn):
    record = await end_break(body.attendanceId)
    if record is None:
        raise HTTPException(status_code=404, detail="Attendance record not found")
    if isinstance(record, dict) and record.get("error"):
        raise HTTPException(status_code=409, detail=record["message"])
    return record