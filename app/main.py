from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import Cookie, FastAPI, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import (
    APP_LOG_FILE,
    DATA_DIR,
    LOGS_DIR,
    NOTE_FILES_DIR,
    SCHEDULES_DIR,
    SESSION_COOKIE_NAME,
    STATIC_DIR,
    USERS_FILE,
)
from app.logging_config import configure_logging, logger
from app.routers import auth, knowledge, note, query, schedule
from app.services import auth_service

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    SCHEDULES_DIR.mkdir(parents=True, exist_ok=True)
    NOTE_FILES_DIR.mkdir(parents=True, exist_ok=True)
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
app.include_router(note.router)
app.include_router(knowledge.router)


@app.get("/", include_in_schema=False)
async def root_redirect():
    return RedirectResponse(url="/login", status_code=307)


@app.get("/login", include_in_schema=False)
async def login_page(session_token: str | None = Cookie(None, alias=SESSION_COOKIE_NAME)):
    try:
        auth_service.get_student_id(session_token)
    except PermissionError:
        return FileResponse(STATIC_DIR / "index.html")
    return RedirectResponse(url="/dashboard", status_code=307)


@app.get("/dashboard", include_in_schema=False)
async def dashboard_page(session_token: str | None = Cookie(None, alias=SESSION_COOKIE_NAME)):
    try:
        auth_service.get_student_id(session_token)
    except PermissionError:
        return RedirectResponse(url="/login", status_code=307)
    return FileResponse(STATIC_DIR / "dashboard.html")


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


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
