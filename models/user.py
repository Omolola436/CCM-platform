from .base import db
from flask_login import UserMixin
from datetime import datetime, timezone


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(50), default="admin", nullable=False)
    org_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime(timezone=True), nullable=True)
    last_login_ip = db.Column(db.String(45), nullable=True)
    last_login_location = db.Column(db.String(100), nullable=True)
    failed_login_attempts = db.Column(db.Integer, default=0, nullable=False)
    locked_until = db.Column(db.DateTime(timezone=True), nullable=True)
    password_changed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    reset_token = db.Column(db.String(255), nullable=True)
    reset_token_expires_at = db.Column(db.DateTime(timezone=True), nullable=True)
    mfa_enabled = db.Column(db.Boolean, default=False, nullable=False)
    mfa_secret = db.Column(db.String(255), nullable=True)
    mfa_last_verified_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    notifications = db.relationship("Notification", backref="user", lazy=True, cascade="all, delete-orphan")

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def is_admin(self):
        return self.role == "admin"

    @property
    def is_manager(self):
        return self.role in {"admin", "manager"}

    def can(self, action):
        return True

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "full_name": self.full_name,
            "role": "admin",
            "is_active": self.is_active,
        }
