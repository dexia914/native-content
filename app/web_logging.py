from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path("logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "web.log"

_configured = False


def get_web_logger() -> logging.Logger:
    global _configured
    logger = logging.getLogger("softpost.web")
    if _configured:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    _configured = True
    return logger


def read_recent_logs(limit: int = 200) -> list[str]:
    if not LOG_FILE.exists():
        return []
    lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
    error_lines = [line for line in lines if " | ERROR | " in line or "Traceback" in line]
    return error_lines[-limit:]
