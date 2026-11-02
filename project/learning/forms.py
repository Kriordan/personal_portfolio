from flask_wtf import FlaskForm
from wtforms import BooleanField, FieldList, Form, FormField, HiddenField, IntegerField, SelectField, TextAreaField
from wtforms.validators import InputRequired, Length, NumberRange
from wtforms.widgets import HiddenInput

from project.curriculum_terms import ARTIFACT_LANGUAGES, BRIEF_ENTRY_TYPES, BRIEF_MAX_ENTRIES, MAX_EXPECTED_ARTIFACTS


class ConceptRatingForm(FlaskForm):
    card_id = HiddenField(validators=[InputRequired(), Length(max=128)])
    content_version = IntegerField(widget=HiddenInput(), validators=[InputRequired(), NumberRange(1, 2147483647)])
    expected_revision = IntegerField(widget=HiddenInput(), validators=[InputRequired(), NumberRange(0, 2147483647)])
    request_id = HiddenField(validators=[InputRequired(), Length(min=36, max=36)])
    rating = SelectField(coerce=int, choices=[(0, "Again"), (3, "Hard"), (4, "Good"), (5, "Easy")],
                         validators=[InputRequired()])


LANGUAGE_LABELS = {"text": "Plain text", "markdown": "Markdown", "pseudocode": "Pseudocode", "sql": "SQL",
                   "python": "Python", "typescript": "TypeScript", "json": "JSON", "yaml": "YAML"}


class FeedbackForm(FlaskForm):
    request_id = HiddenField(validators=[InputRequired(), Length(min=36, max=36)])


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


BRIEF_TYPE_LABELS = {"assumption": "Assumption", "question": "Open question", "decision": "Decision",
                     "next_step": "Next step"}
# Saved entries plus the blank rows a page offers for new ones.
BRIEF_ROWS = BRIEF_MAX_ENTRIES + 3


class BriefEntryForm(Form):
    """One row of the learner's brief. The website can't edit sources; they round-trip unchanged.

    The entry type is `kind` here because a WTForms field named `type` is shadowed by
    the enclosing field's own `type` attribute.
    """

    entry_id = HiddenField(validators=[Length(max=64)])
    kind = SelectField(choices=[(name, BRIEF_TYPE_LABELS[name]) for name in BRIEF_ENTRY_TYPES],
                       validate_choice=False)
    text = TextAreaField()
    pinned = BooleanField()
    remove = BooleanField()
    sources = HiddenField(validators=[Length(max=4096)])


class PracticeWorkspaceForm(FlaskForm):
    """Artifacts, the learner's brief, and a message: every action submits all of them."""

    class Meta:
        # Learners may edit for hours. None would fall back to Flask-WTF's 3600 seconds.
        csrf_time_limit = 86400

    request_id = HiddenField(validators=[InputRequired(), Length(min=36, max=36)])
    expected_sequence = IntegerField(widget=HiddenInput(), validators=[InputRequired(), NumberRange(0, 2147483647)])
    brief_revision = IntegerField(widget=HiddenInput(), validators=[InputRequired(), NumberRange(0, 2147483647)])
    artifacts = FieldList(FormField(ArtifactEditForm), max_entries=MAX_EXPECTED_ARTIFACTS)
    brief = FieldList(FormField(BriefEntryForm), max_entries=BRIEF_ROWS)
    message = TextAreaField()


class DeletePracticeForm(FlaskForm):
    """Confirms a delete; it carries only the CSRF token."""
