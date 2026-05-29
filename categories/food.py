import re

import config
from categories.base import Category
from detector import Detector, OllamaDetector, TwoLayerDetector
from models import Notification, Post

_FREE_WORDS = (
    r"免費|free|請拿|拿走|多餘|多的|多出|多出來|送人|不要了"
    r"|剩食|剩菜|剩下|剩餘|拿去|有需要|帶走|送出|分享|食安自負"
)
_FOOD_WORDS = (
    r"食物|食品|飯|麵|便當|零食|餅乾|水果|蔬菜|菜|湯|肉|蛋|麵包|吐司"
    r"|料理|點心|糕|餅|粽|飲料|奶茶|咖啡|茶|寶特瓶"
    r"|三明治|沙拉|漢堡|披薩|壽司|飯糰|泡麵|湯圓"
    r"|餐盒|餐點|供餐|美食|buffet|豆花|午餐|晚餐|早餐"
)

_PATTERN_FREE_FOOD = re.compile(
    rf"(?=.*({_FREE_WORDS}))(?=.*({_FOOD_WORDS}))", re.IGNORECASE
)
_PATTERN_EVENT_FOOD = re.compile(
    r"(?:研討會|活動|工作坊|workshop|系上|系所|院上).{0,10}"
    r"(?:便當|餐盒|餐點|飲料|茶水|茶點|點心|食物|宵夜|剩食|buffet|美食|午餐|晚餐|早餐)",
    re.IGNORECASE | re.DOTALL,
)
_PATTERN_HAS_CATERING = re.compile(r"(?:有|免費|提供)供餐", re.IGNORECASE)
_PATTERN_NOT_FOOD = re.compile(
    r"免費.*?(?:課程|諮詢|講座|workshop|票|名額|索取|演講|入場)", re.IGNORECASE
)
_SIGNAL_PATTERN = re.compile(rf"({_FREE_WORDS})|({_FOOD_WORDS})", re.IGNORECASE)

_OLLAMA_PROMPT = (
    "你是食物偵測助理。判斷以下社團貼文是否在免費提供食物（讓人拿取）。"
    "只回答 yes 或 no，不要解釋。\n\n貼文：{text}"
)


class FoodKeywordDetector(Detector):
    """Layer 1: fast regex for free-food posts."""

    def is_match(self, text: str) -> bool:
        if not text:
            return False
        if _PATTERN_NOT_FOOD.search(text):
            return False
        if _PATTERN_FREE_FOOD.search(text):
            return True
        if _PATTERN_EVENT_FOOD.search(text):
            return True
        if _PATTERN_HAS_CATERING.search(text):
            return True
        return False


def _format(post: Post) -> Notification:
    return Notification(
        title="社團免費食物通知",
        body=f"🍱 偵測到免費食物！\n\n{post.text[:200]}...\n\n{post.url}",
    )


def build() -> Category:
    l1 = FoodKeywordDetector()
    l2 = (
        OllamaDetector(config.OLLAMA_URL, config.OLLAMA_MODEL, _OLLAMA_PROMPT)
        if config.OLLAMA_ENABLED
        else None
    )
    return Category(
        id="food",
        name="免費食物",
        detector=TwoLayerDetector(l1, l2, signal_pattern=_SIGNAL_PATTERN),
        format_notification=_format,
    )
