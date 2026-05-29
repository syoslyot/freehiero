import os
from dotenv import load_dotenv

load_dotenv()

# FB group URL to monitor
GROUP_URL: str = os.environ["FB_GROUP_URL"]

# How many recent posts to check per poll
POSTS_TO_CHECK: int = int(os.getenv("POSTS_TO_CHECK", "10"))

# Poll interval range in seconds (random between min and max)
POLL_MIN_SEC: int = int(os.getenv("POLL_MIN_SEC", str(8 * 60)))
POLL_MAX_SEC: int = int(os.getenv("POLL_MAX_SEC", str(18 * 60)))

# Enabled notifiers: comma-separated list of "telegram", "gmail", "line"
ENABLED_NOTIFIERS: list[str] = [
    s.strip() for s in os.getenv("ENABLED_NOTIFIERS", "telegram").split(",") if s.strip()
]

# Enabled detection categories: comma-separated (e.g. "food", "housing", "events")
ENABLED_CATEGORIES: list[str] = [
    s.strip() for s in os.getenv("ENABLED_CATEGORIES", "food").split(",") if s.strip()
]

# Telegram
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

# Gmail
GMAIL_SENDER: str = os.getenv("GMAIL_SENDER", "")
GMAIL_APP_PASSWORD: str = os.getenv("GMAIL_APP_PASSWORD", "")
GMAIL_RECIPIENT: str = os.getenv("GMAIL_RECIPIENT", "")

# LINE Messaging API
LINE_CHANNEL_ACCESS_TOKEN: str = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_USER_ID: str = os.getenv("LINE_USER_ID", "")

# IMAP IDLE trigger (optional fast path)
IMAP_ENABLED: bool = os.getenv("IMAP_ENABLED", "false").lower() == "true"
IMAP_HOST: str = os.getenv("IMAP_HOST", "imap.gmail.com")
IMAP_USER: str = os.getenv("IMAP_USER", "")
IMAP_APP_PASSWORD: str = os.getenv("IMAP_APP_PASSWORD", "")

# Ollama (Layer 2 detector, optional)
OLLAMA_ENABLED: bool = os.getenv("OLLAMA_ENABLED", "false").lower() == "true"
OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")
