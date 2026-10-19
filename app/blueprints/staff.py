from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from ..extensions import db
from ..models import PRIORITIES, STAFF_STATUSES, STATUSES, Complaint, ComplaintUpdate, utcnow
from ..security import role_required
from ..services import apply_filters, overdue_filter, status_counts
from ..validators import validate_staff_update

bp = Blueprint("staff", __name__, url_prefix="/staff")


@bp.route("/")
@role_required("staff")
def dashboard():
    mine = Complaint.assigned_to_id == g.user.id
    counts = status_counts(mine)
    overdue = overdue_filter(Complaint.query.filter(mine)).count()
    recent = Complaint.query.filter(mine).order_by(Complaint.created_at.desc()).limit(5).all()
    cards = [
        {"label": "Assigned to me", "value": counts["total"], "tone": "neutral"},
        {"label": "Pending", "value": counts["pending"], "tone": "warn"},
        {"label": "In progress", "value": counts["in_progress"], "tone": "info"},
        {"label": "Overdue", "value": overdue, "tone": "danger"},
    ]
    return render_template(
        "dashboard.html", title="Staff dashboard", cards=cards, recent=recent,
        detail_endpoint="staff.detail", list_endpoint="staff.complaints",
    )


@bp.route("/complaints")
@role_required("staff")
def complaints():
    query = Complaint.query.filter(Complaint.assigned_to_id == g.user.id)
    items = apply_filters(query, request.args, {"status", "priority", "overdue"}).all()
    return render_template(
        "complaints_list.html", title="Assigned complaints", complaints=items,
        fields={"status", "priority", "overdue"}, statuses=STATUSES, priorities=PRIORITIES,
        detail_endpoint="staff.detail", list_endpoint="staff.complaints",
        show_student=True, show_assignee=False,
    )


@bp.route("/complaints/<int:complaint_id>", methods=["GET", "POST"])
@role_required("staff")
def detail(complaint_id):
    complaint = Complaint.query.filter_by(id=complaint_id, assigned_to_id=g.user.id).first_or_404()
    if request.method == "POST":
        data, errors = validate_staff_update(request.form, complaint)
        if errors:
            for message in errors:
                flash(message, "error")
            return render_template(
                "complaint_detail.html", title=f"Complaint #{complaint.id}", complaint=complaint,
                updates=complaint.updates, staff_statuses=STAFF_STATUSES, form=request.form,
            ), 400
        old_status = complaint.status
        complaint.status = data["status"]
        if data["resolution_note"]:
            complaint.resolution_note = data["resolution_note"]
        if data["status"] == "resolved" and old_status != "resolved":
            complaint.resolved_at = utcnow()
        db.session.add(ComplaintUpdate(
            complaint=complaint, author_id=g.user.id, old_status=old_status, new_status=data["status"],
            public_response=data["public_response"] or None, internal_note=data["internal_note"] or None,
        ))
        db.session.commit()
        flash("Complaint updated.", "success")
        return redirect(url_for("staff.detail", complaint_id=complaint.id))
    return render_template(
        "complaint_detail.html", title=f"Complaint #{complaint.id}", complaint=complaint,
        updates=complaint.updates, staff_statuses=STAFF_STATUSES, form={},
    )
