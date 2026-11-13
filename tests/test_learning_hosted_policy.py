"""Strict approval parsing and bounded runtime configuration; no network calls."""
from copy import deepcopy
import unittest

from project.learning import hosted_pilot as hosted
from tests.hosted_pilot_fixtures import approval, environment


class HostedPolicyTests(unittest.TestCase):
    def test_default_off_and_approved_modes_pin_owner_content_and_caps(self):
        self.assertEqual(hosted.settings({}), {"LEARNING_HOSTED_PILOT": False})
        for mode, enabled, cap in (("off", False, 5), ("verification", True, 1), ("pilot", True, 5)):
            with self.subTest(mode=mode):
                saved = hosted.settings(environment(mode=mode, LEARNING_AI_MONTHLY_CAP_USD="500",
                    LEARNING_AI_TOTAL_CAP_USD="500", LEARNING_AI_MODEL="unreviewed", LEARNING_AI_PROVIDER="fake"))
                self.assertEqual(saved["LEARNING_AI_ENABLED"], enabled)
                self.assertEqual(saved["LEARNING_AI_TOTAL_CAP_USD"], cap)
                self.assertEqual(saved["LEARNING_AI_MONTHLY_CAP_USD"], 50)
                self.assertEqual(saved["LEARNING_AI_MODEL"], "gpt-6.1-sol")
                self.assertEqual(saved["LEARNING_AI_PROVIDER"], "openai")
                self.assertEqual(saved["LEARNING_HOSTED_OWNER_ID"], 1)
                self.assertTrue(saved["SESSION_COOKIE_SECURE"])
                self.assertTrue(saved["REMEMBER_COOKIE_SECURE"])
                self.assertEqual(saved["LEARNING_AI_CONTEXT_BYTES"], 524_288)

    def test_incomplete_or_tampered_approvals_and_modes_fail_closed(self):
        valid = approval()
        mutations = [dict(total_microusd=5_000_001), dict(verification_microusd=1_000_001),
            dict(owner_id=True), dict(owner_email="invalid"), dict(target_app="another-app"),
            dict(frozen_at="2099-01-01T00:00:00+00:00"), dict(frozen_at="2026-11-01"),
            dict(source_instance_id="missing"), dict(source_ledger_sha256="z" * 64), dict(format_version=True),
            dict(carryover_microusd=True), dict(carryover_by_period={"2026-13": 37_859}),
            dict(carryover_by_period={"2026-11": 37_858}), dict(extra="ignored"), dict(draft_revisions=[])]
        altered = deepcopy(valid["draft_revisions"])
        altered[0][2] = "b" * 64
        mutations.append(dict(draft_revisions=altered))
        for change in mutations:
            with self.subTest(change=change), self.assertRaises(hosted.PilotPolicyError):
                hosted.load_approval(hosted.canonical(valid | change))
        for raw in (None, "{}", "not-json", "{" + '"format_version":1,' * 2 + '"x":1}', " " * 16_385):
            with self.subTest(raw=str(raw)[:30]), self.assertRaises(hosted.PilotPolicyError):
                hosted.load_approval(raw)
        for changes in ({"LEARNING_HOSTED_PILOT": "true"}, {"LEARNING_HOSTED_AI_MODE": "yes"},
                        {hosted.APPROVAL_VARIABLE: ""}):
            with self.subTest(changes=changes), self.assertRaises(hosted.PilotPolicyError):
                hosted.settings(environment(**changes))

    def test_smaller_caps_are_preserved_and_invalid_values_never_create_an_unlimited_budget(self):
        for name in ("LEARNING_AI_MONTHLY_CAP_USD", "LEARNING_AI_TOTAL_CAP_USD", "LEARNING_AI_WARN_USD"):
            for value in ("NaN", "Infinity", "-1", "0.0000001", "invalid"):
                with self.subTest(name=name, value=value), self.assertRaises(hosted.PilotPolicyError):
                    hosted.settings(environment(**{name: value}))
        saved = hosted.settings(environment(mode="pilot", LEARNING_AI_MONTHLY_CAP_USD="0.123456",
                                             LEARNING_AI_TOTAL_CAP_USD="0"))
        self.assertEqual(saved["LEARNING_AI_MONTHLY_CAP_USD"], 0.123456)
        self.assertEqual(saved["LEARNING_AI_TOTAL_CAP_USD"], 0)
        self.assertLessEqual(saved["LEARNING_AI_WARN_USD"], 0.123456)

    def test_carryover_keeps_total_across_months_and_never_applies_outside_hosted_mode(self):
        saved = hosted.settings(environment())
        self.assertEqual(hosted.carried_spending(saved), 37_859)
        self.assertEqual(hosted.carried_spending(saved, "2026-11"), 37_859)
        self.assertEqual(hosted.carried_spending(saved, "2026-12"), 0)
        self.assertEqual(hosted.carried_spending(saved | {"LEARNING_HOSTED_PILOT": False}), 0)
        with self.assertRaises(hosted.PilotPolicyError):
            hosted.carried_spending({"LEARNING_HOSTED_PILOT": True})
