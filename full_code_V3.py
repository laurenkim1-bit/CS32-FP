"""
Find_time_slots.py

Smart To-Do List Scheduler
  1. Authenticate with Google Calendar
  2. Fetch calendar events + find free slots
  3. Input tasks (name, due date, importance, estimated hours)
  4. Collect user preferences (productive hours, light days, max daily hours)
  5. Schedule tasks into free slots respecting preferences + multi-session splitting
  6. Print a unified week view showing events, scheduled tasks, and free time

Requirements:
    pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client

#delete this - cleanly removed category, difficulty, status
"""

import os
import json
import copy
import datetime
from collections import defaultdict
from zoneinfo import ZoneInfo

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CREDENTIALS_FILE = "client_secret_65549107392-it02m633qlt6irk23jt6np1rj24te994.apps.googleusercontent.com.json"
SCOPES           = ["https://www.googleapis.com/auth/calendar.readonly"]
TOKEN_FILE       = "token.json"
TASKS_FILE       = "tasks.json"
PREFERENCES_FILE = "preferences.json"
TIMEZONE         = "America/New_York"

DAYS_OF_WEEK = [
    "Monday", "Tuesday", "Wednesday",
    "Thursday", "Friday", "Saturday", "Sunday",
]


# ---------------------------------------------------------------------------
# Prompt helpers
# ---------------------------------------------------------------------------

def _prompt_int(prompt: str, lo: int, hi: int) -> int:
    while True:
        raw = input(prompt).strip()
        if raw.isdigit() and lo <= int(raw) <= hi:
            return int(raw)
        print(f"  ⚠️  Please enter a number between {lo} and {hi}.")


def _prompt_float(prompt: str, lo: float, hi: float) -> float:
    while True:
        raw = input(prompt).strip()
        try:
            val = float(raw)
            if lo <= val <= hi:
                return val
        except ValueError:
            pass
        print(f"  ⚠️  Please enter a number between {lo} and {hi}.")


def _prompt_days_until_due(prompt: str) -> datetime.date:
    while True:
        raw = input(prompt).strip()
        if raw.isdigit():
            return datetime.date.today() + datetime.timedelta(days=int(raw))
        print("  ⚠️  Please enter a whole number (e.g. 3 for 3 days from now, 0 for today).")


def _choose_from_list(prompt: str, options: list) -> str:
    print(prompt)
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    idx = _prompt_int("  Enter number: ", 1, len(options))
    return options[idx - 1]


def _choose_multiple(prompt: str, options: list) -> list:
    print(prompt)
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    print("  (Enter numbers separated by commas, or press Enter to skip)")
    while True:
        raw = input("  Your choices: ").strip()
        if raw == "":
            return []
        parts = [p.strip() for p in raw.split(",")]
        if all(p.isdigit() and 1 <= int(p) <= len(options) for p in parts):
            return [options[int(p) - 1] for p in parts]
        print(f"  ⚠️  Enter numbers 1–{len(options)} separated by commas.")


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def authenticate() -> Credentials:
    print("Starting authentication...")
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            flow.redirect_uri = "urn:ietf:wg:oauth:2.0:oob"
            auth_url, _ = flow.authorization_url(prompt="consent")
            print(f"\nPlease visit this URL to authorize:\n{auth_url}\n")
            code = input("Enter the authorization code: ").strip()
            flow.fetch_token(code=code)
            creds = flow.credentials

        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    return creds


# ---------------------------------------------------------------------------
# Calendar event fetching
# ---------------------------------------------------------------------------

def fetch_events(
    creds: Credentials,
    days_ahead: int = 7,
    timezone: str = TIMEZONE,
) -> list:
    service = build("calendar", "v3", credentials=creds)
    tz = ZoneInfo(timezone)

    now        = datetime.datetime.now(tz)
    window_end = now + datetime.timedelta(days=days_ahead)

    events_result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=now.isoformat(),
            timeMax=window_end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    raw_events = events_result.get("items", [])
    events = []

    for e in raw_events:
        start_raw = e.get("start", {})
        end_raw   = e.get("end",   {})

        if "dateTime" in start_raw:
            start_dt = datetime.datetime.fromisoformat(start_raw["dateTime"]).astimezone(tz)
            end_dt   = datetime.datetime.fromisoformat(end_raw["dateTime"]).astimezone(tz)
            all_day  = False
        else:
            date     = datetime.date.fromisoformat(start_raw["date"])
            start_dt = datetime.datetime(date.year, date.month, date.day, 0, 0, tzinfo=tz)
            end_dt   = start_dt + datetime.timedelta(days=1) - datetime.timedelta(minutes=1)
            all_day  = True

        events.append({
            "summary": e.get("summary", "(No title)"),
            "start":   start_dt,
            "end":     end_dt,
            "all_day": all_day,
        })

    return events


