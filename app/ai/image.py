import base64
import time
from pathlib import Path

import httpx
from openai import OpenAI
from PIL import Image, ImageDraw

from app.config import settings


class ImageGenerator:
    """Image generation with provider-agnostic OpenAI-compatible Images API.

    - DALL-E 3 / GPT Image model: typical OpenAI endpoint.
    - Flux.1 via compatible gateways: switch IMAGE_BASE_URL + IMAGE_MODEL.
    """

    def __init__(self) -> None:
        self.provider = settings.image_provider.lower()
        self.model = settings.image_model
        self.client = None
        if self.provider != "wanx":
            self.client = OpenAI(api_key=settings.image_api_key, base_url=settings.image_base_url)

    def generate(self, prompt: str, output_path: Path) -> Path:
        if not settings.image_api_key:
            return self._create_placeholder(output_path, prompt)

        if self.provider == "wanx":
            return self._generate_wanx(prompt, output_path)

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

    def _generate_wanx(self, prompt: str, output_path: Path) -> Path:
        headers = {
            "Authorization": f"Bearer {settings.image_api_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",
        }
        if settings.image_workspace:
            headers["X-DashScope-WorkSpace"] = settings.image_workspace

        create_url = f"{settings.image_base_url.rstrip('/')}/services/aigc/text2image/image-synthesis"
        payload = {
            "model": self.model,
            "input": {"prompt": prompt},
            "parameters": {
                "size": settings.image_size,
                "n": 1,
            },
        }

        with httpx.Client(timeout=120) as client:
            response = client.post(create_url, headers=headers, json=payload)
            self._raise_for_status_with_details(response)
            task_id = response.json()["output"]["task_id"]

            task_url = f"{settings.image_base_url.rstrip('/')}/tasks/{task_id}"
            for _ in range(60):
                task_response = client.get(
                    task_url,
                    headers={"Authorization": f"Bearer {settings.image_api_key}"},
                )
                self._raise_for_status_with_details(task_response)
                output = task_response.json()["output"]
                task_status = output["task_status"]

                if task_status == "SUCCEEDED":
                    image_url = output["results"][0]["url"]
                    image_response = client.get(image_url)
                    image_response.raise_for_status()
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    output_path.write_bytes(image_response.content)
                    return output_path

                if task_status in {"FAILED", "CANCELED", "UNKNOWN"}:
                    raise RuntimeError(f"WanX image generation failed: {output}")

                time.sleep(2)

        raise TimeoutError("WanX image generation timed out while waiting for task completion.")

    @staticmethod
    def _raise_for_status_with_details(response: httpx.Response) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = ""
            try:
                data = response.json()
                code = data.get("code")
                message = data.get("message")
                request_id = data.get("request_id")
                parts = [part for part in [code, message, f"request_id={request_id}" if request_id else None] if part]
                if parts:
                    detail = " | ".join(parts)
            except Exception:
                text = response.text.strip()
                if text:
                    detail = text

            if detail:
                raise RuntimeError(f"WanX request failed: {detail}") from exc
            raise

    @staticmethod
    def _create_placeholder(path: Path, prompt: str) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        image = Image.new("RGB", (1024, 1024), (255, 235, 247))
        draw = ImageDraw.Draw(image)
        draw.text((40, 40), "未配置图片API，使用占位图", fill=(60, 20, 45))
        draw.text((40, 120), prompt[:120], fill=(80, 40, 60))
        image.save(path)
        return path
