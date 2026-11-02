"""Deterministic parser fixtures, including resource and object-construction boundaries."""
import json
from pathlib import Path
import tempfile
import unittest

from project.learning.artifact_checks import MAX_BYTES, MAX_DEPTH, MAX_NODES, check_artifact


class ArtifactCheckTests(unittest.TestCase):
    def test_valid_documents_and_scalar_values(self):
        for language, bodies in {
            "json": ['{"path":"/orders","retry":true}', '[]', 'null', '"[\\\"{"', '1' * 5000],
            "yaml": ['path: /orders\nretry: true\n', '- one\n- two', 'null', '"hello"'],
        }.items():
            for body in bodies:
                with self.subTest(language=language, body=body[:40]):
                    self.assertEqual(check_artifact(language, body)["status"], "passed")

    def test_invalid_documents_report_locations_without_echoing_content(self):
        for language, body, location in (
            ("json", '{\n "secret": }', (2, 12)),
            ("json", '{"é": }', (1, 7)),
            ("yaml", 'secret: [\n', (2, 1)),
        ):
            result = check_artifact(language, body)
            self.assertEqual(result["status"], "error")
            self.assertEqual((result["line"], result["column"]), location)
            self.assertNotIn("secret", json.dumps(result))

    def test_non_json_numeric_constants_and_multiple_documents(self):
        for body in ('NaN', 'Infinity', '-Infinity', '{} {}'):
            self.assertEqual(check_artifact("json", body)["status"], "error")
        self.assertEqual(check_artifact("yaml", '---\na: b\n---\nc: d')["code"], "yaml_subset")

    def test_duplicates_and_unsupported_yaml_values_are_not_design_failures(self):
        for language, body in (("json", '{"a":1,"a":2}'), ("yaml", 'a: 1\na: 2')):
            self.assertEqual(check_artifact(language, body)["code"], "duplicates")
        for body in ('!custom hello', '? [a, b]\n: value', '2026-99-99', 'a: ' + '9' * 5000):
            result = check_artifact("yaml", body)
            self.assertEqual((result["status"], result["code"]), ("not_checked", "yaml_subset"))

    def test_aliases_and_recursive_aliases_are_refused(self):
        for body in ('a: &anchor [1,2]\nb: *anchor', '&anchor [*anchor]',
                     'a: &a [1]\nb: &b [*a,*a]\nc: [*b,*b]'):
            self.assertEqual(check_artifact("yaml", body)["code"], "aliases")

    def test_python_object_tags_never_execute(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "must-not-exist"
            body = f'!!python/object/apply:builtins.open ["{target}", "w"]'
            self.assertEqual(check_artifact("yaml", body)["code"], "yaml_subset")
            self.assertFalse(target.exists())

    def test_byte_nesting_and_node_limits(self):
        for language in ("json", "yaml"):
            self.assertEqual(check_artifact(language, '"' + 'é' * (MAX_BYTES // 2) + '"')["code"], "size")
            self.assertEqual(check_artifact(language, '[' * (MAX_DEPTH + 1) + ']' * (MAX_DEPTH + 1))["code"],
                             "complexity")
        self.assertEqual(check_artifact("yaml", '- x\n' * MAX_NODES)["code"], "complexity")

    def test_empty_and_unsupported_formats_are_explicitly_not_checked(self):
        for language in ("json", "yaml"):
            self.assertEqual(check_artifact(language, ' \n')["code"], "empty")
        for language in ("sql", "python", "typescript", "pseudocode", "text"):
            self.assertEqual(check_artifact(language, 'anything')["code"], "unsupported")