# ---------------------------------------------------------------------------
# Free-slot inference
# ---------------------------------------------------------------------------

def find_free_slots(
    events: list,
    days_ahead: int = 7,
    day_start_hour: int = 8,
    day_end_hour: int = 22,
    min_slot_minutes: int = 30,
    timezone: str = TIMEZONE,
) -> list:
    tz    = ZoneInfo(timezone)
    today = datetime.datetime.now(tz).date()
    free_slots = []

    for offset in range(days_ahead):
        day          = today + datetime.timedelta(days=offset)
        window_start = datetime.datetime(day.year, day.month, day.day, day_start_hour, 0, tzinfo=tz)
        window_end   = datetime.datetime(day.year, day.month, day.day, day_end_hour,   0, tzinfo=tz)

        busy_blocks = []
        for e in events:
            block_start = max(e["start"], window_start)
            block_end   = min(e["end"],   window_end)
            if block_start < block_end:
                busy_blocks.append((block_start, block_end))

        busy_blocks.sort(key=lambda b: b[0])
        merged = []
        for block in busy_blocks:
            if merged and block[0] <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], block[1]))
            else:
                merged.append(list(block))

        cursor = window_start
        for busy_start, busy_end in merged:
            if cursor < busy_start:
                duration = busy_start - cursor
                if duration >= datetime.timedelta(minutes=min_slot_minutes):
                    free_slots.append({
                        "date":     day,
                        "start":    cursor,
                        "end":      busy_start,
                        "duration": duration,
                    })
            cursor = max(cursor, busy_end)

        if cursor < window_end:
            duration = window_end - cursor
            if duration >= datetime.timedelta(minutes=min_slot_minutes):
                free_slots.append({
                    "date":     day,
                    "start":    cursor,
                    "end":      window_end,
                    "duration": duration,
                })

    return free_slots


# ---------------------------------------------------------------------------
# Task input
# ---------------------------------------------------------------------------

def input_one_task() -> dict:
    print("\n" + "─" * 45)

    # Q1 – name
    name = input("  Task name: ").strip()
    while not name:
        name = input("  Task name (cannot be empty): ").strip()

    # Q2 – days until due
    due_date = _prompt_days_until_due("  Days until due (e.g. 3, or 0 for today): ")

    # Q3 – importance
    importance_map = {"h": 3, "m": 2, "l": 1}
    while True:
        raw = input("  Importance — high / medium / low (h/m/l): ").strip().lower()
        if raw in importance_map:
            importance = importance_map[raw]
            break
        print("  ⚠️  Enter h, m, or l.")

    # Q4 – estimated hours
    estimated_hours = _prompt_float("  Estimated hours to complete (e.g. 1.5): ", 0.1, 24.0)

    task = {
        "name":            name,
        "due_date":        due_date,
        "importance":      importance,
        "estimated_hours": estimated_hours,
        "hours_remaining": estimated_hours,
        "session_count":   1,
    }
    task["priority_score"] = compute_priority(task)
    return task


def collect_tasks(load_existing: bool = True) -> list:
    tasks = []

    if load_existing and os.path.exists(TASKS_FILE):
        tasks = _load_tasks()
        print(f"\n📋  Loaded {len(tasks)} existing task(s) from {TASKS_FILE}.")

    print("\n╔══════════════════════════════════════════╗")
    print("║         ✅  TASK INPUT                   ║")
    print("╚══════════════════════════════════════════╝")

    while True:
        print(f"\n  You currently have {len(tasks)} task(s).")
        action = _choose_from_list(
            "\n  What would you like to do?",
            ["Add a new task", "View current tasks", "Done adding tasks"],
        )

        if action == "Add a new task":
            task = input_one_task()
            tasks.append(task)
            print(f"\n  ✅  Added: '{task['name']}'  (priority score: {task['priority_score']:.2f})")
            _save_tasks(tasks)

        elif action == "View current tasks":
            print_tasks(tasks)

        else:
            break

    return tasks


