from flask_wtf import FlaskForm
from wtforms import HiddenField, IntegerField, SelectField
from wtforms.validators import InputRequired, Length, NumberRange
from wtforms.widgets import HiddenInput


class ConceptRatingForm(FlaskForm):
    card_id = HiddenField(validators=[InputRequired(), Length(max=128)])
    content_version = IntegerField(widget=HiddenInput(), validators=[InputRequired(), NumberRange(1, 2147483647)])
    expected_revision = IntegerField(widget=HiddenInput(), validators=[InputRequired(), NumberRange(0, 2147483647)])
    request_id = HiddenField(validators=[InputRequired(), Length(min=36, max=36)])
    rating = SelectField(coerce=int, choices=[(0, "Again"), (3, "Hard"), (4, "Good"), (5, "Easy")],
                         validators=[InputRequired()])
