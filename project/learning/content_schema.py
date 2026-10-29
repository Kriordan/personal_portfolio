"""Version 1 curriculum contracts. Unknown fields fail closed, including nested fields."""
from copy import deepcopy
from pathlib import Path
import json

from marshmallow import Schema, ValidationError, fields, validate

from project.curriculum_terms import ARTIFACT_FORMATS, INTERACTION_STYLES, MAX_EXPECTED_ARTIFACTS


def text_field():
    return fields.String(required=True, validate=validate.Length(min=1, max=50000))


def identifier():
    return fields.String(required=True, validate=[validate.Length(max=128),
        validate.Regexp(r"^[a-z][a-z0-9-]*(?::[a-z0-9-]+)?$",
            error="Use a lowercase stable ID with an optional :question suffix.")])


def texts():
    return fields.List(text_field(), required=True, validate=validate.Length(min=1, max=100))


def ids():
    return fields.List(identifier(), required=True, validate=validate.Length(max=100))


class PositiveInteger(fields.Integer):
    def _deserialize(self, value, attr, data, **kwargs):
        if type(value) is not int or not 1 <= value <= 2147483647:
            raise ValidationError("Must be a positive JSON integer no greater than 2147483647.")
        return super()._deserialize(value, attr, data, **kwargs)


class SectionSchema(Schema):
    id = identifier()
    title = text_field()
    markdown = text_field()


class ReferenceSchema(Schema):
    title = text_field()
    url = fields.Url(required=True, schemes={"https"})


class ConceptSchema(Schema):
    summary = text_field()
    domain = identifier()
    topic = identifier()
    learning_objectives = texts()
    prerequisites = ids()
    prerequisite_knowledge = texts()
    sections = fields.List(fields.Nested(SectionSchema), required=True, validate=validate.Length(min=1))
    review_question_ids = ids()
    exercise_ids = ids()
    references = fields.List(fields.Nested(ReferenceSchema), required=True, validate=validate.Length(min=1))


class QuestionSchema(Schema):
    concept_id = identifier()
    question_type = fields.String(required=True, validate=validate.OneOf(
        ["recall", "scenario", "comparison", "misconception", "tradeoff"]))
    prompt = text_field()
    answer = text_field()
    explanation = text_field()
    remediation_section_id = identifier()


class ArtifactSchema(Schema):
    id = identifier()
    title = text_field()
    format = fields.String(required=True, validate=validate.OneOf(ARTIFACT_FORMATS))
    instructions = text_field()


class DimensionSchema(Schema):
    id = identifier()
    label = text_field()


class BriefSchema(Schema):
    scenario = text_field()
    learning_objectives = texts()
    functional_requirements = texts()
    nonfunctional_requirements = texts()
    prerequisite_concept_ids = ids()
    expected_artifacts = fields.List(fields.Nested(ArtifactSchema), required=True,
        validate=validate.Length(min=1, max=MAX_EXPECTED_ARTIFACTS))
    assessment_dimensions = fields.List(fields.Nested(DimensionSchema), required=True,
        validate=validate.Length(min=1))


class ConstraintSchema(Schema):
    id = identifier()
    clarification_cues = texts()
    fact = text_field()


class FacilitatorSchema(Schema):
    interaction_style = fields.String(required=True, validate=validate.OneOf(INTERACTION_STYLES))
    opening_prompt = text_field()
    instructions = texts()
    hidden_constraints = fields.List(fields.Nested(ConstraintSchema), required=True)
    permitted_hints = fields.List(text_field(), required=True)


class AlternativeSchema(Schema):
    approach = text_field()
    benefits = texts()
    tradeoffs = texts()


class AnchorsSchema(Schema):
    needs_work = text_field()
    developing = text_field()
    strong = text_field()


class RubricSchema(Schema):
    dimension_id = identifier()
    anchors = fields.Nested(AnchorsSchema, required=True)


class RemediationSchema(Schema):
    dimension_id = identifier()
    concept_id = identifier()
    section_id = identifier()
    suggestion = text_field()


class AssessmentSchema(Schema):
    reference_reasoning = texts()
    alternatives = fields.List(fields.Nested(AlternativeSchema), required=True,
        validate=validate.Length(min=1))
    rubric = fields.List(fields.Nested(RubricSchema), required=True, validate=validate.Length(min=1))
    remediation = fields.List(fields.Nested(RemediationSchema), required=True,
        validate=validate.Length(min=1))


