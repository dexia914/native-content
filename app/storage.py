from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, MetaData, String, Table, Text, create_engine, desc, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.models import GeneratedAssets

metadata = MetaData()

generated_posts = Table(
    "generated_posts",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("artifact_dir", String(255), nullable=False, unique=True),
    Column("topic", String(255), nullable=False),
    Column("audience", String(255), nullable=False),
    Column("core", String(255), nullable=False),
    Column("title", String(255), nullable=False),
    Column("body", Text, nullable=False),
    Column("hashtags_json", Text, nullable=False),
    Column("cover_path", String(255), nullable=False),
    Column("markdown_path", String(255), nullable=False),
    Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
)

xhs_accounts = Table(
    "xhs_accounts",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("profile", String(64), nullable=False, unique=True),
    Column("storage_state_json", Text, nullable=False),
    Column("is_active", Boolean, nullable=False, default=False),
    Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
    Column("updated_at", DateTime, nullable=False, default=datetime.utcnow),
)

_engine: Engine | None = None
_schema_ready = False


@dataclass
class GeneratedPostRecord:
    artifact_dir: str
    topic: str
    audience: str
    core: str
    title: str
    body: str
    hashtags: list[str]
    cover_path: str
    markdown_path: str
    created_at: datetime


@dataclass
class XHSAccountRecord:
    id: int
    profile: str
    storage_state: dict
    is_active: bool
    created_at: datetime
    updated_at: datetime


def _get_engine() -> Engine | None:
    global _engine
    if not settings.mysql_url:
        return None
    if _engine is None:
        _engine = create_engine(
            settings.mysql_url,
            pool_pre_ping=True,
            pool_recycle=settings.mysql_pool_recycle,
            pool_size=settings.mysql_pool_size,
        )
    return _engine


def ensure_storage_schema() -> None:
    global _schema_ready
    if _schema_ready:
        return
    engine = _get_engine()
    if engine is None:
        return
    metadata.create_all(engine)
    _schema_ready = True


def save_generated_post(assets: GeneratedAssets, monetization_core: str) -> None:
    engine = _get_engine()
    if engine is None:
        return
    ensure_storage_schema()
    artifact_dir = str(assets.markdown_path.parent)
    payload = {
        "artifact_dir": artifact_dir,
        "topic": assets.post.topic,
        "audience": assets.post.audience,
        "core": monetization_core,
        "title": assets.post.title,
        "body": assets.post.body,
        "hashtags_json": json.dumps(assets.post.hashtags, ensure_ascii=False),
        "cover_path": str(assets.collage_path),
        "markdown_path": str(assets.markdown_path),
        "created_at": datetime.utcnow(),
    }
    try:
        with engine.begin() as conn:
            existing = conn.execute(
                select(generated_posts.c.id).where(generated_posts.c.artifact_dir == artifact_dir)
            ).first()
            if existing:
                conn.execute(generated_posts.update().where(generated_posts.c.id == existing.id).values(**payload))
            else:
                conn.execute(generated_posts.insert().values(**payload))
    except SQLAlchemyError as exc:
        raise RuntimeError(f"Failed to save generated post to MySQL: {exc}") from exc


def list_recent_generated_posts(limit: int = 10) -> list[GeneratedPostRecord]:
    engine = _get_engine()
    if engine is None:
        return []
    ensure_storage_schema()
    try:
        with engine.begin() as conn:
            rows = conn.execute(
                select(generated_posts)
                .order_by(desc(generated_posts.c.created_at), desc(generated_posts.c.id))
                .limit(limit)
            ).mappings()
            return [
                GeneratedPostRecord(
                    artifact_dir=row["artifact_dir"],
                    topic=row["topic"],
                    audience=row["audience"],
                    core=row["core"],
                    title=row["title"],
                    body=row["body"],
                    hashtags=json.loads(row["hashtags_json"]),
                    cover_path=row["cover_path"],
                    markdown_path=row["markdown_path"],
                    created_at=row["created_at"],
                )
                for row in rows
            ]
    except SQLAlchemyError as exc:
        raise RuntimeError(f"Failed to load generated posts from MySQL: {exc}") from exc


