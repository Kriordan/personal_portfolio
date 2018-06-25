from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired


class AddImageForm(FlaskForm):
    image = FileField(
        validators=[FileRequired()]
    )