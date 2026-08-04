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

    raise RuntimeError(f"No sales message found for {hotel_name}.")


def extract_dates(text: str) -> list[str]:
    return re.findall(
        r"\b\d{1,2}/\d{1,2}/\d{4}\b",
        text,
    )


def extract_money_values(text: str, pattern: str) -> list[float]:
    matches = re.findall(
        pattern,
        text,
        flags=re.IGNORECASE,
    )

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
    revenue = extract_money_values(
        text,
        r"\bRev(?:enue)?\b\s*:?\s*\$?\s*([\d,]+(?:\.\d+)?)",
    )

    adr = extract_money_values(
        text,
        r"\bADR\b\s*:?\s*\$?\s*([\d,]+(?:\.\d+)?)",
    )

    revpar = extract_money_values(
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
            f"revenue={len(revenue)}, "
            f"adr={len(adr)}, "
            f"revpar={len(revpar)}, "
            f"rooms={len(rooms)}.\n\n"
            f"Message found:\n{text}"
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
    sections = re.split(
        r"\bSouth Beach\b",
        text,
        maxsplit=1,
        flags=re.IGNORECASE,
    )

    if len(sections) != 2:
        raise RuntimeError(
            "Could not separate Madison Beach and South Beach."
        )

    return [
        extract_standard_property(
            "Madison Beach",
            sections[0],
        ),
        extract_standard_property(
            "South Beach",
            sections[1],
        ),
    ]


def extract_beach_income(text: str, labels: list[str]) -> float:
    for label in labels:
        match = re.search(
            rf"\b{label}\b\s*:?\s*\$?\s*([\d,]+(?:\.\d+)?)",
            text,
            flags=re.IGNORECASE,
        )

        if match:
            return float(match.group(1).replace(",", ""))

    return 0.0


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


def signed_number(value: int) -> str:
    if value > 0:
        return f"+{value}"

    return str(value)


def performance_indicator(change: float, flat_threshold: float = 1.0) -> str:
    if abs(change) <= flat_threshold:
        return "⚪"

    if change > 0:
        return "🟢"

    return "🔴"


def rooms_indicator(change: int) -> str:
    if change == 0:
        return "⚪"

    if change > 0:
        return "🟢"

    return "🔴"


def number_word(value: int) -> str:
    words = {
        0: "zero",
        1: "one",
        2: "two",
        3: "three",
        4: "four",
        5: "five",
        6: "six",
        7: "seven",
        8: "eight",
        9: "nine",
        10: "ten",
    }

    return words.get(value, str(value))


def join_names(names: list[str]) -> str:
    if len(names) == 1:
        return names[0]

    if len(names) == 2:
        return f"{names[0]} and {names[1]}"

    return f"{', '.join(names[:-1])}, and {names[-1]}"


def raw_cell(text: str) -> dict:
    return {
        "type": "raw_text",
        "text": text,
    }


messages = {
    hotel_name: latest_sales_message(
        hotel_name,
        channel_id,
    )
    for hotel_name, channel_id in CHANNELS.items()
}


rows = [
    extract_standard_property(
        "Fenwick",
        messages["Fenwick"],
    ),
    extract_standard_property(
        "Kokomo",
        messages["Kokomo"],
    ),
    *extract_madison_properties(
        messages["Madison"],
    ),
    extract_standard_property(
        "Park Place",
        messages["Park Place"],
    ),
    extract_standard_property(
        "Spinnaker",
        messages["Spinnaker"],
    ),
]


dates = extract_dates(messages["Fenwick"])

if len(dates) >= 2:
    prior_date = dates[0]
    current_date = dates[1]
else:
    current_date = datetime.now().strftime("%m/%d/%Y")
    prior_date = "prior year"


for row in rows:
    row["revenue_change"] = (
        row["revenue_2026"]
        - row["revenue_2025"]
    )

    row["revenue_pct"] = percent_change(
        row["revenue_2026"],
        row["revenue_2025"],
    )

    row["adr_pct"] = percent_change(
        row["adr_2026"],
        row["adr_2025"],
    )

    row["revpar_pct"] = percent_change(
        row["revpar_2026"],
        row["revpar_2025"],
    )

    row["rooms_change"] = (
        row["rooms_2026"]
        - row["rooms_2025"]
    )


total_revenue_2026 = sum(
    row["revenue_2026"]
    for row in rows
)

total_revenue_2025 = sum(
    row["revenue_2025"]
    for row in rows
)

total_revenue_change = (
    total_revenue_2026
    - total_revenue_2025
)

total_revenue_pct = percent_change(
    total_revenue_2026,
    total_revenue_2025,
)

total_rooms_2026 = sum(
    row["rooms_2026"]
    for row in rows
)

total_rooms_2025 = sum(
    row["rooms_2025"]
    for row in rows
)

total_rooms_change = (
    total_rooms_2026
    - total_rooms_2025
)


park_place_beach = extract_beach_income(
    messages["Park Place"],
    ["Beach Sales"],
)

spinnaker_beach = extract_beach_income(
    messages["Spinnaker"],
    ["Beach Stand", "Beach Sales"],
)

combined_beach = (
    park_place_beach
    + spinnaker_beach
)


largest_gain = max(
    rows,
    key=lambda item: item["revenue_change"],
)

largest_decline = min(
    rows,
    key=lambda item: item["revenue_change"],
)

flat_hotels = [
    row["hotel"]
    for row in rows
    if abs(row["revenue_pct"]) <= 1.0
]


if total_revenue_change >= 0:
    overall_sentence = (
        f"Revenue increased *{abs(total_revenue_pct):.1f}%*"
    )
else:
    overall_sentence = (
        f"Revenue decreased *{abs(total_revenue_pct):.1f}%*"
    )


if total_rooms_change > 0:
    overall_sentence += (
        f" while selling *{number_word(total_rooms_change)} "
        f"additional "
        f"{'room' if total_rooms_change == 1 else 'rooms'}*."
    )
elif total_rooms_change < 0:
    overall_sentence += (
        f" while selling *{number_word(abs(total_rooms_change))} "
        f"fewer "
        f"{'room' if abs(total_rooms_change) == 1 else 'rooms'}*."
    )
else:
    overall_sentence += (
        " while selling the same number of rooms."
    )


summary_sentences = [overall_sentence]


if largest_gain["revenue_change"] > 0:
    gain_sentence = (
        f"{largest_gain['hotel']} posted the largest revenue gain, "
        f"up *{money(largest_gain['revenue_change'])} "
        f"({signed_percent(largest_gain['revenue_pct'])})*"
    )

    if (
        largest_gain["adr_pct"] < -1.0
        and largest_gain["rooms_change"] > 0
    ):
        gain_sentence += (
            f", despite ADR decreasing "
            f"*{abs(largest_gain['adr_pct']):.1f}%*, "
            f"with *{number_word(largest_gain['rooms_change'])} "
            f"additional rooms sold*."
        )
    elif largest_gain["adr_pct"] > 1.0:
        gain_sentence += (
            f", with ADR up "
            f"*{largest_gain['adr_pct']:.1f}%*."
        )
    elif largest_gain["rooms_change"] > 0:
        gain_sentence += (
            f", with *{number_word(largest_gain['rooms_change'])} "
            f"additional rooms sold*."
        )
    else:
        gain_sentence += "."

    summary_sentences.append(gain_sentence)


if largest_decline["revenue_change"] < 0:
    decline_sentence = (
        f"{largest_decline['hotel']} experienced the largest "
        f"year-over-year decline. Revenue fell "
        f"*{abs(largest_decline['revenue_pct']):.1f}%*"
    )

    decline_details = []

    if largest_decline["adr_pct"] < -1.0:
        decline_details.append(
            f"ADR down "
            f"*{abs(largest_decline['adr_pct']):.1f}%*"
        )

    if largest_decline["rooms_change"] < 0:
        decline_details.append(
            f"occupancy off "
            f"*{number_word(abs(largest_decline['rooms_change']))} "
            f"{'room' if abs(largest_decline['rooms_change']) == 1 else 'rooms'}*"
        )

    if decline_details:
        decline_sentence += (
            f", with {' and '.join(decline_details)}."
        )
    else:
        decline_sentence += "."

    summary_sentences.append(decline_sentence)


other_flat_hotels = [
    hotel
    for hotel in flat_hotels
    if hotel not in {
        largest_gain["hotel"],
        largest_decline["hotel"],
    }
]

if other_flat_hotels:
    summary_sentences.append(
        f"{join_names(other_flat_hotels)} finished "
        f"essentially flat compared with last year."
    )


table_rows = [
    [
        raw_cell("Hotel"),
        raw_cell("Revenue 26 / 25"),
        raw_cell("ADR 26 / 25"),
        raw_cell("RevPAR 26 / 25"),
        raw_cell("Rooms 26 / 25"),
    ]
]


for row in rows:
    revenue_cell = (
        f"{money(row['revenue_2026'])} / "
        f"{money(row['revenue_2025'])}\n"
        f"{performance_indicator(row['revenue_pct'])} "
        f"{signed_percent(row['revenue_pct'])}"
    )

    adr_cell = (
        f"{money(row['adr_2026'])} / "
        f"{money(row['adr_2025'])}\n"
        f"{performance_indicator(row['adr_pct'])} "
        f"{signed_percent(row['adr_pct'])}"
    )

    revpar_cell = (
        f"{money(row['revpar_2026'])} / "
        f"{money(row['revpar_2025'])}\n"
        f"{performance_indicator(row['revpar_pct'])} "
        f"{signed_percent(row['revpar_pct'])}"
    )

    rooms_cell = (
        f"{row['rooms_2026']} / "
        f"{row['rooms_2025']}\n"
        f"{rooms_indicator(row['rooms_change'])} "
        f"{signed_number(row['rooms_change'])}"
    )

    table_rows.append(
        [
            raw_cell(row["hotel"]),
            raw_cell(revenue_cell),
            raw_cell(adr_cell),
            raw_cell(revpar_cell),
            raw_cell(rooms_cell),
        ]
    )


table_block = {
    "type": "table",
    "column_settings": [
        {
            "align": "left",
            "is_wrapped": True,
        },
        {
            "align": "right",
            "is_wrapped": True,
        },
        {
            "align": "right",
            "is_wrapped": True,
        },
        {
            "align": "right",
            "is_wrapped": True,
        },
        {
            "align": "right",
            "is_wrapped": True,
        },
    ],
    "rows": table_rows,
}


blocks = [
    {
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": "Daily Sales Summary",
            "emoji": True,
        },
    },
    {
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": (
                    f"*{current_date}* compared with "
                    f"*{prior_date}*"
                ),
            }
        ],
    },
    table_block,
    {
        "type": "section",
        "fields": [
            {
                "type": "mrkdwn",
                "text": (
                    f"*Total Revenue*\n"
                    f"{money(total_revenue_2026)} vs "
                    f"{money(total_revenue_2025)}\n"
                    f"{performance_indicator(total_revenue_pct)} "
                    f"*{signed_money(total_revenue_change)} "
                    f"({signed_percent(total_revenue_pct)})*"
                ),
            },
            {
                "type": "mrkdwn",
                "text": (
                    f"*Total Rooms Sold*\n"
                    f"{total_rooms_2026} vs "
                    f"{total_rooms_2025}\n"
                    f"{rooms_indicator(total_rooms_change)} "
                    f"*{signed_number(total_rooms_change)}*"
                ),
            },
        ],
    },
    {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": (
                f"*Beach Income:* "
                f"Park Place {money(park_place_beach)} | "
                f"Spinnaker {money(spinnaker_beach)} | "
                f"Combined *{money(combined_beach)}*"
            ),
        },
    },
    {
        "type": "divider",
    },
    {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": (
                "*Management Read*\n"
                + " ".join(summary_sentences)
            ),
        },
    },
    {
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": (
                    "_South Beach is shown separately but remains included "
                    "in the Madison group and five-hotel total. Beach income "
                    "is not included in room revenue._"
                ),
            }
        ],
    },
]


fallback_text = (
    f"Daily Sales Summary — {current_date} vs {prior_date}. "
    f"Revenue {signed_percent(total_revenue_pct)}; "
    f"rooms sold {signed_number(total_rooms_change)}."
)


client.chat_postMessage(
    channel=os.environ["SLACK_SUMMARY_CHANNEL"],
    text=fallback_text,
    blocks=blocks,
)

print(fallback_text)
