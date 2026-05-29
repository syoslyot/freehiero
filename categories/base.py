from dataclasses import dataclass
from typing import Callable

from detector import Detector
from models import Notification, Post


@dataclass
class Category:
    id: str
    name: str
    detector: Detector
    format_notification: Callable[[Post], Notification]
