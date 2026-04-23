"""
task_manager.py

Handles tasks 1–3 of the CS32-FP smart to-do list:
  1. Input tasks (name, category, due date, estimated time, difficulty, importance)
  2. Sort tasks by priority score
  3. Collect user preferences (productive hours, category preferences, light days)

Usage:
    from task_manager import collect_tasks, collect_preferences
    tasks     = collect_tasks()
    prefs     = collect_preferences()
"""

import datetime
import json
import os
from zoneinfo import ZoneInfo

TASKS_FILE       = "tasks.json"
PREFERENCES_FILE = "preferences.json"
TIMEZONE         = "America/New_York"

CATEGORIES = [
    "Work / Class",
    "Extracurriculars",
    "Errands",
    "Social",
    "Exercise",
    "Personal",
    "Other",
]

DAYS_OF_WEEK = [
    "Monday", "Tuesday", "Wednesday",
    "Thursday", "Friday", "Saturday", "Sunday"
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _prompt_int(prompt: str, lo: int, hi: int) -> int:
    """Keep asking until the user enters an integer in [lo, hi]."""
    while True:
        raw = input(prompt).strip()
        if raw.isdigit() and lo <= int(raw) <= hi:
            return int(raw)
        print(f"  ⚠️  Please enter a number between {lo} and {hi}.")


def _prompt_date(prompt: str) -> datetime.date:
    """Keep asking until the user enters YYYY-MM-DD or presses Enter for today."""
    while True:
        raw = input(prompt).strip()
        if raw == "":
            return datetime.date.today()
        try:
            return datetime.date.fromisoformat(raw)
        except ValueError:
            print("  ⚠️  Use format YYYY-MM-DD (e.g. 2025-05-10), or press Enter for today.")


def _prompt_float(prompt: str, lo: float, hi: float) -> float:
    """Keep asking until the user enters a float in [lo, hi]."""
    while True:
        raw = input(prompt).strip()
        try:
            val = float(raw)
            if lo <= val <= hi:
                return val
        except ValueError:
            pass
        print(f"  ⚠️  Please enter a number between {lo} and {hi}.")


def _choose_from_list(prompt: str, options: list[str]) -> str:
    """Display a numbered menu and return the chosen option string."""
    print(prompt)
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    idx = _prompt_int("  Enter number: ", 1, len(options))
    return options[idx - 1]


def _choose_multiple(prompt: str, options: list[str]) -> list[str]:
    """Let user pick zero or more items by number (comma-separated)."""
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
# Priority score
# ---------------------------------------------------------------------------

def compute_priority(task: dict, today: datetime.date | None = None) -> float:
    """
    Priority score (higher = more urgent / important).

    Components (all normalised to 0–1 before weighting):
      - deadline_imminence  weight 0.40  (1.0 = due today, 0.0 = due ≥30 days away)
      - importance          weight 0.30  (user rating 1–5)
      - difficulty          weight 0.20  (user rating 1–5)
      - estimated_hours     weight 0.10  (shorter tasks get slight boost for quick wins)
    """
    if today is None:
        today = datetime.date.today()

    due: datetime.date = task["due_date"]
    days_left = max(0, (due - today).days)
    deadline_score = max(0.0, 1.0 - days_left / 30.0)

    importance_score = (task["importance"] - 1) / 4.0   # 1-5 → 0-1
    difficulty_score = (task["difficulty"] - 1) / 4.0   # 1-5 → 0-1

    hours = task["estimated_hours"]
    # Quick-win bias: tasks ≤1 h score 1.0; tasks ≥8 h score 0.0
    quickness_score = max(0.0, 1.0 - (hours - 1) / 7.0)

    score = (
        0.40 * deadline_score
        + 0.30 * importance_score
        + 0.20 * difficulty_score
        + 0.10 * quickness_score
    )
    return round(score, 4)


def sort_tasks_by_priority(tasks: list[dict]) -> list[dict]:
    """Return tasks sorted from highest to lowest priority score."""
    today = datetime.date.today()
    for t in tasks:
        t["priority_score"] = compute_priority(t, today)
    return sorted(tasks, key=lambda t: t["priority_score"], reverse=True)


# ---------------------------------------------------------------------------
# Task 1 – Input tasks
# ---------------------------------------------------------------------------

def input_one_task() -> dict:
    """Interactively collect one task from the user."""
    print("\n" + "─" * 45)
    name = input("  Task name: ").strip()
    while not name:
        name = input("  Task name (cannot be empty): ").strip()

    category = _choose_from_list("\n  Category:", CATEGORIES)

    print("\n  Due date")
    due_date = _prompt_date("  Enter date (YYYY-MM-DD) or press Enter for today: ")

    estimated_hours = _prompt_float(
        "\n  Estimated time to complete (hours, e.g. 1.5): ", 0.1, 24.0
    )

    print("\n  Difficulty  (1 = very easy … 5 = very hard)")
    difficulty = _prompt_int("  Rating: ", 1, 5)

    print("\n  Importance  (1 = nice-to-have … 5 = critical)")
    importance = _prompt_int("  Rating: ", 1, 5)

    status_options = ["Not started", "In progress", "Done"]
    status = _choose_from_list("\n  Status:", status_options)

    task = {
        "name":            name,
        "category":        category,
        "due_date":        due_date,
        "estimated_hours": estimated_hours,
        "difficulty":      difficulty,
        "importance":      importance,
        "status":          status,
    }
    task["priority_score"] = compute_priority(task)
    return task


def collect_tasks(load_existing: bool = True) -> list[dict]:
    """
    Collect tasks interactively.  Loads previously saved tasks first
    if load_existing=True and the file exists.
    """
    tasks: list[dict] = []

    # Load existing tasks
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
# Task 2 – Sort & display by priority
# ---------------------------------------------------------------------------

def print_tasks(tasks: list[dict]) -> None:
    """Pretty-print tasks sorted by priority."""
    if not tasks:
        print("\n  (no tasks yet)")
        return

    sorted_tasks = sort_tasks_by_priority(tasks)
    today = datetime.date.today()

    print("\n📋  Tasks by Priority")
    print("=" * 60)
    for i, t in enumerate(sorted_tasks, 1):
        days_left = (t["due_date"] - today).days
        urgency = "🔴" if days_left <= 1 else "🟡" if days_left <= 4 else "🟢"
        status_icon = "✅" if t["status"] == "Done" else "🔄" if t["status"] == "In progress" else "⬜"
        print(
            f"  {i:>2}. {urgency} {status_icon}  {t['name']:<28}"
            f"  score={t['priority_score']:.2f}"
            f"  due={t['due_date']}  ({days_left}d)"
            f"  {t['category']}"
        )
    print()


# ---------------------------------------------------------------------------
# Task 3 – User preferences
# ---------------------------------------------------------------------------

def collect_preferences(load_existing: bool = True) -> dict:
    """
    Interactively collect user scheduling preferences.
    Returns a dict that can be used by the scheduler.
    """
    if load_existing and os.path.exists(PREFERENCES_FILE):
        prefs = _load_preferences()
        print(f"\n⚙️   Loaded existing preferences from {PREFERENCES_FILE}.")
        update = input("  Update preferences? (y/N): ").strip().lower()
        if update != "y":
            return prefs

    print("\n╔══════════════════════════════════════════╗")
    print("║         ⚙️   USER PREFERENCES            ║")
    print("╚══════════════════════════════════════════╝")

    # 1. Productive time of day
    print("\n  When are you most productive?")
    productive_time = _choose_from_list(
        "",
        ["Morning (6 AM – 12 PM)", "Afternoon (12 PM – 5 PM)",
         "Evening (5 PM – 9 PM)", "Night (9 PM – 12 AM)", "No preference"],
    )

    # Map to hour ranges
    productive_hours = {
        "Morning (6 AM – 12 PM)":   (6,  12),
        "Afternoon (12 PM – 5 PM)": (12, 17),
        "Evening (5 PM – 9 PM)":    (17, 21),
        "Night (9 PM – 12 AM)":     (21, 24),
        "No preference":            (8,  22),
    }[productive_time]

    # 2. Hard-task preference
    print("\n  Do you prefer doing hard tasks during your productive hours?")
    hard_tasks_in_productive = _choose_from_list(
        "",
        ["Yes – save hard tasks for peak hours",
         "No – spread tasks evenly",
         "No preference"],
    )

    # 3. Light days
    light_days = _choose_multiple(
        "\n  Which days do you want to be lighter / less busy?",
        DAYS_OF_WEEK,
    )

    # 4. Category time-of-day preferences
    print("\n  Do you prefer doing any categories at a specific time of day?")
    category_time_prefs: dict[str, str] = {}
    for cat in CATEGORIES:
        raw = input(f"  {cat} → preferred time (morning/afternoon/evening/night/any): ").strip().lower()
        if raw in ("morning", "afternoon", "evening", "night"):
            category_time_prefs[cat] = raw

    # 5. Max daily work hours
    max_daily_hours = _prompt_float(
        "\n  Max hours of tasks you want scheduled per day (e.g. 4): ", 0.5, 16.0
    )

    prefs = {
        "productive_time":            productive_time,
        "productive_hours":           productive_hours,
        "hard_tasks_in_productive":   hard_tasks_in_productive,
        "light_days":                 light_days,
        "category_time_prefs":        category_time_prefs,
        "max_daily_hours":            max_daily_hours,
    }

    _save_preferences(prefs)
    print("\n  ✅  Preferences saved.")
    return prefs


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def _task_to_json(task: dict) -> dict:
    """Convert a task dict to a JSON-serialisable form."""
    t = task.copy()
    if isinstance(t.get("due_date"), datetime.date):
        t["due_date"] = t["due_date"].isoformat()
    return t


def _task_from_json(data: dict) -> dict:
    """Restore a task dict from its JSON form."""
    d = data.copy()
    if isinstance(d.get("due_date"), str):
        d["due_date"] = datetime.date.fromisoformat(d["due_date"])
    return d


def _save_tasks(tasks: list[dict]) -> None:
    with open(TASKS_FILE, "w") as f:
        json.dump([_task_to_json(t) for t in tasks], f, indent=2)


def _load_tasks() -> list[dict]:
    with open(TASKS_FILE) as f:
        return [_task_from_json(d) for d in json.load(f)]


def _save_preferences(prefs: dict) -> None:
    with open(PREFERENCES_FILE, "w") as f:
        json.dump(prefs, f, indent=2)


def _load_preferences() -> dict:
    with open(PREFERENCES_FILE) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Standalone demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 50)
    print("  CS32-FP  Smart To-Do List  –  Setup")
    print("=" * 50)

    tasks = collect_tasks()
    print_tasks(tasks)

    prefs = collect_preferences()

    print("\n🎉  Setup complete!")
    print(f"    Tasks saved to:       {TASKS_FILE}")
    print(f"    Preferences saved to: {PREFERENCES_FILE}")
    print("\n  Run Find_time_slots.py to connect your Google Calendar.")
