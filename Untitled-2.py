"""
google_calendar_auth.py

Handles OAuth 2.0 authentication with Google Calendar and extracts
busy/free time slots for the smart to-do list scheduler.

Usage:
    python google_calendar_auth.py

Requirements:
    pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
"""

import os
import json
import datetime
from zoneinfo import ZoneInfo

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CLIENT_SECRETS_FILE = "client_secret_65549107392-u49vtratgsqaosqrsaabla391hfnv5j7.apps.googleusercontent.com.json"
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
TOKEN_FILE = "token.json"  # cached credentials so user only logs in once


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def authenticate() -> Credentials:
    """
    Runs the OAuth 2.0 flow to get user consent and returns valid credentials.
    On first run: opens a browser tab asking the user to grant calendar access.
    On subsequent runs: silently refreshes the cached token.
    """
    creds = None

    # Reuse saved credentials if they exist
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    # If no valid credentials, prompt the user
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
            # Opens browser; falls back to manual copy-paste if no browser available
            creds = flow.run_local_server(port=0)

        # Save for future runs
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    return creds


# ---------------------------------------------------------------------------
# Calendar event fetching
# ---------------------------------------------------------------------------

def fetch_events(
    creds: Credentials,
    days_ahead: int = 7,
    timezone: str = "America/New_York",
) -> list[dict]:
    """
    Fetches all events from the user's primary Google Calendar
    for the next `days_ahead` days.

    Returns a list of dicts with keys:
        summary   – event title (str)
        start     – aware datetime
        end       – aware datetime
        all_day   – bool
    """
    service = build("calendar", "v3", credentials=creds)
    tz = ZoneInfo(timezone)

    now = datetime.datetime.now(tz)
    window_end = now + datetime.timedelta(days=days_ahead)

    # Google Calendar API requires RFC3339 strings
    events_result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=now.isoformat(),
            timeMax=window_end.isoformat(),
            singleEvents=True,          # expand recurring events
            orderBy="startTime",
        )
        .execute()
    )

    raw_events = events_result.get("items", [])
    events = []

    for e in raw_events:
        start_raw = e.get("start", {})
        end_raw = e.get("end", {})

        # All-day events use "date"; timed events use "dateTime"
        if "dateTime" in start_raw:
            start_dt = datetime.datetime.fromisoformat(start_raw["dateTime"]).astimezone(tz)
            end_dt = datetime.datetime.fromisoformat(end_raw["dateTime"]).astimezone(tz)
            all_day = False
        else:
            # All-day: treat as 00:00–23:59 on that date
            date = datetime.date.fromisoformat(start_raw["date"])
            start_dt = datetime.datetime(date.year, date.month, date.day, 0, 0, tzinfo=tz)
            end_dt = start_dt + datetime.timedelta(days=1) - datetime.timedelta(minutes=1)
            all_day = True

        events.append(
            {
                "summary": e.get("summary", "(No title)"),
                "start": start_dt,
                "end": end_dt,
                "all_day": all_day,
            }
        )

    return events


# ---------------------------------------------------------------------------
# Free-slot inference
# ---------------------------------------------------------------------------

def find_free_slots(
    events: list[dict],
    days_ahead: int = 7,
    day_start_hour: int = 8,
    day_end_hour: int = 22,
    min_slot_minutes: int = 30,
    timezone: str = "America/New_York",
) -> list[dict]:
    """
    Given a list of calendar events, returns a list of free time slots.

    Each slot is a dict with:
        date      – datetime.date
        start     – aware datetime
        end       – aware datetime
        duration  – datetime.timedelta

    Parameters:
        day_start_hour    – earliest hour to schedule tasks (default 8 AM)
        day_end_hour      – latest hour to stop scheduling (default 10 PM)
        min_slot_minutes  – ignore slots shorter than this many minutes
    """
    tz = ZoneInfo(timezone)
    today = datetime.datetime.now(tz).date()
    free_slots = []

    for offset in range(days_ahead):
        day = today + datetime.timedelta(days=offset)

        # Define the schedulable window for this day
        window_start = datetime.datetime(day.year, day.month, day.day, day_start_hour, 0, tzinfo=tz)
        window_end = datetime.datetime(day.year, day.month, day.day, day_end_hour, 0, tzinfo=tz)

        # Collect busy blocks that overlap with this day's window
        busy_blocks = []
        for e in events:
            # Clamp event times to the day's window
            block_start = max(e["start"], window_start)
            block_end = min(e["end"], window_end)
            if block_start < block_end:
                busy_blocks.append((block_start, block_end))

        # Sort and merge overlapping busy blocks
        busy_blocks.sort(key=lambda b: b[0])
        merged = []
        for block in busy_blocks:
            if merged and block[0] <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], block[1]))
            else:
                merged.append(list(block))

        # Walk through the day and collect gaps
        cursor = window_start
        for busy_start, busy_end in merged:
            if cursor < busy_start:
                duration = busy_start - cursor
                if duration >= datetime.timedelta(minutes=min_slot_minutes):
                    free_slots.append(
                        {
                            "date": day,
                            "start": cursor,
                            "end": busy_start,
                            "duration": duration,
                        }
                    )
            cursor = max(cursor, busy_end)

        # Gap after the last busy block until window_end
        if cursor < window_end:
            duration = window_end - cursor
            if duration >= datetime.timedelta(minutes=min_slot_minutes):
                free_slots.append(
                    {
                        "date": day,
                        "start": cursor,
                        "end": window_end,
                        "duration": duration,
                    }
                )

    return free_slots


# ---------------------------------------------------------------------------
# Pretty printing helpers (useful for debugging / CLI testing)
# ---------------------------------------------------------------------------

def print_events(events: list[dict]) -> None:
    print("\n📅  Upcoming Calendar Events")
    print("=" * 50)
    if not events:
        print("  (no events found)")
        return
    for e in events:
        tag = "[all-day]" if e["all_day"] else ""
        print(f"  {e['start'].strftime('%a %b %d  %H:%M')} – {e['end'].strftime('%H:%M')}  {tag}  {e['summary']}")


def print_free_slots(slots: list[dict]) -> None:
    print("\n🕓  Free Time Slots")
    print("=" * 50)
    if not slots:
        print("  (no free slots found)")
        return
    current_day = None
    for s in slots:
        if s["date"] != current_day:
            current_day = s["date"]
            print(f"\n  {current_day.strftime('%A, %B %d')}")
        hrs, rem = divmod(int(s["duration"].total_seconds()), 3600)
        mins = rem // 60
        duration_str = f"{hrs}h {mins}m" if hrs else f"{mins}m"
        print(f"    {s['start'].strftime('%H:%M')} – {s['end'].strftime('%H:%M')}  ({duration_str})")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("🔐  Connecting to Google Calendar…")
    credentials = authenticate()
    print("✅  Authenticated successfully!\n")

    events = fetch_events(credentials, days_ahead=7, timezone="America/New_York")
    print_events(events)

    free_slots = find_free_slots(
        events,
        days_ahead=7,
        day_start_hour=8,
        day_end_hour=22,
        min_slot_minutes=30,
        timezone="America/New_York",
    )
    print_free_slots(free_slots)

    # Export for use by the rest of your app
    # free_slots is a plain Python list — pass it directly to your scheduler
    print(f"\n✅  Found {len(free_slots)} free slot(s) across the next 7 days.")
