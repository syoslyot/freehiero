"""Main loop: two concurrent triggers → detect → notify.

Trigger 1 (fast path): IMAP IDLE — fires within seconds when FB sends email notification.
Trigger 2 (fallback):  Periodic poll — fires every 8-15 min regardless of email.

Both paths share the same process_posts() logic; SQLite dedup prevents double-notify.
"""

import asyncio
import random

import config
import store
from detector import TwoLayerDetector
from notifier import Post, build_notifiers
from scraper import FBScraper


async def process_posts(
    scraper: FBScraper,
    detector: TwoLayerDetector,
    notifiers: list,
    source: str,
) -> None:
    print(f"[scheduler] fetch triggered by {source}")
    raw_posts = await scraper.fetch_posts(limit=config.POSTS_TO_CHECK)
    print(f"[scheduler] fetched {len(raw_posts)} posts")

    for raw in raw_posts:
        if store.is_seen(raw.post_id):
            continue

        if detector.is_food_giveaway(raw.text):
            print(f"[scheduler] 🍱 match: {raw.post_id}")
            post = Post(post_id=raw.post_id, text=raw.text, url=raw.url)
            for n in notifiers:
                try:
                    n.send(post)
                except Exception as e:
                    print(f"[scheduler] notify error ({type(n).__name__}): {e}")

        store.mark_seen(raw.post_id)


async def poll_loop(
    scraper: FBScraper,
    detector: TwoLayerDetector,
    notifiers: list,
) -> None:
    """Fallback: periodic poll every POLL_MIN_SEC–POLL_MAX_SEC seconds."""
    while True:
        delay = random.uniform(config.POLL_MIN_SEC, config.POLL_MAX_SEC)
        print(f"[poll] next in {delay / 60:.1f} min")
        await asyncio.sleep(delay)
        await process_posts(scraper, detector, notifiers, source="poll")


async def main() -> None:
    scraper = FBScraper(config.GROUP_URL)
    await scraper.start()
    await scraper.ensure_logged_in()

    detector = TwoLayerDetector()
    notifiers = build_notifiers()

    print(
        f"[scheduler] started | notifiers: {config.ENABLED_NOTIFIERS} "
        f"| imap: {config.IMAP_ENABLED} | ollama: {config.OLLAMA_ENABLED}"
    )

    loop = asyncio.get_running_loop()
    tasks: list[asyncio.Task] = []

    # ── IMAP IDLE fast path ───────────────────────────────────────────────────
    if config.IMAP_ENABLED:
        from imap_trigger import ImapTrigger

        async def on_fb_mail() -> None:
            await process_posts(scraper, detector, notifiers, source="imap")

        imap = ImapTrigger(
            host=config.IMAP_HOST,
            user=config.IMAP_USER,
            password=config.IMAP_APP_PASSWORD,
            on_fb_mail=on_fb_mail,
        )
        imap.start(loop)

    # ── Periodic fallback poll ────────────────────────────────────────────────
    tasks.append(asyncio.create_task(poll_loop(scraper, detector, notifiers)))

    # Initial poll on startup so we don't miss posts during the first delay
    await process_posts(scraper, detector, notifiers, source="startup")

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
