from flask_wtf import FlaskForm
from wtforms import StringField
from wtforms.validators import URL, InputRequired


class AddJobForm(FlaskForm):
    title = StringField(
        "Job Title", validators=[InputRequired("What's the job title?")]
    )
    company_name = StringField(
        "Company Name", validators=[InputRequired("Need a company name")]
    )
    listing_url = StringField(
        "Listing URL",
        validators=[
            InputRequired("Enter the listing's url"),
            URL("This url is no good"),
        ],
    )
