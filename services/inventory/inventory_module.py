"""Dated, item-code-based inventory answers for Auberry."""
from __future__ import annotations

import difflib
import math
import re
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import pandas as pd

MASTER = {"Item_Code", "Item Name", "Item Raw Name", "Vendor Name", "Unit", "Price", "MOQ", "Lead Time", "Avg Daily Consumption"}
MOVEMENT = {"Date", "Item_Code", "Opening Qty", "Opening Value", "Purchase Qty", "Purchase Value", "Issueing Qty", "Issueing Value", "Closing Qty", "Closing value"}
NOISE = set("how much many of the my our is are do i we have there in as now current stock quantity value days will last for what where buy buying from at which who supplies supplier vendor price per kg kgs ltr litre litres warehouse available and should order me give to tell please this long does it today remaining".split())


def norm(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


def item_phrase(question):
    return " ".join(w for w in norm(question).split() if w not in NOISE and not w.isdigit())


def num(value):
    n = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(n) else float(n)


def qty(value):
    rounded = Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return f"{rounded:,.1f}"


def daily_rate(value):
    # Tiny daily use must remain visible in the buying trigger.
    return f"{value:.2f}" if 0 < abs(value) < .1 else qty(value)


def money(value):
    rounded = str(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    sign = "-" if rounded.startswith("-") else ""
    digits = rounded.lstrip("-")
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        groups = []
        while head:
            groups.append(head[-2:])
            head = head[:-2]
        digits = ",".join(reversed(groups)) + "," + tail
    return f"₹{sign}{digits}"


@dataclass
class Inventory:
    items: pd.DataFrame
    daily: pd.DataFrame
    latest_date: object
    source: str

    @classmethod
    def load(cls, path: str | Path):
        master = pd.read_excel(path, sheet_name="Item_Master", dtype=object)
        daily = pd.read_excel(path, sheet_name="Stock_Data", dtype=object)
        if MASTER - set(master) or MOVEMENT - set(daily):
            raise ValueError(f"Missing columns: master {sorted(MASTER-set(master))}; stock {sorted(MOVEMENT-set(daily))}")
        if master.Item_Code.isna().any() or master.Item_Code.duplicated().any():
            raise ValueError("Item_Master must have unique, nonblank Item_Code values.")
        daily["Date"] = pd.to_datetime(daily["Date"], errors="coerce").dt.date
        if daily.Date.isna().any() or daily[["Date", "Item_Code"]].duplicated().any():
            raise ValueError("Stock_Data requires valid dates and one row per date and item code.")
        if set(daily.Item_Code) - set(master.Item_Code):
            raise ValueError("Stock_Data contains item codes absent from Item_Master.")
        for col in ("Opening Qty", "Opening Value", "Purchase Qty", "Purchase Value",
                    "Issueing Qty", "Issueing Value", "Closing Qty", "Closing value"):
            daily[col] = pd.to_numeric(daily[col].replace("-", 0), errors="coerce")
        for col in ("Price", "MOQ", "Lead Time", "Avg Daily Consumption"):
            master[col] = pd.to_numeric(master[col], errors="coerce")
        latest = daily.Date.max()
        if set(daily.loc[daily.Date == latest, "Item_Code"]) != set(master.Item_Code):
            raise ValueError("Latest stock date does not include every master item.")
        return cls(master, daily, latest, str(path))

    def _matches(self, question):
        phrase = item_phrase(question)
        if not phrase:
            return [], "Please name the inventory item."
        needle = norm(phrase)
        names = [(norm(row["Item Name"]), norm(row["Item Raw Name"])) for _, row in self.items.iterrows()]
        matched = [i for i, pair in enumerate(names) if any(re.search(r"\b"+re.escape(needle)+r"\b", name) for name in pair)]
        exact = [i for i in matched if names[i][0] == needle or names[i][1] == needle]
        if exact and needle not in {"maida", "coffee beans", "sugar"}:
            matched = exact
        if not matched:
            scored = []
            for i, pair in enumerate(names):
                tokens = [pair[0], pair[1], *pair[0].split(), *pair[1].split()]
                scored.append((max(difflib.SequenceMatcher(None, needle, t).ratio() for t in tokens if t), i))
            best = max(s for s, _ in scored)
            if best < .73:
                return [], f"I couldn't confidently match '{phrase}' to an inventory item."
            matched = [i for s, i in scored if s >= max(.73, best-.055)]
        return self.items.iloc[matched].to_dict("records"), None

    def _latest(self):
        return self.daily[self.daily.Date == self.latest_date].set_index("Item_Code")

    def reorder(self, limit=5):
        current = self._latest()
        rows = []
        for _, item in self.items.iterrows():
            code = item["Item_Code"]
            stock = num(current.loc[code, "Closing Qty"])
            use, lead = num(item["Avg Daily Consumption"]), num(item["Lead Time"])
            moq, price = num(item["MOQ"]), num(item["Price"])
            if stock is None or use is None or use <= 0 or lead is None or lead < 0:
                continue
            cover = max(0, stock) / use
            shortage = lead*use - stock
            if shortage <= 0 and stock > 0:
                continue
            # Replenish to two lead-time cycles of cover. MOQ is a minimum,
            # not assumed to be a pack-size multiple.
            target = 2*max(lead, 1)*use
            suggested = max(target-stock, moq if moq is not None and moq > 0 else 0)
            discrete = norm(item["Unit"]) in {"pc", "pcs", "pkt", "pack", "packet", "no", "nos", "bottles", "gallon"}
            suggested = math.ceil(suggested) if discrete else math.ceil(suggested*10-1e-9)/10
            exposure = max(shortage, 0)*(price if price is not None and price > 0 else 0)
            rows.append((exposure, shortage, stock, item, cover, suggested))
        rows.sort(key=lambda r: (-r[0], -r[1], str(r[3]["Item Name"])))
        lines = []
        for index, (_, _, stock, item, cover, suggested) in enumerate(rows[:limit], 1):
            unit = item["Unit"]
            flag = " Verify negative stock." if stock < 0 else ""
            lines.append(f'{index}. {item["Item Name"]}: stock {qty(stock)} {unit}; lead {qty(item["Lead Time"])} days; use {daily_rate(item["Avg Daily Consumption"])} {unit}/day; order {qty(suggested)} {unit}.{flag}')
        return (f"Buying priorities as of {self.latest_date:%d %b %Y}:\n" +
                ("\n".join(lines) if lines else "No items with valid consumption and lead time are below lead-time cover.") +
                "\nSuggested quantity targets two lead-time cycles of demand, with MOQ as a minimum. Ranked by projected lead-time shortage value; negative stock is flagged. Check pending orders and physical stock before buying.")

    def movement_answer(self, question):
        q = norm(question)
        purchase = bool(re.search(r"\b(purchase|purchases|purchased)\b", q))
        field = "Purchase Value" if purchase else "Issueing Value"
        label = "Purchase" if purchase else "Issue"
        days_match = re.search(r"\b(?:last|past|previous|for)\s+(\d{1,3})\s+days?\b", q)
        if not days_match:
            days_match = re.search(r"\b(\d{1,3})\s+days?\b", q)
        days = int(days_match.group(1)) if days_match else None
        if days is None and re.search(r"\b(?:last|past|previous|for)\s+(?:(?:one|1)\s+)?weeks?\b|\b(?:last|past|previous)\s+seven\s+days?\b", q):
            days = 7
        if days is not None and not 1 <= days <= 90:
            return "Please choose a trend period between 1 and 90 days."
        start = (self.latest_date - timedelta(days=days-1) if days is not None
                 else self.latest_date.replace(day=1))
        frame = self.daily[(self.daily.Date >= start) & (self.daily.Date <= self.latest_date)]
        total = frame[field].fillna(0).sum()
        span = (self.latest_date-start).days+1
        period = f"{start:%d %b}–{self.latest_date:%d %b %Y}"
        # A specifically requested day-count trend is a dated daily series.
        if days is not None and "trend" in q:
            daily = frame.groupby("Date")[field].sum()
            lines = [f"{day:%d %b %Y} | {money(daily.get(day, 0))}"
                     for day in (start + timedelta(days=i) for i in range(span))]
            return (f"{label} trend ({period}; INR):\nDate | Value\n" +
                    "\n".join(lines) + f"\nTotal: {money(total)}")
        if "average" in q and "trend" not in q and not re.search(r"\b(how|doing|performance)\b", q):
            return f"Average daily {label.lower()} value: {money(total/span)} over {span} calendar days ({period}); total {money(total)}."
        if "trend" in q or re.search(r"\b(how|doing|performance)\b", q):
            by_item = frame.groupby("Item_Code")[field].sum().sort_values(ascending=False).head(5)
            details = self.items.set_index("Item_Code")
            qty_field = "Purchase Qty" if purchase else "Issueing Qty"
            quantities = frame.groupby("Item_Code")[qty_field].sum()
            top = [f'{i}. {details.loc[code, "Item Name"]}: {qty(quantities.get(code, 0))} {details.loc[code, "Unit"]} ({money(value)})'
                   for i, (code, value) in enumerate(by_item.items(), 1) if value > 0]
            return (f"{label} this period ({period}; INR):\n"
                    f"Total: {money(total)}\nAverage per day: {money(total/span)}\n"
                    f"Top 5 items by {label.lower()} value (quantity and value):\n" +
                    ("\n".join(top) if top else "No recorded movement."))
        return f"Total {label.lower()} value: {money(total)} ({period}; INR)."

    def answer(self, question):
        q = norm(question)
        stamp = f"as of {self.latest_date:%d %b %Y}"
        if re.search(r"\b(what|which)\b.*\border\b|\b(reorder|buying priorities|order now|running out|burning items|urgent items|need to buy)\b", q):
            return self.reorder()
        if re.search(r"\b(total|overall|entire|all)\b", q) and ("stock" in q or "closing" in q) and "value" in q:
            latest = self._latest()
            count = int(((latest["Closing Qty"] > 0) & (latest["Closing value"].fillna(0) == 0)).sum())
            return f"Recorded total closing stock value: {money(latest['Closing value'].sum())} {stamp} (all items; INR). {count} items have positive quantity but zero/blank closing value; verify their valuation."
        if re.search(r"\b(purchase|purchases|purchased|issue|issues|issuing)\b", q):
            return self.movement_answer(question)
        matched, error = self._matches(question)
        if error:
            return error
        if re.search(r"\b(kgs?|kilograms?)\b", q):
            matched = [item for item in matched if norm(item["Unit"]) == "kg"]
            if not matched:
                return "No matching inventory items are recorded in KG."
        current = self._latest()
        vendor = bool(re.search(r"\b(vendor|supplier|buy|buying|price|where)\b", q))
        cover = bool(re.search(r"\b(days|last|cover|how long)\b", q))
        lines = []
        for item in matched:
            code = item["Item_Code"]
            row = current.loc[code]
            stock = num(row["Closing Qty"])
            value = num(row["Closing value"])
            unit = item["Unit"]
            prefix = str(item["Item Name"])
            if vendor:
                price = num(item["Price"])
                lines.append(f'{prefix}: {item["Vendor Name"] if pd.notna(item["Vendor Name"]) else "vendor unrecorded"}; listed price {money(price) + " per " + str(unit) if price is not None else "unrecorded"}.')
            elif cover:
                use = num(item["Avg Daily Consumption"])
                if stock is None or use is None or use <= 0:
                    lines.append(f"{prefix}: days cover unavailable (stock or average consumption missing).")
                elif stock < 0:
                    lines.append(f"{prefix}: {qty(stock)} {unit}; negative recorded stock, verify urgently. Days cover unavailable.")
                else:
                    lines.append(f"{prefix}: {qty(stock)} {unit} ÷ {daily_rate(use)} {unit}/day = {stock/use:.1f} days cover.")
            else:
                lines.append(f"{prefix}: {qty(stock) if stock is not None else 'unrecorded'} {unit}; closing value {money(value) if value is not None else 'unrecorded'}.")
        if not vendor and not cover and len(matched) > 1:
            units = {str(x["Unit"]) for x in matched}
            if len(units) == 1:
                rows = [current.loc[x["Item_Code"]] for x in matched]
                if all(num(r["Closing Qty"]) is not None for r in rows):
                    lines.append(f"Combined: {qty(sum(num(r['Closing Qty']) for r in rows))} {next(iter(units))}; recorded value {money(sum(num(r['Closing value']) or 0 for r in rows))}.")
        suffix = " The sheet has no warehouse location field; this is overall recorded stock." if "warehouse" in q else ""
        return f"Inventory {stamp}:\n" + "\n".join(lines) + suffix
