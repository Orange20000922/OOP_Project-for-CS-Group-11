from __future__ import annotations

from datetime import date
from pathlib import Path

from app.logging_config import build_log_targets, configure_logging, logger


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def test_configure_logging_splits_combined_http_error_and_failure_files(tmp_path: Path):
    base_log_file = tmp_path / "logs" / "test.log"
    configure_logging(log_file=base_log_file, force=True)

    logger.info("Application ready")
    logger.info("HTTP GET /health -> 200 (1.23 ms)")
    logger.warning("Query week request failed with auth error: 未登录")
    logger.error("SCNU fetch task failed for 20250001")

    resolved_targets = build_log_targets(base_log_file, for_date=date.today())
    combined_text = _read_text(resolved_targets["combined_daily"])
    http_text = _read_text(resolved_targets["http_daily"])
    error_text = _read_text(resolved_targets["error"])
    failure_text = _read_text(resolved_targets["failure"])

    assert "Application ready" in combined_text
    assert "HTTP GET /health -> 200" not in combined_text

    assert "HTTP GET /health -> 200" in http_text

    assert "SCNU fetch task failed for 20250001" in error_text
    assert "Query week request failed with auth error" not in error_text

    assert "Query week request failed with auth error" in failure_text
    assert "SCNU fetch task failed for 20250001" in failure_text
