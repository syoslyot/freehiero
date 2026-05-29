#!/usr/bin/env python3
"""
label_tool.py  ─  Interactive FB post labeling tool for freehiero training data.

正例模式（在瀏覽器手動搜尋後按 Enter，Enter 預設 y）：
  python3 training/label_tool.py

負例模式（瀏覽一般 feed，Enter 預設 n）：
  python3 training/label_tool.py --negative

爬取模式（只抓貼文，存入 data/pending.json 讓 Claude 在 Claude Code 視窗判斷）：
  python3 training/label_tool.py --scrape-only

匯出為 Colab SAMPLES 格式：
  python3 training/label_tool.py --export
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from playwright.async_api import async_playwright
from playwright_stealth import Stealth

import config

_stealth = Stealth()

ROOT        = Path(__file__).parent.parent
DATA_FILE   = ROOT / "data" / "labeled.json"
PENDING_FILE = ROOT / "data" / "pending.json"
RAW_DIR     = ROOT / "data" / "raw"
SESSION_DIR = str(ROOT / "fb-session")

# ── PII / noise cleaning ──────────────────────────────────────────────────────

_PHONE_RE    = re.compile(r'09\d{2}[-\s]?\d{3}[-\s]?\d{3}|09\d{8}|\(0\d\)\d{4}-?\d{4}|0\d-\d{4}-?\d{4}')
_EMAIL_RE    = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')
_LINE_ID_RE  = re.compile(r'line\s*[：:id]\s*\S+', re.IGNORECASE)
_FB_TRACK_RE = re.compile(r'[a-zA-Z0-9]{20,}')
_FB_LOC_RE   = re.compile(r'[ \xa0]·\s+[\w一-鿿，、]+,\s+台灣\n?')


def _clean_text(text: str) -> str:
    text = text.replace('\xa0', ' ')
    text = re.sub(r'^Facebook\n', '', text)
    text = re.sub(r' 顯示較少\n.*', '', text, flags=re.DOTALL)
    text = _FB_LOC_RE.sub('\n', text)
    text = re.sub(r'^發訊息\n?', '', text, flags=re.MULTILINE)
    text = _PHONE_RE.sub('', text)
    text = _EMAIL_RE.sub('', text)
    text = _LINE_ID_RE.sub('', text)
    text = _FB_TRACK_RE.sub('', text)
    text = re.sub(r'^[a-zA-Z0-9]{3,12}\.[a-z]{2,4}$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\d+$', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


# ── data helpers ──────────────────────────────────────────────────────────────

def _load() -> list[dict]:
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return []


def _save(data: list[dict]) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _hash(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()[:10]


def _load_seen_hashes() -> set[str]:
    """Collect all hashes from labeled.json + pending.json + all raw files."""
    seen: set[str] = {d["hash"] for d in _load()}
    if PENDING_FILE.exists():
        seen |= {d["hash"] for d in json.loads(PENDING_FILE.read_text(encoding="utf-8"))}
    if RAW_DIR.exists():
        for f in RAW_DIR.glob("*.json"):
            if f.name == "manifest.json":
                continue
            seen |= {d["hash"] for d in json.loads(f.read_text(encoding="utf-8"))}
    return seen


# ── labeling session ──────────────────────────────────────────────────────────

async def run_labeling(default_key: str, scrape_only: bool = False) -> None:
    data = _load()
    seen = _load_seen_hashes()

    pending: list[dict] = json.loads(PENDING_FILE.read_text(encoding="utf-8")) if PENDING_FILE.exists() else []
    seen |= {d["hash"] for d in pending}

    shown:   set[str] = set()
    labeled = skipped = 0
    hint = "Enter=y（食物）" if default_key == "y" else "Enter=n（不是）"
    if scrape_only:
        print("[scrape-only] 只爬貼文，存入 data/pending.json")
        print("完成後請在 Claude Code 視窗說「幫我歸檔 pending.json，query 是 ___」")

    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=False,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
            viewport={"width": 1280, "height": 900},
            locale="zh-TW",
        )
        page = await ctx.new_page()
        await _stealth.apply_stealth_async(page)
        await page.goto(config.GROUP_URL, wait_until="domcontentloaded", timeout=30_000)

        print("瀏覽器已開啟，請在瀏覽器中搜尋或瀏覽到目標頁面，準備好後按 Enter 開始爬取...")
        await asyncio.get_event_loop().run_in_executor(None, input)
        await asyncio.sleep(2)

        stall = 0

        while True:
            articles = await page.query_selector_all('[role="feed"] > div')
            batch: list[tuple[str, str]] = []

            for article in articles:
                for btn in await article.query_selector_all('[role="button"]'):
                    if (await btn.inner_text()).strip() in ("查看更多", "See more"):
                        try:
                            await btn.click()
                            await asyncio.sleep(0.5)
                        except Exception:
                            pass
                        break

                text_parts = []
                for el in await article.query_selector_all('[dir="auto"]'):
                    t = (await el.inner_text()).strip()
                    if t:
                        text_parts.append(t)
                text = "\n".join(dict.fromkeys(text_parts)).strip()
                text = _clean_text(text)
                if len(text) < 10:
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
                after = len(await page.query_selector_all('[role="feed"] > div'))
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

                if scrape_only:
                    pending.append({"text": text, "hash": h})
                    seen.add(h)
                    PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
                    PENDING_FILE.write_text(json.dumps(pending, ensure_ascii=False, indent=2), encoding="utf-8")
                    print(f"[+] {preview[:80]}")
                    labeled += 1
                    continue

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

        if scrape_only:
            print(f"\n完成。已爬取 {labeled} 筆，存入 data/pending.json")
        else:
            _save(data)
            print(f"\n完成。標注 {labeled} 筆，跳過 {skipped} 筆。")
        await ctx.close()


# ── export ────────────────────────────────────────────────────────────────────

def export_samples() -> None:
    data = _load()
    if not data:
        print("data/labeled.json 是空的。")
        return
    pos = sum(1 for d in data if d["label"] == 1)
    neg = sum(1 for d in data if d["label"] == 0)
    print(f"# {pos} 正例 / {neg} 負例，共 {len(data)} 筆\n")
    print("SAMPLES = [")
    for d in data:
        escaped = d["text"].replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
        print(f"    ({d['label']}, '{escaped}'),")
    print("]")


# ── entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="freehiero 標注工具")
    ap.add_argument("--negative",    action="store_true", help="負例模式（Enter 預設 n）")
    ap.add_argument("--scrape-only", action="store_true", help="只爬貼文存 data/pending.json，不標注")
    ap.add_argument("--export",      action="store_true", help="匯出 Colab SAMPLES 格式")
    args = ap.parse_args()

    if args.export:
        export_samples()
        return

    default_key = "n" if args.negative else "y"
    asyncio.run(run_labeling(default_key=default_key, scrape_only=args.scrape_only))


if __name__ == "__main__":
    main()
# cd /home/wassup/computer-science/side-projects/freehiero && python3 training/label_tool.py --scrape-only
