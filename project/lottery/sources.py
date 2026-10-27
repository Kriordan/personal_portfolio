"""Read public lottery documents. No lottery HTTP is used by page views."""
import json
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import requests

from .calculations import PRICES

NY_FEED = "https://data.ny.gov/resource/nzqa-7unk.json?$limit=5000"
NY_INFO = "https://data.ny.gov/api/views/nzqa-7unk.json"
NY_COUNT = "https://data.ny.gov/resource/nzqa-7unk.json?$select=count(*)"
CT_CATALOG = "https://ctlottery.com/games/scratch-games"
EASTERN = ZoneInfo("America/New_York")


class SourceError(ValueError):
    """A safe, user-visible failure; never includes a response body."""


class PublicClient:
    def __init__(self, session=None, sleep=time.sleep, clock=time.monotonic):
        self.session = session or requests.Session()
        self.sleep, self.clock = sleep, clock
        self.last_ct = None
        self.count = 0
        self.blocked = set()

    def get(self, url):
        host = urlparse(url).hostname
        if host not in {"ctlottery.com", "data.ny.gov"} or urlparse(url).scheme != "https":
            raise SourceError("Unapproved source URL")
        if host in self.blocked:
            raise SourceError("Source blocked this refresh; waiting until the next run")
        for attempt in range(3):
            if host == "ctlottery.com" and self.last_ct is not None:
                self.sleep(max(0, 2 - (self.clock() - self.last_ct)))
            if host == "ctlottery.com":
                self.last_ct = self.clock()
            self.count += 1
            try:
                response = self.session.get(url, timeout=(10, 30), allow_redirects=False,
                                            headers={"User-Agent": "PortfolioLotteryReader/1.0 (+https://www.keithriordan.com/contact)"})
            except (requests.Timeout, requests.ConnectionError) as exc:
                if attempt == 2:
                    raise SourceError("Source timed out or could not be reached") from exc
                self.sleep(2 ** attempt)
                continue
            if response.status_code in (401, 403, 429):
                self.blocked.add(host)
                # Do not retry a rate limit, including an arbitrarily long Retry-After.
                # The next daily run is the earliest retry; a long Retry-After is persisted by the runner.
                error = SourceError(f"Source returned HTTP {response.status_code}; refresh stopped")
                error.retry_after = response.headers.get("Retry-After")
                raise error
            if response.status_code in (500, 502, 503, 504) and attempt < 2:
                delay = 2 ** attempt
                if response.headers.get("Retry-After"):
                    raw = response.headers["Retry-After"]
                    try:
                        delay = float(raw) if raw.isdigit() else (parsedate_to_datetime(raw) - datetime.now(timezone.utc)).total_seconds()
                    except (ValueError, TypeError):
                        raise SourceError("Invalid Retry-After; refresh stopped")
                    if delay > 30:
                        error = SourceError("Source requested a later retry; refresh stopped")
                        error.retry_after = raw
                        raise error
                self.sleep(max(0, delay))
                continue
            if response.status_code != 200:
                raise SourceError(f"Source returned HTTP {response.status_code}")
            body = response.text
            if len(body) > 8_000_000:
                raise SourceError("Source document exceeds expected size")
            if re.search(r'<title[^>]*>[^<]*(?:captcha|access denied|just a moment)|cf-chl-|verify you are human', body, re.I):
                self.blocked.add(host)
                raise SourceError("Source challenge detected; refresh stopped")
            return body
        raise SourceError("Source unavailable")


def flight_source(html):
    chunks = []
    for raw in re.findall(r'self\.__next_f\.push\((\[.*?\])\)</script>', html, re.S):
        value = json.loads(raw)
        if value[0] == 1 and isinstance(value[1], str):
            chunks.append(value[1])
    return "".join(chunks)


def flight_values(html, key):
    """Decode server-rendered public Next.js data, without executing scripts or calling /api/."""
    source = flight_source(html)
    decoder = json.JSONDecoder()
    for match in re.finditer(r'"' + re.escape(key) + r'"\s*:\s*', source):
        try:
            yield decoder.raw_decode(source[match.end():])[0]
        except json.JSONDecodeError:
            continue


