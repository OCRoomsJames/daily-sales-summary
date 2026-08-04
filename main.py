import os
from slack_sdk import WebClient

client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])

client.chat_postMessage(
    channel=os.environ["SLACK_SUMMARY_CHANNEL"],
    text="Daily Sales Summary bot connected successfully!"
)

print("Message sent.")
