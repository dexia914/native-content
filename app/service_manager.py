from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
import ctypes
from pathlib import Path

from app.web_logging import LOG_FILE, get_web_logger

PID_DIR = Path("run")
PID_DIR.mkdir(parents=True, exist_ok=True)
PID_FILE = PID_DIR / "softpost.pid"

logger = get_web_logger()


def _read_pid() -> int | None:
    if not PID_FILE.exists():
        return None
    try:
        return int(PID_FILE.read_text(encoding="utf-8").strip())
    except Exception:
        return None


def _is_running(pid: int) -> bool:
    if pid <= 0:
        return False

    if os.name == "nt":
        kernel32 = ctypes.windll.kernel32
        process = kernel32.OpenProcess(0x1000, False, pid)
        if not process:
            return False
        try:
            exit_code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(process, ctypes.byref(exit_code)):
                return False
            return exit_code.value == 259
        finally:
            kernel32.CloseHandle(process)

    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _cleanup_stale_pid() -> None:
    pid = _read_pid()
    if pid is None:
        return
    if not _is_running(pid):
        PID_FILE.unlink(missing_ok=True)


def start_main() -> None:
    _cleanup_stale_pid()
    existing = _read_pid()
    if existing and _is_running(existing):
        print(f"softpost web is already running, pid={existing}")
        return

    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.web:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
    ]

    log_handle = open(LOG_FILE, "a", encoding="utf-8")
    kwargs: dict = {
        "stdout": log_handle,
        "stderr": log_handle,
        "stdin": subprocess.DEVNULL,
        "cwd": str(Path.cwd()),
        "close_fds": True,
    }

    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        process = subprocess.Popen(command, creationflags=creationflags, **kwargs)
    else:
        process = subprocess.Popen(command, start_new_session=True, **kwargs)

    PID_FILE.write_text(str(process.pid), encoding="utf-8")
    logger.info("service | started | pid=%s", process.pid)
    print(f"softpost web started in background, pid={process.pid}")
    print("open http://127.0.0.1:8000")


def stop_main() -> None:
    pid = _read_pid()
    if pid is None:
        print("softpost web is not running")
        return

    if not _is_running(pid):
        PID_FILE.unlink(missing_ok=True)
        print("softpost web is not running")
        return

    try:
        os.kill(pid, signal.SIGTERM)
    except OSError as exc:
        PID_FILE.unlink(missing_ok=True)
        logger.exception("service | stop failed | pid=%s", pid)
        print(f"failed to stop softpost web, pid={pid}, error={exc}")
        return

    for _ in range(30):
        if not _is_running(pid):
            PID_FILE.unlink(missing_ok=True)
            logger.info("service | stopped | pid=%s", pid)
            print(f"softpost web stopped, pid={pid}")
            return
        time.sleep(0.2)

    print(f"softpost web stop requested, process may still be shutting down, pid={pid}")


def status_main() -> None:
    _cleanup_stale_pid()
    pid = _read_pid()
    if pid is None:
        print("softpost web is not running")
        return

    if _is_running(pid):
        print(f"softpost web is running, pid={pid}")
        print("url=http://127.0.0.1:8000")
    else:
        PID_FILE.unlink(missing_ok=True)
        print("softpost web is not running")
