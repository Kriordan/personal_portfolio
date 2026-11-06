"""A private reference correction preserves the lesson and its existing contracts."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from project import create_app
from project.learning.content_schema import (
    evaluator_view, facilitator_view, interviewer_view, learner_view, load_catalog,
    opening_view, selector_view,
)
from project.services.curriculum_service import content_checksum
from tests.curriculum_v2_fixtures import CATALOG_V2

CATALOG_V3 = Path(__file__).resolve().parents[1] / "curriculum/idempotency/catalog-v3.json"


class ReferenceRevisionTests(unittest.TestCase):
    def setUp(self):
        self.before = load_catalog(CATALOG_V2)
        self.after = load_catalog(CATALOG_V3)

    def test_only_the_private_reference_advances_content_identity(self):
        self.assertEqual((self.before["schema_version"], self.after["schema_version"]), (2, 2))
        self.assertEqual(self.before["items"][:-1], self.after["items"][:-1])
        old, new = self.before["items"][-1], self.after["items"][-1]
        self.assertEqual((old["version"], new["version"], new["content"]["spec_version"]), (2, 3, 2))
        self.assertNotEqual(content_checksum(old, 2), content_checksum(new, 2))
        restored = deepcopy(new)
        restored["version"] = old["version"]
        old_reasoning = old["content"]["assessment"]["reference_reasoning"]
        new_reasoning = restored["content"]["assessment"]["reference_reasoning"]
        self.assertEqual(len(old_reasoning), len(new_reasoning))
        self.assertEqual([i for i, pair in enumerate(zip(old_reasoning, new_reasoning)) if pair[0] != pair[1]], [1])
        restored["content"]["assessment"]["reference_reasoning"] = old_reasoning
        self.assertEqual(restored, old)

    def test_correction_reaches_only_the_evaluator_projection(self):
        old, new = self.before["items"][-1], self.after["items"][-1]
        corrected = new["content"]["assessment"]["reference_reasoning"][1]
        self.assertIn(corrected, evaluator_view(new)["reference_reasoning"])
        self.assertNotIn(corrected, evaluator_view(old)["reference_reasoning"])
        same_version = dict(new, version=old["version"])
        for projection in (learner_view, opening_view, facilitator_view, selector_view, interviewer_view):
            with self.subTest(projection=projection.__name__):
                self.assertEqual(projection(old), projection(same_version))
                self.assertNotIn(corrected, json.dumps(projection(new)))

    def test_revision_validates_without_tables_and_source_is_not_served(self):
        app = create_app(dict(TESTING=True, SECRET_KEY="fixture", SQLALCHEMY_DATABASE_URI="sqlite://"))
        result = app.test_cli_runner().invoke(args=["validate-curriculum", str(CATALOG_V3)])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("6 items. No database changes.", result.output)
        for path in ("/curriculum/idempotency/catalog-v3.json", "/static/curriculum/idempotency/catalog-v3.json"):
            self.assertEqual(app.test_client().get(path, base_url="https://localhost").status_code, 404)
