from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField
from wtforms.validators import DataRequired, Email, Length, EqualTo
from utils.security import PasswordStrength


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    role = SelectField("Role", choices=[('admin', 'Administrator'), ('manager', 'Manager'), ('user', 'Standard User')], validators=[DataRequired()])
    remember_me = BooleanField("Keep me signed in")
    submit = SubmitField("Sign In")


class ForgotPasswordForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    new_password = PasswordField("New Password", validators=[DataRequired(), Length(8, 128), PasswordStrength(min_length=12)])
    confirm_password = PasswordField("Confirm Password", validators=[DataRequired(), EqualTo("new_password")])
    submit = SubmitField("Reset Password")


class RegisterUserForm(FlaskForm):
    first_name = StringField("First Name", validators=[DataRequired(), Length(2, 100)])
    last_name = StringField("Last Name", validators=[DataRequired(), Length(2, 100)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired(), Length(8, 128), PasswordStrength(min_length=12)])
    confirm_password = PasswordField("Confirm Password", validators=[DataRequired(), EqualTo("password")])
    submit = SubmitField("Create User")


class EditUserForm(FlaskForm):
    first_name = StringField("First Name", validators=[DataRequired(), Length(2, 100)])
    last_name = StringField("Last Name", validators=[DataRequired(), Length(2, 100)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    submit = SubmitField("Save Changes")


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField("Current Password", validators=[DataRequired()])
    new_password = PasswordField("New Password", validators=[DataRequired(), Length(8, 128), PasswordStrength(min_length=12)])
    confirm_password = PasswordField("Confirm New Password", validators=[DataRequired(), EqualTo("new_password")])
    submit = SubmitField("Update Password")


class AdminSetPasswordForm(FlaskForm):
    new_password = PasswordField("New Password", validators=[DataRequired(), Length(8, 128), PasswordStrength(min_length=12)])
    confirm_password = PasswordField("Confirm Password", validators=[DataRequired(), EqualTo("new_password")])
    submit = SubmitField("Reset Password")