class ExerciseSchema(Schema):
    spec_version = PositiveInteger(required=True, validate=validate.Equal(1))
    concept_id = identifier()
    brief = fields.Nested(BriefSchema, required=True)
    facilitator = fields.Nested(FacilitatorSchema, required=True)
    assessment = fields.Nested(AssessmentSchema, required=True)


class ItemSchema(Schema):
    id = identifier()
    version = PositiveInteger(required=True)
    kind = fields.String(required=True, validate=validate.OneOf(["concept", "question", "exercise"]))
    title = text_field()
    content = fields.Dict(required=True)


class CatalogSchema(Schema):
    schema_version = PositiveInteger(required=True, validate=validate.Equal(1))
    items = fields.List(fields.Nested(ItemSchema), required=True, validate=validate.Length(min=1, max=2000))


CONTENT_SCHEMAS = {"concept": ConceptSchema, "question": QuestionSchema, "exercise": ExerciseSchema}


def _unique(values, label):
    if len(set(values)) != len(values):
        raise ValidationError(f"Duplicate {label}.")


def validate_catalog(document):
    """Validate a complete reference closure, without consulting mutable DB state."""
    result = CatalogSchema().load(deepcopy(document))
    items = result["items"]
    _unique([item["id"] for item in items], "item ID")
    by_id = {item["id"]: item for item in items}
    for item in items:
        if len(item["id"]) > 128:
            raise ValidationError("Item ID exceeds 128 characters.")
        item["content"] = CONTENT_SCHEMAS[item["kind"]]().load(item["content"])

    def linked(item_id, kind):
        target = by_id.get(item_id)
        if target is None or target["kind"] != kind:
            raise ValidationError(f"Missing {kind} reference: {item_id}.")
        return target["content"]

    def section(concept_id, section_id):
        if section_id not in {s["id"] for s in linked(concept_id, "concept")["sections"]}:
            raise ValidationError(f"Missing section: {concept_id}/{section_id}.")

    for item in items:
        body = item["content"]
        if item["kind"] == "concept":
            _unique([s["id"] for s in body["sections"]], "section ID")
            for key, kind in (("prerequisites", "concept"), ("review_question_ids", "question"), ("exercise_ids", "exercise")):
                _unique(body[key], key)
                for ref in body[key]:
                    target = linked(ref, kind)
                    if kind != "concept" and target["concept_id"] != item["id"]:
                        raise ValidationError(f"Mismatched parent concept: {ref}.")
        else:
            parent = linked(body["concept_id"], "concept")
            membership = "review_question_ids" if item["kind"] == "question" else "exercise_ids"
            if item["id"] not in parent[membership]:
                raise ValidationError(f"Parent concept must link {item['id']}.")
            if item["kind"] == "question":
                if not item["id"].startswith(body["concept_id"] + ":"):
                    raise ValidationError("Question IDs must use concept-id:question-id.")
                section(body["concept_id"], body["remediation_section_id"])
                continue
            brief, facilitator, assessment = body["brief"], body["facilitator"], body["assessment"]
            for collection in (brief["expected_artifacts"], brief["assessment_dimensions"], facilitator["hidden_constraints"]):
                _unique([entry["id"] for entry in collection], "exercise entry ID")
            for ref in brief["prerequisite_concept_ids"]:
                linked(ref, "concept")
            dimensions = {entry["id"] for entry in brief["assessment_dimensions"]}
            rubric_ids = [entry["dimension_id"] for entry in assessment["rubric"]]
            _unique(rubric_ids, "rubric dimension")
            if set(rubric_ids) != dimensions:
                raise ValidationError("Rubric must cover exactly the public assessment dimensions.")
            for remedy in assessment["remediation"]:
                if remedy["dimension_id"] not in dimensions:
                    raise ValidationError("Remediation references an unknown dimension.")
                section(remedy["concept_id"], remedy["section_id"])

    visited, visiting = set(), set()

    def visit(item_id):
        if item_id in visiting:
            raise ValidationError("Concept prerequisites contain a cycle.")
        if item_id in visited:
            return
        visiting.add(item_id)
        for ref in linked(item_id, "concept")["prerequisites"]:
            visit(ref)
        visiting.remove(item_id)
        visited.add(item_id)

    for item in items:
        if item["kind"] == "concept":
            visit(item["id"])
    return result


def _json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError(f"Duplicate JSON key: {key}.")
        result[key] = value
    return result


