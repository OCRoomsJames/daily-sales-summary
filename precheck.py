import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from slack_sdk import WebClient


client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])


def set_output(value: bool, reason: str) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as output_file:
            output_file.write(f"should_run={'true' if value else 'false'}\n")
            output_file.write(f"reason={reason}\n")

    print(reason)


def latest_sales_message(channel_id: str) -> str:
    response = client.conversations_history(
        channel=channel_id,
        limit=100,
    )

    for message in response.get("messages", []):
        if message.get("subtype"):
            continue

        text = message.get("text", "")
        if re.search(r"\bRev(?:enue)?\b", text, re.IGNORECASE):
            return text

    raise RuntimeError("No Fenwick sales message was found.")


def report_date_from_fenwick() -> str:
    text = latest_sales_message(os.environ["SLACK_FENWICK_CHANNEL"])
    dates = re.findall(r"\b\d{1,2}/\d{1,2}/\d{4}\b", text)

    if len(dates) < 2:
        raise RuntimeError("Could not determine the current report date from Fenwick.")

    return dates[1]


def already_posted(report_date: str) -> bool:
    response = client.conversations_history(
        channel=os.environ["SLACK_SUMMARY_CHANNEL"],
        limit=100,
    )

    for message in response.get("messages", []):
        text = message.get("text", "")
        if "Daily Sales Summary" in text and report_date in text:
            return True

    return False


event_name = os.environ.get("GITHUB_EVENT_NAME", "")

# Manual runs always proceed so you can still generate a report on demand.
if event_name == "workflow_dispatch":
    set_output(True, "Manual run requested; proceeding.")
    raise SystemExit(0)

# Scheduled attempts are accepted only around the intended 8:45 AM Eastern window.
now_et = datetime.now(ZoneInfo("America/New_York"))
minutes_after_midnight = now_et.hour * 60 + now_et.minute
window_start = 8 * 60 + 30
window_end = 9 * 60 + 30

if not (window_start <= minutes_after_midnight <= window_end):
    set_output(
        False,
        f"Scheduled attempt arrived at {now_et:%I:%M %p ET}, outside the 8:30-9:30 AM window; skipping.",
    )
    raise SystemExit(0)

report_date = report_date_from_fenwick()

if already_posted(report_date):
    set_output(False, f"Daily Sales Summary for {report_date} already exists; skipping duplicate.")
else:
    set_output(True, f"No Daily Sales Summary found for {report_date}; proceeding.")
