import logging
from typing import TYPE_CHECKING

import config

if TYPE_CHECKING:
    from categories.base import Category

from categories.food import build as _build_food
from categories.housing import build as _build_housing

_BUILDERS = {
    "food": _build_food,
    "housing": _build_housing,
}


def get_enabled() -> list["Category"]:
    enabled = []
    for cat_id in config.ENABLED_CATEGORIES:
        builder = _BUILDERS.get(cat_id)
        if builder is None:
            logging.warning("[categories] unknown category '%s', skipped", cat_id)
            continue
        enabled.append(builder())
    return enabled
