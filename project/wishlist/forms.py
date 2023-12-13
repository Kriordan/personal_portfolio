from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField
from wtforms.validators import URL, DataRequired


class GiftForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired()])
    description = TextAreaField("Description", validators=[DataRequired()])
    image_url = StringField("Image URL", validators=[DataRequired(), URL()])
