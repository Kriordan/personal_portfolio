"""Vocabulary and limits shared by curriculum schemas, practice models, and forms.

This lives outside the ``project.learning`` package, whose import loads its views,
so models can use it without a circular import. Migrations copy these values
rather than importing them, because a migration must describe its own point in time.
"""

ARTIFACT_FORMATS = ("text", "markdown", "pseudocode", "sql", "typescript", "python", "api-definition")
INTERACTION_STYLES = ("interviewer", "coach", "collaborative", "reviewer")
# The notation a learner writes an artifact in. An API definition may be prose or
# structured; every other format is its own notation.
ARTIFACT_LANGUAGES = ("text", "markdown", "pseudocode", "sql", "python", "typescript", "json", "yaml")
FORMAT_LANGUAGES = {**{name: (name,) for name in ARTIFACT_FORMATS if name != "api-definition"},
                    "api-definition": ("text", "json", "yaml")}
# Kinds of entry in a practice session's editable brief, and how many it holds.
BRIEF_ENTRY_TYPES = ("assumption", "question", "decision", "next_step")
BRIEF_MAX_ENTRIES = 50
# Every artifact an exercise expects must fit one workspace form and one save.
MAX_EXPECTED_ARTIFACTS = 20
