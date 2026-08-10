import os
import re
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from models import db, Consent, DataSubject, ConsentHistory, PolicyVersion, PolicySource
from models.consent import PURPOSES, LEGAL_BASES, CHANNELS, STATUSES
from forms import ConsentForm, PolicyVersionForm, PolicySourceForm
from services.consent_service import ConsentService
from services.audit_service import AuditService
from utils.decorators import permission_required
from utils.permissions import (
    VIEW_CONSENT_REGISTRY, CREATE_CONSENT, WITHDRAW_CONSENT,
    REACTIVATE_CONSENT, EXPORT_CONSENT, DELETE_CONSENT,
    VIEW_POLICIES, CREATE_POLICY, APPROVE_POLICY,
)
from datetime import datetime, timezone
from sqlalchemy import func

consent_bp = Blueprint("consent", __name__, url_prefix="/consent")

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
ALLOWED_EXTENSIONS = {"pdf", "txt", "png", "jpg", "jpeg"}


def _allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@consent_bp.route("/")
@login_required
@permission_required(VIEW_CONSENT_REGISTRY)
def registry():
    q = request.args.get("q", "").strip()
    status_f = request.args.get("status", "")
    purpose_f = request.args.get("purpose", "")
    channel_f = request.args.get("channel", "")
    page = request.args.get("page", 1, type=int)
    org_id = current_user.org_id

    query = db.session.query(Consent).join(DataSubject).filter(Consent.org_id == org_id)
    # Exclude tombstoned records from default view
    query = query.filter(Consent.status != "Deleted")
    if q:
        s = f"%{q}%"
        query = query.filter(db.or_(
            DataSubject.name.ilike(s), DataSubject.email.ilike(s),
            Consent.purpose.ilike(s),
        ))
    if status_f:
        query = query.filter(Consent.status == status_f)
    if purpose_f:
        query = query.filter(Consent.purpose == purpose_f)
    if channel_f:
        query = query.filter(Consent.channel == channel_f)

    consents = query.order_by(Consent.created_at.desc()).paginate(page=page, per_page=15, error_out=False)
    return render_template(
        "consent/registry.html",
        consents=consents, purposes=PURPOSES, legal_bases=LEGAL_BASES,
        channels=CHANNELS, statuses=STATUSES,
        q=q, status_f=status_f, purpose_f=purpose_f, channel_f=channel_f,
    )


@consent_bp.route("/add", methods=["GET", "POST"])
@login_required
@permission_required(CREATE_CONSENT)
def add():
    form = ConsentForm()
    notices = PolicyVersion.query.filter_by(org_id=current_user.org_id).order_by(PolicyVersion.created_at.desc()).all()
    form.policy_version.choices = [(n.version, f"{n.version} — {n.title}") for n in notices] or [("v1.0", "v1.0")]
    if form.validate_on_submit():
        subject = ConsentService.get_or_create_subject(
            name=form.name.data, email=form.email.data,
            org_id=current_user.org_id, phone=form.phone.data, country=form.country.data,
        )
        pv = PolicyVersion.query.filter_by(version=form.policy_version.data, org_id=current_user.org_id).first()

        doc_filename = request.form.get("doc_filename") or None

        consent = ConsentService.create_consent(
            subject=subject, purpose=form.purpose.data, legal_basis=form.legal_basis.data,
            channel=form.channel.data, policy_version=form.policy_version.data,
            notes=form.notes.data, org_id=current_user.org_id,
            created_by=current_user.id, policy_version_id=pv.id if pv else None,
            ip_address=request.remote_addr,
        )
        if doc_filename:
            consent.source_document = doc_filename
        db.session.commit()
        flash("Consent record created successfully.", "success")
        return redirect(url_for("consent.detail", consent_id=consent.id))
    return render_template("consent/add.html", form=form, notices=notices,
                           purposes=PURPOSES, channels=CHANNELS)


@consent_bp.route("/scan-document", methods=["POST"])
@login_required
@permission_required(CREATE_CONSENT)
def scan_document():
    if "document" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["document"]
    if not file.filename or not _allowed_file(file.filename):
        return jsonify({"error": "Unsupported file type. Upload PDF, TXT, JPG or PNG."}), 400

    ext = file.filename.rsplit(".", 1)[1].lower()
    safe_name = f"{uuid.uuid4().hex}.{ext}"
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    save_path = os.path.join(UPLOAD_FOLDER, safe_name)
    file.save(save_path)

    text = ""
    try:
        if ext == "pdf":
            from pdfminer.high_level import extract_text
            text = extract_text(save_path)
        elif ext == "txt":
            with open(save_path, "r", errors="ignore") as f:
                text = f.read()
        else:
            return jsonify({
                "filename": safe_name,
                "extracted": {},
                "raw_text": "",
                "message": "Image saved. Please fill in the form fields manually.",
            })
    except Exception as e:
        return jsonify({"error": f"Could not read document: {str(e)}"}), 500

    extracted = _parse_consent_fields(text)
    extracted["channel"] = "Physical Form"
    return jsonify({
        "filename": safe_name,
        "extracted": extracted,
        "raw_text": text[:2000],
    })


