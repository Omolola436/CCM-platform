from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from models import db, User, Organization, APIKey
from models.api_key import API_KEY_SCOPES
from forms import RegisterUserForm, EditUserForm, AdminSetPasswordForm
from utils.decorators import admin_required, permission_required
from utils.permissions import VALID_ROLES, MANAGE_API_KEYS, CREATE_USER, EDIT_USER, DELETE_USER, VIEW_USERS
from services.audit_service import AuditService

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


# ── Users ─────────────────────────────────────────────────────────────────────

@admin_bp.route("/users")
@login_required
@permission_required(VIEW_USERS)
def users():
    all_users = User.query.filter_by(org_id=current_user.org_id).order_by(User.created_at.desc()).all()
    return render_template("admin/users.html", users=all_users, valid_roles=sorted(VALID_ROLES))


@admin_bp.route("/users/new", methods=["GET", "POST"])
@login_required
@permission_required(CREATE_USER)
def create_user():
    from app import bcrypt
    form = RegisterUserForm()
    if form.validate_on_submit():
        existing = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if existing:
            flash("A user with that email already exists.", "danger")
        else:
            role = request.form.get("role", "user")
            if role not in VALID_ROLES:
                role = "user"
            user = User(
                email=form.email.data.lower().strip(),
                first_name=form.first_name.data,
                last_name=form.last_name.data,
                role=role,
                org_id=current_user.org_id,
                password_hash=bcrypt.generate_password_hash(form.password.data).decode(),
            )
            db.session.add(user)
            AuditService.log("User Created", "User",
                             details=f"Created user {form.email.data} with role '{role}'")
            db.session.commit()
            flash(f"User {user.full_name} created with role '{role}'.", "success")
            return redirect(url_for("admin.users"))
    return render_template("admin/create_user.html", form=form, valid_roles=sorted(VALID_ROLES))


@admin_bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@permission_required(EDIT_USER)
def edit_user(user_id):
    user = User.query.filter_by(id=user_id, org_id=current_user.org_id).first_or_404()
    form = EditUserForm(obj=user)
    if form.validate_on_submit():
        existing = User.query.filter(User.email == form.email.data.lower().strip(),
                                     User.id != user.id).first()
        if existing:
            flash("That email is already in use.", "danger")
        else:
            new_role = request.form.get("role", user.role)
            if new_role not in VALID_ROLES:
                new_role = user.role
            user.first_name = form.first_name.data
            user.last_name  = form.last_name.data
            user.email      = form.email.data.lower().strip()
            old_role        = user.role
            user.role       = new_role
            AuditService.log("User Updated", "User", user.id,
                             f"Updated {user.email}; role: {old_role} → {new_role}")
            db.session.commit()
            flash("User updated successfully.", "success")
            return redirect(url_for("admin.users"))
    return render_template("admin/edit_user.html", form=form, user=user,
                           valid_roles=sorted(VALID_ROLES))


@admin_bp.route("/users/<int:user_id>/reset-password", methods=["GET", "POST"])
@login_required
@admin_required
def reset_password(user_id):
    from app import bcrypt
    user = User.query.filter_by(id=user_id, org_id=current_user.org_id).first_or_404()
    form = AdminSetPasswordForm()
    if form.validate_on_submit():
        user.password_hash = bcrypt.generate_password_hash(form.new_password.data).decode()
        AuditService.log("Password Reset", "User", user.id,
                         f"Admin reset password for {user.email}")
        db.session.commit()
        flash(f"Password reset for {user.full_name}.", "success")
        return redirect(url_for("admin.users"))
    return render_template("admin/reset_password.html", form=form, user=user)


