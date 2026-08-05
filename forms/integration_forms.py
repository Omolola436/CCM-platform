from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField, SubmitField, SelectMultipleField, widgets
from wtforms.validators import DataRequired, Optional, URL, Length
from models.integration import INTEGRATION_TYPES

WEBHOOK_EVENTS = [
    "consent.granted",
    "consent.withdrawn",
    "consent.expired",
    "consent.updated",
    "subject.created",
    "subject.deleted",
]


class MultiCheckboxField(SelectMultipleField):
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()


class IntegrationForm(FlaskForm):
    name = StringField("Integration Name", validators=[DataRequired(), Length(max=255)])
    type = SelectField("Type", choices=[(t, t.upper()) for t in INTEGRATION_TYPES])
    description = TextAreaField("Description", validators=[Optional(), Length(max=1000)])
    endpoint = StringField("Endpoint / Base URL", validators=[Optional(), Length(max=500)])
    api_key = StringField("API Key / Token", validators=[Optional(), Length(max=500)])
    submit = SubmitField("Save Integration")


class WebhookForm(FlaskForm):
    name = StringField("Webhook Name", validators=[DataRequired(), Length(max=255)])
    url = StringField("Endpoint URL", validators=[DataRequired(), Length(max=500)])
    events = MultiCheckboxField("Trigger Events", choices=[(e, e) for e in WEBHOOK_EVENTS])
    secret = StringField("Signing Secret", validators=[Optional(), Length(max=255)])
    submit = SubmitField("Save Webhook")
