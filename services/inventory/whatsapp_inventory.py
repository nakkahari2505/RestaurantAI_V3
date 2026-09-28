"""Inventory branch of the existing V3 WhatsApp message router."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from services.inventory.inventory_module import Inventory, classify_inventory_intent

WORKBOOK = Path(__file__).resolve().parents[2] / "data" / "auberry" / "inventory.xlsx"


@lru_cache(maxsize=2)
def _load(path: str, modified_ns: int):
    return Inventory.load(path)


def answer_inventory_whatsapp(message: str) -> str | None:
    intent = classify_inventory_intent(message)
    if intent is None:
        return None
    if not WORKBOOK.exists():
        return "Inventory data is unavailable: data/auberry/inventory.xlsx is missing." if intent.explicit else None
    try:
        inventory = _load(str(WORKBOOK), WORKBOOK.stat().st_mtime_ns)
    except (OSError, ValueError, KeyError) as exc:
        return f"Inventory data could not be read: {exc}"
    if not intent.explicit:
        matches, error = inventory._matches(message, implicit=True)
        if error and error.startswith("Which rice"):
            return error
        if error or not matches:
            return None
    return inventory.answer(message)
