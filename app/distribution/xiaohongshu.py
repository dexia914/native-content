import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import Locator, Page, TimeoutError as PlaywrightTimeoutError, async_playwright

from app.config import settings
from app.models import GeneratedAssets


class XiaohongshuPublisher:
    async def publish(self, assets: GeneratedAssets, auto_submit: bool = False) -> None:
        """Upload note draft via Xiaohongshu Creator Center and optionally submit it."""
        state_path = Path(settings.xhs_login_state_path)
        if not state_path.exists():
            raise FileNotFoundError(
                f"Missing login state file: {state_path}. "
                "Run `softpost auth` first to export it."
            )

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=settings.xhs_headless)
            context = await browser.new_context(storage_state=str(state_path))
            page = await context.new_page()

            await page.goto(f"{settings.xhs_base_url}/publish/publish", wait_until="domcontentloaded")
            await page.wait_for_load_state("networkidle")

            await self._switch_to_image_mode(page)
            await self._upload_cover(page, assets)
            await self._fill_title(page, assets)
            await self._fill_body(page, assets)

            if auto_submit:
                await self._submit(page)
                await asyncio.sleep(2)
            else:
                await asyncio.sleep(1)

            await context.close()
            await browser.close()

    async def _switch_to_image_mode(self, page: Page) -> None:
        active_image_tab = page.locator(".header-tabs .creator-tab.active .title").filter(has_text="上传图文")
        if await active_image_tab.count() > 0:
            return

        tabs = page.locator(".header-tabs .creator-tab")
        count = await tabs.count()
        for index in range(count):
            tab = tabs.nth(index)
            title = tab.locator(".title")
            try:
                await title.wait_for(state="visible", timeout=1000)
            except PlaywrightTimeoutError:
                continue

            text = (await title.text_content() or "").strip()
            if text != "上传图文":
                continue

            box = await tab.bounding_box()
            if not box or box["width"] <= 0 or box["height"] <= 0:
                continue

            try:
                await tab.click(force=True, timeout=3000)
            except Exception:
                pass

            if await active_image_tab.count() > 0:
                return

            try:
                await title.click(force=True, timeout=3000)
            except Exception:
                pass

            if await active_image_tab.count() > 0:
                return

            dispatched = await tab.evaluate(
                """
                (el) => {
                  const rect = el.getBoundingClientRect();
                  const x = rect.left + rect.width / 2;
                  const y = rect.top + rect.height / 2;
                  const events = ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'];
                  for (const type of events) {
                    el.dispatchEvent(new MouseEvent(type, {
                      bubbles: true,
                      cancelable: true,
                      clientX: x,
                      clientY: y,
                      button: 0
                    }));
                  }
                  return true;
                }
                """
            )
            if dispatched:
                try:
                    await page.locator(".header-tabs .creator-tab.active .title").filter(has_text="上传图文").first.wait_for(
                        state="visible",
                        timeout=5000,
                    )
                    await asyncio.sleep(1)
                    return
                except PlaywrightTimeoutError:
                    continue

        raise RuntimeError("Could not switch to the '上传图文' tab on the Xiaohongshu publish page.")

        await page.locator(".header-tabs .creator-tab.active .title").filter(has_text="上传图文").first.wait_for(
            state="visible",
            timeout=10000,
        )
        await asyncio.sleep(1)


    async def _upload_cover(self, page: Page, assets: GeneratedAssets) -> None:
        preferred = [
            ".upload-content input.upload-input[type='file'][accept*='.jpg']",
            ".upload-content input.upload-input[type='file'][accept*='.jpeg']",
            ".upload-content input.upload-input[type='file'][accept*='.png']",
            ".upload-content input.upload-input[type='file'][accept*='.webp']",
        ]
        locator = await self._first_visible_locator(page, preferred, timeout=10000, include_hidden=True)
        if locator is None:
            fallback = [
                ".upload-content input[type='file'][accept*='.png']",
                ".upload-content input[type='file'][accept*='.jpg']",
                "input[type='file'][accept*='image']",
                "input[type='file']",
            ]
            locator = await self._first_visible_locator(page, fallback, timeout=10000, include_hidden=True)
        if locator is None:
            raise RuntimeError("Could not find the image upload control on the Xiaohongshu publish page.")

        await locator.set_input_files(str(assets.collage_path))
        await asyncio.sleep(5)

    async def _fill_title(self, page: Page, assets: GeneratedAssets) -> None:
        selectors = [
            "input[placeholder*='标题']",
            "input[placeholder*='请输入标题']",
            "input[placeholder*='填写标题']",
            "input:not([type='file'])",
        ]
        locator = await self._first_visible_locator(page, selectors, timeout=8000)
        if locator is not None:
            await locator.click()
            await locator.fill(assets.post.title)

    async def _fill_body(self, page: Page, assets: GeneratedAssets) -> None:
        body_text = assets.post.body.strip()
        if assets.post.hashtags:
            body_text = f"{body_text}\n\n{' '.join(assets.post.hashtags)}".strip()

        selectors = [
            ".ql-editor",
            "textarea",
            "[contenteditable='true']",
            "div[role='textbox']",
        ]
        locator = await self._first_visible_locator(page, selectors, timeout=10000)
        if locator is None:
            raise RuntimeError("Could not find the body editor on the Xiaohongshu publish page.")

        await locator.click()
        try:
            await locator.fill(body_text)
        except Exception:
            await page.keyboard.press("Control+A")
            await page.keyboard.insert_text(body_text)

    async def _submit(self, page: Page) -> None:
        candidates = [
            page.get_by_role("button", name="发布"),
            page.get_by_role("button", name="立即发布"),
            page.get_by_role("button", name="确认发布"),
            page.get_by_role("button", name="发布笔记"),
            page.locator("button:has-text('发布')"),
            page.locator("button:has-text('发布笔记')"),
            page.locator("[role='button']:has-text('发布')"),
            page.locator("div:has-text('发布')"),
        ]
        button = await self._first_actionable(candidates, timeout=10000)
        if button is None:
            raise RuntimeError("Could not find the publish button. Update selectors in app/distribution/xiaohongshu.py.")

        await button.click()
        await asyncio.sleep(2)

        confirm_candidates = [
            page.get_by_role("button", name="确认发布"),
            page.get_by_role("button", name="确认"),
            page.locator("button:has-text('确认发布')"),
            page.locator("button:has-text('确认')"),
        ]
        confirm = await self._first_actionable(confirm_candidates, timeout=4000)
        if confirm is not None:
            await confirm.click()

    async def _first_visible_locator(
        self,
        page: Page,
        selectors: list[str],
        timeout: int,
        include_hidden: bool = False,
    ) -> Locator | None:
        for selector in selectors:
            locator = page.locator(selector)
            count = await locator.count()
            for index in range(count):
                candidate = locator.nth(index)
                try:
                    if include_hidden:
                        await candidate.wait_for(state="attached", timeout=timeout)
                        accept = await candidate.get_attribute("accept")
                        if accept and ("mp4" in accept or "mov" in accept or "video" in accept):
                            continue
                        return candidate

                    await candidate.wait_for(state="visible", timeout=timeout)
                    return candidate
                except PlaywrightTimeoutError:
                    continue
        return None

    async def _first_actionable(self, candidates: list[Locator], timeout: int) -> Locator | None:
        for locator in candidates:
            try:
                count = await locator.count()
                for index in range(count):
                    candidate = locator.nth(index)
                    await candidate.wait_for(state="visible", timeout=timeout)
                    text = (await candidate.text_content() or "").strip()
                    if text == "上传视频":
                        continue
                    if await candidate.is_enabled():
                        return candidate
            except PlaywrightTimeoutError:
                continue
        return None


