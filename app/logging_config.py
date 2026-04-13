from __future__ import annotations

import logging
import sys
from pathlib import Path

from loguru import logger

from app.config import APP_LOG_FILE, LOG_LEVEL

_configured = False


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


def configure_logging(log_file: Path = APP_LOG_FILE, level: str = LOG_LEVEL, *, force: bool = False) -> None:
    global _configured
    if _configured and not force:
        return

    log_file.parent.mkdir(parents=True, exist_ok=True)
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
        log_file,
        level=level,
        enqueue=False,
        encoding="utf-8",
        rotation="10 MB",
        retention=5,
        backtrace=False,
        diagnose=False,
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


__all__ = ["configure_logging", "logger"]
