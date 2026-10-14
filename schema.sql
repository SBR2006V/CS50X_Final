-- Smart Routine Generator - Database Schema
-- CS50x Final Project

-- Enforce foreign key constraints
PRAGMA foreign_keys = ON;

-- Drop tables in reverse order of foreign key dependencies for clean re-initialization
DROP TABLE IF EXISTS timetable_entries;
DROP TABLE IF EXISTS section_requirements;
DROP TABLE IF EXISTS teacher_subjects;
DROP TABLE IF EXISTS sections;
DROP TABLE IF EXISTS teachers;
DROP TABLE IF EXISTS subjects;

-- 1. Subjects Table
-- Stores academic subjects offered in the curriculum (e.g., CS101 - Introduction to Programming)
CREATE TABLE subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL
);

-- 2. Teachers Table
-- Stores faculty members
CREATE TABLE teachers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE
);

-- 3. Teacher-Subject Mapping Table (Many-to-Many)
-- Models teacher qualifications:
-- - One teacher can be qualified to teach multiple subjects
-- - One subject can be taught by multiple teachers
CREATE TABLE teacher_subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    teacher_id INTEGER NOT NULL,
    subject_id INTEGER NOT NULL,
    FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
    UNIQUE (teacher_id, subject_id)
);

-- 4. Sections Table
-- Represents student cohorts/classes (e.g., "Section A", "Section B")
CREATE TABLE sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

-- 5. Section Requirements Table
-- Defines how many periods of each subject a specific section requires per week.
-- A week has 5 working days * 6 periods = 30 total periods maximum.
CREATE TABLE section_requirements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    section_id INTEGER NOT NULL,
    subject_id INTEGER NOT NULL,
    weekly_periods INTEGER NOT NULL CHECK (weekly_periods > 0 AND weekly_periods <= 30),
    FOREIGN KEY (section_id) REFERENCES sections(id) ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
    UNIQUE (section_id, subject_id)
);

-- 6. Timetable Entries Table
-- Holds the scheduled routine.
-- Working days: Monday to Friday. Periods: 1 to 6.
CREATE TABLE timetable_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    section_id INTEGER NOT NULL,
    teacher_id INTEGER NOT NULL,
    subject_id INTEGER NOT NULL,
    day_of_week TEXT NOT NULL CHECK (day_of_week IN ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday')),
    period INTEGER NOT NULL CHECK (period >= 1 AND period <= 6),
    FOREIGN KEY (section_id) REFERENCES sections(id) ON DELETE CASCADE,
    FOREIGN KEY (teacher_id) REFERENCES teachers(id) ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,

    -- CONSTRAINT: Prevent Section Clashes
    -- A student section cannot have two different classes during the same period on the same day.
    UNIQUE (section_id, day_of_week, period),

    -- CONSTRAINT: Prevent Teacher Clashes
    -- A teacher cannot be scheduled to teach two different classes during the same period on the same day.
    UNIQUE (teacher_id, day_of_week, period)
);
