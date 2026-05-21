from pydantic import BaseModel
from typing import Optional, List


class AttendanceIn(BaseModel):
    employeeId: int
    employeeName: str
    loginPhoto: Optional[str] = None    # base64 webcam snapshot at login


class LogoutIn(BaseModel):
    attendanceId: int
    logoutPhoto: Optional[str] = None   # base64 webcam snapshot at logout


class AttendanceRecord(BaseModel):
    id: int
    employeeId: int
    employeeName: str
    date: str
    loginTime: Optional[str] = None
    logoutTime: Optional[str] = None
    loginPhoto: Optional[str] = None
    logoutPhoto: Optional[str] = None
    breaks: List = []
    onBreak: bool = False
    alreadyIn: Optional[bool] = False