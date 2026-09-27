"""Inventory branch of the existing V3 WhatsApp message router."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from services.inventory.inventory_module import Inventory, norm

WORKBOOK = Path(__file__).resolve().parents[2] / "data" / "auberry" / "inventory.xlsx"


@lru_cache(maxsize=2)
def _load(path: str, modified_ns: int):
    return Inventory.load(path)


def answer_inventory_whatsapp(message: str) -> str | None:
    q = norm(message)
    if re.search(r"\b(sales|transaction|revenue|ads|adt|apt)\b", q):
        return None
    explicit = bool(re.search(
        r"\b(inventory|stock|closing|warehouse|reorder|purchase|purchases|"
        r"issue|issues|issuing|consumption|supplier|vendor|buying|lead time)\b", q))
    contextual = bool(re.search(
        r"\bhow (much|many)\b.*\b(have|left|available)\b|"
        r"\bhow long\b.*\blast\b|\bwhere\b.*\bbuy\b|"
        r"\bwhat should i order\b|\bprice\b", q))
    if not (explicit or contextual):
        return None
    if not WORKBOOK.exists():
        return "Inventory data is unavailable: data/auberry/inventory.xlsx is missing." if explicit else None
    try:
        inventory = _load(str(WORKBOOK), WORKBOOK.stat().st_mtime_ns)
    except (OSError, ValueError, KeyError) as exc:
        return f"Inventory data could not be read: {exc}"
    if not explicit and "price" in q:
        matches, error = inventory._matches(message)
        if error or not matches:
            return None
    return inventory.answer(message)
