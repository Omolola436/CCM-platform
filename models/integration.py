from .base import db
from datetime import datetime, timezone

INTEGRATION_TYPES = ["crm", "email", "analytics", "webhook", "api", "custom"]
INTEGRATION_STATUSES = ["active", "inactive", "error", "pending"]


class Integration(db.Model):
    __tablename__ = "integrations"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=True)
    endpoint = db.Column(db.String(500), nullable=True)
    api_key = db.Column(db.String(500), nullable=True)
    config = db.Column(db.JSON, nullable=True)
    status = db.Column(db.String(50), default="inactive")
    last_synced = db.Column(db.DateTime(timezone=True), nullable=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "status": self.status,
            "last_synced": self.last_synced.isoformat() if self.last_synced else None,
        }


class Webhook(db.Model):
    __tablename__ = "webhooks"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    events = db.Column(db.JSON, nullable=False, default=list)
    secret = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(50), default="active")
    last_triggered = db.Column(db.DateTime(timezone=True), nullable=True)
    last_response_code = db.Column(db.Integer, nullable=True)
    trigger_count = db.Column(db.Integer, default=0)
    org_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "events": self.events,
            "status": self.status,
            "trigger_count": self.trigger_count,
            "last_triggered": self.last_triggered.isoformat() if self.last_triggered else None,
        }
