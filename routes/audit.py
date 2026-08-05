from flask import Blueprint, render_template, request, make_response, send_file, redirect, url_for
from flask_login import login_required, current_user
from models import db, AuditLog, Consent, DataSubject
from services.report_service import ReportService
from utils.decorators import permission_required
from utils.permissions import VIEW_AUDIT_LOGS, EXPORT_AUDIT_LOGS
from sqlalchemy import func
import csv, io
from datetime import datetime, timezone

audit_bp = Blueprint("audit", __name__, url_prefix="/audit")


@audit_bp.route("/")
@login_required
@permission_required(VIEW_AUDIT_LOGS)
def logs():
    q = request.args.get("q", "").strip()
    action_f = request.args.get("action", "")
    entity_f = request.args.get("entity", "")
    page = request.args.get("page", 1, type=int)
    org_id = current_user.org_id

    query = AuditLog.query.filter_by(org_id=org_id)
    if q:
        s = f"%{q}%"
        query = query.filter(db.or_(
            AuditLog.actor_email.ilike(s), AuditLog.details.ilike(s),
            AuditLog.action.ilike(s),
        ))
    if action_f:
        query = query.filter(AuditLog.action == action_f)
    if entity_f:
        query = query.filter(AuditLog.entity_type == entity_f)

    logs_p = query.order_by(AuditLog.created_at.desc()).paginate(page=page, per_page=20, error_out=False)

    actions = [a[0] for a in db.session.query(AuditLog.action).filter_by(org_id=org_id).distinct().order_by(AuditLog.action).all()]
    entities = [e[0] for e in db.session.query(AuditLog.entity_type).filter_by(org_id=org_id).distinct().order_by(AuditLog.entity_type).all()]

    action_counts = (
        db.session.query(AuditLog.action, func.count(AuditLog.id).label("n"))
        .filter_by(org_id=org_id).group_by(AuditLog.action)
        .order_by(func.count(AuditLog.id).desc()).all()
    )
    total_logs = db.session.query(func.count(AuditLog.id)).filter_by(org_id=org_id).scalar() or 0

    return render_template("audit/logs.html",
                           logs=logs_p, actions=actions, entities=entities,
                           action_counts=action_counts, total_logs=total_logs,
                           q=q, action_f=action_f, entity_f=entity_f)


@audit_bp.route("/export/csv")
@login_required
@permission_required(EXPORT_AUDIT_LOGS)
def export_csv():
    org_id = current_user.org_id
    logs = AuditLog.query.filter_by(org_id=org_id).order_by(AuditLog.created_at.desc()).all()
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["ID", "Timestamp", "Action", "Entity Type", "Entity ID",
                "Actor Email", "Actor Name", "Actor Role", "Details", "Location", "IP Address"])
    for log in logs:
        w.writerow([
            log.id,
            log.created_at.strftime("%Y-%m-%d %H:%M:%S UTC") if log.created_at else "",
            log.action, log.entity_type, log.entity_id or "",
            log.actor_email or "", log.actor_name or "", log.actor_role or "",
            log.details or "", log.location or "", log.ip_address or "",
        ])
    fname = f"ccmp_audit_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
    resp = make_response(out.getvalue())
    resp.headers["Content-Disposition"] = f"attachment; filename={fname}"
    resp.headers["Content-Type"] = "text/csv"
    return resp


@audit_bp.route("/report/<report_type>")
@login_required
@permission_required(EXPORT_AUDIT_LOGS)
def report(report_type):
    if report_type not in ("audit", "ndpa", "gdpr"):
        return redirect(url_for("audit.logs"))
    buf = ReportService.generate_audit_report(current_user.org_id, report_type)
    fname = f"ccmp_{report_type}_report_{datetime.now(timezone.utc).strftime('%Y%m%d')}.pdf"
    return send_file(buf, mimetype="application/pdf",
                     as_attachment=True, download_name=fname)
