"""
Smart Routine Generator - Flask Application
CS50x Final Project

Step 2D: Section management and weekly subject requirements.
"""

import os
import sqlite3
from flask import Flask, flash, g, redirect, render_template, request, url_for

from database import DATABASE_PATH, get_db_connection

app = Flask(__name__)
# Secret key for session management and flash messages
app.secret_key = os.environ.get("SECRET_KEY", "smart-routine-generator-dev-key")


def get_db():
    """
    Obtain a database connection for the current web request.
    Reuses get_db_connection() from database.py to ensure:
      1. PRAGMA foreign_keys = ON is executed.
      2. row_factory is set to sqlite3.Row for dictionary-like column access.
      Supports app.config['DATABASE_PATH'] for test isolation.
    """
    if "db" not in g:
        db_path = app.config.get("DATABASE_PATH", DATABASE_PATH)
        g.db = get_db_connection(db_path)
    return g.db


@app.teardown_appcontext
def close_db(error=None):
    """
    Automatically called when the application context is torn down (end of request).
    Safely closes the database connection if one was opened during this request.
    """
    db = g.pop("db", None)
    if db is not None:
        db.close()


@app.route("/")
def index():
    """
    Dashboard route (GET /).
    Queries summary counts from the database and passes them to templates/index.html.
    """
    db = get_db()
    counts = {
        "subjects": db.execute("SELECT COUNT(*) AS count FROM subjects;").fetchone()["count"],
        "teachers": db.execute("SELECT COUNT(*) AS count FROM teachers;").fetchone()["count"],
        "sections": db.execute("SELECT COUNT(*) AS count FROM sections;").fetchone()["count"],
        "entries": db.execute("SELECT COUNT(*) AS count FROM timetable_entries;").fetchone()["count"],
    }
    return render_template("index.html", counts=counts)


@app.route("/setup", methods=["GET"])
def setup():
    """
    Academic Setup route (GET /setup).
    Retrieves all registered subjects, teachers, and sections along with their
    respective qualifications and weekly period requirements.
    """
    db = get_db()
    subjects = db.execute(
        "SELECT id, code, name FROM subjects ORDER BY code ASC;"
    ).fetchall()

    # Retrieve all teachers ordered by name
    teachers_rows = db.execute(
        "SELECT id, name, email FROM teachers ORDER BY name ASC;"
    ).fetchall()

    # Retrieve all teacher-subject qualifications joined with subject details
    qual_rows = db.execute(
        """
        SELECT ts.teacher_id, s.id AS subject_id, s.code AS subject_code, s.name AS subject_name
        FROM teacher_subjects ts
        JOIN subjects s ON ts.subject_id = s.id
        ORDER BY s.code ASC;
        """
    ).fetchall()

    # Map qualifications to their respective teacher
    teacher_qualifications = {}
    for row in qual_rows:
        teacher_qualifications.setdefault(row["teacher_id"], []).append({
            "id": row["subject_id"],
            "code": row["subject_code"],
            "name": row["subject_name"],
        })

    # Build teacher objects with embedded qualifications
    teachers = []
    for t in teachers_rows:
        t_dict = dict(t)
        t_dict["subjects"] = teacher_qualifications.get(t["id"], [])
        teachers.append(t_dict)

    # Retrieve all sections ordered by name
    sections_rows = db.execute(
        "SELECT id, name FROM sections ORDER BY name ASC;"
    ).fetchall()

    # Retrieve all section requirements joined with subject details
    req_rows = db.execute(
        """
        SELECT sr.id AS requirement_id, sr.section_id, sr.subject_id, sr.weekly_periods,
               s.code AS subject_code, s.name AS subject_name
        FROM section_requirements sr
        JOIN subjects s ON sr.subject_id = s.id
        ORDER BY s.code ASC;
        """
    ).fetchall()

    # Map requirements to their respective section
    section_requirements_map = {}
    for row in req_rows:
        section_requirements_map.setdefault(row["section_id"], []).append({
            "id": row["requirement_id"],
            "subject_id": row["subject_id"],
            "subject_code": row["subject_code"],
            "name": row["subject_name"],
            "weekly_periods": row["weekly_periods"],
        })

    # Build section objects with embedded requirements and total periods
    sections = []
    for sec in sections_rows:
        sec_dict = dict(sec)
        sec_reqs = section_requirements_map.get(sec["id"], [])
        sec_dict["requirements"] = sec_reqs
        sec_dict["total_periods"] = sum(r["weekly_periods"] for r in sec_reqs)
        sections.append(sec_dict)

    active_tab = request.args.get("tab", "subjects")
    return render_template(
        "setup.html",
        subjects=subjects,
        teachers=teachers,
        sections=sections,
        active_tab=active_tab,
    )


