"""
Smart Routine Generator - Flask Application
CS50x Final Project

Step 3B: Automated timetable generation, transaction rollback, and routine display.
"""

import os
import sqlite3
from typing import Any

from flask import Flask, flash, g, has_request_context, redirect, render_template, request, session, url_for

from database import DATABASE_PATH, get_db_connection
from scheduler import DAYS, PERIODS, generate_schedule

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
        """
        SELECT s.id, s.code, s.name,
               (SELECT COUNT(*) FROM teacher_subjects ts WHERE ts.subject_id = s.id) AS teacher_count,
               (SELECT COUNT(*) FROM section_requirements sr WHERE sr.subject_id = s.id) AS requirement_count,
               (SELECT COUNT(*) FROM timetable_entries te WHERE te.subject_id = s.id) AS timetable_count
        FROM subjects s
        ORDER BY s.code ASC;
        """
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

    # Query scheduled timetable entries count per teacher
    teacher_tt_rows = db.execute(
        "SELECT teacher_id, COUNT(*) AS count FROM timetable_entries GROUP BY teacher_id;"
    ).fetchall()
    teacher_tt_map = {row["teacher_id"]: row["count"] for row in teacher_tt_rows}

    # Build teacher objects with embedded qualifications and timetable counts
    teachers = []
    for t in teachers_rows:
        t_dict = dict(t)
        t_subs = teacher_qualifications.get(t["id"], [])
        t_dict["subjects"] = t_subs
        t_dict["subject_ids"] = [s["id"] for s in t_subs]
        t_dict["timetable_count"] = teacher_tt_map.get(t["id"], 0)
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

    raw_tab = request.args.get("tab", "subjects").strip().lower()
    active_tab = raw_tab if raw_tab in ("subjects", "teachers", "sections") else "subjects"
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

    return redirect(url_for("setup", tab="subjects"))


@app.route("/subjects/<int:subject_id>/edit", methods=["POST"])
@app.route("/subjects/edit", methods=["POST"])
def edit_subject(subject_id: int | None = None):
    """
    POST route to edit an existing academic subject.
    Validates required fields, auto-uppercases code, prevents duplicate code collisions,
    and updates the subject record using a parameterized UPDATE query.
    """
    if subject_id is None:
        subject_id_raw = request.form.get("subject_id", "").strip()
        try:
            subject_id = int(subject_id_raw)
        except ValueError:
            flash("Invalid subject ID.", "danger")
            return redirect(url_for("setup", tab="subjects"))

    code = request.form.get("code", "").strip().upper()
    name = request.form.get("name", "").strip()

    # 1. Validation for missing fields
    if not code or not name:
        flash("Both Subject Code and Subject Name are required.", "danger")
        return redirect(url_for("setup", tab="subjects"))

    db = get_db()

    # 2. Verify that the subject exists
    existing = db.execute("SELECT id, code, name FROM subjects WHERE id = ?;", (subject_id,)).fetchone()
    if not existing:
        flash("Subject not found.", "danger")
        return redirect(url_for("setup", tab="subjects"))

    # 3. Prevent duplicate code collision with any other subject
    duplicate = db.execute(
        "SELECT id, code FROM subjects WHERE code = ? AND id != ?;",
        (code, subject_id),
    ).fetchone()
    if duplicate:
        flash(f"A subject with code '{code}' already exists. Please choose a unique code.", "danger")
        return redirect(url_for("setup", tab="subjects"))

    old_code = existing["code"]

    # 4. Parameterized UPDATE query in a transaction
    try:
        with db:
            db.execute(
                "UPDATE subjects SET code = ?, name = ? WHERE id = ?;",
                (code, name, subject_id),
            )
        flash(f"Subject '{old_code}' updated successfully to '{code} - {name}'!", "success")
    except sqlite3.IntegrityError:
        flash(f"A subject with code '{code}' already exists. Please choose a unique code.", "danger")
    except Exception as e:
        db.rollback()
        flash(f"Database error while updating subject: {str(e)}", "danger")

    return redirect(url_for("setup", tab="subjects"))


