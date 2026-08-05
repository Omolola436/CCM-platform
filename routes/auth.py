from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User
from forms import LoginForm, RegisterUserForm, ChangePasswordForm, ForgotPasswordForm
from services.audit_service import AuditService
from services.mail_service import send_email
from utils.security import clear_failed_login_attempts, clear_reset_token, create_password_reset_token, get_client_ip, handle_failed_login, is_account_locked, is_rate_limited, is_reset_token_valid, reset_rate_limit
from datetime import datetime, timezone

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
    form = LoginForm()
    forgot_form = ForgotPasswordForm()
    if form.validate_on_submit():
        from app import bcrypt
        if is_rate_limited():
            flash("Too many login attempts. Please wait a few minutes before trying again.", "warning")
            return render_template("auth/login.html", form=form, forgot_form=forgot_form, show_forgot=False)
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if user and not user.is_active:
            flash("This account is disabled.", "danger")
        elif user and is_account_locked(user):
            flash(f"This account is locked until {user.locked_until.strftime('%Y-%m-%d %H:%M')} due to repeated failed sign-in attempts.", "danger")
        elif user and user.role == form.role.data and bcrypt.check_password_hash(user.password_hash, form.password.data):
            if user.role == "admin" and user.mfa_enabled:
                flash("Admin MFA is required before you can continue. Please configure a second factor in your environment.", "warning")
                return render_template("auth/login.html", form=form, forgot_form=forgot_form, show_forgot=False)
            clear_failed_login_attempts(user)
            user.last_login = datetime.now(timezone.utc)
            user.last_login_ip = get_client_ip()
            user.last_login_location = request.headers.get("X-Forwarded-For", request.remote_addr)
            user.password_changed_at = user.password_changed_at or user.created_at
            reset_rate_limit()
            db.session.commit()
            login_user(user, remember=form.remember_me.data)
            AuditService.log("User Login", "Authentication", None,
                             f"{user.email} signed in from {request.remote_addr}", org_id=user.org_id,
                             actor_id=user.id, actor_email=user.email, actor_name=user.full_name,
                             actor_role=user.role, location=request.remote_addr)
            db.session.commit()
            next_page = request.args.get("next")
            return redirect(next_page or url_for("dashboard.index"))
        else:
            if user:
                handle_failed_login(user)
                db.session.commit()
                AuditService.log("Login Failed", "Authentication", None,
                                 f"Failed login for {user.email}", org_id=user.org_id,
                                 actor_id=user.id, actor_email=user.email, actor_name=user.full_name,
                                 actor_role=user.role, location=request.remote_addr)
                db.session.commit()
            flash("Invalid email, role, or password.", "danger")
    return render_template("auth/login.html", form=form, forgot_form=forgot_form, show_forgot=False)


@auth_bp.route("/forgot-password", methods=["POST"])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
    form = ForgotPasswordForm()
    login_form = LoginForm()
    if form.validate_on_submit():
        from app import bcrypt
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if user and user.is_active:
            token = create_password_reset_token(user)
            reset_link = url_for("auth.reset_password", token=token, _external=True)
            send_email(user.email, "CCMP Password Reset", f"Use the following link to reset your password: {reset_link}\n\nThis link expires in 1 hour.")
            db.session.commit()
            AuditService.log("Password Reset Requested", "Authentication", None,
                             f"Password reset requested for {user.email}", org_id=user.org_id,
                             actor_id=user.id, actor_email=user.email, actor_name=user.full_name,
                             actor_role=user.role, location=request.remote_addr)
            db.session.commit()
        flash("If an account exists for that email, a password reset link has been sent.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/login.html", form=login_form, forgot_form=form, show_forgot=True)


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))
    form = ChangePasswordForm()
    user = User.query.filter(User.reset_token == token).first()
    if not user or not user.is_active or not is_reset_token_valid(user, token):
        flash("This password reset link is invalid or has expired.", "danger")
        return redirect(url_for("auth.login"))

    if form.validate_on_submit():
        from app import bcrypt
        user.password_hash = bcrypt.generate_password_hash(form.new_password.data).decode()
        user.password_changed_at = datetime.now(timezone.utc)
        clear_failed_login_attempts(user)
        clear_reset_token(user)
        db.session.commit()
        AuditService.log("Password Reset", "Authentication", None,
                         f"{user.email} reset password via email link", org_id=user.org_id,
                         actor_id=user.id, actor_email=user.email, actor_name=user.full_name,
                         actor_role=user.role, location=request.remote_addr)
        db.session.commit()
        flash("Your password has been updated. Please sign in with your new password.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", form=form, token=token)


@auth_bp.route("/logout")
@login_required
def logout():
    AuditService.log("User Logout", "User", current_user.id,
                     f"{current_user.email} signed out", org_id=current_user.org_id)
    db.session.commit()
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        from app import bcrypt
        if bcrypt.check_password_hash(current_user.password_hash, form.current_password.data):
            current_user.password_hash = bcrypt.generate_password_hash(form.new_password.data).decode()
            current_user.password_changed_at = datetime.now(timezone.utc)
            clear_failed_login_attempts(current_user)
            db.session.commit()
            AuditService.log("Password Changed", "Authentication", None,
                             f"{current_user.email} updated password", org_id=current_user.org_id,
                             actor_id=current_user.id, actor_email=current_user.email, actor_name=current_user.full_name,
                             actor_role=current_user.role, location=request.remote_addr)
            db.session.commit()
            flash("Password updated successfully.", "success")
            return redirect(url_for("auth.profile"))
        flash("Current password is incorrect.", "danger")
    return render_template("auth/profile.html", form=form)