def _parse_consent_fields(text):
    result = {}
    text_clean = " ".join(text.split())

    email_match = re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text_clean)
    if email_match:
        result["email"] = email_match.group(0)

    phone_match = re.search(r"(?:\+?\d[\d\s\-().]{7,20}\d)", text_clean)
    if phone_match:
        result["phone"] = phone_match.group(0).strip()

    name_match = re.search(
        r"(?:full\s*name|name|applicant|subject|data\s*subject)[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
        text_clean, re.IGNORECASE
    )
    if name_match:
        result["name"] = name_match.group(1).strip()

    country_match = re.search(r"(?:country|nationality|location)[:\s]+([A-Za-z ]+?)(?:[,\n]|$)", text_clean, re.IGNORECASE)
    if country_match:
        result["country"] = country_match.group(1).strip()

    text_lower = text_clean.lower()
    purpose_keywords = {
        "Marketing": ["marketing", "promotional", "advertisement", "newsletter", "campaign"],
        "Analytics & Research": ["analytics", "research", "analysis", "statistics", "survey"],
        "Service Delivery": ["service", "delivery", "fulfil", "contract", "agreement"],
        "HR & Employment": ["hr", "employment", "payroll", "employee", "recruitment"],
        "Legal & Compliance": ["legal", "compliance", "regulatory", "audit", "obligation"],
        "Customer Support": ["support", "customer", "helpdesk", "service desk"],
        "Financial Processing": ["financial", "payment", "billing", "invoice", "transaction"],
    }
    for purpose, keywords in purpose_keywords.items():
        if any(kw in text_lower for kw in keywords):
            result["purpose"] = purpose
            break

    channel_keywords = {
        "Web Form": ["web form", "website", "online form", "web portal"],
        "Email": ["email", "e-mail"],
        "Paper Form": ["paper", "physical form", "printed", "hand-signed", "wet signature"],
        "Mobile App": ["mobile app", "app", "android", "ios"],
        "In-Person": ["in-person", "in person", "face to face", "verbal"],
        "API": ["api", "integration", "system"],
    }
    for channel, keywords in channel_keywords.items():
        if any(kw in text_lower for kw in keywords):
            result["channel"] = channel
            break

    return result


@consent_bp.route("/report")
@login_required
@permission_required(VIEW_CONSENT_REGISTRY)
def report():
    org_id = current_user.org_id
    from datetime import timedelta

    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")

    query = Consent.query.filter_by(org_id=org_id).filter(Consent.status != "Deleted")
    if date_from:
        try:
            query = query.filter(Consent.created_at >= datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=timezone.utc))
        except ValueError:
            pass
    if date_to:
        try:
            query = query.filter(Consent.created_at <= datetime.strptime(date_to, "%Y-%m-%d").replace(tzinfo=timezone.utc))
        except ValueError:
            pass

    all_consents = query.order_by(Consent.created_at.desc()).all()

    total = len(all_consents)
    active = sum(1 for c in all_consents if c.status == "Active")
    withdrawn = sum(1 for c in all_consents if c.status == "Withdrawn")
    expired = sum(1 for c in all_consents if c.status == "Expired")

    by_purpose = {}
    by_channel = {}
    by_legal_basis = {}
    for c in all_consents:
        by_purpose[c.purpose] = by_purpose.get(c.purpose, 0) + 1
        by_channel[c.channel] = by_channel.get(c.channel, 0) + 1
        by_legal_basis[c.legal_basis] = by_legal_basis.get(c.legal_basis, 0) + 1

    by_purpose = sorted(by_purpose.items(), key=lambda x: x[1], reverse=True)
    by_channel = sorted(by_channel.items(), key=lambda x: x[1], reverse=True)
    by_legal_basis = sorted(by_legal_basis.items(), key=lambda x: x[1], reverse=True)

    history_q = db.session.query(ConsentHistory).join(Consent).filter(
        Consent.org_id == org_id
    ).order_by(ConsentHistory.timestamp.desc()).limit(200).all()

    return render_template(
        "consent/report.html",
        all_consents=all_consents,
        total=total, active=active, withdrawn=withdrawn, expired=expired,
        by_purpose=by_purpose, by_channel=by_channel, by_legal_basis=by_legal_basis,
        history=history_q,
        date_from=date_from, date_to=date_to,
    )