# ---------------------------------------------------------------------------
# Priority scoring
# ---------------------------------------------------------------------------

def compute_priority(task: dict, today: datetime.date = None) -> float:
    """
    Weighted priority score (0.0 – 1.0, higher = do sooner).

    Weights:
      0.50  deadline imminence  (due today=1.0, due in 30+ days=0.0)
      0.40  importance          (high=1.0, medium=0.5, low=0.0)
      0.10  quick-win bias      (tasks ≤1h score highest)
    """
    if today is None:
        today = datetime.date.today()

    days_left      = max(0, (task["due_date"] - today).days)
    deadline_score = max(0.0, 1.0 - days_left / 30.0)

    # importance stored as 1/2/3 (low/medium/high) → normalise to 0/0.5/1.0
    importance_score = (task["importance"] - 1) / 2.0

    hours           = task["estimated_hours"]
    quickness_score = max(0.0, 1.0 - (hours - 1) / 7.0)

    return round(
        0.50 * deadline_score
        + 0.40 * importance_score
        + 0.10 * quickness_score,
        4,
    )


def sort_tasks_by_priority(tasks: list) -> list:
    today = datetime.date.today()
    for t in tasks:
        t["priority_score"] = compute_priority(t, today)
    return sorted(tasks, key=lambda t: t["priority_score"], reverse=True)


def print_tasks(tasks: list) -> None:
    if not tasks:
        print("\n  (no tasks yet)")
        return
    sorted_tasks = sort_tasks_by_priority(tasks)
    today        = datetime.date.today()
    imp_label    = {1: "low", 2: "med", 3: "high"}
    print("\n📋  Tasks by Priority")
    print("=" * 65)
    for i, t in enumerate(sorted_tasks, 1):
        days_left  = (t["due_date"] - today).days
        urgency    = "🔴" if days_left <= 1 else "🟡" if days_left <= 4 else "🟢"
        hrs_left   = t.get("hours_remaining", t["estimated_hours"])
        importance = imp_label.get(t["importance"], "?")
        print(
            f"  {i:>2}. {urgency}  {t['name']:<30}"
            f"  score={t['priority_score']:.2f}"
            f"  due in {days_left}d"
            f"  {importance} importance"
            f"  {hrs_left:.1f}h"
        )
    print()


# ---------------------------------------------------------------------------
# User preferences
# ---------------------------------------------------------------------------

def collect_preferences(load_existing: bool = True) -> dict:
    if load_existing and os.path.exists(PREFERENCES_FILE):
        prefs = _load_preferences()
        print(f"\n⚙️   Loaded existing preferences from {PREFERENCES_FILE}.")
        if input("  Update preferences? (Y/N): ").strip().lower() != "y":
            return prefs

    print("\n╔══════════════════════════════════════════╗")
    print("║         ⚙️   USER PREFERENCES             ║")
    print("╚══════════════════════════════════════════╝")

    productive_time = _choose_from_list(
        "\n  When are you most productive?",
        ["Morning (6 AM – 12 PM)", "Afternoon (12 PM – 5 PM)",
         "Evening (5 PM – 9 PM)", "Night (9 PM – 12 AM)", "No preference"],
    )
    productive_hours = {
        "Morning (6 AM – 12 PM)":   (6,  12),
        "Afternoon (12 PM – 5 PM)": (12, 17),
        "Evening (5 PM – 9 PM)":    (17, 21),
        "Night (9 PM – 12 AM)":     (21, 24),
        "No preference":            (8,  22),
    }[productive_time]

    high_importance_in_productive = _choose_from_list(
        "\n  Do you prefer doing high-importance tasks during your productive hours?",
        ["Yes – save high-importance tasks for peak hours",
         "No – spread tasks evenly",
         "No preference"],
    )

    light_days = _choose_multiple(
        "\n  Which days do you want to be lighter / less busy?",
        DAYS_OF_WEEK,
    )

    max_daily_hours = _prompt_float(
        "\n  Max hours of tasks to schedule per day (e.g. 4): ", 0.5, 16.0
    )

    prefs = {
        "productive_time":               productive_time,
        "productive_hours":              productive_hours,
        "high_importance_in_productive": high_importance_in_productive,
        "light_days":                    light_days,
        "max_daily_hours":               max_daily_hours,
    }
    _save_preferences(prefs)
    print("\n  ✅  Preferences saved.")
    return prefs


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

