# Smart Routine Generator

#### Video Demo: https://youtu.be/vqBt0uZEnzw?si=W6TZ15YAJDEvW1FU

#### Description:

Smart Routine Generator is a web application developed as my CS50x Final Project. The purpose of this project is to simplify the process of creating academic timetables for multiple sections by automatically assigning subjects and qualified teachers to weekly class periods.

Creating a timetable manually can be time-consuming, especially when several sections share teachers. A teacher cannot teach two classes in the same time slot, and each section must follow its specified subject requirements. Managing these constraints manually can lead to scheduling conflicts and repeated adjustments. I built this application to automate the scheduling process and make timetable creation easier to manage.

### Features

**Academic Setup:** The application allows users to manage subjects, teachers, and sections. Users can assign subject qualifications to teachers and specify how many weekly periods each subject requires for a particular section.

**Automatic Timetable Generation:** The application uses a backtracking algorithm to search for a valid timetable. It considers subject requirements and teacher qualifications while checking that a section or teacher is not assigned to multiple classes in the same time slot. The scheduler also prioritizes more constrained scheduling tasks to improve the search process.

**Constraint Validation:** The application checks whether the requested timetable can be generated. For example, if a section requires more periods than the weekly timetable can accommodate, the application reports that the configuration is impossible rather than generating an invalid schedule.

**Timetable Management:** Generated timetables can be viewed by section. When relevant academic setup data changes, the application marks the existing timetable as outdated so users know that it may no longer reflect the current configuration.

**PDF Export:** Users can export a section's timetable as a PDF. Exporting is restricted when the timetable is outdated, helping prevent users from downloading a timetable that may not match the current academic setup.

### Files and Their Purpose

- `app.py` contains the Flask application, routes, request handling, and the logic connecting the user interface, database, and scheduling functionality.
- `scheduler.py` contains the timetable generation algorithm. It uses backtracking to assign required subject periods while respecting teacher qualifications and avoiding section and teacher clashes.
- `database.py` contains database-related functions used to interact with the application's SQLite database and manage academic information.
- `schema.sql` defines the database structure, including tables for subjects, teachers, teacher-subject qualifications, sections, section requirements, and timetable entries.
- `requirements.txt` lists the Python packages required to run the application.
- `templates/` contains the HTML templates used to display the dashboard, academic setup pages, timetable views, and result messages.
- `static/` contains the application's static assets, including CSS used to style the interface.
- `routine.db` is the local SQLite database file used by the application, if included in the submitted project.
- `test_app.py`, `test_db.py`, and `test_scheduler.py` contain tests for application routes and behavior, database operations, and scheduling logic, respectively.
- `pdf_generator.py` generates downloadable PDF versions of section timetables using ReportLab.
- `pyproject.toml` contains Python project and tool configuration.

### Design Choices

I chose Python and Flask because they make it straightforward to build a web application while keeping the backend logic organized. SQLite provides a simple database solution without requiring a separate database server, making the application easy to run locally.

The most important design decision was using backtracking instead of assigning periods randomly or using a simple greedy approach. A greedy approach can make an early assignment that prevents later subjects from being scheduled. Backtracking allows the scheduler to try an assignment, continue searching, and undo the assignment if it leads to a dead end. Prioritizing the most constrained tasks helps the algorithm address difficult assignments earlier.

I also separated the scheduling algorithm from the Flask routes and database operations. This makes the scheduling logic easier to test independently and keeps the application more maintainable. Another important decision was to avoid replacing a previously generated timetable when a new scheduling attempt fails. This prevents a failed attempt from destroying a previously saved schedule.

### Limitations and Future Improvements

The current version assumes teachers are available during every period and does not manage classroom allocation. It uses a fixed weekly structure of five weekdays and six periods per day. Future improvements could include teacher availability, room allocation, configurable academic calendars and additional scheduling preferences.

### Running the Project

1. Install Python and ensure it is available from your terminal.
2. Open a terminal in the project directory.
3. Install the required dependencies:

   `pip install -r requirements.txt`

4. Start the application:

   `flask --app app run`

5. Open the local address displayed in the terminal in your web browser.

This project helped me apply concepts from Python programming, web development, database management, constraint satisfaction, recursion, and algorithm design to a practical problem.

### Author

- Name: Sourasish Biswas
- GitHub: SBR2006V
- edX: SBR06V
- Location: Kolkata, India
