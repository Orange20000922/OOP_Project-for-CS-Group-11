from __future__ import annotations

import logging
import sys
from datetime import date
from pathlib import Path

from loguru import logger

from app.config import APP_LOG_FILE, LOG_LEVEL

_configured = False
_FAILURE_KEYWORDS = (
    "failed",
    "failure",
    "timed out",
    "timeout",
    "rejected",
    "invalid",
    "denied",
    "captcha",
    "expired",
    "redirected to unexpected",
)


class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame = logging.currentframe()
        depth = 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def build_log_targets(log_file: Path, *, for_date: date | None = None) -> dict[str, Path]:
    resolved_log_file = Path(log_file)
    logs_root = resolved_log_file.parent
    stem = resolved_log_file.stem or "app"
    suffix = resolved_log_file.suffix or ".log"
    date_token = for_date.strftime("%Y-%m-%d") if for_date is not None else "{time:YYYY-MM-DD}"

    return {
        "combined_daily": logs_root / "combined" / f"{stem}_{date_token}{suffix}",
        "http_daily": logs_root / "http" / f"{stem}_http_{date_token}{suffix}",
        "error": logs_root / "errors" / f"{stem}_errors{suffix}",
        "failure": logs_root / "failures" / f"{stem}_failures{suffix}",
    }


def _message_text(record: dict) -> str:
    return str(record.get("message", ""))


def _is_http_access_record(record: dict) -> bool:
    return _message_text(record).startswith("HTTP ")


def _is_failure_record(record: dict) -> bool:
    if record["exception"] is not None:
        return True
    if record["level"].name == "ERROR":
        return True
    if record["level"].no < logger.level("WARNING").no:
        return False

    message = _message_text(record).casefold()
    return any(keyword in message for keyword in _FAILURE_KEYWORDS)


def configure_logging(log_file: Path = APP_LOG_FILE, level: str = LOG_LEVEL, *, force: bool = False) -> None:
    global _configured
    if _configured and not force:
        return

    targets = build_log_targets(log_file)
    for path in targets.values():
        path.parent.mkdir(parents=True, exist_ok=True)

    logger.remove()
    logger.add(
        sys.stderr,
        level=level,
        colorize=True,
        enqueue=False,
        backtrace=False,
        diagnose=False,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "{name}:{function}:{line} - <level>{message}</level>"
        ),
    )
    logger.add(
        targets["combined_daily"],
        level="DEBUG",
        enqueue=False,
        encoding="utf-8",
        rotation="00:00",
        retention="30 days",
        compression="zip",
        backtrace=False,
        diagnose=False,
        filter=lambda record: not _is_http_access_record(record),
        format=(
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
            "{process.id}:{thread.id} | {name}:{function}:{line} - {message}"
        ),
    )
    logger.add(
        targets["http_daily"],
        level="INFO",
        enqueue=False,
        encoding="utf-8",
        rotation="00:00",
        retention="14 days",
        compression="zip",
        backtrace=False,
        diagnose=False,
        filter=_is_http_access_record,
        format=(
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
            "{process.id}:{thread.id} | {name}:{function}:{line} - {message}"
        ),
    )
    logger.add(
        targets["error"],
        level="ERROR",
        enqueue=False,
        encoding="utf-8",
        rotation="10 MB",
        retention="90 days",
        compression="zip",
        backtrace=True,
        diagnose=False,
        format=(
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
            "{process.id}:{thread.id} | {name}:{function}:{line} - {message}"
        ),
    )
    logger.add(
        targets["failure"],
        level="WARNING",
        enqueue=False,
        encoding="utf-8",
        rotation="10 MB",
        retention="60 days",
        compression="zip",
        backtrace=True,
        diagnose=False,
        filter=_is_failure_record,
        format=(
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
            "{process.id}:{thread.id} | {name}:{function}:{line} - {message}"
        ),
    )

    intercept_handler = InterceptHandler()
    logging.basicConfig(handlers=[intercept_handler], level=0, force=True)
    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        target = logging.getLogger(logger_name)
        target.handlers = [intercept_handler]
        target.propagate = False

    _configured = True


__all__ = ["build_log_targets", "configure_logging", "logger"]