@app.route("/subjects", methods=["POST"])
def add_subject():
    """
    POST route to add a new academic subject.
    Validates inputs, executes a parameterized INSERT query,
    handles unique code collisions gracefully, and redirects back to setup.
    """
    code = request.form.get("code", "").strip().upper()
    name = request.form.get("name", "").strip()

    # 1. Validation for missing fields
    if not code or not name:
        flash("Both Subject Code and Subject Name are required.", "danger")
        return redirect(url_for("setup"))

    db = get_db()
    # 2. Parameterized SQL query with duplicate handling
    try:
        db.execute(
            "INSERT INTO subjects (code, name) VALUES (?, ?);",
            (code, name),
        )
        db.commit()
        flash(f"Subject '{code} - {name}' added successfully!", "success")
    except sqlite3.IntegrityError:
        flash(f"A subject with code '{code}' already exists. Please choose a unique code.", "danger")

    return redirect(url_for("setup"))


@app.route("/teachers", methods=["POST"])
def add_teacher():
    """
    POST route to add a new faculty member (teacher).
    Validates name (required), processes optional email, executes parameterized SQL INSERT,
    handles unique email constraint violations gracefully, and redirects back to setup.
    """
    name = request.form.get("name", "").strip()
    raw_email = request.form.get("email", "").strip()
    email = raw_email if raw_email else None

    # 1. Server-side validation: Teacher name is required
    if not name:
        flash("Teacher name is required.", "danger")
        return redirect(url_for("setup", tab="teachers"))

    db = get_db()
    # 2. Parameterized SQL INSERT to prevent SQL injection
    try:
        db.execute(
            "INSERT INTO teachers (name, email) VALUES (?, ?);",
            (name, email),
        )
        db.commit()
        flash(f"Teacher '{name}' added successfully!", "success")
    except sqlite3.IntegrityError:
        flash(f"A teacher with email '{email}' already exists. Please choose a unique email.", "danger")

    return redirect(url_for("setup", tab="teachers"))


