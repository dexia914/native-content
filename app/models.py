from dataclasses import dataclass
from pathlib import Path


@dataclass
class SoftPost:
    topic: str
    audience: str
    title: str
    body: str
    image_prompt: str
    hashtags: list[str]


@dataclass
class GeneratedAssets:
    post: SoftPost
    raw_image_path: Path
    collage_path: Path
    markdown_path: Path