@admin_bp.route("/users/<int:user_id>/toggle", methods=["POST"])
@login_required
@permission_required(EDIT_USER)
def toggle_user(user_id):
    user = User.query.filter_by(id=user_id, org_id=current_user.org_id).first_or_404()
    if user.id == current_user.id:
        flash("You cannot deactivate your own account.", "warning")
    else:
        user.is_active = not user.is_active
        AuditService.log("User Status Changed", "User", user.id,
                         f"{'Activated' if user.is_active else 'Deactivated'} {user.email}")
        db.session.commit()
        flash(f"User {'activated' if user.is_active else 'deactivated'}.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
@permission_required(DELETE_USER)
def delete_user(user_id):
    user = User.query.filter_by(id=user_id, org_id=current_user.org_id).first_or_404()
    if user.id == current_user.id:
        flash("You cannot delete your own account.", "warning")
        return redirect(url_for("admin.users"))
    name  = user.full_name
    email = user.email
    AuditService.log("User Deleted", "User", user.id, f"Deleted user {email}")
    db.session.delete(user)
    db.session.commit()
    flash(f"User {name} has been removed.", "danger")
    return redirect(url_for("admin.users"))


# ── API Key management ────────────────────────────────────────────────────────

@admin_bp.route("/api-keys")
@login_required
@permission_required(MANAGE_API_KEYS)
def api_keys():
    keys = (APIKey.query
            .filter_by(org_id=current_user.org_id)
            .order_by(APIKey.created_at.desc())
            .all())
    return render_template("admin/api_keys.html", keys=keys, scopes=API_KEY_SCOPES)


@admin_bp.route("/api-keys/new", methods=["POST"])
@login_required
@permission_required(MANAGE_API_KEYS)
def create_api_key():
    name    = request.form.get("name", "").strip()
    scopes  = request.form.getlist("scopes")
    expires = request.form.get("expires_at") or None

    if not name:
        flash("Key name is required.", "danger")
        return redirect(url_for("admin.api_keys"))

    # Validate scopes
    valid_scopes = [s for s in scopes if s in API_KEY_SCOPES]
    if not valid_scopes:
        flash("Select at least one scope.", "danger")
        return redirect(url_for("admin.api_keys"))

    raw = APIKey.generate()

    expires_dt = None
    if expires:
        from datetime import datetime, timezone
        try:
            expires_dt = datetime.fromisoformat(expires).replace(tzinfo=timezone.utc)
        except ValueError:
            flash("Invalid expiry date.", "danger")
            return redirect(url_for("admin.api_keys"))

    key = APIKey(
        name=name,
        key_hash=APIKey.hash_key(raw),
        key_prefix=raw[:12],
        scopes=valid_scopes,
        org_id=current_user.org_id,
        created_by=current_user.id,
        expires_at=expires_dt,
    )
    db.session.add(key)
    AuditService.log("API Key Created", "APIKey", details=f"Key '{name}' with scopes {valid_scopes}")
    db.session.commit()

    # Flash only the raw key value — the template shows explanatory text separately
    flash(raw, "api_key_reveal")
    return redirect(url_for("admin.api_keys"))


@admin_bp.route("/api-keys/<int:key_id>/revoke", methods=["POST"])
@login_required
@permission_required(MANAGE_API_KEYS)
def revoke_api_key(key_id):
    key = APIKey.query.filter_by(id=key_id, org_id=current_user.org_id).first_or_404()
    key.is_active = False
    AuditService.log("API Key Revoked", "APIKey", key_id, f"Revoked key '{key.name}'")
    db.session.commit()
    flash(f"API key '{key.name}' has been revoked.", "warning")
    return redirect(url_for("admin.api_keys"))


@admin_bp.route("/api-keys/<int:key_id>/delete", methods=["POST"])
@login_required
@permission_required(MANAGE_API_KEYS)
def delete_api_key(key_id):
    key = APIKey.query.filter_by(id=key_id, org_id=current_user.org_id).first_or_404()
    name = key.name
    AuditService.log("API Key Deleted", "APIKey", key_id, f"Deleted key '{name}'")
    db.session.delete(key)
    db.session.commit()
    flash(f"API key '{name}' deleted.", "danger")
    return redirect(url_for("admin.api_keys"))
