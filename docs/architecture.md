# Architecture

freehiero 監測私人 FB 社團的貼文，依啟用的類別（category）偵測並即時通知。
目前正式支援：`food`（免費食物）；`housing` 模組已建立但尚未正式啟用；架構設計可直接擴充至活動、二手商品等。

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
│              (iterate over categories)                       │
└──────────────────────────┬───────────────────────────────────┘
                           │
          ┌────────────────┼─────────────────┐
          ▼                ▼                 ▼
     scraper.py       categories/        store.py
   (Playwright)    (Category registry)  (SQLite)
          │                │
          │    ┌───────────┴──────────────┐
          │    ▼                          ▼
          │  food.py               housing.py（已建立，未正式啟用）
          │  ├ FoodKeywordDetector
          │  ├ TwoLayerDetector
          │  └ format_notification()
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
| `scraper.py` | Playwright persistent context 登入 FB，抓取最新 N 篇貼文；回傳 `Post` |
| `models.py` | 共用 dataclass：`Post`（貼文）、`Notification`（通知內容） |
| `categories/` | Category 登記表；每個模組定義一個類別的偵測邏輯與訊息格式 |
| `detector.py` | 基礎設施：`Detector` ABC、`OllamaDetector`、`TwoLayerDetector` |
| `notifier.py` | 三個通知管道的統一介面：Telegram / Gmail / LINE |
| `store.py` | SQLite，以 `(post_id, category_id)` 防止重複通知 |
| `imap_trigger.py` | IMAP IDLE 背景 thread，收到 FB email 時呼叫 async callback |
| `config.py` | 從 `.env` 讀取所有設定 |
| `crawlers/login.py` | 首次 FB 登入，建立 `fb-session/` |
| `crawlers/label_tool.py` | 互動式資料標注工具，儲存至 `data/training_data.json` |

## Category 系統

每個 category 是一個 `Category` dataclass：

```python
@dataclass
class Category:
    id: str                                       # 唯一識別，對應 .env ENABLED_CATEGORIES
    name: str                                     # 人類可讀名稱，用於 log / 通知
    detector: Detector                            # TwoLayerDetector(l1, l2, signal_pattern)
    format_notification: Callable[[Post], Notification]
```

### 新增一個類別只需三步

1. 建立 `categories/<name>.py`，定義 L1 Detector（+ 可選 L2 prompt）、`format_notification`、`build()` factory
2. 在 `categories/__init__.py` 的 `_BUILDERS` dict 加上 `"<name>": _build_<name>`
3. 在 `.env` 的 `ENABLED_CATEGORIES` 加上 `<name>`

核心的 `scheduler.py`、`notifier.py`、`store.py`、`detector.py` 不需要改動。

## 兩層偵測（TwoLayerDetector）

`TwoLayerDetector` 是通用基礎設施，由每個 category 自行組裝：

```
貼文文字
  │
  ├─ L1: CategoryKeywordDetector（< 1ms）
  │   └─ category 自定義 regex → True / False / 不確定
  │
  └─ L2: OllamaDetector（~3s, CPU, 選配）
      │  只在 signal_pattern 命中時才啟動（節省推論資源）
      └─ category 自定義 prompt → yes/no
```

L2 只在有「部分信號」時才啟動，95% 的貼文在 L1 就結束。

## 反爬蟲設計

- **Persistent browser context**：session 存在 `fb-session/`，避免重複登入觸發 2FA
- **playwright-stealth**：抹除 Headless 特徵，降低被 FB 偵測機率
- **隨機輪詢間隔**：`random.uniform(POLL_MIN_SEC, POLL_MAX_SEC)` 避免固定 pattern
- **IMAP IDLE 減少 browser 開啟頻率**：email 觸發時才開 browser，大幅降低請求量

## 訓練資料流程

```
crawlers/login.py      ← 首次登入，建立 fb-session/
crawlers/label_tool.py ← 互動式標注，儲存至 data/training_data.json
                           --scrape-only  → 爬貼文存 data/pending.json（再請 Claude 歸檔）
                           --negative     → 負例模式（瀏覽一般 feed，Enter 預設 n）
                           --export       → 匯出 Colab SAMPLES 格式
data/training_data.json      ← 已標注資料（gitignore，個資已遮蔽）
data/raw/              ← 各 query 的原始爬取資料（英文檔名）
data/raw/manifest.json ← filename → 實際 query 對照表
```

資料集目前從 `data/raw/` 重建中（`training_data.json` 先前資料已失效）。已爬取 query：`免費`、`免費 飲料`、`（無篩選）`。