@app.route("/subjects/<int:subject_id>/delete", methods=["POST"])
@app.route("/subjects/delete", methods=["POST"])
def delete_subject(subject_id: int | None = None):
    """
    POST route to delete an existing academic subject.
    Safely inspects and removes all dependent records in a single atomic transaction:
      1. timetable_entries referencing this subject
      2. section_requirements referencing this subject
      3. teacher_subjects referencing this subject
      4. the subject itself
    Never leaves orphaned records and marks the timetable outdated if affected.
    """
    if subject_id is None:
        subject_id_raw = request.form.get("subject_id", "").strip()
        try:
            subject_id = int(subject_id_raw)
        except ValueError:
            flash("Invalid subject ID.", "danger")
            return redirect(url_for("setup", tab="subjects"))

    db = get_db()

    # 1. Verify subject exists
    subject = db.execute("SELECT id, code, name FROM subjects WHERE id = ?;", (subject_id,)).fetchone()
    if not subject:
        flash("Subject not found.", "danger")
        return redirect(url_for("setup", tab="subjects"))

    code = subject["code"]
    name = subject["name"]

    # 2. Explicitly inspect dependent records
    teacher_count = db.execute(
        "SELECT COUNT(*) AS count FROM teacher_subjects WHERE subject_id = ?;", (subject_id,)
    ).fetchone()["count"]
    req_count = db.execute(
        "SELECT COUNT(*) AS count FROM section_requirements WHERE subject_id = ?;", (subject_id,)
    ).fetchone()["count"]
    tt_count = db.execute(
        "SELECT COUNT(*) AS count FROM timetable_entries WHERE subject_id = ?;", (subject_id,)
    ).fetchone()["count"]

    # 3. Explicit safe transaction deleting related records in dependency order
    try:
        with db:
            if tt_count > 0:
                db.execute("DELETE FROM timetable_entries WHERE subject_id = ?;", (subject_id,))
            if req_count > 0:
                db.execute("DELETE FROM section_requirements WHERE subject_id = ?;", (subject_id,))
            if teacher_count > 0:
                db.execute("DELETE FROM teacher_subjects WHERE subject_id = ?;", (subject_id,))
            db.execute("DELETE FROM subjects WHERE id = ?;", (subject_id,))

        if teacher_count > 0 or req_count > 0 or tt_count > 0:
            details = []
            if teacher_count:
                details.append(f"{teacher_count} teacher qualification(s)")
            if req_count:
                details.append(f"{req_count} section requirement(s)")
            if tt_count:
                details.append(f"{tt_count} timetable entry/entries")
            flash(
                f"Subject '{code} - {name}' deleted successfully along with associated records ({', '.join(details)}).",
                "warning",
            )
            # Mark timetable outdated if timetable or requirements were impacted
            if tt_count > 0 or req_count > 0:
                session["timetable_outdated"] = True
                reasons = session.get("outdated_reasons", [])
                reasons.append(
                    f"Subject '{code}' was deleted, removing {tt_count} scheduled slot(s) and {req_count} requirement(s)."
                )
                session["outdated_reasons"] = reasons
        else:
            flash(f"Subject '{code} - {name}' deleted successfully.", "success")

    except Exception as e:
        db.rollback()
        flash(f"Database error while deleting subject '{code}': {str(e)}", "danger")

    return redirect(url_for("setup", tab="subjects"))


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


