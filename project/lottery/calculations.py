"""Deterministic calculations, independent of HTTP, Flask and the database."""
import math
from datetime import datetime, timedelta, timezone

PRICES = (10, 20, 30, 50)
TARGETS = (500, 1000, 10000, 100000, 1000000)
MODEL_VERSION = 1


def utc(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def is_stale(source_at, checked_at, now=None):
    now = now or datetime.now(timezone.utc)
    return any(now - utc(t) > timedelta(hours=48) for t in (source_at, checked_at))


def money(value):
    return "Unverified" if value is None else f"${value:,.0f}"


def odds(probability):
    if probability is None:
        return "Unavailable"
    if probability <= 0:
        return "No qualifying prizes"
    # Two significant digits avoid suggesting precision the depletion model lacks.
    denominator = float(f"{1 / probability:.2g}")
    return f"1 in {denominator:,.0f}" if denominator >= 10 else f"1 in {denominator:.1f}"


def calculate(game, target):
    result = dict(game, launch_probability=None, probability=None, per_dollar=None,
                  qualifying_remaining=0, top_remaining=None, reason=game.get("issue"))
    tiers = game.get("tiers", [])
    if tiers:
        result["top_remaining"] = tiers[0].get("remaining", 0)
    if result["reason"]:
        return result
    if game.get("status") != "active":
        result["reason"] = "Game ended"
        return result
    if game.get("price") not in PRICES or not tiers:
        result["reason"] = "Awaiting verified game details"
        return result
    if any(t.get("amount") is None for t in tiers):
        result["reason"] = "Prize value needs verification"
        return result
    try:
        for t in tiers:
            if (type(t["original"]) is not int or type(t["remaining"]) is not int
                    or t["original"] <= 0 or not 0 <= t["remaining"] <= t["original"]
                    or not math.isfinite(t["launch_probability"])
                    or not 0 < t["launch_probability"] <= 1):
                raise ValueError()
        if sum(t["launch_probability"] for t in tiers) > 1.00001:
            raise ValueError()
        qualifying = [t for t in tiers if t["amount"] >= target]
        result["launch_probability"] = sum(t["launch_probability"] for t in qualifying)
        result["qualifying_remaining"] = sum(t["remaining"] for t in qualifying)
        low = [t for t in tiers if t["amount"] < 1000]
        original_low = sum(t["original"] for t in low)
        retention = sum(t["remaining"] for t in low) / original_low
        if not 0 < retention <= 1:
            raise ValueError()
        probability = sum(t["launch_probability"] * t["remaining"] / t["original"]
                          for t in qualifying) / retention
        if not math.isfinite(probability) or not 0 <= probability <= 1:
            raise ValueError()
        result.update(probability=probability, per_dollar=probability / game["price"], retention=retention)
        if not result["qualifying_remaining"]:
            result["reason"] = "No qualifying prizes unclaimed"
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        result.update(reason="Probability inputs need verification", probability=None, per_dollar=None)
    return result


def rank(games, target, basis="ticket"):
    results = [calculate(game, target) for game in games]
    metric = "per_dollar" if basis == "dollar" else "probability"
    return sorted(results, key=lambda g: (bool(g["reason"]), -(g.get(metric) or 0),
                                         g.get("price") or 1000, int(g["game_number"])))
