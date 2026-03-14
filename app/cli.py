from pathlib import Path

import typer
from rich import print

from app.account_state import build_profile_state_path
from app.content.generator import SoftPostPipeline
from app.distribution.xiaohongshu import (
    export_login_state_sync,
    export_login_state_to_sync,
    get_auth_status,
    publish_sync,
)

app = typer.Typer(help="动态选题 -> 小红书软文与封面生成、登录态管理、自动发布")


@app.command()
def generate(
    topic: str = typer.Option(..., help="内容选题，例如：看短剧赚钱"),
    audience: str = typer.Option("宝妈,大学生", help="目标受众，多个值用英文逗号分隔"),
    core: str = typer.Option("玩一玩就能赚钱、看短剧赚钱", help="核心卖点或重点表达"),
) -> None:
    pipeline = SoftPostPipeline()
    assets = pipeline.run(topic=topic, audience=audience, monetization_core=core)

    print("[green]生成完成[/green]")
    print(f"标题: {assets.post.title}")
    print(f"封面: {assets.collage_path}")
    print(f"稿件: {assets.markdown_path}")


@app.command()
def publish(
    artifact_dir: str = typer.Option(..., help="generate 输出目录，例如 outputs/20260701_xxx"),
    auto_submit: bool = typer.Option(False, "--auto-submit", help="自动点击最终发布按钮"),
) -> None:
    folder = Path(artifact_dir)
    markdown = folder / "post.md"
    cover = folder / "cover.png"
    if not markdown.exists() or not cover.exists():
        raise typer.BadParameter("artifact_dir 下缺少 post.md 或 cover.png")

    lines = markdown.read_text(encoding="utf-8").splitlines()
    title = lines[0].replace("#", "").strip() if lines else ""
    content_lines = [line.strip() for line in lines[3:] if line.strip()]
    hashtags = [line for line in content_lines if line.startswith("#")]
    body = "\n".join(line for line in content_lines if not line.startswith("#")).strip()

    from app.models import GeneratedAssets, SoftPost

    post = SoftPost(topic="", audience="", title=title, body=body, image_prompt="", hashtags=hashtags)
    assets = GeneratedAssets(post=post, raw_image_path=cover, collage_path=cover, markdown_path=markdown)
    publish_sync(assets, auto_submit=auto_submit)

    if auto_submit:
        print("[green]已尝试自动提交发布[/green]")
    else:
        print("[green]已填写到小红书发布页，但未自动点击最终发布[/green]")


@app.command()
def auth(
    profile: str = typer.Option(
        "",
        "--profile",
        help="新增账号配置名，例如 main、backup。会保存到 .auth/xiaohongshu-<profile>.json",
    )
) -> None:
    if profile.strip():
        state_path = build_profile_state_path(profile)
        exported = export_login_state_to_sync(state_path)
        print(f"[green]新增账号登录态已保存[/green]: {exported}")
        print("[green]该账号已自动切换为当前生效账号[/green]")
        return

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
