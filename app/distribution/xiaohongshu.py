from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from playwright.async_api import BrowserContext, Locator, Page, TimeoutError as PlaywrightTimeoutError, async_playwright

from app.account_state import get_active_login_account, save_login_account
from app.config import settings
from app.models import GeneratedAssets

TAB_TIMEOUT_MS = 5000
UPLOAD_TIMEOUT_MS = 10000
EDITOR_TIMEOUT_MS = 10000
PUBLISH_TIMEOUT_MS = 10000
UPLOAD_SETTLE_SECONDS = 5
SUBMIT_SETTLE_SECONDS = 2
LOGIN_WAIT_SECONDS = 300

AUTH_COOKIE_NAMES = {
    "customer-sso-sid",
    "access-token-creator.xiaohongshu.com",
    "galaxy_creator_session_id",
    "galaxy.creator.beaker.session.id",
    "x-user-id-creator.xiaohongshu.com",
}


class XiaohongshuPublisher:
    async def publish(self, assets: GeneratedAssets, auto_submit: bool = False) -> None:
        account = get_active_login_account()
        if account is None:
            raise FileNotFoundError("No active Xiaohongshu account in MySQL. Add one from the Web page or run `softpost-cli auth`.")

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=settings.xhs_headless)
            context = await browser.new_context(storage_state=account.storage_state)
            page = await context.new_page()
            await page.goto(f"{settings.xhs_base_url}/publish/publish", wait_until="domcontentloaded")
            await page.wait_for_load_state("networkidle")

            await self._switch_to_image_mode(page)
            await self._upload_cover(page, assets)
            await self._fill_title(page, assets)
            await self._fill_body(page, assets)

            if auto_submit:
                await self._submit(page)
                await asyncio.sleep(SUBMIT_SETTLE_SECONDS)
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

            for clickable in (tab, title):
                try:
                    await clickable.click(force=True, timeout=3000)
                except Exception:
                    pass
                if await active_image_tab.count() > 0:
                    await asyncio.sleep(1)
                    return

            dispatched = await tab.evaluate(
                """
                (el) => {
                  const rect = el.getBoundingClientRect();
                  const x = rect.left + rect.width / 2;
                  const y = rect.top + rect.height / 2;
                  for (const type of ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click']) {
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
                        timeout=TAB_TIMEOUT_MS,
                    )
                    await asyncio.sleep(2)
                    return
                except PlaywrightTimeoutError:
                    continue

        raise RuntimeError("Could not switch to the '上传图文' tab on the Xiaohongshu publish page.")

    async def _upload_cover(self, page: Page, assets: GeneratedAssets) -> None:
        preferred = [
            ".upload-content input.upload-input[type='file'][accept*='.jpg']",
            ".upload-content input.upload-input[type='file'][accept*='.jpeg']",
            ".upload-content input.upload-input[type='file'][accept*='.png']",
            ".upload-content input.upload-input[type='file'][accept*='.webp']",
        ]
        locator = await self._first_visible_locator(page, preferred, timeout=UPLOAD_TIMEOUT_MS, include_hidden=True)
        if locator is None:
            fallback = [
                ".upload-content input[type='file'][accept*='.png']",
                ".upload-content input[type='file'][accept*='.jpg']",
                "input[type='file'][accept*='image']",
                "input[type='file']",
            ]
            locator = await self._first_visible_locator(page, fallback, timeout=UPLOAD_TIMEOUT_MS, include_hidden=True)
        if locator is None:
            raise RuntimeError("Could not find the image upload control on the Xiaohongshu publish page.")

        await locator.set_input_files(str(assets.collage_path))
        await asyncio.sleep(UPLOAD_SETTLE_SECONDS)

    async def _fill_title(self, page: Page, assets: GeneratedAssets) -> None:
        selectors = [
            "input[placeholder*='标题']",
            "input[placeholder*='请输入标题']",
            "input[placeholder*='填写标题']",
            "input:not([type='file'])",
        ]
        locator = await self._first_visible_locator(page, selectors, timeout=EDITOR_TIMEOUT_MS)
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
        locator = await self._first_visible_locator(page, selectors, timeout=EDITOR_TIMEOUT_MS)
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
        button = await self._first_actionable(candidates, timeout=PUBLISH_TIMEOUT_MS)
        if button is None:
            raise RuntimeError("Could not find the publish button. Update selectors in app/distribution/xiaohongshu.py.")

        await button.click()
        await asyncio.sleep(SUBMIT_SETTLE_SECONDS)

        confirm_candidates = [
            page.get_by_role("button", name="确认发布"),
            page.get_by_role("button", name="确认"),
            page.locator("button:has-text('确认发布')"),
            page.locator("button:has-text('确认')"),
        ]
        confirm = await self._first_actionable(confirm_candidates, timeout=4000)
        if confirm is not None:
            await confirm.click()
            await asyncio.sleep(SUBMIT_SETTLE_SECONDS)

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


async def _wait_for_manual_login(context: BrowserContext, page: Page, timeout_seconds: int = LOGIN_WAIT_SECONDS) -> None:
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    while asyncio.get_running_loop().time() < deadline:
        try:
            cookies = await context.cookies()
            auth_names = {cookie.get("name") for cookie in cookies}
            if AUTH_COOKIE_NAMES & auth_names and "creator.xiaohongshu.com" in page.url:
                return
        except Exception:
            pass
        await asyncio.sleep(2)

    raise TimeoutError("等待小红书账号登录超时。请确认已在弹出的浏览器中完成登录，并已进入创作中心页面。")


async def _export_login_state_impl(profile: str) -> str:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto(f"{settings.xhs_base_url}/publish/publish", wait_until="domcontentloaded")
        await _wait_for_manual_login(context, page)
        storage_state = await context.storage_state()
        await context.close()
        await browser.close()

    record = save_login_account(profile, storage_state, make_active=True)
    return record.profile


async def export_login_state(profile: str = "default") -> str:
    return await _export_login_state_impl(profile)


def publish_sync(assets: GeneratedAssets, auto_submit: bool = False) -> None:
    asyncio.run(XiaohongshuPublisher().publish(assets, auto_submit=auto_submit))


def export_login_state_sync(profile: str = "default") -> str:
    return asyncio.run(export_login_state(profile))


def get_auth_status() -> dict[str, str | int | float]:
    account = get_active_login_account()
    if account is None:
        raise FileNotFoundError("No active Xiaohongshu account in MySQL. Add one from the Web page or run `softpost-cli auth` first.")

    cookies = account.storage_state.get("cookies", [])
    key_cookies = [
        cookie
        for cookie in cookies
        if cookie.get("name") in AUTH_COOKIE_NAMES
        and isinstance(cookie.get("expires"), (int, float))
        and cookie.get("expires", 0) > 0
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
        message = "登录态已过期，请重新登录并保存账号。"
    elif days_left <= 3:
        level = "expiring_soon"
        message = "登录态将在 3 天内到期，建议尽快重新保存账号。"
    else:
        level = "ok"
        message = "登录态看起来仍可用。"

    return {
        "profile": account.profile,
        "cookie_count": len(key_cookies),
        "earliest_cookie": str(earliest["name"]),
        "earliest_expiry_utc": expiry_utc,
        "days_left": days_left,
        "level": level,
        "message": message,
    }
