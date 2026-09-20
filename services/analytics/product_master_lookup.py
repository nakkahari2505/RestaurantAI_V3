from __future__ import annotations

import re
from difflib import SequenceMatcher

import pandas as pd


# User-facing commercial terms that should route to the product-master lookup.
# The answer remains the same for every accepted term: MRP + COGS + COGS %.
_PRODUCT_MASTER_TERMS = (
    "mrp",
    "price",
    "selling price",
    "menu price",
    "product price",
    "item price",
    "cogs",
    "cost",
    "food cost",
    "product cost",
    "gross margin",
    "gross profit",
    "margin",
    "gm",
)


def _normalize(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).casefold()).strip()


def _column_key(value: object) -> str:
    text = str(value).casefold().strip()
    text = text.replace("%", " percentage ")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _find_column(columns, candidates):
    normalized = {_column_key(column): column for column in columns}
    for candidate in candidates:
        key = _column_key(candidate)
        if key in normalized:
            return normalized[key]
    return None


def _format_money(value: float) -> str:
    if float(value).is_integer():
        return f"₹{int(value):,}"
    return f"₹{value:,.2f}"


def _fuzzy_ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()


def _looks_like_product_master_question(message: str) -> bool:
    """
    Detect product-master questions using commercial terms with spelling tolerance.

    Examples accepted:
    - MRP / mrpp
    - price / prise / prce
    - COGS / OCGS / cog
    - cost / food cost
    - gross margin / gross margn
    - margin / GM
    """
    text = _normalize(message)
    if not text:
        return False

    # Fast exact phrase check first.
    for term in _PRODUCT_MASTER_TERMS:
        if re.search(rf"\b{re.escape(term)}\b", text):
            return True

    tokens = text.split()

    # Check 1-, 2- and 3-word windows against the accepted vocabulary.
    # Thresholds are deliberately conservative enough to tolerate common
    # transpositions/missing letters without turning unrelated questions
    # into product-master lookups.
    windows: list[str] = []
    for size in (1, 2, 3):
        for i in range(len(tokens) - size + 1):
            windows.append(" ".join(tokens[i:i + size]))

    for window in windows:
        for term in _PRODUCT_MASTER_TERMS:
            # Tiny abbreviations such as GM need a stricter rule.
            if term == "gm":
                if window == "gm":
                    return True
                continue

            # Single-word commercial terms can tolerate one or two mistyped letters.
            threshold = 0.72 if " " not in term else 0.76
            if _fuzzy_ratio(window, term) >= threshold:
                return True

    return False


def _is_intent_noise_token(token: str) -> bool:
    """Return True for a misspelled commercial-intent token that should be removed."""
    token_n = _normalize(token)
    if not token_n:
        return False

    single_terms = ("mrp", "price", "cogs", "cost", "margin", "gm")
    for term in single_terms:
        if term == "gm":
            if token_n == "gm":
                return True
            continue
        if _fuzzy_ratio(token_n, term) >= 0.72:
            return True
    return False


def _extract_product_text(message: str) -> str:
    text = " ".join(str(message).strip().split())

    text = re.sub(
        r"(?i)^\s*(what|whats|what's|tell me|give me|show me|can you tell me)\s+",
        "",
        text,
    )

    # Remove exact multi-word commercial phrases first.
    text = re.sub(
        r"(?i)\b("
        r"selling\s+price|menu\s+price|product\s+price|item\s+price|"
        r"food\s+cost|product\s+cost|gross\s+margin|gross\s+profit|"
        r"cogs\s*%|cogs\s+percentage|cogs\s+percent"
        r")\b",
        " ",
        text,
    )

    # Remove fuzzy multi-word intent phrases as well (e.g. "gross margn").
    raw_tokens = text.split()
    keep = [True] * len(raw_tokens)
    fuzzy_multi_terms = ("selling price", "menu price", "product price", "item price",
                         "food cost", "product cost", "gross margin", "gross profit")
    for i in range(len(raw_tokens) - 1):
        pair = " ".join(
            token.strip(" ?.,:;!-_()[]{}") for token in raw_tokens[i:i + 2]
        )
        if any(_fuzzy_ratio(pair, term) >= 0.76 for term in fuzzy_multi_terms):
            keep[i] = False
            keep[i + 1] = False
    text = " ".join(token for token, flag in zip(raw_tokens, keep) if flag)

    # Remove common structural words.
    text = re.sub(
        r"(?i)\b(of|for|is|the|a|an|product|item|percentage|percent)\b",
        " ",
        text,
    )

    # Remove exact or fuzzy single-word intent terms (e.g. OCGS, prce, margn).
    remaining = []
    for token in text.split():
        clean = token.strip(" ?.,:;!-_()[]{}")
        if _is_intent_noise_token(clean):
            continue
        remaining.append(token)

    return " ".join(remaining).strip(" ?.,:;!-")


