from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from flask import Blueprint, make_response, render_template, request
from flask_login import login_required

from .calculations import PRICES, TARGETS, is_stale, money, odds, rank, utc
from .models import LotteryRefreshRun
from .service import latest_snapshot

lottery_blueprint = Blueprint("lottery", __name__)


def stamp(value):
    if not value:
        return "Not yet available"
    return utc(value).astimezone(ZoneInfo("America/New_York")).strftime("%b %-d, %Y · %-I:%M %p %Z")


def source_stamp(value, state):
    # CT publishes a calendar date, not a publication time.
    if state == "ct":
        return utc(value).astimezone(ZoneInfo("America/New_York")).strftime("%b %-d, %Y")
    return stamp(value)


def status(source):
    snapshot = latest_snapshot(source)
    success = LotteryRefreshRun.query.filter_by(source=source, status="success").order_by(LotteryRefreshRun.finished_at.desc()).first()
    latest = LotteryRefreshRun.query.filter_by(source=source).order_by(LotteryRefreshRun.started_at.desc()).first()
    scheduled = LotteryRefreshRun.query.filter_by(source=source, scheduled=True).order_by(LotteryRefreshRun.started_at.desc()).first()
    checked = success.finished_at if success else (snapshot.fetched_at if snapshot else None)
    stale = not snapshot or is_stale(snapshot.source_at, checked)
    interrupted = latest and latest.status == "running" and utc(latest.started_at) < datetime.now(timezone.utc) - timedelta(hours=1)
    return dict(snapshot=snapshot, checked=checked, latest=latest, scheduled=scheduled, stale=stale, interrupted=interrupted)


@lottery_blueprint.get("/scratch-offs")
@login_required
def index():
    state = request.args.get("state", "ny")
    if state not in ("ny", "ct"):
        state = "ny"
    target = request.args.get("preset", type=int) or request.args.get("target", 1000, type=int)
    if target not in TARGETS:
        target = 1000
    basis = "dollar" if request.args.get("basis") == "dollar" else "ticket"
    info, draw = status(state), status("draw")
    games = info["snapshot"].data["games"] if info["snapshot"] else []
    available = sorted({g["price"] for g in games if g.get("price") in PRICES and g.get("status") == "active"})
    prices = [p for p in request.args.getlist("price", type=int) if p in available]
    if not prices and "prices_set" not in request.args:
        prices = available
    query = request.args.get("q", "").strip()[:100]
    ranked = rank([g for g in games if g.get("price") in prices and g.get("status") == "active"], target, basis)
    visible = [g for g in ranked if query.casefold() in (g["name"] + " " + g["game_number"]).casefold()]
    picks = [g for g in visible if not g["reason"]][:3]
    pending = [g for g in games if g.get("price") is None]
    response = make_response(render_template("lottery/index.html", state=state, target=target, basis=basis,
                                            prices=prices, available=available, targets=TARGETS, query=query,
                                            games=visible, picks=picks, pending=pending, info=info, draw=draw,
                                            money=money, odds=odds, stamp=stamp,
                                            source_stamp=lambda value: source_stamp(value, state)))
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response
