import pytest
from unittest.mock import MagicMock, patch

from detector import KeywordDetector, OllamaDetector, TwoLayerDetector


class TestKeywordDetector:
    def setup_method(self):
        self.det = KeywordDetector()

    # ── 正例 ──────────────────────────────────────────────────────────────────
    @pytest.mark.parametrize("text", [
        # free_word + food_word 同行
        "免費送！剩下的便當，快來拿",
        "多餘的餅乾，送給有需要的人，WP大廳",
        "有多的蛋糕，不要浪費，歡迎拿走",
        "free food！三明治在學生活動中心",
        "不要了，帶走，有麵包跟水果",
        "剩食分享，剩菜一鍋，有人要嗎",
        "寶特瓶裝奶茶6瓶，送人",
        "拿去！咖啡放在一樓桌上",
        "家裡帶的水果拿不完，不要了歡迎來拿",
        "活動剩下零食，請拿",
        # 新增 free_words
        "研討會多出來的餐盒，食安自負，請來自取",
        "剩餘便當在系館門口，先到先得",
        # 新增 food_words
        "免費領取餐盒，數量有限",
        "研討會多的便當和便當Buffet，有需要的人可至工科新館1樓",
        "免費餐點、茶點，今天沒吃完要冰冰箱",
        # event food pattern
        "研討會剩下的便當，地點國際會議廳B1",
        "研討會多的日式便當，目前有10個",
        "資源系研討會好吃的午餐，有素食便當",
        "活動buffet有剩，歡迎自備餐盒",
        "工作坊結束後剩下很多點心，請來取",
        # catering pattern
        "5/12 Meetup活動資訊，注意事項：有供餐",
        "舞展工作人員福利：當日免費供餐",
    ])
    def test_positive(self, text):
        assert self.det.is_food_giveaway(text) is True

    # ── 負例 ──────────────────────────────────────────────────────────────────
    @pytest.mark.parametrize("text", [
        "出售二手書，200元",
        "免費活動！社團公演，歡迎來看",       # 活動但無食物
        "免費諮詢，心理輔導中心開放預約",
        "免費課程，名額有限，立即報名",
        "免費演講，歡迎報名",                 # 演講
        "免費入場及抽獎，印尼文化節",         # 入場
        "徵室友，套房近學校",
        "今天吃了好吃的便當",                 # 有食物但不是送
        "免費索取票券",
        "有人要一起打球嗎",
        "",                                   # 空字串
        "天氣好適合出去走走",
        "研討會抽獎，全新iPad一台",           # 研討會但非食物
        "學術研討會徵求攝影師，時間13:30，包含午餐",  # 研討會+午餐但距離遠
    ])
    def test_negative(self, text):
        assert self.det.is_food_giveaway(text) is False


class TestTwoLayerDetector:
    def test_l1_hit_skips_ollama(self):
        """L1 直接命中時不呼叫 L2。"""
        with patch("detector.config") as mock_cfg:
            mock_cfg.OLLAMA_ENABLED = True
            mock_cfg.OLLAMA_URL = "http://localhost:11434"
            mock_cfg.OLLAMA_MODEL = "qwen2.5:0.5b"
            det = TwoLayerDetector()
            det._ollama = MagicMock(spec=OllamaDetector)
            result = det.is_food_giveaway("免費便當，快來拿！")
            det._ollama.is_food_giveaway.assert_not_called()
            assert result is True

    def test_l2_called_on_partial_signal(self):
        """L1 無法確定、有部分信號時，呼叫 L2。"""
        with patch("detector.config") as mock_cfg:
            mock_cfg.OLLAMA_ENABLED = True
            mock_cfg.OLLAMA_URL = "http://localhost:11434"
            mock_cfg.OLLAMA_MODEL = "qwen2.5:0.5b"
            det = TwoLayerDetector()
            mock_ollama = MagicMock(spec=OllamaDetector)
            mock_ollama.is_food_giveaway.return_value = True
            det._ollama = mock_ollama
            # 只有食物關鍵字，沒有免費關鍵字 → L1 不命中但有 signal → L2
            result = det.is_food_giveaway("有飯，有人要嗎")
            mock_ollama.is_food_giveaway.assert_called_once()
            assert result is True

    def test_no_signal_skips_l2(self):
        """完全沒有關鍵字信號，L2 不應被呼叫。"""
        with patch("detector.config") as mock_cfg:
            mock_cfg.OLLAMA_ENABLED = True
            mock_cfg.OLLAMA_URL = "http://localhost:11434"
            mock_cfg.OLLAMA_MODEL = "qwen2.5:0.5b"
            det = TwoLayerDetector()
            mock_ollama = MagicMock(spec=OllamaDetector)
            det._ollama = mock_ollama
            result = det.is_food_giveaway("徵室友，近學校，水電費另計")
            mock_ollama.is_food_giveaway.assert_not_called()
            assert result is False
