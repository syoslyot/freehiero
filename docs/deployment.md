# Deployment

部署到 VPS，讓系統 24/7 背景執行。

## 推薦：Oracle Cloud Free Tier

永久免費的 ARM VM（Ampere A1）：4 vCPU、24 GB RAM，足以跑 Playwright + Ollama。

申請步驟：
1. 前往 [oracle.com/cloud/free](https://oracle.com/cloud/free) 註冊
2. 建立 VM → 選 **Always Free** → Instance shape: `VM.Standard.A1.Flex`
3. OS: Ubuntu 22.04 LTS（ARM）
4. 下載 SSH key，保存好

## VPS 初始設定

```bash
# SSH 進入 VPS
ssh -i your-key.pem ubuntu@<VPS_IP>

# 更新系統
sudo apt update && sudo apt upgrade -y

# 安裝 Python、相依套件
sudo apt install -y python3.11 python3.11-venv python3-pip git

# 安裝 Chromium 相依套件（Playwright 需要）
sudo apt install -y \
  libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libxcomposite1 \
  libxdamage1 libxfixes3 libxrandr2 libgbm1 libxkbcommon0 libpango-1.0-0 \
  libcairo2 libasound2

# 安裝 Xvfb（虛擬螢幕，讓 non-headless browser 在無螢幕環境執行）
sudo apt install -y xvfb
```

## 部署應用程式

```bash
# 複製專案
git clone https://github.com/syoslyot/freehiero.git /opt/freehiero
cd /opt/freehiero

# 建立 venv 並安裝套件
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# 建立 .env
cp .env.example .env
nano .env   # 填入所有設定
```

## 首次 FB 登入（在 VPS 上）

VPS 沒有螢幕，需要用 Xvfb 跑虛擬顯示，再透過 VNC 或 SSH X11 forwarding 看畫面。

**方法一：SSH X11 forwarding（較簡單）**

```bash
# 本機執行（需要安裝 X11，Mac 用 XQuartz，Windows 用 Xming）
ssh -X -i your-key.pem ubuntu@<VPS_IP>

# 在 VPS 上
export DISPLAY=:0
cd /opt/freehiero && source .venv/bin/activate
python scheduler.py   # browser 視窗會顯示在本機
```

**方法二：在本機登入後複製 session 到 VPS**

```bash
# 在本機登入後
python scheduler.py   # 登入 FB，按 Enter 後 fb-session/ 建立完成

# 把 session 複製到 VPS
scp -i your-key.pem -r fb-session/ ubuntu@<VPS_IP>:/opt/freehiero/
```

推薦方法二，較不依賴圖形環境。

## 設定 systemd service

```bash
# 複製 service 設定
sudo cp /opt/freehiero/fb-monitor.service /etc/systemd/system/

# 啟動並設為開機自啟
sudo systemctl daemon-reload
sudo systemctl enable --now fb-monitor

# 查看狀態 / 日誌
sudo systemctl status fb-monitor
sudo journalctl -u fb-monitor -f
```

`fb-monitor.service` 內容重點：
- `Restart=always`：crash 後 30 秒自動重啟
- `Environment=DISPLAY=:99`：使用 Xvfb 虛擬螢幕
- 需在 service 啟動前確保 Xvfb 已執行（或改用 headless mode）

## 啟動 Xvfb（配合 systemd）

建立 Xvfb service：

```bash
sudo tee /etc/systemd/system/xvfb.service > /dev/null <<'EOF'
[Unit]
Description=Xvfb virtual display
Before=fb-monitor.service

[Service]
ExecStart=/usr/bin/Xvfb :99 -screen 0 1280x900x24
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable --now xvfb
```

## Ollama（選配，VPS 上）

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:0.5b

# Ollama 預設在 localhost:11434，不需額外設定
```

Oracle Free Tier 的 24GB RAM 足以跑 0.5b 模型的 CPU 推論。

## 更新部署

```bash
cd /opt/freehiero
git pull
source .venv/bin/activate
pip install -r requirements.txt   # 如果 requirements.txt 有變動
sudo systemctl restart fb-monitor
```
