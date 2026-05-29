# 資料標注工具

工作目錄必須是專案根目錄（`freehiero/`）。

## 指令

```bash
# 正例模式：瀏覽器搜尋後 Enter 開始，Enter 預設 y（是免費食物）
python3 crawlers/label_tool.py

# 負例模式：Enter 預設 n（不是免費食物）
python3 crawlers/label_tool.py --negative

# 只爬取，不標注，存入 data/pending.json
python3 crawlers/label_tool.py --scrape-only

# 匯出為 Colab SAMPLES 格式（印到 stdout）
python3 crawlers/label_tool.py --export
```

## 工作流程

1. 執行 `--scrape-only`，瀏覽器開啟後在 FB 社團搜尋欄輸入 query
2. 滾動到目標頁面後回終端按 Enter 開始爬取
3. 爬完後在 Claude Code 說「幫我歸檔 pending.json，query 是 ___」

## 建議 Query

Qwen2.5-0.5B 的 IFeval strict 只有 27.9，依賴 surface pattern 多於語意理解。
資料集需要涵蓋**多樣的正例表面形式**與**有 signal 但非送食物的硬負例**。

### 正例導向（免費食物密度高）

| query | 說明 |
|-------|------|
| `便當` | 最高頻正例，研討會剩餘便當 |
| `研討會 多` | 剩餘食物，表面形式多變 |
| `供餐` | 活動有供餐（最需要收集的邊界正例） |
| `剩食` | 幾乎全是正例，明確送出意圖 |
| `拿走` | 意圖信號，含「帶走」「快來拿」等 |

### 負例導向（有 signal 但非送食物）

| query | 說明 |
|-------|------|
| `免費 活動` | L1 最常見 false positive 來源 |
| `問卷` | 問卷貼文常夾帶食物關鍵字 |
| `出售` | 有食物關鍵字但在賣不在送 |
| `今天吃` | 描述自己吃，非送出 |

### 已爬取（`data/raw/` 現有）

| 英文檔名 | query | 筆數 |
|---------|-------|------|
| `free` | 免費 | 181 |
| `free_drinks` | 免費 飲料 | 271 |
| `unfiltered` | （無篩選） | 254 |
| `bento` | 便當 | 85 |
| `for_sale` | 出售 | 91 |
| `seminar_extra` | 研討會 多 | 74 |
| `survey` | 問卷 | 81 |
| `catering` | 供餐 | 79 |
| `leftover_food` | 剩食 | 67 |
| `free_event` | 免費 活動 | 47 |
| `graduation_sale` | 畢業出清 | 79 |

## 資料路徑

| 路徑 | 說明 |
|------|------|
| `data/pending.json` | 待歸檔的爬取結果 |
| `data/raw/<name>.json` | 各 query 的原始資料（不可修改） |
| `data/manifest.json` | 英文檔名 → 實際 query 對照表 |
| `data/categories/free_food/training_data.json` | 訓練集（Claude 標注，894 筆） |
| `data/categories/free_food/test_data.json` | 測試集（Claude 標注，234 筆） |

標注原則與統計詳見 [docs/dataset.md](dataset.md)。
