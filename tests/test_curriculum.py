"""Content contracts and audience boundaries, with deterministic local fixtures."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from marshmallow import ValidationError

from project import create_app
from project.learning.content_schema import (
    evaluator_view, facilitator_view, learner_view, load_catalog, opening_view, validate_catalog,
)
from project.services.curriculum_service import content_checksum

CATALOG = Path(__file__).resolve().parents[1] / "curriculum/idempotency/catalog.json"


class CurriculumSchemaTests(unittest.TestCase):
    def setUp(self):
        self.catalog = load_catalog(CATALOG)

    def test_complete_pilot_content_and_markdown_snapshots(self):
        self.assertEqual([item["kind"] for item in self.catalog["items"]],
                         ["concept", "question", "question", "question", "question", "exercise"])
        concept = self.catalog["items"][0]
        self.assertIn("timeout", concept["content"]["sections"][0]["markdown"])
        self.assertNotIn("markdown_file", json.dumps(self.catalog))
        self.assertEqual(content_checksum(concept), content_checksum(dict(reversed(list(concept.items())))))
        changed = deepcopy(concept)
        changed["content"]["sections"][0]["markdown"] += "\nA correction."
        self.assertNotEqual(content_checksum(concept), content_checksum(changed))

    def test_strict_versions_unknown_fields_and_duplicate_ids(self):
        for invalid in (True, 1.5, "1", 0, 2147483648):
            with self.subTest(invalid=invalid):
                draft = deepcopy(self.catalog)
                draft["items"][0]["version"] = invalid
                with self.assertRaises(ValidationError):
                    validate_catalog(draft)
        draft = deepcopy(self.catalog)
        draft["items"][-1]["content"]["brief"]["reference_solution"] = "Must not become public"
        with self.assertRaises(ValidationError):
            validate_catalog(draft)
        draft = deepcopy(self.catalog)
        draft["items"].append(deepcopy(draft["items"][0]))
        with self.assertRaisesRegex(ValidationError, "Duplicate item"):
            validate_catalog(draft)
        draft = deepcopy(self.catalog)
        draft["items"][-1]["content"]["spec_version"] = 2
        with self.assertRaises(ValidationError):
            validate_catalog(draft)

    def test_missing_links_cycles_and_mismatched_rubrics_fail(self):
        mutations = [
            lambda c: c["items"][0]["content"].update(prerequisites=["absent"]),
            lambda c: c["items"][0]["content"].update(prerequisites=["idempotency"]),
            lambda c: c["items"][1]["content"].update(remediation_section_id="absent"),
            lambda c: c["items"][-1]["content"]["assessment"]["rubric"].pop(),
            lambda c: c["items"][-1]["content"]["assessment"]["remediation"][0].update(concept_id="absent"),
            lambda c: c["items"][0]["content"]["review_question_ids"].pop(),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                draft = deepcopy(self.catalog)
                mutate(draft)
                with self.assertRaises(ValidationError):
                    validate_catalog(draft)

    def test_duplicate_json_keys_and_escaping_markdown_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "catalog.json"
            path.write_text('{"schema_version": 1, "schema_version": 1, "items": []}')
            with self.assertRaisesRegex(ValidationError, "Duplicate JSON key"):
                load_catalog(path)
            for source in ("../outside.md", "/outside.md", "linked.md"):
                with self.subTest(source=source):
                    if source == "linked.md":
                        (root / source).symlink_to(root.parent / "outside.md")
                    draft = deepcopy(self.catalog)
                    section = draft["items"][0]["content"]["sections"][0]
                    section.pop("markdown")
                    section["markdown_file"] = source
                    path.write_text(json.dumps(draft))
                    with self.assertRaisesRegex(ValidationError, "inside the catalog"):
                        load_catalog(path)

    def test_learner_projection_excludes_all_private_fields_and_future_fields(self):
        exercise = deepcopy(self.catalog["items"][-1])
        exercise["content"]["assessment"]["reference_reasoning"] = ["EVALUATOR_SENTINEL"]
        exercise["content"]["facilitator"]["hidden_constraints"][0]["fact"] = "HIDDEN_SENTINEL"
        exercise["content"]["brief"]["future_private_field"] = "FUTURE_SENTINEL"
        exercise["content"]["brief"]["expected_artifacts"][0]["future_private_field"] = "NESTED_SENTINEL"
        result = learner_view(exercise)
        serialized = json.dumps(result)
        for secret in ("EVALUATOR_SENTINEL", "HIDDEN_SENTINEL", "FUTURE_SENTINEL", "NESTED_SENTINEL", "facilitator", "assessment\""):
            self.assertNotIn(secret, serialized)
        result["content"]["brief"]["expected_artifacts"][0]["title"] = "Changed locally"
        self.assertNotEqual(result["content"]["brief"], exercise["content"]["brief"])
        self.assertEqual(exercise["content"]["brief"]["expected_artifacts"][0]["title"], "API contract")

    def test_facilitator_gets_only_approved_facts_and_never_evaluation(self):
        exercise = self.catalog["items"][-1]
        self.assertEqual(facilitator_view(exercise)["revealed_constraints"], [])
        disclosed = facilitator_view(exercise, revealed_constraint_ids=["scope"])
        self.assertEqual([entry["id"] for entry in disclosed["revealed_constraints"]], ["scope"])
        self.assertNotIn("clarification_cues", json.dumps(disclosed))
        self.assertNotIn("reference_reasoning", disclosed)
        with self.assertRaises(ValidationError):
            facilitator_view(exercise, revealed_constraint_ids=["invented"])
        self.assertIn("reference_reasoning", evaluator_view(exercise))
        self.assertEqual(disclosed["interaction_style"], "interviewer")

    def test_opening_view_exposes_only_the_authored_first_line(self):
        exercise = deepcopy(self.catalog["items"][-1])
        facilitator = exercise["content"]["facilitator"]
        facilitator["instructions"] = ["INSTRUCTION_SENTINEL"]
        facilitator["permitted_hints"] = ["HINT_SENTINEL"]
        facilitator["hidden_constraints"][0].update(fact="HIDDEN_SENTINEL", clarification_cues=["CUE_SENTINEL"])
        exercise["content"]["assessment"]["reference_reasoning"] = ["EVALUATOR_SENTINEL"]
        opening = opening_view(exercise)
        self.assertEqual(opening, {"interaction_style": "interviewer",
                                   "opening_prompt": facilitator["opening_prompt"]})
        serialized = json.dumps(opening)
        for secret in ("INSTRUCTION_SENTINEL", "HINT_SENTINEL", "HIDDEN_SENTINEL", "CUE_SENTINEL", "EVALUATOR_SENTINEL"):
            self.assertNotIn(secret, serialized)

    def test_shared_terms_match_the_content_schema(self):
        from project.curriculum_terms import ARTIFACT_FORMATS, ARTIFACT_LANGUAGES, FORMAT_LANGUAGES
        self.assertEqual(set(FORMAT_LANGUAGES), set(ARTIFACT_FORMATS))
        self.assertTrue(all(set(languages) <= set(ARTIFACT_LANGUAGES) for languages in FORMAT_LANGUAGES.values()))
        draft = deepcopy(self.catalog)
        draft["items"][-1]["content"]["brief"]["expected_artifacts"][0]["format"] = "yaml"
        with self.assertRaises(ValidationError):
            validate_catalog(draft)

    def test_an_exercise_expects_at_most_twenty_artifacts(self):
        # The practice workspace edits every artifact in one form and saves them in one request.
        for count, valid in ((20, True), (21, False)):
            with self.subTest(count=count):
                draft = deepcopy(self.catalog)
                brief = draft["items"][-1]["content"]["brief"]
                brief["expected_artifacts"] = [dict(brief["expected_artifacts"][0], id=f"part-{index}")
                                               for index in range(count)]
                if valid:
                    validate_catalog(draft)
                else:
                    with self.assertRaisesRegex(ValidationError, "expected_artifacts"):
                        validate_catalog(draft)

    def test_review_answer_requires_explicit_reveal(self):
        question = self.catalog["items"][1]
        self.assertNotIn("answer", learner_view(question)["content"])
        self.assertNotIn("explanation", learner_view(question)["content"])
        self.assertEqual(learner_view(question, reveal_answer=True)["content"]["answer"],
                         question["content"]["answer"])

    def test_validation_cli_needs_no_database_tables(self):
        app = create_app(dict(TESTING=True, SECRET_KEY="fixture", SQLALCHEMY_DATABASE_URI="sqlite://"))
        result = app.test_cli_runner().invoke(args=["validate-curriculum", str(CATALOG)])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("6 items. No database changes.", result.output)

    def test_private_source_is_not_served_as_a_web_asset(self):
        app = create_app(dict(TESTING=True, SECRET_KEY="fixture", SQLALCHEMY_DATABASE_URI="sqlite://"))
        for path in ("/curriculum/idempotency/catalog.json", "/static/curriculum/idempotency/catalog.json"):
            with self.subTest(path=path):
                response = app.test_client().get(path, base_url="https://localhost")
                self.assertEqual(response.status_code, 404)
                self.assertNotIn(b"reference_reasoning", response.data)
