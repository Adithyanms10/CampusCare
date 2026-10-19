from datetime import datetime, timedelta, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


def utcnow():
    """Naive UTC time (MySQL DATETIME has no timezone)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


ROLES = ("student", "staff", "admin")
STATUSES = ("pending", "in_progress", "resolved", "rejected", "closed")
OPEN_STATUSES = ("pending", "in_progress")
STAFF_STATUSES = ("in_progress", "resolved", "rejected", "closed")
PRIORITIES = ("low", "medium", "high", "urgent")
SLA_DAYS = {"low": 14, "medium": 7, "high": 3, "urgent": 1}


def _in(column, values):
    return "{} IN ({})".format(column, ", ".join("'%s'" % v for v in values))


class Department(db.Model):
    __tablename__ = "departments"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    users = db.relationship("User", back_populates="department")
    categories = db.relationship("Category", back_populates="department")


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=True)

    department = db.relationship("Department", back_populates="categories")
    complaints = db.relationship("Complaint", back_populates="category")


class User(db.Model):
    __tablename__ = "users"
    __table_args__ = (db.CheckConstraint(_in("role", ROLES), name="ck_users_role"),)

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student")
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    department = db.relationship("Department", back_populates="users")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Complaint(db.Model):
    __tablename__ = "complaints"
    __table_args__ = (
        db.CheckConstraint(_in("status", STATUSES), name="ck_complaints_status"),
        db.CheckConstraint(_in("priority", PRIORITIES), name="ck_complaints_priority"),
    )

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    assigned_to_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    subject = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    priority = db.Column(db.String(20), nullable=False, default="medium")
    resolution_note = db.Column(db.Text, nullable=True)
    due_date = db.Column(db.DateTime, nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    student = db.relationship("User", foreign_keys=[student_id])
    assignee = db.relationship("User", foreign_keys=[assigned_to_id])
    category = db.relationship("Category", back_populates="complaints")
    updates = db.relationship(
        "ComplaintUpdate",
        back_populates="complaint",
        order_by="ComplaintUpdate.id",
        cascade="all, delete-orphan",
    )

    def set_priority(self, priority):
        self.priority = priority
        base = self.created_at or utcnow()
        self.due_date = base + timedelta(days=SLA_DAYS[priority])

    @property
    def is_overdue(self):
        return (
            self.status in OPEN_STATUSES
            and self.due_date is not None
            and self.due_date < utcnow()
        )


class ComplaintUpdate(db.Model):
    """One entry in a complaint's history (status change, reply, note, assignment)."""

    __tablename__ = "complaint_updates"

    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.Integer, db.ForeignKey("complaints.id"), nullable=False, index=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    old_status = db.Column(db.String(20), nullable=True)
    new_status = db.Column(db.String(20), nullable=True)
    public_response = db.Column(db.Text, nullable=True)  # student can see
    internal_note = db.Column(db.Text, nullable=True)  # staff/admin only
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    complaint = db.relationship("Complaint", back_populates="updates")
    author = db.relationship("User")

    @property
    def status_changed(self):
        return self.old_status != self.new_status

    @property
    def visible_to_student(self):
        return bool(self.public_response) or self.status_changed
