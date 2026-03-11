from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.config import settings
from app.models import SoftPost


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if settings.font_path:
        return ImageFont.truetype(settings.font_path, size=size)
    return ImageFont.load_default()


def make_cover_collage(raw_image_path: Path, post: SoftPost, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    image = cv2.imread(str(raw_image_path))
    if image is None:
        raise FileNotFoundError(f"Cannot read image: {raw_image_path}")

    image = cv2.resize(image, (1080, 1440))

    overlay = image.copy()
    cv2.rectangle(overlay, (0, 0), (1080, 360), (255, 88, 163), -1)
    cv2.addWeighted(overlay, 0.35, image, 0.65, 0, image)

    pil_img = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil_img)

    title_font = _load_font(56)
    body_font = _load_font(32)

    draw.text((58, 72), "边玩边赚 / 碎片时间", font=body_font, fill=(255, 255, 255))
    draw.text((58, 130), post.title[:22], font=title_font, fill=(255, 255, 255))
    draw.text((58, 230), "宝妈/大学生友好 | 真实体验向", font=body_font, fill=(255, 255, 255))

    y = 1280
    draw.rounded_rectangle((44, y, 1036, 1410), radius=26, fill=(255, 255, 255, 235))
    draw.text((76, y + 24), "#" + " #".join(post.hashtags[:5]), font=body_font, fill=(73, 25, 52))

    pil_img.save(out_path)
    return out_path


def render_markdown(post: SoftPost, collage_path: Path, markdown_path: Path) -> Path:
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    tags = " ".join(post.hashtags)
    content = (
        f"# {post.title}\n\n"
        f"![封面图]({collage_path.name})\n\n"
        f"{post.body}\n\n"
        f"{tags}\n"
    )
    markdown_path.write_text(content, encoding="utf-8")
    return markdown_path
