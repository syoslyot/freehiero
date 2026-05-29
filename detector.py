import re
from abc import ABC, abstractmethod

import httpx


class Detector(ABC):
    @abstractmethod
    def is_match(self, text: str) -> bool: ...


class OllamaDetector(Detector):
    """Layer 2: calls local Ollama; prompt_template must contain {text}."""

    def __init__(self, url: str, model: str, prompt_template: str) -> None:
        self._url = url
        self._model = model
        self._prompt_template = prompt_template

    def is_match(self, text: str) -> bool:
        if not text:
            return False
        try:
            resp = httpx.post(
                f"{self._url}/api/generate",
                json={
                    "model": self._model,
                    "prompt": self._prompt_template.format(text=text[:500]),
                    "stream": False,
                },
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json().get("response", "").strip().lower().startswith("yes")
        except Exception as e:
            print(f"[OllamaDetector] error: {e}")
            return False


class TwoLayerDetector(Detector):
    """L1 fast check; L2 only runs when L1 misses and signal_pattern matches (if given)."""

    def __init__(
        self,
        l1: Detector,
        l2: Detector | None = None,
        signal_pattern: re.Pattern | None = None,
    ) -> None:
        self._l1 = l1
        self._l2 = l2
        self._signal_pattern = signal_pattern

    def is_match(self, text: str) -> bool:
        if self._l1.is_match(text):
            return True
        if self._l2 is None:
            return False
        if self._signal_pattern is not None and not self._signal_pattern.search(text):
            return False
        return self._l2.is_match(text)
