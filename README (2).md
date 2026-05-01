# CS32-FP
## Description
*This project creates a smart to-do list program that helps users manage tasks by computing priority, organizing tasks by deadline and importance, and recommending what to do based on available time.*

## Before You Run
1. Install dependencies:
   ```
   pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
   ```
2. Place your Google OAuth credentials file in the project folder

## Components

**1) Ask the user to input tasks**

The program uses the `input_one_task` function to collect the following for each task:
- Task name
- Days until due (e.g. type `3` for a task due in 3 days)
- Importance: high, medium, or low
- Estimated hours to complete

The program validates all inputs before accepting them, and sends error messages for invalid inputs. Tasks are saved to `tasks.json` so that the user does not need to re-enter tasks every time they run the program.

**2) Sort tasks by priority**

The `compute_priority` function calculates a priority score (0.0–1.0) for each task as a weighted sum:
- 0.50 — deadline imminence (due today = 1.0, due in 30+ days = 0.0)
- 0.40 — importance (high = 1.0, medium = 0.5, low = 0.0)
- 0.10 — quick-win bias (shorter tasks get a small boost)

Tasks are then sorted from highest to lowest priority score and displayed in the terminal.

**3) Collect user preferences**

The `collect_preferences` function asks the user:
- When they are most productive (morning, afternoon, evening, or night)
- Whether they want high-importance tasks saved for their productive hours
- Which days of the week they want to keep lighter
- Maximum hours of tasks to schedule per day

Preferences are saved to `preferences.json` and reloaded automatically on subsequent runs.

**4) Connect to Google Calendar and identify open time slots**

Authentication is handled via an OAuth 2.0 Client ID created in Google Cloud Console. When the program runs, it prints an authorization URL in the terminal. The user follows the link, signs in with Google, copies the authorization code, and pastes it back into the terminal. The program then pulls events from the user's primary Google Calendar and uses the `find_free_slots` function to infer free time gaps of at least 30 minutes across the next 7 days.

**5) Suggest tasks to complete during open time slots**

The `schedule_tasks` function assigns tasks to free slots based on:
- Priority score (highest priority scheduled first)
- User preferences (productive hours, light days, max daily hours)
- Duration (tasks are split across multiple sessions if no single slot is large enough)

The scheduler runs two passes per task: first trying to find a slot that matches all preferences, then relaxing constraints if no perfect slot exists, so every task gets scheduled somewhere.

**6) Output a proposed weekly schedule**

The `print_week_view` function prints a unified day-by-day schedule combining:
- 📅 Pre-existing Google Calendar events
- 📝 Scheduled tasks (with a short explanation of why each was placed there, e.g. "matches your productive hours")
- 🕓 Remaining free time

## Motivation
The goal of this program is to help users — including busy college students — organize their to-do lists and complete all tasks in a productive and efficient manner.

## External Contributors
I used Claude to help write the code for this project. I prompted it to write the Google Calendar authentication and event-fetching logic, explaining what it would be used for. I then asked it to help gather user task inputs, specifying what details to collect and that inputs should be validated before being used in the priority score formula. I asked it to help design a weighted priority score formula and return a ranked task list. I also used Claude to build the user preferences collection and to integrate the calendar data, tasks, and preferences into a unified weekly schedule output. Along the way I used Claude to debug OAuth authentication errors encountered when running in a GitHub Codespaces environment.
