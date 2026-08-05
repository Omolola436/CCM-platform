from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField, SubmitField, DateTimeLocalField
from wtforms.validators import DataRequired, Email, Optional, Length
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