def flight_text(html, value):
    """Resolve a length-prefixed Flight text record used for some long payment terms."""
    if not re.fullmatch(r'\$[0-9a-f]+', value):
        return value
    source = flight_source(html)
    match = re.search(r'(?:^|\n)' + value[1:] + r':T([0-9a-f]+),', source)
    if not match:
        raise SourceError("CT payment terms reference missing")
    length = int(match[1], 16)
    try:
        return source[match.end():].encode('utf-8')[:length].decode('utf-8')
    except UnicodeDecodeError as exc:
        raise SourceError("CT payment terms incomplete") from exc


def currency(value):
    text = str(value).strip().replace("$$", "$")
    if not re.fullmatch(r'\$?[\d,]+(?:\.\d{1,2})?', text):
        return None
    number = float(text.replace("$", "").replace(",", ""))
    return int(number) if number.is_integer() and number > 0 else None


def plain(value):
    return unescape(re.sub(r'<[^>]*>', '', value)).strip().replace("$$", "$")


def ct_catalog(html):
    candidates = [v for v in flight_values(html, "games") if isinstance(v, list) and v and isinstance(v[0], dict) and "gameNo" in v[0]]
    if len(candidates) != 1 or len(candidates[0]) < 10:
        raise SourceError("CT catalog structure needs verification")
    games = candidates[0]
    if any(type(g.get("gameNo")) is not int or type(g.get("ticketCostRaw")) is not int or g.get("status") not in ("active", "new", "ended") for g in games):
        raise SourceError("CT catalog fields missing or changed")
    if len({g["gameNo"] for g in games}) != len(games):
        raise SourceError("CT catalog contains duplicate games")
    return [g for g in games if g.get("ticketCostRaw") in PRICES and g.get("status") in ("active", "new")]


def ct_game(html, expected_number):
    candidates = [v for v in flight_values(html, "game") if isinstance(v, dict) and str(v.get("gameNo")) == str(expected_number)]
    if len(candidates) != 1:
        raise SourceError("CT game details missing or ambiguous")
    raw = candidates[0]
    required = ("totalTickets", "prizes", "asOf", "status", "ticketCostRaw", "gameName")
    if any(raw.get(k) is None for k in required) or type(raw["totalTickets"]) is not int or raw["totalTickets"] <= 0:
        raise SourceError("CT game inputs missing")
    date = datetime.fromisoformat(raw["asOf"]).replace(tzinfo=EASTERN).astimezone(timezone.utc)
    prizes = sorted(raw["prizes"], key=lambda p: p["amountRaw"], reverse=True)
    if not prizes:
        raise SourceError("CT prize table empty")
    game = dict(game_number=str(expected_number), name=plain(raw.get("displayNameHtml") or raw["gameName"]),
                price=raw["ticketCostRaw"], status="active" if raw["status"] in ("active", "new") else "ended",
                start_date=raw.get("startDate"), end_date=None if str(raw.get("stopDate", "")).startswith("2099") else raw.get("stopDate"),
                source_at=date.isoformat(), url=f"{CT_CATALOG}/{expected_number}", total_tickets=raw["totalTickets"], tiers=[])
    advertised = currency(raw.get("displayTopPrize") or raw.get("topPrize"))
    terms = plain(flight_text(html, raw.get("howToPlay", {}).get("core", "")))
    top_cash = currency(prizes[0]["amountRaw"])
    for index, p in enumerate(prizes):
        original, remaining = p.get("total"), p.get("remaining")
        if type(original) is not int or type(remaining) is not int or not 0 <= remaining <= original or original <= 0:
            raise SourceError("CT prize counts invalid")
        amount = currency(p["amountRaw"])
        label = plain(p["amount"])
        if index == 0 and advertised != top_cash:
            # The public table advertises an annuity while embedded data uses its cash option.
            # Require both values explicitly in the official payment terms.
            values = [currency(v) for v in re.findall(r'\$[\d,]+(?:\.\d{2})?', terms)]
            if advertised and top_cash and advertised in values and top_cash in values and "annuity" in terms.lower() and "cash option" in terms.lower():
                amount = advertised
                term = re.search(r'(\d+)\s*[- ]year\s+annuity', terms, re.I)
                label = f"${advertised:,} {term.group(1) + '-year ' if term else ''}annuity / ${top_cash:,} cash option"
            else:
                amount = None
                game["issue"] = "Advertised prize/payment terms need verification"
        game["tiers"].append(dict(label=label, amount=amount, original=original, remaining=remaining,
                                  launch_probability=original / raw["totalTickets"]))
    if sum(t["original"] for t in game["tiers"]) > raw["totalTickets"]:
        raise SourceError("CT original prize totals exceed tickets")
    return game


