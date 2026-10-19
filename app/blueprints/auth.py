from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from ..extensions import db
from ..models import User
from ..security import role_home
from ..validators import validate_registration

bp = Blueprint("auth", __name__)


@bp.route("/")
def index():
    if g.user:
        return redirect(role_home(g.user.role))
    return redirect(url_for("auth.login"))


@bp.route("/register", methods=["GET", "POST"])
def register():
    if g.user:
        return redirect(role_home(g.user.role))
    if request.method == "POST":
        data, errors = validate_registration(request.form)
        if errors:
            for message in errors:
                flash(message, "error")
            return render_template("auth/register.html", form=request.form), 400
        # Self-registration always creates a student. Staff/admin are created by an administrator.
        user = User(name=data["name"], email=data["email"], role="student")
        user.set_password(data["password"])
        db.session.add(user)
        db.session.commit()
        flash("Account created. You can log in now.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/register.html", form={})


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(role_home(g.user.role))
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        user = User.query.filter_by(email=email).first()
        if user is None or not user.check_password(password):
            flash("Incorrect email or password.", "error")
            return render_template("auth/login.html", form=request.form), 401
        if not user.is_active:
            flash("This account is disabled. Contact an administrator.", "error")
            return render_template("auth/login.html", form=request.form), 403
        session.clear()  # prevents session fixation
        session["user_id"] = user.id
        session.permanent = True
        return redirect(role_home(user.role))
    return render_template("auth/login.html", form={})


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))