@app.route("/qualifications", methods=["POST"])
def add_qualification():
    """
    POST route to assign subject qualifications to a teacher.
    Accepts teacher_id and one or more subject_ids.
    Validates inputs, prevents duplicate qualifications, executes parameterized SQL queries,
    and returns informative flash feedback.
    """
    teacher_id_raw = request.form.get("teacher_id", "").strip()
    subject_ids_raw = request.form.getlist("subject_ids")
    # Support 'subject_id' fallback for single-select or testing compatibility
    if not subject_ids_raw and request.form.get("subject_id"):
        single_sub = request.form.get("subject_id", "").strip()
        if single_sub:
            subject_ids_raw = [single_sub]

    # 1. Validate teacher selection
    if not teacher_id_raw:
        flash("Please select a teacher.", "danger")
        return redirect(url_for("setup", tab="teachers"))

    try:
        teacher_id = int(teacher_id_raw)
    except ValueError:
        flash("Invalid teacher selected.", "danger")
        return redirect(url_for("setup", tab="teachers"))

    # 2. Validate subject selection
    if not subject_ids_raw:
        flash("Please select at least one subject.", "danger")
        return redirect(url_for("setup", tab="teachers"))

    subject_ids = []
    for s_id_raw in subject_ids_raw:
        try:
            subject_ids.append(int(s_id_raw))
        except (ValueError, TypeError):
            flash("Invalid subject selection.", "danger")
            return redirect(url_for("setup", tab="teachers"))

    # Deduplicate subject_ids in the request payload while preserving order
    subject_ids = list(dict.fromkeys(subject_ids))

    db = get_db()

    # 3. Verify that the teacher exists
    teacher = db.execute("SELECT id, name FROM teachers WHERE id = ?;", (teacher_id,)).fetchone()
    if not teacher:
        flash("Selected teacher not found.", "danger")
        return redirect(url_for("setup", tab="teachers"))

    teacher_name = teacher["name"]

    # 4. Verify that all selected subjects exist
    placeholders = ",".join("?" for _ in subject_ids)
    found_subjects = db.execute(
        f"SELECT id, code FROM subjects WHERE id IN ({placeholders});",
        subject_ids,
    ).fetchall()

    if len(found_subjects) != len(subject_ids):
        flash("One or more selected subjects do not exist.", "danger")
        return redirect(url_for("setup", tab="teachers"))

    subject_code_map = {row["id"]: row["code"] for row in found_subjects}

    # 5. Fetch existing qualifications for this teacher to prevent duplicates
    existing_rows = db.execute(
        "SELECT subject_id FROM teacher_subjects WHERE teacher_id = ?;",
        (teacher_id,),
    ).fetchall()
    existing_subject_ids = {row["subject_id"] for row in existing_rows}

    added_codes = []
    duplicate_codes = []

    for s_id in subject_ids:
        s_code = subject_code_map[s_id]
        if s_id in existing_subject_ids:
            duplicate_codes.append(s_code)
        else:
            try:
                db.execute(
                    "INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?);",
                    (teacher_id, s_id),
                )
                added_codes.append(s_code)
            except sqlite3.IntegrityError:
                duplicate_codes.append(s_code)

    if added_codes:
        db.commit()

    # 6. Informative flash messages
    if added_codes and not duplicate_codes:
        flash(f"Successfully qualified {teacher_name} for {', '.join(added_codes)}.", "success")
    elif added_codes and duplicate_codes:
        flash(
            f"Qualified {teacher_name} for {', '.join(added_codes)}. Note: Already qualified for {', '.join(duplicate_codes)}.",
            "warning",
        )
    else:
        flash(
            f"{teacher_name} is already qualified for {', '.join(duplicate_codes)}.",
            "warning",
        )

    return redirect(url_for("setup", tab="teachers"))


@app.route("/sections", methods=["POST"])
def add_section():
    """
    POST route to add a new student section (cohort).
    Validates name (required), executes parameterized SQL INSERT,
    handles unique section name collisions gracefully, and redirects back to setup.
    """
    name = request.form.get("name", "").strip()

    # 1. Server-side validation: Section name is required
    if not name:
        flash("Section name is required.", "danger")
        return redirect(url_for("setup", tab="sections"))

    db = get_db()
    # 2. Parameterized SQL INSERT to prevent SQL injection
    try:
        db.execute(
            "INSERT INTO sections (name) VALUES (?);",
            (name,),
        )
        db.commit()
        flash(f"Section '{name}' added successfully!", "success")
    except sqlite3.IntegrityError:
        flash(f"A section with name '{name}' already exists. Please choose a unique name.", "danger")

    return redirect(url_for("setup", tab="sections"))


