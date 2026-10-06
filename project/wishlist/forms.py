from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length


class GiftForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(max=140)], filters=[lambda value: value.strip() if value else value])
    body = TextAreaField("Description", validators=[DataRequired(), Length(max=140)], filters=[lambda value: value.strip() if value else value])
    image = FileField("Image", validators=[FileAllowed(["jpg", "jpeg", "png"])])
