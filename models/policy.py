from .base import db
from datetime import datetime, timezone


class PolicyVersion(db.Model):
    __tablename__ = "policy_versions"

    id = db.Column(db.Integer, primary_key=True)
    version = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    summary = db.Column(db.Text, nullable=True)
    effective_date = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    is_current = db.Column(db.Boolean, default=False)
    org_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    consents = db.relationship("Consent", backref="policy_version_obj", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "version": self.version,
            "title": self.title,
            "summary": self.summary,
            "effective_date": self.effective_date.isoformat() if self.effective_date else None,
            "is_current": self.is_current,
        }
