from .base import db
from datetime import datetime, timezone


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    entity_type = db.Column(db.String(100), nullable=False)
    entity_id = db.Column(db.Integer, nullable=True)
    action = db.Column(db.String(100), nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    actor_email = db.Column(db.String(255), nullable=True)
    actor_name = db.Column(db.String(255), nullable=True)
    actor_role = db.Column(db.String(50), nullable=True)
    details = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(50), nullable=True)
    location = db.Column(db.String(100), nullable=True)
    user_agent = db.Column(db.String(500), nullable=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "action": self.action,
            "actor_email": self.actor_email,
            "actor_name": self.actor_name,
            "actor_role": self.actor_role,
            "details": self.details,
            "ip_address": self.ip_address,
            "location": self.location,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
