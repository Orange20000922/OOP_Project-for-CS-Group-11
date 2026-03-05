from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import STATIC_DIR, DATA_DIR, SCHEDULES_DIR
from app.routers import auth, schedule, query


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时确保数据目录存在
    DATA_DIR.mkdir(exist_ok=True)
    SCHEDULES_DIR.mkdir(exist_ok=True)
    STATIC_DIR.mkdir(exist_ok=True)
    yield


app = FastAPI(
    title="学生课表管理系统",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(auth.router)
app.include_router(schedule.router)
app.include_router(query.router)

# 前端静态文件，挂载在最后（兜底路由）
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
