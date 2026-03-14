import json
from typing import Any

from openai import OpenAI

from app.config import settings
from app.models import SoftPost


class LLMClient:
    """Provider-agnostic client that speaks OpenAI-compatible API."""

    def __init__(self) -> None:
        self.client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
        self.model = settings.llm_model

    def complete_json(self, prompt: str) -> dict[str, Any]:
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0.8,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "你是严谨的 JSON 生成器。"},
                {"role": "user", "content": prompt},
            ],
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)


class SoftPostWriter:
    def __init__(self, llm_client: LLMClient) -> None:
        self.llm_client = llm_client

    def generate(self, topic: str, audience: str, monetization_core: str, prompt: str) -> SoftPost:
        data = self.llm_client.complete_json(prompt)
        image_prompt = data.get(
            "image_prompt",
            f"小红书封面底图，主题：{topic}，高点击风格，顶部和底部留白",
        )
        if settings.no_text_in_image:
            image_prompt = (
                f"{image_prompt}。"
                "不要生成任何文字、中文、英文、繁体字、数字、水印、logo、UI界面、聊天截图。"
                "只生成适合后期排版的封面背景图。"
            )

        return SoftPost(
            topic=topic,
            audience=audience,
            title=data.get("title", "碎片时间也能做的低门槛副业思路"),
            body=data.get("body", "先收藏，后面我再补充更完整的实操细节。"),
            image_prompt=image_prompt,
            hashtags=data.get("hashtags", ["副业", "大学生兼职", "宝妈副业"]),
        )
