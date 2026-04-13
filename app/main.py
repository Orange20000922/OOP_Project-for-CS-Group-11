from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from app.config import APP_LOG_FILE, DATA_DIR, LOGS_DIR, SCHEDULES_DIR, STATIC_DIR, USERS_FILE
from app.logging_config import configure_logging, logger
from app.routers import auth, query, schedule

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    SCHEDULES_DIR.mkdir(parents=True, exist_ok=True)
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    if not USERS_FILE.exists():
        USERS_FILE.write_text('{"users": []}', encoding="utf-8")
        logger.info("Initialized empty user store at {}", USERS_FILE)
    logger.info("Application startup completed; logs will be written to {}", APP_LOG_FILE)
    yield
    logger.info("Application shutdown completed")


app = FastAPI(
    title="学生课表管理系统",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(auth.router)
app.include_router(schedule.router)
app.include_router(query.router)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    started_at = perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (perf_counter() - started_at) * 1000
        logger.exception(
            "HTTP {} {} failed after {:.2f} ms",
            request.method,
            request.url.path,
            duration_ms,
        )
        raise

    duration_ms = (perf_counter() - started_at) * 1000
    logger.info(
        "HTTP {} {} -> {} ({:.2f} ms)",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