def _best_product_match(query: str, product_names: list[str]) -> tuple[str | None, float]:
    query_n = _normalize(query)
    if not query_n:
        return None, 0.0

    best_name = None
    best_score = 0.0
    for name in product_names:
        name_n = _normalize(name)
        if query_n == name_n:
            return name, 1.0
        score = SequenceMatcher(None, query_n, name_n).ratio()
        # Strongly reward containment for short natural-language variants.
        if query_n in name_n or name_n in query_n:
            score = max(score, 0.92)
        if score > best_score:
            best_name, best_score = name, score
    return best_name, best_score


def answer_product_master_question(data: dict, message: str) -> str | None:
    """
    Answer product-master commercial questions from item_category.

    Accepted intents include MRP, price, COGS/cost and gross-margin wording,
    with spelling tolerance. Regardless of the wording used, the response
    intentionally returns all three available fields: MRP, COGS and COGS %.

    Returns None when the message does not look like a product-master question.
    """
    if not _looks_like_product_master_question(str(message)):
        return None

    master = data.get("item_category")
    if not isinstance(master, pd.DataFrame) or master.empty:
        return "Sorry, product master information is not available in the current data."

    item_col = _find_column(master.columns, ("Item Name", "Item", "Product Name", "Product"))
    mrp_col = _find_column(master.columns, ("MRP", "Selling Price", "Menu Price", "Price"))
    cogs_col = _find_column(master.columns, ("COGS", "COGS Value", "Cost", "Food Cost", "Product Cost"))
    cogs_pct_col = _find_column(
        master.columns,
        ("COGS %", "COGS%", "COGS Percentage", "Food Cost %", "Food Cost%"),
    )

    if item_col is None or mrp_col is None or cogs_col is None:
        return "Sorry, I’m unable to answer this question with my current product-master data."

    work = master.copy()
    work = work[work[item_col].notna()].copy()
    work[item_col] = work[item_col].astype(str).str.strip()
    work = work[work[item_col] != ""]

    query = _extract_product_text(message)
    names = work[item_col].drop_duplicates().tolist()
    matched_name, score = _best_product_match(query, names)

    # Deliberately conservative: spelling tolerant, but do not confidently answer the wrong product.
    if matched_name is None or score < 0.62:
        return "Sorry, I couldn’t reliably match that product in the current product master."

    row = work.loc[work[item_col] == matched_name].iloc[-1]
    mrp = pd.to_numeric(pd.Series([row[mrp_col]]), errors="coerce").iloc[0]
    cogs = pd.to_numeric(pd.Series([row[cogs_col]]), errors="coerce").iloc[0]

    if pd.isna(mrp) or pd.isna(cogs):
        return f"I found *{matched_name}*, but its MRP/COGS details are incomplete in the product master."

    if cogs_pct_col is not None:
        cogs_pct = pd.to_numeric(pd.Series([row[cogs_pct_col]]), errors="coerce").iloc[0]
    else:
        cogs_pct = float(cogs) / float(mrp) * 100.0 if float(mrp) else float("nan")

    if pd.notna(cogs_pct) and abs(float(cogs_pct)) <= 1.0:
        # Excel percentage cells may be stored as 0.32 rather than 32.
        cogs_pct = float(cogs_pct) * 100.0

    pct_text = f"{float(cogs_pct):.1f}%" if pd.notna(cogs_pct) else "Not available"

    return (
        f"*{matched_name}*\n"
        f"MRP: *{_format_money(float(mrp))}*\n"
        f"COGS: *{_format_money(float(cogs))}*\n"
        f"COGS %: *{pct_text}*"
    )
