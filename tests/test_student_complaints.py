import pytest

from app.extensions import db
from app.models import Complaint, ComplaintUpdate

from .conftest import fresh, login, make_complaint

GOOD = {"subject": "Water leak in corridor", "description": "There is a leak outside room 12 since Monday."}


def test_student_can_submit_complaint(client, users, category):
    login(client, "alice@college.edu")
    response = client.post("/student/complaints/new", data={**GOOD, "category_id": str(category)})
    assert response.status_code == 302
    complaint = Complaint.query.one()
    assert complaint.student_id == users["alice"]
    assert complaint.status == "pending"
    assert complaint.priority == "medium"
    assert complaint.due_date is not None
    assert complaint.assigned_to_id is None


@pytest.mark.parametrize("change", [
    {"subject": "Hi"},
    {"description": "too short"},
    {"category_id": "9999"},
    {"category_id": ""},
    {"category_id": "abc"},
])
def test_invalid_complaint_is_rejected(client, users, category, change):
    login(client, "alice@college.edu")
    response = client.post("/student/complaints/new", data={**GOOD, "category_id": str(category), **change})
    assert response.status_code == 400
    assert Complaint.query.count() == 0


def test_student_sees_only_own_complaints(client, users, category):
    make_complaint(users["alice"], category, subject="Alice complaint here")
    make_complaint(users["bob"], category, subject="Bob private complaint")
    login(client, "alice@college.edu")
    page = client.get("/student/complaints").get_data(as_text=True)
    assert "Alice complaint here" in page
    assert "Bob private complaint" not in page


def test_student_cannot_view_another_students_complaint(client, users, category):
    bobs = make_complaint(users["bob"], category)
    login(client, "alice@college.edu")
    assert client.get(f"/student/complaints/{bobs}").status_code == 404


def test_student_cannot_modify_complaints_via_staff_or_admin_routes(client, users, category):
    own = make_complaint(users["alice"], category, assigned_to_id=users["staff"])
    login(client, "alice@college.edu")
    assert client.post(f"/staff/complaints/{own}", data={"status": "resolved"}).status_code == 403
    assert client.post(f"/admin/complaints/{own}/assign", data={"priority": "urgent"}).status_code == 403
    assert fresh(Complaint, own).status == "pending"


def test_student_filters_by_status_and_category(client, users, category, other_category):
    make_complaint(users["alice"], category, subject="Pending hostel issue")
    make_complaint(users["alice"], other_category, subject="Resolved library issue", status="resolved")
    login(client, "alice@college.edu")
    by_status = client.get("/student/complaints?status=resolved").get_data(as_text=True)
    assert "Resolved library issue" in by_status and "Pending hostel issue" not in by_status
    by_category = client.get(f"/student/complaints?category={category}").get_data(as_text=True)
    assert "Pending hostel issue" in by_category and "Resolved library issue" not in by_category


def test_student_sees_response_and_resolution_but_not_internal_notes(client, users, category):
    cid = make_complaint(users["alice"], category, assigned_to_id=users["staff"])
    complaint = db.session.get(Complaint, cid)
    complaint.status, complaint.resolution_note = "resolved", "Fan was replaced on Friday."
    db.session.add(ComplaintUpdate(complaint_id=cid, author_id=users["staff"], old_status="pending",
                                   new_status="resolved", public_response="We fixed it today.",
                                   internal_note="Contractor invoice pending"))
    db.session.commit()
    login(client, "alice@college.edu")
    page = client.get(f"/student/complaints/{cid}").get_data(as_text=True)
    assert "We fixed it today." in page
    assert "Fan was replaced on Friday." in page
    assert "Contractor invoice pending" not in page