@consent_bp.route("/export-csv")
@login_required
@permission_required(EXPORT_CONSENT)
def export_csv():
    import csv
    import io
    from flask import Response
    org_id = current_user.org_id
    consents = (Consent.query.filter_by(org_id=org_id)
                .filter(Consent.status != "Deleted")
                .order_by(Consent.created_at.desc()).all())
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Data Subject", "Email", "Phone", "Country",
                     "Purpose", "Legal Basis", "Channel", "Status",
                     "Policy Version", "Notes", "Created At", "Updated At"])
    for c in consents:
        writer.writerow([
            c.id,
            c.data_subject.name if c.data_subject else "",
            c.data_subject.email if c.data_subject else "",
            c.data_subject.phone if c.data_subject else "",
            c.data_subject.country if c.data_subject else "",
            c.purpose, c.legal_basis, c.channel, c.status, c.policy_version,
            c.notes or "",
            c.created_at.strftime("%Y-%m-%d %H:%M:%S") if c.created_at else "",
            c.updated_at.strftime("%Y-%m-%d %H:%M:%S") if c.updated_at else "",
        ])
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=consent_report.csv"},
    )


@consent_bp.route("/<int:consent_id>")
@login_required
@permission_required(VIEW_CONSENT_REGISTRY)
def detail(consent_id):
    c = Consent.query.filter_by(id=consent_id, org_id=current_user.org_id).first_or_404()
    history = ConsentHistory.query.filter_by(consent_id=consent_id).order_by(ConsentHistory.timestamp.desc()).all()
    integrity_ok = ConsentService.verify_fingerprint(c)
    return render_template("consent/detail.html", consent=c, history=history,
                           integrity_ok=integrity_ok)