def _explain(task: dict, slot: dict, prefs: dict) -> str:
    reasons = []
    if task["priority_score"] >= 0.7:
        reasons.append("high priority")
    p_start, p_end = prefs["productive_hours"]
    if p_start <= slot["start"].hour < p_end:
        reasons.append("matches your productive hours")
    return ("Scheduled here: " + ", ".join(reasons)) if reasons else "Scheduled to fit your calendar"


def schedule_tasks(tasks: list, free_slots: list, prefs: dict) -> list:
    """
    Assign tasks to free slots respecting preferences.
    Splits tasks across multiple sessions if no single slot is large enough.
    Returns a list of scheduled blocks.
    """
    slots        = copy.deepcopy(free_slots)
    sorted_tasks = sort_tasks_by_priority(copy.deepcopy(tasks))
    schedule     = []
    daily_booked = {}   # date -> hours already booked that day

    p_start, p_end = prefs["productive_hours"]

    for task in sorted_tasks:
        remaining = task.get("hours_remaining", task["estimated_hours"])
        if remaining <= 0:
            continue

        # Two passes: first try slots matching preferences, then any available slot
        for strict in (True, False):
            if remaining <= 0:
                break

            for slot in slots:
                if remaining <= 0:
                    break

                slot_hour      = slot["start"].hour
                day_name       = slot["date"].strftime("%A")
                already_booked = daily_booked.get(slot["date"], 0.0)

                # Skip fully used slots
                if slot["duration"] < datetime.timedelta(minutes=30):
                    continue

                # Respect light days
                if day_name in prefs["light_days"]:
                    continue

                # Respect max daily hours
                if already_booked >= prefs["max_daily_hours"]:
                    continue

                # High-importance tasks → productive hours (strict pass only)
                is_important  = task["importance"] >= 3
                in_productive = p_start <= slot_hour < p_end
                if (strict
                        and prefs["high_importance_in_productive"].startswith("Yes")
                        and is_important
                        and not in_productive):
                    continue

                # How much can we book here?
                slot_hours_available = slot["duration"].total_seconds() / 3600
                hours_allowed_today  = prefs["max_daily_hours"] - already_booked
                chunk = min(remaining, slot_hours_available, hours_allowed_today)
                if chunk < 0.5:
                    continue

                end_time = slot["start"] + datetime.timedelta(hours=chunk)
                schedule.append({
                    "task":    task,
                    "start":   slot["start"],
                    "end":     end_time,
                    "session": task["session_count"],
                    "reason":  _explain(task, slot, prefs),
                })

                remaining                  -= chunk
                task["hours_remaining"]     = remaining
                task["session_count"]      += 1
                daily_booked[slot["date"]]  = already_booked + chunk
                slot["start"]              += datetime.timedelta(hours=chunk)
                slot["duration"]           -= datetime.timedelta(hours=chunk)

    return schedule


# ---------------------------------------------------------------------------
# Output – unified week view
# ---------------------------------------------------------------------------

