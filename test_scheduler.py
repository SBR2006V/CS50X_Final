"""
Unit tests for Smart Routine Generator Scheduling Algorithm (Step 3A).
Tests backtracking logic, constraint satisfaction, clash prevention, and edge cases.
"""

import gc
from pathlib import Path
import sqlite3
import unittest

from database import init_db, get_db_connection
from scheduler import (
    DAYS,
    PERIODS,
    TOTAL_WEEKLY_SLOTS,
    ScheduleResult,
    expand_requirements,
    generate_schedule,
)

TEST_DB_PATH = Path(__file__).resolve().parent / "test_routine_scheduler.db"


class TestSchedulerAlgorithm(unittest.TestCase):
    """
    Unit test suite verifying the backtracking scheduler.
    Tests both in-memory constraint solving and SQLite database integration.
    """

    @classmethod
    def setUpClass(cls):
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
        # Clean tables before each database test
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

    def test_expand_requirements(self):
        """Verify that weekly period requirements correctly unpack into individual session items."""
        requirements = [
            {"section_id": 1, "subject_id": 101, "weekly_periods": 3},
            {"section_id": 1, "subject_id": 102, "weekly_periods": 2},
            {"section_id": 2, "subject_id": 101, "weekly_periods": 1},
        ]
        sessions = expand_requirements(requirements)
        self.assertEqual(len(sessions), 6)
        # Check that subject 101 appears 3 times for section 1 and 1 time for section 2
        sec1_sub101 = [s for s in sessions if s["section_id"] == 1 and s["subject_id"] == 101]
        self.assertEqual(len(sec1_sub101), 3)

    def test_missing_qualification_fails_with_clear_error(self):
        """Verify that a requirement with no qualified teacher is caught early with a clear message."""
        sections = [{"id": 1, "name": "CSE-A"}]
        subjects = [{"id": 10, "code": "CS101", "name": "Intro to CS"}]
        teachers = [{"id": 1, "name": "Dr. Ada"}]
        teacher_subjects = []  # No teacher qualified for CS101
        requirements = [{"section_id": 1, "subject_id": 10, "weekly_periods": 4}]

        result = generate_schedule(
            sections=sections,
            subjects=subjects,
            teachers=teachers,
            teacher_subjects=teacher_subjects,
            requirements=requirements,
        )

        self.assertFalse(result.success)
        self.assertEqual(result.entries, [])
        self.assertIn("No qualified teacher available", result.error)
        self.assertIn("CS101", result.error)
        self.assertIn("CSE-A", result.error)

    def test_successful_single_section_schedule(self):
        """Verify conflict-free schedule generation for a single section with multiple subjects."""
        sections = [{"id": 1, "name": "CSE-A"}]
        subjects = [
            {"id": 1, "code": "CS101", "name": "Intro to CS"},
            {"id": 2, "code": "MATH101", "name": "Calculus"},
            {"id": 3, "code": "PHY101", "name": "Physics"},
        ]
        teachers = [
            {"id": 1, "name": "Dr. Ada"},
            {"id": 2, "name": "Prof. Euler"},
            {"id": 3, "name": "Dr. Newton"},
        ]
        teacher_subjects = [
            {"teacher_id": 1, "subject_id": 1},
            {"teacher_id": 2, "subject_id": 2},
            {"teacher_id": 3, "subject_id": 3},
        ]
        requirements = [
            {"section_id": 1, "subject_id": 1, "weekly_periods": 4},
            {"section_id": 1, "subject_id": 2, "weekly_periods": 4},
            {"section_id": 1, "subject_id": 3, "weekly_periods": 3},
        ]

        result = generate_schedule(
            sections=sections,
            subjects=subjects,
            teachers=teachers,
            teacher_subjects=teacher_subjects,
            requirements=requirements,
        )

        self.assertTrue(result.success)
        self.assertIsNone(result.error)
        self.assertEqual(len(result.entries), 11)  # 4 + 4 + 3

        # Verify all entries have valid day and period
        for entry in result.entries:
            self.assertIn(entry["day_of_week"], DAYS)
            self.assertIn(entry["period"], PERIODS)
            self.assertEqual(entry["section_id"], 1)

    def test_only_qualified_teachers_assigned(self):
        """Verify that every scheduled session is assigned to an authorized teacher."""
        sections = [{"id": 1, "name": "CSE-A"}]
        subjects = [
            {"id": 1, "code": "CS101", "name": "Intro to CS"},
            {"id": 2, "code": "MATH101", "name": "Calculus"},
        ]
        teachers = [
            {"id": 10, "name": "Teacher Ada"},
            {"id": 20, "name": "Teacher Euler"},
        ]
        # Only Teacher Ada can teach CS101; Only Teacher Euler can teach MATH101
        teacher_subjects = [
            {"teacher_id": 10, "subject_id": 1},
            {"teacher_id": 20, "subject_id": 2},
        ]
        requirements = [
            {"section_id": 1, "subject_id": 1, "weekly_periods": 3},
            {"section_id": 1, "subject_id": 2, "weekly_periods": 3},
        ]

        result = generate_schedule(
            sections=sections,
            subjects=subjects,
            teachers=teachers,
            teacher_subjects=teacher_subjects,
            requirements=requirements,
        )

        self.assertTrue(result.success)
        for entry in result.entries:
            if entry["subject_id"] == 1:
                self.assertEqual(entry["teacher_id"], 10)
            elif entry["subject_id"] == 2:
                self.assertEqual(entry["teacher_id"], 20)

    def test_no_section_clashes(self):
        """Verify that a section is never double-booked on the same day and period."""
        sections = [{"id": 1, "name": "CSE-A"}]
        subjects = [
            {"id": 1, "code": "CS101", "name": "CS"},
            {"id": 2, "code": "MATH101", "name": "Math"},
        ]
        teachers = [
            {"id": 1, "name": "Teacher 1"},
            {"id": 2, "name": "Teacher 2"},
        ]
        teacher_subjects = [
            {"teacher_id": 1, "subject_id": 1},
            {"teacher_id": 2, "subject_id": 2},
        ]
        requirements = [
            {"section_id": 1, "subject_id": 1, "weekly_periods": 5},
            {"section_id": 1, "subject_id": 2, "weekly_periods": 5},
        ]

        result = generate_schedule(
            sections=sections,
            subjects=subjects,
            teachers=teachers,
            teacher_subjects=teacher_subjects,
            requirements=requirements,
        )

        self.assertTrue(result.success)
        seen_section_slots = set()
        for entry in result.entries:
            slot = (entry["section_id"], entry["day_of_week"], entry["period"])
            self.assertNotIn(slot, seen_section_slots, f"Duplicate section slot found: {slot}")
            seen_section_slots.add(slot)

    def test_no_teacher_clashes_across_multiple_sections(self):
        """Verify that a shared teacher is never scheduled for two sections at the same day & period."""
        sections = [
            {"id": 1, "name": "CSE-A"},
            {"id": 2, "name": "CSE-B"},
        ]
        subjects = [{"id": 1, "code": "CS101", "name": "CS"}]
        # Single teacher shared by both sections
        teachers = [{"id": 100, "name": "Prof. Turing"}]
        teacher_subjects = [{"teacher_id": 100, "subject_id": 1}]
        requirements = [
            {"section_id": 1, "subject_id": 1, "weekly_periods": 6},
            {"section_id": 2, "subject_id": 1, "weekly_periods": 6},
        ]

        result = generate_schedule(
            sections=sections,
            subjects=subjects,
            teachers=teachers,
            teacher_subjects=teacher_subjects,
            requirements=requirements,
        )

        self.assertTrue(result.success)
        self.assertEqual(len(result.entries), 12)

        seen_teacher_slots = set()
        for entry in result.entries:
            slot = (entry["teacher_id"], entry["day_of_week"], entry["period"])
            self.assertNotIn(slot, seen_teacher_slots, f"Teacher clash detected at: {slot}")
            seen_teacher_slots.add(slot)

    def test_impossible_schedule_overloaded_section(self):
        """Verify that a section requesting > 30 periods fails immediately without partial results."""
        sections = [{"id": 1, "name": "CSE-Overloaded"}]
        subjects = [{"id": 1, "code": "CS101", "name": "CS"}]
        teachers = [{"id": 1, "name": "Dr. Ada"}]
        teacher_subjects = [{"teacher_id": 1, "subject_id": 1}]
        # 31 periods exceeds 5 days * 6 periods = 30
        requirements = [{"section_id": 1, "subject_id": 1, "weekly_periods": 31}]

        result = generate_schedule(
            sections=sections,
            subjects=subjects,
            teachers=teachers,
            teacher_subjects=teacher_subjects,
            requirements=requirements,
        )

        self.assertFalse(result.success)
        self.assertEqual(result.entries, [])
        self.assertIn("exceeds the maximum limit of 30", result.error)

    def test_impossible_schedule_overloaded_single_teacher(self):
        """Verify failure when cumulative demands on a single teacher exceed 30 periods."""
        sections = [
            {"id": 1, "name": "Section 1"},
            {"id": 2, "name": "Section 2"},
        ]
        subjects = [{"id": 1, "code": "CS101", "name": "CS"}]
        # Only 1 teacher available
        teachers = [{"id": 1, "name": "Sole Teacher"}]
        teacher_subjects = [{"teacher_id": 1, "subject_id": 1}]
        # 20 + 15 = 35 periods demanded from a single teacher (max is 30)
        requirements = [
            {"section_id": 1, "subject_id": 1, "weekly_periods": 20},
            {"section_id": 2, "subject_id": 1, "weekly_periods": 15},
        ]

        result = generate_schedule(
            sections=sections,
            subjects=subjects,
            teachers=teachers,
            teacher_subjects=teacher_subjects,
            requirements=requirements,
        )

        self.assertFalse(result.success)
        self.assertEqual(result.entries, [])
        self.assertIn("exceeding the maximum limit of 30", result.error)

    def test_full_30_period_schedule(self):
        """Verify that a section requiring exactly 30 periods completely fills the timetable."""
        sections = [{"id": 1, "name": "Section-Full"}]
        subjects = [
            {"id": 1, "code": "SUB1", "name": "Subject 1"},
            {"id": 2, "code": "SUB2", "name": "Subject 2"},
            {"id": 3, "code": "SUB3", "name": "Subject 3"},
            {"id": 4, "code": "SUB4", "name": "Subject 4"},
            {"id": 5, "code": "SUB5", "name": "Subject 5"},
        ]
        teachers = [{"id": i, "name": f"Teacher {i}"} for i in range(1, 6)]
        teacher_subjects = [{"teacher_id": i, "subject_id": i} for i in range(1, 6)]
        # 5 subjects * 6 periods = 30 periods
        requirements = [{"section_id": 1, "subject_id": i, "weekly_periods": 6} for i in range(1, 6)]

        result = generate_schedule(
            sections=sections,
            subjects=subjects,
            teachers=teachers,
            teacher_subjects=teacher_subjects,
            requirements=requirements,
        )

        self.assertTrue(result.success)
        self.assertEqual(len(result.entries), 30)

        # Every slot in Monday-Friday, periods 1-6 must be covered exactly once
        all_expected_slots = {(day, period) for day in DAYS for period in PERIODS}
        actual_slots = {(e["day_of_week"], e["period"]) for e in result.entries}
        self.assertEqual(all_expected_slots, actual_slots)

    def test_multiple_qualified_teachers_distributed_workload(self):
        """Verify that when multiple teachers are qualified, the solver leverages both without clashes."""
        sections = [
            {"id": 1, "name": "Section A"},
            {"id": 2, "name": "Section B"},
        ]
        subjects = [{"id": 1, "code": "CS101", "name": "CS"}]
        # Two teachers qualified for CS101
        teachers = [
            {"id": 1, "name": "Teacher Alpha"},
            {"id": 2, "name": "Teacher Beta"},
        ]
        teacher_subjects = [
            {"teacher_id": 1, "subject_id": 1},
            {"teacher_id": 2, "subject_id": 1},
        ]
        # Total 36 periods demanded (impossible for 1 teacher, but possible for 2 teachers)
        requirements = [
            {"section_id": 1, "subject_id": 1, "weekly_periods": 18},
            {"section_id": 2, "subject_id": 1, "weekly_periods": 18},
        ]

        result = generate_schedule(
            sections=sections,
            subjects=subjects,
            teachers=teachers,
            teacher_subjects=teacher_subjects,
            requirements=requirements,
        )

        self.assertTrue(result.success)
        self.assertEqual(len(result.entries), 36)

        # Confirm that both teachers were utilized
        teachers_used = {e["teacher_id"] for e in result.entries}
        self.assertEqual(teachers_used, {1, 2})

    def test_empty_requirements_returns_clear_error(self):
        """Verify that running with empty requirements returns a descriptive error."""
        result = generate_schedule(
            sections=[{"id": 1, "name": "CSE-A"}],
            subjects=[{"id": 1, "code": "CS101", "name": "CS"}],
            teachers=[{"id": 1, "name": "Ada"}],
            teacher_subjects=[{"teacher_id": 1, "subject_id": 1}],
            requirements=[],
        )
        self.assertFalse(result.success)
        self.assertIn("No section requirements found", result.error)

    def test_database_integration_and_constraint_compatibility(self):
        """
        Verify end-to-end integration with SQLite database.
        Generates a schedule from database rows and inserts entries directly
        into the timetable_entries table to prove 100% compatibility with SQLite constraints.
        """
        conn = get_db_connection(TEST_DB_PATH)
        try:
            with conn:
                # 1. Setup DB records
                s1 = conn.execute("INSERT INTO subjects (code, name) VALUES ('CS101', 'Intro to CS');").lastrowid
                s2 = conn.execute("INSERT INTO subjects (code, name) VALUES ('MATH101', 'Calculus');").lastrowid

                t1 = conn.execute("INSERT INTO teachers (name, email) VALUES ('Prof. Turing', 'turing@cs.edu');").lastrowid
                t2 = conn.execute("INSERT INTO teachers (name, email) VALUES ('Prof. Lovelace', 'ada@math.edu');").lastrowid

                conn.execute("INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?);", (t1, s1))
                conn.execute("INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?);", (t2, s2))

                sec1 = conn.execute("INSERT INTO sections (name) VALUES ('CSE-A');").lastrowid
                sec2 = conn.execute("INSERT INTO sections (name) VALUES ('CSE-B');").lastrowid

                conn.execute("INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, 5);", (sec1, s1))
                conn.execute("INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, 5);", (sec1, s2))
                conn.execute("INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, 5);", (sec2, s1))
                conn.execute("INSERT INTO section_requirements (section_id, subject_id, weekly_periods) VALUES (?, ?, 5);", (sec2, s2))

            # 2. Run scheduler directly against the database connection
            result = generate_schedule(conn=conn)
            self.assertTrue(result.success)
            self.assertEqual(len(result.entries), 20)  # (5+5) + (5+5) = 20 entries

            # 3. Insert into timetable_entries table - this tests schema UNIQUE constraints live!
            with conn:
                for e in result.entries:
                    conn.execute(
                        """
                        INSERT INTO timetable_entries (section_id, teacher_id, subject_id, day_of_week, period)
                        VALUES (?, ?, ?, ?, ?);
                        """,
                        (e["section_id"], e["teacher_id"], e["subject_id"], e["day_of_week"], e["period"]),
                    )

            # 4. Verify count in DB
            db_count = conn.execute("SELECT COUNT(*) AS total FROM timetable_entries;").fetchone()["total"]
            self.assertEqual(db_count, 20)

        finally:
            conn.close()

    def test_schedule_result_interface_compatibility(self):
        """Verify ScheduleResult supports both attribute access (.success) and dict subscripting (['success'])."""
        res_success = ScheduleResult(success=True, entries=[{"section_id": 1}], error=None)
        self.assertTrue(res_success)
        self.assertTrue(res_success.success)
        self.assertTrue(res_success["success"])
        self.assertEqual(res_success["entries"], [{"section_id": 1}])
        self.assertEqual(res_success["schedule"], [{"section_id": 1}])
        self.assertEqual(res_success.schedule, [{"section_id": 1}])
        self.assertIsNone(res_success.get("error"))

        res_fail = ScheduleResult(success=False, error="Teacher not qualified")
        self.assertFalse(res_fail)
        self.assertFalse(res_fail.success)
        self.assertFalse(res_fail["success"])
        self.assertEqual(res_fail["error"], "Teacher not qualified")
        self.assertEqual(res_fail.get("error"), "Teacher not qualified")
        self.assertEqual(res_fail["entries"], [])
        self.assertEqual(res_fail["schedule"], [])


if __name__ == "__main__":
    unittest.main()
