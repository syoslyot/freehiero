#!/usr/bin/env python3
"""
label_tool.py  ─  Interactive FB post labeling tool for freehiero training data.

正例模式（搜尋食物關鍵字，Enter 預設 y）：
  python label_tool.py --query "研討會 食物 飲料 免費 餐盒 便當"

負例模式（瀏覽一般 feed，Enter 預設 n）：
  python label_tool.py --negative

匯出為 Colab SAMPLES 格式：
  python label_tool.py --export
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path

from playwright.async_api import async_playwright
from playwright_stealth import stealth_async

import config

DATA_FILE = Path("labeled_data.json")
SESSION_DIR = "fb-session"


# ── data helpers ──────────────────────────────────────────────────────────────

def _load() -> list[dict]:
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return []


def _save(data: list[dict]) -> None:
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _hash(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()[:10]


# ── labeling session ──────────────────────────────────────────────────────────

async def run_labeling(url: str, default_key: str) -> None:
    data = _load()
    seen: set[str] = {d["hash"] for d in data}
    shown: set[str] = set()
    labeled = skipped = 0
    hint = "Enter=y（食物）" if default_key == "y" else "Enter=n（不是）"

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=False,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        ctx = await browser.new_persistent_context(
            user_data_dir=SESSION_DIR,
            viewport={"width": 1280, "height": 900},
            locale="zh-TW",
        )
        page = await ctx.new_page()
        await stealth_async(page)
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        await page.wait_for_selector('div[role="article"]', timeout=15_000)
        await asyncio.sleep(2)

        stall = 0

        while True:
            articles = await page.query_selector_all('div[role="article"]')
            batch: list[tuple[str, str]] = []

            for article in articles:
                text = (await article.inner_text()).strip()
                if len(text) < 30:
                    continue
                h = _hash(text)
                if h in shown:
                    continue
                shown.add(h)
                if h in seen:
                    continue
                batch.append((h, text))

            if not batch:
                prev = len(articles)
                await page.evaluate("window.scrollBy(0, window.innerHeight * 3)")
                await asyncio.sleep(3)
                after = len(await page.query_selector_all('div[role="article"]'))
                stall = stall + 1 if after <= prev else 0
                if stall >= 3:
                    print("\n已到底部，沒有更多新貼文。")
                    break
                continue

            stall = 0

            for h, text in batch:
                pos = sum(1 for d in data if d["label"] == 1)
                neg = sum(1 for d in data if d["label"] == 0)
                preview = text[:350].replace("\n", " ／ ")
                print(f"\n{'─'*64}")
                print(preview)
                print(f"{'─'*64}")
                print(
                    f"[y] 免費食物  [n] 不是  [s] 跳過  [q] 結束"
                    f"  {hint}  ｜ 正:{pos} 負:{neg}",
                    end=" > ",
                    flush=True,
                )

                try:
                    raw = input().strip().lower()
                except EOFError:
                    raw = "q"

                choice = raw if raw in ("y", "n", "s", "q") else default_key

                if choice == "q":
                    _save(data)
                    print(f"\n儲存完畢。標注 {labeled} 筆，跳過 {skipped} 筆。")
                    await ctx.close()
                    await browser.close()
                    return
                elif choice in ("y", "n"):
                    data.append({"label": 1 if choice == "y" else 0, "text": text, "hash": h})
                    seen.add(h)
                    _save(data)
                    labeled += 1
                else:
                    skipped += 1

            await page.evaluate("window.scrollBy(0, window.innerHeight * 2)")
            await asyncio.sleep(2)

        _save(data)
        print(f"\n完成。標注 {labeled} 筆，跳過 {skipped} 筆。")
        await ctx.close()
        await browser.close()


# ── export ────────────────────────────────────────────────────────────────────

def export_samples() -> None:
    data = _load()
    if not data:
        print("labeled_data.json 是空的。")
        return
    pos = sum(1 for d in data if d["label"] == 1)
    neg = sum(1 for d in data if d["label"] == 0)
    print(f"# {pos} 正例 / {neg} 負例，共 {len(data)} 筆\n")
    print("SAMPLES = [")
    for d in data:
        escaped = (
            d["text"]
            .replace("\\", "\\\\")
            .replace("'", "\\'")
            .replace("\n", "\\n")
        )
        print(f"    ({d['label']}, '{escaped}'),")
    print("]")


# ── entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="freehiero 標注工具")
    ap.add_argument("--query", default=None, help="搜尋關鍵字（空白分隔）")
    ap.add_argument("--negative", action="store_true", help="負例模式：瀏覽一般 feed")
    ap.add_argument("--export", action="store_true", help="匯出 Colab SAMPLES 格式")
    args = ap.parse_args()

    if args.export:
        export_samples()
        return

    if args.negative:
        asyncio.run(run_labeling(config.FB_GROUP_URL, default_key="n"))
    elif args.query:
        encoded = args.query.replace(" ", "%20")
        url = f"{config.FB_GROUP_URL}search/?q={encoded}"
        asyncio.run(run_labeling(url, default_key="y"))
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
