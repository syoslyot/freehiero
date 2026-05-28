import os
import tempfile

import pytest

import store


@pytest.fixture(autouse=True)
def tmp_db(monkeypatch, tmp_path):
    """每個測試用獨立的臨時 SQLite 檔。"""
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "test.db"))


class TestStore:
    def test_new_post_not_seen(self):
        assert store.is_seen("post_abc") is False

    def test_mark_then_seen(self):
        store.mark_seen("post_123")
        assert store.is_seen("post_123") is True

    def test_mark_idempotent(self):
        store.mark_seen("post_456")
        store.mark_seen("post_456")  # INSERT OR IGNORE, should not raise
        assert store.is_seen("post_456") is True

    def test_different_posts_independent(self):
        store.mark_seen("post_1")
        assert store.is_seen("post_2") is False

    def test_multiple_posts(self):
        ids = [f"post_{i}" for i in range(5)]
        for pid in ids:
            store.mark_seen(pid)
        for pid in ids:
            assert store.is_seen(pid) is True
