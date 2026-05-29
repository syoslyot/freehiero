"""Main loop: two concurrent triggers → detect → notify.

Trigger 1 (fast path): IMAP IDLE — fires within seconds when FB sends email notification.
Trigger 2 (fallback):  Periodic poll — fires every 8-15 min regardless of email.

Both paths share the same process_posts() logic; SQLite dedup prevents double-notify.
"""

import asyncio
import random

import config
import store
from categories import get_enabled
from categories.base import Category
from notifier import Notifier, build_notifiers
from scraper import FBScraper


async def process_posts(
    scraper: FBScraper,
    categories: list[Category],
    notifiers: list[Notifier],
    source: str,
) -> None:
    print(f"[scheduler] fetch triggered by {source}")
    posts = await scraper.fetch_posts(limit=config.POSTS_TO_CHECK)
    print(f"[scheduler] fetched {len(posts)} posts")

    for post in posts:
        for category in categories:
            if store.is_seen(post.post_id, category.id):
                continue
            if category.detector.is_match(post.text):
                print(f"[scheduler] match [{category.name}]: {post.post_id}")
                notification = category.format_notification(post)
                for n in notifiers:
                    try:
                        n.send(notification)
                    except Exception as e:
                        print(f"[scheduler] notify error ({type(n).__name__}): {e}")
            store.mark_seen(post.post_id, category.id)


async def poll_loop(
    scraper: FBScraper,
    categories: list[Category],
    notifiers: list[Notifier],
) -> None:
    """Fallback: periodic poll every POLL_MIN_SEC–POLL_MAX_SEC seconds."""
    while True:
        delay = random.uniform(config.POLL_MIN_SEC, config.POLL_MAX_SEC)
        print(f"[poll] next in {delay / 60:.1f} min")
        await asyncio.sleep(delay)
        await process_posts(scraper, categories, notifiers, source="poll")


async def main() -> None:
    scraper = FBScraper(config.GROUP_URL)
    await scraper.start()
    await scraper.ensure_logged_in()

    categories = get_enabled()
    notifiers = build_notifiers()

    print(
        f"[scheduler] started | categories: {[c.id for c in categories]} "
        f"| notifiers: {config.ENABLED_NOTIFIERS} "
        f"| imap: {config.IMAP_ENABLED}"
    )

    loop = asyncio.get_running_loop()
    tasks: list[asyncio.Task] = []

    # ── IMAP IDLE fast path ───────────────────────────────────────────────────
    if config.IMAP_ENABLED:
        from imap_trigger import ImapTrigger

        async def on_fb_mail() -> None:
            await process_posts(scraper, categories, notifiers, source="imap")

        imap = ImapTrigger(
            host=config.IMAP_HOST,
            user=config.IMAP_USER,
            password=config.IMAP_APP_PASSWORD,
            on_fb_mail=on_fb_mail,
        )
        imap.start(loop)

    # ── Periodic fallback poll ────────────────────────────────────────────────
    tasks.append(asyncio.create_task(poll_loop(scraper, categories, notifiers)))

    # Initial poll on startup so we don't miss posts during the first delay
    await process_posts(scraper, categories, notifiers, source="startup")

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
