from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user
from models import db, Consent, DataSubject, AuditLog, ConsentHistory
from sqlalchemy import func, extract
from datetime import datetime, timezone, timedelta

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@login_required
def index():
    org_id = current_user.org_id
    now = datetime.now(timezone.utc)

    # Core metrics
    total = db.session.query(func.count(Consent.id)).filter_by(org_id=org_id).scalar() or 0
    active = db.session.query(func.count(Consent.id)).filter_by(org_id=org_id, status="Active").scalar() or 0
    withdrawn = db.session.query(func.count(Consent.id)).filter_by(org_id=org_id, status="Withdrawn").scalar() or 0
    expired = db.session.query(func.count(Consent.id)).filter_by(org_id=org_id, status="Expired").scalar() or 0
    subjects = db.session.query(func.count(DataSubject.id)).filter_by(org_id=org_id).scalar() or 0
    compliance_rate = round(active / total * 100, 1) if total else 0

    # Month-over-month comparison
    first_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month_end = first_of_month - timedelta(seconds=1)
    total_last_month = db.session.query(func.count(Consent.id)).filter(
        Consent.org_id == org_id,
        Consent.created_at <= last_month_end,
    ).scalar() or 0
    active_last_month = db.session.query(func.count(Consent.id)).filter(
        Consent.org_id == org_id,
        Consent.status == "Active",
        Consent.created_at <= last_month_end,
    ).scalar() or 0
    compliance_last_month = round(active_last_month / total_last_month * 100, 1) if total_last_month else 0
    compliance_change = round(compliance_rate - compliance_last_month, 1)
    total_change = total - total_last_month
    active_change = active - active_last_month

    # Expiring consents (using expires_at field)
    expiring_7 = db.session.query(func.count(Consent.id)).filter(
        Consent.org_id == org_id,
        Consent.status == "Active",
        Consent.expires_at.isnot(None),
        Consent.expires_at <= now + timedelta(days=7),
        Consent.expires_at >= now,
    ).scalar() or 0

    expiring_30 = db.session.query(func.count(Consent.id)).filter(
        Consent.org_id == org_id,
        Consent.status == "Active",
        Consent.expires_at.isnot(None),
        Consent.expires_at <= now + timedelta(days=30),
        Consent.expires_at >= now,
    ).scalar() or 0

    # Compliance alerts (ordered: danger first, then warning)
    alerts = []
    if expired > 0:
        alerts.append({
            "level": "danger",
            "icon": "x-circle-fill",
            "msg": f"{expired} consent record{'s' if expired != 1 else ''} {'have' if expired != 1 else 'has'} expired — immediate review required",
            "action_url": "/consent/?status=Expired",
            "action_label": "Review Now",
        })
    if compliance_rate < 80 and total > 0:
        alerts.append({
            "level": "danger",
            "icon": "shield-x",
            "msg": f"Compliance rate is {compliance_rate}% — below the 80% organisational threshold",
            "action_url": "/consent/report",
            "action_label": "View Report",
        })
    if withdrawn > 0:
        alerts.append({
            "level": "warning",
            "icon": "exclamation-triangle-fill",
            "msg": f"{withdrawn} withdrawal request{'s' if withdrawn != 1 else ''} {'are' if withdrawn != 1 else 'is'} pending — verify connected systems have been updated",
            "action_url": "/consent/?status=Withdrawn",
            "action_label": "Review",
        })
    if expiring_7 > 0:
        alerts.append({
            "level": "warning",
            "icon": "clock-fill",
            "msg": f"{expiring_7} active consent{'s' if expiring_7 != 1 else ''} expire{'s' if expiring_7 == 1 else ''} within 7 days — proactive renewal recommended",
            "action_url": "/consent/",
            "action_label": "View",
        })

    # Purpose and channel distribution
    purpose_stats = (
        db.session.query(Consent.purpose, func.count(Consent.id).label("n"))
        .filter_by(org_id=org_id, status="Active")
        .group_by(Consent.purpose)
        .order_by(func.count(Consent.id).desc())
        .limit(8)
        .all()
    )
    channel_stats = (
        db.session.query(Consent.channel, func.count(Consent.id).label("n"))
        .filter_by(org_id=org_id)
        .group_by(Consent.channel)
        .order_by(func.count(Consent.id).desc())
        .all()
    )

    # 6-month trend data
    months, granted_trend, withdrawn_trend = [], [], []
    for i in range(5, -1, -1):
        target = now - timedelta(days=30 * i)
        m = target.month
        y = target.year
        months.append(target.strftime("%b %Y"))
        g = db.session.query(func.count(ConsentHistory.id)).filter(
            ConsentHistory.new_status == "Active",
            extract("month", ConsentHistory.timestamp) == m,
            extract("year", ConsentHistory.timestamp) == y,
        ).scalar() or 0
        w = db.session.query(func.count(ConsentHistory.id)).filter(
            ConsentHistory.new_status == "Withdrawn",
            extract("month", ConsentHistory.timestamp) == m,
            extract("year", ConsentHistory.timestamp) == y,
        ).scalar() or 0
        granted_trend.append(g)
        withdrawn_trend.append(w)

    # Recent data for widgets
    recent_activity = (
        db.session.query(AuditLog)
        .filter_by(org_id=org_id)
        .order_by(AuditLog.created_at.desc())
        .limit(10)
        .all()
    )
    recent_consents = (
        db.session.query(Consent)
        .filter_by(org_id=org_id)
        .order_by(Consent.created_at.desc())
        .limit(6)
        .all()
    )

    total_audit_events = db.session.query(func.count(AuditLog.id)).filter_by(org_id=org_id).scalar() or 0

    # Compliance posture text for executive summary
    if compliance_rate >= 95:
        posture = "excellent"
    elif compliance_rate >= 80:
        posture = "good"
    elif compliance_rate >= 60:
        posture = "moderate"
    else:
        posture = "poor"

    return render_template(
        "dashboard/index.html",
        total=total, active=active, withdrawn=withdrawn, expired=expired,
        subjects=subjects, compliance_rate=compliance_rate, posture=posture,
        compliance_change=compliance_change, compliance_last_month=compliance_last_month,
        total_change=total_change, active_change=active_change,
        expiring_7=expiring_7, expiring_30=expiring_30,
        alerts=alerts,
        purpose_stats=purpose_stats, channel_stats=channel_stats,
        months=months, granted_trend=granted_trend, withdrawn_trend=withdrawn_trend,
        recent_activity=recent_activity, recent_consents=recent_consents,
        total_audit_events=total_audit_events,
        today=now,
    )


@dashboard_bp.route("/api/dashboard-data")
@login_required
def dashboard_data():
    org_id = current_user.org_id
    active = db.session.query(func.count(Consent.id)).filter_by(org_id=org_id, status="Active").scalar() or 0
    withdrawn = db.session.query(func.count(Consent.id)).filter_by(org_id=org_id, status="Withdrawn").scalar() or 0
    expired = db.session.query(func.count(Consent.id)).filter_by(org_id=org_id, status="Expired").scalar() or 0
    return jsonify({"active": active, "withdrawn": withdrawn, "expired": expired})
