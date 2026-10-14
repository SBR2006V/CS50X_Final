"""
Smart Routine Generator - Scheduling Algorithm Module
CS50x Final Project

Step 3A: Backtracking constraint satisfaction scheduler.
Generates conflict-free weekly timetables assigning each required class session to:
- A valid working day (Monday through Friday)
- A valid time period (Period 1 to Period 6)
- A teacher qualified to teach that specific subject

Constraints Enforced:
1. Section Clash Prevention: A student section cannot have two classes at the same day & period.
2. Teacher Clash Prevention: A teacher cannot teach two different classes at the same day & period.
3. Teacher Qualification: Only teachers explicitly mapped to a subject may teach it.
4. Capacity Bounds: A section cannot exceed 30 periods per week (5 days * 6 periods).
5. Teacher Capacity Bounds: A teacher cannot exceed 30 periods per week (5 days * 6 periods).
6. Completeness: All required sessions must be assigned; partial schedules are never accepted.
"""

from collections import Counter
from pathlib import Path
import sqlite3
from typing import Dict, List, Optional, Set, Tuple, Union

from database import DATABASE_PATH, get_db_connection

# Working week definition matching schema.sql constraints
DAYS: List[str] = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
PERIODS: List[int] = [1, 2, 3, 4, 5, 6]
TOTAL_WEEKLY_SLOTS: int = len(DAYS) * len(PERIODS)  # 5 * 6 = 30 slots


class ScheduleResult:
    """
    Encapsulates the result of a timetable generation run.

    Attributes:
        success (bool): True if a complete conflict-free schedule was generated; False otherwise.
        entries (list[dict]): The scheduled class entries if successful; empty list if failed.
        error (str or None): Descriptive error message if generation failed or prerequisites missing.
    """

    def __init__(self, success: bool, entries: Optional[List[dict]] = None, error: Optional[str] = None):
        self.success = bool(success)
        self.entries = entries if (success and entries is not None) else []
        self.error = error

    def __repr__(self) -> str:
        return f"<ScheduleResult success={self.success} entries={len(self.entries)} error={self.error!r}>"

    def to_dict(self) -> dict:
        """Convert result to a dictionary representation."""
        return {
            "success": self.success,
            "entries": self.entries,
            "error": self.error,
        }


def expand_requirements(requirements: List[dict]) -> List[dict]:
    """
    Expand weekly subject requirements into individual class sessions.

    For example, if Section 1 requires 3 periods of CS101, this generates
    3 individual unassigned class session items for Section 1 and CS101.

    Args:
        requirements: List of requirement dictionaries containing 'section_id',
                      'subject_id', and 'weekly_periods'.

    Returns:
        List of single-period session dicts: [{'section_id': ..., 'subject_id': ...}, ...]
    """
    sessions = []
    for req in requirements:
        sec_id = req["section_id"]
        sub_id = req["subject_id"]
        periods = req.get("weekly_periods", 0)

        for _ in range(periods):
            sessions.append({
                "section_id": sec_id,
                "subject_id": sub_id,
            })
    return sessions


def load_scheduling_data_from_db(conn: sqlite3.Connection) -> dict:
    """
    Fetch all active configuration data required for timetable generation from the database.
    """
    subjects_rows = conn.execute("SELECT id, code, name FROM subjects;").fetchall()
    teachers_rows = conn.execute("SELECT id, name, email FROM teachers;").fetchall()
    sections_rows = conn.execute("SELECT id, name FROM sections;").fetchall()
    qual_rows = conn.execute("SELECT teacher_id, subject_id FROM teacher_subjects;").fetchall()
    req_rows = conn.execute("SELECT section_id, subject_id, weekly_periods FROM section_requirements;").fetchall()

    return {
        "subjects": [dict(r) for r in subjects_rows],
        "teachers": [dict(r) for r in teachers_rows],
        "sections": [dict(r) for r in sections_rows],
        "teacher_subjects": [dict(r) for r in qual_rows],
        "requirements": [dict(r) for r in req_rows],
    }


