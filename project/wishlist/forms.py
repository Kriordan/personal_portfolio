from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired


class GiftForm(FlaskForm):
    body = TextAreaField("Body", validators=[DataRequired()])
    title = StringField("Title", validators=[DataRequired()])
    submit = SubmitField("Submit")
