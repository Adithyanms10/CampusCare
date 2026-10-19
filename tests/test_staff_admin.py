from datetime import timedelta

import pytest

from app.extensions import db
from app.models import Category, Complaint, ComplaintUpdate, Department, User, utcnow

from .conftest import fresh, login, make_complaint, make_user


# ---------- admin: assignment and priority ----------

def test_admin_assigns_complaint_and_sets_priority(client, users, category):
    cid = make_complaint(users["alice"], category)
    login(client, "admin@college.edu")
    response = client.post(f"/admin/complaints/{cid}/assign",
                           data={"assigned_to_id": str(users["staff"]), "priority": "urgent"})
    assert response.status_code == 302
    complaint = fresh(Complaint, cid)
    assert complaint.assigned_to_id == users["staff"]
    assert complaint.priority == "urgent"
    assert complaint.due_date - complaint.created_at == timedelta(days=1)
    log = ComplaintUpdate.query.filter_by(complaint_id=cid).one()
    assert "Sam Staff" in log.internal_note and not log.visible_to_student


def test_admin_cannot_assign_to_student_or_use_bad_priority(client, users, category):
    cid = make_complaint(users["alice"], category)
    login(client, "admin@college.edu")
    client.post(f"/admin/complaints/{cid}/assign", data={"assigned_to_id": str(users["bob"]), "priority": "high"})
    client.post(f"/admin/complaints/{cid}/assign", data={"assigned_to_id": str(users["staff"]), "priority": "banana"})
    complaint = fresh(Complaint, cid)
    assert complaint.assigned_to_id is None and complaint.priority == "medium"


def test_admin_cannot_assign_to_disabled_staff(client, users, category):
    off = make_user("off@college.edu", "staff", active=False)
    cid = make_complaint(users["alice"], category)
    login(client, "admin@college.edu")
    client.post(f"/admin/complaints/{cid}/assign", data={"assigned_to_id": str(off), "priority": "high"})
    assert fresh(Complaint, cid).assigned_to_id is None


def test_staff_and_students_cannot_assign(client, users, category):
    cid = make_complaint(users["alice"], category)
    for email in ("staff@college.edu", "alice@college.edu"):
        client.post("/logout")
        login(client, email)
        response = client.post(f"/admin/complaints/{cid}/assign",
                               data={"assigned_to_id": str(users["staff"]), "priority": "high"})
        assert response.status_code == 403
    assert fresh(Complaint, cid).assigned_to_id is None


# ---------- staff: viewing and updating ----------

def test_staff_sees_only_assigned_complaints(client, users, category):
    make_complaint(users["alice"], category, subject="Mine to handle", assigned_to_id=users["staff"])
    make_complaint(users["bob"], category, subject="Belongs to colleague", assigned_to_id=users["staff2"])
    make_complaint(users["bob"], category, subject="Nobody has this one")
    login(client, "staff@college.edu")
    page = client.get("/staff/complaints").get_data(as_text=True)
    assert "Mine to handle" in page
    assert "Belongs to colleague" not in page and "Nobody has this one" not in page


def test_staff_cannot_open_unassigned_or_colleagues_complaint(client, users, category):
    theirs = make_complaint(users["alice"], category, assigned_to_id=users["staff2"])
    unassigned = make_complaint(users["alice"], category)
    login(client, "staff@college.edu")
    assert client.get(f"/staff/complaints/{theirs}").status_code == 404
    assert client.post(f"/staff/complaints/{unassigned}", data={"status": "in_progress", "internal_note": "x"}).status_code == 404


def test_staff_filters_by_status_and_priority(client, users, category):
    a = make_complaint(users["alice"], category, subject="Urgent fan problem", assigned_to_id=users["staff"])
    make_complaint(users["alice"], category, subject="Routine paint request", assigned_to_id=users["staff"])
    complaint = db.session.get(Complaint, a)
    complaint.set_priority("urgent")
    db.session.commit()
    login(client, "staff@college.edu")
    page = client.get("/staff/complaints?priority=urgent").get_data(as_text=True)
    assert "Urgent fan problem" in page and "Routine paint request" not in page


def test_staff_updates_status_with_notes(client, users, category):
    cid = make_complaint(users["alice"], category, assigned_to_id=users["staff"])
    login(client, "staff@college.edu")
    response = client.post(f"/staff/complaints/{cid}", data={
        "status": "in_progress", "public_response": "We are looking into it.", "internal_note": "Call maintenance"})
    assert response.status_code == 302
    assert fresh(Complaint, cid).status == "in_progress"
    update = ComplaintUpdate.query.one()
    assert (update.old_status, update.new_status) == ("pending", "in_progress")
    assert update.public_response == "We are looking into it." and update.internal_note == "Call maintenance"


