# Architecture

freehiero 監測私人 FB 社團的貼文，偵測免費食物資訊後即時通知。

## 系統架構圖

```
┌──────────────────────────────────────────────────────────────┐
│                         scheduler.py                         │
│                                                              │
│  ┌─────────────────────┐    ┌──────────────────────────┐    │
│  │   IMAP IDLE thread  │    │   Periodic poll (async)  │    │
│  │  (fast path, ~秒)   │    │   (fallback, 8–15 min)   │    │
│  └────────┬────────────┘    └────────────┬─────────────┘    │
│           │ on_fb_mail()                 │ every N min       │
│           └──────────────┬───────────────┘                  │
│                          ▼                                   │
│                   process_posts()                            │
└──────────────────────────┬───────────────────────────────────┘
                           │
          ┌────────────────┼─────────────────┐
          ▼                ▼                 ▼
     scraper.py       detector.py        store.py
   (Playwright)     (TwoLayerDetector)   (SQLite)
          │                │
          │         ┌──────┴──────┐
          │         ▼             ▼
          │   KeywordDetector  OllamaDetector
          │    (L1, regex)   (L2, qwen2.5:0.5b)
          │
          └──────────────────────────────────▶ notifier.py
                                               ├ TelegramNotifier
                                               ├ GmailNotifier
                                               └ LineNotifier
```

## 觸發機制

### Fast path：IMAP IDLE（選配，建議啟用）

FB 帳號對社團開啟「所有通知」後，每當有新貼文 FB 會寄 email。
`imap_trigger.py` 用 IMAP IDLE 與 mail server 保持長連線（不輪詢），
有新信進來 server 主動推送 → 立刻觸發 `process_posts()`。

延遲：幾秒（取決於 FB email 發送速度）。

### Fallback：定時輪詢

每隔 8–15 分鐘（隨機，避免被 FB 識別為 bot）Playwright 開 browser 讀取社團 feed。
即使 IMAP 啟用，此 fallback 仍保持運行，確保 email 萬一延遲不漏貼文。

## 元件說明

| 檔案 | 職責 |
|------|------|
| `scheduler.py` | 主進入點；啟動 IMAP thread 與 poll loop，協調 `process_posts()` |
| `scraper.py` | Playwright persistent context 登入 FB，抓取最新 N 篇貼文 |
| `detector.py` | 兩層偵測：L1 keyword regex + L2 Ollama（選配） |
| `notifier.py` | 三個通知管道的統一介面：Telegram / Gmail / LINE |
| `store.py` | SQLite，記錄已通知 post ID，防止重複通知 |
| `imap_trigger.py` | IMAP IDLE 背景 thread，收到 FB email 時呼叫 async callback |
| `config.py` | 從 `.env` 讀取所有設定 |

## 兩層偵測（TwoLayerDetector）

```
貼文文字
  │
  ├─ L1: KeywordDetector（< 1ms）
  │   ├─ 直接命中（免費 + 食物關鍵字同時出現）→ True
  │   ├─ 明顯非食物（免費課程/活動/票）       → False
  │   └─ 不確定（有部分信號）                 → L2
  │
  └─ L2: OllamaDetector（~3s, CPU, 選配）
      └─ qwen2.5:0.5b prompt → yes/no
```

L2 只在有「部分信號」時才啟動，95% 的貼文在 L1 就結束。

## 反爬蟲設計

- **Persistent browser context**：session 存在 `fb-session/`，避免重複登入觸發 2FA
- **playwright-stealth**：抹除 Headless 特徵，降低被 FB 偵測機率
- **隨機輪詢間隔**：`random.uniform(POLL_MIN_SEC, POLL_MAX_SEC)` 避免固定 pattern
- **IMAP IDLE 減少 browser 開啟頻率**：email 觸發時才開 browser，大幅降低請求量
