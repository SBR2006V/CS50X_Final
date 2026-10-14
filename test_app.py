"""
Tests for Flask application routes, subject management, teacher management, qualifications, and section requirements (Step 2B, 2C & 2D).
Uses Python's built-in unittest and Flask's test_client.
"""

import gc
from pathlib import Path
import unittest

from app import app
from database import get_db_connection, init_db

TEST_DB_PATH = Path(__file__).resolve().parent / "test_routine.db"


class TestAppRoutesAndSubjects(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Configure Flask application for testing with an isolated database
        app.config["TESTING"] = True
        app.config["DATABASE_PATH"] = TEST_DB_PATH
        if TEST_DB_PATH.exists():
            try:
                TEST_DB_PATH.unlink()
            except PermissionError:
                pass
        init_db(TEST_DB_PATH)

    @classmethod
    def tearDownClass(cls):
        gc.collect()
        if TEST_DB_PATH.exists():
            try:
                TEST_DB_PATH.unlink()
            except PermissionError:
                pass

    def setUp(self):
        self.client = app.test_client()
        # Clean subject, teacher, section, and mapping tables before each test for test isolation
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                conn.execute("DELETE FROM timetable_entries;")
                conn.execute("DELETE FROM section_requirements;")
                conn.execute("DELETE FROM teacher_subjects;")
                conn.execute("DELETE FROM sections;")
                conn.execute("DELETE FROM teachers;")
                conn.execute("DELETE FROM subjects;")
        finally:
            conn.close()

    def test_dashboard_route_loads(self):
        """GET / should return 200 OK and render the Academic Dashboard."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Academic Dashboard", response.data)
        self.assertIn(b"Subjects", response.data)

    def test_setup_page_loads_and_displays_form_and_table(self):
        """GET /setup should return 200 OK with the subject creation form and table."""
        response = self.client.get("/setup")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Add New Subject", response.data)
        self.assertIn(b"Subject Code", response.data)
        self.assertIn(b"Subject Name", response.data)
        self.assertIn(b"Registered Subjects", response.data)
        self.assertIn(b"No subjects added yet", response.data)

    def test_add_subject_success(self):
        """POST /subjects with valid data should save to DB, redirect, and display success flash."""
        payload = {"code": "cs101", "name": "Introduction to Computer Science"}
        response = self.client.post("/subjects", data=payload, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        # Verify success flash message and table presence (code auto-uppercased to CS101)
        self.assertIn(b"added successfully!", response.data)
        self.assertIn(b"CS101", response.data)
        self.assertIn(b"Introduction to Computer Science", response.data)

        # Verify database record directly
        conn = get_db_connection(TEST_DB_PATH)
        try:
            row = conn.execute("SELECT * FROM subjects WHERE code = 'CS101';").fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["name"], "Introduction to Computer Science")
        finally:
            conn.close()

    def test_add_subject_missing_code(self):
        """POST /subjects with an empty code should fail validation and show an error message."""
        payload = {"code": "   ", "name": "Calculus I"}
        response = self.client.post("/subjects", data=payload, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Both Subject Code and Subject Name are required.", response.data)

        # Verify nothing was added to the database
        conn = get_db_connection(TEST_DB_PATH)
        try:
            count = conn.execute("SELECT COUNT(*) AS total FROM subjects;").fetchone()["total"]
            self.assertEqual(count, 0)
        finally:
            conn.close()

    def test_add_subject_missing_name(self):
        """POST /subjects with an empty name should fail validation and show an error message."""
        payload = {"code": "MATH101", "name": "  "}
        response = self.client.post("/subjects", data=payload, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Both Subject Code and Subject Name are required.", response.data)

        # Verify nothing was added to the database
        conn = get_db_connection(TEST_DB_PATH)
        try:
            count = conn.execute("SELECT COUNT(*) AS total FROM subjects;").fetchone()["total"]
            self.assertEqual(count, 0)
        finally:
            conn.close()

    def test_add_subject_duplicate_code(self):
        """POST /subjects with an existing code should trigger a duplicate error message."""
        # Insert initial subject
        self.client.post(
            "/subjects",
            data={"code": "PHY101", "name": "General Physics I"},
            follow_redirects=True,
        )

        # Attempt to insert a second subject with the same code (case-insensitive check)
        response = self.client.post(
            "/subjects",
            data={"code": "phy101", "name": "Alternative Physics"},
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"already exists", response.data)

        # Verify only one subject exists in database
        conn = get_db_connection(TEST_DB_PATH)
        try:
            rows = conn.execute("SELECT * FROM subjects WHERE code = 'PHY101';").fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["name"], "General Physics I")
        finally:
            conn.close()

    # =========================================================================
    # Step 2C Tests: Teacher Management & Subject Qualifications
    # =========================================================================

    def test_setup_page_displays_teacher_forms_and_table(self):
        """GET /setup should render Teacher form, Qualification form, and Registered Teachers table."""
        response = self.client.get("/setup")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Add New Teacher", response.data)
        self.assertIn(b"Teacher Name", response.data)
        self.assertIn(b"Email Address", response.data)
        self.assertIn(b"Assign Subject Qualifications", response.data)
        self.assertIn(b"Registered Teachers", response.data)
        self.assertIn(b"No teachers registered yet", response.data)

    def test_add_teacher_success_with_email(self):
        """POST /teachers with name and email should save to DB, redirect, and display success flash."""
        payload = {"name": "Dr. Ada Lovelace", "email": "ada@example.edu"}
        response = self.client.post("/teachers", data=payload, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"added successfully!", response.data)
        self.assertIn(b"Dr. Ada Lovelace", response.data)
        self.assertIn(b"ada@example.edu", response.data)

        # Direct database verification
        conn = get_db_connection(TEST_DB_PATH)
        try:
            row = conn.execute("SELECT * FROM teachers WHERE email = 'ada@example.edu';").fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["name"], "Dr. Ada Lovelace")
            self.assertEqual(row["email"], "ada@example.edu")
        finally:
            conn.close()

    def test_add_teacher_success_without_email(self):
        """POST /teachers without an email should succeed with NULL in database."""
        payload = {"name": "Prof. Alan Turing", "email": "   "}
        response = self.client.post("/teachers", data=payload, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"added successfully!", response.data)
        self.assertIn(b"Prof. Alan Turing", response.data)
        self.assertIn(b"Not provided", response.data)

        conn = get_db_connection(TEST_DB_PATH)
        try:
            row = conn.execute("SELECT * FROM teachers WHERE name = 'Prof. Alan Turing';").fetchone()
            self.assertIsNotNone(row)
            self.assertIsNone(row["email"])
        finally:
            conn.close()

    def test_add_teacher_missing_name(self):
        """POST /teachers with missing name should fail validation and show error message."""
        payload = {"name": "   ", "email": "ada@example.edu"}
        response = self.client.post("/teachers", data=payload, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Teacher name is required.", response.data)

        # Verify nothing was added
        conn = get_db_connection(TEST_DB_PATH)
        try:
            count = conn.execute("SELECT COUNT(*) AS total FROM teachers;").fetchone()["total"]
            self.assertEqual(count, 0)
        finally:
            conn.close()

    def test_add_teacher_duplicate_email(self):
        """POST /teachers with an already registered email should trigger duplicate error."""
        self.client.post(
            "/teachers",
            data={"name": "Teacher One", "email": "unique@example.edu"},
            follow_redirects=True,
        )

        response = self.client.post(
            "/teachers",
            data={"name": "Teacher Two", "email": "unique@example.edu"},
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"already exists", response.data)

        conn = get_db_connection(TEST_DB_PATH)
        try:
            rows = conn.execute("SELECT * FROM teachers WHERE email = 'unique@example.edu';").fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["name"], "Teacher One")
        finally:
            conn.close()

    def test_add_qualification_single_subject_success(self):
        """POST /qualifications with a valid teacher and one subject should save mapping."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                t_id = conn.execute("INSERT INTO teachers (name, email) VALUES ('Grace Hopper', 'grace@navy.mil');").lastrowid
                s_id = conn.execute("INSERT INTO subjects (code, name) VALUES ('CS101', 'Intro to CS');").lastrowid
        finally:
            conn.close()

        response = self.client.post(
            "/qualifications",
            data={"teacher_id": str(t_id), "subject_ids": [str(s_id)]},
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Successfully qualified Grace Hopper", response.data)
        self.assertIn(b"CS101", response.data)

        conn = get_db_connection(TEST_DB_PATH)
        try:
            mapping = conn.execute(
                "SELECT * FROM teacher_subjects WHERE teacher_id = ? AND subject_id = ?;",
                (t_id, s_id),
            ).fetchone()
            self.assertIsNotNone(mapping)
        finally:
            conn.close()

    def test_add_qualification_multiple_subjects_success(self):
        """POST /qualifications with multiple subjects should qualify teacher for all selected subjects."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                t_id = conn.execute("INSERT INTO teachers (name) VALUES ('Prof. Euler');").lastrowid
                s1_id = conn.execute("INSERT INTO subjects (code, name) VALUES ('MATH101', 'Calculus I');").lastrowid
                s2_id = conn.execute("INSERT INTO subjects (code, name) VALUES ('MATH102', 'Linear Algebra');").lastrowid
        finally:
            conn.close()

        response = self.client.post(
            "/qualifications",
            data={"teacher_id": str(t_id), "subject_ids": [str(s1_id), str(s2_id)]},
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Successfully qualified Prof. Euler", response.data)
        self.assertIn(b"MATH101", response.data)
        self.assertIn(b"MATH102", response.data)

        conn = get_db_connection(TEST_DB_PATH)
        try:
            rows = conn.execute(
                "SELECT subject_id FROM teacher_subjects WHERE teacher_id = ? ORDER BY subject_id ASC;",
                (t_id,),
            ).fetchall()
            self.assertEqual(len(rows), 2)
            self.assertEqual([r["subject_id"] for r in rows], [s1_id, s2_id])
        finally:
            conn.close()

    def test_add_qualification_missing_teacher(self):
        """POST /qualifications with missing teacher should fail validation."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                s_id = conn.execute("INSERT INTO subjects (code, name) VALUES ('BIO101', 'Biology');").lastrowid
        finally:
            conn.close()

        response = self.client.post(
            "/qualifications",
            data={"teacher_id": "", "subject_ids": [str(s_id)]},
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Please select a teacher.", response.data)

    def test_add_qualification_missing_subjects(self):
        """POST /qualifications with missing subjects should fail validation."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                t_id = conn.execute("INSERT INTO teachers (name) VALUES ('Prof. Turing');").lastrowid
        finally:
            conn.close()

        response = self.client.post(
            "/qualifications",
            data={"teacher_id": str(t_id)},
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Please select at least one subject.", response.data)

    def test_add_qualification_invalid_ids(self):
        """POST /qualifications with non-existent or malformed IDs should show clear error."""
        # Non-existent teacher ID
        response = self.client.post(
            "/qualifications",
            data={"teacher_id": "9999", "subject_ids": ["1"]},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Selected teacher not found.", response.data)

        # Malformed non-integer teacher ID
        response = self.client.post(
            "/qualifications",
            data={"teacher_id": "invalid", "subject_ids": ["1"]},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Invalid teacher selected.", response.data)

    def test_add_qualification_duplicate_prevention(self):
        """POST /qualifications with duplicate subject should prevent duplicate DB entry and warn user."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                t_id = conn.execute("INSERT INTO teachers (name) VALUES ('Dr. Ada');").lastrowid
                s_id = conn.execute("INSERT INTO subjects (code, name) VALUES ('CS101', 'Intro to CS');").lastrowid
                conn.execute("INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?);", (t_id, s_id))
        finally:
            conn.close()

        # Attempt to re-qualify with duplicate subject
        response = self.client.post(
            "/qualifications",
            data={"teacher_id": str(t_id), "subject_ids": [str(s_id)]},
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"already qualified", response.data)

        # Verify only 1 row exists in database
        conn = get_db_connection(TEST_DB_PATH)
        try:
            count = conn.execute(
                "SELECT COUNT(*) AS total FROM teacher_subjects WHERE teacher_id = ? AND subject_id = ?;",
                (t_id, s_id),
            ).fetchone()["total"]
            self.assertEqual(count, 1)
        finally:
            conn.close()

    def test_add_qualification_mixed_new_and_duplicate(self):
        """POST /qualifications with a mix of new and duplicate subjects should save new and warn for duplicates."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                t_id = conn.execute("INSERT INTO teachers (name) VALUES ('Dr. Ada');").lastrowid
                s1_id = conn.execute("INSERT INTO subjects (code, name) VALUES ('CS101', 'Intro to CS');").lastrowid
                s2_id = conn.execute("INSERT INTO subjects (code, name) VALUES ('CS102', 'Data Structures');").lastrowid
                conn.execute("INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?);", (t_id, s1_id))
        finally:
            conn.close()

        # Submit s1 (already qualified) and s2 (new qualification)
        response = self.client.post(
            "/qualifications",
            data={"teacher_id": str(t_id), "subject_ids": [str(s1_id), str(s2_id)]},
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"CS102", response.data)
        self.assertIn(b"already qualified", response.data.lower())

        conn = get_db_connection(TEST_DB_PATH)
        try:
            rows = conn.execute(
                "SELECT subject_id FROM teacher_subjects WHERE teacher_id = ? ORDER BY subject_id ASC;",
                (t_id,),
            ).fetchall()
            self.assertEqual(len(rows), 2)
            self.assertEqual([r["subject_id"] for r in rows], [s1_id, s2_id])
        finally:
            conn.close()

    def test_setup_displays_teachers_and_qualifications(self):
        """GET /setup should display teachers and their assigned qualification badges."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                t_id = conn.execute("INSERT INTO teachers (name, email) VALUES ('Prof. Turing', 'turing@cam.ac.uk');").lastrowid
                s1_id = conn.execute("INSERT INTO subjects (code, name) VALUES ('CS101', 'Intro to CS');").lastrowid
                s2_id = conn.execute("INSERT INTO subjects (code, name) VALUES ('MATH101', 'Calculus');").lastrowid
                conn.execute("INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?);", (t_id, s1_id))
                conn.execute("INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?);", (t_id, s2_id))
        finally:
            conn.close()

        response = self.client.get("/setup?tab=teachers")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Prof. Turing", response.data)
        self.assertIn(b"turing@cam.ac.uk", response.data)
        self.assertIn(b"CS101", response.data)
        self.assertIn(b"MATH101", response.data)

    def test_dashboard_teacher_count_updates(self):
        """GET / should dynamically reflect the registered teacher count on the dashboard."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                conn.execute("INSERT INTO teachers (name) VALUES ('Prof. Alpha');")
                conn.execute("INSERT INTO teachers (name) VALUES ('Prof. Beta');")
        finally:
            conn.close()

        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Teachers", response.data)
        self.assertIn(b">2<", response.data)

    # =========================================================================
    # Step 2D Tests: Section Management & Weekly Subject Requirements
    # =========================================================================

    def test_setup_page_displays_sections_forms_and_table(self):
        """GET /setup should render Section form, Requirement form, and Registered Sections table."""
        # 1. When empty, renders Section form, Requirement card with prerequisites info, and empty section table
        response = self.client.get("/setup?tab=sections")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Add New Section", response.data)
        self.assertIn(b"Section Name", response.data)
        self.assertIn(b"Assign Subject Requirement", response.data)
        self.assertIn(b"Registered Sections &amp; Requirements", response.data)
        self.assertIn(b"No sections registered yet", response.data)

        # 2. When section and subject exist, requirement form displays weekly periods input
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                conn.execute("INSERT INTO sections (name) VALUES ('CSE-A');")
                conn.execute("INSERT INTO subjects (code, name) VALUES ('CS101', 'Intro to CS');")
        finally:
            conn.close()

        res_with_data = self.client.get("/setup?tab=sections")
        self.assertEqual(res_with_data.status_code, 200)
        self.assertIn(b"Weekly Periods", res_with_data.data)

    def test_add_section_success(self):
        """POST /sections with valid name should save to DB, redirect, and display success flash."""
        payload = {"name": "CSE-A"}
        response = self.client.post("/sections", data=payload, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"added successfully!", response.data)
        self.assertIn(b"CSE-A", response.data)

        # Direct database verification
        conn = get_db_connection(TEST_DB_PATH)
        try:
            row = conn.execute("SELECT * FROM sections WHERE name = 'CSE-A';").fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["name"], "CSE-A")
        finally:
            conn.close()

    def test_add_section_missing_name(self):
        """POST /sections with missing name should fail validation and show error message."""
        payload = {"name": "   "}
        response = self.client.post("/sections", data=payload, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Section name is required.", response.data)

        conn = get_db_connection(TEST_DB_PATH)
        try:
            count = conn.execute("SELECT COUNT(*) AS total FROM sections;").fetchone()["total"]
            self.assertEqual(count, 0)
        finally:
            conn.close()

    def test_add_section_duplicate_name(self):
        """POST /sections with duplicate name should trigger unique constraint error."""
        self.client.post(
            "/sections",
            data={"name": "CSE-A"},
            follow_redirects=True,
        )

        response = self.client.post(
            "/sections",
            data={"name": "CSE-A"},
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"already exists", response.data)

        conn = get_db_connection(TEST_DB_PATH)
        try:
            rows = conn.execute("SELECT * FROM sections WHERE name = 'CSE-A';").fetchall()
            self.assertEqual(len(rows), 1)
        finally:
            conn.close()

    def test_add_requirement_success(self):
        """POST /requirements with valid section, subject, and weekly_periods should save mapping."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                sec_id = conn.execute("INSERT INTO sections (name) VALUES ('CSE-A');").lastrowid
                sub_id = conn.execute("INSERT INTO subjects (code, name) VALUES ('CS101', 'Intro to CS');").lastrowid
        finally:
            conn.close()

        response = self.client.post(
            "/requirements",
            data={"section_id": str(sec_id), "subject_id": str(sub_id), "weekly_periods": "4"},
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Assigned 4 weekly periods", response.data)
        self.assertIn(b"CS101", response.data)
        self.assertIn(b"CSE-A", response.data)

        conn = get_db_connection(TEST_DB_PATH)
        try:
            row = conn.execute(
                "SELECT * FROM section_requirements WHERE section_id = ? AND subject_id = ?;",
                (sec_id, sub_id),
            ).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["weekly_periods"], 4)
        finally:
            conn.close()

    def test_add_requirement_missing_fields(self):
        """POST /requirements with missing required fields should fail validation."""
        # Missing section_id
        res1 = self.client.post(
            "/requirements",
            data={"section_id": "", "subject_id": "1", "weekly_periods": "4"},
            follow_redirects=True,
        )
        self.assertEqual(res1.status_code, 200)
        self.assertIn(b"Please select a section.", res1.data)

        # Missing subject_id
        res2 = self.client.post(
            "/requirements",
            data={"section_id": "1", "subject_id": "", "weekly_periods": "4"},
            follow_redirects=True,
        )
        self.assertEqual(res2.status_code, 200)
        self.assertIn(b"Please select a subject.", res2.data)

        # Missing weekly_periods
        res3 = self.client.post(
            "/requirements",
            data={"section_id": "1", "subject_id": "1", "weekly_periods": ""},
            follow_redirects=True,
        )
        self.assertEqual(res3.status_code, 200)
        self.assertIn(b"Weekly periods count is required.", res3.data)

    def test_add_requirement_invalid_period_bounds(self):
        """POST /requirements with periods outside 1-30 should fail server-side validation."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                sec_id = conn.execute("INSERT INTO sections (name) VALUES ('CSE-B');").lastrowid
                sub_id = conn.execute("INSERT INTO subjects (code, name) VALUES ('MATH101', 'Calculus');").lastrowid
        finally:
            conn.close()

        # 0 periods is invalid (< 1)
        res_zero = self.client.post(
            "/requirements",
            data={"section_id": str(sec_id), "subject_id": str(sub_id), "weekly_periods": "0"},
            follow_redirects=True,
        )
        self.assertEqual(res_zero.status_code, 200)
        self.assertIn(b"Weekly periods must be between 1 and 30.", res_zero.data)

        # 31 periods is invalid (> 30)
        res_overflow = self.client.post(
            "/requirements",
            data={"section_id": str(sec_id), "subject_id": str(sub_id), "weekly_periods": "31"},
            follow_redirects=True,
        )
        self.assertEqual(res_overflow.status_code, 200)
        self.assertIn(b"Weekly periods must be between 1 and 30.", res_overflow.data)

        # Non-integer period
        res_alpha = self.client.post(
            "/requirements",
            data={"section_id": str(sec_id), "subject_id": str(sub_id), "weekly_periods": "five"},
            follow_redirects=True,
        )
        self.assertEqual(res_alpha.status_code, 200)
        self.assertIn(b"Weekly periods must be a valid integer.", res_alpha.data)

    def test_add_requirement_nonexistent_ids(self):
        """POST /requirements with non-existent foreign keys should fail validation."""
        # Non-existent section
        res_sec = self.client.post(
            "/requirements",
            data={"section_id": "9999", "subject_id": "1", "weekly_periods": "4"},
            follow_redirects=True,
        )
        self.assertEqual(res_sec.status_code, 200)
        self.assertIn(b"Selected section not found.", res_sec.data)

        # Non-existent subject
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                sec_id = conn.execute("INSERT INTO sections (name) VALUES ('CSE-C');").lastrowid
        finally:
            conn.close()

        res_sub = self.client.post(
            "/requirements",
            data={"section_id": str(sec_id), "subject_id": "9999", "weekly_periods": "4"},
            follow_redirects=True,
        )
        self.assertEqual(res_sub.status_code, 200)
        self.assertIn(b"Selected subject not found.", res_sub.data)

    def test_add_requirement_duplicate_prevention(self):
        """POST /requirements with a subject already assigned to section should warn and prevent duplicate entry."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                sec_id = conn.execute("INSERT INTO sections (name) VALUES ('CSE-A');").lastrowid
                sub_id = conn.execute("INSERT INTO subjects (code, name) VALUES ('CS101', 'Intro to CS');").lastrowid
                conn.execute(
                    "INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, 4);",
                    (sec_id, sub_id),
                )
        finally:
            conn.close()

        # Attempt duplicate insertion
        response = self.client.post(
            "/requirements",
            data={"section_id": str(sec_id), "subject_id": str(sub_id), "weekly_periods": "5"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"already assigned 4 periods", response.data)

        # Verify database still only has 1 record with original 4 periods
        conn = get_db_connection(TEST_DB_PATH)
        try:
            rows = conn.execute(
                "SELECT * FROM section_requirements WHERE section_id = ? AND subject_id = ?;",
                (sec_id, sub_id),
            ).fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["weekly_periods"], 4)
        finally:
            conn.close()

    def test_add_requirement_exceeds_30_period_weekly_limit(self):
        """POST /requirements attempting to allocate > 30 cumulative weekly periods to a section must be rejected."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                sec_id = conn.execute("INSERT INTO sections (name) VALUES ('CSE-A');").lastrowid
                s1_id = conn.execute("INSERT INTO subjects (code, name) VALUES ('CS101', 'Intro to CS');").lastrowid
                s2_id = conn.execute("INSERT INTO subjects (code, name) VALUES ('MATH101', 'Calculus');").lastrowid
                # Allocate 20 periods to s1
                conn.execute(
                    "INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, 20);",
                    (sec_id, s1_id),
                )
        finally:
            conn.close()

        # Attempting to allocate 15 periods to s2 would total 35 periods (> 30 limit)
        response = self.client.post(
            "/requirements",
            data={"section_id": str(sec_id), "subject_id": str(s2_id), "weekly_periods": "15"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"already has 20/30 periods allocated", response.data)
        self.assertIn(b"Only 10 period(s) remaining", response.data)

        # Verify second requirement was not added to database
        conn = get_db_connection(TEST_DB_PATH)
        try:
            count = conn.execute(
                "SELECT COUNT(*) AS total FROM section_requirements WHERE section_id = ?;",
                (sec_id,),
            ).fetchone()["total"]
            self.assertEqual(count, 1)
        finally:
            conn.close()

    def test_add_requirement_exact_30_periods_allowed(self):
        """POST /requirements allocating exactly 30 total weekly periods to a section should succeed."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                sec_id = conn.execute("INSERT INTO sections (name) VALUES ('CSE-A');").lastrowid
                s1_id = conn.execute("INSERT INTO subjects (code, name) VALUES ('CS101', 'Intro to CS');").lastrowid
                s2_id = conn.execute("INSERT INTO subjects (code, name) VALUES ('MATH101', 'Calculus');").lastrowid
                conn.execute(
                    "INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, 20);",
                    (sec_id, s1_id),
                )
        finally:
            conn.close()

        # Allocate exactly remaining 10 periods (20 + 10 = 30)
        response = self.client.post(
            "/requirements",
            data={"section_id": str(sec_id), "subject_id": str(s2_id), "weekly_periods": "10"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Assigned 10 weekly periods", response.data)
        self.assertIn(b"Total: 30/30 periods", response.data)

        conn = get_db_connection(TEST_DB_PATH)
        try:
            total = conn.execute(
                "SELECT SUM(weekly_periods) AS total FROM section_requirements WHERE section_id = ?;",
                (sec_id,),
            ).fetchone()["total"]
            self.assertEqual(total, 30)
        finally:
            conn.close()

    def test_setup_displays_sections_and_requirements(self):
        """GET /setup should display sections with cumulative weekly load and subject requirement badges."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                sec_id = conn.execute("INSERT INTO sections (name) VALUES ('CSE-A');").lastrowid
                s1_id = conn.execute("INSERT INTO subjects (code, name) VALUES ('CS101', 'Intro to CS');").lastrowid
                s2_id = conn.execute("INSERT INTO subjects (code, name) VALUES ('MATH101', 'Calculus');").lastrowid
                conn.execute(
                    "INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, 4);",
                    (sec_id, s1_id),
                )
                conn.execute(
                    "INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, 6);",
                    (sec_id, s2_id),
                )
        finally:
            conn.close()

        response = self.client.get("/setup?tab=sections")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"CSE-A", response.data)
        self.assertIn(b"10 / 30 periods", response.data)
        self.assertIn(b"CS101", response.data)
        self.assertIn(b"4 periods/wk", response.data)
        self.assertIn(b"MATH101", response.data)
        self.assertIn(b"6 periods/wk", response.data)

    def test_dashboard_section_count_updates(self):
        """GET / should dynamically reflect registered section count on the dashboard."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                conn.execute("INSERT INTO sections (name) VALUES ('CSE-A');")
                conn.execute("INSERT INTO sections (name) VALUES ('CSE-B');")
        finally:
            conn.close()

        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Sections", response.data)
        self.assertIn(b">2<", response.data)


if __name__ == "__main__":
    unittest.main()
