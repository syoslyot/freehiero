"""
測試 ImapTrigger 的核心邏輯。

IMAP IDLE 的完整連線流程需要真實 server，這裡只測試：
1. 建構參數正確儲存
2. 收到 EXISTS 且信件來自 facebookmail.com 時，callback 被呼叫
3. 收到 EXISTS 但信件不是來自 Facebook 時，callback 不呼叫
4. 沒有 EXISTS 時，callback 不呼叫
"""

import asyncio
import threading
from unittest.mock import MagicMock, call, patch

import pytest

from imap_trigger import ImapTrigger


def make_trigger(callback=None):
    if callback is None:
        async def callback(): pass
    return ImapTrigger(
        host="imap.gmail.com",
        user="test@gmail.com",
        password="pw",
        on_fb_mail=callback,
    )


class TestImapTriggerInit:
    def test_stores_credentials(self):
        t = make_trigger()
        assert t._host == "imap.gmail.com"
        assert t._user == "test@gmail.com"
        assert t._password == "pw"

    def test_stop_event_initially_clear(self):
        t = make_trigger()
        assert not t._stop.is_set()

    def test_stop_sets_event(self):
        t = make_trigger()
        t.stop()
        assert t._stop.is_set()


class TestIdleSessionLogic:
    """
    模擬 _idle_session 的 IMAP 互動，驗證 callback 觸發條件。
    直接呼叫 _idle_session 並在第一次迴圈結束後讓 _stop 設定為 True。
    """

    def _make_mock_conn(self, idle_resp, exists_line, search_type, search_data):
        conn = MagicMock()
        conn.readline.side_effect = [
            b"+ idling",   # IDLE 確認
            exists_line,   # server push
            b"A001 OK",    # DONE 回應
        ]
        conn.search.return_value = (search_type, [search_data])
        conn.socket.return_value = MagicMock()
        return conn

    def test_fb_email_triggers_callback(self):
        """EXISTS + 有未讀 FB 信 → callback 被呼叫。"""
        triggered = []

        async def cb():
            triggered.append(True)

        loop = asyncio.new_event_loop()
        trigger = make_trigger(cb)
        trigger._loop = loop
        trigger._stop = MagicMock()
        # 第一次 is_set() 回 False（進入迴圈），第二次回 True（離開迴圈）
        trigger._stop.is_set.side_effect = [False, True]

        conn = self._make_mock_conn(
            idle_resp=b"+ idling",
            exists_line=b"* 5 EXISTS",
            search_type="OK",
            search_data=b"1 2",
        )

        with patch("imap_trigger.imaplib.IMAP4_SSL", return_value=conn):
            trigger._idle_session()

        # run_coroutine_threadsafe 排進 loop，需 run 一次讓它執行
        loop.run_until_complete(asyncio.sleep(0))
        loop.close()
        assert triggered == [True]

    def test_no_fb_email_no_callback(self):
        """EXISTS 但沒有未讀 FB 信 → callback 不呼叫。"""
        triggered = []

        async def cb():
            triggered.append(True)

        loop = asyncio.new_event_loop()
        trigger = make_trigger(cb)
        trigger._loop = loop
        trigger._stop = MagicMock()
        trigger._stop.is_set.side_effect = [False, True]

        conn = self._make_mock_conn(
            idle_resp=b"+ idling",
            exists_line=b"* 5 EXISTS",
            search_type="OK",
            search_data=b"",   # 空 → 沒有 FB 未讀信
        )

        with patch("imap_trigger.imaplib.IMAP4_SSL", return_value=conn):
            trigger._idle_session()

        loop.run_until_complete(asyncio.sleep(0))
        loop.close()
        assert triggered == []

    def test_no_exists_no_callback(self):
        """Server push 不含 EXISTS → callback 不呼叫。"""
        triggered = []

        async def cb():
            triggered.append(True)

        loop = asyncio.new_event_loop()
        trigger = make_trigger(cb)
        trigger._loop = loop
        trigger._stop = MagicMock()
        trigger._stop.is_set.side_effect = [False, True]

        conn = self._make_mock_conn(
            idle_resp=b"+ idling",
            exists_line=b"* OK Still here",   # 不含 EXISTS
            search_type="OK",
            search_data=b"1",
        )

        with patch("imap_trigger.imaplib.IMAP4_SSL", return_value=conn):
            trigger._idle_session()

        loop.run_until_complete(asyncio.sleep(0))
        loop.close()
        assert triggered == []
