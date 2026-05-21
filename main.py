from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes.Employeeroutes import router as employee_router
from routes.Attendanceroutes import router as attendance_router
from routes.Breakroutes import router as break_router
from routes.Leaveroutes import router as leave_router

from service.db import get_pool, close_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    await get_pool()   # creates pool + runs attendance_schema.sql once
    yield
    await close_pool()


app = FastAPI(title="AttendAI API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(employee_router)
app.include_router(attendance_router)
app.include_router(break_router)
app.include_router(leave_router)