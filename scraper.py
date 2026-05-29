"""
Scrape latest posts from a private FB group using Playwright.

Login is done manually once; the persistent context (fb-session/) stores
cookies so subsequent runs skip login.
"""

from __future__ import annotations

import asyncio
import re

from playwright.async_api import BrowserContext, Page, async_playwright
from playwright_stealth import Stealth

from models import Post

_stealth = Stealth()

SESSION_DIR = "fb-session"
_POST_ID_RE = re.compile(r"/posts/(\d+)")
_STORY_ID_RE = re.compile(r"story_fbid=(\d+)")


async def _extract_posts(page: Page, limit: int) -> list[Post]:
    """Extract up to `limit` posts from the current group feed page."""
    # FB renders posts as <div role="article"> elements
    articles = await page.query_selector_all('div[role="article"]')
    posts: list[Post] = []

    for article in articles[:limit]:
        # Try to find the permalink inside the article
        permalink = None
        for selector in [
            'a[href*="/posts/"]',
            'a[href*="story_fbid="]',
            'a[href*="/permalink/"]',
        ]:
            link = await article.query_selector(selector)
            if link:
                href = await link.get_attribute("href") or ""
                permalink = href
                break

        if not permalink:
            continue

        # Extract post ID
        m = _POST_ID_RE.search(permalink) or _STORY_ID_RE.search(permalink)
        if not m:
            continue
        post_id = m.group(1)

        # Extract visible text
        text = (await article.inner_text()).strip()

        # Normalise URL to absolute
        if permalink.startswith("/"):
            permalink = "https://www.facebook.com" + permalink

        posts.append(Post(post_id=post_id, text=text, url=permalink))

    return posts


class FBScraper:
    def __init__(self, group_url: str) -> None:
        self._group_url = group_url
        self._playwright = None
        self._context: BrowserContext | None = None

    async def start(self) -> None:
        self._playwright = await async_playwright().start()
        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=False,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
            viewport={"width": 1280, "height": 900},
            locale="zh-TW",
        )

    async def stop(self) -> None:
        if self._context:
            await self._context.close()
        if self._playwright:
            await self._playwright.stop()

    async def ensure_logged_in(self) -> None:
        """Open FB and wait for user to log in manually if session is not saved."""
        page = await self._context.new_page()
        await _stealth.apply_stealth_async(page)
        await page.goto("https://www.facebook.com/", wait_until="domcontentloaded")
        # If the login form is present, we need manual login
        login_form = await page.query_selector('input[name="email"]')
        if login_form:
            print("[scraper] Session not found. Please log in manually in the browser window.")
            print("[scraper] Press Enter here after you have logged in...")
            await asyncio.get_event_loop().run_in_executor(None, input)
        await page.close()

    async def fetch_posts(self, limit: int = 10) -> list[Post]:
        page = await self._context.new_page()
        await _stealth.apply_stealth_async(page)
        try:
            await page.goto(self._group_url, wait_until="domcontentloaded", timeout=30_000)
            # Wait for feed to render
            await page.wait_for_selector('div[role="article"]', timeout=15_000)
            # Small pause to let lazy-loaded content settle
            await asyncio.sleep(2)
            return await _extract_posts(page, limit)
        except Exception as e:
            print(f"[scraper] fetch error: {e}")
            return []
        finally:
            await page.close()
