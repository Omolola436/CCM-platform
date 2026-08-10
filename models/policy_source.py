"""
PolicySource — a watched URL that feeds automatic PolicyVersion creation.

When the content at `url` changes (detected by SHA-256 hash), the sync
service auto-creates a new PolicyVersion for the org and records the event
in the audit log.
"""
from .base import db
from datetime import datetime, timezone


class PolicySource(db.Model):
    __tablename__ = "policy_sources"

    id                  = db.Column(db.Integer, primary_key=True)
    name                = db.Column(db.String(255), nullable=False)
    url                 = db.Column(db.String(1000), nullable=False)
    org_id              = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False)
    created_by          = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    is_active           = db.Column(db.Boolean, default=True, nullable=False)

    # Sync state
    content_hash        = db.Column(db.String(64), nullable=True)   # SHA-256 of last fetched text
    last_checked_at     = db.Column(db.DateTime(timezone=True), nullable=True)
    last_changed_at     = db.Column(db.DateTime(timezone=True), nullable=True)
    last_error          = db.Column(db.Text, nullable=True)
    check_interval_min  = db.Column(db.Integer, default=60, nullable=False)

    # When a change is detected, auto-set the new version as the current policy?
    auto_set_current    = db.Column(db.Boolean, default=False, nullable=False)

    created_at          = db.Column(db.DateTime(timezone=True),
                                    default=lambda: datetime.now(timezone.utc))

    versions = db.relationship("PolicyVersion", backref="source", lazy=True)

    @property
    def status(self) -> str:
        if not self.is_active:
            return "paused"
        if self.last_error:
            return "error"
        if self.last_checked_at is None:
            return "pending"
        return "ok"

    def to_dict(self) -> dict:
        return {
            "id":               self.id,
            "name":             self.name,
            "url":              self.url,
            "status":           self.status,
            "last_checked_at":  self.last_checked_at.isoformat() if self.last_checked_at else None,
            "last_changed_at":  self.last_changed_at.isoformat() if self.last_changed_at else None,
            "last_error":       self.last_error,
            "auto_set_current": self.auto_set_current,
        }
