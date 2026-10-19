from sqlalchemy import func

from .extensions import db
from .models import OPEN_STATUSES, PRIORITIES, STATUSES, Complaint, utcnow


def apply_filters(query, args, fields):
    """Apply whitelisted filters from the query string. Invalid values are ignored."""
    status = args.get("status", "")
    if "status" in fields and status in STATUSES:
        query = query.filter(Complaint.status == status)
    priority = args.get("priority", "")
    if "priority" in fields and priority in PRIORITIES:
        query = query.filter(Complaint.priority == priority)
    category = args.get("category", "")
    if "category" in fields and category.isdigit():
        query = query.filter(Complaint.category_id == int(category))
    assignee = args.get("assignee", "")
    if "assignee" in fields:
        if assignee == "none":
            query = query.filter(Complaint.assigned_to_id.is_(None))
        elif assignee.isdigit():
            query = query.filter(Complaint.assigned_to_id == int(assignee))
    if "overdue" in fields and args.get("overdue") == "1":
        query = overdue_filter(query)
    return query.order_by(Complaint.created_at.desc(), Complaint.id.desc())


def overdue_filter(query):
    return query.filter(Complaint.status.in_(OPEN_STATUSES), Complaint.due_date < utcnow())


def status_counts(*criteria):
    rows = (
        db.session.query(Complaint.status, func.count(Complaint.id))
        .filter(*criteria)
        .group_by(Complaint.status)
        .all()
    )
    counts = {s: 0 for s in STATUSES}
    counts.update(dict(rows))
    counts["total"] = sum(counts[s] for s in STATUSES)
    return counts
