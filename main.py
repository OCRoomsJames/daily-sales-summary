import os
import re
from datetime import datetime

from slack_sdk import WebClient


client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])

CHANNELS = {
    "Fenwick": os.environ["SLACK_FENWICK_CHANNEL"],
    "Kokomo": os.environ["SLACK_KOKOMO_CHANNEL"],
    "Madison": os.environ["SLACK_MADISON_CHANNEL"],
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


def extract_values(text: str, pattern: str) -> list[float]:
    matches = re.findall(pattern, text, flags=re.IGNORECASE)

    return [
        float(value.replace(",", ""))
        for value in matches
    ]


def extract_rooms(text: str) -> list[int]:
    matches = re.findall(
        r"\bRooms?\s*Sold\b\s*:?\s*([\d,]+)",
        text,
        flags=re.IGNORECASE,
    )

    return [
        int(value.replace(",", ""))
        for value in matches
    ]


def extract_standard_property(hotel_name: str, text: str) -> dict:
    revenue = extract_values(
        text,
        r"\bRev(?:enue)?\b\s*:?\s*\$?\s*([\d,]+(?:\.\d+)?)",
    )

    adr = extract_values(
        text,
        r"\bADR\b\s*:?\s*\$?\s*([\d,]+(?:\.\d+)?)",
    )

    revpar = extract_values(
        text,
        r"\bRev\s*Par\b|\bRevPAR\b",
    )

    # RevPAR needs a separate expression because the amount follows the label.
    revpar = extract_values(
        text,
        r"\b(?:Rev\s*Par|RevPAR)\b\s*:?\s*\$?\s*([\d,]+(?:\.\d+)?)",
    )

    rooms = extract_rooms(text)

    if not (
        len(revenue) == 2
        and len(adr) == 2
        and len(revpar) == 2
        and len(rooms) == 2
    ):
        raise RuntimeError(
            f"{hotel_name} had unexpected data counts: "
            f"revenue={len(revenue)}, adr={len(adr)}, "
            f"revpar={len(revpar)}, rooms={len(rooms)}."
        )

    return {
        "hotel": hotel_name,
        "revenue_2025": revenue[0],
        "revenue_2026": revenue[1],
        "adr_2025": adr[0],
        "adr_2026": adr[1],
        "revpar_2025": revpar[0],
        "revpar_2026": revpar[1],
        "rooms_2025": rooms[0],
        "rooms_2026": rooms[1],
    }


def extract_madison_properties(text: str) -> list[dict]:
    parts = re.split(
        r"\bSouth Beach\b",
        text,
        maxsplit=1,
        flags=re.IGNORECASE,
    )

    if len(parts) != 2:
        raise RuntimeError("Could not separate Madison Beach and South Beach.")

    madison = extract_standard_property("Madison Beach", parts[0])
    south_beach = extract_standard_property("South Beach", parts[1])

    return [madison, south_beach]


def percent_change(current: float, prior: float) -> float:
    if prior == 0:
        return 0.0

    return (current - prior) / prior * 100


def money(value: float) -> str:
    return f"${value:,.2f}"


def signed_money(value: float) -> str:
    sign = "+" if value >= 0 else "-"
    return f"{sign}${abs(value):,.2f}"


def signed_percent(value: float) -> str:
    sign = "+" if value >= 0 else "-"
    return f"{sign}{abs(value):.1f}%"


def room_difference(current: int, prior: int) -> str:
    difference = current - prior

    if difference > 0:
        return f"+{difference}"

    return str(difference)


messages = {
    hotel_name: latest_sales_message(hotel_name, channel_id)
    for hotel_name, channel_id in CHANNELS.items()
}

rows = [
    extract_standard_property("Fenwick", messages["Fenwick"]),
    extract_standard_property("Kokomo", messages["Kokomo"]),
    *extract_madison_properties(messages["Madison"]),
    extract_standard_property("Park Place", messages["Park Place"]),
    extract_standard_property("Spinnaker", messages["Spinnaker"]),
]

dates = extract_dates(messages["Fenwick"])

if len(dates) >= 2:
    prior_date = dates[0]
    current_date = dates[1]
else:
    current_date = datetime.now().strftime("%m/%d/%Y")
    prior_date = "prior year"

table_lines = []

header = (
    f"{'Hotel':<16}"
    f"{'Revenue 26 / 25':>27}"
    f"{'ADR 26 / 25':>23}"
    f"{'RevPAR 26 / 25':>25}"
    f"{'Rooms 26 / 25':>18}"
)

table_lines.append(header)

for row in rows:
    revenue_pct = percent_change(
        row["revenue_2026"],
        row["revenue_2025"],
    )

    adr_pct = percent_change(
        row["adr_2026"],
        row["adr_2025"],
    )

    revpar_pct = percent_change(
        row["revpar_2026"],
        row["revpar_2025"],
    )

    revenue_text = (
        f"{money(row['revenue_2026'])} / "
        f"{money(row['revenue_2025'])} "
        f"({signed_percent(revenue_pct)})"
    )

    adr_text = (
        f"{money(row['adr_2026'])} / "
        f"{money(row['adr_2025'])} "
        f"({signed_percent(adr_pct)})"
    )

    revpar_text = (
        f"{money(row['revpar_2026'])} / "
        f"{money(row['revpar_2025'])} "
        f"({signed_percent(revpar_pct)})"
    )

    rooms_text = (
        f"{row['rooms_2026']} / "
        f"{row['rooms_2025']} "
        f"({room_difference(row['rooms_2026'], row['rooms_2025'])})"
    )

    table_lines.append(
        f"{row['hotel']:<16}"
        f"{revenue_text:>27}"
        f"{adr_text:>23}"
        f"{revpar_text:>25}"
        f"{rooms_text:>18}"
    )

five_hotel_rows = [
    row
    for row in rows
    if row["hotel"] != "South Beach"
]

total_revenue_2026 = sum(
    row["revenue_2026"]
    for row in five_hotel_rows
) + next(
    row["revenue_2026"]
    for row in rows
    if row["hotel"] == "South Beach"
)

total_revenue_2025 = sum(
    row["revenue_2025"]
    for row in five_hotel_rows
) + next(
    row["revenue_2025"]
    for row in rows
    if row["hotel"] == "South Beach"
)

total_revenue_change = total_revenue_2026 - total_revenue_2025
total_revenue_pct = percent_change(
    total_revenue_2026,
    total_revenue_2025,
)

total_rooms_2026 = sum(row["rooms_2026"] for row in rows)
total_rooms_2025 = sum(row["rooms_2025"] for row in rows)
total_room_change = total_rooms_2026 - total_rooms_2025

revenue_changes = [
    {
        "hotel": row["hotel"],
        "change": row["revenue_2026"] - row["revenue_2025"],
    }
    for row in rows
]

largest_gain = max(
    revenue_changes,
    key=lambda item: item["change"],
)

largest_decline = min(
    revenue_changes,
    key=lambda item: item["change"],
)

direction = "increased" if total_revenue_change >= 0 else "decreased"

room_wording = (
    f"despite selling {abs(total_room_change)} fewer room"
    if total_room_change < 0
    else f"while selling {total_room_change} more room"
    if total_room_change > 0
    else "while selling the same number of rooms"
)

if abs(total_room_change) != 1 and total_room_change != 0:
    room_wording += "s"

management_read = (
    f"*Management read:* Revenue {direction} "
    f"*{abs(total_revenue_pct):.1f}%* {room_wording} overall."
)

if largest_gain["change"] > 0:
    management_read += (
        f" {largest_gain['hotel']} drove the gain, up "
        f"*{money(largest_gain['change'])}*."
    )

if largest_decline["change"] < 0:
    management_read += (
        f" {largest_decline['hotel']} was the largest drag, down "
        f"*{money(abs(largest_decline['change']))}*."
    )

output = (
    f"*Expanded Daily Sales Summary — "
    f"{current_date} vs {prior_date}*\n\n"
    f"```{chr(10).join(table_lines)}```\n\n"
    f"*Five-hotel total revenue:* "
    f"*{money(total_revenue_2026)}* vs "
    f"*{money(total_revenue_2025)}* — "
    f"*{signed_money(total_revenue_change)} "
    f"({signed_percent(total_revenue_pct)})*\n"
    f"*Total rooms sold:* "
    f"*{total_rooms_2026}* vs *{total_rooms_2025}* "
    f"— {room_difference(total_rooms_2026, total_rooms_2025)} rooms\n\n"
    f"{management_read}\n\n"
    "_South Beach is shown separately for operating detail but remains "
    "included in the Madison group and five-hotel revenue total._"
)

client.chat_postMessage(
    channel=os.environ["SLACK_SUMMARY_CHANNEL"],
    text=output,
)

print(output)
