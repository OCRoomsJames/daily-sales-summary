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


def latest_sales_message(channel_id):
    response = client.conversations_history(
        channel=channel_id,
        limit=10
    )

    for msg in response["messages"]:
        if msg.get("subtype"):
            continue

        text = msg.get("text", "")

        if "Rev:" in text:
            return text

    raise Exception(f"No sales message found for {channel_id}")


def extract_revenues(text):
    matches = re.findall(r"Rev:\s*\$?([\d,]+\.\d+|[\d,]+)", text)

    values = [
        float(v.replace(",", ""))
        for v in matches
    ]

    if len(values) == 2:
        return values[1], values[0]

    if len(values) == 4:
        return (
            values[1] + values[3],
            values[0] + values[2],
        )

    raise Exception(
        f"Unexpected number of Rev values ({len(values)}).\n\n{text}"
    )


output = "*Daily Sales Summary TEST*\n\n"

for hotel, channel in HOTELS.items():

    message = latest_sales_message(channel)

    rev2026, rev2025 = extract_revenues(message)

    output += (
        f"*{hotel}*\n"
        f"2026: ${rev2026:,.2f}\n"
        f"2025: ${rev2025:,.2f}\n\n"
    )

client.chat_postMessage(
    channel=os.environ["SLACK_SUMMARY_CHANNEL"],
    text=output
)

print(output)