@app.route("/teachers/<int:teacher_id>/edit", methods=["POST"])
@app.route("/teachers/edit", methods=["POST"])
def edit_teacher(teacher_id: int | None = None):
    """
    POST route to edit an existing faculty member's details and qualifications.
    Validates name (required), processes optional email, prevents email collisions,
    synchronizes qualified subjects in an atomic transaction,
    and marks the timetable outdated if any scheduled routine periods are invalidated.
    """
    if teacher_id is None:
        teacher_id_raw = request.form.get("teacher_id", "").strip()
        try:
            teacher_id = int(teacher_id_raw)
        except ValueError:
            flash("Invalid teacher ID.", "danger")
            return redirect(url_for("setup", tab="teachers"))

    name = request.form.get("name", "").strip()
    raw_email = request.form.get("email", "").strip()
    email = raw_email if raw_email else None
    subject_ids_raw = request.form.getlist("subject_ids")

    # 1. Server-side validation: Teacher name is required
    if not name:
        flash("Teacher name is required.", "danger")
        return redirect(url_for("setup", tab="teachers"))

    db = get_db()

    # 2. Verify that the teacher exists
    existing = db.execute("SELECT id, name, email FROM teachers WHERE id = ?;", (teacher_id,)).fetchone()
    if not existing:
        flash("Teacher not found.", "danger")
        return redirect(url_for("setup", tab="teachers"))

    # 3. Check for unique email collision if email provided
    if email:
        dup_email = db.execute(
            "SELECT id, name FROM teachers WHERE LOWER(email) = LOWER(?) AND id != ?;",
            (email, teacher_id),
        ).fetchone()
        if dup_email:
            flash(f"A teacher with email '{email}' already exists. Please choose a unique email.", "danger")
            return redirect(url_for("setup", tab="teachers"))

    # 4. Parse and validate subject_ids
    selected_subject_ids = []
    for s_raw in subject_ids_raw:
        try:
            selected_subject_ids.append(int(s_raw))
        except (ValueError, TypeError):
            pass
    selected_subject_ids = list(dict.fromkeys(selected_subject_ids))

    if selected_subject_ids:
        placeholders = ",".join("?" for _ in selected_subject_ids)
        found_count = db.execute(
            f"SELECT COUNT(*) AS c FROM subjects WHERE id IN ({placeholders});",
            selected_subject_ids,
        ).fetchone()["c"]
        if found_count != len(selected_subject_ids):
            flash("One or more selected subjects do not exist.", "danger")
            return redirect(url_for("setup", tab="teachers"))

    # 5. Check if qualification change affects existing scheduled timetable slots
    current_quals = {
        r["subject_id"]
        for r in db.execute(
            "SELECT subject_id FROM teacher_subjects WHERE teacher_id = ?;", (teacher_id,)
        ).fetchall()
    }
    removed_quals = current_quals - set(selected_subject_ids)
    affected_slots = 0
    if removed_quals:
        placeholders = ",".join("?" for _ in removed_quals)
        affected_slots = db.execute(
            f"SELECT COUNT(*) AS c FROM timetable_entries WHERE teacher_id = ? AND subject_id IN ({placeholders});",
            [teacher_id, *removed_quals],
        ).fetchone()["c"]

    # 6. Execute atomic update transaction
    try:
        with db:
            db.execute(
                "UPDATE teachers SET name = ?, email = ? WHERE id = ?;",
                (name, email, teacher_id),
            )
            # Re-synchronize qualifications
            db.execute("DELETE FROM teacher_subjects WHERE teacher_id = ?;", (teacher_id,))
            for s_id in selected_subject_ids:
                db.execute(
                    "INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?);",
                    (teacher_id, s_id),
                )

        flash(f"Teacher '{name}' updated successfully!", "success")

        # Mark timetable outdated if removed qualifications invalidate scheduled timetable entries
        if affected_slots > 0:
            session["timetable_outdated"] = True
            reasons = session.get("outdated_reasons", [])
            reasons.append(
                f"Teacher '{name}' was unqualified for one or more subjects scheduled in {affected_slots} timetable period(s)."
            )
            session["outdated_reasons"] = reasons

    except sqlite3.IntegrityError:
        flash(f"A teacher with email '{email}' already exists. Please choose a unique email.", "danger")
    except Exception as e:
        db.rollback()
        flash(f"Database error while updating teacher: {str(e)}", "danger")

    return redirect(url_for("setup", tab="teachers"))


