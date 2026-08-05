"""
REST API v1 — authenticated via session OR X-API-Key header.

Rate limiting: 200 requests/minute per IP (shared limiter from app).
Scope enforcement: key-based callers need the matching scope;
                   session-based callers need the matching RBAC permission.
"""
from flask import Blueprint, jsonify, request, g
from models import db, Consent, DataSubject, ConsentHistory
from models.consent import PURPOSES, LEGAL_BASES, CHANNELS
from services.consent_service import ConsentService
from services.audit_service import AuditService
from utils.decorators import api_auth_required, api_scope_required
from utils.permissions import (
    VIEW_CONSENT_REGISTRY, CREATE_CONSENT, WITHDRAW_CONSENT,
    VIEW_AUDIT_LOGS, EXPORT_CONSENT,
)

api_bp = Blueprint("api", __name__, url_prefix="/api/v1")


# ── Helpers ───────────────────────────────────────────────────────────────────

def api_error(msg, code=400):
    return jsonify({"success": False, "error": msg}), code


def api_ok(data=None, msg=None):
    resp = {"success": True}
    if data is not None:
        resp["data"] = data
    if msg:
        resp["message"] = msg
    return jsonify(resp)


def _org_id():
    """Return the effective org_id for this request (key or session)."""
    return getattr(g, "api_org_id", None)


# ── Public ────────────────────────────────────────────────────────────────────

@api_bp.route("/health")
def health():
    return api_ok(msg="CCMP API is running")


# ── Consents ──────────────────────────────────────────────────────────────────

@api_bp.route("/consents", methods=["GET"])
@api_auth_required
@api_scope_required("consents:read", session_permission=VIEW_CONSENT_REGISTRY)
def list_consents():
    org_id  = _org_id()
    status  = request.args.get("status")
    purpose = request.args.get("purpose")
    page    = request.args.get("page", 1, type=int)

    q = Consent.query.filter_by(org_id=org_id)
    if status:
        q = q.filter_by(status=status)
    if purpose:
        q = q.filter_by(purpose=purpose)
    p = q.order_by(Consent.created_at.desc()).paginate(page=page, per_page=50, error_out=False)
    return api_ok({
        "consents": [c.to_dict() for c in p.items],
        "total": p.total, "page": p.page, "pages": p.pages,
    })


@api_bp.route("/consents", methods=["POST"])
@api_auth_required
@api_scope_required("consents:write", session_permission=CREATE_CONSENT)
def create_consent():
    data = request.get_json() or {}
    required = ["name", "email", "purpose", "legal_basis", "channel", "policy_version"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return api_error(f"Missing required fields: {', '.join(missing)}")
    if data["purpose"] not in PURPOSES:
        return api_error(f"Invalid purpose. Valid: {PURPOSES}")
    if data["legal_basis"] not in LEGAL_BASES:
        return api_error(f"Invalid legal_basis. Valid: {LEGAL_BASES}")
    if data["channel"] not in CHANNELS:
        return api_error(f"Invalid channel. Valid: {CHANNELS}")

    org_id = _org_id()
    from flask_login import current_user
    created_by = current_user.id if current_user.is_authenticated else None

    subject = ConsentService.get_or_create_subject(
        name=data["name"], email=data["email"],
        org_id=org_id,
        phone=data.get("phone"), country=data.get("country"),
    )
    consent = ConsentService.create_consent(
        subject=subject, purpose=data["purpose"],
        legal_basis=data["legal_basis"], channel=data["channel"],
        policy_version=data["policy_version"], notes=data.get("notes"),
        org_id=org_id, created_by=created_by,
        source="API", ip_address=request.remote_addr,
    )
    db.session.commit()
    return api_ok(consent.to_dict(), "Consent created"), 201


@api_bp.route("/consents/<int:consent_id>", methods=["GET"])
@api_auth_required
@api_scope_required("consents:read", session_permission=VIEW_CONSENT_REGISTRY)
def get_consent(consent_id):
    c = Consent.query.filter_by(id=consent_id, org_id=_org_id()).first_or_404()
    return api_ok(c.to_dict())


@api_bp.route("/consents/<int:consent_id>/withdraw", methods=["POST"])
@api_auth_required
@api_scope_required("consents:withdraw", session_permission=WITHDRAW_CONSENT)
def withdraw_consent(consent_id):
    c = Consent.query.filter_by(id=consent_id, org_id=_org_id()).first_or_404()
    if c.status == "Withdrawn":
        return api_error("Consent is already withdrawn")
    data  = request.get_json() or {}
    actor = getattr(g, "api_actor", "API")
    ConsentService.withdraw_consent(c, actor,
                                    reason=data.get("reason"), source="API",
                                    ip_address=request.remote_addr)
    db.session.commit()
    return api_ok(c.to_dict(), "Consent withdrawn")


@api_bp.route("/consents/<int:consent_id>/history", methods=["GET"])
@api_auth_required
@api_scope_required("consents:read", session_permission=VIEW_CONSENT_REGISTRY)
def consent_history(consent_id):
    c = Consent.query.filter_by(id=consent_id, org_id=_org_id()).first_or_404()
    history = (ConsentHistory.query
               .filter_by(consent_id=consent_id)
               .order_by(ConsentHistory.timestamp.desc())
               .all())
    return api_ok([h.to_dict() for h in history])


# ── Subjects ──────────────────────────────────────────────────────────────────

@api_bp.route("/subjects/<email>/consents", methods=["GET"])
@api_auth_required
@api_scope_required("subjects:read", session_permission=VIEW_CONSENT_REGISTRY)
def subject_consents(email):
    subject = DataSubject.query.filter_by(
        email=email.lower(), org_id=_org_id()
    ).first_or_404()
    consents = Consent.query.filter_by(subject_id=subject.id).all()
    return api_ok({
        "subject":  subject.to_dict(),
        "consents": [c.to_dict() for c in consents],
    })


# ── Sync ──────────────────────────────────────────────────────────────────────

@api_bp.route("/sync", methods=["POST"])
@api_auth_required
@api_scope_required("sync:write", session_permission=None)  # admin/manager only via RBAC not needed here
def sync():
    # Restrict session callers to manager+ manually (sync is an integration action)
    api_key = getattr(g, "api_key", None)
    if api_key is None:
        from flask_login import current_user
        if not current_user.is_manager:
            return jsonify({"success": False, "error": "Insufficient permissions."}), 403
    data = request.get_json() or {}
    AuditService.log("External Sync Triggered", "Integration",
                     details=str(data.get("source", "Unknown")))
    db.session.commit()
    return api_ok(msg=f"Sync acknowledged from {data.get('source', 'unknown')}")


# ── Caller identity ───────────────────────────────────────────────────────────

@api_bp.route("/me", methods=["GET"])
@api_auth_required
def api_me():
    """Return identity info for the current caller (key or session)."""
    from flask_login import current_user
    if getattr(g, "api_key", None):
        key = g.api_key
        return api_ok({
            "auth_type":  "api_key",
            "key_name":   key.name,
            "key_prefix": key.key_prefix,
            "scopes":     key.scopes,
            "org_id":     key.org_id,
        })
    return api_ok({
        "auth_type":   "session",
        "user_id":     current_user.id,
        "email":       current_user.email,
        "role":        current_user.role,
        "permissions": sorted(current_user.get_permissions()),
        "org_id":      current_user.org_id,
    })
