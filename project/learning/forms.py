from flask_wtf import FlaskForm
from wtforms import FieldList, Form, FormField, HiddenField, IntegerField, SelectField, TextAreaField
from wtforms.validators import InputRequired, Length, NumberRange
from wtforms.widgets import HiddenInput

from project.curriculum_terms import ARTIFACT_LANGUAGES


class ConceptRatingForm(FlaskForm):
    card_id = HiddenField(validators=[InputRequired(), Length(max=128)])
    content_version = IntegerField(widget=HiddenInput(), validators=[InputRequired(), NumberRange(1, 2147483647)])
    expected_revision = IntegerField(widget=HiddenInput(), validators=[InputRequired(), NumberRange(0, 2147483647)])
    request_id = HiddenField(validators=[InputRequired(), Length(min=36, max=36)])
    rating = SelectField(coerce=int, choices=[(0, "Again"), (3, "Hard"), (4, "Good"), (5, "Easy")],
                         validators=[InputRequired()])


LANGUAGE_LABELS = {"text": "Plain text", "markdown": "Markdown", "pseudocode": "Pseudocode", "sql": "SQL",
                   "python": "Python", "typescript": "TypeScript", "json": "JSON", "yaml": "YAML"}


class StartPracticeForm(FlaskForm):
    exercise_id = HiddenField(validators=[InputRequired(), Length(max=128)])
    concept_id = HiddenField(validators=[InputRequired(), Length(max=128)])
    request_id = HiddenField(validators=[InputRequired(), Length(min=36, max=36)])


class ArtifactEditForm(Form):
    """One artifact editor. CSRF belongs to the enclosing workspace form."""

    artifact_id = HiddenField(validators=[InputRequired(), Length(max=128)])
    base_revision = IntegerField(widget=HiddenInput(), validators=[InputRequired(), NumberRange(0, 2147483647)])
    # The service checks each notation against the artifact's format.
    language = SelectField(choices=[(name, LANGUAGE_LABELS[name]) for name in ARTIFACT_LANGUAGES],
                           validate_choice=False)
    body = TextAreaField()


class PracticeWorkspaceForm(FlaskForm):
    class Meta:
        # Learners may edit for hours. None would fall back to Flask-WTF's 3600 seconds.
        csrf_time_limit = 86400

    request_id = HiddenField(validators=[InputRequired(), Length(min=36, max=36)])
    artifacts = FieldList(FormField(ArtifactEditForm), max_entries=20)
