from pydantic import BaseModel
from typing import Optional


class BreakStartIn(BaseModel):
    attendanceId: int


class BreakEndIn(BaseModel):
    attendanceId: int


class BreakRecord(BaseModel):
    id: int
    attendanceId: int
    breakStart: str
    breakEnd: Optional[str] = None