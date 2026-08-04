import os
import re

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
    response = client.conversations_history(
        channel=channel_id,
        limit=100,
    )

    for message in response.get("messages", []):
        if message.get("subtype"):
            continue

        text = message.get("text", "")

        # Matches Rev, Rev:, Revenue, or Revenue:
        if re.search(r"\bRev(?:enue)?\b", text, re.IGNORECASE):
            return text

    raise RuntimeError(
        f"No sales message containing Rev or Revenue was found for {hotel_name}."
    )


def extract_revenues(hotel_name: str, text: str) -> tuple[float, float]:
    # Matches:
    # Rev: $17,624.09
    # Revenue: $29,683.54
    # Revenue      $46,172.34
    # Rev: $13,563
    matches = re.findall(
        r"\bRev(?:enue)?\b\s*:?\s*\$?\s*([\d,]+(?:\.\d+)?)",
        text,
        flags=re.IGNORECASE,
    )

    values = [float(value.replace(",", "")) for value in matches]

    if len(values) == 2:
        revenue_2025 = values[0]
        revenue_2026 = values[1]
        return revenue_2026, revenue_2025

    if len(values) == 4:
        # Madison Beach and South Beach are posted together.
        revenue_2025 = values[0] + values[2]
        revenue_2026 = values[1] + values[3]
        return revenue_2026, revenue_2025

    raise RuntimeError(
        f"{hotel_name} contained {len(values)} revenue values instead of 2 or 4.\n\n"
        f"Message found:\n{text}"
    )


output = "*Daily Sales Summary TEST*\n\n"

for hotel_name, channel_id in HOTELS.items():
    message = latest_sales_message(hotel_name, channel_id)
    revenue_2026, revenue_2025 = extract_revenues(hotel_name, message)

    output += (
        f"*{hotel_name}*\n"
        f"2026: ${revenue_2026:,.2f}\n"
        f"2025: ${revenue_2025:,.2f}\n\n"
    )

client.chat_postMessage(
    channel=os.environ["SLACK_SUMMARY_CHANNEL"],
    text=output,
)

print(output)