def print_week_view(events: list, schedule: list, free_slots: list) -> None:
    tz        = ZoneInfo(TIMEZONE)
    today     = datetime.datetime.now(tz).date()
    day_items = defaultdict(list)

    for e in events:
        day_items[e["start"].date()].append({
            "type":    "event",
            "start":   e["start"],
            "end":     e["end"],
            "label":   e["summary"],
            "all_day": e["all_day"],
        })

    for s in schedule:
        total_sessions = s["task"]["session_count"] - 1
        session_label  = f" (Part {s['session']}/{total_sessions})" if total_sessions > 1 else ""
        day_items[s["start"].date()].append({
            "type":   "task",
            "start":  s["start"],
            "end":    s["end"],
            "label":  s["task"]["name"] + session_label,
            "reason": s["reason"],
            "score":  s["task"]["priority_score"],
        })

    for slot in free_slots:
        if slot["duration"] >= datetime.timedelta(minutes=30):
            day_items[slot["date"]].append({
                "type":  "free",
                "start": slot["start"],
                "end":   slot["end"],
                "label": "",
            })

    print("\n")
    print("╔══════════════════════════════════════════════════════════╗")
    print("║              📆  WEEK SCHEDULE                           ║")
    print("╚══════════════════════════════════════════════════════════╝")

    for day in sorted(day_items.keys()):
        items     = sorted(day_items[day], key=lambda x: x["start"])
        day_label = day.strftime("%A, %B %d")
        if day == today:
            day_label += "  ← today"
        print(f"\n  {day_label}")
        print("  " + "─" * 54)

        for item in items:
            time_str = f"{item['start'].strftime('%H:%M')} – {item['end'].strftime('%H:%M')}"

            if item["type"] == "event":
                tag = "[all-day]" if item.get("all_day") else "📅"
                print(f"    {time_str}  {tag} {item['label']}")

            elif item["type"] == "task":
                hrs = (item["end"] - item["start"]).total_seconds() / 3600
                print(f"    {time_str}  📝 [TASK] {item['label']}")
                print(f"                    ↳ {item['reason']}  (score={item['score']:.2f}, {hrs:.1f}h)")

            elif item["type"] == "free":
                hrs, rem = divmod(int((item["end"] - item["start"]).total_seconds()), 3600)
                mins     = rem // 60
                dur_str  = f"{hrs}h {mins}m" if hrs else f"{mins}m"
                print(f"    {time_str}  🕓 FREE ({dur_str})")

    print()


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def _task_to_json(task: dict) -> dict:
    t = task.copy()
    if isinstance(t.get("due_date"), datetime.date):
        t["due_date"] = t["due_date"].isoformat()
    return t


def _task_from_json(data: dict) -> dict:
    d = data.copy()
    if isinstance(d.get("due_date"), str):
        d["due_date"] = datetime.date.fromisoformat(d["due_date"])
    return d


def _save_tasks(tasks: list) -> None:
    with open(TASKS_FILE, "w") as f:
        json.dump([_task_to_json(t) for t in tasks], f, indent=2)


def _load_tasks() -> list:
    with open(TASKS_FILE) as f:
        return [_task_from_json(d) for d in json.load(f)]


def _save_preferences(prefs: dict) -> None:
    with open(PREFERENCES_FILE, "w") as f:
        json.dump(prefs, f, indent=2)


def _load_preferences() -> dict:
    with open(PREFERENCES_FILE) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 58)
    print("  CS32-FP  Smart To-Do List Scheduler")
    print("=" * 58)

    # Step 1 – Google Calendar
    print("\n🔐  Connecting to Google Calendar…")
    credentials = authenticate()
    print("✅  Authenticated successfully!\n")

    events = fetch_events(credentials, days_ahead=7, timezone=TIMEZONE)
    free_slots = find_free_slots(
        events,
        days_ahead=7,
        day_start_hour=8,
        day_end_hour=22,
        min_slot_minutes=30,
        timezone=TIMEZONE,
    )
    print(f"📅  Fetched {len(events)} calendar event(s).")
    print(f"🕓  Found {len(free_slots)} free slot(s) across the next 7 days.\n")

    # Step 2 – Tasks
    tasks = collect_tasks()
    print_tasks(tasks)

    # Step 3 – Preferences
    prefs = collect_preferences()

    # Step 4 – Schedule
    print("\n⏳  Building your schedule…")
    schedule = schedule_tasks(tasks, free_slots, prefs)
    print(f"✅  Scheduled {len(schedule)} task session(s).\n")

    # Step 5 – Print unified week view
    print_week_view(events, schedule, free_slots)

    print(f"💾  Tasks saved to:       {TASKS_FILE}")
    print(f"💾  Preferences saved to: {PREFERENCES_FILE}")
    print("\n🎉  Done!")
