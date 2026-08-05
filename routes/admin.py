from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from models import db, User, Organization
from forms import RegisterUserForm, EditUserForm, AdminSetPasswordForm
from utils.decorators import admin_required
from services.audit_service import AuditService

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/users")
@login_required
@admin_required
def users():
    all_users = User.query.filter_by(org_id=current_user.org_id).order_by(User.created_at.desc()).all()
    return render_template("admin/users.html", users=all_users)


@admin_bp.route("/users/new", methods=["GET", "POST"])
@login_required
@admin_required
def create_user():
    from app import bcrypt
    form = RegisterUserForm()
    if form.validate_on_submit():
        existing = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if existing:
            flash("A user with that email already exists.", "danger")
        else:
            user = User(
                email=form.email.data.lower().strip(),
                first_name=form.first_name.data,
                last_name=form.last_name.data,
                role="admin",
                org_id=current_user.org_id,
                password_hash=bcrypt.generate_password_hash(form.password.data).decode(),
            )
            db.session.add(user)
            AuditService.log("User Created", "User", details=f"Created user {form.email.data}")
            db.session.commit()
            flash(f"User {user.full_name} created and granted access.", "success")
            return redirect(url_for("admin.users"))
    return render_template("admin/create_user.html", form=form)


@admin_bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_user(user_id):
    user = User.query.filter_by(id=user_id, org_id=current_user.org_id).first_or_404()
    form = EditUserForm(obj=user)
    if form.validate_on_submit():
        existing = User.query.filter(User.email == form.email.data.lower().strip(), User.id != user.id).first()
        if existing:
            flash("That email is already in use.", "danger")
        else:
            user.first_name = form.first_name.data
            user.last_name = form.last_name.data
            user.email = form.email.data.lower().strip()
            AuditService.log("User Updated", "User", user.id, f"Updated profile for {user.email}")
            db.session.commit()
            flash("User updated successfully.", "success")
            return redirect(url_for("admin.users"))
    return render_template("admin/edit_user.html", form=form, user=user)


@admin_bp.route("/users/<int:user_id>/reset-password", methods=["GET", "POST"])
@login_required
@admin_required
def reset_password(user_id):
    from app import bcrypt
    user = User.query.filter_by(id=user_id, org_id=current_user.org_id).first_or_404()
    form = AdminSetPasswordForm()
    if form.validate_on_submit():
        user.password_hash = bcrypt.generate_password_hash(form.new_password.data).decode()
        AuditService.log("Password Reset", "User", user.id, f"Admin reset password for {user.email}")
        db.session.commit()
        flash(f"Password reset for {user.full_name}.", "success")
        return redirect(url_for("admin.users"))
    return render_template("admin/reset_password.html", form=form, user=user)


@admin_bp.route("/users/<int:user_id>/toggle", methods=["POST"])
@login_required
@admin_required
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
@admin_required
def delete_user(user_id):
    user = User.query.filter_by(id=user_id, org_id=current_user.org_id).first_or_404()
    if user.id == current_user.id:
        flash("You cannot delete your own account.", "warning")
        return redirect(url_for("admin.users"))
    name = user.full_name
    email = user.email
    AuditService.log("User Deleted", "User", user.id, f"Deleted user {email}")
    db.session.delete(user)
    db.session.commit()
    flash(f"User {name} has been removed.", "danger")
    return redirect(url_for("admin.users"))
