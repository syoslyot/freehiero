import re
from abc import ABC, abstractmethod

import httpx

import config


class Detector(ABC):
    @abstractmethod
    def is_food_giveaway(self, text: str) -> bool: ...


# ── Layer 1 ───────────────────────────────────────────────────────────────────

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

# Both a free-signal word and a food word must appear on the same line
_PATTERN_FREE_FOOD = re.compile(
    rf"(?=.*({_FREE_WORDS}))(?=.*({_FOOD_WORDS}))", re.IGNORECASE
)

# Event (研討會 / 活動 / 工作坊 …) with leftover food nearby
_PATTERN_EVENT_FOOD = re.compile(
    r"(?:研討會|活動|工作坊|workshop|系上|系所|院上).{0,10}"
    r"(?:便當|餐盒|餐點|飲料|茶水|茶點|點心|食物|宵夜|剩食|buffet|美食|午餐|晚餐|早餐)",
    re.IGNORECASE | re.DOTALL,
)

# Explicit catering/free-meal announcement
_PATTERN_HAS_CATERING = re.compile(
    r"(?:有|免費|提供)供餐", re.IGNORECASE
)

# Obvious negatives: free things that are clearly not food
_PATTERN_NOT_FOOD = re.compile(
    r"免費.*?(?:課程|諮詢|講座|workshop|票|名額|索取|演講|入場)", re.IGNORECASE
)


class KeywordDetector(Detector):
    """Layer 1: fast regex. Returns True if text almost certainly describes free food."""

    def is_food_giveaway(self, text: str) -> bool:
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


# ── Layer 2 (optional) ────────────────────────────────────────────────────────

_OLLAMA_PROMPT = (
    "你是食物偵測助理。判斷以下社團貼文是否在免費提供食物（讓人拿取）。"
    "只回答 yes 或 no，不要解釋。\n\n貼文：{text}"
)


class OllamaDetector(Detector):
    """Layer 2: uses local Ollama model for ambiguous cases."""

    def is_food_giveaway(self, text: str) -> bool:
        if not text:
            return False
        try:
            resp = httpx.post(
                f"{config.OLLAMA_URL}/api/generate",
                json={
                    "model": config.OLLAMA_MODEL,
                    "prompt": _OLLAMA_PROMPT.format(text=text[:500]),
                    "stream": False,
                },
                timeout=30,
            )
            resp.raise_for_status()
            answer = resp.json().get("response", "").strip().lower()
            return answer.startswith("yes")
        except Exception as e:
            print(f"[OllamaDetector] error: {e}")
            return False


class TwoLayerDetector(Detector):
    """Layer 1 + optional Layer 2."""

    def __init__(self) -> None:
        self._kw = KeywordDetector()
        self._ollama = OllamaDetector() if config.OLLAMA_ENABLED else None

    def is_food_giveaway(self, text: str) -> bool:
        # Layer 1 direct match
        if self._kw.is_food_giveaway(text):
            return True
        # Layer 2 for borderline cases (has free/food keywords individually but not combined)
        if self._ollama and self._has_any_signal(text):
            return self._ollama.is_food_giveaway(text)
        return False

    @staticmethod
    def _has_any_signal(text: str) -> bool:
        return bool(re.search(_FREE_WORDS, text, re.IGNORECASE)) or bool(
            re.search(_FOOD_WORDS, text, re.IGNORECASE)
        )