async def export_login_state() -> Path:
    """Open login page and save Playwright storage state after manual login."""
    state_path = Path(settings.xhs_login_state_path)
    state_path.parent.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto(f"{settings.xhs_base_url}/publish/publish", wait_until="domcontentloaded")
        print("请在打开的浏览器中完成登录，确认进入创作中心后，回到终端按回车保存登录态。")
        input()

        await context.storage_state(path=str(state_path))
        await context.close()
        await browser.close()

    return state_path


def publish_sync(assets: GeneratedAssets, auto_submit: bool = False) -> None:
    asyncio.run(XiaohongshuPublisher().publish(assets, auto_submit=auto_submit))


def export_login_state_sync() -> Path:
    return asyncio.run(export_login_state())


def get_auth_status() -> dict[str, str | int | float]:
    state_path = Path(settings.xhs_login_state_path)
    if not state_path.exists():
        raise FileNotFoundError(f"Missing login state file: {state_path}. Run `softpost auth` first.")

    data = json.loads(state_path.read_text(encoding="utf-8"))
    cookies = data.get("cookies", [])
    key_names = {
        "customer-sso-sid",
        "access-token-creator.xiaohongshu.com",
        "galaxy_creator_session_id",
        "galaxy.creator.beaker.session.id",
        "x-user-id-creator.xiaohongshu.com",
    }

    key_cookies = [
        cookie
        for cookie in cookies
        if cookie.get("name") in key_names and isinstance(cookie.get("expires"), (int, float)) and cookie.get("expires", 0) > 0
    ]
    if not key_cookies:
        raise RuntimeError("No expiring Xiaohongshu auth cookies were found in the saved storage state.")

    earliest = min(key_cookies, key=lambda cookie: cookie["expires"])
    now = datetime.now(timezone.utc).timestamp()
    seconds_left = earliest["expires"] - now
    days_left = round(seconds_left / 86400, 2)
    expiry_utc = datetime.fromtimestamp(earliest["expires"], timezone.utc).isoformat()

    if seconds_left <= 0:
        level = "expired"
        message = "[red]登录态已过期，请重新执行 `softpost auth`。[/red]"
    elif days_left <= 3:
        level = "expiring_soon"
        message = "[yellow]登录态将在 3 天内到期，建议尽快重新导出。[/yellow]"
    else:
        level = "ok"
        message = "[green]登录态看起来仍可用。[/green]"

    return {
        "state_path": str(state_path),
        "cookie_count": len(key_cookies),
        "earliest_cookie": str(earliest["name"]),
        "earliest_expiry_utc": expiry_utc,
        "days_left": days_left,
        "level": level,
        "message": message,
    }
