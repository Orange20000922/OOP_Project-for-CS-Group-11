from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import DATA_DIR, SCHEDULES_DIR, STATIC_DIR, USERS_FILE
from app.routers import auth, query, schedule


@asynccontextmanager
async def lifespan(app: FastAPI):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SCHEDULES_DIR.mkdir(parents=True, exist_ok=True)
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    if not USERS_FILE.exists():
        USERS_FILE.write_text('{"users": []}', encoding="utf-8")
    yield


app = FastAPI(
    title="学生课表管理系统",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(auth.router)
app.include_router(schedule.router)
app.include_router(query.router)

app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
