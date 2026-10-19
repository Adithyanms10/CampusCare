import click
from flask import Flask, render_template

from .config import Config
from .extensions import db, migrate
from .security import init_security


def create_app(config_object=None):
    app = Flask(__name__)
    app.config.from_object(config_object or Config)

    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY is not set. Copy .env.example to .env and fill it in.")
    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        raise RuntimeError("DATABASE_URL is not set. Copy .env.example to .env and fill it in.")

    db.init_app(app)
    from . import models  # noqa: F401  (registers tables for migrations)

    migrate.init_app(app, db)
    init_security(app)

    from .blueprints import admin, auth, staff, student

    for module in (auth, student, staff, admin):
        app.register_blueprint(module.bp)

    register_errors(app)
    register_cli(app)
    return app


def register_errors(app):
    messages = {
        400: "Bad request",
        403: "You do not have permission to view this page.",
        404: "Page not found",
        500: "Something went wrong on our side.",
    }

    def handler(error):
        code = getattr(error, "code", 500)
        detail = getattr(error, "description", "") if code == 400 else messages.get(code, "Error")
        return render_template("error.html", code=code, message=detail or messages.get(code)), code

    for code in messages:
        app.register_error_handler(code, handler)


def register_cli(app):
    from .models import Category, Department, User

    @app.cli.command("init-data")
    def init_data():
        """Create starter departments and complaint categories."""
        departments = ["Computer Science", "Administration", "Library", "Hostel", "Accounts"]
        categories = ["Academic", "Hostel", "Library", "Infrastructure", "Fees and Accounts", "Harassment", "Other"]
        for name in departments:
            if not Department.query.filter_by(name=name).first():
                db.session.add(Department(name=name))
        for name in categories:
            if not Category.query.filter_by(name=name).first():
                db.session.add(Category(name=name))
        db.session.commit()
        click.echo("Starter departments and categories created.")

    @app.cli.command("create-admin")
    @click.option("--name", prompt=True)
    @click.option("--email", prompt=True)
    @click.password_option()
    def create_admin(name, email, password):
        """Create the first administrator account."""
        from .validators import check_password_strength

        email = email.strip().lower()
        problem = check_password_strength(password)
        if problem:
            raise click.ClickException(problem)
        if User.query.filter_by(email=email).first():
            raise click.ClickException("A user with that email already exists.")
        user = User(name=name.strip(), email=email, role="admin")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Administrator {email} created.")
