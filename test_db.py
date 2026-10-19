"""
Unit and constraint verification tests for Smart Routine Generator database.
Runs automated tests using Python's built-in sqlite3 and unittest.
"""

import gc
import sqlite3
import unittest
from pathlib import Path

from database import SCHEMA_PATH, get_db_connection, init_db, verify_tables

TEST_DB_PATH = Path(__file__).resolve().parent / "test_routine.db"


class TestDatabaseSchema(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Initialize test database
        if TEST_DB_PATH.exists():
            try:
                TEST_DB_PATH.unlink()
            except PermissionError:
                pass
        init_db(db_path=TEST_DB_PATH, schema_path=SCHEMA_PATH)

    @classmethod
    def tearDownClass(cls):
        gc.collect()
        if TEST_DB_PATH.exists():
            try:
                TEST_DB_PATH.unlink()
            except PermissionError:
                pass

    def setUp(self):
        # Clean tables before each test
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

    def test_all_six_tables_exist(self):
        """Verify that all six required tables are created."""
        self.assertTrue(verify_tables(TEST_DB_PATH))

    def test_foreign_key_enforcement(self):
        """Verify that foreign keys are enforced when PRAGMA foreign_keys = ON."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                with conn:
                    conn.execute(
                        "INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?);",
                        (999, 999),
                    )
        finally:
            conn.close()

    def test_teacher_qualification_unique_constraint(self):
        """Verify that the same subject cannot be added twice to a teacher."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                t_id = conn.execute("INSERT INTO teachers (name) VALUES ('Prof. Alan Turing');").lastrowid
                s_id = conn.execute("INSERT INTO subjects (code, name) VALUES ('CS101', 'Intro to CS');").lastrowid
                conn.execute(
                    "INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?);",
                    (t_id, s_id),
                )

            with self.assertRaises(sqlite3.IntegrityError):
                with conn:
                    conn.execute(
                        "INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?);",
                        (t_id, s_id),
                    )
        finally:
            conn.close()

    def test_section_clash_prevention(self):
        """
        Verify that a student section cannot be scheduled for two different classes
        in the same period on the same day.
        """
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                t1 = conn.execute("INSERT INTO teachers (name) VALUES ('Dr. Ada Lovelace');").lastrowid
                t2 = conn.execute("INSERT INTO teachers (name) VALUES ('Prof. Alan Turing');").lastrowid
                s1 = conn.execute("INSERT INTO subjects (code, name) VALUES ('MATH101', 'Calculus');").lastrowid
                s2 = conn.execute("INSERT INTO subjects (code, name) VALUES ('CS101', 'Programming');").lastrowid
                sec = conn.execute("INSERT INTO sections (name) VALUES ('Section A');").lastrowid

                # Section A has MATH101 with Dr. Ada on Monday Period 1
                conn.execute(
                    """
                    INSERT INTO timetable_entries (section_id, teacher_id, subject_id, day_of_week, period)
                    VALUES (?, ?, ?, 'Monday', 1);
                    """,
                    (sec, t1, s1),
                )

            # Trying to book Section A in Monday Period 1 again MUST fail
            with self.assertRaises(sqlite3.IntegrityError):
                with conn:
                    conn.execute(
                        """
                        INSERT INTO timetable_entries (section_id, teacher_id, subject_id, day_of_week, period)
                        VALUES (?, ?, ?, 'Monday', 1);
                        """,
                        (sec, t2, s2),
                    )
        finally:
            conn.close()

    def test_teacher_clash_prevention(self):
        """
        Verify that a teacher cannot be scheduled to teach two different sections
        in the same period on the same day.
        """
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                t1 = conn.execute("INSERT INTO teachers (name) VALUES ('Dr. Ada Lovelace');").lastrowid
                s1 = conn.execute("INSERT INTO subjects (code, name) VALUES ('MATH101', 'Calculus');").lastrowid
                sec_a = conn.execute("INSERT INTO sections (name) VALUES ('Section A');").lastrowid
                sec_b = conn.execute("INSERT INTO sections (name) VALUES ('Section B');").lastrowid

                # Dr. Ada teaches Section A on Monday Period 2
                conn.execute(
                    """
                    INSERT INTO timetable_entries (section_id, teacher_id, subject_id, day_of_week, period)
                    VALUES (?, ?, ?, 'Monday', 2);
                    """,
                    (sec_a, t1, s1),
                )

            # Trying to book Dr. Ada for Section B on Monday Period 2 MUST fail
            with self.assertRaises(sqlite3.IntegrityError):
                with conn:
                    conn.execute(
                        """
                        INSERT INTO timetable_entries (section_id, teacher_id, subject_id, day_of_week, period)
                        VALUES (?, ?, ?, 'Monday', 2);
                        """,
                        (sec_b, t1, s1),
                    )
        finally:
            conn.close()

    def test_period_and_day_check_constraints(self):
        """Verify that period must be 1-6 and day must be Monday-Friday."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                t = conn.execute("INSERT INTO teachers (name) VALUES ('Prof. Grace Hopper');").lastrowid
                s = conn.execute("INSERT INTO subjects (code, name) VALUES ('CS102', 'Data Structures');").lastrowid
                sec = conn.execute("INSERT INTO sections (name) VALUES ('Section C');").lastrowid

            # Invalid period 7 (should fail: 1 to 6 allowed)
            with self.assertRaises(sqlite3.IntegrityError):
                with conn:
                    conn.execute(
                        """
                        INSERT INTO timetable_entries (section_id, teacher_id, subject_id, day_of_week, period)
                        VALUES (?, ?, ?, 'Monday', 7);
                        """,
                        (sec, t, s),
                    )

            # Invalid day 'Saturday' (should fail: Monday-Friday allowed)
            with self.assertRaises(sqlite3.IntegrityError):
                with conn:
                    conn.execute(
                        """
                        INSERT INTO timetable_entries (section_id, teacher_id, subject_id, day_of_week, period)
                        VALUES (?, ?, ?, 'Saturday', 1);
                        """,
                        (sec, t, s),
                    )
        finally:
            conn.close()

    def test_section_requirements_check_constraints(self):
        """Verify section requirements bounds (1 to 30 periods per week)."""
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                sec = conn.execute("INSERT INTO sections (name) VALUES ('Section D');").lastrowid
                sub = conn.execute("INSERT INTO subjects (code, name) VALUES ('PHY101', 'Physics');").lastrowid

            # 0 periods is invalid
            with self.assertRaises(sqlite3.IntegrityError):
                with conn:
                    conn.execute(
                        "INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, 0);",
                        (sec, sub),
                    )

            # 31 periods exceeds maximum weekly limit (5 days * 6 periods = 30)
            with self.assertRaises(sqlite3.IntegrityError):
                with conn:
                    conn.execute(
                        "INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, 31);",
                        (sec, sub),
                    )
        finally:
            conn.close()

    def test_teacher_foreign_key_cascade_deletion(self):
        """
        Verify that deleting a teacher cascades to delete dependent records
        in teacher_subjects and timetable_entries under foreign key constraints.
        """
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                t_id = conn.execute("INSERT INTO teachers (name, email) VALUES ('Dr. Turing', 'turing@ai.org');").lastrowid
                sub_id = conn.execute("INSERT INTO subjects (code, name) VALUES ('CS101', 'Intro to CS');").lastrowid
                sec_id = conn.execute("INSERT INTO sections (name) VALUES ('Section A');").lastrowid
                conn.execute("INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?);", (t_id, sub_id))
                conn.execute(
                    """
                    INSERT INTO timetable_entries (section_id, teacher_id, subject_id, day_of_week, period)
                    VALUES (?, ?, ?, 'Monday', 1);
                    """,
                    (sec_id, t_id, sub_id),
                )

            # Verify rows exist before deletion
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM teachers WHERE id = ?;", (t_id,)).fetchone()["c"], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM teacher_subjects WHERE teacher_id = ?;", (t_id,)).fetchone()["c"], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM timetable_entries WHERE teacher_id = ?;", (t_id,)).fetchone()["c"], 1)

            # Delete teacher
            with conn:
                conn.execute("DELETE FROM teachers WHERE id = ?;", (t_id,))

            # Verify cascade deletion took place
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM teachers WHERE id = ?;", (t_id,)).fetchone()["c"], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM teacher_subjects WHERE teacher_id = ?;", (t_id,)).fetchone()["c"], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM timetable_entries WHERE teacher_id = ?;", (t_id,)).fetchone()["c"], 0)
            # Subject and section should remain intact
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM subjects WHERE id = ?;", (sub_id,)).fetchone()["c"], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM sections WHERE id = ?;", (sec_id,)).fetchone()["c"], 1)
        finally:
            conn.close()

    def test_section_foreign_key_cascade_deletion(self):
        """
        Verify that deleting a section cascades to delete dependent records
        in section_requirements and timetable_entries under foreign key constraints.
        """
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                t_id = conn.execute("INSERT INTO teachers (name, email) VALUES ('Dr. Turing', 'turing@ai.org');").lastrowid
                sub_id = conn.execute("INSERT INTO subjects (code, name) VALUES ('CS101', 'Intro to CS');").lastrowid
                sec_id = conn.execute("INSERT INTO sections (name) VALUES ('Section A');").lastrowid
                sec_b_id = conn.execute("INSERT INTO sections (name) VALUES ('Section B');").lastrowid
                conn.execute("INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?);", (t_id, sub_id))
                conn.execute("INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, 4);", (sec_id, sub_id))
                conn.execute("INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, 3);", (sec_b_id, sub_id))
                conn.execute(
                    """
                    INSERT INTO timetable_entries (section_id, teacher_id, subject_id, day_of_week, period)
                    VALUES (?, ?, ?, 'Monday', 1);
                    """,
                    (sec_id, t_id, sub_id),
                )
                conn.execute(
                    """
                    INSERT INTO timetable_entries (section_id, teacher_id, subject_id, day_of_week, period)
                    VALUES (?, ?, ?, 'Monday', 2);
                    """,
                    (sec_b_id, t_id, sub_id),
                )

            # Verify rows exist before deletion
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM sections WHERE id = ?;", (sec_id,)).fetchone()["c"], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM section_requirements WHERE section_id = ?;", (sec_id,)).fetchone()["c"], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM timetable_entries WHERE section_id = ?;", (sec_id,)).fetchone()["c"], 1)

            # Delete section
            with conn:
                conn.execute("DELETE FROM sections WHERE id = ?;", (sec_id,))

            # Verify cascade deletion took place for Section A
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM sections WHERE id = ?;", (sec_id,)).fetchone()["c"], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM section_requirements WHERE section_id = ?;", (sec_id,)).fetchone()["c"], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM timetable_entries WHERE section_id = ?;", (sec_id,)).fetchone()["c"], 0)

            # Other section (Section B), teacher, and subject should remain intact
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM sections WHERE id = ?;", (sec_b_id,)).fetchone()["c"], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM section_requirements WHERE section_id = ?;", (sec_b_id,)).fetchone()["c"], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM timetable_entries WHERE section_id = ?;", (sec_b_id,)).fetchone()["c"], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM teachers WHERE id = ?;", (t_id,)).fetchone()["c"], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) AS c FROM subjects WHERE id = ?;", (sub_id,)).fetchone()["c"], 1)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
