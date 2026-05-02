def get_valid_int(prompt, error_msg, min_val=None, max_val=None):
    while True:
        try:
            value = int(input(prompt))
            if (min_val is not None and value < min_val) or \
               (max_val is not None and value > max_val):
                print(error_msg)
            else:
                return value
        except ValueError:
            print(error_msg)


def get_valid_float(prompt, error_msg):
    while True:
        try:
            value = float(input(prompt))
            return value
        except ValueError:
            print(error_msg)


def get_tasks():
    tasks = []

    while True:
        name = input("Enter task name (press Enter to finish): ").strip()
        if name == "":
            break

        category = input("Enter category (class, errands, exercise, etc.): ").strip()

        due_in_days = get_valid_int(
            "Enter due in days: ",
            "Due in days must be a non-negative integer.",
            0
        )

        estimated_time = get_valid_float(
            "Enter estimated time (in hours): ",
            "Estimated time must be a number."
        )

        difficulty = get_valid_int(
            "Enter difficulty (1-5): ",
            "Difficulty must be an integer between 1 and 5.",
            1, 5
        )

        importance = get_valid_int(
            "Enter importance (1-5): ",
            "Importance must be an integer between 1 and 5.",
            1, 5
        )


        task = {
            "name": name,
            "category": category,
            "due_in_days": due_in_days,
            "estimated_time": estimated_time,
            "difficulty": difficulty,
            "importance": importance
        }

        tasks.append(task)
        print("Task added!\n")

    return tasks


def calculate_priority(task):
    urgency = max(0, 7 - task["due_in_days"])

    score = (
        4 * task["importance"]
        + 3 * urgency
        + 2 * task["difficulty"]
        - task["estimated_time"]
    )

    return score


def sort_tasks_by_priority(tasks):
    # add priority score
    for task in tasks:
        task["priority_score"] = calculate_priority(task)

    # sort tasks (highest score first)
    sorted_tasks = sorted(
        tasks,
        key=lambda task: task["priority_score"],
        reverse=True
    )

    # dictionary of dictionaries (in sorted order)
    prioritized_tasks = {}

    for i in range(len(sorted_tasks)):
        prioritized_tasks[f"task_{i + 1}"] = sorted_tasks[i]

    return prioritized_tasks


# ---- MAIN PROGRAM ----

tasks = get_tasks()

prioritized_tasks = sort_tasks_by_priority(tasks)

print("\nTasks in priority order:")
for key in prioritized_tasks:
    print(f"{key}: {prioritized_tasks[key]}")

