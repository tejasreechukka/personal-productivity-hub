import sqlite3
from pathlib import Path
from datetime import date, timedelta

import pandas as pd
import streamlit as st


# ---------- APP CONFIGURATION ----------

st.set_page_config(
    page_title="My Productivity Hub",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "productivity.db"

CATEGORIES = [
    "University",
    "Data Skills",
    "Career",
    "Portfolio",
    "Networking",
    "Wellbeing",
    "Personal",
]

st.markdown("""
<style>
.stApp {
    background: #0b1120;
    color: #e5e7eb;
}
[data-testid="stSidebar"] {
    background: #111827;
}
[data-testid="stMetric"] {
    background: #172033;
    border: 1px solid #273449;
    padding: 16px;
    border-radius: 12px;
}
div.stButton > button {
    border-radius: 9px;
}
.block-container {
    padding-top: 2rem;
    padding-bottom: 3rem;
    max-width: 1200px;
}
</style>
""", unsafe_allow_html=True)


# ---------- DATABASE ----------

def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def execute(sql, params=()):
    with connect() as conn:
        conn.execute(sql, params)


def query(sql, params=()):
    with connect() as conn:
        return conn.execute(sql, params).fetchall()


def init_db():
    with connect() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS habits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS checkins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            habit_id INTEGER NOT NULL,
            check_date TEXT NOT NULL,
            UNIQUE(habit_id, check_date),
            FOREIGN KEY(habit_id) REFERENCES habits(id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Not started',
            notes TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            project_id INTEGER,
            due_date TEXT,
            priority INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'To do',
            created_at TEXT NOT NULL,
            FOREIGN KEY(project_id) REFERENCES projects(id)
                ON DELETE SET NULL
        );
        """)

        # Add starter habits only when the database is new.
        count = conn.execute(
            "SELECT COUNT(*) FROM habits"
        ).fetchone()[0]

        if count == 0:
            starters = [
                ("Study for 30 minutes", "University"),
                ("Practise Python or SQL", "Data Skills"),
                ("Complete one career action", "Career"),
                ("Work on one portfolio project", "Portfolio"),
                ("Send one networking message", "Networking"),
                ("Move or do yoga for 10 minutes", "Wellbeing"),
                ("Plan tomorrow", "Personal"),
            ]
            conn.executemany(
                "INSERT INTO habits (name, category) VALUES (?, ?)",
                starters,
            )


init_db()
today = date.today()
today_str = today.isoformat()


# ---------- HELPER FUNCTIONS ----------

def add_checkin(habit_id, day):
    execute(
        "INSERT OR IGNORE INTO checkins (habit_id, check_date) "
        "VALUES (?, ?)",
        (habit_id, day),
    )


def remove_checkin(habit_id, day):
    execute(
        "DELETE FROM checkins WHERE habit_id=? AND check_date=?",
        (habit_id, day),
    )


def active_habits():
    return query(
        "SELECT * FROM habits WHERE active=1 ORDER BY id"
    )


def completion_for(day):
    habits = active_habits()
    if not habits:
        return 0, 0, 0

    completed = query(
        "SELECT COUNT(*) AS n FROM checkins c "
        "JOIN habits h ON h.id=c.habit_id "
        "WHERE c.check_date=? AND h.active=1",
        (day,),
    )[0]["n"]

    total = len(habits)
    return completed, total, round(completed / total * 100)


def project_options():
    return query("SELECT id, name FROM projects ORDER BY name")


# ---------- SIDEBAR NAVIGATION ----------

st.sidebar.title("⚡ Productivity Hub")
st.sidebar.caption("Small steps. Consistent progress.")

page = st.sidebar.radio(
    "Navigate",
    ["Dashboard", "Habits", "Projects & Tasks", "Insights"],
)

st.sidebar.divider()
st.sidebar.caption(f"Today: {today.strftime('%A, %d %B %Y')}")
st.sidebar.caption("Your data is stored locally.")


# ---------- DASHBOARD ----------

if page == "Dashboard":
    st.title("Your daily command centre")
    st.caption("Focus on progress, not perfection.")

    selected_day = st.date_input(
        "Check-in date",
        value=today,
        key="dashboard_date",
    )
    day_str = selected_day.isoformat()

    completed, total, percentage = completion_for(day_str)

    open_tasks = query(
        "SELECT * FROM tasks WHERE status != 'Done' "
        "ORDER BY priority DESC, "
        "CASE WHEN due_date IS NULL THEN 1 ELSE 0 END, due_date "
        "LIMIT 100"
    )

    done_tasks = query(
        "SELECT COUNT(*) AS n FROM tasks WHERE status='Done'"
    )[0]["n"]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Habits completed", f"{completed}/{total}")
    m2.metric("Daily progress", f"{percentage}%")
    m3.metric("Open tasks", len(open_tasks))
    m4.metric("Tasks completed", done_tasks)

    st.progress(percentage / 100 if total else 0)

    left, right = st.columns([1.2, 1])

    with left:
        st.subheader("Today's habits")

        habits = active_habits()
        for habit in habits:
            done = bool(query(
                "SELECT id FROM checkins "
                "WHERE habit_id=? AND check_date=?",
                (habit["id"], day_str),
            ))

            checked = st.checkbox(
                f"{habit['name']}  ·  {habit['category']}",
                value=done,
                key=f"check_{habit['id']}_{day_str}",
            )

            if checked != done:
                if checked:
                    add_checkin(habit["id"], day_str)
                else:
                    remove_checkin(habit["id"], day_str)
                st.rerun()

        if not habits:
            st.info("Add your first habit in the Habits section.")

    with right:
        st.subheader("Your next actions")

        priorities = query(
            "SELECT t.*, p.name AS project_name "
            "FROM tasks t LEFT JOIN projects p "
            "ON t.project_id=p.id "
            "WHERE t.status != 'Done' AND t.priority=1 "
            "ORDER BY t.due_date LIMIT 3"
        )

        if priorities:
            for task in priorities:
                due = f" · Due {task['due_date']}" if task["due_date"] else ""
                project = (
                    f" · {task['project_name']}"
                    if task["project_name"] else ""
                )
                st.write(f"**{task['title']}**{due}{project}")
        else:
            st.info("No priority tasks yet. Add up to three important tasks.")

        st.subheader("Add a quick task")

        with st.form("quick_task_form", clear_on_submit=True):
            task_title = st.text_input("What needs to be done?")
            due = st.date_input("Due date", value=today, key="quick_due")
            priority = st.checkbox("Mark as a priority")
            submitted = st.form_submit_button(
                "Add task", use_container_width=True
            )

            if submitted:
                if task_title.strip():
                    execute(
                        "INSERT INTO tasks "
                        "(title, due_date, priority, created_at) "
                        "VALUES (?, ?, ?, ?)",
                        (
                            task_title.strip(),
                            due.isoformat(),
                            int(priority),
                            today_str,
                        ),
                    )
                    st.success("Task added.")
                    st.rerun()
                else:
                    st.warning("Enter a task name first.")

    st.divider()
    st.subheader("Tasks to work on")

    if open_tasks:
        for task in open_tasks:
            col1, col2 = st.columns([4, 1])
            with col1:
                flag = "⭐ " if task["priority"] else ""
                due = f" · Due {task['due_date']}" if task["due_date"] else ""
                st.write(f"{flag}{task['title']} — {task['status']}{due}")
            with col2:
                if st.button("Complete", key=f"complete_{task['id']}"):
                    execute(
                        "UPDATE tasks SET status='Done' WHERE id=?",
                        (task["id"],),
                    )
                    st.rerun()
    else:
        st.info("You're clear! Add a task whenever something comes up.")


# ---------- HABITS ----------

elif page == "Habits":
    st.title("Habit manager")
    st.caption("Keep your routine realistic and flexible.")

    with st.expander("＋ Add a new habit", expanded=False):
        with st.form("add_habit_form", clear_on_submit=True):
            name = st.text_input("Habit name")
            category = st.selectbox("Category", CATEGORIES)
            submitted = st.form_submit_button("Create habit")

            if submitted:
                if name.strip():
                    execute(
                        "INSERT INTO habits (name, category) VALUES (?, ?)",
                        (name.strip(), category),
                    )
                    st.success("Habit created.")
                    st.rerun()
                else:
                    st.warning("Enter a habit name.")

    st.subheader("Your active habits")

    for habit in active_habits():
        c1, c2, c3 = st.columns([3, 2, 1])
        c1.write(f"**{habit['name']}**")
        c2.caption(habit["category"])

        if c3.button("Archive", key=f"archive_{habit['id']}"):
            execute(
                "UPDATE habits SET active=0 WHERE id=?",
                (habit["id"],),
            )
            st.rerun()

    archived = query(
        "SELECT * FROM habits WHERE active=0 ORDER BY id"
    )

    if archived:
        with st.expander("Archived habits"):
            for habit in archived:
                c1, c2 = st.columns([3, 1])
                c1.write(habit["name"])
                if c2.button("Restore", key=f"restore_{habit['id']}"):
                    execute(
                        "UPDATE habits SET active=1 WHERE id=?",
                        (habit["id"],),
                    )
                    st.rerun()

    st.divider()
    st.subheader("Check-in history")

    history_day = st.date_input(
        "Choose a day to review",
        value=today,
        key="history_day",
    )
    day_str = history_day.isoformat()
    history_habits = query(
        "SELECT h.id, h.name, h.category, "
        "CASE WHEN c.id IS NULL THEN 0 ELSE 1 END AS done "
        "FROM habits h LEFT JOIN checkins c "
        "ON h.id=c.habit_id AND c.check_date=? "
        "WHERE h.active=1 ORDER BY h.id",
        (day_str,),
    )

    if history_habits:
        done_count = sum(h["done"] for h in history_habits)
        st.write(
            f"{done_count} of {len(history_habits)} habits completed "
            f"on {history_day.strftime('%d %b %Y')}."
        )
        for habit in history_habits:
            mark = "✅" if habit["done"] else "⬜"
            st.write(f"{mark} {habit['name']} — {habit['category']}")


# ---------- PROJECTS AND TASKS ----------

elif page == "Projects & Tasks":
    st.title("Projects & tasks")
    st.caption("Every big goal needs a clear next action.")

    with st.expander("＋ Create a project", expanded=False):
        with st.form("project_form", clear_on_submit=True):
            project_name = st.text_input("Project name")
            category = st.selectbox(
                "Project category", CATEGORIES, key="project_category"
            )
            notes = st.text_area("Goal or notes")
            submitted = st.form_submit_button("Create project")

            if submitted:
                if project_name.strip():
                    execute(
                        "INSERT INTO projects "
                        "(name, category, notes, created_at) "
                        "VALUES (?, ?, ?, ?)",
                        (
                            project_name.strip(),
                            category,
                            notes.strip(),
                            today_str,
                        ),
                    )
                    st.success("Project created.")
                    st.rerun()
                else:
                    st.warning("Enter a project name.")

    projects = project_options()
    project_map = {p["name"]: p["id"] for p in projects}

    st.subheader("Your projects")

    if projects:
        for project in query("SELECT * FROM projects ORDER BY id DESC"):
            with st.container(border=True):
                c1, c2 = st.columns([3, 2])
                c1.markdown(f"**{project['name']}**")
                c1.caption(f"{project['category']} · {project['notes']}")
                statuses = [
                    "Not started", "In progress", "On hold", "Completed"
                ]
                current = (
                    project["status"]
                    if project["status"] in statuses
                    else "Not started"
                )
                new_status = c2.selectbox(
                    "Status",
                    statuses,
                    index=statuses.index(current),
                    key=f"project_status_{project['id']}",
                )
                if new_status != project["status"]:
                    execute(
                        "UPDATE projects SET status=? WHERE id=?",
                        (new_status, project["id"]),
                    )
                    st.rerun()

                if st.button(
                    "Delete project",
                    key=f"delete_project_{project['id']}",
                ):
                    execute(
                        "DELETE FROM projects WHERE id=?",
                        (project["id"],),
                    )
                    st.rerun()
    else:
        st.info("Create a project to start organizing your interests.")

    st.divider()
    st.subheader("Add a task to a project")

    with st.form("project_task_form", clear_on_submit=True):
        task_title = st.text_input("Task description")

        project_names = ["No project"] + list(project_map.keys())
        selected_project = st.selectbox("Project", project_names)
        due = st.date_input("Due date", value=today, key="project_task_due")
        priority = st.checkbox("One of my top priorities")
        submitted = st.form_submit_button("Add task")

        if submitted:
            if task_title.strip():
                project_id = (
                    project_map[selected_project]
                    if selected_project != "No project" else None
                )
                execute(
                    "INSERT INTO tasks "
                    "(title, project_id, due_date, priority, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        task_title.strip(),
                        project_id,
                        due.isoformat(),
                        int(priority),
                        today_str,
                    ),
                )
                st.success("Task added.")
                st.rerun()
            else:
                st.warning("Enter a task description.")

    st.divider()
    st.subheader("Manage all tasks")

    tasks = query(
        "SELECT t.*, p.name AS project_name "
        "FROM tasks t LEFT JOIN projects p ON t.project_id=p.id "
        "ORDER BY CASE WHEN t.status='Done' THEN 1 ELSE 0 END, "
        "t.priority DESC, t.due_date"
    )

    if tasks:
        for task in tasks:
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 2, 1])
                c1.write(f"**{task['title']}**")
                c1.caption(
                    f"{task['project_name'] or 'General'} · "
                    f"{task['due_date'] or 'No due date'}"
                )

                task_statuses = ["To do", "In progress", "Done"]
                current = (
                    task["status"]
                    if task["status"] in task_statuses else "To do"
                )
                new_status = c2.selectbox(
                    "Task status",
                    task_statuses,
                    index=task_statuses.index(current),
                    key=f"task_status_{task['id']}",
                )
                if new_status != task["status"]:
                    execute(
                        "UPDATE tasks SET status=? WHERE id=?",
                        (new_status, task["id"]),
                    )
                    st.rerun()

                if c3.button("Delete", key=f"delete_task_{task['id']}"):
                    execute("DELETE FROM tasks WHERE id=?", (task["id"],))
                    st.rerun()
    else:
        st.info("No tasks yet. Add your first next action above.")


# ---------- WEEKLY INSIGHTS ----------

elif page == "Insights":
    st.title("Your progress")
    st.caption("Review your consistency without judging yourself.")

    end_day = date.today()
    start_day = end_day - timedelta(days=6)
    days = [
        (start_day + timedelta(days=i)).isoformat()
        for i in range(7)
    ]

    habits = active_habits()
    rows = []

    for day in days:
        completed, total, pct = completion_for(day)
        rows.append({
            "Date": date.fromisoformat(day).strftime("%a %d"),
            "Completed": completed,
            "Available": total,
            "Progress (%)": pct,
        })

    df = pd.DataFrame(rows)

    if habits:
        st.subheader("Daily habit completion")
        st.line_chart(
            df.set_index("Date")[["Progress (%)"]],
            y="Progress (%)",
        )
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("Add habits to start building your history.")

    st.subheader("Task summary")

    task_counts = query(
        "SELECT status, COUNT(*) AS n FROM tasks GROUP BY status"
    )
    if task_counts:
        task_df = pd.DataFrame([
            {"Status": r["status"], "Tasks": r["n"]}
            for r in task_counts
        ])
        st.bar_chart(task_df.set_index("Status"))
        st.dataframe(task_df, use_container_width=True, hide_index=True)
    else:
        st.info("Add tasks to see your task summary.")

    st.caption(
        "Weekly history covers the last 7 calendar days, including today. "
        "Archived habits are excluded from the active-habit percentage."
    )