def ny_games(rows, metadata, source_at):
    if not isinstance(rows, list) or not rows or len(rows) >= 5000:
        raise SourceError("NY prize feed missing or exceeds collection limit")
    groups = {}
    for r in rows:
        number = str(r["game_number"])
        original, remaining, paid = (int(r[k]) for k in ("total", "unpaid", "paid"))
        # The feed includes zero-count placeholders for unreleased games.
        # They stay unranked until a positive original structure is verified.
        if original < 0 or min(remaining, paid) < 0 or remaining + paid != original:
            raise SourceError("NY prize counts invalid")
        groups.setdefault(number, []).append(r)
    games = []
    for number, prizes in groups.items():
        if number not in metadata:
            games.append(dict(game_number=number, name=prizes[0]["game_name"].strip(), price=None, status="unknown",
                              tiers=[], issue="Awaiting verified game details", source_at=source_at,
                              url="https://nylottery.ny.gov/scratch-off-games"))
            continue
        g = dict(metadata[number], source_at=source_at, tiers=[])
        current = {r["prize_amount"]: r for r in prizes}
        if len(current) != len(prizes) or set(current) != {t["source_label"] for t in metadata[number]["tiers"]}:
            g["issue"] = "Original prize structure changed; verification required"
        else:
            for tier in metadata[number]["tiers"]:
                r = current[tier["source_label"]]
                if int(r["total"]) != tier["original"]:
                    g["issue"] = "Original prize structure changed; verification required"
                g["tiers"].append(dict(tier, remaining=int(r["unpaid"]), launch_probability=1 / tier["odds_denominator"]))
        games.append(g)
    # Do not recommend metadata entries which disappeared from the official prize feed.
    return games


def draw_game(html, slug):
    identifier = slug.replace("-", "")
    statuses = [v for v in flight_values(html, "status") if isinstance(v, dict) and v.get("game") == identifier]
    if len(statuses) != 1:
        raise SourceError("Draw-game status missing or ambiguous")
    raw = statuses[0]
    prices = [g for v in flight_values(html, "games") if isinstance(v, list) for g in v
              if isinstance(g, dict) and g.get("apiSlug") == identifier]
    if not prices:
        raise SourceError("Draw-game price missing")
    price = currency(prices[0]["basePrice"])
    cells = [v for v in flight_values(html, "cells") if isinstance(v, list) and "JACKPOT" in v]
    denominators = {int(m.group(1).replace(",", "")) for row in cells for v in row
                    if isinstance(v, str) and (m := re.fullmatch(r'1 in ([\d,]+)', v))}
    if len(denominators) != 1 or not price or raw.get("jackpotPending"):
        raise SourceError("Draw-game jackpot/odds awaiting publication")
    jackpot, cash = raw["jackpot"], raw["cashValue"]
    if not all(type(v) is int and v > 0 for v in (jackpot, cash)) or cash > jackpot:
        raise SourceError("Draw-game amounts invalid")
    next_draw = datetime.fromisoformat(raw["nextDrawDate"]).replace(tzinfo=EASTERN).astimezone(timezone.utc)
    return dict(name="Powerball" if slug == "powerball" else "Mega Millions", price=price, jackpot=jackpot,
                cash=cash, next_draw=next_draw.isoformat(), odds=denominators.pop(),
                url=f"https://ctlottery.com/games/draw-games/{slug}")
