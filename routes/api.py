from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from models import db, Consent, DataSubject, ConsentHistory
from models.consent import PURPOSES, LEGAL_BASES, CHANNELS
from services.consent_service import ConsentService
from services.audit_service import AuditService

api_bp = Blueprint("api", __name__, url_prefix="/api/v1")


def api_error(msg, code=400):
    return jsonify({"success": False, "error": msg}), code


def api_ok(data=None, msg=None):
    resp = {"success": True}
    if data is not None:
        resp["data"] = data
    if msg:
        resp["message"] = msg
    return jsonify(resp)


@api_bp.route("/health")
def health():
    return api_ok(msg="CCMP API is running")


@api_bp.route("/consents", methods=["GET"])
@login_required
def list_consents():
    org_id = current_user.org_id
    status = request.args.get("status")
    purpose = request.args.get("purpose")
    page = request.args.get("page", 1, type=int)

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
@login_required
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

    subject = ConsentService.get_or_create_subject(
        name=data["name"], email=data["email"],
        org_id=current_user.org_id,
        phone=data.get("phone"), country=data.get("country"),
    )
    consent = ConsentService.create_consent(
        subject=subject, purpose=data["purpose"],
        legal_basis=data["legal_basis"], channel=data["channel"],
        policy_version=data["policy_version"], notes=data.get("notes"),
        org_id=current_user.org_id, created_by=current_user.id,
        source="API", ip_address=request.remote_addr,
    )
    db.session.commit()
    return api_ok(consent.to_dict(), "Consent created"), 201


@api_bp.route("/consents/<int:consent_id>", methods=["GET"])
@login_required
def get_consent(consent_id):
    c = Consent.query.filter_by(id=consent_id, org_id=current_user.org_id).first_or_404()
    return api_ok(c.to_dict())


@api_bp.route("/consents/<int:consent_id>/withdraw", methods=["POST"])
@login_required
def withdraw_consent(consent_id):
    c = Consent.query.filter_by(id=consent_id, org_id=current_user.org_id).first_or_404()
    if c.status == "Withdrawn":
        return api_error("Consent is already withdrawn")
    data = request.get_json() or {}
    ConsentService.withdraw_consent(c, current_user.full_name,
                                    reason=data.get("reason"), source="API",
                                    ip_address=request.remote_addr)
    db.session.commit()
    return api_ok(c.to_dict(), "Consent withdrawn")


@api_bp.route("/consents/<int:consent_id>/history", methods=["GET"])
@login_required
def consent_history(consent_id):
    c = Consent.query.filter_by(id=consent_id, org_id=current_user.org_id).first_or_404()
    history = ConsentHistory.query.filter_by(consent_id=consent_id).order_by(ConsentHistory.timestamp.desc()).all()
    return api_ok([h.to_dict() for h in history])


@api_bp.route("/subjects/<email>/consents", methods=["GET"])
@login_required
def subject_consents(email):
    subject = DataSubject.query.filter_by(email=email.lower(), org_id=current_user.org_id).first_or_404()
    consents = Consent.query.filter_by(subject_id=subject.id).all()
    return api_ok({
        "subject": subject.to_dict(),
        "consents": [c.to_dict() for c in consents],
    })


@api_bp.route("/sync", methods=["POST"])
@login_required
def sync():
    data = request.get_json() or {}
    AuditService.log("External Sync Triggered", "Integration", details=str(data.get("source", "Unknown")))
    db.session.commit()
    return api_ok(msg=f"Sync acknowledged from {data.get('source', 'unknown')}")
