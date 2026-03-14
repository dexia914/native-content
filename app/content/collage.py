from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.config import settings
from app.models import SoftPost


def _font_candidates() -> list[str]:
    return [
        # Windows
        "C:/Windows/Fonts/msyhbd.ttc",
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/simsun.ttc",
        # Ubuntu / Debian common CJK fonts
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc",
        "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/arphic/uming.ttc",
        "/usr/share/fonts/truetype/arphic/ukai.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if settings.font_path:
        return ImageFont.truetype(settings.font_path, size=size)

    for font_path in _font_candidates():
        if Path(font_path).exists():
            return ImageFont.truetype(font_path, size=size)

    return ImageFont.load_default()


def _read_image(path: Path):
    # cv2.imread often fails on Windows when the path contains Chinese characters.
    data = np.fromfile(str(path), dtype=np.uint8)
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    if not text:
        return 0
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def _wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
    max_lines: int,
) -> list[str]:
    if not text:
        return [""]

    lines: list[str] = []
    current = ""

    for char in text:
        candidate = f"{current}{char}"
        if _text_width(draw, candidate, font) <= max_width:
            current = candidate
            continue

        if current:
            lines.append(current)
            current = char
        else:
            lines.append(candidate)
            current = ""

        if len(lines) == max_lines:
            break

    if current and len(lines) < max_lines:
        lines.append(current)

    remaining = text[len("".join(lines)) :]
    if remaining and lines:
        last = lines[-1]
        ellipsis = "..."
        while last and _text_width(draw, f"{last}{ellipsis}", font) > max_width:
            last = last[:-1]
        lines[-1] = f"{last}{ellipsis}" if last else ellipsis

    return lines[:max_lines]


def _fit_font_size(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_width: int,
    start_size: int,
    min_size: int,
    max_lines: int,
) -> tuple[ImageFont.ImageFont, list[str]]:
    for size in range(start_size, min_size - 1, -2):
        font = _load_font(size)
        lines = _wrap_text(draw, text, font, max_width=max_width, max_lines=max_lines)
        if lines and _text_width(draw, lines[-1], font) <= max_width:
            return font, lines
    font = _load_font(min_size)
    return font, _wrap_text(draw, text, font, max_width=max_width, max_lines=max_lines)


def _fit_tag_line(
    draw: ImageDraw.ImageDraw,
    tags: list[str],
    max_width: int,
    start_size: int,
    min_size: int,
) -> tuple[ImageFont.ImageFont, str]:
    text = "  ".join(f"#{tag.lstrip('#')}" for tag in tags)
    for size in range(start_size, min_size - 1, -2):
        font = _load_font(size)
        if _text_width(draw, text, font) <= max_width:
            return font, text

    font = _load_font(min_size)
    truncated = text
    while truncated and _text_width(draw, f"{truncated}...", font) > max_width:
        truncated = truncated[:-1]
    return font, f"{truncated}..." if truncated else ""


def make_cover_collage(raw_image_path: Path, post: SoftPost, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    image = _read_image(raw_image_path)
    if image is None:
        raise FileNotFoundError(f"Cannot read image: {raw_image_path}")

    image = cv2.resize(image, (1080, 1440))

    # Use a top scrim instead of blurring the full image so the background keeps its texture.
    gradient = np.zeros((480, 1080, 3), dtype=np.uint8)
    gradient[:] = (40, 18, 26)
    alpha = np.linspace(0.78, 0.0, 480, dtype=np.float32).reshape(480, 1, 1)
    image[:480] = (gradient * alpha + image[:480] * (1 - alpha)).astype(np.uint8)

    pil_img = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil_img, "RGBA")

    card_left = 44
    card_top = 48
    card_right = 1036
    card_bottom = 422
    draw.rounded_rectangle((card_left, card_top, card_right, card_bottom), radius=36, fill=(231, 74, 135, 212))

    label_font = _load_font(28)
    subtitle_font = _load_font(30)
    title_font, title_lines = _fit_font_size(
        draw,
        post.title,
        max_width=card_right - card_left - 84,
        start_size=58,
        min_size=40,
        max_lines=3,
    )

    draw.text((84, 86), "碎片时间也能做", font=label_font, fill=(255, 244, 248, 255))

    title_y = 140
    title_line_height = title_font.size + 16
    for line in title_lines:
        draw.text((84, title_y), line, font=title_font, fill=(255, 255, 255, 255))
        title_y += title_line_height

    draw.text((84, 362), "低门槛尝试 | 真实体验向", font=subtitle_font, fill=(255, 242, 246, 245))

    tag_left = 52
    tag_top = 1228
    tag_right = 1028
    tag_bottom = 1384
    draw.rounded_rectangle((tag_left, tag_top, tag_right, tag_bottom), radius=28, fill=(255, 255, 255, 238))

    tag_font, tag_text = _fit_tag_line(
        draw,
        post.hashtags[:5],
        max_width=tag_right - tag_left - 52,
        start_size=28,
        min_size=20,
    )
    draw.text((78, 1282), tag_text, font=tag_font, fill=(91, 33, 59, 255))

    pil_img.save(out_path)
    return out_path


def render_markdown(post: SoftPost, collage_path: Path, markdown_path: Path) -> Path:
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    tags = " ".join(f"#{tag.lstrip('#')}" for tag in post.hashtags)
    content = (
        f"# {post.title}\n\n"
        f"![封面图]({collage_path.name})\n\n"
        f"{post.body}\n\n"
        f"{tags}\n"
    )
    markdown_path.write_text(content, encoding="utf-8")
    return markdown_path
