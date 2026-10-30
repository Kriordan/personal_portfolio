"""Learning AI spending: worst-case reservations, settlement, and a monthly cap.

The ledger (`LearningAICharge`) is content-free and outlives practice deletion. A month's
committed spend is every settled cost plus every unsettled reservation, including
uncertain ones: a call whose outcome is unknown may still have been charged.

Callers own the transaction. `reserve` takes the budget lock, so reservations are
serialized; take it after the request and session rows (lock order: owner, request,
session, budget, charge).
"""
from __future__ import annotations

from datetime import timezone

from flask import current_app
from sqlalchemy import case, func, select, text

from project.database import db
from project.models import LearningAICharge

# Verified provider prices in micro-dollars per million tokens, keyed by (model, service tier).
# An unpriced model gets no AI. Input tokens are billed at one of three rates: cached reads
# ("cached_input"), writes to the prompt cache ("cache_write", for the default 30-minute
# lifetime), and the rest ("input"). An entry may add "long_context": {"above_input_tokens": n,
# ...the same rates...}.
# These are OpenAI's published standard prices for the evaluation candidates, checked October 29, 2026.
# Long-context rates apply above 272K input tokens, read here as 272,000, the lower reading.
PRICING_VERSION = "openai-2026-10-29"
PRICES: dict = {
    ("gpt-6-astra", "default"): {"input": 10_000_000, "cached_input": 1_000_000, "cache_write": 12_500_000,
                                 "output": 50_000_000,
                                 "long_context": {"above_input_tokens": 272_000, "input": 20_000_000,
                                                  "cached_input": 2_000_000, "cache_write": 25_000_000,
                                                  "output": 75_000_000}},
    ("gpt-6.1-sol", "default"): {"input": 2_000_000, "cached_input": 100_000, "cache_write": 2_500_000,
                                 "output": 10_000_000,
                                 "long_context": {"above_input_tokens": 272_000, "input": 4_000_000,
                                                  "cached_input": 200_000, "cache_write": 5_000_000,
                                                  "output": 15_000_000}},
    ("gpt-6.1-terra", "default"): {"input": 1_000_000, "cached_input": 50_000, "cache_write": 1_250_000,
                                   "output": 5_000_000,
                                   "long_context": {"above_input_tokens": 272_000, "input": 2_000_000,
                                                    "cached_input": 100_000, "cache_write": 2_500_000,
                                                    "output": 7_500_000}},
}
# The scripted fake provider has its own prices, so budgets can be exercised without a paid call.
FAKE_PRICING_VERSION = "fake-1"
FAKE_PRICES = {("fake-interviewer", "default"): {"input": 2_000_000, "cached_input": 200_000, "output": 8_000_000}}
# The curriculum importer uses (1427870284, 1).
BUDGET_LOCK = (1427870284, 2)


class BudgetExhausted(Exception):
    """The call could take the month past its cap, or its model has no price. Nothing was reserved."""

    def __init__(self, code="budget"):
        super().__init__(code)
        self.code = code


def _rates(provider, model, tier):
    table, version = (FAKE_PRICES, FAKE_PRICING_VERSION) if provider == "fake" else (PRICES, PRICING_VERSION)
    rates = table.get((model, tier))
    return (rates, version) if rates else (None, None)


def priced(provider, model, tier):
    return _rates(provider, model, tier)[0] is not None