@consent_bp.route("/<int:consent_id>/edit", methods=["GET", "POST"])
@login_required
@permission_required(CREATE_CONSENT)
def edit(consent_id):
    """
    Only non-fingerprinted fields (notes, expires_at) may be edited.
    Immutable fields (purpose, legal_basis, channel, policy_version) are
    displayed read-only; changing them requires creating a new consent.
    """
    c = Consent.query.filter_by(id=consent_id, org_id=current_user.org_id).first_or_404()
    if c.status == "Deleted":
        flash("Cannot edit a deleted consent record.", "danger")
        return redirect(url_for("consent.registry"))

    if request.method == "POST":
        notes = request.form.get("notes", "").strip()
        expires_at_raw = request.form.get("expires_at", "").strip()

        c.notes = notes or None
        if expires_at_raw:
            try:
                c.expires_at = datetime.strptime(expires_at_raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                flash("Invalid expiry date format.", "danger")
                return redirect(url_for("consent.edit", consent_id=consent_id))
        else:
            c.expires_at = None

        c.updated_at = datetime.now(timezone.utc)
        AuditService.log("Consent Notes Updated", "Consent", c.id,
                         f"Notes/expiry updated for consent #{c.id}",
                         org_id=current_user.org_id)
        db.session.commit()
        flash("Consent notes updated.", "success")
        return redirect(url_for("consent.detail", consent_id=c.id))

    return render_template("consent/edit.html", consent=c)


@consent_bp.route("/<int:consent_id>/withdraw", methods=["POST"])
@login_required
@permission_required(WITHDRAW_CONSENT)
def withdraw(consent_id):
    c = Consent.query.filter_by(id=consent_id, org_id=current_user.org_id).first_or_404()
    reason = request.form.get("reason", "").strip()
    if c.status not in ("Withdrawn", "Deleted"):
        ConsentService.withdraw_consent(c, current_user.full_name, reason, ip_address=request.remote_addr)
        db.session.commit()
        flash("Consent withdrawn.", "warning")
    return redirect(url_for("consent.detail", consent_id=consent_id))


@consent_bp.route("/<int:consent_id>/reactivate", methods=["POST"])
@login_required
@permission_required(REACTIVATE_CONSENT)
def reactivate(consent_id):
    c = Consent.query.filter_by(id=consent_id, org_id=current_user.org_id).first_or_404()
    if c.status not in ("Active", "Deleted"):
        ConsentService.reactivate_consent(c, current_user.full_name, ip_address=request.remote_addr)
        db.session.commit()
        flash("Consent reactivated.", "success")
    return redirect(url_for("consent.detail", consent_id=consent_id))


@consent_bp.route("/<int:consent_id>/delete", methods=["POST"])
@login_required
@permission_required(DELETE_CONSENT)
def delete(consent_id):
    """
    Tombstone deletion — marks the record as 'Deleted' with a history entry
    and an audit log. The record and its complete ConsentHistory are preserved
    for auditability. Hard-delete is intentionally prohibited.
    """
    c = Consent.query.filter_by(id=consent_id, org_id=current_user.org_id).first_or_404()
    if c.status == "Deleted":
        flash("Consent is already deleted.", "warning")
        return redirect(url_for("consent.registry"))

    reason = request.form.get("reason", "").strip() or "Consent record deleted by administrator."
    old_status = c.status

    # Create immutable history entry before mutating
    ConsentService._record_history(
        consent_id=c.id,
        old_status=old_status,
        new_status="Deleted",
        changed_by=current_user.full_name,
        reason=reason,
        source="Web UI",
        ip_address=request.remote_addr,
    )
    c.status = "Deleted"
    c.updated_at = datetime.now(timezone.utc)

    AuditService.log("Consent Deleted", "Consent", c.id,
                     f"Tombstoned consent #{c.id} for '{c.purpose}' — {reason}",
                     org_id=current_user.org_id)
    db.session.commit()
    flash("Consent record deleted. The record is retained for audit purposes.", "danger")
    return redirect(url_for("consent.registry"))


@consent_bp.route("/policies")
@login_required
@permission_required(VIEW_POLICIES)
def policies():
    pvs = PolicyVersion.query.filter_by(org_id=current_user.org_id).order_by(PolicyVersion.created_at.desc()).all()
    return render_template("consent/policies.html", policies=pvs)


@consent_bp.route("/policies/new", methods=["GET", "POST"])
@login_required
@permission_required(CREATE_POLICY)
def add_policy():
    form = PolicyVersionForm()
    if form.validate_on_submit():
        if form.is_current.data == "1":
            PolicyVersion.query.filter_by(org_id=current_user.org_id).update({"is_current": False})
        pv = PolicyVersion(
            version=form.version.data,
            title=form.title.data,
            summary=form.summary.data,
            content=form.content.data,
            is_current=(form.is_current.data == "1"),
            org_id=current_user.org_id,
            created_by=current_user.id,
        )
        db.session.add(pv)
        AuditService.log("Policy Version Created", "PolicyVersion",
                         details=f"Version: {form.version.data}")
        db.session.commit()
        flash(f"Policy version {pv.version} created.", "success")
        return redirect(url_for("consent.policies"))
    return render_template("consent/add_policy.html", form=form)


@consent_bp.route("/policies/sources/new", methods=["GET", "POST"])
@login_required
@permission_required(CREATE_POLICY)
def new_policy_source():
    form = PolicySourceForm()
    if form.validate_on_submit():
        source = PolicySource(
            name=form.name.data,
            url=form.url.data,
            check_interval_min=form.check_interval_min.data,
            auto_set_current=form.auto_set_current.data,
            org_id=current_user.org_id,
            created_by=current_user.id,
        )
        db.session.add(source)
        db.session.commit()

        # Prime the source immediately so the first version is available without
        # waiting for the background loop.
        from services.policy_sync_service import PolicySyncService
        result = PolicySyncService.sync_source(source)
        if result.get("changed"):
            flash(f"Policy source added and version {result['version']} was created.", "success")
        elif result.get("error"):
            flash(f"Policy source added, but the first check failed: {result['error']}", "warning")
        else:
            flash("Policy source added. No policy change was detected.", "success")
        return redirect(url_for("consent.policies"))
    return render_template("consent/policy_source_form.html", form=form)


@consent_bp.route("/policies/sources/<int:source_id>/sync", methods=["POST"])
@login_required
@permission_required(CREATE_POLICY)
def sync_policy_source(source_id):
    source = PolicySource.query.filter_by(
        id=source_id, org_id=current_user.org_id
    ).first_or_404()
    from services.policy_sync_service import PolicySyncService
    result = PolicySyncService.sync_source(source)
    if result.get("changed"):
        flash(f"New policy version {result['version']} created automatically.", "success")
    elif result.get("error"):
        flash(f"Policy check failed: {result['error']}", "danger")
    else:
        flash("No policy change detected.", "info")
    return redirect(url_for("consent.policies"))


@consent_bp.route("/policies/sources/<int:source_id>/toggle", methods=["POST"])
@login_required
@permission_required(CREATE_POLICY)
def toggle_policy_source(source_id):
    source = PolicySource.query.filter_by(
        id=source_id, org_id=current_user.org_id
    ).first_or_404()
    source.is_active = not source.is_active
    db.session.commit()
    flash(
        f"Automatic checks {'enabled' if source.is_active else 'paused'} for '{source.name}'.",
        "success",
    )
    return redirect(url_for("consent.policies"))
