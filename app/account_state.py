from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re

from app.config import settings

AUTH_DIR = Path(".auth")
ACTIVE_ACCOUNT_FILE = AUTH_DIR / "active_xhs_account.txt"


@dataclass
class LoginStateFile:
    name: str
    path: str
    is_active: bool
    updated_at: str


def _default_login_state_path() -> Path:
    return Path(settings.xhs_login_state_path)


def build_profile_state_path(profile: str) -> Path:
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "-", profile.strip()).strip("-_").lower()
    if not normalized:
        raise ValueError("profile 不能为空，且至少要包含字母或数字。")
    AUTH_DIR.mkdir(parents=True, exist_ok=True)
    return AUTH_DIR / f"xiaohongshu-{normalized}.json"


def get_active_login_state_path() -> Path:
    if ACTIVE_ACCOUNT_FILE.exists():
        raw = ACTIVE_ACCOUNT_FILE.read_text(encoding="utf-8").strip()
        if raw:
            path = Path(raw)
            if path.exists():
                return path
    return _default_login_state_path()


def set_active_login_state_path(path_str: str) -> Path:
    path = Path(path_str)
    if not path.exists():
        raise FileNotFoundError(f"登录态文件不存在: {path}")
    if path.suffix.lower() != ".json":
        raise ValueError("登录态文件必须是 .json")

    AUTH_DIR.mkdir(parents=True, exist_ok=True)
    ACTIVE_ACCOUNT_FILE.write_text(str(path), encoding="utf-8")
    return path


def ensure_active_login_state() -> Path:
    path = get_active_login_state_path()
    if path.exists():
        AUTH_DIR.mkdir(parents=True, exist_ok=True)
        ACTIVE_ACCOUNT_FILE.write_text(str(path), encoding="utf-8")
    return path


def list_login_state_files() -> list[LoginStateFile]:
    AUTH_DIR.mkdir(parents=True, exist_ok=True)
    active = get_active_login_state_path().resolve(strict=False)
    files = sorted(AUTH_DIR.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    items: list[LoginStateFile] = []
    for file in files:
        stat = file.stat()
        items.append(
            LoginStateFile(
                name=file.stem,
                path=str(file),
                is_active=file.resolve(strict=False) == active,
                updated_at=datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            )
        )
    return items
