"""
Tests for Flask application routes, subject management, teacher management, and qualifications (Step 2B & 2C).
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
        # Clean subject, teacher, and mapping tables before each test for test isolation
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                conn.execute("DELETE FROM timetable_entries;")
                conn.execute("DELETE FROM section_requirements;")
                conn.execute("DELETE FROM teacher_subjects;")
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


if __name__ == "__main__":
    unittest.main()
