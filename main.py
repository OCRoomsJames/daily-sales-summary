import os
from slack_sdk import WebClient

client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])

response = client.conversations_history(
    channel=os.environ["SLACK_SPINNAKER_CHANNEL"],
    limit=10
)

messages = response["messages"]

latest_sales_message = None

for message in messages:
    # Skip Slack system messages like "joined the channel"
    if message.get("subtype"):
        continue

    text = message.get("text", "")

    if "Rev:" in text:
        latest_sales_message = text
        break

if latest_sales_message is None:
    raise Exception("Could not find a sales message.")

client.chat_postMessage(
    channel=os.environ["SLACK_SUMMARY_CHANNEL"],
    text=f"*Spinnaker read test:*\n```{latest_sales_message}```"
)

print("Success!")
