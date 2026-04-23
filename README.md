# CS32-FP
## Description
*This project will create a smart to-do list program that helps users manage tasks by computing priority, organizing tasks by category and deadline, and recommending what to do based on available time.*

## Components
*The program will do the following:*

**1) Ask the user to input tasks and relevant information such as:**
- Task name
- Category (e.g., work, extracurriculars, errands, exercise)
- Due date
- Estimated time
- Difficulty (ranked 1-5)
- Importance (ranked 1-5)
These tasks will be stored in a dictionary.
The program uses the input_one_task function to ask the user whether they want to add a new task, edit task status, view current tasks, or finish adding tasks. If the user chooses to add a new task, the program will validate the user inputs to make sure they are usable in the priority score formula, then return the task, including all the relevant information.

**2) Sort tasks by priority**

Here, the program's compute_priority function will calculate a “priority score” for each task based on estimated time, deadline imminence, difficulty, and importance. This looks like a weighted sum of each of those factors:
- 0.40  deadline imminence  (due today=1.0, due in 30+ days=0.0)
- 0.30  importance          (1–5 scale)
- 0.20  difficulty          (1–5 scale)
- 0.10  quick-win bias      (i.e., if the task is short and can be knocked-out quickly)

**3. Collect user preferences**

Some users may prefer working on tasks within certain categories at particular times in the day, or doing tasks in a particular order. Users may be more productive in the morning (or at night), and prefer to do more difficult tasks during these times of higher productivity. Users might want to have certain days (e.g., weekends) be less busy. The program will use the collect_preferences function to collect this information and incorporate it into the proposed schedule.

**4. Have users upload their Google Calendar and identify open time slots**
I did this by creating an OAuth 2.0 Client ID in Google Cloud. This allows the program to pull events from the user's Google Calendar and and extract start/end times, which it then uses to infer free time slots using the find_free_slots function. Once the program runs, a link is printed in the terminal. If the user follows this link, it will take them to a page that allows them to "Sign in or provide access to CS32-FP" by copying an authorization code and pasting it back into terminal.


**5. Suggest tasks to complete during open time slots**

These suggestions will be based on:
- Duration (tasks that fit in open time slots)
- Priority score
- User preferences

The function schedule_tasks assigns tasks to free slots respecting preferences, splits tasks across multiple sessions if no single slot is large enough, and then returns a list of scheduled blocks. The final print out also includes a short explanation for why a certain task was scheduled at a certain time, such as "matches your productive hours".

**5. Output a proposed schedule for the week**

This will combine the user's Google Calendar events with task scheduling suggestions to optimize schedule for each day of the week. The schedule printed in terminal will have a task (from this program), event (pre-existing from the user's Google Calendar), or free time ("FREE")

## Motivation
The goal of this program is to help users (including busy college students!) organize their to-do lists and complete all tasks in a productive and efficient manner.


## External contributors
I used Claude to write the code for this project. I first prompted it to help me write the code to import Google Calendar information from the user, explaining the what I would use this for. Then I asked it to help me gather user task inputs, and specified what details to ask for (task name, category, due date, etc.) as well as to validate the user inputs so that they are usable in the prioty score generator. Then, I asked it to help me create a formula to compute a priority score for each task, and return a ranked list of tasks. I also asked Claude to collect user preferences on when they are most productive, when they want to do tasks, days they want to keep lighter/less busy, etc. Finally, I used AI to integrate together information from the user's Google Calendar, their inputted tasks (and associated priority scores), and user preferences to output a weekly schedule. 
