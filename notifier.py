import smtplib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from email.message import EmailMessage

import httpx

import config


@dataclass
class Post:
    post_id: str
    text: str
    url: str


class Notifier(ABC):
    @abstractmethod
    def send(self, post: Post) -> None: ...


# ── Telegram ──────────────────────────────────────────────────────────────────

class TelegramNotifier(Notifier):
    def send(self, post: Post) -> None:
        msg = f"🍱 偵測到免費食物！\n\n{post.text[:200]}...\n\n{post.url}"
        httpx.post(
            f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": config.TELEGRAM_CHAT_ID, "text": msg},
            timeout=10,
        ).raise_for_status()


# ── Gmail ─────────────────────────────────────────────────────────────────────

class GmailNotifier(Notifier):
    def send(self, post: Post) -> None:
        msg = EmailMessage()
        msg["Subject"] = "🍱 社團免費食物通知"
        msg["From"] = config.GMAIL_SENDER
        msg["To"] = config.GMAIL_RECIPIENT
        msg.set_content(f"{post.text[:400]}\n\n{post.url}")
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(config.GMAIL_SENDER, config.GMAIL_APP_PASSWORD)
            s.send_message(msg)


# ── LINE Messaging API ────────────────────────────────────────────────────────

class LineNotifier(Notifier):
    def send(self, post: Post) -> None:
        msg = f"🍱 偵測到免費食物！\n\n{post.text[:200]}...\n\n{post.url}"
        httpx.post(
            "https://api.line.me/v2/bot/message/push",
            headers={
                "Authorization": f"Bearer {config.LINE_CHANNEL_ACCESS_TOKEN}",
                "Content-Type": "application/json",
            },
            json={
                "to": config.LINE_USER_ID,
                "messages": [{"type": "text", "text": msg}],
            },
            timeout=10,
        ).raise_for_status()


# ── Factory ───────────────────────────────────────────────────────────────────

def build_notifiers() -> list[Notifier]:
    mapping: dict[str, type[Notifier]] = {
        "telegram": TelegramNotifier,
        "gmail": GmailNotifier,
        "line": LineNotifier,
    }
    notifiers = []
    for name in config.ENABLED_NOTIFIERS:
        cls = mapping.get(name)
        if cls:
            notifiers.append(cls())
        else:
            print(f"[notifier] unknown notifier '{name}', skipped")
    return notifiers
