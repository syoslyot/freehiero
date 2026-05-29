"""Set required env vars before any module is imported during test collection."""
import os

os.environ.setdefault("FB_GROUP_URL", "https://www.facebook.com/groups/test/")
os.environ.setdefault("ENABLED_NOTIFIERS", "telegram")
os.environ.setdefault("ENABLED_CATEGORIES", "food")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("TELEGRAM_CHAT_ID", "12345")
