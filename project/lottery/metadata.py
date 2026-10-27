"""Strict, reviewable import format for manually verified NY facts."""
import math
from datetime import date
from urllib.parse import urlparse

from .calculations import PRICES, utc


def validate_metadata(document):
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise ValueError("Expected schema_version 1")
    games = document.get("games")
    if not isinstance(games, list) or not games:
        raise ValueError("Expected a nonempty games list")
    numbers = set()
    for g in games:
        number = g.get("game_number", "")
        if not isinstance(number, str) or not number.isdigit() or number in numbers:
            raise ValueError("Game numbers must be unique numeric strings")
        numbers.add(number)
        if g.get("price") not in PRICES or g.get("status") not in ("active", "ended") or not g.get("name"):
            raise ValueError(f"{number}: price, status and name required")
        utc(g["verified_at"])
        for key in ("start_date", "end_date"):
            if g.get(key):
                date.fromisoformat(g[key])
        for url in [g.get("url", ""), *g.get("provenance", [])]:
            if urlparse(url).scheme != "https" or urlparse(url).hostname not in ("nylottery.ny.gov", "edit.nylottery.ny.gov", "data.ny.gov"):
                raise ValueError(f"{number}: official HTTPS provenance required")
        if not g.get("provenance") or not g.get("tiers"):
            raise ValueError(f"{number}: provenance and tiers required")
        labels = set()
        for t in g["tiers"]:
            source = t.get("source_label")
            if not source or source in labels or not t.get("label"):
                raise ValueError(f"{number}: unique source labels required")
            labels.add(source)
            if type(t.get("original")) is not int or t["original"] <= 0:
                raise ValueError(f"{number}: positive original counts required")
            odds = t.get("odds_denominator")
            if type(odds) not in (int, float) or not math.isfinite(odds) or odds < 1:
                raise ValueError(f"{number}: published tier odds required")
            if t.get("amount") is None:
                if not g.get("issue"):
                    raise ValueError(f"{number}: unresolved amounts require an issue")
            elif type(t["amount"]) is not int or t["amount"] <= 0:
                raise ValueError(f"{number}: gross prize must be a positive integer")
        if sum(1 / t["odds_denominator"] for t in g["tiers"]) > 1:
            raise ValueError(f"{number}: impossible tier probabilities")
    return games
