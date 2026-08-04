import os
from slack_sdk import WebClient

client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])

response = client.conversations_history(
    channel=os.environ["SLACK_SPINNAKER_CHANNEL"],
    limit=1
)

messages = response.get("messages", [])

if not messages:
    raise RuntimeError("No messages found in the Spinnaker channel.")

latest_message = messages[0].get("text", "")

print("Latest Spinnaker message:")
print(latest_message)

client.chat_postMessage(
    channel=os.environ["SLACK_SUMMARY_CHANNEL"],
    text=f"*Spinnaker read test:*\n```{latest_message}```"
)

print("Spinnaker message read successfully.")
