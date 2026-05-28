"""Main loop: poll FB group → detect → notify."""

import asyncio
import random

import config
import store
from detector import TwoLayerDetector
from notifier import Post, build_notifiers
from scraper import FBScraper


async def main() -> None:
    scraper = FBScraper(config.GROUP_URL)
    await scraper.start()
    await scraper.ensure_logged_in()

    detector = TwoLayerDetector()
    notifiers = build_notifiers()

    print(f"[scheduler] started | notifiers: {config.ENABLED_NOTIFIERS} | ollama: {config.OLLAMA_ENABLED}")

    while True:
        print("[scheduler] polling...")
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

            # Mark seen regardless of match to avoid re-evaluating old posts
            store.mark_seen(raw.post_id)

        delay = random.uniform(config.POLL_MIN_SEC, config.POLL_MAX_SEC)
        print(f"[scheduler] next poll in {delay / 60:.1f} min")
        await asyncio.sleep(delay)


if __name__ == "__main__":
    asyncio.run(main())
