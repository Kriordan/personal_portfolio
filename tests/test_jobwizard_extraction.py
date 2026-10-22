"""Offline tests of source selection and rejection, independent of Flask/DB."""
import importlib.util
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("extraction", Path(__file__).resolve().parents[1] / "project/jobwizard/extraction.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
URL = "https://jobs.ashbyhq.com/example/01234567-0123-0123-0123-012345678901"


def fixture():
    job = {"@type": "JobPosting", "title": "Engineer", "hiringOrganization": {"name": "Example Labs"}}
    return {"final_url": URL, "heading": "Engineer", "page_title": "Engineer @ Example Labs",
            "header_text": "Engineer. Remote within Canada only. Full time.", "company_candidates": [],
            "description": "Example Labs builds data tools.\nA degree or equivalent experience is accepted.\nNo visa sponsorship is available.\nPython is required; Rust is preferred.\nPay is CAD 100,000–150,000 per year.",
            "jsonld": [json.dumps(job)]}


class ExtractionTests(unittest.TestCase):
    def test_array_graph_parsing_and_direct_title_company(self):
        raw = fixture()
        raw["jsonld"] = [json.dumps({"@graph": [json.loads(raw["jsonld"][0])]})]
        source = module.normalize_source(raw, URL, "ashby")
        self.assertEqual(source["fields"]["title"]["value"], "Engineer")
        self.assertEqual(source["fields"]["company_name"]["value"], "Example Labs")
        self.assertTrue(any("No visa sponsorship" in b["text"] for b in source["blocks"]))

    def test_malformed_metadata_does_not_destroy_visible_source(self):
        raw = fixture(); raw["jsonld"] = ["{broken"]
        source = module.normalize_source(raw, URL, "ashby")
        self.assertIsNone(source["fields"]["company_name"])
        self.assertIn("malformed_structured_data", source["warnings"])
        self.assertEqual(source["fields"]["title"]["value"], "Engineer")

    def test_ambiguous_postings_do_not_pick_first_employer(self):
        raw = fixture()
        other = json.loads(raw["jsonld"][0]); other["hiringOrganization"]["name"] = "Another Employer"
        raw["jsonld"].append(json.dumps(other))
        source = module.normalize_source(raw, URL, "ashby")
        self.assertIn("ambiguous_structured_posting", source["warnings"])
        self.assertIsNone(source["fields"]["company_name"])

    def test_unmatched_posting_never_overrides_visible_title(self):
        raw = fixture(); raw["heading"] = "Different Engineer"
        source = module.normalize_source(raw, URL, "ashby")
        self.assertEqual(source["fields"]["title"]["value"], "Different Engineer")
        self.assertIsNone(source["fields"]["company_name"])

    def test_confidential_employer_preserved(self):
        raw = fixture(); raw["description"] = raw["description"].replace("Example Labs", "Confidential employer")
        raw["jsonld"] = [raw["jsonld"][0].replace("Example Labs", "Confidential employer")]
        self.assertEqual(module.normalize_source(raw, URL, "ashby")["fields"]["company_name"]["value"], "Confidential employer")

    def test_bounds_redirect_and_error_fail_before_summary(self):
        for key, value in [("description", "x" * 80001), ("final_url", URL + "/different"), ("error", "page_expired"), ("description", "short")]:
            raw = fixture(); raw[key] = value
            with self.assertRaises(module.ExtractionError):
                module.normalize_source(raw, URL, "ashby")

    def test_long_paragraph_preserves_tail_without_exceeding_block_limit(self):
        raw = fixture(); raw["description"] += " detail" * 900 + " FINAL restriction."
        source = module.normalize_source(raw, URL, "ashby")
        self.assertTrue(any("FINAL restriction." in b["text"] for b in source["blocks"]))
        self.assertTrue(all(len(b["text"]) <= 400 for b in source["blocks"]))

    def test_summary_uses_server_excerpts_and_rejects_wrong_ids_and_new_numbers(self):
        source = module.normalize_source(fixture(), URL, "ashby")
        pay = next(b for b in source["blocks"] if "CAD 100" in b["text"])
        bullet = {"category": "compensation", "text": "CAD 100,000–150,000 per year.", "evidence": [pay["id"]]}
        value = {"bullets": [bullet], "more_details": False, "conflicts": []}
        self.assertEqual(len(module.validate_summary(value, source)["bullets"]), 1)
        self.assertEqual(module.validate_summary(value, source)["bullets"][0]["evidence"], [{"block_id": pay["id"], "quote": pay["text"]}])
        for bad in [dict(bullet, text="CAD 500,000 per year."), dict(bullet, evidence=["s999"]), dict(bullet, evidence=[{"block_id": pay["id"], "quote": "invented evidence"}])]:
            result = module.validate_summary(dict(value, bullets=[bad]), source)
            self.assertEqual(result["bullets"], [])
            self.assertTrue(result["more_details"])

    def test_invalid_schema_is_rejected(self):
        source = module.normalize_source(fixture(), URL, "ashby")
        for value in [None, {}, {"bullets": [], "more_details": "false", "conflicts": []}, {"bullets": [{}] * 9, "more_details": False, "conflicts": []}]:
            with self.assertRaises(module.ExtractionError):
                module.validate_summary(value, source)

    def test_omitted_material_constraint_forces_review_warning(self):
        source = module.normalize_source(fixture(), URL, "ashby")
        result = module.validate_summary({"bullets": [], "more_details": False, "conflicts": []}, source)
        self.assertTrue(result["coverage_warning"])
        self.assertTrue(result["more_details"])

    def test_multiple_location_pay_ranges_require_details_review(self):
        raw = fixture(); raw["header_text"] = "Pay: London $100–$200; New York $120–$250; Seattle $110–$240."
        source = module.normalize_source(raw, URL, "ashby")
        result = module.validate_summary({"bullets": [], "more_details": False, "conflicts": []}, source)
        self.assertTrue(result["detailed_pay_scales"])
        self.assertTrue(result["more_details"])

    def test_request_has_no_tools_or_state_and_only_normalized_public_blocks(self):
        raw = fixture(); raw["private_notes"] = "must never be sent"
        source = module.normalize_source(raw, URL, "ashby")
        request = module.summary_request(source)
        self.assertFalse(request["store"])
        self.assertNotIn("tools", request)
        self.assertNotIn("must never be sent", request["input"])
        self.assertTrue(request["text"]["format"]["strict"])


if __name__ == "__main__":
    unittest.main()
