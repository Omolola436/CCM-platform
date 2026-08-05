from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, DataSubject, Consent, PolicyVersion
from models.consent import PURPOSES
from forms import PreferenceLookupForm
from services.consent_service import ConsentService
from services.audit_service import AuditService

preference_bp = Blueprint("preference", __name__, url_prefix="/preference")


@preference_bp.route("/", methods=["GET", "POST"])
def centre():
    form = PreferenceLookupForm()
    subject = None
    consents = []
    notices = []
    if form.validate_on_submit():
        email = form.email.data.lower().strip()
        subject = DataSubject.query.filter_by(email=email).first()
        if not subject:
            flash("No records found for that email address.", "warning")
        else:
            consents = Consent.query.filter_by(subject_id=subject.id).order_by(Consent.created_at.desc()).all()
            notices = PolicyVersion.query.filter_by(org_id=subject.org_id).order_by(PolicyVersion.created_at.desc()).all()
            AuditService.log("Preference Centre Accessed", "DataSubject", subject.id,
                             f"Self-service lookup for {email}", org_id=subject.org_id,
                             actor_email=email, actor_name=subject.name)
            db.session.commit()
    return render_template("preference/centre.html", form=form, subject=subject,
                           consents=consents, notices=notices, purposes=PURPOSES)


@preference_bp.route("/withdraw/<int:consent_id>", methods=["POST"])
def withdraw(consent_id):
    consent = Consent.query.get_or_404(consent_id)
    email = request.form.get("email", "")
    if consent.status != "Withdrawn":
        ConsentService.withdraw_consent(
            consent, consent.data_subject.name,
            reason="Self-service withdrawal via Preference Centre.",
            source="Preference Centre", ip_address=request.remote_addr,
        )
        AuditService.log("Self-Service Withdrawal", "Consent", consent.id,
                         f"Subject withdrew consent for '{consent.purpose}'",
                         org_id=consent.org_id,
                         actor_email=consent.data_subject.email,
                         actor_name=consent.data_subject.name)
        db.session.commit()
        flash(f"Consent for '{consent.purpose}' has been withdrawn.", "warning")
    return redirect(url_for("preference.centre") + f"?email={email}")


@preference_bp.route("/withdraw-all/<int:subject_id>", methods=["POST"])
def withdraw_all(subject_id):
    subject = DataSubject.query.get_or_404(subject_id)
    active = Consent.query.filter_by(subject_id=subject_id, status="Active").all()
    for c in active:
        ConsentService.withdraw_consent(
            c, subject.name,
            reason="Bulk withdrawal via Preference Centre.",
            source="Preference Centre", ip_address=request.remote_addr,
        )
    if active:
        AuditService.log("Bulk Self-Service Withdrawal", "DataSubject", subject.id,
                         f"All {len(active)} active consents withdrawn by subject",
                         org_id=subject.org_id, actor_email=subject.email, actor_name=subject.name)
    db.session.commit()
    flash(f"All {len(active)} active consents withdrawn.", "warning")
    return redirect(url_for("preference.centre") + f"?email={subject.email}")
