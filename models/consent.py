from .base import db
from datetime import datetime, timezone

PURPOSES = [
    "Marketing Communications",
    "Analytics & Profiling",
    "Third-Party Sharing",
    "Service Delivery",
    "Research & Development",
    "Newsletter",
    "SMS Notifications",
    "Email Notifications",
    "Location Tracking",
    "Behavioural Advertising",
]

LEGAL_BASES = [
    "Consent",
    "Contract",
    "Legitimate Interest",
    "Legal Obligation",
    "Vital Interest",
    "Public Task",
]

CHANNELS = [
    "Website",
    "Mobile App",
    "Physical Form",
    "CRM System",
    "Call Centre",
    "Customer Portal",
    "Email",
    "Branch",
    "API",
]

STATUSES = ["Active", "Withdrawn", "Expired", "Pending"]


class DataSubject(db.Model):
    __tablename__ = "data_subjects"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(50), nullable=True)
    country = db.Column(db.String(100), nullable=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    consents = db.relationship("Consent", backref="data_subject", lazy=True, cascade="all, delete-orphan")

    __table_args__ = (db.UniqueConstraint("email", "org_id", name="uq_subject_email_org"),)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "country": self.country,
        }


class Consent(db.Model):
    __tablename__ = "consents"

    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("data_subjects.id"), nullable=False)
    purpose = db.Column(db.String(255), nullable=False)
    legal_basis = db.Column(db.String(100), nullable=False)
    channel = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(50), nullable=False, default="Active")
    policy_version_id = db.Column(db.Integer, db.ForeignKey("policy_versions.id"), nullable=True)
    policy_version = db.Column(db.String(50), nullable=False, default="v1.0")
    notes = db.Column(db.Text, nullable=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    expires_at = db.Column(db.DateTime(timezone=True), nullable=True)
    source_document = db.Column(db.String(255), nullable=True)
    # SHA-256 of immutable fields — computed at creation, verifiable anytime
    consent_fingerprint = db.Column(db.String(64), nullable=True)

    history = db.relationship("ConsentHistory", backref="consent", lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "subject_id": self.subject_id,
            "subject_name": self.data_subject.name if self.data_subject else None,
            "subject_email": self.data_subject.email if self.data_subject else None,
            "purpose": self.purpose,
            "legal_basis": self.legal_basis,
            "channel": self.channel,
            "status": self.status,
            "policy_version": self.policy_version,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


class ConsentHistory(db.Model):
    __tablename__ = "consent_history"

    id = db.Column(db.Integer, primary_key=True)
    consent_id = db.Column(db.Integer, db.ForeignKey("consents.id"), nullable=False)
    old_status = db.Column(db.String(50), nullable=True)
    new_status = db.Column(db.String(50), nullable=False)
    changed_by = db.Column(db.String(255), nullable=True)
    reason = db.Column(db.Text, nullable=True)
    source = db.Column(db.String(100), default="Web UI")
    ip_address = db.Column(db.String(50), nullable=True)
    timestamp = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "consent_id": self.consent_id,
            "old_status": self.old_status,
            "new_status": self.new_status,
            "changed_by": self.changed_by,
            "reason": self.reason,
            "source": self.source,
            "ip_address": self.ip_address,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }
