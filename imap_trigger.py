"""
IMAP IDLE listener — triggers the scraper immediately when FB sends a notification email.

Runs in a background thread; uses asyncio.run_coroutine_threadsafe to hand off
to the main event loop without blocking it.

Gmail setup:
  1. Enable IMAP in Gmail settings (Settings → See all settings → Forwarding and POP/IMAP)
  2. Generate an app password (myaccount.google.com/apppasswords)
  3. Set IMAP_USER / IMAP_APP_PASSWORD in .env
"""

from __future__ import annotations

import asyncio
import imaplib
import socket
import threading
import time
from collections.abc import Callable, Coroutine
from typing import Any

FB_MAIL_DOMAIN = b'"facebookmail.com"'
IDLE_TIMEOUT_SEC = 25 * 60  # re-IDLE before server 30-min cutoff
RECONNECT_DELAY_SEC = 30


class ImapTrigger:
    """Watches Gmail via IMAP IDLE; calls `on_fb_mail` coroutine on every FB notification."""

    def __init__(
        self,
        host: str,
        user: str,
        password: str,
        on_fb_mail: Callable[[], Coroutine[Any, Any, None]],
    ) -> None:
        self._host = host
        self._user = user
        self._password = password
        self._on_fb_mail = on_fb_mail
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop = threading.Event()

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        t = threading.Thread(target=self._run, daemon=True, name="imap-idle")
        t.start()

    def stop(self) -> None:
        self._stop.set()

    # ── internal ──────────────────────────────────────────────────────────────

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self._idle_session()
            except Exception as e:
                print(f"[imap] connection error: {e} — retry in {RECONNECT_DELAY_SEC}s")
                time.sleep(RECONNECT_DELAY_SEC)

    def _idle_session(self) -> None:
        conn = imaplib.IMAP4_SSL(self._host)
        conn.login(self._user, self._password)
        conn.select("INBOX")
        print("[imap] IDLE session started")

        try:
            while not self._stop.is_set():
                # Enter IDLE
                conn.send(b"A001 IDLE\r\n")
                resp = conn.readline()
                if b"idling" not in resp.lower():
                    raise RuntimeError(f"IDLE rejected: {resp!r}")

                # Block until server pushes a notification or timeout
                conn.socket().settimeout(IDLE_TIMEOUT_SEC)
                try:
                    line = conn.readline()
                except socket.timeout:
                    line = b""  # normal keepalive timeout, re-IDLE

                # Exit IDLE before doing anything else
                conn.socket().settimeout(30)
                conn.send(b"DONE\r\n")
                conn.readline()

                if b"EXISTS" not in line:
                    continue

                # New mail — check if it's from Facebook
                conn.socket().settimeout(30)
                typ, data = conn.search(None, "FROM", FB_MAIL_DOMAIN, "UNSEEN")
                if typ != "OK" or not data[0]:
                    continue

                ids = data[0].split()
                conn.store(
                    b",".join(ids), "+FLAGS", "\\Seen"
                )
                print(f"[imap] FB notification email detected → triggering scraper")
                asyncio.run_coroutine_threadsafe(
                    self._on_fb_mail(), self._loop  # type: ignore[arg-type]
                )

        finally:
            try:
                conn.logout()
            except Exception:
                pass
            print("[imap] session closed")
