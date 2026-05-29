# Deployment

部署到 VPS，讓系統 24/7 背景執行。

## 推薦：Oracle Cloud Free Tier

永久免費的 ARM VM（Ampere A1）：4 vCPU、24 GB RAM，足以跑 Playwright + Ollama。

申請步驟：
1. 前往 [oracle.com/cloud/free](https://oracle.com/cloud/free) 註冊
2. 建立 VM → 選 **Always Free** → Instance shape: `VM.Standard.A1.Flex`
3. OS: Ubuntu 22.04 LTS（ARM）
4. 下載 SSH key 並保存

## VPS 初始設定

```bash
ssh -i your-key.pem ubuntu@<VPS_IP>

sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-pip git

# Playwright Chromium 相依套件
sudo apt install -y \
  libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libxcomposite1 \
  libxdamage1 libxfixes3 libxrandr2 libgbm1 libxkbcommon0 libpango-1.0-0 \
  libcairo2 libasound2

# 虛擬螢幕（non-headless browser 在無螢幕環境執行）
sudo apt install -y xvfb
```

## 部署應用程式

```bash
git clone https://github.com/syoslyot/freehiero.git /opt/freehiero
cd /opt/freehiero

python3 -m venv .venv
source .venv/bin/activate
pip3 install -r requirements.txt
python3 -m playwright install chromium

cp .env.example .env
nano .env   # 填入所有設定
```

## 首次 FB 登入

推薦在**本機**登入後，把 session 複製到 VPS（不依賴圖形環境）：

```bash
# 本機：登入並建立 fb-session/
python3 training/login.py

# 複製 session 到 VPS
scp -i your-key.pem -r fb-session/ ubuntu@<VPS_IP>:/opt/freehiero/
```

或在 VPS 上透過 SSH X11 forwarding：

```bash
# 本機執行（Mac 需 XQuartz，Windows 需 Xming）
ssh -X -i your-key.pem ubuntu@<VPS_IP>

# VPS 上
cd /opt/freehiero && source .venv/bin/activate
python3 training/login.py
```

## 設定 systemd service

```bash
sudo cp /opt/freehiero/fb-monitor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now fb-monitor

# 查看狀態 / 日誌
sudo systemctl status fb-monitor
sudo journalctl -u fb-monitor -f
```

`fb-monitor.service` 重點：
- `Restart=always`：crash 後 30 秒自動重啟
- `Environment=DISPLAY=:99`：使用 Xvfb 虛擬螢幕

## 啟動 Xvfb（配合 systemd）

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

## Ollama（選配）

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:0.5b
```

Oracle Free Tier 的 24 GB RAM 足以跑 0.5b 模型的 CPU 推論（~3s/篇）。

## 更新部署

```bash
cd /opt/freehiero
git pull
source .venv/bin/activate
pip3 install -r requirements.txt
sudo systemctl restart fb-monitor
```
