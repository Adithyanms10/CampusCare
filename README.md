# Campus Care

College complaint management web app. Flask + SQLAlchemy + MySQL, Flask sessions for login.
Roles: **student** (submits and tracks complaints), **staff** (handles assigned complaints), **admin** (users, assignment, priorities, statistics).

## Status (read this first)
This code was written in an environment with no internet, so **the test suite and the app have not been run yet**.
Only Python syntax and Jinja template syntax were checked. Run the steps below and fix anything that fails.

## 1. Requirements
Python 3.10+ and MySQL 8 (or MariaDB 10.6+).

## 2. Create the MySQL database and user
```sql
CREATE DATABASE campus_care CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'campus_user'@'localhost' IDENTIFIED BY 'choose-a-strong-password';
GRANT ALL PRIVILEGES ON campus_care.* TO 'campus_user'@'localhost';
FLUSH PRIVILEGES;
```

## 3. Install
```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # Windows: copy .env.example .env
```
Edit `.env`: set `SECRET_KEY` (generate with `python -c "import secrets; print(secrets.token_hex(32))"`)
and put your MySQL password in `DATABASE_URL`. Never commit `.env`.

## 4. Create the tables (migrations)
```bash
export FLASK_APP=run.py         # Windows: set FLASK_APP=run.py
flask db init                   # once only, creates the migrations/ folder
flask db migrate -m "initial tables"
flask db upgrade
```

## 5. Starter data and first admin
```bash
flask init-data                 # default departments and complaint categories
flask create-admin              # asks for name, email, password
```
Students register themselves at `/register`. Staff and extra admins are created by an admin on the Users page.
(Self-registration only makes students on purpose, otherwise anyone could make themselves admin.)

## 6. Run
```bash
flask run
```
Open http://127.0.0.1:5000. Typical flow: student submits, admin assigns to staff and sets priority, staff updates status and replies.

## 7. Tests
```bash
pytest -v
```
Tests use an in-memory SQLite database, so they do not touch MySQL. They cover registration/login, complaint creation,
status updates, role permissions, student-to-student isolation, staff assignment, invalid forms and CSRF.
Because they use SQLite, MySQL-specific behaviour (for example the CHECK constraints on older MySQL versions) is not tested.

## Project layout
```
app/__init__.py      application factory, error pages, CLI commands
app/config.py        settings read from environment variables
app/models.py        User, Department, Category, Complaint, ComplaintUpdate
app/security.py      CSRF, role_required, security headers
app/validators.py    server-side validation
app/services.py      complaint filters and statistics
app/blueprints/      auth, student, staff, admin routes
app/templates/       Jinja templates;  app/static/  CSS and JS
tests/               pytest suite
```

## Design decisions
- Status values: pending, in_progress, resolved, rejected, closed. Priorities: low, medium, high, urgent. Both are stored as text with database CHECK constraints.
- Overdue = still pending/in progress and past its due date. Due date comes from priority (urgent 1 day, high 3, medium 7, low 14).
- Other students' complaints return 404 (not 403) so their existence is not revealed.
- Internal notes are never sent to the student's page.
- A `Category` table was added next to the four requested models because admins must manage categories.

## Not implemented
File uploads, password reset, email notifications, login rate limiting, pagination, editing a complaint after submission.
Before real deployment: serve over HTTPS, set `SESSION_COOKIE_SECURE=1`, and add rate limiting on `/login`.
