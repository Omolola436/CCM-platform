from models import db, AuditLog
from flask import request
from flask_login import current_user


class AuditService:

    @staticmethod
    def log(action, entity_type="System", entity_id=None, details=None, org_id=None,
            actor_id=None, actor_email=None, actor_name=None, actor_role=None, location=None):
        ip = request.remote_addr if request else None
        ua = request.headers.get("User-Agent", "")[:500] if request else None

        if actor_id is None and current_user and current_user.is_authenticated:
            actor_id = current_user.id
            actor_email = current_user.email
            actor_name = current_user.full_name
            actor_role = actor_role or current_user.role
            org_id = org_id or current_user.org_id

        if location is None:
            location = request.remote_addr if request else None

        log = AuditLog(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor_id=actor_id,
            actor_email=actor_email,
            actor_name=actor_name,
            actor_role=actor_role,
            details=details,
            ip_address=ip,
            location=location,
            user_agent=ua,
            org_id=org_id,
        )
        db.session.add(log)
        try:
            db.session.flush()
        except Exception:
            db.session.rollback()