def generate_schedule(
    conn: Optional[sqlite3.Connection] = None,
    db_path: Optional[Union[str, Path]] = None,
    sections: Optional[List[dict]] = None,
    subjects: Optional[List[dict]] = None,
    teachers: Optional[List[dict]] = None,
    teacher_subjects: Optional[List[dict]] = None,
    requirements: Optional[List[dict]] = None,
) -> ScheduleResult:
    """
    Generate a complete, clash-free timetable using recursive backtracking.

    Can be invoked either with a database connection / path, or with in-memory data structures.

    Args:
        conn: Optional active SQLite database connection.
        db_path: Optional path to an SQLite database file.
        sections: Optional list of section dicts (in-memory mode).
        subjects: Optional list of subject dicts (in-memory mode).
        teachers: Optional list of teacher dicts (in-memory mode).
        teacher_subjects: Optional list of qualification dicts (in-memory mode).
        requirements: Optional list of requirement dicts (in-memory mode).

    Returns:
        ScheduleResult: Result object containing success status, schedule entries, or error.
    """
    # 1. Load data from DB if connection or path provided
    if conn is not None:
        data = load_scheduling_data_from_db(conn)
        sections = data["sections"]
        subjects = data["subjects"]
        teachers = data["teachers"]
        teacher_subjects = data["teacher_subjects"]
        requirements = data["requirements"]
    elif db_path is not None:
        connection = get_db_connection(Path(db_path))
        try:
            data = load_scheduling_data_from_db(connection)
            sections = data["sections"]
            subjects = data["subjects"]
            teachers = data["teachers"]
            teacher_subjects = data["teacher_subjects"]
            requirements = data["requirements"]
        finally:
            connection.close()
    else:
        # Default fallback to default DATABASE_PATH if no in-memory structures provided
        if sections is None and subjects is None and requirements is None:
            connection = get_db_connection(DATABASE_PATH)
            try:
                data = load_scheduling_data_from_db(connection)
                sections = data["sections"]
                subjects = data["subjects"]
                teachers = data["teachers"]
                teacher_subjects = data["teacher_subjects"]
                requirements = data["requirements"]
            finally:
                connection.close()

    # Ensure lists are initialized
    sections = sections or []
    subjects = subjects or []
    teachers = teachers or []
    teacher_subjects = teacher_subjects or []
    requirements = requirements or []

    # 2. Check for empty requirements
    if not requirements:
        return ScheduleResult(
            success=False,
            entries=[],
            error="No section requirements found to schedule. Please configure subject requirements first.",
        )

    # 3. Build quick lookup maps
    sections_map = {s["id"]: s for s in sections}
    subjects_map = {s["id"]: s for s in subjects}
    teachers_map = {t["id"]: t for t in teachers}

    # Map each subject to its list of qualified teacher IDs
    qualified_teachers: Dict[int, List[int]] = {}
    for ts in teacher_subjects:
        t_id = ts["teacher_id"]
        s_id = ts["subject_id"]
        qualified_teachers.setdefault(s_id, []).append(t_id)

    # 4. Prerequisite Validation: Verify every required subject has at least one qualified teacher
    for req in requirements:
        sec_id = req["section_id"]
        sub_id = req["subject_id"]
        sub_code = subjects_map.get(sub_id, {}).get("code", f"ID {sub_id}")
        sec_name = sections_map.get(sec_id, {}).get("name", f"ID {sec_id}")

        teachers_for_subject = qualified_teachers.get(sub_id, [])
        if not teachers_for_subject:
            return ScheduleResult(
                success=False,
                entries=[],
                error=f"No qualified teacher available for subject '{sub_code}' required by Section '{sec_name}'.",
            )

    # 5. Capacity Validation: Verify no section requests more than total available slots (30)
    section_totals: Counter = Counter()
    for req in requirements:
        section_totals[req["section_id"]] += req.get("weekly_periods", 0)

    for sec_id, total in section_totals.items():
        if total > TOTAL_WEEKLY_SLOTS:
            sec_name = sections_map.get(sec_id, {}).get("name", f"ID {sec_id}")
            return ScheduleResult(
                success=False,
                entries=[],
                error=f"Section '{sec_name}' requires {total} weekly periods, which exceeds the maximum limit of {TOTAL_WEEKLY_SLOTS} periods.",
            )

    # 6. Teacher Capacity Validation: Detect bottleneck where a sole qualified teacher is overloaded
    sole_teacher_demand: Counter = Counter()
    for req in requirements:
        sub_id = req["subject_id"]
        teachers_for_sub = qualified_teachers.get(sub_id, [])
        if len(teachers_for_sub) == 1:
            sole_teacher_demand[teachers_for_sub[0]] += req.get("weekly_periods", 0)

    for t_id, total in sole_teacher_demand.items():
        if total > TOTAL_WEEKLY_SLOTS:
            t_name = teachers_map.get(t_id, {}).get("name", f"ID {t_id}")
            return ScheduleResult(
                success=False,
                entries=[],
                error=f"Teacher '{t_name}' is the sole qualified instructor for subjects requiring {total} weekly periods, exceeding the maximum limit of {TOTAL_WEEKLY_SLOTS} periods.",
            )

    # 7. Aggregate Subject Capacity: Verify total required periods for subject <= sum of teacher capacities
    subject_totals: Counter = Counter()
    for req in requirements:
        subject_totals[req["subject_id"]] += req.get("weekly_periods", 0)

    for sub_id, total in subject_totals.items():
        max_possible = len(qualified_teachers.get(sub_id, [])) * TOTAL_WEEKLY_SLOTS
        if total > max_possible:
            sub_code = subjects_map.get(sub_id, {}).get("code", f"ID {sub_id}")
            return ScheduleResult(
                success=False,
                entries=[],
                error=f"Subject '{sub_code}' requires {total} weekly periods, but the {len(qualified_teachers.get(sub_id, []))} qualified teacher(s) can teach at most {max_possible} periods.",
            )

    # 8. Expand requirements into individual period sessions
    sessions = expand_requirements(requirements)

    # 9. Heuristic Ordering: Sort sessions by Most Constrained Variable (MCV)
    # Sessions with fewer qualified teachers are scheduled first to reduce search branching.
    sessions.sort(key=lambda s: len(qualified_teachers.get(s["subject_id"], [])))

    # 10. Backtracking Solver State
    schedule_entries: List[dict] = []
    section_slots: Set[Tuple[int, str, int]] = set()  # (section_id, day, period)
    teacher_slots: Set[Tuple[int, str, int]] = set()  # (teacher_id, day, period)
    teacher_period_count: Counter = Counter()          # teacher_id -> int
    sec_sub_day_count: Counter = Counter()             # (section_id, subject_id, day)

    def backtrack(idx: int) -> bool:
        """
        Recursive backtracking function to assign sessions[idx].
        Returns True if a complete valid assignment is found, False if backtracking is required.
        """
        # Base case: All individual sessions have been assigned without clash
        if idx == len(sessions):
            return True

        session = sessions[idx]
        sec_id = session["section_id"]
        sub_id = session["subject_id"]
        available_teachers = qualified_teachers[sub_id]

        # Filter out teachers who have already reached the 30-period weekly maximum
        candidate_teachers = [t for t in available_teachers if teacher_period_count[t] < TOTAL_WEEKLY_SLOTS]
        if not candidate_teachers:
            return False

        # Workload balancing heuristic: Try the least-loaded teacher first
        candidate_teachers.sort(key=lambda t: teacher_period_count[t])

        # Prioritize days with fewer classes of this subject already scheduled for this section
        # to ensure an even, pedagogical distribution across Monday through Friday.
        ordered_days = sorted(DAYS, key=lambda d: sec_sub_day_count[(sec_id, sub_id, d)])

        for day in ordered_days:
            for period in PERIODS:
                # Constraint 1: Check Section Clash
                if (sec_id, day, period) in section_slots:
                    continue

                for teacher_id in candidate_teachers:
                    # Constraint 2: Check Teacher Clash
                    if (teacher_id, day, period) in teacher_slots:
                        continue

                    # Choose: assign this slot and teacher
                    section_slots.add((sec_id, day, period))
                    teacher_slots.add((teacher_id, day, period))
                    teacher_period_count[teacher_id] += 1
                    sec_sub_day_count[(sec_id, sub_id, day)] += 1

                    entry = {
                        "section_id": sec_id,
                        "teacher_id": teacher_id,
                        "subject_id": sub_id,
                        "day_of_week": day,
                        "period": period,
                        "section_name": sections_map.get(sec_id, {}).get("name", str(sec_id)),
                        "teacher_name": teachers_map.get(teacher_id, {}).get("name", str(teacher_id)),
                        "subject_code": subjects_map.get(sub_id, {}).get("code", str(sub_id)),
                        "subject_name": subjects_map.get(sub_id, {}).get("name", str(sub_id)),
                    }
                    schedule_entries.append(entry)

                    # Recurse: assign the remaining sessions
                    if backtrack(idx + 1):
                        return True

                    # Un-choose (Backtrack): revert state and explore next possibility
                    schedule_entries.pop()
                    sec_sub_day_count[(sec_id, sub_id, day)] -= 1
                    teacher_period_count[teacher_id] -= 1
                    section_slots.remove((sec_id, day, period))
                    teacher_slots.remove((teacher_id, day, period))

        # No valid assignment possible from this state
        return False

    # Execute backtracking search
    success = backtrack(0)

    if success:
        # Sort schedule by section name, day index, and period for clean presentation
        day_order = {day: i for i, day in enumerate(DAYS)}
        schedule_entries.sort(key=lambda e: (e["section_name"], day_order[e["day_of_week"]], e["period"]))
        return ScheduleResult(success=True, entries=schedule_entries)

    # Exhausted all combinations without finding a complete conflict-free schedule
    return ScheduleResult(
        success=False,
        entries=[],
        error="Unable to generate a conflict-free schedule. The timetable constraints cannot be satisfied simultaneously with the available teachers and slots.",
    )
