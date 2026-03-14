from datetime import datetime
from pathlib import Path

from app.ai.image import ImageGenerator
from app.ai.llm import LLMClient, SoftPostWriter
from app.config import settings
from app.content.collage import make_cover_collage, render_markdown
from app.models import GeneratedAssets
from app.prompts import build_softpost_prompt
from app.storage import save_generated_post


class SoftPostPipeline:
    def __init__(self) -> None:
        self.writer = SoftPostWriter(LLMClient())
        self.image_gen = ImageGenerator()

    def run(self, topic: str, audience: str, monetization_core: str) -> GeneratedAssets:
        prompt = build_softpost_prompt(topic, audience, monetization_core)
        post = self.writer.generate(topic, audience, monetization_core, prompt)

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = Path(settings.output_dir) / f"{stamp}_{topic[:18]}"
        base.mkdir(parents=True, exist_ok=True)

        raw = self.image_gen.generate(post.image_prompt, base / "raw.png")
        collage = make_cover_collage(raw, post, base / "cover.png")
        md = render_markdown(post, collage, base / "post.md")
        assets = GeneratedAssets(post=post, raw_image_path=raw, collage_path=collage, markdown_path=md)
        save_generated_post(assets, monetization_core)
        return assets
