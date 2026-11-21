"""Versioned feedback content: reference closure, compatibility, and private projections."""
from copy import deepcopy
import json
import unittest

from marshmallow import ValidationError

from project import create_app
from project.learning.content_schema import (
    evaluator_view, facilitator_view, interviewer_view, learner_view, load_catalog,
    opening_view, selector_view, validate_catalog,
)
from project.services.curriculum_service import content_checksum
from tests.curriculum_v2_fixtures import CATALOG_V2, PRIVATE_V2, feedback_catalog
from tests.test_curriculum import CATALOG


class FeedbackContentTests(unittest.TestCase):
    def setUp(self):
        self.catalog = load_catalog(CATALOG_V2)

    def mapping(self, catalog):
        return catalog["items"][-1]["content"]["assessment"]["misconceptions"][0]

    def test_v2_preserves_ids_lesson_questions_and_interview_contract(self):
        original = load_catalog(CATALOG)
        self.assertEqual((original["schema_version"], self.catalog["schema_version"]), (1, 2))
        self.assertEqual(len(self.catalog["items"]), len(original["items"]))
        for old, new in zip(original["items"], self.catalog["items"]):
            self.assertEqual((old["version"], new["version"]), (1, 2))
            content = deepcopy(new)
            content["version"] = 1
            if content["kind"] == "exercise":
                self.assertEqual(content["content"]["spec_version"], 2)
                mappings = content["content"]["assessment"].pop("misconceptions")
                self.assertEqual(len(mappings), 4)
                content["content"]["spec_version"] = 1
            self.assertEqual(content, old)
        linked_questions = {ref for mapping in mappings for ref in mapping["review_question_ids"]}
        self.assertEqual(linked_questions, set(original["items"][0]["content"]["review_question_ids"]))

    def test_catalog_and_exercise_versions_are_explicit_and_strict(self):
        for version in (None, True, 2.0, "2", 0, 3):
            with self.subTest(version=version):
                changed = deepcopy(self.catalog)
                changed["schema_version"] = version
                with self.assertRaises(ValidationError):
                    validate_catalog(changed)
                changed = deepcopy(self.catalog)
                changed["items"][-1]["content"]["spec_version"] = version
                with self.assertRaises(ValidationError):
                    validate_catalog(changed)
        changed = deepcopy(self.catalog)
        changed["items"][-1]["content"]["spec_version"] = 1
        with self.assertRaises(ValidationError):
            validate_catalog(changed)
        changed = load_catalog(CATALOG)
        changed["items"][-1]["content"]["assessment"]["misconceptions"] = [self.mapping(self.catalog)]
        with self.assertRaises(ValidationError):
            validate_catalog(changed)

    def test_mapping_fields_are_required_and_unknown_fields_fail_closed(self):
        for field in self.mapping(self.catalog):
            changed = deepcopy(self.catalog)
            self.mapping(changed).pop(field)
            with self.subTest(field=field), self.assertRaises(ValidationError):
                validate_catalog(changed)
        for target in (lambda c: c["items"][-1]["content"]["assessment"], self.mapping):
            changed = deepcopy(self.catalog)
            target(changed)["future_field"] = "not supported"
            with self.assertRaises(ValidationError):
                validate_catalog(changed)
        changed = deepcopy(self.catalog)
        changed["items"][-1]["content"]["assessment"].pop("misconceptions")
        with self.assertRaises(ValidationError):
            validate_catalog(changed)

    def test_mapping_and_question_collections_are_bounded_and_unique(self):
        for count in (0, 101):
            changed = deepcopy(self.catalog)
            changed["items"][-1]["content"]["assessment"]["misconceptions"] = [
                dict(self.mapping(self.catalog), id=f"misconception-{index}") for index in range(count)]
            with self.subTest(count=count), self.assertRaises(ValidationError):
                validate_catalog(changed)
        for refs in ([], ["idempotency:timeout"] * 2, ["idempotency:timeout"] * 101, "idempotency:timeout"):
            changed = deepcopy(self.catalog)
            self.mapping(changed)["review_question_ids"] = refs
            with self.subTest(refs=refs), self.assertRaises(ValidationError):
                validate_catalog(changed)
        changed = deepcopy(self.catalog)
        changed["items"][-1]["content"]["assessment"]["misconceptions"].append(deepcopy(self.mapping(changed)))
        with self.assertRaisesRegex(ValidationError, "Duplicate misconception ID"):
            validate_catalog(changed)

    def test_dimension_concept_section_and_question_links_are_checked(self):
        for change in (dict(dimension_id="unknown"), dict(concept_id="unknown"), dict(section_id="unknown"),
                       dict(review_question_ids=["idempotency:unknown"]), dict(review_question_ids=["idempotency"]),
                       dict(id="Invalid ID"), dict(description=None), dict(evidence_guidance="")):
            changed = deepcopy(self.catalog)
            self.mapping(changed).update(change)
            with self.subTest(change=change), self.assertRaises(ValidationError):
                validate_catalog(changed)

    def test_remediation_may_target_another_concept_but_questions_must_match(self):
        changed = deepcopy(self.catalog)
        prerequisite = deepcopy(changed["items"][0])
        prerequisite["id"] = "transactions"
        prerequisite["content"].update(exercise_ids=[], review_question_ids=["transactions:atomicity"])
        question = deepcopy(changed["items"][1])
        question["id"] = "transactions:atomicity"
        question["content"]["concept_id"] = "transactions"
        changed["items"].extend([prerequisite, question])
        mapping = changed["items"][5]["content"]["assessment"]["misconceptions"][0]
        mapping["concept_id"] = "transactions"
        with self.assertRaisesRegex(ValidationError, "belong to its remediation concept"):
            validate_catalog(changed)
        mapping["review_question_ids"] = ["transactions:atomicity"]
        self.assertEqual(validate_catalog(changed), changed)

    def test_evaluator_gets_an_allowlisted_copy_for_the_pinned_spec_version(self):
        exercise = deepcopy(self.catalog["items"][-1])
        exercise["content"]["assessment"]["misconceptions"][0]["future_private"] = "UNKNOWN"
        view = evaluator_view(exercise)
        self.assertEqual(set(view), {"reference_reasoning", "alternatives", "rubric", "remediation", "misconceptions"})
        self.assertNotIn("UNKNOWN", json.dumps(view))
        view["misconceptions"][0]["review_question_ids"].append("idempotency:scope")
        self.assertEqual(exercise["content"]["assessment"]["misconceptions"][0]["review_question_ids"],
                         ["idempotency:timeout"])
        self.assertNotIn("misconceptions", evaluator_view(load_catalog(CATALOG)["items"][-1]))
        for version in (True, "2", 3):
            exercise["content"]["spec_version"] = version
            with self.assertRaises(ValidationError):
                evaluator_view(exercise)

    def test_all_non_evaluator_audiences_exclude_mappings(self):
        exercise = feedback_catalog()["items"][-1]
        for view in (learner_view(exercise), opening_view(exercise), facilitator_view(exercise),
                     selector_view(exercise), interviewer_view(exercise),
                     interviewer_view(exercise, revealed_constraint_ids=["scope"], hint_index=0)):
            for secret in (*PRIVATE_V2, "misconceptions", "evidence_guidance"):
                self.assertNotIn(secret, json.dumps(view))
        for secret in PRIVATE_V2:
            self.assertIn(secret, json.dumps(evaluator_view(exercise)))

    def test_mapping_changes_are_part_of_the_immutable_checksum(self):
        exercise = self.catalog["items"][-1]
        changed = deepcopy(exercise)
        changed["content"]["assessment"]["misconceptions"][0]["review_question_ids"] = ["idempotency:race"]
        self.assertNotEqual(content_checksum(exercise, 2), content_checksum(changed, 2))
        self.assertNotEqual(content_checksum(exercise, 1), content_checksum(exercise, 2))

    def test_both_catalogs_validate_without_tables_and_v2_source_is_not_served(self):
        app = create_app(dict(TESTING=True, SECRET_KEY="fixture", SQLALCHEMY_DATABASE_URI="sqlite://"))
        for path in (CATALOG, CATALOG_V2):
            result = app.test_cli_runner().invoke(args=["validate-curriculum", str(path)])
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("6 items. No database changes.", result.output)
        for path in ("/curriculum/idempotency/catalog-v2.json", "/static/curriculum/idempotency/catalog-v2.json"):
            response = app.test_client().get(path, base_url="https://localhost")
            self.assertEqual(response.status_code, 404)
            self.assertNotIn(b"evidence_guidance", response.data)
