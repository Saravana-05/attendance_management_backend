from pydantic import BaseModel
from typing import Optional


class LeaveApplyIn(BaseModel):
    employeeId: int
    employeeName: str
    leaveType: str          # "Casual" | "Sick" | "Earned" | "Other"
    fromDate: str           # YYYY-MM-DD
    toDate: str             # YYYY-MM-DD
    reason: Optional[str] = None