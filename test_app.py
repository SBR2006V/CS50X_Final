"""
Tests for Flask application routes, subject management, teacher management, qualifications, section requirements, and routine generation (Step 2B, 2C, 2D & 3B).
Uses Python's built-in unittest and Flask's test_client.
"""

import gc
from pathlib import Path
import re
import sqlite3
import unittest
from unittest.mock import patch

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

    def test_dashboard_cards_have_clickable_navigation_links(self):
        """
        Dashboard summary cards for Subjects, Teachers, and Sections should be clickable links
        navigating to the setup route with the corresponding tab selected.
        """
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.data.decode("utf-8")

        # Verify Subjects card link, ID, and accessible label
        self.assertIn('href="/setup?tab=subjects"', html)
        self.assertIn('id="card-subjects"', html)
        self.assertIn('aria-label="Subjects:', html)

        # Verify Teachers card link, ID, and accessible label
        self.assertIn('href="/setup?tab=teachers"', html)
        self.assertIn('id="card-teachers"', html)
        self.assertIn('aria-label="Teachers:', html)

        # Verify Sections card link, ID, and accessible label
        self.assertIn('href="/setup?tab=sections"', html)
        self.assertIn('id="card-sections"', html)
        self.assertIn('aria-label="Sections:', html)

        # Verify cards maintain accessibility classes
        self.assertIn("stat-card-link", html)
        self.assertIn("text-decoration-none", html)

    def test_setup_tab_query_parameter_selection(self):
        """
        GET /setup with ?tab= parameter should activate the requested tab button and pane.
        Invalid or absent parameters should fall back to the default 'subjects' tab.
        """
        # 1. Subjects tab explicitly selected
        res_sub = self.client.get("/setup?tab=subjects")
        self.assertEqual(res_sub.status_code, 200)
        html_sub = res_sub.data.decode("utf-8")
        self.assertTrue(re.search(r'class="nav-link fw-semibold active"\s+id="subjects-tab"', html_sub))
        self.assertFalse(re.search(r'class="nav-link fw-semibold active"\s+id="teachers-tab"', html_sub))
        self.assertFalse(re.search(r'class="nav-link fw-semibold active"\s+id="sections-tab"', html_sub))
        self.assertTrue(re.search(r'class="tab-pane fade show active"\s+id="subjects-pane"', html_sub))
        self.assertFalse(re.search(r'class="tab-pane fade show active"\s+id="teachers-pane"', html_sub))
        self.assertFalse(re.search(r'class="tab-pane fade show active"\s+id="sections-pane"', html_sub))

        # 2. Teachers tab selected
        res_teach = self.client.get("/setup?tab=teachers")
        self.assertEqual(res_teach.status_code, 200)
        html_teach = res_teach.data.decode("utf-8")
        self.assertTrue(re.search(r'class="nav-link fw-semibold active"\s+id="teachers-tab"', html_teach))
        self.assertFalse(re.search(r'class="nav-link fw-semibold active"\s+id="subjects-tab"', html_teach))
        self.assertFalse(re.search(r'class="nav-link fw-semibold active"\s+id="sections-tab"', html_teach))
        self.assertTrue(re.search(r'class="tab-pane fade show active"\s+id="teachers-pane"', html_teach))
        self.assertFalse(re.search(r'class="tab-pane fade show active"\s+id="subjects-pane"', html_teach))
        self.assertFalse(re.search(r'class="tab-pane fade show active"\s+id="sections-pane"', html_teach))

        # 3. Sections tab selected
        res_sec = self.client.get("/setup?tab=sections")
        self.assertEqual(res_sec.status_code, 200)
        html_sec = res_sec.data.decode("utf-8")
        self.assertTrue(re.search(r'class="nav-link fw-semibold active"\s+id="sections-tab"', html_sec))
        self.assertFalse(re.search(r'class="nav-link fw-semibold active"\s+id="subjects-tab"', html_sec))
        self.assertFalse(re.search(r'class="nav-link fw-semibold active"\s+id="teachers-tab"', html_sec))
        self.assertTrue(re.search(r'class="tab-pane fade show active"\s+id="sections-pane"', html_sec))
        self.assertFalse(re.search(r'class="tab-pane fade show active"\s+id="subjects-pane"', html_sec))
        self.assertFalse(re.search(r'class="tab-pane fade show active"\s+id="teachers-pane"', html_sec))

        # 4. Default /setup without parameter falls back to subjects
        res_default = self.client.get("/setup")
        self.assertEqual(res_default.status_code, 200)
        html_default = res_default.data.decode("utf-8")
        self.assertTrue(re.search(r'class="nav-link fw-semibold active"\s+id="subjects-tab"', html_default))
        self.assertTrue(re.search(r'class="tab-pane fade show active"\s+id="subjects-pane"', html_default))

        # 5. Invalid query parameter safely defaults to subjects
        res_invalid = self.client.get("/setup?tab=invalid_tab_name")
        self.assertEqual(res_invalid.status_code, 200)
        html_invalid = res_invalid.data.decode("utf-8")
        self.assertTrue(re.search(r'class="nav-link fw-semibold active"\s+id="subjects-tab"', html_invalid))
        self.assertTrue(re.search(r'class="tab-pane fade show active"\s+id="subjects-pane"', html_invalid))

    def test_setup_tab_selection_persists_on_page_refresh(self):
        """
        Simulate a user navigating to a specific tab and refreshing the page:
        the server should continuously serve the requested tab as active.
        """
        # Navigate to Teachers tab
        res1 = self.client.get("/setup?tab=teachers")
        self.assertEqual(res1.status_code, 200)
        html1_first = res1.data.decode("utf-8")
        self.assertTrue(re.search(r'class="tab-pane fade show active"\s+id="teachers-pane"', html1_first))

        # Refresh page (repeat request to the same URL)
        res1_refresh = self.client.get("/setup?tab=teachers")
        self.assertEqual(res1_refresh.status_code, 200)
        html1_refreshed = res1_refresh.data.decode("utf-8")
        self.assertTrue(re.search(r'class="tab-pane fade show active"\s+id="teachers-pane"', html1_refreshed))
        self.assertFalse(re.search(r'class="tab-pane fade show active"\s+id="subjects-pane"', html1_refreshed))

        # Navigate to Sections tab
        res2 = self.client.get("/setup?tab=sections")
        self.assertEqual(res2.status_code, 200)
        html2_first = res2.data.decode("utf-8")
        self.assertTrue(re.search(r'class="tab-pane fade show active"\s+id="sections-pane"', html2_first))

        # Refresh page
        res2_refresh = self.client.get("/setup?tab=sections")
        self.assertEqual(res2_refresh.status_code, 200)
        html2_refreshed = res2_refresh.data.decode("utf-8")
        self.assertTrue(re.search(r'class="tab-pane fade show active"\s+id="sections-pane"', html2_refreshed))
        self.assertFalse(re.search(r'class="tab-pane fade show active"\s+id="subjects-pane"', html2_refreshed))

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

    def test_setup_subjects_table_displays_edit_and_delete_actions_and_modals(self):
        """GET /setup should display Edit and Delete action buttons and modals for each registered subject."""
        self.client.post("/subjects", data={"code": "CS101", "name": "Intro to CS"}, follow_redirects=True)

        response = self.client.get("/setup")
        self.assertEqual(response.status_code, 200)
        html = response.data.decode("utf-8")

        self.assertIn("Actions", html)
        self.assertIn("Edit", html)
        self.assertIn("Delete", html)
        self.assertIn("editSubjectModal", html)
        self.assertIn("deleteSubjectModal", html)
        self.assertIn("/edit", html)
        self.assertIn("/delete", html)

    def test_edit_subject_success(self):
        """POST /subjects/<id>/edit should update subject code (uppercased) and name in DB, and flash success."""
        # 1. Add initial subject
        self.client.post("/subjects", data={"code": "CS101", "name": "Intro to CS"}, follow_redirects=True)
        conn = get_db_connection(TEST_DB_PATH)
        sub_id = conn.execute("SELECT id FROM subjects WHERE code = 'CS101';").fetchone()["id"]
        conn.close()

        # 2. Edit subject code and name
        res = self.client.post(
            f"/subjects/{sub_id}/edit",
            data={"code": "cs102", "name": "Data Structures"},
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"updated successfully", res.data)
        self.assertIn(b"CS102", res.data)
        self.assertIn(b"Data Structures", res.data)

        # 3. Verify in database directly
        conn = get_db_connection(TEST_DB_PATH)
        row = conn.execute("SELECT code, name FROM subjects WHERE id = ?;", (sub_id,)).fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(row["code"], "CS102")
        self.assertEqual(row["name"], "Data Structures")

        # 4. Verify dashboard count remains 1
        res_dash = self.client.get("/")
        self.assertEqual(res_dash.status_code, 200)
        self.assertIn(b">1<", res_dash.data)

    def test_edit_subject_name_only_preserves_code(self):
        """POST /subjects/<id>/edit keeping the existing code should succeed without self-collision error."""
        self.client.post("/subjects", data={"code": "MATH101", "name": "Calculus I"}, follow_redirects=True)
        conn = get_db_connection(TEST_DB_PATH)
        sub_id = conn.execute("SELECT id FROM subjects WHERE code = 'MATH101';").fetchone()["id"]
        conn.close()

        res = self.client.post(
            f"/subjects/{sub_id}/edit",
            data={"code": "MATH101", "name": "Calculus and Analytic Geometry"},
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"updated successfully", res.data)

        conn = get_db_connection(TEST_DB_PATH)
        row = conn.execute("SELECT code, name FROM subjects WHERE id = ?;", (sub_id,)).fetchone()
        conn.close()
        self.assertEqual(row["code"], "MATH101")
        self.assertEqual(row["name"], "Calculus and Analytic Geometry")

    def test_edit_subject_missing_fields_validation(self):
        """POST /subjects/<id>/edit with empty code or name should fail validation and not alter DB."""
        self.client.post("/subjects", data={"code": "BIO101", "name": "General Biology"}, follow_redirects=True)
        conn = get_db_connection(TEST_DB_PATH)
        sub_id = conn.execute("SELECT id FROM subjects WHERE code = 'BIO101';").fetchone()["id"]
        conn.close()

        # Missing code
        res1 = self.client.post(
            f"/subjects/{sub_id}/edit",
            data={"code": "   ", "name": "New Name"},
            follow_redirects=True,
        )
        self.assertEqual(res1.status_code, 200)
        self.assertIn(b"Both Subject Code and Subject Name are required.", res1.data)

        # Missing name
        res2 = self.client.post(
            f"/subjects/{sub_id}/edit",
            data={"code": "BIO102", "name": "  "},
            follow_redirects=True,
        )
        self.assertEqual(res2.status_code, 200)
        self.assertIn(b"Both Subject Code and Subject Name are required.", res2.data)

        # DB must remain unchanged
        conn = get_db_connection(TEST_DB_PATH)
        row = conn.execute("SELECT code, name FROM subjects WHERE id = ?;", (sub_id,)).fetchone()
        conn.close()
        self.assertEqual(row["code"], "BIO101")
        self.assertEqual(row["name"], "General Biology")

    def test_edit_subject_duplicate_code_prevention(self):
        """POST /subjects/<id>/edit trying to rename to an existing subject's code should trigger duplicate error."""
        self.client.post("/subjects", data={"code": "ENG101", "name": "English Composition"}, follow_redirects=True)
        self.client.post("/subjects", data={"code": "HIST101", "name": "World History"}, follow_redirects=True)

        conn = get_db_connection(TEST_DB_PATH)
        hist_id = conn.execute("SELECT id FROM subjects WHERE code = 'HIST101';").fetchone()["id"]
        conn.close()

        # Attempt to rename HIST101 to eng101
        res = self.client.post(
            f"/subjects/{hist_id}/edit",
            data={"code": "eng101", "name": "World History Revised"},
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"already exists", res.data)

        # Verify HIST101 was not renamed
        conn = get_db_connection(TEST_DB_PATH)
        row = conn.execute("SELECT code FROM subjects WHERE id = ?;", (hist_id,)).fetchone()
        conn.close()
        self.assertEqual(row["code"], "HIST101")

    def test_edit_subject_nonexistent_id(self):
        """POST /subjects/99999/edit should fail with subject not found flash."""
        res = self.client.post(
            "/subjects/99999/edit",
            data={"code": "FAKE101", "name": "Fake Subject"},
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Subject not found", res.data)

    def test_delete_subject_standalone_success(self):
        """POST /subjects/<id>/delete for a standalone subject should delete row and decrement dashboard count."""
        self.client.post("/subjects", data={"code": "CHEM101", "name": "General Chemistry"}, follow_redirects=True)
        conn = get_db_connection(TEST_DB_PATH)
        sub_id = conn.execute("SELECT id FROM subjects WHERE code = 'CHEM101';").fetchone()["id"]
        conn.close()

        # Verify dashboard shows 1 subject initially
        res_dash1 = self.client.get("/")
        self.assertIn(b">1<", res_dash1.data)

        # Delete subject
        res_del = self.client.post(f"/subjects/{sub_id}/delete", follow_redirects=True)
        self.assertEqual(res_del.status_code, 200)
        self.assertIn(b"deleted successfully", res_del.data)

        # Verify row is gone from DB
        conn = get_db_connection(TEST_DB_PATH)
        row = conn.execute("SELECT * FROM subjects WHERE id = ?;", (sub_id,)).fetchone()
        conn.close()
        self.assertIsNone(row)

        # Verify dashboard count is now 0
        res_dash2 = self.client.get("/")
        self.assertIn(b">0<", res_dash2.data)

    def test_delete_subject_with_related_records_safe_transaction(self):
        """
        POST /subjects/<id>/delete for a subject with teacher qualifications, section requirements,
        and timetable entries should safely delete all dependent records without foreign key errors.
        """
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                sub_id = conn.execute("INSERT INTO subjects (code, name) VALUES ('CS101', 'Intro to CS');").lastrowid
                t_id = conn.execute("INSERT INTO teachers (name, email) VALUES ('Prof. Turing', 'turing@ai.edu');").lastrowid
                sec_id = conn.execute("INSERT INTO sections (name) VALUES ('CSE-A');").lastrowid
                conn.execute("INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?);", (t_id, sub_id))
                conn.execute("INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, 4);", (sec_id, sub_id))
        finally:
            conn.close()

        # Generate routine -> 4 timetable entries
        res_gen = self.client.post("/routine/generate", follow_redirects=True)
        self.assertEqual(res_gen.status_code, 200)

        # Verify initial counts in DB
        conn = get_db_connection(TEST_DB_PATH)
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM subjects;").fetchone()["c"], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM teacher_subjects;").fetchone()["c"], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM section_requirements;").fetchone()["c"], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM timetable_entries;").fetchone()["c"], 4)
        finally:
            conn.close()

        # Verify that setup page displays consequences warning in delete modal
        res_setup = self.client.get("/setup?tab=subjects")
        self.assertEqual(res_setup.status_code, 200)
        self.assertIn(b"Consequences of Deletion", res_setup.data)
        self.assertIn(b"faculty qualification", res_setup.data)
        self.assertIn(b"section weekly requirement", res_setup.data)
        self.assertIn(b"scheduled class period", res_setup.data)

        # Delete subject
        res_del = self.client.post(f"/subjects/{sub_id}/delete", follow_redirects=True)
        self.assertEqual(res_del.status_code, 200)
        self.assertIn(b"deleted successfully along with associated records", res_del.data)

        # Verify safe transaction: subject and dependent rows deleted, parent teachers/sections preserved
        conn = get_db_connection(TEST_DB_PATH)
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM subjects;").fetchone()["c"], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM teacher_subjects;").fetchone()["c"], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM section_requirements;").fetchone()["c"], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM timetable_entries;").fetchone()["c"], 0)
            # Teachers and sections must still exist intact
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM teachers;").fetchone()["c"], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM sections;").fetchone()["c"], 1)
        finally:
            conn.close()

        # Dashboard counts reflect deletion
        res_dash = self.client.get("/")
        self.assertIn(b">0<", res_dash.data)  # 0 subjects, 0 scheduled entries

    def test_delete_subject_marks_timetable_outdated_when_routine_exists(self):
        """
        When a subject that is scheduled in the timetable is deleted,
        GET /routine must display the timetable as Outdated and never as 'Published & Up to Date'.
        """
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                sub1 = conn.execute("INSERT INTO subjects (code, name) VALUES ('CS101', 'Computer Science');").lastrowid
                sub2 = conn.execute("INSERT INTO subjects (code, name) VALUES ('MATH101', 'Calculus');").lastrowid
                t_id = conn.execute("INSERT INTO teachers (name, email) VALUES ('Dr. Euler', 'euler@math.org');").lastrowid
                sec_id = conn.execute("INSERT INTO sections (name) VALUES ('SEC-1');").lastrowid
                conn.execute("INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?);", (t_id, sub1))
                conn.execute("INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?);", (t_id, sub2))
                conn.execute("INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, 4);", (sec_id, sub1))
                conn.execute("INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, 2);", (sec_id, sub2))
        finally:
            conn.close()

        # Generate initial timetable (6 slots)
        res_gen = self.client.post("/routine/generate", follow_redirects=True)
        self.assertEqual(res_gen.status_code, 200)
        self.assertIn(b"Published &amp; Up to Date", res_gen.data)

        # Delete subject CS101
        res_del = self.client.post(f"/subjects/{sub1}/delete", follow_redirects=True)
        self.assertEqual(res_del.status_code, 200)

        # Visit GET /routine -> Must show Outdated Timetable warning
        res_routine = self.client.get("/routine")
        self.assertEqual(res_routine.status_code, 200)
        self.assertIn(b"Outdated Timetable", res_routine.data)
        self.assertIn(b"Timetable Outdated", res_routine.data)
        self.assertNotIn(b"Published &amp; Up to Date", res_routine.data)

        # Regenerating routine should succeed and restore 'Published & Up to Date' for remaining setup
        res_regen = self.client.post("/routine/generate", follow_redirects=True)
        self.assertEqual(res_regen.status_code, 200)
        self.assertIn(b"Published &amp; Up to Date", res_regen.data)

    def test_delete_subject_nonexistent_id(self):
        """POST /subjects/99999/delete should fail with subject not found flash."""
        res = self.client.post("/subjects/99999/delete", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Subject not found", res.data)

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

    def test_setup_teachers_table_displays_edit_and_delete_actions_and_modals(self):
        """GET /setup?tab=teachers should display Edit and Delete buttons and modals for each registered teacher."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                t_id = conn.execute("INSERT INTO teachers (name, email) VALUES ('Dr. Katherine Johnson', 'kjohnson@nasa.gov');").lastrowid
                s_id = conn.execute("INSERT INTO subjects (code, name) VALUES ('MATH101', 'Orbital Mechanics');").lastrowid
                conn.execute("INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?);", (t_id, s_id))
        finally:
            conn.close()

        response = self.client.get("/setup?tab=teachers")
        self.assertEqual(response.status_code, 200)
        html = response.data.decode("utf-8")

        self.assertIn("Actions", html)
        self.assertIn("Edit", html)
        self.assertIn("Delete", html)
        self.assertIn(f"editTeacherModal{t_id}", html)
        self.assertIn(f"deleteTeacherModal{t_id}", html)
        self.assertIn(f"/teachers/{t_id}/edit", html)
        self.assertIn(f"/teachers/{t_id}/delete", html)
        self.assertIn("Dr. Katherine Johnson", html)
        self.assertIn("kjohnson@nasa.gov", html)
        self.assertIn("MATH101", html)

    def test_edit_teacher_success_name_and_email(self):
        """POST /teachers/<id>/edit should update name and email, redirect, and flash success."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                t_id = conn.execute("INSERT INTO teachers (name, email) VALUES ('Ada Lovelace', 'ada@example.edu');").lastrowid
        finally:
            conn.close()

        # Update name and email
        response = self.client.post(
            f"/teachers/{t_id}/edit",
            data={"name": "Lady Ada Lovelace", "email": "lady.ada@computing.org"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"updated successfully", response.data)
        self.assertIn(b"Lady Ada Lovelace", response.data)
        self.assertIn(b"lady.ada@computing.org", response.data)

        # Direct database verification
        conn = get_db_connection(TEST_DB_PATH)
        try:
            row = conn.execute("SELECT name, email FROM teachers WHERE id = ?;", (t_id,)).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["name"], "Lady Ada Lovelace")
            self.assertEqual(row["email"], "lady.ada@computing.org")
        finally:
            conn.close()

        # Dashboard teacher count remains 1
        res_dash = self.client.get("/")
        self.assertIn(b">1<", res_dash.data)

    def test_edit_teacher_without_email_clears_email(self):
        """POST /teachers/<id>/edit with empty email should set email to NULL in database."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                t_id = conn.execute("INSERT INTO teachers (name, email) VALUES ('Prof. Turing', 'alan@bletchley.uk');").lastrowid
        finally:
            conn.close()

        response = self.client.post(
            f"/teachers/{t_id}/edit",
            data={"name": "Prof. Alan Turing", "email": "   "},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"updated successfully", response.data)
        self.assertIn(b"Not provided", response.data)

        conn = get_db_connection(TEST_DB_PATH)
        try:
            row = conn.execute("SELECT name, email FROM teachers WHERE id = ?;", (t_id,)).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["name"], "Prof. Alan Turing")
            self.assertIsNone(row["email"])
        finally:
            conn.close()

    def test_edit_teacher_name_only_preserves_same_email(self):
        """POST /teachers/<id>/edit keeping the existing email should not trigger duplicate collision."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                t_id = conn.execute("INSERT INTO teachers (name, email) VALUES ('Prof. Euler', 'euler@basel.ch');").lastrowid
        finally:
            conn.close()

        response = self.client.post(
            f"/teachers/{t_id}/edit",
            data={"name": "Leonhard Euler", "email": "euler@basel.ch"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"updated successfully", response.data)

        conn = get_db_connection(TEST_DB_PATH)
        try:
            row = conn.execute("SELECT name, email FROM teachers WHERE id = ?;", (t_id,)).fetchone()
            self.assertEqual(row["name"], "Leonhard Euler")
            self.assertEqual(row["email"], "euler@basel.ch")
        finally:
            conn.close()

    def test_edit_teacher_missing_name_validation(self):
        """POST /teachers/<id>/edit with empty name should fail validation and not alter DB."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                t_id = conn.execute("INSERT INTO teachers (name, email) VALUES ('Dr. Gauss', 'gauss@gottingen.de');").lastrowid
        finally:
            conn.close()

        response = self.client.post(
            f"/teachers/{t_id}/edit",
            data={"name": "   ", "email": "new.gauss@gottingen.de"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Teacher name is required.", response.data)

        # Database record must remain untouched
        conn = get_db_connection(TEST_DB_PATH)
        try:
            row = conn.execute("SELECT name, email FROM teachers WHERE id = ?;", (t_id,)).fetchone()
            self.assertEqual(row["name"], "Dr. Gauss")
            self.assertEqual(row["email"], "gauss@gottingen.de")
        finally:
            conn.close()

    def test_edit_teacher_duplicate_email_validation(self):
        """POST /teachers/<id>/edit with an email belonging to another teacher should trigger duplicate error."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                t1_id = conn.execute("INSERT INTO teachers (name, email) VALUES ('Teacher One', 't1@university.edu');").lastrowid
                t2_id = conn.execute("INSERT INTO teachers (name, email) VALUES ('Teacher Two', 't2@university.edu');").lastrowid
        finally:
            conn.close()

        # Try updating Teacher Two with Teacher One's email (case-insensitive test)
        response = self.client.post(
            f"/teachers/{t2_id}/edit",
            data={"name": "Teacher Two Modified", "email": "T1@UNIVERSITY.EDU"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"already exists", response.data)

        # Verify Teacher Two was not updated
        conn = get_db_connection(TEST_DB_PATH)
        try:
            row = conn.execute("SELECT name, email FROM teachers WHERE id = ?;", (t2_id,)).fetchone()
            self.assertEqual(row["name"], "Teacher Two")
            self.assertEqual(row["email"], "t2@university.edu")
        finally:
            conn.close()

    def test_edit_teacher_updating_qualifications(self):
        """POST /teachers/<id>/edit should synchronize teacher qualifications (add new, remove omitted)."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                t_id = conn.execute("INSERT INTO teachers (name, email) VALUES ('Dr. Shannon', 'shannon@bell.labs');").lastrowid
                s1_id = conn.execute("INSERT INTO subjects (code, name) VALUES ('INFO101', 'Information Theory');").lastrowid
                s2_id = conn.execute("INSERT INTO subjects (code, name) VALUES ('MATH101', 'Discrete Math');").lastrowid
                s3_id = conn.execute("INSERT INTO subjects (code, name) VALUES ('CS101', 'Digital Logic');").lastrowid
                # Initially qualified for s1 and s2
                conn.execute("INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?);", (t_id, s1_id))
                conn.execute("INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?);", (t_id, s2_id))
        finally:
            conn.close()

        # Edit teacher: keep s2, remove s1, add s3
        response = self.client.post(
            f"/teachers/{t_id}/edit",
            data={"name": "Dr. Claude Shannon", "email": "shannon@bell.labs", "subject_ids": [str(s2_id), str(s3_id)]},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"updated successfully", response.data)

        # Verify qualifications in database
        conn = get_db_connection(TEST_DB_PATH)
        try:
            rows = conn.execute(
                "SELECT subject_id FROM teacher_subjects WHERE teacher_id = ? ORDER BY subject_id ASC;",
                (t_id,),
            ).fetchall()
            assigned_ids = [r["subject_id"] for r in rows]
            assert s2_id is not None and s3_id is not None
            self.assertEqual(assigned_ids, sorted([s2_id, s3_id]))
            self.assertNotIn(s1_id, assigned_ids)
        finally:
            conn.close()

    def test_edit_teacher_nonexistent_id(self):
        """POST /teachers/99999/edit should fail with teacher not found flash."""
        response = self.client.post(
            "/teachers/99999/edit",
            data={"name": "Ghost Teacher", "email": "ghost@uni.edu"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Teacher not found", response.data)

    def test_delete_teacher_standalone_success(self):
        """POST /teachers/<id>/delete for a standalone teacher should delete row and decrement dashboard count."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                t_id = conn.execute("INSERT INTO teachers (name, email) VALUES ('Prof. Fermat', 'fermat@margin.fr');").lastrowid
        finally:
            conn.close()

        # Verify dashboard count is 1
        res_dash1 = self.client.get("/")
        self.assertIn(b">1<", res_dash1.data)

        # Delete teacher
        response = self.client.post(f"/teachers/{t_id}/delete", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"deleted successfully", response.data)

        # Verify record deleted from database
        conn = get_db_connection(TEST_DB_PATH)
        try:
            row = conn.execute("SELECT * FROM teachers WHERE id = ?;", (t_id,)).fetchone()
            self.assertIsNone(row)
        finally:
            conn.close()

        # Verify dashboard count is 0
        res_dash2 = self.client.get("/")
        self.assertIn(b">0<", res_dash2.data)

    def test_delete_teacher_with_qualifications_and_timetable_entries_safe_transaction(self):
        """
        POST /teachers/<id>/delete for a teacher with qualifications and timetable entries
        should safely delete dependent records in an atomic transaction and preserve other entities.
        """
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                sub_id = conn.execute("INSERT INTO subjects (code, name) VALUES ('CS101', 'Computer Science');").lastrowid
                t_id = conn.execute("INSERT INTO teachers (name, email) VALUES ('Dr. Turing', 'alan@ai.org');").lastrowid
                sec_id = conn.execute("INSERT INTO sections (name) VALUES ('SEC-A');").lastrowid
                conn.execute("INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?);", (t_id, sub_id))
                conn.execute("INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, 4);", (sec_id, sub_id))
        finally:
            conn.close()

        # Generate routine -> 4 timetable entries
        res_gen = self.client.post("/routine/generate", follow_redirects=True)
        self.assertEqual(res_gen.status_code, 200)

        # Verify initial DB state
        conn = get_db_connection(TEST_DB_PATH)
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM teachers;").fetchone()["c"], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM teacher_subjects;").fetchone()["c"], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM timetable_entries WHERE teacher_id = ?;", (t_id,)).fetchone()["c"], 4)
        finally:
            conn.close()

        # Verify consequence warnings are rendered in Setup -> Teachers delete modal
        res_setup = self.client.get("/setup?tab=teachers")
        self.assertEqual(res_setup.status_code, 200)
        self.assertIn(b"Consequences of Deletion", res_setup.data)
        self.assertIn(b"subject qualification", res_setup.data)
        self.assertIn(b"scheduled class period", res_setup.data)

        # Delete teacher
        res_del = self.client.post(f"/teachers/{t_id}/delete", follow_redirects=True)
        self.assertEqual(res_del.status_code, 200)
        self.assertIn(b"deleted successfully along with associated records", res_del.data)

        # Verify safe transaction: teacher, teacher_subjects, and teacher's timetable entries deleted
        conn = get_db_connection(TEST_DB_PATH)
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM teachers WHERE id = ?;", (t_id,)).fetchone()["c"], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM teacher_subjects WHERE teacher_id = ?;", (t_id,)).fetchone()["c"], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM timetable_entries WHERE teacher_id = ?;", (t_id,)).fetchone()["c"], 0)
            # Subject and section must still exist intact
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM subjects WHERE id = ?;", (sub_id,)).fetchone()["c"], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM sections WHERE id = ?;", (sec_id,)).fetchone()["c"], 1)
        finally:
            conn.close()

        # Dashboard counts updated
        res_dash = self.client.get("/")
        self.assertIn(b">0<", res_dash.data)

    def test_delete_teacher_marks_timetable_outdated_when_routine_exists(self):
        """
        When a teacher who is scheduled in the timetable is deleted,
        GET /routine must display the timetable as Outdated and never as 'Published & Up to Date'.
        """
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                sub1 = conn.execute("INSERT INTO subjects (code, name) VALUES ('CS101', 'Intro to CS');").lastrowid
                sub2 = conn.execute("INSERT INTO subjects (code, name) VALUES ('MATH101', 'Calculus');").lastrowid
                t1 = conn.execute("INSERT INTO teachers (name, email) VALUES ('Dr. Turing', 'turing@ai.org');").lastrowid
                t2 = conn.execute("INSERT INTO teachers (name, email) VALUES ('Dr. Euler', 'euler@math.org');").lastrowid
                sec = conn.execute("INSERT INTO sections (name) VALUES ('BATCH-1');").lastrowid
                conn.execute("INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?);", (t1, sub1))
                conn.execute("INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?);", (t2, sub2))
                conn.execute("INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, 3);", (sec, sub1))
                conn.execute("INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, 2);", (sec, sub2))
        finally:
            conn.close()

        # Generate routine
        res_gen = self.client.post("/routine/generate", follow_redirects=True)
        self.assertEqual(res_gen.status_code, 200)
        self.assertIn(b"Published &amp; Up to Date", res_gen.data)

        # Delete teacher 1
        res_del = self.client.post(f"/teachers/{t1}/delete", follow_redirects=True)
        self.assertEqual(res_del.status_code, 200)

        # Check GET /routine -> Outdated Timetable
        res_routine = self.client.get("/routine")
        self.assertEqual(res_routine.status_code, 200)
        self.assertIn(b"Outdated Timetable", res_routine.data)
        self.assertIn(b"Timetable Outdated", res_routine.data)
        self.assertNotIn(b"Published &amp; Up to Date", res_routine.data)

    def test_edit_teacher_unqualifying_scheduled_subject_marks_timetable_outdated(self):
        """
        When editing a teacher removes qualifications for subjects currently scheduled in the timetable,
        the timetable must be marked Outdated with a clear explanation.
        """
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                sub_id = conn.execute("INSERT INTO subjects (code, name) VALUES ('CS101', 'Intro to CS');").lastrowid
                t_id = conn.execute("INSERT INTO teachers (name, email) VALUES ('Dr. Turing', 'turing@ai.org');").lastrowid
                sec_id = conn.execute("INSERT INTO sections (name) VALUES ('BATCH-1');").lastrowid
                conn.execute("INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?);", (t_id, sub_id))
                conn.execute("INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, 4);", (sec_id, sub_id))
        finally:
            conn.close()

        # Generate routine
        res_gen = self.client.post("/routine/generate", follow_redirects=True)
        self.assertEqual(res_gen.status_code, 200)
        self.assertIn(b"Published &amp; Up to Date", res_gen.data)

        # Edit teacher to remove qualification for CS101 (pass empty subject_ids)
        res_edit = self.client.post(
            f"/teachers/{t_id}/edit",
            data={"name": "Dr. Turing", "email": "turing@ai.org", "subject_ids": []},
            follow_redirects=True,
        )
        self.assertEqual(res_edit.status_code, 200)
        self.assertIn(b"updated successfully", res_edit.data)

        # Timetable must now be marked Outdated
        res_routine = self.client.get("/routine")
        self.assertEqual(res_routine.status_code, 200)
        self.assertIn(b"Outdated Timetable", res_routine.data)
        self.assertIn(b"Timetable Outdated", res_routine.data)
        self.assertNotIn(b"Published &amp; Up to Date", res_routine.data)

    def test_delete_teacher_nonexistent_id(self):
        """POST /teachers/99999/delete should fail with teacher not found flash."""
        res = self.client.post("/teachers/99999/delete", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Teacher not found", res.data)

    def test_edit_teacher_via_form_body_teacher_id(self):
        """POST /teachers/edit with teacher_id in form payload should successfully update teacher."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                t_id = conn.execute("INSERT INTO teachers (name, email) VALUES ('Grace Hopper', 'grace@navy.mil');").lastrowid
        finally:
            conn.close()

        response = self.client.post(
            "/teachers/edit",
            data={"teacher_id": str(t_id), "name": "Rear Adm. Grace Hopper", "email": "hopper@navy.mil"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"updated successfully", response.data)
        self.assertIn(b"Rear Adm. Grace Hopper", response.data)

        conn = get_db_connection(TEST_DB_PATH)
        try:
            row = conn.execute("SELECT name, email FROM teachers WHERE id = ?;", (t_id,)).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["name"], "Rear Adm. Grace Hopper")
            self.assertEqual(row["email"], "hopper@navy.mil")
        finally:
            conn.close()

    def test_edit_teacher_invalid_teacher_id_string(self):
        """POST /teachers/edit with non-numeric teacher_id should flash invalid teacher ID."""
        response = self.client.post(
            "/teachers/edit",
            data={"teacher_id": "not-an-id", "name": "Fake Teacher"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Invalid teacher ID.", response.data)

    def test_edit_teacher_nonexistent_subject_id_fails(self):
        """POST /teachers/<id>/edit with non-existent subject_id should flash error and preserve qualifications."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                t_id = conn.execute("INSERT INTO teachers (name, email) VALUES ('Prof. Gauss', 'gauss@math.org');").lastrowid
                s_id = conn.execute("INSERT INTO subjects (code, name) VALUES ('MATH201', 'Calculus II');").lastrowid
                conn.execute("INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?);", (t_id, s_id))
        finally:
            conn.close()

        response = self.client.post(
            f"/teachers/{t_id}/edit",
            data={"name": "Prof. Carl Gauss", "email": "gauss@math.org", "subject_ids": ["99999"]},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"One or more selected subjects do not exist.", response.data)

        # Existing qualification must remain intact
        conn = get_db_connection(TEST_DB_PATH)
        try:
            rows = conn.execute("SELECT subject_id FROM teacher_subjects WHERE teacher_id = ?;", (t_id,)).fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["subject_id"], s_id)
        finally:
            conn.close()

    def test_edit_teacher_invalid_subject_id_format_fails(self):
        """POST /teachers/<id>/edit with non-numeric subject_id should flash invalid subject selection."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                t_id = conn.execute("INSERT INTO teachers (name) VALUES ('Prof. Hilbert');").lastrowid
        finally:
            conn.close()

        response = self.client.post(
            f"/teachers/{t_id}/edit",
            data={"name": "Prof. David Hilbert", "subject_ids": ["abc-invalid"]},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Invalid subject selection.", response.data)

    def test_delete_teacher_via_form_body_teacher_id(self):
        """POST /teachers/delete with teacher_id in form payload should successfully delete teacher."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                t_id = conn.execute("INSERT INTO teachers (name) VALUES ('Prof. Dirichlet');").lastrowid
        finally:
            conn.close()

        response = self.client.post(
            "/teachers/delete",
            data={"teacher_id": str(t_id)},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"deleted successfully", response.data)

        conn = get_db_connection(TEST_DB_PATH)
        try:
            row = conn.execute("SELECT * FROM teachers WHERE id = ?;", (t_id,)).fetchone()
            self.assertIsNone(row)
        finally:
            conn.close()

    def test_delete_teacher_invalid_teacher_id_string(self):
        """POST /teachers/delete with non-numeric teacher_id should flash invalid teacher ID."""
        response = self.client.post(
            "/teachers/delete",
            data={"teacher_id": "not-valid-id"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Invalid teacher ID.", response.data)

    def test_edit_teacher_preserving_scheduled_qualifications_does_not_mark_timetable_outdated(self):
        """
        When editing a teacher removes an unscheduled qualification (leaving scheduled qualifications intact),
        the timetable should remain valid and up-to-date.
        """
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                s1 = conn.execute("INSERT INTO subjects (code, name) VALUES ('CS101', 'Intro to CS');").lastrowid
                s2 = conn.execute("INSERT INTO subjects (code, name) VALUES ('CS102', 'Data Structures');").lastrowid
                t_id = conn.execute("INSERT INTO teachers (name, email) VALUES ('Dr. Turing', 'alan@ai.org');").lastrowid
                sec = conn.execute("INSERT INTO sections (name) VALUES ('SEC-A');").lastrowid
                conn.execute("INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?);", (t_id, s1))
                conn.execute("INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?);", (t_id, s2))
                # Only CS101 is required and will be scheduled
                conn.execute("INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, 2);", (sec, s1))
        finally:
            conn.close()

        # Generate routine -> only CS101 is scheduled
        res_gen = self.client.post("/routine/generate", follow_redirects=True)
        self.assertEqual(res_gen.status_code, 200)
        self.assertIn(b"Published &amp; Up to Date", res_gen.data)

        # Edit teacher: keep s1 (CS101), drop s2 (CS102) which was never scheduled
        res_edit = self.client.post(
            f"/teachers/{t_id}/edit",
            data={"name": "Dr. Alan Turing", "email": "alan@ai.org", "subject_ids": [str(s1)]},
            follow_redirects=True,
        )
        self.assertEqual(res_edit.status_code, 200)
        self.assertIn(b"updated successfully", res_edit.data)

        # Timetable should still be Up to Date!
        res_routine = self.client.get("/routine")
        self.assertEqual(res_routine.status_code, 200)
        self.assertIn(b"Published &amp; Up to Date", res_routine.data)
        self.assertNotIn(b"Outdated Timetable", res_routine.data)

    def test_teacher_change_does_not_silently_publish_new_timetable_until_regenerated(self):
        """
        Verify that deleting a scheduled teacher marks timetable outdated, drops affected slots,
        does NOT silently regenerate, and only regenerates upon explicit user action.
        """
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                sub1 = conn.execute("INSERT INTO subjects (code, name) VALUES ('CS101', 'Intro to CS');").lastrowid
                t1 = conn.execute("INSERT INTO teachers (name, email) VALUES ('Teacher 1', 't1@uni.edu');").lastrowid
                t2 = conn.execute("INSERT INTO teachers (name, email) VALUES ('Teacher 2', 't2@uni.edu');").lastrowid
                sec = conn.execute("INSERT INTO sections (name) VALUES ('BATCH-X');").lastrowid
                conn.execute("INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?);", (t1, sub1))
                conn.execute("INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?);", (t2, sub1))
                conn.execute("INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, 2);", (sec, sub1))
        finally:
            conn.close()

        # Generate routine initially
        res_gen = self.client.post("/routine/generate", follow_redirects=True)
        self.assertEqual(res_gen.status_code, 200)

        conn = get_db_connection(TEST_DB_PATH)
        try:
            t1_entries = conn.execute("SELECT COUNT(*) AS c FROM timetable_entries WHERE teacher_id = ?;", (t1,)).fetchone()["c"]
            self.assertGreater(t1_entries, 0)
        finally:
            conn.close()

        # Delete teacher 1
        res_del = self.client.post(f"/teachers/{t1}/delete", follow_redirects=True)
        self.assertEqual(res_del.status_code, 200)

        # 1. Timetable is outdated and has fewer entries than required (NOT silently regenerated)
        conn = get_db_connection(TEST_DB_PATH)
        try:
            current_entries_count = conn.execute("SELECT COUNT(*) AS c FROM timetable_entries;").fetchone()["c"]
            self.assertEqual(current_entries_count, 2 - t1_entries)
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM timetable_entries WHERE teacher_id = ?;", (t1,)).fetchone()["c"], 0)
        finally:
            conn.close()

        res_routine = self.client.get("/routine")
        self.assertIn(b"Outdated Timetable", res_routine.data)
        self.assertIn(b"Regenerate Routine", res_routine.data)

        # 2. Only after explicit Regenerate Routine is clicked, routine is re-published with remaining teacher
        res_regen = self.client.post("/routine/generate", follow_redirects=True)
        self.assertEqual(res_regen.status_code, 200)
        self.assertIn(b"Published &amp; Up to Date", res_regen.data)

        conn = get_db_connection(TEST_DB_PATH)
        try:
            new_entries_count = conn.execute("SELECT COUNT(*) AS c FROM timetable_entries;").fetchone()["c"]
            self.assertEqual(new_entries_count, 2)
        finally:
            conn.close()

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

    def test_setup_sections_table_displays_delete_actions_and_modals(self):
        """GET /setup?tab=sections should display Delete button and confirmation modal identifying section by name and explaining removal of associated records."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                sec_id = conn.execute("INSERT INTO sections (name) VALUES ('CSE-Alpha');").lastrowid
                sub_id = conn.execute("INSERT INTO subjects (code, name) VALUES ('CS101', 'Intro to CS');").lastrowid
                conn.execute("INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, 4);", (sec_id, sub_id))
        finally:
            conn.close()

        response = self.client.get("/setup?tab=sections")
        self.assertEqual(response.status_code, 200)
        html = response.data.decode("utf-8")

        self.assertIn("Actions", html)
        self.assertIn("Delete", html)
        self.assertIn(f"deleteSectionModal{sec_id}", html)
        self.assertIn(f"/sections/{sec_id}/delete", html)
        self.assertIn("CSE-Alpha", html)
        self.assertIn("Consequences of Deletion", html)
        self.assertIn("weekly subject requirement(s) will be removed", html)

    def test_delete_section_no_subject_requirements_success(self):
        """POST /sections/<id>/delete for a section with no subject requirements should delete section, decrement dashboard count, and flash success."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                sec_id = conn.execute("INSERT INTO sections (name) VALUES ('CSE-EMPTY');").lastrowid
        finally:
            conn.close()

        # Dashboard shows 1 section
        res_dash1 = self.client.get("/")
        self.assertIn(b">1<", res_dash1.data)

        # Delete section
        response = self.client.post(f"/sections/{sec_id}/delete", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"deleted successfully", response.data)
        self.assertIn(b"CSE-EMPTY", response.data)

        # Verify record is deleted from database
        conn = get_db_connection(TEST_DB_PATH)
        try:
            row = conn.execute("SELECT * FROM sections WHERE id = ?;", (sec_id,)).fetchone()
            self.assertIsNone(row)
        finally:
            conn.close()

        # Dashboard count decremented
        res_dash2 = self.client.get("/")
        self.assertIn(b">0<", res_dash2.data)

    def test_delete_section_with_subject_requirements_removes_associated_records(self):
        """POST /sections/<id>/delete for a section with subject requirements removes the section and all its requirements while preserving subjects."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                sec_id = conn.execute("INSERT INTO sections (name) VALUES ('CSE-REQS');").lastrowid
                sub1_id = conn.execute("INSERT INTO subjects (code, name) VALUES ('CS101', 'Intro to CS');").lastrowid
                sub2_id = conn.execute("INSERT INTO subjects (code, name) VALUES ('MATH101', 'Calculus');").lastrowid
                conn.execute("INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, 4);", (sec_id, sub1_id))
                conn.execute("INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, 3);", (sec_id, sub2_id))
        finally:
            conn.close()

        response = self.client.post(f"/sections/{sec_id}/delete", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"deleted successfully along with associated records", response.data)
        self.assertIn(b"2 section requirement(s)", response.data)

        conn = get_db_connection(TEST_DB_PATH)
        try:
            # Section is gone
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM sections WHERE id = ?;", (sec_id,)).fetchone()["c"], 0)
            # Section requirements are removed
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM section_requirements WHERE section_id = ?;", (sec_id,)).fetchone()["c"], 0)
            # Subjects remain intact
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM subjects WHERE id IN (?, ?);", (sub1_id, sub2_id)).fetchone()["c"], 2)
        finally:
            conn.close()

    def test_delete_section_with_timetable_entries_removes_associated_records(self):
        """POST /sections/<id>/delete for a section with timetable entries removes the section, its requirements, and its timetable entries."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                sec_id = conn.execute("INSERT INTO sections (name) VALUES ('CSE-ROUTINE');").lastrowid
                sub_id = conn.execute("INSERT INTO subjects (code, name) VALUES ('CS101', 'Intro to CS');").lastrowid
                t_id = conn.execute("INSERT INTO teachers (name, email) VALUES ('Dr. Ada', 'ada@cs.edu');").lastrowid
                conn.execute("INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?);", (t_id, sub_id))
                conn.execute("INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, 4);", (sec_id, sub_id))
        finally:
            conn.close()

        # Generate routine
        res_gen = self.client.post("/routine/generate", follow_redirects=True)
        self.assertEqual(res_gen.status_code, 200)

        conn = get_db_connection(TEST_DB_PATH)
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM timetable_entries WHERE section_id = ?;", (sec_id,)).fetchone()["c"], 4)
        finally:
            conn.close()

        # Delete section
        response = self.client.post(f"/sections/{sec_id}/delete", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"deleted successfully along with associated records", response.data)
        self.assertIn(b"4 timetable slot(s)", response.data)

        # Confirm associated records are removed
        conn = get_db_connection(TEST_DB_PATH)
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM sections WHERE id = ?;", (sec_id,)).fetchone()["c"], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM section_requirements WHERE section_id = ?;", (sec_id,)).fetchone()["c"], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM timetable_entries WHERE section_id = ?;", (sec_id,)).fetchone()["c"], 0)
            # Subject and teacher remain intact
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM subjects WHERE id = ?;", (sub_id,)).fetchone()["c"], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM teachers WHERE id = ?;", (t_id,)).fetchone()["c"], 1)
        finally:
            conn.close()

    def test_delete_section_preserves_other_sections_and_their_records(self):
        """Deleting one section leaves other sections, their requirements, and their timetable entries unchanged."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                sec_a = conn.execute("INSERT INTO sections (name) VALUES ('CSE-A');").lastrowid
                sec_b = conn.execute("INSERT INTO sections (name) VALUES ('CSE-B');").lastrowid
                sub = conn.execute("INSERT INTO subjects (code, name) VALUES ('CS101', 'Intro to CS');").lastrowid
                t = conn.execute("INSERT INTO teachers (name) VALUES ('Dr. Turing');").lastrowid
                conn.execute("INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?);", (t, sub))
                conn.execute("INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, 3);", (sec_a, sub))
                conn.execute("INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, 4);", (sec_b, sub))
        finally:
            conn.close()

        # Generate routine -> 7 total entries (3 for A, 4 for B)
        self.client.post("/routine/generate", follow_redirects=True)

        # Delete section A
        response = self.client.post(f"/sections/{sec_a}/delete", follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        conn = get_db_connection(TEST_DB_PATH)
        try:
            # Section A is deleted
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM sections WHERE id = ?;", (sec_a,)).fetchone()["c"], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM section_requirements WHERE section_id = ?;", (sec_a,)).fetchone()["c"], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM timetable_entries WHERE section_id = ?;", (sec_a,)).fetchone()["c"], 0)

            # Section B and its records are completely intact!
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM sections WHERE id = ?;", (sec_b,)).fetchone()["c"], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM section_requirements WHERE section_id = ?;", (sec_b,)).fetchone()["c"], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM timetable_entries WHERE section_id = ?;", (sec_b,)).fetchone()["c"], 4)
        finally:
            conn.close()

    def test_delete_section_rejects_invalid_or_nonexistent_id(self):
        """POST /sections/delete or /sections/<id>/delete with invalid or nonexistent ID should flash error and not affect DB."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                sec_id = conn.execute("INSERT INTO sections (name) VALUES ('CSE-STAY');").lastrowid
        finally:
            conn.close()

        # 1. Nonexistent section ID in URL path
        res_nonexistent = self.client.post("/sections/99999/delete", follow_redirects=True)
        self.assertEqual(res_nonexistent.status_code, 200)
        self.assertIn(b"Section not found.", res_nonexistent.data)

        # 2. Non-numeric section ID in form body
        res_invalid_str = self.client.post("/sections/delete", data={"section_id": "invalid-id"}, follow_redirects=True)
        self.assertEqual(res_invalid_str.status_code, 200)
        self.assertIn(b"Invalid section ID.", res_invalid_str.data)

        # 3. Empty section ID in form body
        res_empty = self.client.post("/sections/delete", data={"section_id": ""}, follow_redirects=True)
        self.assertEqual(res_empty.status_code, 200)
        self.assertIn(b"Invalid section ID.", res_empty.data)

        # Existing section still exists
        conn = get_db_connection(TEST_DB_PATH)
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM sections WHERE id = ?;", (sec_id,)).fetchone()["c"], 1)
        finally:
            conn.close()

    def test_delete_section_via_form_body_success(self):
        """POST /sections/delete with valid section_id in form payload should delete the section."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                sec_id = conn.execute("INSERT INTO sections (name) VALUES ('CSE-FORM');").lastrowid
        finally:
            conn.close()

        response = self.client.post("/sections/delete", data={"section_id": str(sec_id)}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"deleted successfully", response.data)
        self.assertIn(b"CSE-FORM", response.data)

        conn = get_db_connection(TEST_DB_PATH)
        try:
            self.assertIsNone(conn.execute("SELECT * FROM sections WHERE id = ?;", (sec_id,)).fetchone())
        finally:
            conn.close()

    def test_delete_section_failed_deletion_rolls_back_correctly(self):
        """If an error occurs during section deletion transaction, the transaction rolls back cleanly preserving all records."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                sec_id = conn.execute("INSERT INTO sections (name) VALUES ('CSE-ROLLBACK');").lastrowid
                sub_id = conn.execute("INSERT INTO subjects (code, name) VALUES ('CS101', 'Intro to CS');").lastrowid
                t_id = conn.execute("INSERT INTO teachers (name) VALUES ('Dr. Turing');").lastrowid
                conn.execute("INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?);", (t_id, sub_id))
                conn.execute("INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, 2);", (sec_id, sub_id))
                conn.execute(
                    """
                    INSERT INTO timetable_entries (section_id, teacher_id, subject_id, day_of_week, period)
                    VALUES (?, ?, ?, 'Monday', 1);
                    """,
                    (sec_id, t_id, sub_id),
                )
        finally:
            conn.close()

        # Simulate database failure during transaction (e.g. error executing DELETE FROM sections)
        real_get_db = app.view_functions["delete_section"].__globals__["get_db"]

        class FailingConnectionProxy:
            def __init__(self, target_conn):
                self._conn = target_conn

            def execute(self, sql, *args, **kwargs):
                if "DELETE FROM sections" in sql:
                    raise sqlite3.OperationalError("Simulated database failure during section deletion")
                return self._conn.execute(sql, *args, **kwargs)

            def rollback(self):
                return self._conn.rollback()

            def commit(self):
                return self._conn.commit()

            def close(self):
                return self._conn.close()

            def __enter__(self):
                self._conn.__enter__()
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                return self._conn.__exit__(exc_type, exc_val, exc_tb)

            def __getattr__(self, name):
                return getattr(self._conn, name)

        with patch("app.get_db", side_effect=lambda: FailingConnectionProxy(real_get_db())):
            response = self.client.post(f"/sections/{sec_id}/delete", follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Database error while deleting section", response.data)
            self.assertIn(b"Simulated database failure", response.data)

        # Confirm transaction rolled back: section, requirement, and timetable entry all preserved!
        conn = get_db_connection(TEST_DB_PATH)
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM sections WHERE id = ?;", (sec_id,)).fetchone()["c"], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM section_requirements WHERE section_id = ?;", (sec_id,)).fetchone()["c"], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM timetable_entries WHERE section_id = ?;", (sec_id,)).fetchone()["c"], 1)
        finally:
            conn.close()

    def test_delete_section_marks_timetable_outdated_when_routine_exists(self):
        """When a section scheduled in the timetable is deleted, the timetable must be marked Outdated and not automatically regenerated."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                sec1 = conn.execute("INSERT INTO sections (name) VALUES ('BATCH-1');").lastrowid
                sec2 = conn.execute("INSERT INTO sections (name) VALUES ('BATCH-2');").lastrowid
                sub = conn.execute("INSERT INTO subjects (code, name) VALUES ('CS101', 'Intro to CS');").lastrowid
                t = conn.execute("INSERT INTO teachers (name, email) VALUES ('Dr. Turing', 'turing@ai.org');").lastrowid
                conn.execute("INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?);", (t, sub))
                conn.execute("INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, 2);", (sec1, sub))
                conn.execute("INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, 3);", (sec2, sub))
        finally:
            conn.close()

        # Generate routine -> initially published and up to date
        res_gen = self.client.post("/routine/generate", follow_redirects=True)
        self.assertEqual(res_gen.status_code, 200)
        self.assertIn(b"Published &amp; Up to Date", res_gen.data)

        # Delete Section 1
        res_del = self.client.post(f"/sections/{sec1}/delete", follow_redirects=True)
        self.assertEqual(res_del.status_code, 200)

        # Check GET /routine -> Must display Outdated Timetable warning, never 'Published & Up to Date'
        res_routine = self.client.get("/routine")
        self.assertEqual(res_routine.status_code, 200)
        self.assertIn(b"Outdated Timetable", res_routine.data)
        self.assertIn(b"Timetable Outdated", res_routine.data)
        self.assertIn(b"BATCH-1", res_routine.data)
        self.assertNotIn(b"Published &amp; Up to Date", res_routine.data)

        # Verify timetable entries were NOT silently wiped or regenerated: Batch 2 entries still remain (3 entries)
        conn = get_db_connection(TEST_DB_PATH)
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM timetable_entries WHERE section_id = ?;", (sec2,)).fetchone()["c"], 3)
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM timetable_entries WHERE section_id = ?;", (sec1,)).fetchone()["c"], 0)
        finally:
            conn.close()

        # Regenerating routine restores 'Published & Up to Date' for remaining setup
        res_regen = self.client.post("/routine/generate", follow_redirects=True)
        self.assertEqual(res_regen.status_code, 200)
        self.assertIn(b"Published &amp; Up to Date", res_regen.data)

    def test_delete_section_cannot_be_deleted_through_get_request(self):
        """GET /sections/<id>/delete and GET /sections/delete must return 405 Method Not Allowed and not delete section."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                sec_id = conn.execute("INSERT INTO sections (name) VALUES ('CSE-SAFE');").lastrowid
        finally:
            conn.close()

        # Attempt GET deletion via parameterized path
        res_get_path = self.client.get(f"/sections/{sec_id}/delete")
        self.assertEqual(res_get_path.status_code, 405)

        # Attempt GET deletion via endpoint
        res_get_endpoint = self.client.get("/sections/delete")
        self.assertEqual(res_get_endpoint.status_code, 405)

        # Section must still exist intact in database
        conn = get_db_connection(TEST_DB_PATH)
        try:
            row = conn.execute("SELECT * FROM sections WHERE id = ?;", (sec_id,)).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["name"], "CSE-SAFE")
        finally:
            conn.close()

    # =========================================================================
    # Step 3B Tests: Timetable Generation, Transactions, and Routine Views
    # =========================================================================

    def test_routine_page_loads_empty_state(self):
        """GET /routine should return 200 OK and show empty state when no routine exists."""
        response = self.client.get("/routine")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Weekly Timetable Routine", response.data)
        self.assertIn(b"No Timetable Generated Yet", response.data)
        self.assertIn(b"Generate Timetable Now", response.data)

    def test_generate_routine_success(self):
        """POST /routine/generate should successfully generate, commit, and display routine grid."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                sec_id = conn.execute("INSERT INTO sections (name) VALUES ('CSE-A');").lastrowid
                s1_id = conn.execute("INSERT INTO subjects (code, name) VALUES ('CS101', 'Intro to CS');").lastrowid
                s2_id = conn.execute("INSERT INTO subjects (code, name) VALUES ('MATH101', 'Calculus');").lastrowid
                t1_id = conn.execute("INSERT INTO teachers (name, email) VALUES ('Dr. Ada Lovelace', 'ada@cs.edu');").lastrowid
                t2_id = conn.execute("INSERT INTO teachers (name, email) VALUES ('Prof. Euler', 'euler@math.edu');").lastrowid

                conn.execute("INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?);", (t1_id, s1_id))
                conn.execute("INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?);", (t2_id, s2_id))

                conn.execute("INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, 4);", (sec_id, s1_id))
                conn.execute("INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, 3);", (sec_id, s2_id))
        finally:
            conn.close()

        response = self.client.post("/routine/generate", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Timetable successfully generated and published!", response.data)
        self.assertIn(b"CS101", response.data)
        self.assertIn(b"MATH101", response.data)
        self.assertIn(b"Dr. Ada Lovelace", response.data)
        self.assertIn(b"Prof. Euler", response.data)
        self.assertIn(b"CSE-A", response.data)

        # Direct database verification
        conn = get_db_connection(TEST_DB_PATH)
        try:
            count = conn.execute("SELECT COUNT(*) AS total FROM timetable_entries;").fetchone()["total"]
            self.assertEqual(count, 7)  # 4 + 3 = 7
        finally:
            conn.close()

    def test_generate_routine_teacher_and_section_clash_prevention(self):
        """POST /routine/generate must prevent section and teacher clashes across sections."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                sec1_id = conn.execute("INSERT INTO sections (name) VALUES ('CSE-A');").lastrowid
                sec2_id = conn.execute("INSERT INTO sections (name) VALUES ('CSE-B');").lastrowid
                sub_id = conn.execute("INSERT INTO subjects (code, name) VALUES ('CS101', 'Intro to CS');").lastrowid
                t_id = conn.execute("INSERT INTO teachers (name) VALUES ('Prof. Turing');").lastrowid

                conn.execute("INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?);", (t_id, sub_id))

                conn.execute("INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, 5);", (sec1_id, sub_id))
                conn.execute("INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, 5);", (sec2_id, sub_id))
        finally:
            conn.close()

        response = self.client.post("/routine/generate", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Timetable successfully generated", response.data)

        conn = get_db_connection(TEST_DB_PATH)
        try:
            # 1. Total entries
            total = conn.execute("SELECT COUNT(*) AS total FROM timetable_entries;").fetchone()["total"]
            self.assertEqual(total, 10)

            # 2. Section clash verification: no section has 2 classes in the same (day, period)
            sec_clashes = conn.execute(
                """
                SELECT section_id, day_of_week, period, COUNT(*) AS cnt
                FROM timetable_entries
                GROUP BY section_id, day_of_week, period
                HAVING cnt > 1;
                """
            ).fetchall()
            self.assertEqual(len(sec_clashes), 0, "Section clash detected!")

            # 3. Teacher clash verification: teacher never teaches 2 classes in the same (day, period)
            teacher_clashes = conn.execute(
                """
                SELECT teacher_id, day_of_week, period, COUNT(*) AS cnt
                FROM timetable_entries
                GROUP BY teacher_id, day_of_week, period
                HAVING cnt > 1;
                """
            ).fetchall()
            self.assertEqual(len(teacher_clashes), 0, "Teacher clash detected!")
        finally:
            conn.close()

    def test_generate_routine_failure_missing_qualifications(self):
        """POST /routine/generate should fail and not save partial entries if a subject lacks a teacher."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                sec_id = conn.execute("INSERT INTO sections (name) VALUES ('CSE-A');").lastrowid
                sub_id = conn.execute("INSERT INTO subjects (code, name) VALUES ('CS101', 'Intro to CS');").lastrowid
                # No teacher qualified for CS101!
                conn.execute("INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, 4);", (sec_id, sub_id))
        finally:
            conn.close()

        response = self.client.post("/routine/generate", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Timetable generation failed:", response.data)
        self.assertIn(b"No qualified teacher available", response.data)

        # Verify no entries were saved in timetable_entries
        conn = get_db_connection(TEST_DB_PATH)
        try:
            count = conn.execute("SELECT COUNT(*) AS total FROM timetable_entries;").fetchone()["total"]
            self.assertEqual(count, 0)
        finally:
            conn.close()

    def test_generate_routine_failure_overloaded_section(self):
        """POST /routine/generate should fail and not save partial entries if section requirements are impossible."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                sec_id = conn.execute("INSERT INTO sections (name) VALUES ('CSE-A');").lastrowid
                s1_id = conn.execute("INSERT INTO subjects (code, name) VALUES ('CS101', 'Intro to CS');").lastrowid
                s2_id = conn.execute("INSERT INTO subjects (code, name) VALUES ('MATH101', 'Calculus');").lastrowid
                t_id = conn.execute("INSERT INTO teachers (name) VALUES ('Dr. Ada');").lastrowid
                conn.execute("INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?);", (t_id, s1_id))
                conn.execute("INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?);", (t_id, s2_id))
                # 20 + 15 = 35 periods exceeds maximum 30
                conn.execute("INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, 20);", (sec_id, s1_id))
                conn.execute("INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, 15);", (sec_id, s2_id))
        finally:
            conn.close()

        response = self.client.post("/routine/generate", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Timetable generation failed:", response.data)

        conn = get_db_connection(TEST_DB_PATH)
        try:
            count = conn.execute("SELECT COUNT(*) AS total FROM timetable_entries;").fetchone()["total"]
            self.assertEqual(count, 0)
        finally:
            conn.close()

    def test_generate_routine_replaces_old_entries_atomically(self):
        """POST /routine/generate should replace previous timetable without duplicating entries."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                sec_id = conn.execute("INSERT INTO sections (name) VALUES ('CSE-A');").lastrowid
                sub_id = conn.execute("INSERT INTO subjects (code, name) VALUES ('CS101', 'Intro to CS');").lastrowid
                t_id = conn.execute("INSERT INTO teachers (name) VALUES ('Dr. Ada');").lastrowid
                conn.execute("INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?);", (t_id, sub_id))
                conn.execute("INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, 4);", (sec_id, sub_id))
        finally:
            conn.close()

        # Run 1: generate 4 periods
        res1 = self.client.post("/routine/generate", follow_redirects=True)
        self.assertEqual(res1.status_code, 200)

        conn = get_db_connection(TEST_DB_PATH)
        try:
            count1 = conn.execute("SELECT COUNT(*) AS total FROM timetable_entries;").fetchone()["total"]
            self.assertEqual(count1, 4)
        finally:
            conn.close()

        # Update requirement to 6 periods
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                conn.execute("UPDATE section_requirements SET weekly_periods = 6 WHERE section_id = ?;", (sec_id,))
        finally:
            conn.close()

        # Run 2: regenerate
        res2 = self.client.post("/routine/generate", follow_redirects=True)
        self.assertEqual(res2.status_code, 200)

        conn = get_db_connection(TEST_DB_PATH)
        try:
            count2 = conn.execute("SELECT COUNT(*) AS total FROM timetable_entries;").fetchone()["total"]
            self.assertEqual(count2, 6)  # Exactly 6, not 4 + 6 = 10!
        finally:
            conn.close()

    def test_generate_routine_transaction_rollback_on_db_error(self):
        """If a database error occurs during insertion, the transaction rolls back cleanly without losing old timetable."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                sec_id = conn.execute("INSERT INTO sections (name) VALUES ('CSE-A');").lastrowid
                sub_id = conn.execute("INSERT INTO subjects (code, name) VALUES ('CS101', 'Intro to CS');").lastrowid
                t_id = conn.execute("INSERT INTO teachers (name) VALUES ('Dr. Ada');").lastrowid
                conn.execute("INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?);", (t_id, sub_id))
                conn.execute("INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, 4);", (sec_id, sub_id))
                # Insert initial timetable entry
                conn.execute(
                    """
                    INSERT INTO timetable_entries (section_id, teacher_id, subject_id, day_of_week, period)
                    VALUES (?, ?, ?, 'Monday', 1);
                    """,
                    (sec_id, t_id, sub_id),
                )
        finally:
            conn.close()

        # Simulate a database constraint failure by mocking generate_schedule with an invalid entry
        from scheduler import ScheduleResult
        malformed_result = ScheduleResult(
            success=True,
            entries=[
                # Invalid foreign key IDs (99999) and invalid day 'InvalidDay' will trigger SQLite constraint violation
                {"section_id": 99999, "teacher_id": 99999, "subject_id": 99999, "day_of_week": "InvalidDay", "period": 99}
            ]
        )

        with patch("app.generate_schedule", return_value=malformed_result):
            response = self.client.post("/routine/generate", follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Database error while saving timetable:", response.data)

        # Verify transaction rollback preserved the previous timetable entry
        conn = get_db_connection(TEST_DB_PATH)
        try:
            count = conn.execute("SELECT COUNT(*) AS total FROM timetable_entries;").fetchone()["total"]
            self.assertEqual(count, 1)  # Preserved!
        finally:
            conn.close()

    def test_dashboard_entries_count_reflects_routine(self):
        """GET / should dynamically show the number of scheduled routine entries."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                sec_id = conn.execute("INSERT INTO sections (name) VALUES ('CSE-A');").lastrowid
                sub_id = conn.execute("INSERT INTO subjects (code, name) VALUES ('CS101', 'Intro to CS');").lastrowid
                t_id = conn.execute("INSERT INTO teachers (name) VALUES ('Dr. Ada');").lastrowid
                conn.execute("INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?);", (t_id, sub_id))
                conn.execute("INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, 5);", (sec_id, sub_id))
        finally:
            conn.close()

        self.client.post("/routine/generate", follow_redirects=True)

        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Scheduled Entries", response.data)
        self.assertIn(b">5<", response.data)

    def test_unqualified_subject_regeneration_fails_and_preserves_old_entries(self):
        """
        Regression test:
        When a requirement has no qualified teacher:
        1. Generation must fail with subject- and section-specific error.
        2. No partial entries are inserted.
        3. Previously saved timetable entries remain unchanged (safety behavior).
        4. The UI clearly communicates that the existing timetable is outdated / generation failed.
        5. The UI does not label the old timetable as 'Published & Up to Date'.
        6. The dashboard count continues to reflect stored entries.
        7. When a qualified teacher is provided, regeneration succeeds and replaces the timetable atomically.
        """
        # Step 1: Initial valid setup (CSE-A has 4 periods of CS101, taught by Dr. Ada)
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                sec_id = conn.execute("INSERT INTO sections (name) VALUES ('CSE-A');").lastrowid
                cs_id = conn.execute("INSERT INTO subjects (code, name) VALUES ('CS101', 'Intro to CS');").lastrowid
                t_ada = conn.execute("INSERT INTO teachers (name, email) VALUES ('Dr. Ada', 'ada@cs.edu');").lastrowid
                conn.execute("INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?);", (t_ada, cs_id))
                conn.execute("INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, 4);", (sec_id, cs_id))
        finally:
            conn.close()

        # Generate initial timetable
        res_initial = self.client.post("/routine/generate", follow_redirects=True)
        self.assertEqual(res_initial.status_code, 200)
        self.assertIn(b"Timetable successfully generated and published!", res_initial.data)
        self.assertIn(b"Published &amp; Up to Date", res_initial.data)

        conn = get_db_connection(TEST_DB_PATH)
        try:
            initial_count = conn.execute("SELECT COUNT(*) AS total FROM timetable_entries;").fetchone()["total"]
            self.assertEqual(initial_count, 4)
        finally:
            conn.close()

        # Step 2: Add a new subject requirement with NO qualified teacher assigned
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                phy_id = conn.execute("INSERT INTO subjects (code, name) VALUES ('PHY101', 'Physics');").lastrowid
                # No teacher added to teacher_subjects for PHY101!
                conn.execute("INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, 2);", (sec_id, phy_id))
        finally:
            conn.close()

        # Step 3: User clicks 'Regenerate Routine'
        res_regen = self.client.post("/routine/generate", follow_redirects=True)
        self.assertEqual(res_regen.status_code, 200)

        # Requirement 1: Generation fails with clear subject- and section-specific error
        self.assertIn(b"Timetable generation failed:", res_regen.data)
        self.assertIn(b"PHY101", res_regen.data)
        self.assertIn(b"CSE-A", res_regen.data)
        self.assertIn(b"No qualified teacher available for subject", res_regen.data)

        # Requirement 2 & 3: No partial entries saved, previous 4 entries completely preserved
        conn = get_db_connection(TEST_DB_PATH)
        try:
            count_after_fail = conn.execute("SELECT COUNT(*) AS total FROM timetable_entries;").fetchone()["total"]
            self.assertEqual(count_after_fail, 4, "Previous entries were deleted or partial entries were inserted!")

            # Verify no PHY101 entries exist
            phy_entries = conn.execute("SELECT COUNT(*) AS total FROM timetable_entries WHERE subject_id = ?;", (phy_id,)).fetchone()["total"]
            self.assertEqual(phy_entries, 0, "Partial PHY101 entries were erroneously inserted!")
        finally:
            conn.close()

        # Requirement 4: UI clearly communicates the timetable is outdated and that latest generation failed
        self.assertIn(b"Outdated Timetable", res_regen.data)
        self.assertIn(b"Timetable Outdated", res_regen.data)
        self.assertIn(b"Latest Generation Attempt Failed:", res_regen.data)
        self.assertNotIn(b"Published &amp; Up to Date", res_regen.data)

        # Requirement 6: Dashboard count continues to reflect exactly the 4 stored entries
        res_dash = self.client.get("/")
        self.assertEqual(res_dash.status_code, 200)
        self.assertIn(b">4<", res_dash.data)

        # Step 4: Now add a qualified teacher for PHY101
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                t_newton = conn.execute("INSERT INTO teachers (name, email) VALUES ('Dr. Newton', 'newton@sci.edu');").lastrowid
                conn.execute("INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?);", (t_newton, phy_id))
        finally:
            conn.close()

        # Step 5: Regenerate routine with valid configuration
        res_success = self.client.post("/routine/generate", follow_redirects=True)
        self.assertEqual(res_success.status_code, 200)
        self.assertIn(b"Timetable successfully generated and published!", res_success.data)
        self.assertIn(b"Published &amp; Up to Date", res_success.data)
        self.assertIn(b"6 total periods", res_success.data)

        # Total entries updated to 6 (4 + 2)
        conn = get_db_connection(TEST_DB_PATH)
        try:
            final_count = conn.execute("SELECT COUNT(*) AS total FROM timetable_entries;").fetchone()["total"]
            self.assertEqual(final_count, 6)
        finally:
            conn.close()

    def test_ui_communicates_outdated_routine_when_requirements_change_without_regeneration(self):
        """GET /routine should show outdated warning if setup was changed after timetable was generated."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                sec_id = conn.execute("INSERT INTO sections (name) VALUES ('CSE-A');").lastrowid
                cs_id = conn.execute("INSERT INTO subjects (code, name) VALUES ('CS101', 'Intro to CS');").lastrowid
                t_ada = conn.execute("INSERT INTO teachers (name, email) VALUES ('Dr. Ada', 'ada@cs.edu');").lastrowid
                conn.execute("INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?);", (t_ada, cs_id))
                conn.execute("INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, 4);", (sec_id, cs_id))
        finally:
            conn.close()

        # Generate routine -> initially up to date
        self.client.post("/routine/generate", follow_redirects=True)

        # Modify requirements directly in setup (e.g. change CS101 from 4 to 6 periods)
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                conn.execute("UPDATE section_requirements SET weekly_periods = 6 WHERE section_id = ?;", (sec_id,))
        finally:
            conn.close()

        # Visit GET /routine
        res = self.client.get("/routine")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Outdated Timetable", res.data)
        self.assertIn(b"Requirements mismatch", res.data)
        self.assertNotIn(b"Published &amp; Up to Date", res.data)


class TestTimetablePdfExport(unittest.TestCase):
    """
    Comprehensive tests for the Timetable PDF Export feature:
    - Valid section PDF export and downloading.
    - PDF response content type and disposition download filename.
    - Section-specific timetable data present in generated PDF.
    - Data isolation between multiple sections in exported PDFs.
    - Graceful handling of missing or invalid section IDs.
    - Rejection of export when no timetable has been generated or for sections without entries.
    - Timetable freshness enforcement: blocking export when timetable is outdated.
    - Guarantee that PDF export does not modify timetable entries or invoke the scheduler.
    - Strict HTTP GET enforcement (rejecting POST with 405 Method Not Allowed).
    - UI rendering of Download PDF buttons and dropdowns on the Routine page.
    """

    @classmethod
    def setUpClass(cls):
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

    def _setup_single_section_routine(self):
        """Helper to create Section CSE-A, Subject CS101, Teacher Dr. Ada, 4 periods, and publish routine."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                sec_id = conn.execute("INSERT INTO sections (name) VALUES ('CSE-A');").lastrowid
                cs_id = conn.execute("INSERT INTO subjects (code, name) VALUES ('CS101', 'Intro to Computer Science');").lastrowid
                t_id = conn.execute("INSERT INTO teachers (name, email) VALUES ('Dr. Ada Lovelace', 'ada@cs.edu');").lastrowid
                conn.execute("INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?);", (t_id, cs_id))
                conn.execute("INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, 4);", (sec_id, cs_id))
        finally:
            conn.close()

        res = self.client.post("/routine/generate", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        return sec_id, cs_id, t_id

    def test_export_valid_timetable_for_section(self):
        """GET /routine/export/<id> should return 200 with PDF mimetype, attachment header, and correct layout data."""
        sec_id, _, _ = self._setup_single_section_routine()

        res = self.client.get(f"/routine/export/{sec_id}")
        self.assertEqual(res.status_code, 200)

        # 1. Correct headers
        self.assertEqual(res.headers.get("Content-Type"), "application/pdf")
        disposition = res.headers.get("Content-Disposition", "")
        self.assertIn("attachment", disposition)
        self.assertIn("Routine_Section_CSE-A.pdf", disposition)

        # 2. PDF binary format validation
        pdf_bytes = res.data
        self.assertTrue(pdf_bytes.startswith(b"%PDF"), "Response is not a valid PDF binary")

        # 3. Document contents
        self.assertIn(b"Smart Routine Generator", pdf_bytes)
        self.assertIn(b"CSE-A", pdf_bytes)
        self.assertIn(b"CS101", pdf_bytes)
        self.assertIn(b"Dr. Ada Lovelace", pdf_bytes)
        self.assertIn(b"Monday", pdf_bytes)
        self.assertIn(b"Period 1", pdf_bytes)
        self.assertIn(b"Period 6", pdf_bytes)
        self.assertIn(b"Free", pdf_bytes)

    def test_export_pdf_via_query_parameter(self):
        """GET /routine/export?section_id=<id> should successfully export the timetable."""
        sec_id, _, _ = self._setup_single_section_routine()

        res = self.client.get(f"/routine/export?section_id={sec_id}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("Content-Type"), "application/pdf")
        self.assertIn("Routine_Section_CSE-A.pdf", res.headers.get("Content-Disposition", ""))
        self.assertTrue(res.data.startswith(b"%PDF"))

    def test_export_pdf_section_specific_data_isolation(self):
        """Exported PDF should only contain data for the requested section and isolate it from other sections."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                sec_1 = conn.execute("INSERT INTO sections (name) VALUES ('Section-One');").lastrowid
                sec_2 = conn.execute("INSERT INTO sections (name) VALUES ('Section-Two');").lastrowid
                sub_1 = conn.execute("INSERT INTO subjects (code, name) VALUES ('CS101', 'Intro to CS');").lastrowid
                sub_2 = conn.execute("INSERT INTO subjects (code, name) VALUES ('MATH201', 'Calculus');").lastrowid
                t_1 = conn.execute("INSERT INTO teachers (name, email) VALUES ('Dr. Alan Turing', 'turing@cs.edu');").lastrowid
                t_2 = conn.execute("INSERT INTO teachers (name, email) VALUES ('Dr. Carl Gauss', 'gauss@math.edu');").lastrowid
                conn.execute("INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?);", (t_1, sub_1))
                conn.execute("INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?);", (t_2, sub_2))
                conn.execute("INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, 3);", (sec_1, sub_1))
                conn.execute("INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, 3);", (sec_2, sub_2))
        finally:
            conn.close()

        res_gen = self.client.post("/routine/generate", follow_redirects=True)
        self.assertEqual(res_gen.status_code, 200)

        # Export Section-One
        res_one = self.client.get(f"/routine/export/{sec_1}")
        self.assertEqual(res_one.status_code, 200)
        self.assertIn(b"Section-One", res_one.data)
        self.assertIn(b"CS101", res_one.data)
        self.assertIn(b"Alan Turing", res_one.data)
        self.assertNotIn(b"Section-Two", res_one.data)
        self.assertNotIn(b"MATH201", res_one.data)
        self.assertNotIn(b"Carl Gauss", res_one.data)

        # Export Section-Two
        res_two = self.client.get(f"/routine/export/{sec_2}")
        self.assertEqual(res_two.status_code, 200)
        self.assertIn(b"Section-Two", res_two.data)
        self.assertIn(b"MATH201", res_two.data)
        self.assertIn(b"Carl Gauss", res_two.data)
        self.assertNotIn(b"Section-One", res_two.data)
        self.assertNotIn(b"CS101", res_two.data)
        self.assertNotIn(b"Alan Turing", res_two.data)

    def test_export_pdf_missing_or_invalid_section_ids(self):
        """Invalid, nonexistent, or missing section IDs should be rejected with flash error and redirected to /routine."""
        self._setup_single_section_routine()

        # 1. Nonexistent section ID
        res_nonexistent = self.client.get("/routine/export/99999", follow_redirects=True)
        self.assertEqual(res_nonexistent.status_code, 200)
        self.assertIn(b"Section not found.", res_nonexistent.data)

        # 2. Negative section ID
        res_neg = self.client.get("/routine/export/-1", follow_redirects=True)
        self.assertEqual(res_neg.status_code, 200)
        self.assertIn(b"Invalid section ID provided for PDF export.", res_neg.data)

        # 3. Zero section ID
        res_zero = self.client.get("/routine/export/0", follow_redirects=True)
        self.assertEqual(res_zero.status_code, 200)
        self.assertIn(b"Invalid section ID provided for PDF export.", res_zero.data)

        # 4. Non-numeric section ID via query param
        res_str = self.client.get("/routine/export?section_id=invalid_text", follow_redirects=True)
        self.assertEqual(res_str.status_code, 200)
        self.assertIn(b"Invalid section ID provided for PDF export.", res_str.data)

        # 5. Missing query parameter entirely
        res_empty = self.client.get("/routine/export", follow_redirects=True)
        self.assertEqual(res_empty.status_code, 200)
        self.assertIn(b"Please select a section to export.", res_empty.data)

    def test_export_pdf_when_no_timetable_generated(self):
        """Export should be blocked with an informative message when no timetable has been generated yet."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                sec_id = conn.execute("INSERT INTO sections (name) VALUES ('CSE-NEW');").lastrowid
        finally:
            conn.close()

        res = self.client.get(f"/routine/export/{sec_id}", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"No timetable has been generated yet. Please generate the timetable before exporting.", res.data)

    def test_export_pdf_blocked_when_timetable_is_outdated_by_requirements_change(self):
        """When setup requirements change after generation, PDF export must be blocked with an outdated error."""
        sec_id, _, _ = self._setup_single_section_routine()

        # Alter requirements directly without regenerating timetable
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                conn.execute("UPDATE section_requirements SET weekly_periods = 8 WHERE section_id = ?;", (sec_id,))
        finally:
            conn.close()

        res = self.client.get(f"/routine/export/{sec_id}", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Cannot export PDF: Timetable is outdated", res.data)
        self.assertIn(b"Please regenerate the timetable first.", res.data)

    def test_export_pdf_blocked_when_session_marks_timetable_outdated(self):
        """When session marks timetable as outdated (e.g. deletion of a teacher/section), export must be blocked."""
        sec_id, _, _ = self._setup_single_section_routine()

        with self.client.session_transaction() as sess:
            sess["timetable_outdated"] = True
            sess["outdated_reasons"] = ["A section was deleted, invalidating timetable slots."]

        res = self.client.get(f"/routine/export/{sec_id}", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Cannot export PDF: Timetable is outdated", res.data)
        self.assertIn(b"Please regenerate the timetable first.", res.data)

    def test_export_pdf_blocked_when_last_generation_failed(self):
        """When the previous generation attempt failed, PDF export must be blocked."""
        sec_id, _, _ = self._setup_single_section_routine()

        with self.client.session_transaction() as sess:
            sess["last_generation_error"] = "No qualified teacher available for subject PHY101"

        res = self.client.get(f"/routine/export/{sec_id}", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Cannot export PDF: Timetable is outdated", res.data)
        self.assertIn(b"Last generation attempt failed", res.data)

    def test_export_pdf_does_not_modify_timetable_entries_or_trigger_scheduling(self):
        """PDF export must be purely read-only: never invoke generate_schedule() or modify SQLite records."""
        sec_id, _, _ = self._setup_single_section_routine()

        # Capture exact database state before export
        conn = get_db_connection(TEST_DB_PATH)
        try:
            entries_before = conn.execute(
                "SELECT id, section_id, teacher_id, subject_id, day_of_week, period FROM timetable_entries ORDER BY id;"
            ).fetchall()
            entries_before_list = [dict(r) for r in entries_before]
            self.assertEqual(len(entries_before_list), 4)
        finally:
            conn.close()

        # Patch generate_schedule in app to verify it is NEVER invoked during PDF export
        with patch("app.generate_schedule", side_effect=RuntimeError("Scheduler was invoked during PDF export!")):
            res = self.client.get(f"/routine/export/{sec_id}")
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.headers.get("Content-Type"), "application/pdf")

        # Verify database state after export is completely untouched
        conn = get_db_connection(TEST_DB_PATH)
        try:
            entries_after = conn.execute(
                "SELECT id, section_id, teacher_id, subject_id, day_of_week, period FROM timetable_entries ORDER BY id;"
            ).fetchall()
            entries_after_list = [dict(r) for r in entries_after]
            self.assertEqual(entries_before_list, entries_after_list)
        finally:
            conn.close()

    def test_export_pdf_post_request_rejected_with_405(self):
        """PDF export is strictly a GET endpoint; POST requests must be rejected with 405 Method Not Allowed."""
        sec_id, _, _ = self._setup_single_section_routine()

        res = self.client.post(f"/routine/export/{sec_id}")
        self.assertEqual(res.status_code, 405)

    def test_routine_page_renders_download_pdf_button(self):
        """Routine page should display the Download PDF button when a timetable is published."""
        sec_id, _, _ = self._setup_single_section_routine()

        res = self.client.get("/routine")
        self.assertEqual(res.status_code, 200)
        html = res.data.decode("utf-8")

        self.assertIn("Download PDF", html)
        self.assertIn(f"/routine/export/{sec_id}", html)

    def test_routine_page_renders_disabled_download_pdf_when_outdated(self):
        """Routine page should show disabled Download PDF button when the timetable is outdated."""
        sec_id, _, _ = self._setup_single_section_routine()

        # Invalidate freshness
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                conn.execute("UPDATE section_requirements SET weekly_periods = 10 WHERE section_id = ?;", (sec_id,))
        finally:
            conn.close()

        res = self.client.get("/routine")
        self.assertEqual(res.status_code, 200)
        html = res.data.decode("utf-8")

        self.assertIn("Download PDF", html)
        self.assertIn("disabled", html)
        self.assertIn("Timetable is outdated. Please regenerate before downloading PDF.", html)


class TestSectionRequirementEditAndDelete(unittest.TestCase):
    """
    Comprehensive tests for editing and deleting individual section subject requirements:
    - Editing an individual requirement's weekly period count.
    - Resolving requirement ID from path or form body.
    - Rejecting invalid period counts (non-integer, <= 0, > 30, empty).
    - Enforcing cumulative 30-period section capacity limit on edit.
    - Handling nonexistent or invalid requirement IDs gracefully.
    - Marking timetable as outdated when editing affects the routine, while preserving entries.
    - Deleting an individual requirement and verifying isolated removal (other requirements, subjects, sections untouched).
    - Preserving existing timetable entries upon requirement deletion while tagging the timetable as outdated.
    - Preventing GET requests from modifying data (405 Method Not Allowed).
    - UI rendering of Edit and Delete buttons and modals beside each requirement.
    """

    @classmethod
    def setUpClass(cls):
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

    def _setup_section_and_requirements(self):
        """Helper to create Section CSE-A with CS101 (4 periods) and MATH201 (6 periods)."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                sec_id = conn.execute("INSERT INTO sections (name) VALUES ('CSE-A');").lastrowid
                sub1_id = conn.execute("INSERT INTO subjects (code, name) VALUES ('CS101', 'Intro to CS');").lastrowid
                sub2_id = conn.execute("INSERT INTO subjects (code, name) VALUES ('MATH201', 'Calculus');").lastrowid
                req1_id = conn.execute(
                    "INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, 4);",
                    (sec_id, sub1_id),
                ).lastrowid
                req2_id = conn.execute(
                    "INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, 6);",
                    (sec_id, sub2_id),
                ).lastrowid
        finally:
            conn.close()
        return sec_id, sub1_id, sub2_id, req1_id, req2_id

    def test_edit_requirement_success(self):
        """POST /requirements/<id>/edit should update weekly periods, recalculate section load, and flash success."""
        sec_id, sub1_id, sub2_id, req1_id, req2_id = self._setup_section_and_requirements()

        response = self.client.post(
            f"/requirements/{req1_id}/edit",
            data={"weekly_periods": "8"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Updated &#39;CS101&#39; requirement for Section &#39;CSE-A&#39; to 8 weekly period(s)", response.data)
        self.assertIn(b"Total: 14/30 periods", response.data)

        # Verify database record updated
        conn = get_db_connection(TEST_DB_PATH)
        try:
            row = conn.execute("SELECT weekly_periods FROM section_requirements WHERE id = ?;", (req1_id,)).fetchone()
            self.assertEqual(row["weekly_periods"], 8)

            # Other requirement unchanged
            other_row = conn.execute("SELECT weekly_periods FROM section_requirements WHERE id = ?;", (req2_id,)).fetchone()
            self.assertEqual(other_row["weekly_periods"], 6)
        finally:
            conn.close()

    def test_edit_requirement_form_body_resolution(self):
        """POST /requirements/edit with requirement_id in form body should correctly update the record."""
        sec_id, sub1_id, sub2_id, req1_id, req2_id = self._setup_section_and_requirements()

        response = self.client.post(
            "/requirements/edit",
            data={"requirement_id": str(req1_id), "weekly_periods": "5"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Updated &#39;CS101&#39; requirement", response.data)

        conn = get_db_connection(TEST_DB_PATH)
        try:
            row = conn.execute("SELECT weekly_periods FROM section_requirements WHERE id = ?;", (req1_id,)).fetchone()
            self.assertEqual(row["weekly_periods"], 5)
        finally:
            conn.close()

    def test_edit_requirement_rejects_invalid_period_counts(self):
        """POST /requirements/<id>/edit should reject non-integer, <= 0, > 30, and empty weekly periods."""
        sec_id, sub1_id, sub2_id, req1_id, req2_id = self._setup_section_and_requirements()

        invalid_inputs = [
            ("abc", b"Weekly periods must be a valid integer."),
            ("0", b"Weekly periods must be between 1 and 30."),
            ("-4", b"Weekly periods must be between 1 and 30."),
            ("31", b"Weekly periods must be between 1 and 30."),
            ("", b"Weekly periods count is required."),
        ]

        for val, expected_msg in invalid_inputs:
            with self.subTest(val=val):
                res = self.client.post(
                    f"/requirements/{req1_id}/edit",
                    data={"weekly_periods": val},
                    follow_redirects=True,
                )
                self.assertEqual(res.status_code, 200)
                self.assertIn(expected_msg, res.data)

        # Database record should remain untouched at original 4 periods
        conn = get_db_connection(TEST_DB_PATH)
        try:
            row = conn.execute("SELECT weekly_periods FROM section_requirements WHERE id = ?;", (req1_id,)).fetchone()
            self.assertEqual(row["weekly_periods"], 4)
        finally:
            conn.close()

    def test_edit_requirement_enforces_30_period_cumulative_limit(self):
        """Editing requirement to exceed 30 periods across section should be rejected."""
        sec_id, sub1_id, sub2_id, req1_id, req2_id = self._setup_section_and_requirements()

        # Other requirement has 6 periods. Trying to set 25 periods -> 6 + 25 = 31 > 30
        res = self.client.post(
            f"/requirements/{req1_id}/edit",
            data={"weekly_periods": "25"},
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Cannot set 25 periods", res.data)
        self.assertIn(b"other requirements totaling 6/30 periods", res.data)
        self.assertIn(b"Only 24 period(s) remaining", res.data)

        # Confirm value was not updated
        conn = get_db_connection(TEST_DB_PATH)
        try:
            row = conn.execute("SELECT weekly_periods FROM section_requirements WHERE id = ?;", (req1_id,)).fetchone()
            self.assertEqual(row["weekly_periods"], 4)
        finally:
            conn.close()

    def test_edit_requirement_exact_30_periods_allowed(self):
        """Editing requirement such that section reaches exactly 30 total periods should succeed."""
        sec_id, sub1_id, sub2_id, req1_id, req2_id = self._setup_section_and_requirements()

        # Other requirement has 6 periods. Setting 24 periods -> 6 + 24 = 30
        res = self.client.post(
            f"/requirements/{req1_id}/edit",
            data={"weekly_periods": "24"},
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Total: 30/30 periods", res.data)

        conn = get_db_connection(TEST_DB_PATH)
        try:
            row = conn.execute("SELECT weekly_periods FROM section_requirements WHERE id = ?;", (req1_id,)).fetchone()
            self.assertEqual(row["weekly_periods"], 24)
        finally:
            conn.close()

    def test_edit_requirement_nonexistent_or_invalid_id(self):
        """Editing nonexistent or invalid requirement IDs should flash error and redirect."""
        res_nonexistent = self.client.post(
            "/requirements/99999/edit",
            data={"weekly_periods": "5"},
            follow_redirects=True,
        )
        self.assertEqual(res_nonexistent.status_code, 200)
        self.assertIn(b"Requirement not found.", res_nonexistent.data)

        res_invalid_str = self.client.post(
            "/requirements/edit",
            data={"requirement_id": "invalid_id", "weekly_periods": "5"},
            follow_redirects=True,
        )
        self.assertEqual(res_invalid_str.status_code, 200)
        self.assertIn(b"Invalid requirement ID.", res_invalid_str.data)

        res_negative = self.client.post(
            "/requirements/edit",
            data={"requirement_id": "-5", "weekly_periods": "5"},
            follow_redirects=True,
        )
        self.assertEqual(res_negative.status_code, 200)
        self.assertIn(b"Invalid requirement ID.", res_negative.data)

    def test_edit_requirement_marks_timetable_outdated_and_preserves_entries(self):
        """When an edited requirement affects a published timetable, the timetable must be marked outdated and entries preserved."""
        sec_id, sub1_id, sub2_id, req1_id, req2_id = self._setup_section_and_requirements()

        # Add teacher qualified for both subjects
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                t_id = conn.execute("INSERT INTO teachers (name, email) VALUES ('Dr. Ada', 'ada@cs.edu');").lastrowid
                conn.execute("INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?);", (t_id, sub1_id))
                conn.execute("INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?);", (t_id, sub2_id))
        finally:
            conn.close()

        # Generate routine -> 10 total periods (4 + 6)
        res_gen = self.client.post("/routine/generate", follow_redirects=True)
        self.assertEqual(res_gen.status_code, 200)
        self.assertIn(b"Published &amp; Up to Date", res_gen.data)

        # Edit CS101 requirement from 4 to 7 periods
        res_edit = self.client.post(
            f"/requirements/{req1_id}/edit",
            data={"weekly_periods": "7"},
            follow_redirects=True,
        )
        self.assertEqual(res_edit.status_code, 200)

        # Timetable entries in DB must be preserved (still 10 rows)
        conn = get_db_connection(TEST_DB_PATH)
        try:
            entries_count = conn.execute("SELECT COUNT(*) AS total FROM timetable_entries;").fetchone()["total"]
            self.assertEqual(entries_count, 10, "Existing timetable entries must be preserved until user regenerates!")
        finally:
            conn.close()

        # Routine page should display Outdated Timetable warning
        res_routine = self.client.get("/routine")
        self.assertEqual(res_routine.status_code, 200)
        self.assertIn(b"Outdated Timetable", res_routine.data)
        self.assertNotIn(b"Published &amp; Up to Date", res_routine.data)

        # PDF export must be blocked
        res_pdf = self.client.get(f"/routine/export/{sec_id}", follow_redirects=True)
        self.assertEqual(res_pdf.status_code, 200)
        self.assertIn(b"Cannot export PDF: Timetable is outdated", res_pdf.data)

    def test_delete_requirement_success_and_preserves_other_records(self):
        """Deleting an individual requirement should remove only that record, preserving other requirements, subjects, and sections."""
        sec_id, sub1_id, sub2_id, req1_id, req2_id = self._setup_section_and_requirements()

        # Also add another section with requirements
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                sec2_id = conn.execute("INSERT INTO sections (name) VALUES ('CSE-B');").lastrowid
                req_b_id = conn.execute(
                    "INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, 4);",
                    (sec2_id, sub1_id),
                ).lastrowid
        finally:
            conn.close()

        # Delete req1_id (CS101 in CSE-A)
        response = self.client.post(f"/requirements/{req1_id}/delete", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Removed requirement of 4 weekly period(s) of &#39;CS101&#39; from Section &#39;CSE-A&#39;.", response.data)

        # Check DB state
        conn = get_db_connection(TEST_DB_PATH)
        try:
            # Deleted requirement is gone
            r1 = conn.execute("SELECT * FROM section_requirements WHERE id = ?;", (req1_id,)).fetchone()
            self.assertIsNone(r1)

            # Other requirement for CSE-A still exists
            r2 = conn.execute("SELECT * FROM section_requirements WHERE id = ?;", (req2_id,)).fetchone()
            self.assertIsNotNone(r2)
            self.assertEqual(r2["weekly_periods"], 6)

            # Requirement for CSE-B still exists
            rb = conn.execute("SELECT * FROM section_requirements WHERE id = ?;", (req_b_id,)).fetchone()
            self.assertIsNotNone(rb)

            # Both sections and subjects still exist
            self.assertIsNotNone(conn.execute("SELECT * FROM sections WHERE id = ?;", (sec_id,)).fetchone())
            self.assertIsNotNone(conn.execute("SELECT * FROM sections WHERE id = ?;", (sec2_id,)).fetchone())
            self.assertIsNotNone(conn.execute("SELECT * FROM subjects WHERE id = ?;", (sub1_id,)).fetchone())
            self.assertIsNotNone(conn.execute("SELECT * FROM subjects WHERE id = ?;", (sub2_id,)).fetchone())
        finally:
            conn.close()

    def test_delete_requirement_form_body_resolution(self):
        """POST /requirements/delete with requirement_id in form body should delete the record."""
        sec_id, sub1_id, sub2_id, req1_id, req2_id = self._setup_section_and_requirements()

        response = self.client.post(
            "/requirements/delete",
            data={"requirement_id": str(req1_id)},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Removed requirement", response.data)

        conn = get_db_connection(TEST_DB_PATH)
        try:
            row = conn.execute("SELECT * FROM section_requirements WHERE id = ?;", (req1_id,)).fetchone()
            self.assertIsNone(row)
        finally:
            conn.close()

    def test_delete_requirement_nonexistent_or_invalid_id(self):
        """Deleting nonexistent or invalid requirement IDs should flash error and redirect."""
        res_nonexistent = self.client.post("/requirements/99999/delete", follow_redirects=True)
        self.assertEqual(res_nonexistent.status_code, 200)
        self.assertIn(b"Requirement not found.", res_nonexistent.data)

        res_invalid_str = self.client.post(
            "/requirements/delete",
            data={"requirement_id": "not_an_int"},
            follow_redirects=True,
        )
        self.assertEqual(res_invalid_str.status_code, 200)
        self.assertIn(b"Invalid requirement ID.", res_invalid_str.data)

        res_negative = self.client.post(
            "/requirements/delete",
            data={"requirement_id": "-1"},
            follow_redirects=True,
        )
        self.assertEqual(res_negative.status_code, 200)
        self.assertIn(b"Invalid requirement ID.", res_negative.data)

    def test_delete_requirement_marks_timetable_outdated_and_preserves_entries(self):
        """Deleting a requirement when a timetable is published should mark routine outdated while preserving timetable entries."""
        sec_id, sub1_id, sub2_id, req1_id, req2_id = self._setup_section_and_requirements()

        # Add teacher qualified for both subjects
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                t_id = conn.execute("INSERT INTO teachers (name, email) VALUES ('Dr. Ada', 'ada@cs.edu');").lastrowid
                conn.execute("INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?);", (t_id, sub1_id))
                conn.execute("INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?);", (t_id, sub2_id))
        finally:
            conn.close()

        # Generate routine -> 10 entries scheduled
        self.client.post("/routine/generate", follow_redirects=True)

        # Delete req1_id
        res_del = self.client.post(f"/requirements/{req1_id}/delete", follow_redirects=True)
        self.assertEqual(res_del.status_code, 200)

        # Timetable entries are PRESERVED (still 10 rows)
        conn = get_db_connection(TEST_DB_PATH)
        try:
            entries_count = conn.execute("SELECT COUNT(*) AS total FROM timetable_entries;").fetchone()["total"]
            self.assertEqual(entries_count, 10, "Timetable entries must be preserved until user regenerates!")
        finally:
            conn.close()

        # Routine page shows Outdated Timetable
        res_routine = self.client.get("/routine")
        self.assertEqual(res_routine.status_code, 200)
        self.assertIn(b"Outdated Timetable", res_routine.data)

        # PDF export blocked
        res_pdf = self.client.get(f"/routine/export/{sec_id}", follow_redirects=True)
        self.assertEqual(res_pdf.status_code, 200)
        self.assertIn(b"Cannot export PDF: Timetable is outdated", res_pdf.data)

    def test_edit_and_delete_requirement_reject_get_requests(self):
        """GET requests to edit or delete requirement endpoints must return 405 Method Not Allowed."""
        sec_id, sub1_id, sub2_id, req1_id, req2_id = self._setup_section_and_requirements()

        # GET on item routes
        res_edit = self.client.get(f"/requirements/{req1_id}/edit")
        self.assertEqual(res_edit.status_code, 405)

        res_del = self.client.get(f"/requirements/{req1_id}/delete")
        self.assertEqual(res_del.status_code, 405)

        # GET on base routes
        res_edit_base = self.client.get("/requirements/edit")
        self.assertEqual(res_edit_base.status_code, 405)

        res_del_base = self.client.get("/requirements/delete")
        self.assertEqual(res_del_base.status_code, 405)

    def test_ui_renders_edit_and_delete_controls_for_individual_requirements(self):
        """Academic setup page should display Edit and Delete controls and modals beside each requirement."""
        sec_id, sub1_id, sub2_id, req1_id, req2_id = self._setup_section_and_requirements()

        res = self.client.get("/setup?tab=sections")
        self.assertEqual(res.status_code, 200)
        html = res.data.decode("utf-8")

        # Edit button and modal for req1_id
        self.assertIn(f"editRequirementModal{req1_id}", html)
        self.assertIn(f"/requirements/{req1_id}/edit", html)
        self.assertIn("Weekly Periods", html)

        # Delete button and modal for req1_id
        self.assertIn(f"deleteRequirementModal{req1_id}", html)
        self.assertIn(f"/requirements/{req1_id}/delete", html)
        self.assertIn("Are you sure you want to remove the requirement of", html)
        self.assertIn("CS101", html)
        self.assertIn("CSE-A", html)

        # Modals for req2_id also present
        self.assertIn(f"editRequirementModal{req2_id}", html)
        self.assertIn(f"deleteRequirementModal{req2_id}", html)
        self.assertIn("MATH201", html)


if __name__ == "__main__":
    unittest.main()
