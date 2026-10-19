import pytest

from app.extensions import db
from app.models import User

from .conftest import PASSWORD, login

VALID = {"name": "New Student", "email": "new@college.edu", "password": PASSWORD, "confirm_password": PASSWORD}


def test_register_creates_student_with_hashed_password(client):
    response = client.post("/register", data=VALID)
    assert response.status_code == 302
    user = User.query.filter_by(email="new@college.edu").first()
    assert user.role == "student"
    assert user.password_hash != PASSWORD
    assert user.check_password(PASSWORD)


def test_register_cannot_choose_role(client):
    client.post("/register", data={**VALID, "role": "admin"})
    assert User.query.filter_by(email="new@college.edu").first().role == "student"


@pytest.mark.parametrize("change", [
    {"email": "not-an-email"},
    {"name": "A"},
    {"password": "short1", "confirm_password": "short1"},
    {"password": "allletters", "confirm_password": "allletters"},
    {"confirm_password": "Different1"},
])
def test_register_rejects_invalid_input(client, change):
    response = client.post("/register", data={**VALID, **change})
    assert response.status_code == 400
    assert User.query.count() == 0


def test_register_rejects_duplicate_email(client, users):
    response = client.post("/register", data={**VALID, "email": "ALICE@college.edu"})
    assert response.status_code == 400
    assert User.query.filter_by(email="alice@college.edu").count() == 1


@pytest.mark.parametrize("email, target", [
    ("alice@college.edu", "/student/"),
    ("staff@college.edu", "/staff/"),
    ("admin@college.edu", "/admin/"),
])
def test_login_redirects_by_role(client, users, email, target):
    response = login(client, email)
    assert response.status_code == 302
    assert response.headers["Location"].endswith(target)


def test_login_wrong_password_and_unknown_email(client, users):
    assert login(client, "alice@college.edu", "WrongPass1").status_code == 401
    assert login(client, "nobody@college.edu").status_code == 401


def test_disabled_account_cannot_log_in(client, app):
    from .conftest import make_user
    make_user("off@college.edu", "student", active=False)
    assert login(client, "off@college.edu").status_code == 403


def test_logout_requires_post_and_clears_session(client, users):
    login(client, "alice@college.edu")
    assert client.get("/logout").status_code == 405
    assert client.post("/logout").status_code == 302
    response = client.get("/student/")
    assert response.status_code == 302 and "/login" in response.headers["Location"]


def test_protected_page_redirects_anonymous_user(client):
    response = client.get("/student/")
    assert response.status_code == 302 and "/login" in response.headers["Location"]


def test_user_disabled_mid_session_is_logged_out(client, users):
    login(client, "alice@college.edu")
    user = db.session.get(User, users["alice"])
    user.is_active = False
    db.session.commit()
    assert client.get("/student/").status_code == 302


def test_csrf_blocks_forms_without_token(app):
    app.config["CSRF_ENABLED"] = True
    client = app.test_client()
    assert client.post("/login", data={"email": "a@b.co", "password": "x"}).status_code == 400
    client.get("/login")
    with client.session_transaction() as session:
        token = session["csrf_token"]
    response = client.post("/login", data={"email": "a@b.co", "password": "x", "csrf_token": token})
    assert response.status_code == 401  # passed CSRF, failed credentials
