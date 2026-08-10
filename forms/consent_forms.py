from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField, SubmitField, DateTimeLocalField, IntegerField, BooleanField
from wtforms.validators import DataRequired, Email, Optional, Length, NumberRange, URL
from models.consent import PURPOSES, LEGAL_BASES, CHANNELS


class ConsentForm(FlaskForm):
    name = StringField("Full Name", validators=[DataRequired(), Length(2, 255)])
    email = StringField("Email Address", validators=[DataRequired(), Email()])
    phone = StringField("Phone", validators=[Optional(), Length(max=50)])
    country = StringField("Country", validators=[Optional(), Length(max=100)])
    purpose = SelectField("Processing Purpose", validators=[DataRequired()],
                          choices=[(p, p) for p in PURPOSES])
    legal_basis = SelectField("Legal Basis", validators=[DataRequired()],
                              choices=[(b, b) for b in LEGAL_BASES])
    channel = SelectField("Collection Channel", validators=[DataRequired()],
                          choices=[(c, c) for c in CHANNELS])
    policy_version = SelectField("Policy Version", validators=[DataRequired()], choices=[])
    notes = TextAreaField("Notes", validators=[Optional(), Length(max=2000)])
    submit = SubmitField("Record Consent")


class PolicyVersionForm(FlaskForm):
    version = StringField("Version", validators=[DataRequired(), Length(max=50)])
    title = StringField("Title", validators=[DataRequired(), Length(max=255)])
    summary = TextAreaField("Summary", validators=[Optional(), Length(max=1000)])
    content = TextAreaField("Full Content", validators=[DataRequired()])
    is_current = SelectField("Set as Current", choices=[("1", "Yes — mark as active policy"), ("0", "No")])
    submit = SubmitField("Save Policy Version")


class PolicySourceForm(FlaskForm):
    name = StringField("Source Name", validators=[DataRequired(), Length(max=255)])
    url = StringField("Policy URL", validators=[DataRequired(), Length(max=1000), URL()])
    check_interval_min = IntegerField(
        "Check Every (minutes)",
        validators=[DataRequired(), NumberRange(min=5, max=10080)],
        default=60,
    )
    auto_set_current = BooleanField(
        "Make detected changes the current policy automatically",
        default=True,
    )
    submit = SubmitField("Watch This Policy")