def load_catalog(path):
    """Resolve Markdown only inside the catalog directory, then freeze its text."""
    path = Path(path).resolve()
    document = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_json_object)
    # Validate the envelope before walking source-controlled paths.
    document = CatalogSchema().load(document)
    for item in document["items"]:
        if item["kind"] != "concept":
            continue
        sections = item["content"].get("sections", [])
        if not isinstance(sections, list):
            raise ValidationError("Concept sections must be an array.")
        for section in sections:
            if not isinstance(section, dict) or "markdown_file" not in section:
                continue
            relative = section.pop("markdown_file")
            if not isinstance(relative, str) or "markdown" in section:
                raise ValidationError("Use exactly one Markdown source per section.")
            source = (path.parent / relative).resolve()
            if not source.is_relative_to(path.parent) or source.suffix != ".md":
                raise ValidationError("Markdown source must be a .md file inside the catalog directory.")
            section["markdown"] = source.read_text(encoding="utf-8")
    return validate_catalog(document)


def learner_view(item, *, reveal_answer=False):
    """An explicit DTO, never a serialization of the stored private snapshot."""
    result = {key: item[key] for key in ("id", "kind", "title", "version")}
    body = item["content"]
    if item["kind"] == "exercise":
        result["content"] = {"spec_version": body["spec_version"], "concept_id": body["concept_id"],
                             "brief": BriefSchema().dump(body["brief"])}
    else:
        schema = CONTENT_SCHEMAS[item["kind"]]
        exclude = () if item["kind"] != "question" or reveal_answer else ("answer", "explanation")
        result["content"] = schema(exclude=exclude).dump(body)
    return deepcopy(result)


def facilitator_view(item, *, revealed_constraint_ids=()):
    """Only server-approved disclosures reach the conversation counterpart."""
    body = item["content"]["facilitator"]
    known = {constraint["id"] for constraint in body["hidden_constraints"]}
    if not set(revealed_constraint_ids) <= known:
        raise ValidationError("Unknown constraint disclosure.")
    result = FacilitatorSchema(exclude=("hidden_constraints",)).dump(body)
    result["revealed_constraints"] = [ConstraintSchema(only=("id", "fact")).dump(constraint)
        for constraint in body["hidden_constraints"] if constraint["id"] in revealed_constraint_ids]
    return deepcopy(result)


def opening_view(item):
    """The interviewer's authored first line, which the learner is meant to see.

    It is the only facilitator field a learner receives; hints, instructions and
    hidden facts stay server-side.
    """
    body = item["content"]["facilitator"]
    return {"interaction_style": body["interaction_style"], "opening_prompt": body["opening_prompt"]}


def selector_view(item, *, revealed_constraint_ids=()):
    """What the disclosure selector may see: the clarification cues of requirements still hidden.

    Never facts, hints, instructions, or evaluation material.
    """
    body = item["content"]["facilitator"]
    known = {constraint["id"] for constraint in body["hidden_constraints"]}
    if not set(revealed_constraint_ids) <= known:
        raise ValidationError("Unknown constraint disclosure.")
    return deepcopy([{"id": constraint["id"], "cues": list(constraint["clarification_cues"])}
                     for constraint in body["hidden_constraints"]
                     if constraint["id"] not in revealed_constraint_ids])


def interviewer_view(item, *, revealed_constraint_ids=(), hint_index=None):
    """What the conversational call may see: the authored instructions, the revealed facts, and
    one permitted hint only when the learner asked for help.

    Never clarification cues, unrevealed facts, other hints, or evaluation material.
    """
    body = item["content"]["facilitator"]
    known = {constraint["id"] for constraint in body["hidden_constraints"]}
    if not set(revealed_constraint_ids) <= known:
        raise ValidationError("Unknown constraint disclosure.")
    hints = body["permitted_hints"]
    if hint_index is not None and not (type(hint_index) is int and 0 <= hint_index < len(hints)):
        raise ValidationError("Unknown hint.")
    return deepcopy({
        "interaction_style": body["interaction_style"],
        "instructions": list(body["instructions"]),
        "revealed_constraints": [{"id": constraint["id"], "fact": constraint["fact"]}
                                 for constraint in body["hidden_constraints"]
                                 if constraint["id"] in revealed_constraint_ids],
        "hint": hints[hint_index] if hint_index is not None else None,
    })


def evaluator_view(item):
    """Server use only; do not attach this to a learner or conversation response."""
    return deepcopy(AssessmentSchema().dump(item["content"]["assessment"]))
