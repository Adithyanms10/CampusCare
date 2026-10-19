"""Server-side validation. Each function returns (clean_data, errors)."""
import re

from .models import PRIORITIES, ROLES, STAFF_STATUSES, Category, Department, User, db

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _text(form, key):
    return (form.get(key) or "").strip()


def _length(errors, label, value, low, high):
    if len(value) < low:
        errors.append(f"{label} must be at least {low} characters.")
    elif len(value) > high:
        errors.append(f"{label} must be at most {high} characters.")


def check_password_strength(password):
    if len(password) < 8:
        return "Password must be at least 8 characters."
    if not (re.search(r"[A-Za-z]", password) and re.search(r"\d", password)):
        return "Password must contain at least one letter and one number."
    if len(password) > 128:
        return "Password must be at most 128 characters."
    return None


def validate_registration(form, require_confirm=True):
    errors = []
    name = _text(form, "name")
    email = _text(form, "email").lower()
    password = form.get("password") or ""
    _length(errors, "Name", name, 2, 100)
    if not EMAIL_RE.match(email) or len(email) > 255:
        errors.append("Enter a valid email address.")
    elif db.session.query(User.id).filter_by(email=email).first():
        errors.append("An account with this email already exists.")
    problem = check_password_strength(password)
    if problem:
        errors.append(problem)
    if require_confirm and password != (form.get("confirm_password") or ""):
        errors.append("Passwords do not match.")
    return {"name": name, "email": email, "password": password}, errors


def validate_complaint(form):
    errors = []
    subject = _text(form, "subject")
    description = _text(form, "description")
    category_raw = _text(form, "category_id")
    _length(errors, "Subject", subject, 5, 150)
    _length(errors, "Description", description, 20, 3000)
    category = None
    if category_raw.isdigit():
        category = db.session.get(Category, int(category_raw))
    if category is None:
        errors.append("Choose a valid category.")
    return {"subject": subject, "description": description, "category": category}, errors


def validate_staff_update(form, complaint):
    errors = []
    status = _text(form, "status")
    public_response = _text(form, "public_response")
    internal_note = _text(form, "internal_note")
    resolution_note = _text(form, "resolution_note")
    if status != complaint.status and status not in STAFF_STATUSES:
        errors.append("Choose a valid status.")
    for label, value in (("Response", public_response), ("Internal note", internal_note), ("Resolution note", resolution_note)):
        if len(value) > 3000:
            errors.append(f"{label} must be at most 3000 characters.")
    if status == "resolved" and not (resolution_note or complaint.resolution_note):
        errors.append("Add resolution details before marking a complaint resolved.")
    if status == "rejected" and not public_response:
        errors.append("Explain the rejection in a student-visible response.")
    if not errors and status == complaint.status and not (public_response or internal_note or resolution_note):
        errors.append("Nothing to update. Change the status or add a note.")
    return {
        "status": status,
        "public_response": public_response,
        "internal_note": internal_note,
        "resolution_note": resolution_note,
    }, errors


def validate_assignment(form):
    errors = []
    priority = _text(form, "priority")
    assignee_raw = _text(form, "assigned_to_id")
    if priority not in PRIORITIES:
        errors.append("Choose a valid priority.")
    assignee = None
    if assignee_raw:
        if assignee_raw.isdigit():
            assignee = db.session.get(User, int(assignee_raw))
        if assignee is None or assignee.role != "staff" or not assignee.is_active:
            errors.append("Complaints can only be assigned to an active staff member.")
    return {"priority": priority, "assignee": assignee}, errors


def validate_user_fields(form):
    errors = []
    role = _text(form, "role")
    dept_raw = _text(form, "department_id")
    if role not in ROLES:
        errors.append("Choose a valid role.")
    department = None
    if dept_raw:
        department = db.session.get(Department, int(dept_raw)) if dept_raw.isdigit() else None
        if department is None:
            errors.append("Choose a valid department.")
    return {"role": role, "department": department}, errors


def validate_name(form, label="Name"):
    errors = []
    name = _text(form, "name")
    _length(errors, label, name, 2, 100)
    return name, errors
