# Setup

## 前置需求

- Python 3.11+
- 已被加入目標 FB 私人社團的 FB 帳號

## 安裝

```bash
git clone https://github.com/syoslyot/freehiero.git
cd freehiero
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

## 設定 .env

```bash
cp .env.example .env
```

編輯 `.env`，必填欄位：

| 變數 | 說明 |
|------|------|
| `FB_GROUP_URL` | 目標社團 URL，例如 `https://www.facebook.com/groups/12345/` |
| `ENABLED_NOTIFIERS` | 啟用的通知管道，逗號分隔，例如 `telegram,gmail` |

## 通知管道設定

### Telegram（最簡單）

1. 在 Telegram 搜尋 `@BotFather` → `/newbot` → 取得 `BOT_TOKEN`
2. 搜尋 `@userinfobot` → 取得自己的 `CHAT_ID`
3. 填入 `.env`：
   ```
   TELEGRAM_BOT_TOKEN=123456:ABC...
   TELEGRAM_CHAT_ID=987654321
   ```

### Gmail SMTP

1. Google 帳號 → 安全性 → 兩步驟驗證（需先開啟）
2. 搜尋「應用程式密碼」→ 新增 → 複製 16 位密碼
3. 填入 `.env`：
   ```
   GMAIL_SENDER=you@gmail.com
   GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
   GMAIL_RECIPIENT=notify@example.com
   ```

### LINE Messaging API

1. 前往 [LINE Developers Console](https://developers.line.biz/)
2. 建立 Provider → 建立 Messaging API channel
3. 在 channel 設定頁取得 Channel access token（long-lived）
4. 對 bot 傳一則訊息後，透過 webhook log 取得自己的 User ID
5. 填入 `.env`：
   ```
   LINE_CHANNEL_ACCESS_TOKEN=...
   LINE_USER_ID=U...
   ```

## IMAP IDLE 設定（選配，強烈建議）

啟用後延遲從 ~13 分鐘降到幾秒。

1. Gmail → 設定 → 查看所有設定 → 轉寄和 POP/IMAP → **啟用 IMAP**
2. 在監測 FB 帳號的 Gmail，確認 FB email 通知已開啟：
   FB → 設定 → 通知 → Email → 社團貼文 → 開啟
3. 填入 `.env`：
   ```
   IMAP_ENABLED=true
   IMAP_USER=your-monitored-account@gmail.com
   IMAP_APP_PASSWORD=xxxx xxxx xxxx xxxx   # 同 Gmail SMTP 的 app password
   ```
   > `IMAP_APP_PASSWORD` 與 `GMAIL_APP_PASSWORD` 可以是同一組（同帳號時）

## Ollama 設定（選配，Layer 2 偵測）

增強對模糊語意的識別率（例如「東西帶走」而非「食物送人」）。

```bash
# 安裝 Ollama: https://ollama.com
ollama pull qwen2.5:0.5b
```

填入 `.env`：
```
OLLAMA_ENABLED=true
```

## 第一次執行

```bash
python scheduler.py
```

首次執行時，Playwright 會開啟 Chromium 視窗等待手動登入 FB。
登入完成後按 Enter，session 存入 `fb-session/`，之後不需重複登入。

> 如果跑在沒有螢幕的環境（如 VPS），請先參考 [deployment.md](deployment.md) 設定 Xvfb。
