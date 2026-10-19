from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from ..extensions import db
from ..models import STATUSES, Category, Complaint, utcnow
from ..security import role_required
from ..services import apply_filters, status_counts
from ..validators import validate_complaint

bp = Blueprint("student", __name__, url_prefix="/student")



@bp.route("/")
@role_required("student")
def dashboard():
    mine = Complaint.student_id == g.user.id
    counts = status_counts(mine)
    recent = Complaint.query.filter(mine).order_by(Complaint.created_at.desc()).limit(5).all()
    cards = [
        {"label": "Total complaints", "value": counts["total"], "tone": "neutral"},
        {"label": "Pending", "value": counts["pending"], "tone": "warn"},
        {"label": "In progress", "value": counts["in_progress"], "tone": "info"},
        {"label": "Resolved", "value": counts["resolved"], "tone": "ok"},
    ]
    return render_template(
        "dashboard.html", title="My dashboard", cards=cards, recent=recent,
        detail_endpoint="student.detail", list_endpoint="student.complaints",
    )


@bp.route("/complaints")
@role_required("student")
def complaints():
    query = Complaint.query.filter(Complaint.student_id == g.user.id)
    items = apply_filters(query, request.args, {"status", "category"}).all()
    return render_template(
        "complaints_list.html", title="My complaints", complaints=items,
        fields={"status", "category"}, statuses=STATUSES,
        categories=Category.query.order_by(Category.name).all(),
        detail_endpoint="student.detail", list_endpoint="student.complaints",
        show_student=False, show_assignee=False,
    )


@bp.route("/complaints/new", methods=["GET", "POST"])
@role_required("student")
def new_complaint():
    categories = Category.query.order_by(Category.name).all()
    if request.method == "POST":
        data, errors = validate_complaint(request.form)
        if errors:
            for message in errors:
                flash(message, "error")
            return render_template("complaint_new.html", title="New complaint", categories=categories, form=request.form), 400
        complaint = Complaint(
            student_id=g.user.id, category_id=data["category"].id,
            subject=data["subject"], description=data["description"], created_at=utcnow(),
        )
        complaint.set_priority("medium")
        db.session.add(complaint)
        db.session.commit()
        flash("Complaint submitted. You can track it from My complaints.", "success")
        return redirect(url_for("student.detail", complaint_id=complaint.id))
    return render_template("complaint_new.html", title="New complaint", categories=categories, form={})


@bp.route("/complaints/<int:complaint_id>")
@role_required("student")
def detail(complaint_id):
    # 404 (not 403) for other students' complaints, so existence is not leaked.
    complaint = Complaint.query.filter_by(id=complaint_id, student_id=g.user.id).first_or_404()
    updates = [u for u in complaint.updates if u.visible_to_student]
    return render_template("complaint_detail.html", title=f"Complaint #{complaint.id}", complaint=complaint, updates=updates)
