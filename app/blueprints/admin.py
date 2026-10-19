from flask import Blueprint, flash, g, redirect, render_template, request, url_for
from sqlalchemy import func

from ..extensions import db
from ..models import PRIORITIES, ROLES, STATUSES, Category, Complaint, ComplaintUpdate, Department, User
from ..security import role_required
from ..services import apply_filters, overdue_filter, status_counts
from ..validators import (
    validate_assignment, validate_name, validate_registration, validate_user_fields,
)

bp = Blueprint("admin", __name__, url_prefix="/admin")


def _flash_all(errors):
    for message in errors:
        flash(message, "error")


def _active_staff():
    return User.query.filter_by(role="staff", is_active=True).order_by(User.name).all()


@bp.route("/")
@role_required("admin")
def dashboard():
    counts = status_counts()
    overdue = overdue_filter(Complaint.query).count()
    unassigned = Complaint.query.filter(
        Complaint.assigned_to_id.is_(None), Complaint.status.in_(("pending", "in_progress"))
    ).count()
    cards = [
        {"label": "All complaints", "value": counts["total"], "tone": "neutral"},
        {"label": "Pending", "value": counts["pending"], "tone": "warn"},
        {"label": "In progress", "value": counts["in_progress"], "tone": "info"},
        {"label": "Resolved", "value": counts["resolved"], "tone": "ok"},
        {"label": "Unassigned", "value": unassigned, "tone": "warn"},
        {"label": "Overdue", "value": overdue, "tone": "danger"},
    ]
    recent = Complaint.query.order_by(Complaint.created_at.desc()).limit(5).all()
    by_category = (
        db.session.query(Category.name, func.count(Complaint.id))
        .outerjoin(Complaint, Complaint.category_id == Category.id)
        .group_by(Category.id, Category.name).order_by(Category.name).all()
    )
    return render_template(
        "dashboard.html", title="Admin dashboard", cards=cards, recent=recent,
        by_category=by_category, detail_endpoint="admin.detail", list_endpoint="admin.complaints",
    )


@bp.route("/complaints")
@role_required("admin")
def complaints():
    fields = {"status", "priority", "category", "assignee", "overdue"}
    items = apply_filters(Complaint.query, request.args, fields).all()
    return render_template(
        "complaints_list.html", title="All complaints", complaints=items, fields=fields,
        statuses=STATUSES, priorities=PRIORITIES, categories=Category.query.order_by(Category.name).all(),
        assignees=_active_staff(), detail_endpoint="admin.detail", list_endpoint="admin.complaints",
        show_student=True, show_assignee=True,
    )


@bp.route("/complaints/<int:complaint_id>")
@role_required("admin")
def detail(complaint_id):
    complaint = db.get_or_404(Complaint, complaint_id)
    return render_template(
        "complaint_detail.html", title=f"Complaint #{complaint.id}", complaint=complaint,
        updates=complaint.updates, priorities=PRIORITIES, assignees=_active_staff(),
    )


@bp.route("/complaints/<int:complaint_id>/assign", methods=["POST"])
@role_required("admin")
def assign(complaint_id):
    complaint = db.get_or_404(Complaint, complaint_id)
    data, errors = validate_assignment(request.form)
    if errors:
        _flash_all(errors)
        return redirect(url_for("admin.detail", complaint_id=complaint.id)), 303
    changes = []
    new_assignee_id = data["assignee"].id if data["assignee"] else None
    if new_assignee_id != complaint.assigned_to_id:
        complaint.assigned_to_id = new_assignee_id
        changes.append("Assigned to " + (data["assignee"].name if data["assignee"] else "nobody"))
    if data["priority"] != complaint.priority:
        complaint.set_priority(data["priority"])
        changes.append("Priority set to " + data["priority"])
    if changes:
        db.session.add(ComplaintUpdate(
            complaint=complaint, author_id=g.user.id, old_status=complaint.status,
            new_status=complaint.status, internal_note="; ".join(changes),
        ))
        db.session.commit()
        flash("Complaint updated.", "success")
    else:
        flash("No changes to save.", "error")
    return redirect(url_for("admin.detail", complaint_id=complaint.id))


@bp.route("/users")
@role_required("admin")
def users():
    return render_template(
        "admin_users.html", title="Users", users=User.query.order_by(User.role, User.name).all(),
        roles=ROLES, departments=Department.query.order_by(Department.name).all(),
    )


@bp.route("/users/new", methods=["POST"])
@role_required("admin")
def create_user():
    data, errors = validate_registration(request.form, require_confirm=False)
    fields, field_errors = validate_user_fields(request.form)
    errors += field_errors
    if errors:
        _flash_all(errors)
        return redirect(url_for("admin.users"))
    user = User(name=data["name"], email=data["email"], role=fields["role"], department=fields["department"])
    user.set_password(data["password"])
    db.session.add(user)
    db.session.commit()
    flash(f"Account created for {user.email}.", "success")
    return redirect(url_for("admin.users"))


@bp.route("/users/<int:user_id>", methods=["POST"])
@role_required("admin")
def update_user(user_id):
    user = db.get_or_404(User, user_id)
    fields, errors = validate_user_fields(request.form)
    is_active = request.form.get("is_active") == "1"
    if user.id == g.user.id and (fields["role"] != "admin" or not is_active):
        errors.append("You cannot remove your own admin access or deactivate yourself.")
    if errors:
        _flash_all(errors)
        return redirect(url_for("admin.users"))
    user.role, user.department, user.is_active = fields["role"], fields["department"], is_active
    db.session.commit()
    flash(f"Updated {user.email}.", "success")
    return redirect(url_for("admin.users"))


@bp.route("/organization")
@role_required("admin")
def organization():
    return render_template(
        "admin_organization.html", title="Departments and categories",
        departments=Department.query.order_by(Department.name).all(),
        categories=Category.query.order_by(Category.name).all(),
    )


def _add_named(model, label):
    name, errors = validate_name(request.form, label)
    if not errors and model.query.filter(func.lower(model.name) == name.lower()).first():
        errors.append(f"{label} already exists.")
    if errors:
        _flash_all(errors)
        return None
    return name


@bp.route("/departments/new", methods=["POST"])
@role_required("admin")
def add_department():
    name = _add_named(Department, "Department")
    if name:
        db.session.add(Department(name=name))
        db.session.commit()
        flash("Department added.", "success")
    return redirect(url_for("admin.organization"))


@bp.route("/departments/<int:dept_id>/delete", methods=["POST"])
@role_required("admin")
def delete_department(dept_id):
    dept = db.get_or_404(Department, dept_id)
    if dept.users or dept.categories:
        flash("This department still has users or categories. Move them first.", "error")
    else:
        db.session.delete(dept)
        db.session.commit()
        flash("Department deleted.", "success")
    return redirect(url_for("admin.organization"))


@bp.route("/categories/new", methods=["POST"])
@role_required("admin")
def add_category():
    name = _add_named(Category, "Category")
    if name:
        db.session.add(Category(name=name))
        db.session.commit()
        flash("Category added.", "success")
    return redirect(url_for("admin.organization"))


@bp.route("/categories/<int:cat_id>/delete", methods=["POST"])
@role_required("admin")
def delete_category(cat_id):
    cat = db.get_or_404(Category, cat_id)
    if cat.complaints:
        flash("This category already has complaints, so it cannot be deleted.", "error")
    else:
        db.session.delete(cat)
        db.session.commit()
        flash("Category deleted.", "success")
    return redirect(url_for("admin.organization"))
