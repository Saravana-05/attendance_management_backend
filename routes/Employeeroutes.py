"""
routes/Employeeroutes.py
─────────────────────────
FastAPI router for employee endpoints.
"""

import asyncio
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from domain.Employeedomain import EmployeeIn
from service.Employeeservice import broker, add_employee, get_all_employees, delete_employee

router = APIRouter()


# ── Health ────────────────────────────────────────────────────────────────────

@router.get("/health")
async def health():
    return {"status": "ok"}


# ── SSE stream ────────────────────────────────────────────────────────────────

async def _event_generator(q: asyncio.Queue) -> AsyncGenerator[str, None]:
    yield "event: connected\ndata: {}\n\n"
    try:
        while True:
            try:
                payload = await asyncio.wait_for(q.get(), timeout=25)
                yield f"data: {payload}\n\n"
            except asyncio.TimeoutError:
                yield ": ping\n\n"
    except asyncio.CancelledError:
        pass


@router.get("/attendance/stream")
async def attendance_stream():
    q = broker.add_client()

    async def generator():
        try:
            async for chunk in _event_generator(q):
                yield chunk
        finally:
            broker.remove_client(q)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Employees ─────────────────────────────────────────────────────────────────

@router.post("/employees", status_code=201)
async def create_employee(body: EmployeeIn):
    return await add_employee(body.name, body.photo, body.encoding)


@router.get("/employees")
async def list_employees():
    return await get_all_employees()


@router.delete("/employees/{employee_id}", status_code=204)
async def remove_employee(employee_id: int):
    deleted = await delete_employee(employee_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Employee not found")