"""
routes/Leaveroutes.py
──────────────────────
FastAPI router for leave endpoints.
"""

from fastapi import APIRouter, HTTPException, Query

from domain.Leavedomain import LeaveApplyIn
from service.Leaveservice import apply_leave, get_all_leaves, get_leave_by_date

router = APIRouter()


@router.get("/leaves")                              # ← added (needed for initialSync)
async def list_leaves():
    return await get_all_leaves()


@router.post("/leave", status_code=201)
async def create_leave(body: LeaveApplyIn):
    return await apply_leave(
        body.employeeId, body.employeeName, body.leaveType,
        body.fromDate, body.toDate, body.reason,
    )


@router.get("/leave/check")
async def check_leave(employeeId: int = Query(...), date: str = Query(...)):
    record = await get_leave_by_date(employeeId, date)
    if not record:
        raise HTTPException(status_code=404, detail="No leave on this date")
    return record