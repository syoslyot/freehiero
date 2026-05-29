# Categories 開發指南

## 概念

每個 category 描述「一種要偵測的貼文類型」。系統啟動時依 `.env` 的 `ENABLED_CATEGORIES` 載入對應模組，對每篇貼文逐一檢查，命中則發送通知。

核心結構：

```python
# categories/base.py
@dataclass
class Category:
    id: str                                        # 對應 ENABLED_CATEGORIES 的值
    name: str                                      # 用於 log 和通知標題
    detector: Detector                             # 偵測邏輯
    format_notification: Callable[[Post], Notification]  # 通知內容格式
```

## 目前支援的 Categories

| id | 名稱 | 模組 | 說明 |
|----|------|------|------|
| `food` | 免費食物 | `categories/food.py` | 便當、飲料、零食等剩食或免費送出 |

## 新增一個 Category

以新增「二手商品」（`used_goods`）為例。

### Step 1：建立 `categories/used_goods.py`

```python
import re

import config
from categories.base import Category
from detector import Detector, OllamaDetector, TwoLayerDetector
from models import Notification, Post

# ── 關鍵字 ────────────────────────────────────────────────────────────────────

_SELL_WORDS = r"出售|二手|轉讓|便宜賣|賤賣|清倉|出清"
_GOODS_WORDS = r"書|電腦|手機|鍵盤|耳機|螢幕|桌椅|冰箱|洗衣機|腳踏車"

_PATTERN_LISTING = re.compile(
    rf"(?=.*({_SELL_WORDS}))(?=.*({_GOODS_WORDS}))", re.IGNORECASE
)
_SIGNAL_PATTERN = re.compile(rf"({_SELL_WORDS})|({_GOODS_WORDS})", re.IGNORECASE)

_OLLAMA_PROMPT = (
    "你是二手交易助理。判斷以下社團貼文是否在販售或轉讓二手商品。"
    "只回答 yes 或 no，不要解釋。\n\n貼文：{text}"
)

# ── L1 Detector ───────────────────────────────────────────────────────────────

class UsedGoodsKeywordDetector(Detector):
    def is_match(self, text: str) -> bool:
        if not text:
            return False
        return bool(_PATTERN_LISTING.search(text))

# ── 通知格式 ──────────────────────────────────────────────────────────────────

def _format(post: Post) -> Notification:
    return Notification(
        title="社團二手商品通知",
        body=f"🛍️ 偵測到二手商品！\n\n{post.text[:200]}...\n\n{post.url}",
    )

# ── Factory ───────────────────────────────────────────────────────────────────

def build() -> Category:
    l1 = UsedGoodsKeywordDetector()
    l2 = (
        OllamaDetector(config.OLLAMA_URL, config.OLLAMA_MODEL, _OLLAMA_PROMPT)
        if config.OLLAMA_ENABLED
        else None
    )
    return Category(
        id="used_goods",
        name="二手商品",
        detector=TwoLayerDetector(l1, l2, signal_pattern=_SIGNAL_PATTERN),
        format_notification=_format,
    )
```

### Step 2：在 `categories/__init__.py` 登記

```python
from categories.food import build as _build_food
from categories.housing import build as _build_housing          # 已存在（未正式啟用）
from categories.used_goods import build as _build_used_goods   # ← 新增這行

_BUILDERS = {
    "food": _build_food,
    "housing": _build_housing,                                  # 已存在（未正式啟用）
    "used_goods": _build_used_goods,                           # ← 新增這行
}
```

### Step 3：在 `.env` 啟用

```
ENABLED_CATEGORIES=food,used_goods
```

**不需要動** `scheduler.py`、`notifier.py`、`store.py`、`detector.py`。

---

## 偵測器設計原則

### L1（KeywordDetector）

- 純 regex，< 1ms，**不應有 false negative**（寧可多送 L2，不要漏）
- `_PATTERN_NOT_*`：明顯不符合的樣式直接 early return False
- `_SIGNAL_PATTERN`：L1 未命中但有部分關鍵字 → 觸發 L2

### L2（OllamaDetector，選配）

- 模型：`qwen2.5:0.5b`（~3s, CPU only），啟用需設 `OLLAMA_ENABLED=true`
- prompt 必須包含 `{text}` 佔位符，要求模型只回答 `yes` / `no`
- 只在 `signal_pattern` 命中時啟動，避免對完全無關的貼文浪費推論時間

### TwoLayerDetector 流程

```
is_match(text)
  ├─ l1.is_match(text) == True  →  return True
  ├─ l2 is None                 →  return False
  ├─ signal_pattern 未命中      →  return False（跳過 l2）
  └─ l2.is_match(text)          →  return 結果
```

---

## 注意事項

### SQLite schema

`store.py` 使用 `(post_id, category_id)` 複合主鍵。同一篇貼文對不同 category 是獨立記錄，因此新增類別後，歷史貼文會被重新檢查一次（只有新 category，不影響已通知的舊 category）。

### 多 category 同時命中

同一篇貼文可以同時命中多個 category，每個 category 各自發送一則通知，互不干擾。

### 訓練資料

每個 category 應建立獨立的訓練資料集（參考 `colab_detector_test.ipynb` 的食物範例），
在上線前評估 L1 的 Precision / Recall，確保不會大量誤報。
