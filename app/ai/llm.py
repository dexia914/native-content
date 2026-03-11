import json
from typing import Any

from openai import OpenAI

from app.config import settings
from app.models import SoftPost


class LLMClient:
    """Provider-agnostic client that speaks OpenAI-compatible API.

    DeepSeek / Qwen / many gateways expose compatible chat endpoint.
    You can switch provider by replacing base_url + api_key + model in .env.
    """

    def __init__(self) -> None:
        self.client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
        self.model = settings.llm_model

    def complete_json(self, prompt: str) -> dict[str, Any]:
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0.8,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "你是严谨的JSON生成器。"},
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
        return SoftPost(
            topic=topic,
            audience=audience,
            title=data.get("title", "今天发现一个碎片时间副业思路"),
            body=data.get("body", "先收藏，后面我再补充实操细节。"),
            image_prompt=data.get("image_prompt", f"小红书封面，主题：{topic}，高点击风格"),
            hashtags=data.get("hashtags", ["#副业", "#大学生", "#宝妈"]),
        )
