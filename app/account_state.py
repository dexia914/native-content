from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re

from app.storage import (
    XHSAccountRecord,
    get_active_xhs_account,
    get_xhs_account,
    list_xhs_accounts,
    save_xhs_account,
    set_active_xhs_account,
)


@dataclass
class LoginAccount:
    profile: str
    is_active: bool
    updated_at: str


def build_profile_name(profile: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "-", profile.strip()).strip("-_").lower()
    if not normalized:
        raise ValueError("profile 不能为空，且至少要包含字母或数字。")
    return normalized


def list_login_accounts() -> list[LoginAccount]:
    return [
        LoginAccount(
            profile=record.profile,
            is_active=record.is_active,
            updated_at=record.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        )
        for record in list_xhs_accounts()
    ]


def get_active_login_account() -> XHSAccountRecord | None:
    return get_active_xhs_account()


def get_login_account(profile: str) -> XHSAccountRecord | None:
    return get_xhs_account(build_profile_name(profile))


def save_login_account(profile: str, storage_state: dict, make_active: bool = True) -> XHSAccountRecord:
    return save_xhs_account(build_profile_name(profile), storage_state, make_active=make_active)


def set_active_login_account(profile: str) -> XHSAccountRecord:
    return set_active_xhs_account(build_profile_name(profile))


def format_account_option_label(profile: str, updated_at: datetime) -> str:
    return f"{profile} · {updated_at.strftime('%Y-%m-%d %H:%M:%S')}"
