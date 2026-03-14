from pathlib import Path

import typer
from rich import print

from app.content.generator import SoftPostPipeline
from app.distribution.xiaohongshu import export_login_state_sync, get_auth_status, publish_sync

app = typer.Typer(help="动态选题 -> 小红书软文（文案+图片）生成与分发")


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
    auto_submit: bool = typer.Option(False, "--auto-submit", help="自动点击发布按钮"),
) -> None:
    folder = Path(artifact_dir)
    markdown = folder / "post.md"
    cover = folder / "cover.png"
    if not markdown.exists() or not cover.exists():
        raise typer.BadParameter("artifact_dir 下缺少 post.md 或 cover.png")

    lines = markdown.read_text(encoding="utf-8").splitlines()
    title = lines[0].replace("#", "").strip() if lines else ""
    content_lines = [ln.strip() for ln in lines[3:] if ln.strip()]
    hashtags = [ln for ln in content_lines if ln.startswith("#")]
    body = "\n".join([ln for ln in content_lines if not ln.startswith("#")]).strip()

    from app.models import GeneratedAssets, SoftPost

    post = SoftPost(topic="", audience="", title=title, body=body, image_prompt="", hashtags=hashtags)
    assets = GeneratedAssets(post=post, raw_image_path=cover, collage_path=cover, markdown_path=markdown)
    publish_sync(assets, auto_submit=auto_submit)

    if auto_submit:
        print("[green]已尝试自动提交发布[/green]")
    else:
        print("[green]已填写到小红书发布页（未自动点击发布）[/green]")


@app.command()
def auth() -> None:
    state_path = export_login_state_sync()
    print(f"[green]登录态已保存[/green]: {state_path}")


@app.command("auth-status")
def auth_status() -> None:
    status = get_auth_status()
    print(f"登录态文件: {status['state_path']}")
    print(f"关键 cookie 数量: {status['cookie_count']}")
    print(f"最早到期 cookie: {status['earliest_cookie']}")
    print(f"最早到期时间(UTC): {status['earliest_expiry_utc']}")
    print(f"剩余天数: {status['days_left']}")
    print(f"状态: {status['level']}")
    if status["message"]:
        print(status["message"])


if __name__ == "__main__":
    app()
