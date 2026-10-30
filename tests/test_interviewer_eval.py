"""The interviewer evaluation harness: the reviewed cases, its checks, and the learning-eval command."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from project import create_app
from project.learning import interviewer, interviewer_eval
from project.learning.content_schema import evaluator_view
from project.services.practice_worker import FakeProvider

SETTINGS = dict(provider="fake", model="fake-interviewer", selector_model="fake-interviewer", tier="default",
                max_output_tokens=1200, selector_max_output_tokens=200, reasoning_effort=None, call_seconds=60)


class InterviewerEvaluationTests(unittest.TestCase):
    def setUp(self):
        data = interviewer_eval.load_cases()
        self.cases = {case["id"]: case for case in data["cases"]}
        self.item = interviewer_eval.exercise(data["exercise_id"])

    def checks(self, case_id, provider):
        return interviewer_eval.run_case(provider, self.item, self.cases[case_id], SETTINGS,
                                         profile_version="interviewer-1")["checks"]

    def test_the_cases_are_well_formed(self):
        facilitator = self.item["content"]["facilitator"]
        known = {entry["id"] for entry in facilitator["hidden_constraints"]}
        artifacts = {spec["id"] for spec in self.item["content"]["brief"]["expected_artifacts"]}
        self.assertGreaterEqual(len(self.cases), 12)
        for case in self.cases.values():
            with self.subTest(case=case["id"]):
                self.assertTrue(set(case["expect"]["constraint_ids"]) <= known - set(case.get("revealed_before", [])))
                self.assertIs(type(case["expect"]["hint_requested"]), bool)
                self.assertTrue(set(case.get("artifacts", {})) <= artifacts)
                self.assertTrue(case["reply_should"])
        # A paraphrase for every hidden requirement, none quoting its cues.
        for entry in facilitator["hidden_constraints"]:
            case = self.cases[f"{entry['id']}-paraphrase"]
            self.assertEqual(case["expect"]["constraint_ids"], [entry["id"]])
            self.assertFalse(any(cue.rstrip("?").lower() in case["message"].lower() for cue in entry["clarification_cues"]))

    def test_every_case_passes_its_checks_with_the_scripted_provider(self):
        results = interviewer_eval.run(interviewer_eval.scripted_provider, list(self.cases.values()), self.item, SETTINGS)
        self.assertTrue(results["passed"], results["summary"])
        self.assertEqual(set(results["summary"]), {
            "selector_offers_what_is_hidden", "selector_sees_cues_only", "selector_valid", "selector_matches",
            "reply_sees_only_what_it_may", "reply_carries_what_was_earned", "reply_valid",
            "reply_reveals_nothing_unearned", "reply_shares_no_reference_reasoning"})
        self.assertEqual(results["summary"]["selector_matches"], {"passed": len(self.cases), "of": len(self.cases)})
        self.assertTrue(all(call["seconds"] >= 0 for case in results["cases"] for call in case["calls"]))
        self.assertGreater(results["tokens"]["input_tokens"], 0)

    def test_the_checks_catch_a_wrong_selection_a_leak_and_copied_reasoning(self):
        expect = self.cases["unrelated"]["expect"]
        storage = next(entry["fact"] for entry in self.item["content"]["facilitator"]["hidden_constraints"]
                       if entry["id"] == "storage")
        reference = evaluator_view(self.item)["reference_reasoning"][1]
        wrong = self.checks("unrelated", FakeProvider(selections=[{"constraint_ids": ["storage"], "hint_requested": False}],
                                                      replies=["Fine."]))
        self.assertFalse(wrong["selector_matches"])
        self.assertFalse(self.checks("unrelated", FakeProvider(selections=[{"constraint_ids": ["nope"]}]))["selector_valid"])
        leaky = self.checks("unrelated", FakeProvider(selections=[expect], replies=[f"Remember: {storage}"]))
        self.assertFalse(leaky["reply_reveals_nothing_unearned"])
        number_only = self.checks("unrelated", FakeProvider(selections=[expect], replies=["Plan for 2,000 a second."]))
        self.assertFalse(number_only["reply_reveals_nothing_unearned"])
        copying = self.checks("unrelated", FakeProvider(selections=[expect], replies=[reference]))
        self.assertFalse(copying["reply_shares_no_reference_reasoning"])
        self.assertFalse(self.checks("unrelated", FakeProvider(selections=[expect], replies=[""]))["reply_valid"])

    def test_the_request_checks_catch_a_builder_that_shares_too_much(self):
        real = interviewer.facilitator

        def everything(item, context, selection):
            return real(item, context, {"constraint_ids": [entry["id"] for entry in context["selector"]["hidden"]],
                                        "hint_requested": False})
        with patch.object(interviewer, "facilitator", everything):
            self.assertFalse(self.checks("unrelated", interviewer_eval.scripted_provider(self.cases["unrelated"]))
                             ["reply_sees_only_what_it_may"])
        real_selector = interviewer.selector_request

        def with_facts(context, settings):
            body = real_selector(context, settings)
            material = json.loads(body["input"])
            material["notes"] = [entry["fact"] for entry in self.item["content"]["facilitator"]["hidden_constraints"]]
            body["input"] = json.dumps(material, ensure_ascii=False)
            return body
        with patch.object(interviewer, "selector_request", with_facts):
            self.assertFalse(self.checks("unrelated", interviewer_eval.scripted_provider(self.cases["unrelated"]))
                             ["selector_sees_cues_only"])

    def test_the_checks_catch_a_reply_missing_what_was_earned(self):
        real_facilitator, real_reply = interviewer.facilitator, interviewer.reply_request

        def nothing_new(item, context, selection):
            return real_facilitator(item, context, {"constraint_ids": [], "hint_requested": selection["hint_requested"]})

        def no_hint(item, context, selection):
            return real_facilitator(item, context, dict(selection, hint_requested=False))

        def forgetting(context, facilitator, settings):
            return real_reply(context, dict(facilitator, revealed=[]), settings)
        for case_id, name, replacement in (("scope-paraphrase", "facilitator", nothing_new),
                                           ("hint-request", "facilitator", no_hint),
                                           ("already-revealed", "reply_request", forgetting)):
            with self.subTest(case=case_id), patch.object(interviewer, name, replacement):
                checks = self.checks(case_id, interviewer_eval.scripted_provider(self.cases[case_id]))
                self.assertFalse(checks["reply_carries_what_was_earned"])

    def test_the_checks_catch_a_selector_offered_what_was_already_revealed(self):
        def everything(context, settings):
            hidden = [{"id": entry["id"], "cues": entry["clarification_cues"]}
                      for entry in self.item["content"]["facilitator"]["hidden_constraints"]]
            return real(dict(context, selector=dict(context["selector"], hidden=hidden)), settings)
        real = interviewer.selector_request
        with patch.object(interviewer, "selector_request", everything):
            checks = self.checks("already-revealed", interviewer_eval.scripted_provider(self.cases["already-revealed"]))
        self.assertFalse(checks["selector_offers_what_is_hidden"])

    def test_the_leak_checks_read_text_as_the_model_does(self):
        item = json.loads(json.dumps(self.item))
        storage = next(entry for entry in item["content"]["facilitator"]["hidden_constraints"] if entry["id"] == "storage")
        storage["fact"] = 'Peak load is "2,000 attempts"\nper second, across tenants.'
        real = interviewer.reply_request

        def leaking(context, facilitator, settings):
            body = real(context, facilitator, settings)
            material = json.loads(body["input"])
            material["notes"] = storage["fact"]
            body["input"] = json.dumps(material, ensure_ascii=False)
            return body
        with patch.object(interviewer, "reply_request", leaking):
            checks = interviewer_eval.run_case(interviewer_eval.scripted_provider(self.cases["unrelated"]), item,
                                               self.cases["unrelated"], SETTINGS, profile_version="interviewer-1")["checks"]
        self.assertFalse(checks["reply_sees_only_what_it_may"])
        for reply in ("We expect 2000 attempts.", "Peak is 2,000, at the busiest hour."):
            with self.subTest(reply=reply):
                provider = FakeProvider(selections=[self.cases["unrelated"]["expect"]], replies=[reply])
                self.assertFalse(self.checks("unrelated", provider)["reply_reveals_nothing_unearned"])

    def test_the_command_runs_the_cases_and_can_write_its_results(self):
        app = create_app({"TESTING": True, "SECRET_KEY": "fixture", "SQLALCHEMY_DATABASE_URI": "sqlite://"})
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "results.json"
            result = app.test_cli_runner().invoke(args=["learning-eval", "--case", "hint-request", "--output", str(output)])
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("selector_matches: 1 of 1", result.output)
            saved = json.loads(output.read_text())
            self.assertEqual(([case["id"] for case in saved["cases"]], saved["passed"]), (["hint-request"], True))
            self.assertEqual(saved["cases"][0]["selection"], {"constraint_ids": [], "hint_requested": True})
        typo = app.test_cli_runner().invoke(args=["learning-eval", "--case", "no-such-case"])
        self.assertNotEqual(typo.exit_code, 0)
        self.assertIn("No such case: no-such-case", typo.output)
        with patch.dict(os.environ):
            os.environ.pop("LEARNING_OPENAI_API_KEY", None)
            refused = app.test_cli_runner().invoke(args=["learning-eval", "--provider", "openai"])
        self.assertNotEqual(refused.exit_code, 0)  # no key, so nothing is called or written
        self.assertIn("LEARNING_OPENAI_API_KEY", refused.output)


if __name__ == "__main__":
    unittest.main()
