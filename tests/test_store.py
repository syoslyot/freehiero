import pytest

import store


@pytest.fixture(autouse=True)
def tmp_db(monkeypatch, tmp_path):
    """每個測試用獨立的臨時 SQLite 檔。"""
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "test.db"))


class TestStore:
    def test_new_post_not_seen(self):
        assert store.is_seen("post_abc", "food") is False

    def test_mark_then_seen(self):
        store.mark_seen("post_123", "food")
        assert store.is_seen("post_123", "food") is True

    def test_mark_idempotent(self):
        store.mark_seen("post_456", "food")
        store.mark_seen("post_456", "food")  # INSERT OR IGNORE, should not raise
        assert store.is_seen("post_456", "food") is True

    def test_different_posts_independent(self):
        store.mark_seen("post_1", "food")
        assert store.is_seen("post_2", "food") is False

    def test_multiple_posts(self):
        ids = [f"post_{i}" for i in range(5)]
        for pid in ids:
            store.mark_seen(pid, "food")
        for pid in ids:
            assert store.is_seen(pid, "food") is True

    def test_same_post_different_categories_independent(self):
        """同一篇貼文對不同 category 是獨立記錄。"""
        store.mark_seen("post_1", "food")
        assert store.is_seen("post_1", "housing") is False

    def test_multiple_categories_for_same_post(self):
        store.mark_seen("post_1", "food")
        store.mark_seen("post_1", "housing")
        assert store.is_seen("post_1", "food") is True
        assert store.is_seen("post_1", "housing") is True
