"""
ConsentService — all consent lifecycle operations go through here.

Integrity guarantee
-------------------
Every status transition creates an immutable ConsentHistory entry BEFORE
the Consent record is updated.  The `consent_fingerprint` stored at creation
time (SHA-256 of the immutable fields) lets an auditor verify that core
consent data (subject_id, purpose, legal_basis, channel, policy_version,
org_id, created_at) was never tampered with after the record was committed.
"""
import hashlib
import json
from models import db, DataSubject, Consent, ConsentHistory, PolicyVersion
from services.audit_service import AuditService
from datetime import datetime, timezone


class ConsentService:

    # ── Subjects ──────────────────────────────────────────────────────────────

    @staticmethod
    def get_or_create_subject(name, email, org_id, phone=None, country=None):
        subject = DataSubject.query.filter_by(
            email=email.lower().strip(), org_id=org_id
        ).first()
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

    # ── Consent creation ──────────────────────────────────────────────────────

    @staticmethod
    def create_consent(subject, purpose, legal_basis, channel, policy_version, notes,
                       org_id, created_by=None, policy_version_id=None, source="Web UI",
                       ip_address=None):
        now = datetime.now(timezone.utc)
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
            created_at=now,
        )
        db.session.add(consent)
        db.session.flush()  # obtain consent.id and created_at

        # Compute and store integrity fingerprint
        consent.consent_fingerprint = ConsentService._compute_fingerprint(consent)
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

    # ── Status transitions ────────────────────────────────────────────────────

    @staticmethod
    def withdraw_consent(consent, actor_name, reason=None, source="Web UI", ip_address=None):
        old_status = consent.status
        # History first — before mutating the record
        ConsentService._record_history(
            consent_id=consent.id,
            old_status=old_status,
            new_status="Withdrawn",
            changed_by=actor_name,
            reason=reason or "Consent withdrawn.",
            source=source,
            ip_address=ip_address,
        )
        consent.status = "Withdrawn"
        consent.updated_at = datetime.now(timezone.utc)
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
        ConsentService._record_history(
            consent_id=consent.id,
            old_status=old_status,
            new_status="Active",
            changed_by=actor_name,
            reason=reason or "Consent reactivated.",
            source="Web UI",
            ip_address=ip_address,
        )
        consent.status = "Active"
        consent.updated_at = datetime.now(timezone.utc)
        AuditService.log(
            action="Consent Reactivated",
            entity_type="Consent",
            entity_id=consent.id,
            details=f"Purpose: {consent.purpose}",
            org_id=consent.org_id,
        )

    # ── Integrity ─────────────────────────────────────────────────────────────

    @staticmethod
    def _compute_fingerprint(consent: Consent) -> str:
        """
        Return a SHA-256 hex digest over the immutable fields of a Consent.
        Any post-creation change to these fields would produce a different hash.
        """
        payload = json.dumps({
            "subject_id":    consent.subject_id,
            "purpose":       consent.purpose,
            "legal_basis":   consent.legal_basis,
            "channel":       consent.channel,
            "policy_version": consent.policy_version,
            "org_id":        consent.org_id,
            "created_at":    consent.created_at.isoformat() if consent.created_at else None,
        }, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()

    @staticmethod
    def verify_fingerprint(consent: Consent) -> bool:
        """
        Return True if the consent record's immutable fields match the stored fingerprint.
        A False result indicates the record may have been tampered with.
        """
        if not consent.consent_fingerprint:
            return False  # pre-fingerprint record; flag for manual review
        return consent.consent_fingerprint == ConsentService._compute_fingerprint(consent)

    # ── Internal ──────────────────────────────────────────────────────────────

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
