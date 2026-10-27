"""Verified retail schedules; calendar math never fetches or buys tickets.

Rules verified 2026-10-26 against the official links returned below. NY's
published close time is 22:00 for both games; CT Mega Millions closes at 22:45.
Advance draws include the next draw. Prices exclude optional Powerball add-ons.
"""
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from .calculations import utc

EASTERN = ZoneInfo("America/New_York")
RULES = (
    dict(name="Powerball", slug="powerball", ny_slug="powerball", days=(0, 2, 5), draw=time(22, 59), price=2, maximum=39),
    dict(name="Mega Millions", slug="mega-millions", ny_slug="megamillions", days=(1, 4), draw=time(23), price=5, maximum=26),
)


def draw_plan(state="ny", summaries=(), stale=True, now=None):
    state = state if state in ("ny", "ct") else "ny"
    now = utc(now or datetime.now(timezone.utc)).astimezone(EASTERN)
    saved = {g["name"]: g for g in summaries}
    games = []
    for rule in RULES:
        cutoff = time(22, 45) if state == "ct" and rule["slug"] == "mega-millions" else time(22)
        upcoming, closed_today = [], False
        for offset in range(8):
            day = now.date() + timedelta(days=offset)
            if day.weekday() not in rule["days"]:
                continue
            close_at = datetime.combine(day, cutoff, EASTERN)
            draw_at = datetime.combine(day, rule["draw"], EASTERN)
            if now >= close_at:
                closed_today = offset == 0 and now < draw_at
                continue
            upcoming.append(dict(date=draw_at.isoformat(), label=draw_at.strftime("%a, %b %-d"), cutoff_at=close_at.isoformat()))
        upcoming = upcoming[:len(rule["days"])]
        source = saved.get(rule["name"])
        matches = bool(source and utc(source["next_draw"]) == utc(upcoming[0]["date"]))
        games.append(dict(
            name=rule["name"], price=rule["price"], maximum_draws=rule["maximum"],
            cutoff=cutoff.strftime("%-I:%M %p") + " ET", sales_closed=closed_today,
            next_draw=upcoming[0], week=upcoming,
            jackpot=source["jackpot"] if source and matches and not stale else None,
            cash=source["cash"] if source and matches and not stale else None,
            odds=source["odds"] if source else None,
            saved_draw=source["next_draw"] if source else None,
            url=(f"https://nylottery.ny.gov/draw-game/?game={rule['ny_slug']}" if state == "ny"
                 else f"https://ctlottery.com/games/draw-games/{rule['slug']}"),
        ))
    return dict(state=state, as_of=now.isoformat(), date_label=now.strftime("%A, %b %-d"), games=games,
                weekly_cost=16, maximum_cost=208, rules_verified="2026-10-26",
                next_draw_stops=[dict(day="Monday", tickets="Powerball for Monday + Mega Millions for Tuesday"),
                                 dict(day="Wednesday", tickets="Powerball for Wednesday"),
                                 dict(day="Friday", tickets="Mega Millions for Friday + Powerball for Saturday")])
