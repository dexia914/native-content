import base64
from pathlib import Path

from openai import OpenAI
from PIL import Image, ImageDraw

from app.config import settings


class ImageGenerator:
    """Image generation with provider-agnostic OpenAI-compatible Images API.

    - DALL-E 3 / GPT Image model: typical OpenAI endpoint.
    - Flux.1 via compatible gateways: switch IMAGE_BASE_URL + IMAGE_MODEL.
    """

    def __init__(self) -> None:
        self.client = OpenAI(api_key=settings.image_api_key, base_url=settings.image_base_url)
        self.model = settings.image_model

    def generate(self, prompt: str, output_path: Path) -> Path:
        if not settings.image_api_key:
            return self._create_placeholder(output_path, prompt)

        result = self.client.images.generate(
            model=self.model,
            prompt=prompt,
            size=settings.image_size,
        )
        b64 = result.data[0].b64_json
        if not b64:
            return self._create_placeholder(output_path, prompt)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(base64.b64decode(b64))
        return output_path

    @staticmethod
    def _create_placeholder(path: Path, prompt: str) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        image = Image.new("RGB", (1024, 1024), (255, 235, 247))
        draw = ImageDraw.Draw(image)
        draw.text((40, 40), "未配置图片API，使用占位图", fill=(60, 20, 45))
        draw.text((40, 120), prompt[:120], fill=(80, 40, 60))
        image.save(path)
        return path
