from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, Integration, Webhook
from models.integration import INTEGRATION_TYPES, INTEGRATION_STATUSES
from forms import IntegrationForm, WebhookForm
from utils.decorators import permission_required
from utils.permissions import VIEW_INTEGRATIONS, MANAGE_INTEGRATIONS
from services.audit_service import AuditService

integration_bp = Blueprint("integration", __name__, url_prefix="/integrations")


@integration_bp.route("/")
@login_required
@permission_required(VIEW_INTEGRATIONS)
def index():
    integrations = Integration.query.filter_by(org_id=current_user.org_id).order_by(Integration.created_at.desc()).all()
    webhooks = Webhook.query.filter_by(org_id=current_user.org_id).order_by(Webhook.created_at.desc()).all()
    return render_template("integration/index.html", integrations=integrations, webhooks=webhooks)


@integration_bp.route("/new", methods=["GET", "POST"])
@login_required
@permission_required(MANAGE_INTEGRATIONS)
def new_integration():
    form = IntegrationForm()
    if form.validate_on_submit():
        intg = Integration(
            name=form.name.data, type=form.type.data,
            description=form.description.data, endpoint=form.endpoint.data,
            api_key=form.api_key.data, status="inactive",
            org_id=current_user.org_id, created_by=current_user.id,
        )
        db.session.add(intg)
        AuditService.log("Integration Created", "Integration",
                         details=f"'{form.name.data}' ({form.type.data})")
        db.session.commit()
        flash(f"Integration '{intg.name}' added.", "success")
        return redirect(url_for("integration.index"))
    return render_template("integration/form.html", form=form, title="New Integration")


@integration_bp.route("/<int:intg_id>/toggle", methods=["POST"])
@login_required
@permission_required(MANAGE_INTEGRATIONS)
def toggle_integration(intg_id):
    intg = Integration.query.filter_by(id=intg_id, org_id=current_user.org_id).first_or_404()
    intg.status = "inactive" if intg.status == "active" else "active"
    AuditService.log("Integration Status Changed", "Integration", intg_id,
                     f"'{intg.name}' set to {intg.status}")
    db.session.commit()
    flash(f"Integration set to {intg.status}.", "success")
    return redirect(url_for("integration.index"))


@integration_bp.route("/<int:intg_id>/delete", methods=["POST"])
@login_required
@permission_required(MANAGE_INTEGRATIONS)
def delete_integration(intg_id):
    intg = Integration.query.filter_by(id=intg_id, org_id=current_user.org_id).first_or_404()
    db.session.delete(intg)
    AuditService.log("Integration Deleted", "Integration", intg_id,
                     f"Deleted '{intg.name}'")
    db.session.commit()
    flash("Integration removed.", "danger")
    return redirect(url_for("integration.index"))


@integration_bp.route("/webhooks/new", methods=["GET", "POST"])
@login_required
@permission_required(MANAGE_INTEGRATIONS)
def new_webhook():
    form = WebhookForm()
    if form.validate_on_submit():
        wh = Webhook(
            name=form.name.data, url=form.url.data,
            events=form.events.data, secret=form.secret.data,
            status="active", org_id=current_user.org_id, created_by=current_user.id,
        )
        db.session.add(wh)
        AuditService.log("Webhook Created", "Webhook",
                         details=f"'{form.name.data}' → {form.url.data}")
        db.session.commit()
        flash(f"Webhook '{wh.name}' created.", "success")
        return redirect(url_for("integration.index"))
    return render_template("integration/webhook_form.html", form=form)


@integration_bp.route("/webhooks/<int:wh_id>/delete", methods=["POST"])
@login_required
@permission_required(MANAGE_INTEGRATIONS)
def delete_webhook(wh_id):
    wh = Webhook.query.filter_by(id=wh_id, org_id=current_user.org_id).first_or_404()
    db.session.delete(wh)
    AuditService.log("Webhook Deleted", "Webhook", wh_id,
                     f"Deleted '{wh.name}'")
    db.session.commit()
    flash("Webhook removed.", "danger")
    return redirect(url_for("integration.index"))