def cost(rates, *, input_tokens, output_tokens, cached_input_tokens=0, cache_write_tokens=0):
    """Micro-dollars, rounded up. A long-context tier applies above its input threshold.

    Cached reads and cache writes are parts of `input_tokens`, each billed at its own rate.
    """
    long_context = rates.get("long_context")
    if long_context and input_tokens > long_context["above_input_tokens"]:
        rates = long_context
    uncached = max(input_tokens - cached_input_tokens - cache_write_tokens, 0)
    total = (uncached * rates["input"] + cached_input_tokens * rates.get("cached_input", rates["input"])
             + cache_write_tokens * rates.get("cache_write", rates["input"]) + output_tokens * rates["output"])
    return -(-total // 1_000_000)


def _dollars(name, default):
    return round(float(current_app.config.get(name, default)) * 1_000_000)


def cap_microusd():
    return _dollars("LEARNING_AI_MONTHLY_CAP_USD", 50)


def warn_microusd():
    return _dollars("LEARNING_AI_WARN_USD", 40)


def period(now):
    return now.astimezone(timezone.utc).strftime("%Y-%m")


def committed(period_name):
    """Settled cost plus every unsettled reservation in the month, in micro-dollars."""
    amount = case((LearningAICharge.state == "settled", LearningAICharge.cost_microusd),
                  else_=LearningAICharge.reserved_microusd)
    # PostgreSQL sums bigint as numeric, which would reach JSON as a string.
    return int(db.session.scalar(select(func.coalesce(func.sum(amount), 0)).where(
        LearningAICharge.period == period_name, LearningAICharge.state != "released")) or 0)


def month_status(now, *, smallest_microusd=0):
    """The month's spending. `exhausted` once not even the smallest possible call would fit.

    Reservations never take the month past its cap, so spending alone rarely reaches it.
    """
    spent, cap, warn = committed(period(now)), cap_microusd(), warn_microusd()
    return {"spent_microusd": spent, "cap_microusd": cap, "warn_microusd": warn,
            "warning": spent >= warn, "exhausted": spent + smallest_microusd >= cap}


def worst_case(provider, model, tier, *, input_bytes, max_output_tokens):
    """The most one call can cost, in micro-dollars, or None for an unpriced model.

    Every token is at least one byte, so the request body's UTF-8 size bounds its input tokens.
    Any input token may be a cache write, which costs more than ordinary input.
    """
    rates, _ = _rates(provider, model, tier)
    if rates is None:
        return None
    return max(cost(rates, input_tokens=input_bytes, output_tokens=max_output_tokens),
               cost(rates, input_tokens=input_bytes, cache_write_tokens=input_bytes, output_tokens=max_output_tokens))


def fits(amount, now):
    """Whether `amount` more fits under the cap now. Only `reserve`, under the budget lock, is binding."""
    return committed(period(now)) + amount <= cap_microusd()


def _lock():
    if db.session.get_bind().dialect.name != "sqlite":
        db.session.execute(text("SELECT pg_advisory_xact_lock(:space, :key)"),
                           {"space": BUDGET_LOCK[0], "key": BUDGET_LOCK[1]})
    # On SQLite the caller's earlier write already holds the database's single write lock.


def reserve(*, user_id, reply_id, purpose, provider, model, tier, input_bytes, max_output_tokens, expires_at, now):
    """Reserve the most one call can cost (`worst_case`), or raise BudgetExhausted. Returns the charge ID."""
    _, version = _rates(provider, model, tier)
    amount = worst_case(provider, model, tier, input_bytes=input_bytes, max_output_tokens=max_output_tokens)
    if amount is None:
        raise BudgetExhausted("unpriced")
    _lock()
    if not fits(amount, now):
        raise BudgetExhausted("budget")
    charge = LearningAICharge(user_id=user_id, reply_id=reply_id, purpose=purpose, period=period(now),
                              provider=provider, model=model, service_tier=tier, pricing_version=version,
                              state="reserved", reserved_microusd=amount, expires_at=expires_at, created_at=now)
    db.session.add(charge)
    db.session.flush()
    return charge.id


def _tokens(usage):
    """Token counts from a provider's usage report, or None when they can't be trusted."""
    if not isinstance(usage, dict):
        return None
    optional = ("cached_input_tokens", "cache_write_tokens")
    values = {key: usage.get(key, 0 if key in optional else None)
              for key in ("input_tokens", *optional, "output_tokens")}
    if not all(type(value) is int and value >= 0 for value in values.values()):
        return None
    if values["cached_input_tokens"] + values["cache_write_tokens"] > values["input_tokens"]:
        return None
    return values


def settle(charge_id, *, usage, now):
    """Record what the call cost. Without trustworthy usage, the reservation stands as the cost."""
    charge = db.session.get(LearningAICharge, charge_id, populate_existing=True)
    rates, _ = _rates(charge.provider, charge.model, charge.service_tier)
    tokens = _tokens(usage)
    if tokens is None or rates is None:
        charge.cost_microusd = charge.reserved_microusd
    else:
        charge.cost_microusd = cost(rates, **tokens)
        charge.input_tokens = tokens["input_tokens"]
        charge.cached_input_tokens = tokens["cached_input_tokens"]
        charge.cache_write_tokens = tokens["cache_write_tokens"]
        charge.output_tokens = tokens["output_tokens"]
    charge.state, charge.settled_at = "settled", now


def release(charge_id, *, now):
    """The provider refused the call before doing paid work (for example 400, 401, 403, or 429)."""
    charge = db.session.get(LearningAICharge, charge_id, populate_existing=True)
    charge.state, charge.cost_microusd, charge.settled_at = "released", 0, now
