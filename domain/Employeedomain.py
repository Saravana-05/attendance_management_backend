from pydantic import BaseModel
from typing import List


class EmployeeIn(BaseModel):
    name: str
    photo: str              # base64 data:image/jpeg;base64,...
    encoding: List[float]   # 128-dim face descriptor array


class EmployeeOut(BaseModel):
    id: int
    name: str
    photo: str
    encoding: List[float]