@app.route("/teachers/<int:teacher_id>/delete", methods=["POST"])
@app.route("/teachers/delete", methods=["POST"])
def delete_teacher(teacher_id: int | None = None):
    """
    POST route to delete an existing faculty member.
    Safely inspects and removes all dependent records in a single atomic transaction:
      1. timetable_entries referencing this teacher
      2. teacher_subjects referencing this teacher
      3. the teacher record itself
    Never leaves orphaned records and marks the timetable outdated if affected.
    """
    if teacher_id is None:
        teacher_id_raw = request.form.get("teacher_id", "").strip()
        try:
            teacher_id = int(teacher_id_raw)
        except ValueError:
            flash("Invalid teacher ID.", "danger")
            return redirect(url_for("setup", tab="teachers"))

    db = get_db()

    # 1. Verify that the teacher exists
    teacher = db.execute("SELECT id, name, email FROM teachers WHERE id = ?;", (teacher_id,)).fetchone()
    if not teacher:
        flash("Teacher not found.", "danger")
        return redirect(url_for("setup", tab="teachers"))

    name = teacher["name"]

    # 2. Inspect dependent records
    qual_count = db.execute(
        "SELECT COUNT(*) AS count FROM teacher_subjects WHERE teacher_id = ?;", (teacher_id,)
    ).fetchone()["count"]
    tt_count = db.execute(
        "SELECT COUNT(*) AS count FROM timetable_entries WHERE teacher_id = ?;", (teacher_id,)
    ).fetchone()["count"]

    # 3. Explicit safe transaction deleting related records in dependency order
    try:
        with db:
            if tt_count > 0:
                db.execute("DELETE FROM timetable_entries WHERE teacher_id = ?;", (teacher_id,))
            if qual_count > 0:
                db.execute("DELETE FROM teacher_subjects WHERE teacher_id = ?;", (teacher_id,))
            db.execute("DELETE FROM teachers WHERE id = ?;", (teacher_id,))

        if qual_count > 0 or tt_count > 0:
            details = []
            if qual_count:
                details.append(f"{qual_count} qualification(s)")
            if tt_count:
                details.append(f"{tt_count} timetable slot(s)")
            flash(
                f"Teacher '{name}' deleted successfully along with associated records ({', '.join(details)}).",
                "warning",
            )
            if tt_count > 0:
                session["timetable_outdated"] = True
                reasons = session.get("outdated_reasons", [])
                reasons.append(
                    f"Teacher '{name}' was deleted, removing {tt_count} scheduled timetable period(s)."
                )
                session["outdated_reasons"] = reasons
        else:
            flash(f"Teacher '{name}' deleted successfully.", "success")

    except Exception as e:
        db.rollback()
        flash(f"Database error while deleting teacher '{name}': {str(e)}", "danger")

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


