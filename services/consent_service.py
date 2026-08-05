from models import db, DataSubject, Consent, ConsentHistory, PolicyVersion
from services.audit_service import AuditService
from datetime import datetime, timezone


class ConsentService:

    @staticmethod
    def get_or_create_subject(name, email, org_id, phone=None, country=None):
        subject = DataSubject.query.filter_by(email=email.lower().strip(), org_id=org_id).first()
        if not subject:
            subject = DataSubject(
                name=name,
                email=email.lower().strip(),
                phone=phone,
                country=country,
                org_id=org_id,
            )
            db.session.add(subject)
            db.session.flush()
        return subject

    @staticmethod
    def create_consent(subject, purpose, legal_basis, channel, policy_version, notes,
                       org_id, created_by=None, policy_version_id=None, source="Web UI",
                       ip_address=None):
        consent = Consent(
            subject_id=subject.id,
            purpose=purpose,
            legal_basis=legal_basis,
            channel=channel,
            status="Active",
            policy_version=policy_version,
            policy_version_id=policy_version_id,
            notes=notes,
            org_id=org_id,
            created_by=created_by,
        )
        db.session.add(consent)
        db.session.flush()

        ConsentService._record_history(
            consent_id=consent.id,
            old_status=None,
            new_status="Active",
            changed_by=subject.name,
            reason=f"Consent granted for '{purpose}' via {channel}.",
            source=source,
            ip_address=ip_address,
        )
        AuditService.log(
            action="Consent Granted",
            entity_type="Consent",
            entity_id=consent.id,
            details=f"Purpose: {purpose} | Channel: {channel} | Policy: {policy_version}",
            org_id=org_id,
        )
        return consent

    @staticmethod
    def withdraw_consent(consent, actor_name, reason=None, source="Web UI", ip_address=None):
        old_status = consent.status
        consent.status = "Withdrawn"
        consent.updated_at = datetime.now(timezone.utc)
        ConsentService._record_history(
            consent_id=consent.id,
            old_status=old_status,
            new_status="Withdrawn",
            changed_by=actor_name,
            reason=reason or "Consent withdrawn.",
            source=source,
            ip_address=ip_address,
        )
        AuditService.log(
            action="Consent Withdrawn",
            entity_type="Consent",
            entity_id=consent.id,
            details=f"Purpose: {consent.purpose} | Reason: {reason or 'Not specified'}",
            org_id=consent.org_id,
        )

    @staticmethod
    def reactivate_consent(consent, actor_name, reason=None, ip_address=None):
        old_status = consent.status
        consent.status = "Active"
        consent.updated_at = datetime.now(timezone.utc)
        ConsentService._record_history(
            consent_id=consent.id,
            old_status=old_status,
            new_status="Active",
            changed_by=actor_name,
            reason=reason or "Consent reactivated.",
            source="Web UI",
            ip_address=ip_address,
        )
        AuditService.log(
            action="Consent Reactivated",
            entity_type="Consent",
            entity_id=consent.id,
            details=f"Purpose: {consent.purpose}",
            org_id=consent.org_id,
        )

    @staticmethod
    def _record_history(consent_id, old_status, new_status, changed_by, reason,
                        source="Web UI", ip_address=None):
        h = ConsentHistory(
            consent_id=consent_id,
            old_status=old_status,
            new_status=new_status,
            changed_by=changed_by,
            reason=reason,
            source=source,
            ip_address=ip_address,
        )
        db.session.add(h)
