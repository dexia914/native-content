import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

from app.config import settings
from app.models import GeneratedAssets


class XiaohongshuPublisher:
    async def publish(self, assets: GeneratedAssets) -> None:
        """Upload note draft via Xiaohongshu Creator Center.

        DOM selectors may change; update selectors in this method when needed.
        Make sure you've exported login state to XHS_LOGIN_STATE_PATH before using this.
        """
        state_path = Path(settings.xhs_login_state_path)
        if not state_path.exists():
            raise FileNotFoundError(
                f"Missing login state file: {state_path}. "
                "Please login once and export storage state manually."
            )

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=settings.xhs_headless)
            context = await browser.new_context(storage_state=str(state_path))
            page = await context.new_page()

            await page.goto(f"{settings.xhs_base_url}/publish/publish", wait_until="networkidle")
            await page.set_input_files("input[type='file']", str(assets.collage_path))

            await page.fill("textarea", f"{assets.post.body}\n\n{' '.join(assets.post.hashtags)}")

            # In many flows there is a separate title input.
            title_inputs = page.locator("input[placeholder*='标题']")
            if await title_inputs.count() > 0:
                await title_inputs.first.fill(assets.post.title)

            await asyncio.sleep(1)
            await context.close()
            await browser.close()


def publish_sync(assets: GeneratedAssets) -> None:
    asyncio.run(XiaohongshuPublisher().publish(assets))
