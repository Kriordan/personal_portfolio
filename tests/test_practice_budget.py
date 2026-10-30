"""Learning AI prices: what a call costs, the most it can cost, and which usage reports are trusted.

Pure arithmetic, without a database. Rates are micro-dollars per million tokens, so a rate of
1,000,000 is one micro-dollar a token.
"""
import unittest
from unittest.mock import patch

from project.services import practice_budget as budget

RATES = {"input": 1_000_000, "cached_input": 100_000, "cache_write": 1_250_000, "output": 4_000_000,
         "long_context": {"above_input_tokens": 1_000, "input": 2_000_000, "cached_input": 200_000,
                          "cache_write": 2_500_000, "output": 6_000_000}}
RATE_KEYS = {"input", "cached_input", "cache_write", "output"}


class CostTests(unittest.TestCase):
    def test_input_is_billed_as_cached_reads_cache_writes_and_the_rest(self):
        # 100 input tokens: 40 cached reads, 50 writes, and 10 ordinary; then 20 output tokens.
        # 10 x 1 + 40 x 0.1 + 50 x 1.25 + 20 x 4 = 156.5 micro-dollars, rounded up.
        self.assertEqual(budget.cost(RATES, input_tokens=100, cached_input_tokens=40, cache_write_tokens=50,
                                     output_tokens=20), 157)
        self.assertEqual(budget.cost(RATES, input_tokens=100, output_tokens=20), 180)
        self.assertEqual(budget.cost(RATES, input_tokens=0, cached_input_tokens=0, output_tokens=0), 0)
        self.assertEqual(budget.cost(RATES, input_tokens=1, cached_input_tokens=1, output_tokens=0), 1)  # 0.1, rounded up

    def test_long_context_rates_apply_above_the_threshold_to_the_whole_request(self):
        self.assertEqual(budget.cost(RATES, input_tokens=1_000, output_tokens=10), 1_000 + 40)
        self.assertEqual(budget.cost(RATES, input_tokens=1_001, output_tokens=10), 2_002 + 60)
        self.assertEqual(budget.cost(RATES, input_tokens=1_001, cache_write_tokens=1_001, output_tokens=0),
                         2_503)  # 2,502.5, rounded up

    def test_a_table_without_cache_rates_bills_reads_and_writes_as_input(self):
        plain = {"input": 1_000_000, "output": 4_000_000}
        self.assertEqual(budget.cost(plain, input_tokens=10, cached_input_tokens=3, cache_write_tokens=5,
                                     output_tokens=1), 10 + 4)


class WorstCaseTests(unittest.TestCase):
    def worst(self, rates, input_bytes, max_output_tokens=20):
        with patch.dict(budget.PRICES, {("test-model", "default"): rates}):
            return budget.worst_case("openai", "test-model", "default", input_bytes=input_bytes,
                                     max_output_tokens=max_output_tokens)

    def test_every_input_byte_is_priced_as_a_cache_write(self):
        self.assertEqual(self.worst(RATES, 100), 125 + 80)
        self.assertEqual(self.worst(RATES, 2_000), 5_000 + 120)  # past the long-context threshold

    def test_no_split_of_the_input_costs_more_than_the_worst_case(self):
        for rates in (RATES, {**RATES, "cache_write": 900_000}, {"input": 1_000_000, "output": 4_000_000}):
            worst = self.worst(rates, 100)
            for cached in range(0, 101, 25):
                for written in range(0, 101 - cached, 25):
                    with self.subTest(rates=rates, cached=cached, written=written):
                        self.assertLessEqual(budget.cost(rates, input_tokens=100, cached_input_tokens=cached,
                                                         cache_write_tokens=written, output_tokens=20), worst)

    def test_an_unpriced_model_has_no_worst_case(self):
        self.assertIsNone(budget.worst_case("openai", "unpriced-model", "default", input_bytes=1, max_output_tokens=1))


class UsageTests(unittest.TestCase):
    def test_cached_reads_and_writes_are_optional_parts_of_the_input(self):
        self.assertEqual(budget._tokens({"input_tokens": 9, "output_tokens": 2}),
                         {"input_tokens": 9, "cached_input_tokens": 0, "cache_write_tokens": 0, "output_tokens": 2})
        usage = {"input_tokens": 9, "cached_input_tokens": 3, "cache_write_tokens": 6, "output_tokens": 2}
        self.assertEqual(budget._tokens(usage), usage)

    def test_usage_that_does_not_add_up_is_not_trusted(self):
        for usage in ({"input_tokens": 9, "cached_input_tokens": 4, "cache_write_tokens": 6, "output_tokens": 2},
                      {"input_tokens": 9, "cache_write_tokens": -1, "output_tokens": 2},
                      {"input_tokens": 9, "cache_write_tokens": True, "output_tokens": 2},
                      {"input_tokens": 9, "cache_write_tokens": 1.0, "output_tokens": 2},
                      {"input_tokens": 9}, None, []):
            with self.subTest(usage=usage):
                self.assertIsNone(budget._tokens(usage))


class PriceTableTests(unittest.TestCase):
    def test_every_price_has_each_rate_and_writes_cost_at_least_input(self):
        self.assertTrue(budget.PRICES)
        for key, rates in budget.PRICES.items():
            with self.subTest(price=key):
                tiers = [rates, rates["long_context"]] if "long_context" in rates else [rates]
                for tier in tiers:
                    self.assertTrue(RATE_KEYS <= set(tier))
                    self.assertTrue(all(type(tier[name]) is int and tier[name] > 0 for name in RATE_KEYS))
                    self.assertLessEqual(tier["cached_input"], tier["input"])
                    self.assertGreaterEqual(tier["cache_write"], tier["input"])
                if "long_context" in rates:
                    self.assertEqual(set(rates["long_context"]), RATE_KEYS | {"above_input_tokens"})
                    self.assertTrue(all(rates["long_context"][name] >= rates[name] for name in RATE_KEYS))


if __name__ == "__main__":
    unittest.main()
