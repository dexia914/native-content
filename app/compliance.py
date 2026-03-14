from __future__ import annotations

import re

from app.config import settings
from app.models import SoftPost

RISKY_PHRASES: list[tuple[str, str]] = [
    ("赚钱", "攒点零花"),
    ("变现", "做记录"),
    ("搞钱", "提升效率"),
    ("副业", "日常尝试"),
    ("网赚", "线上体验"),
    ("提现", "查看记录"),
    ("月入", "每月积累"),
    ("日入", "单日记录"),
    ("稳稳的", "相对稳定"),
    ("躺赚", "顺手做"),
    ("零成本赚钱", "低门槛尝试"),
    ("评论区敲", "评论区交流"),
    ("发你入口", "一起交流体验"),
    ("私信我", "欢迎交流"),
    ("带你做", "分享过程"),
]

RISKY_HASHTAGS = {
    "副业",
    "搞钱",
    "赚钱",
    "变现",
    "网赚",
    "兼职",
    "提现",
}


def apply_compliance_mode(post: SoftPost) -> SoftPost:
    if not settings.xhs_compliance_mode:
        return post

    title = _sanitize_text(post.title)
    body = _sanitize_text(post.body)
    hashtags = _sanitize_hashtags(post.hashtags)
    image_prompt = _sanitize_image_prompt(post.image_prompt)

    if "风险提示" not in body and "请理性看待" not in body:
        body = f"{body}\n\n风险提示：内容仅作个人体验分享，请理性看待，不作收益承诺。".strip()

    return SoftPost(
        topic=post.topic,
        audience=post.audience,
        title=title,
        body=body,
        image_prompt=image_prompt,
        hashtags=hashtags,
    )


def _sanitize_text(text: str) -> str:
    cleaned = text
    for source, target in RISKY_PHRASES:
        cleaned = cleaned.replace(source, target)

    cleaned = re.sub(r"(日入|月入)\s*\d+[元块wW万]*", "记录会因人而异", cleaned)
    cleaned = re.sub(r"赚了?\s*\d+[元块wW万]*", "有一些记录反馈", cleaned)
    cleaned = re.sub(r"暴富", "过度期待", cleaned)
    cleaned = re.sub(r"保证收益|稳定工资|轻松月入", "绝对化表述", cleaned)
    return cleaned


def _sanitize_hashtags(tags: list[str]) -> list[str]:
    safe_tags: list[str] = []
    for tag in tags:
        normalized = tag.lstrip("#").strip()
        if not normalized:
            continue
        if any(risky in normalized for risky in RISKY_HASHTAGS):
            replacement = normalized.replace("副业", "生活分享").replace("兼职", "日常记录").replace("赚钱", "体验记录")
            replacement = replacement.replace("变现", "效率").replace("搞钱", "时间利用")
            normalized = replacement
        if normalized not in safe_tags:
            safe_tags.append(normalized)

    fallback_tags = ["日常分享", "经验记录", "时间管理", "生活方式"]
    for tag in fallback_tags:
        if len(safe_tags) >= 8:
            break
        if tag not in safe_tags:
            safe_tags.append(tag)
    return safe_tags[:12]


def _sanitize_image_prompt(prompt: str) -> str:
    cleaned = _sanitize_text(prompt)
    compliance_suffix = "整体呈现真实生活分享风格，避免营销感、广告感、收益暗示。"
    if compliance_suffix not in cleaned:
        cleaned = f"{cleaned}。{compliance_suffix}"
    return cleaned
