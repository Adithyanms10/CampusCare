import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.models import Category, Complaint, Department, User

PASSWORD = "Passw0rd1"


@pytest.fixture()
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def make_user(email, role="student", name=None, active=True, department_id=None):
    user = User(name=name or email.split("@")[0].title(), email=email, role=role,
                is_active=active, department_id=department_id)
    user.set_password(PASSWORD)
    db.session.add(user)
    db.session.commit()
    return user.id


def make_complaint(student_id, category_id, subject="Broken fan in room 12", assigned_to_id=None, status="pending"):
    complaint = Complaint(student_id=student_id, category_id=category_id, subject=subject,
                          description="The ceiling fan has not worked for two weeks.",
                          assigned_to_id=assigned_to_id, status=status)
    complaint.set_priority("medium")
    db.session.add(complaint)
    db.session.commit()
    return complaint.id


def fresh(model, pk):
    """Reload an object so tests see what the request handlers committed."""
    db.session.expire_all()
    return db.session.get(model, pk)


def login(client, email, password=PASSWORD):
    return client.post("/login", data={"email": email, "password": password})


@pytest.fixture()
def category(app):
    cat = Category(name="Hostel")
    other = Category(name="Library")
    db.session.add_all([cat, other])
    db.session.commit()
    return cat.id


@pytest.fixture()
def other_category(app, category):
    return Category.query.filter_by(name="Library").first().id


@pytest.fixture()
def users(app):
    return {
        "alice": make_user("alice@college.edu", "student"),
        "bob": make_user("bob@college.edu", "student"),
        "staff": make_user("staff@college.edu", "staff", name="Sam Staff"),
        "staff2": make_user("staff2@college.edu", "staff", name="Sara Staff"),
        "admin": make_user("admin@college.edu", "admin"),
    }