def _row_to_xhs_account(row: dict) -> XHSAccountRecord:
    return XHSAccountRecord(
        id=row["id"],
        profile=row["profile"],
        storage_state=json.loads(row["storage_state_json"]),
        is_active=bool(row["is_active"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def save_xhs_account(profile: str, storage_state: dict, make_active: bool = True) -> XHSAccountRecord:
    engine = _get_engine()
    if engine is None:
        raise RuntimeError("MYSQL_URL is not configured, cannot store Xiaohongshu accounts in MySQL.")

    ensure_storage_schema()
    now = datetime.utcnow()
    payload = {
        "profile": profile,
        "storage_state_json": json.dumps(storage_state, ensure_ascii=False),
        "updated_at": now,
    }

    try:
        with engine.begin() as conn:
            existing = conn.execute(select(xhs_accounts).where(xhs_accounts.c.profile == profile)).mappings().first()
            if make_active:
                conn.execute(xhs_accounts.update().values(is_active=False))
            if existing:
                values = dict(payload)
                if make_active:
                    values["is_active"] = True
                conn.execute(xhs_accounts.update().where(xhs_accounts.c.id == existing["id"]).values(**values))
            else:
                values = {
                    **payload,
                    "is_active": make_active,
                    "created_at": now,
                }
                conn.execute(xhs_accounts.insert().values(**values))

            row = conn.execute(select(xhs_accounts).where(xhs_accounts.c.profile == profile)).mappings().first()
            if row is None:
                raise RuntimeError("Failed to reload saved Xiaohongshu account.")
            return _row_to_xhs_account(row)
    except SQLAlchemyError as exc:
        raise RuntimeError(f"Failed to save Xiaohongshu account to MySQL: {exc}") from exc


def list_xhs_accounts() -> list[XHSAccountRecord]:
    engine = _get_engine()
    if engine is None:
        return []
    ensure_storage_schema()
    try:
        with engine.begin() as conn:
            rows = conn.execute(
                select(xhs_accounts)
                .order_by(desc(xhs_accounts.c.is_active), desc(xhs_accounts.c.updated_at), desc(xhs_accounts.c.id))
            ).mappings()
            return [_row_to_xhs_account(row) for row in rows]
    except SQLAlchemyError as exc:
        raise RuntimeError(f"Failed to load Xiaohongshu accounts from MySQL: {exc}") from exc


def get_xhs_account(profile: str) -> XHSAccountRecord | None:
    engine = _get_engine()
    if engine is None:
        return None
    ensure_storage_schema()
    try:
        with engine.begin() as conn:
            row = conn.execute(select(xhs_accounts).where(xhs_accounts.c.profile == profile)).mappings().first()
            return _row_to_xhs_account(row) if row else None
    except SQLAlchemyError as exc:
        raise RuntimeError(f"Failed to load Xiaohongshu account from MySQL: {exc}") from exc


def get_active_xhs_account() -> XHSAccountRecord | None:
    engine = _get_engine()
    if engine is None:
        return None
    ensure_storage_schema()
    try:
        with engine.begin() as conn:
            row = conn.execute(
                select(xhs_accounts)
                .where(xhs_accounts.c.is_active.is_(True))
                .order_by(desc(xhs_accounts.c.updated_at), desc(xhs_accounts.c.id))
            ).mappings().first()
            return _row_to_xhs_account(row) if row else None
    except SQLAlchemyError as exc:
        raise RuntimeError(f"Failed to load active Xiaohongshu account from MySQL: {exc}") from exc


def set_active_xhs_account(profile: str) -> XHSAccountRecord:
    engine = _get_engine()
    if engine is None:
        raise RuntimeError("MYSQL_URL is not configured, cannot switch Xiaohongshu accounts in MySQL.")

    ensure_storage_schema()
    try:
        with engine.begin() as conn:
            existing = conn.execute(select(xhs_accounts).where(xhs_accounts.c.profile == profile)).mappings().first()
            if existing is None:
                raise FileNotFoundError(f"Xiaohongshu account profile does not exist: {profile}")

            conn.execute(xhs_accounts.update().values(is_active=False))
            conn.execute(
                xhs_accounts.update().where(xhs_accounts.c.profile == profile).values(
                    is_active=True,
                    updated_at=datetime.utcnow(),
                )
            )
            row = conn.execute(select(xhs_accounts).where(xhs_accounts.c.profile == profile)).mappings().first()
            if row is None:
                raise RuntimeError("Failed to reload active Xiaohongshu account.")
            return _row_to_xhs_account(row)
    except SQLAlchemyError as exc:
        raise RuntimeError(f"Failed to switch Xiaohongshu account in MySQL: {exc}") from exc
