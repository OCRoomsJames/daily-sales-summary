import os
import re
from datetime import datetime

from slack_sdk import WebClient


client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])

HOTELS = {
    "Fenwick": os.environ["SLACK_FENWICK_CHANNEL"],
    "Kokomo": os.environ["SLACK_KOKOMO_CHANNEL"],
    "Madison + South Beach": os.environ["SLACK_MADISON_CHANNEL"],
    "Park Place": os.environ["SLACK_PARK_PLACE_CHANNEL"],
    "Spinnaker": os.environ["SLACK_SPINNAKER_CHANNEL"],
}


def latest_sales_message(hotel_name: str, channel_id: str) -> str:
    response = client.conversations_history(channel=channel_id, limit=100)

    for message in response.get("messages", []):
        if message.get("subtype"):
            continue

        text = message.get("text", "")

        if re.search(r"\bRev(?:enue)?\b", text, re.IGNORECASE):
            return text

    raise RuntimeError(f"No sales message found for {hotel_name}.")


def extract_dates(text: str) -> list[str]:
    return re.findall(r"\b\d{1,2}/\d{1,2}/\d{4}\b", text)


def extract_revenues(hotel_name: str, text: str) -> tuple[float, float]:
    matches = re.findall(
        r"\bRev(?:enue)?\b\s*:?\s*\$?\s*([\d,]+(?:\.\d+)?)",
        text,
        flags=re.IGNORECASE,
    )

    values = [float(value.replace(",", "")) for value in matches]

    if len(values) == 2:
        return values[1], values[0]

    if len(values) == 4:
        revenue_2025 = values[0] + values[2]
        revenue_2026 = values[1] + values[3]
        return revenue_2026, revenue_2025

    raise RuntimeError(
        f"{hotel_name} contained {len(values)} revenue values instead of 2 or 4."
    )


def money(value: float, include_sign: bool = False) -> str:
    if include_sign:
        sign = "+" if value >= 0 else "-"
        return f"{sign}${abs(value):,.2f}"

    return f"${value:,.2f}"


results = []
report_dates = None

for hotel_name, channel_id in HOTELS.items():
    message = latest_sales_message(hotel_name, channel_id)
    revenue_2026, revenue_2025 = extract_revenues(hotel_name, message)

    if report_dates is None:
        dates = extract_dates(message)
        if len(dates) >= 2:
            report_dates = (dates[1], dates[0])

    results.append(
        {
            "hotel": hotel_name,
            "revenue_2026": revenue_2026,
            "revenue_2025": revenue_2025,
            "change": revenue_2026 - revenue_2025,
        }
    )

total_2026 = sum(item["revenue_2026"] for item in results)
total_2025 = sum(item["revenue_2025"] for item in results)
total_change = total_2026 - total_2025
percent_change = (total_change / total_2025 * 100) if total_2025 else 0

largest_gain = max(results, key=lambda item: item["change"])
largest_decline = min(results, key=lambda item: item["change"])

flat_hotels = [
    item["hotel"]
    for item in results
    if item["revenue_2025"]
    and abs(item["change"] / item["revenue_2025"]) <= 0.01
]

if report_dates:
    current_date, prior_date = report_dates
else:
    current_date = datetime.now().strftime("%m/%d/%Y")
    prior_date = "prior year"

header = (
    f"*Daily Sales Summary — {current_date} vs {prior_date}*\n\n"
    "```"
    f"{'Hotel':<25}"
    f"{'2026 Revenue':>16}"
    f"{'2025 Revenue':>16}"
    f"{'Change':>16}\n"
)

rows = ""

for item in results:
    rows += (
        f"{item['hotel']:<25}"
        f"{money(item['revenue_2026']):>16}"
        f"{money(item['revenue_2025']):>16}"
        f"{money(item['change'], True):>16}\n"
    )

rows += (
    f"{'TOTAL':<25}"
    f"{money(total_2026):>16}"
    f"{money(total_2025):>16}"
    f"{money(total_change, True):>16}"
)

table = header + rows + "```"

direction = "up" if total_change >= 0 else "down"

summary = (
    f"*Read:* Total revenue was {direction} "
    f"*{money(abs(total_change))}, or {abs(percent_change):.1f}%*, "
    f"versus last year's comparable day."
)

if largest_gain["change"] > 0:
    summary += (
        f" {largest_gain['hotel']} was the main positive driver, "
        f"up *{money(largest_gain['change'])}*."
    )

if largest_decline["change"] < 0:
    summary += (
        f" {largest_decline['hotel']} had the largest decline, "
        f"down *{money(abs(largest_decline['change']))}*."
    )

if flat_hotels:
    summary += f" {', '.join(flat_hotels)} was essentially flat."

note = (
    "_Note: Madison includes the separate South Beach section "
    "in the Madison total._"
)

output = f"{table}\n\n{summary}\n\n{note}"

client.chat_postMessage(
    channel=os.environ["SLACK_SUMMARY_CHANNEL"],
    text=output,
)

print(output)
