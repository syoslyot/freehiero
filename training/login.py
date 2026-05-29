#!/usr/bin/env python3
# cd /home/wassup/computer-science/side-projects/freehiero && python3 training/login.py
import asyncio, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scraper import FBScraper
import config


async def login():
    s = FBScraper(config.GROUP_URL)
    await s.start()
    await s.ensure_logged_in()
    await s.stop()


asyncio.run(login())
# cd /home/wassup/computer-science/side-projects/freehiero && python3 training/label_tool.py --scrape-only
