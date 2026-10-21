from flask_wtf import FlaskForm
from wtforms import HiddenField, StringField
from wtforms.validators import InputRequired


class AddJobForm(FlaskForm):
    request_id = HiddenField()
    expected_revision = HiddenField()
    # Shared service enforces lengths while allowing unchanged legacy values.
    title = StringField("Job title", validators=[InputRequired()])
    company_name = StringField("Company", validators=[InputRequired()])
    listing_url = StringField("Listing URL", validators=[InputRequired()])


class JobActionForm(FlaskForm):
    request_id = HiddenField(validators=[InputRequired()])
    expected_revision = HiddenField(validators=[InputRequired()])
    action = HiddenField(validators=[InputRequired()])