@app.route("/requirements", methods=["POST"])
@app.route("/section-requirements", methods=["POST"])
def add_requirement():
    """
    POST route to assign weekly subject requirements to a student section.
    Validates section, subject, and weekly period constraints (1-30 periods,
    and cumulative maximum of 30 periods per section).
    Prevents duplicates and executes parameterized SQL INSERT queries.
    """
    section_id_raw = request.form.get("section_id", "").strip()
    subject_id_raw = request.form.get("subject_id", "").strip()
    weekly_periods_raw = request.form.get("weekly_periods", "").strip()

    # 1. Validate section selection
    if not section_id_raw:
        flash("Please select a section.", "danger")
        return redirect(url_for("setup", tab="sections"))

    try:
        section_id = int(section_id_raw)
    except ValueError:
        flash("Invalid section selected.", "danger")
        return redirect(url_for("setup", tab="sections"))

    # 2. Validate subject selection
    if not subject_id_raw:
        flash("Please select a subject.", "danger")
        return redirect(url_for("setup", tab="sections"))

    try:
        subject_id = int(subject_id_raw)
    except ValueError:
        flash("Invalid subject selected.", "danger")
        return redirect(url_for("setup", tab="sections"))

    # 3. Validate weekly periods value
    if not weekly_periods_raw:
        flash("Weekly periods count is required.", "danger")
        return redirect(url_for("setup", tab="sections"))

    try:
        weekly_periods = int(weekly_periods_raw)
    except ValueError:
        flash("Weekly periods must be a valid integer.", "danger")
        return redirect(url_for("setup", tab="sections"))

    if weekly_periods < 1 or weekly_periods > 30:
        flash("Weekly periods must be between 1 and 30.", "danger")
        return redirect(url_for("setup", tab="sections"))

    db = get_db()

    # 4. Verify that the section exists
    section = db.execute("SELECT id, name FROM sections WHERE id = ?;", (section_id,)).fetchone()
    if not section:
        flash("Selected section not found.", "danger")
        return redirect(url_for("setup", tab="sections"))

    section_name = section["name"]

    # 5. Verify that the subject exists
    subject = db.execute("SELECT id, code, name FROM subjects WHERE id = ?;", (subject_id,)).fetchone()
    if not subject:
        flash("Selected subject not found.", "danger")
        return redirect(url_for("setup", tab="sections"))

    subject_code = subject["code"]

    # 6. Check for duplicate requirement
    existing_req = db.execute(
        "SELECT id, weekly_periods FROM section_requirements WHERE section_id = ? AND subject_id = ?;",
        (section_id, subject_id),
    ).fetchone()

    if existing_req:
        flash(
            f"Section '{section_name}' is already assigned {existing_req['weekly_periods']} periods for '{subject_code}'.",
            "warning",
        )
        return redirect(url_for("setup", tab="sections"))

    # 7. Check cumulative 30-period limit for the section
    current_total = db.execute(
        "SELECT COALESCE(SUM(weekly_periods), 0) AS total FROM section_requirements WHERE section_id = ?;",
        (section_id,),
    ).fetchone()["total"]

    if current_total + weekly_periods > 30:
        remaining = 30 - current_total
        flash(
            f"Cannot add {weekly_periods} periods. Section '{section_name}' already has {current_total}/30 periods allocated. Only {remaining} period(s) remaining.",
            "danger",
        )
        return redirect(url_for("setup", tab="sections"))

    # 8. Insert new requirement via parameterized query
    try:
        db.execute(
            "INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, ?);",
            (section_id, subject_id, weekly_periods),
        )
        db.commit()
        new_total = current_total + weekly_periods
        flash(
            f"Assigned {weekly_periods} weekly periods of '{subject_code}' to Section '{section_name}' (Total: {new_total}/30 periods).",
            "success",
        )
    except sqlite3.IntegrityError:
        flash(
            f"Could not save requirement: A conflict occurred for Section '{section_name}' and '{subject_code}'.",
            "danger",
        )

    return redirect(url_for("setup", tab="sections"))


@app.route("/routine")
def routine():
    """
    Placeholder route for Routine Generation and timetable viewing.
    """
    return render_template("routine.html")


if __name__ == "__main__":
    # Start the local development server on port 5000 with debug enabled
    app.run(debug=True, port=5000)