def get_timetable_sync_status(db):
    """
    Check whether the saved timetable in timetable_entries matches
    the current section_requirements and teacher qualifications.

    Returns a dict with:
        is_generated (bool): True if at least 1 entry is in timetable_entries.
        total_entries (int): Count of scheduled timetable entries.
        total_required (int): Cumulative periods required across all sections.
        is_outdated (bool): True if the saved timetable is out of sync with current setup.
        outdated_reasons (list[str]): Explanations for why the routine is outdated.
        section_status (dict): Maps section_id -> {'required': int, 'scheduled': int, 'is_outdated': bool}
    """
    total_entries = db.execute("SELECT COUNT(*) AS count FROM timetable_entries;").fetchone()["count"]
    total_required = db.execute("SELECT COALESCE(SUM(weekly_periods), 0) AS total FROM section_requirements;").fetchone()["total"]

    if total_entries == 0:
        return {
            "is_generated": False,
            "total_entries": 0,
            "total_required": total_required,
            "is_outdated": False,
            "outdated_reasons": [],
            "section_status": {},
        }

    # Section-level and requirement-level comparisons
    req_rows = db.execute(
        "SELECT section_id, subject_id, weekly_periods FROM section_requirements;"
    ).fetchall()
    req_map = {(r["section_id"], r["subject_id"]): r["weekly_periods"] for r in req_rows}

    sched_rows = db.execute(
        "SELECT section_id, subject_id, COUNT(*) AS cnt FROM timetable_entries GROUP BY section_id, subject_id;"
    ).fetchall()
    sched_map = {(r["section_id"], r["subject_id"]): r["cnt"] for r in sched_rows}

    # Check for subjects required but lacking qualified teachers
    unqualified_rows = db.execute(
        """
        SELECT sec.name AS section_name, sub.code AS subject_code
        FROM section_requirements sr
        JOIN sections sec ON sr.section_id = sec.id
        JOIN subjects sub ON sr.subject_id = sub.id
        WHERE sr.subject_id NOT IN (SELECT DISTINCT subject_id FROM teacher_subjects);
        """
    ).fetchall()

    # Check for scheduled entries whose teachers are no longer qualified
    invalid_teachers = db.execute(
        """
        SELECT te.id
        FROM timetable_entries te
        LEFT JOIN teacher_subjects ts ON te.teacher_id = ts.teacher_id AND te.subject_id = ts.subject_id
        WHERE ts.teacher_id IS NULL;
        """
    ).fetchall()

    outdated_reasons = []
    is_outdated = False

    if has_request_context() and session.get("timetable_outdated"):
        is_outdated = True
        for r in session.get("outdated_reasons", []):
            if r not in outdated_reasons:
                outdated_reasons.append(r)
        if not session.get("outdated_reasons"):
            outdated_reasons.append(
                "Academic setup was modified after timetable generation. Please regenerate the routine."
            )

    if req_map != sched_map:
        is_outdated = True
        outdated_reasons.append(
            f"Requirements mismatch: {total_entries} period(s) currently scheduled, but {total_required} period(s) are required by the academic setup."
        )

    if unqualified_rows:
        is_outdated = True
        for u in unqualified_rows:
            outdated_reasons.append(
                f"Subject '{u['subject_code']}' required by Section '{u['section_name']}' has no qualified teacher assigned."
            )

    if invalid_teachers:
        is_outdated = True
        outdated_reasons.append(
            f"{len(invalid_teachers)} scheduled period(s) have teachers who are no longer qualified for the subject."
        )

    # Per-section summary
    section_status = {}
    sections = db.execute("SELECT id FROM sections;").fetchall()
    for sec in sections:
        sec_id = sec["id"]
        sec_req = sum(r["weekly_periods"] for r in req_rows if r["section_id"] == sec_id)
        sec_sched = sum(r["cnt"] for r in sched_rows if r["section_id"] == sec_id)
        section_status[sec_id] = {
            "required": sec_req,
            "scheduled": sec_sched,
            "is_outdated": (sec_req != sec_sched),
        }

    return {
        "is_generated": True,
        "total_entries": total_entries,
        "total_required": total_required,
        "is_outdated": is_outdated,
        "outdated_reasons": outdated_reasons,
        "section_status": section_status,
    }


