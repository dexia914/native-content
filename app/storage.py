from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, Text, create_engine, desc, select
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
                conn.execute(
                    generated_posts.update().where(generated_posts.c.id == existing.id).values(**payload)
                )
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