def test_resolving_requires_resolution_details(client, users, category):
    cid = make_complaint(users["alice"], category, assigned_to_id=users["staff"])
    login(client, "staff@college.edu")
    assert client.post(f"/staff/complaints/{cid}", data={"status": "resolved"}).status_code == 400
    assert fresh(Complaint, cid).status == "pending"
    response = client.post(f"/staff/complaints/{cid}", data={"status": "resolved", "resolution_note": "Replaced the fan."})
    assert response.status_code == 302
    complaint = fresh(Complaint, cid)
    assert complaint.status == "resolved" and complaint.resolved_at is not None
    assert complaint.resolution_note == "Replaced the fan."


@pytest.mark.parametrize("data", [
    {"status": "pending-ish"},
    {"status": "rejected"},      # needs a student-visible explanation
    {"status": "pending"},       # no change and no note
])
def test_invalid_staff_updates_are_rejected(client, users, category, data):
    cid = make_complaint(users["alice"], category, assigned_to_id=users["staff"])
    login(client, "staff@college.edu")
    assert client.post(f"/staff/complaints/{cid}", data=data).status_code == 400
    assert fresh(Complaint, cid).status == "pending"
    assert ComplaintUpdate.query.count() == 0


# ---------- admin: monitoring, overdue, users, org ----------

def test_admin_sees_all_complaints_and_overdue_filter(client, users, category):
    late = make_complaint(users["alice"], category, subject="Very late complaint")
    make_complaint(users["bob"], category, subject="Fresh complaint")
    complaint = db.session.get(Complaint, late)
    complaint.due_date = utcnow() - timedelta(days=2)
    db.session.commit()
    assert fresh(Complaint, late).is_overdue
    login(client, "admin@college.edu")
    everything = client.get("/admin/complaints").get_data(as_text=True)
    assert "Very late complaint" in everything and "Fresh complaint" in everything
    overdue = client.get("/admin/complaints?overdue=1").get_data(as_text=True)
    assert "Very late complaint" in overdue and "Fresh complaint" not in overdue


def test_resolved_complaints_are_never_overdue(client, users, category):
    cid = make_complaint(users["alice"], category, status="resolved")
    complaint = db.session.get(Complaint, cid)
    complaint.due_date = utcnow() - timedelta(days=5)
    db.session.commit()
    assert not fresh(Complaint, cid).is_overdue


def test_admin_dashboard_loads_with_statistics(client, users, category):
    make_complaint(users["alice"], category)
    login(client, "admin@college.edu")
    response = client.get("/admin/")
    assert response.status_code == 200 and "All complaints" in response.get_data(as_text=True)


@pytest.mark.parametrize("path", ["/admin/", "/admin/users", "/admin/organization", "/admin/complaints"])
def test_admin_pages_forbidden_for_non_admins(client, users, path):
    for email in ("alice@college.edu", "staff@college.edu"):
        client.post("/logout")
        login(client, email)
        assert client.get(path).status_code == 403


def test_staff_and_admin_pages_forbidden_for_wrong_roles(client, users):
    login(client, "alice@college.edu")
    assert client.get("/staff/").status_code == 403
    client.post("/logout")
    login(client, "admin@college.edu")
    assert client.get("/student/").status_code == 403
    assert client.get("/staff/complaints").status_code == 403


def test_admin_creates_staff_account(client, users):
    login(client, "admin@college.edu")
    client.post("/admin/users/new", data={"name": "New Staff", "email": "ns@college.edu",
                                          "password": "Passw0rd1", "role": "staff"})
    user = User.query.filter_by(email="ns@college.edu").one()
    assert user.role == "staff" and user.check_password("Passw0rd1")


def test_non_admin_cannot_create_accounts(client, users):
    login(client, "staff@college.edu")
    response = client.post("/admin/users/new", data={"name": "Evil", "email": "evil@college.edu",
                                                     "password": "Passw0rd1", "role": "admin"})
    assert response.status_code == 403
    assert User.query.filter_by(email="evil@college.edu").first() is None


def test_admin_can_disable_user_but_not_themselves(client, users):
    login(client, "admin@college.edu")
    client.post(f"/admin/users/{users['bob']}", data={"role": "student", "is_active": "0"})
    assert fresh(User, users["bob"]).is_active is False
    client.post(f"/admin/users/{users['admin']}", data={"role": "student", "is_active": "0"})
    admin = fresh(User, users["admin"])
    assert admin.role == "admin" and admin.is_active is True


def test_admin_manages_departments_and_categories(client, users, category):
    login(client, "admin@college.edu")
    client.post("/admin/departments/new", data={"name": "Physics"})
    client.post("/admin/departments/new", data={"name": "physics"})  # duplicate, case-insensitive
    assert Department.query.filter_by(name="Physics").count() == 1
    assert Department.query.count() == 1
    dept = Department.query.one()
    make_user("hod@college.edu", "staff", department_id=dept.id)
    client.post(f"/admin/departments/{dept.id}/delete")
    assert Department.query.count() == 1  # still has a user, so delete is blocked
    make_complaint(users["alice"], category)
    client.post(f"/admin/categories/{category}/delete")
    assert db.session.get(Category, category) is not None  # has complaints, so delete is blocked
