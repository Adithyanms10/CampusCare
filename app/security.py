import secrets
from functools import wraps

from flask import abort, current_app, flash, g, redirect, request, session, url_for

from .extensions import db
from .models import User


def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(16)
    return session["csrf_token"]


def role_home(role):
    return url_for({"student": "student.dashboard", "staff": "staff.dashboard", "admin": "admin.dashboard"}[role])


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("Please log in to continue.", "error")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped


def role_required(*roles):
    """Backend authorization: 401-style redirect if logged out, 403 if wrong role."""

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if g.user is None:
                flash("Please log in to continue.", "error")
                return redirect(url_for("auth.login"))
            if g.user.role not in roles:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


def init_security(app):
    @app.before_request
    def load_user():
        g.user = None
        user_id = session.get("user_id")
        if user_id:
            user = db.session.get(User, user_id)
            if user is not None and user.is_active:
                g.user = user
            else:
                session.clear()

    @app.before_request
    def csrf_protect():
        if not current_app.config.get("CSRF_ENABLED", True):
            return
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            sent = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token") or ""
            expected = session.get("csrf_token") or ""
            if not expected or not secrets.compare_digest(sent, expected):
                abort(400, description="Your form expired or was invalid. Please go back and try again.")

    # Jinja global (not just context) so imported macros like csrf() can call it.
    app.jinja_env.globals["csrf_token"] = csrf_token

    @app.context_processor
    def inject_globals():
        return {"current_user": g.get("user")}

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        return response