@app.route("/routine", methods=["GET"])
def routine():
    """
    Timetable Routine route (GET /routine).
    Retrieves all sections and the published timetable entries from the database,
    structures the entries into day-by-period grids for each section,
    determines if the timetable is outdated compared to the current configuration,
    and displays the routine screen.
    """
    db = get_db()

    # Retrieve all sections ordered by name
    sections = db.execute("SELECT id, name FROM sections ORDER BY name ASC;").fetchall()

    # Retrieve all timetable entries joined with section, teacher, and subject details
    entries = db.execute(
        """
        SELECT te.id, te.section_id, te.teacher_id, te.subject_id, te.day_of_week, te.period,
               sec.name AS section_name, t.name AS teacher_name,
               sub.code AS subject_code, sub.name AS subject_name
        FROM timetable_entries te
        JOIN sections sec ON te.section_id = sec.id
        JOIN teachers t ON te.teacher_id = t.id
        JOIN subjects sub ON te.subject_id = sub.id
        ORDER BY sec.name ASC, te.day_of_week ASC, te.period ASC;
        """
    ).fetchall()

    sync_status = get_timetable_sync_status(db)
    last_generation_error = session.get("last_generation_error")

    # Build a lookup grid per section: section_id -> {day -> {period -> slot_info}}
    section_timetables: dict[int, Any] = {}
    for sec in sections:
        sec_id = sec["id"]
        sec_info = sync_status["section_status"].get(sec_id, {"required": 0, "scheduled": 0, "is_outdated": False})
        section_timetables[sec_id] = {
            "section": sec,
            "grid": {day: {period: None for period in PERIODS} for day in DAYS},
            "total_classes": 0,
            "required_classes": sec_info["required"],
            "is_outdated": sec_info["is_outdated"],
        }

    for row in entries:
        sec_id = row["section_id"]
        day = row["day_of_week"]
        period = row["period"]
        if sec_id in section_timetables and day in section_timetables[sec_id]["grid"]:
            section_timetables[sec_id]["grid"][day][period] = {
                "subject_code": row["subject_code"],
                "subject_name": row["subject_name"],
                "teacher_name": row["teacher_name"],
            }
            section_timetables[sec_id]["total_classes"] += 1

    return render_template(
        "routine.html",
        sections=sections,
        entries=entries,
        section_timetables=section_timetables,
        days=DAYS,
        periods=PERIODS,
        sync_status=sync_status,
        last_generation_error=last_generation_error,
    )


@app.route("/routine/generate", methods=["POST"])
@app.route("/generate-routine", methods=["POST"])
def generate_routine():
    """
    POST route to generate and publish an automated timetable.
    1. Loads the database configuration and invokes generate_schedule().
    2. If scheduling fails, stores the error in session, flashes error, and halts (saving no partial entries).
    3. If scheduling succeeds, atomically replaces the existing timetable_entries
       inside a database transaction. If any error occurs, rolls back cleanly.
    """
    db = get_db()

    # 1. Generate schedule using scheduler module
    result = generate_schedule(conn=db)

    # Support both ScheduleResult object and dictionary formats safely
    is_success = result.get("success") if isinstance(result, dict) else getattr(result, "success", False)
    error_msg = result.get("error") if isinstance(result, dict) else getattr(result, "error", "Unknown error")
    schedule_entries = (
        (result.get("entries") or result.get("schedule"))
        if isinstance(result, dict)
        else (getattr(result, "entries", None) or getattr(result, "schedule", []))
    )

    if not is_success:
        session["last_generation_error"] = error_msg
        flash(f"Timetable generation failed: {error_msg}", "danger")
        return redirect(url_for("routine"))

    # 2. Save the complete schedule atomically inside a database transaction
    try:
        with db:
            # Clear previous entries to prevent duplication
            db.execute("DELETE FROM timetable_entries;")

            # Insert all newly scheduled entries
            for entry in schedule_entries:
                db.execute(
                    """
                    INSERT INTO timetable_entries (section_id, teacher_id, subject_id, day_of_week, period)
                    VALUES (?, ?, ?, ?, ?);
                    """,
                    (
                        entry["section_id"],
                        entry["teacher_id"],
                        entry["subject_id"],
                        entry["day_of_week"],
                        entry["period"],
                    ),
                )

        # Clear any prior generation error and outdated flags upon success
        session.pop("last_generation_error", None)
        session.pop("timetable_outdated", None)
        session.pop("outdated_reasons", None)

        flash(
            f"Timetable successfully generated and published! ({len(schedule_entries)} total class periods scheduled).",
            "success",
        )
    except Exception as e:
        db.rollback()
        session["last_generation_error"] = str(e)
        flash(f"Database error while saving timetable: {str(e)}", "danger")

    return redirect(url_for("routine"))


if __name__ == "__main__":
    # Start the local development server on port 5000 with debug enabled
    app.run(debug=True, port=5000)
