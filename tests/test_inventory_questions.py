"""Representative WhatsApp questions against the dated Auberry workbook."""
import unittest
import re

from services.inventory.whatsapp_inventory import answer_inventory_whatsapp


CASES = [
    ("How many water bottles are there?", "Auberry Water Bottle:"),
    ("How much maidaa do I have?", "Combined:"),
    ("How much coffee beans?", "Coffee Beans-Big Cup"),
    ("How much rice do I have?", "Which rice do you mean"),
    ("Closing stock at warehouse", "Total recorded closing stock value:"),
    ("What is my total inventory value?", "Total recorded closing stock value:"),
    ("Opening stock of oil", "Oil:"),
    ("What was the total opening stock value?", "Total recorded opening stock value:"),
    ("How long will my oil last?", "cover"),
    ("Where are we buying maida from?", "Sri Sai Roller Flour"),
    ("How is purchase this month?", "Top 5 items by purchase value"),
    ("How much oil did we purchase this month?", "Purchase for Oil"),
    ("How many KG of sugar were issued this month?", "KG; value"),
    ("Issue trend last one week", "Date | Value (INR)"),
    ("Purchase trend for last 6 days", "Date | Value (INR)"),
    ("day wise purchase for last 10 days", "Date | Value (INR)"),
    ("day wise issue in last one week", "Date | Value (INR)"),
    ("daily purchase breakdown for last 5 days", "Date | Value (INR)"),
    ("Average daily consumption of Oil", "LTR/day"),
    ("average rice consumption trend?", "Which rice do you mean"),
    ("What should I order today?", "order "),
    ("Which are running out of stock?", "Buying priorities"),
    ("Food closing stock value", "Food closing stock value:"),
    ("How is packaging purchase this month?", "Top 5 items by purchase value"),
    ("Total issue quantity this month", "different units"),
]


OTHER = [
    "Yesterday sales",
    "Price of chocolate cake",
    "How many transactions yesterday?",
]


class InventoryQuestions(unittest.TestCase):
    def test_inventory_questions(self):
        for question, expected in CASES:
            with self.subTest(question=question):
                answer = answer_inventory_whatsapp(question)
                self.assertIsNotNone(answer)
                self.assertIn(expected, answer)

    def test_other_business_questions_keep_existing_router(self):
        for question in OTHER:
            with self.subTest(question=question):
                self.assertIsNone(answer_inventory_whatsapp(question))

    def test_requested_daily_rows(self):
        for question, count in (
            ("day wise purchase for last 10 days", 10),
            ("day wise issue in last one week", 7),
        ):
            with self.subTest(question=question):
                answer = answer_inventory_whatsapp(question)
                dated_rows = re.findall(r"(?m)^\d{2} [A-Za-z]{3} \d{4} \| ₹", answer)
                self.assertEqual(len(dated_rows), count)
                self.assertIn("Total: ₹", answer)


if __name__ == "__main__":
    unittest.main()
