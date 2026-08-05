from .base import db
from datetime import datetime, timezone


class Organization(db.Model):
    __tablename__ = "organizations"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    domain = db.Column(db.String(255), nullable=True)
    plan = db.Column(db.String(50), default="enterprise")
    industry = db.Column(db.String(100), nullable=True)
    country = db.Column(db.String(100), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    users = db.relationship("User", backref="organization", lazy=True, cascade="all, delete-orphan")
    data_subjects = db.relationship("DataSubject", backref="organization", lazy=True, cascade="all, delete-orphan")
    consents = db.relationship("Consent", backref="organization", lazy=True, cascade="all, delete-orphan")
    policy_versions = db.relationship("PolicyVersion", backref="organization", lazy=True, cascade="all, delete-orphan")
    audit_logs = db.relationship("AuditLog", backref="organization", lazy=True, cascade="all, delete-orphan")
    integrations = db.relationship("Integration", backref="organization", lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "domain": self.domain,
            "plan": self.plan,
            "industry": self.industry,
        }
