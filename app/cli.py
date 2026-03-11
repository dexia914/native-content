from pathlib import Path

import typer
from rich import print

from app.content.generator import SoftPostPipeline
from app.distribution.xiaohongshu import publish_sync

app = typer.Typer(help="动态选题 -> 小红书软文(文案+图片) 生成与分发")


@app.command()
def generate(
    topic: str = typer.Option(..., help="动态选题，如：看短剧赚钱"),
    audience: str = typer.Option("宝妈,大学生", help="目标受众"),
    core: str = typer.Option("玩一玩就能赚钱、看短剧赚钱", help="核心卖点"),
) -> None:
    pipeline = SoftPostPipeline()
    assets = pipeline.run(topic=topic, audience=audience, monetization_core=core)

    print("[green]生成完成[/green]")
    print(f"标题: {assets.post.title}")
    print(f"封面: {assets.collage_path}")
    print(f"稿件: {assets.markdown_path}")


@app.command()
def publish(
    artifact_dir: str = typer.Option(..., help="generate 输出目录，如 outputs/20260701_xxx"),
) -> None:
    folder = Path(artifact_dir)
    markdown = folder / "post.md"
    cover = folder / "cover.png"
    if not markdown.exists() or not cover.exists():
        raise typer.BadParameter("artifact_dir 下缺少 post.md 或 cover.png")

    # Minimal load from markdown (title/body separated by first heading line)
    lines = markdown.read_text(encoding="utf-8").splitlines()
    title = lines[0].replace("#", "").strip() if lines else ""
    body = "\n".join([ln for ln in lines[3:] if not ln.startswith("#")]).strip()

    from app.models import GeneratedAssets, SoftPost

    post = SoftPost(topic="", audience="", title=title, body=body, image_prompt="", hashtags=[])
    assets = GeneratedAssets(post=post, raw_image_path=cover, collage_path=cover, markdown_path=markdown)
    publish_sync(assets)
    print("[green]已提交到小红书发布页（草稿/待发布）[/green]")


if __name__ == "__main__":
    app()
