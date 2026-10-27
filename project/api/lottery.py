"""Authenticated snapshot reads. No refresh endpoint and no upstream I/O."""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from project.database import db
from project.models import User
from project.lottery.calculations import calculate, odds, utc
from project.lottery.planner import draw_plan
from project.lottery.views import comparison, source_stamp, stamp, status

lottery_api_blueprint = Blueprint("api_lottery", __name__, url_prefix="/lottery")


@lottery_api_blueprint.after_request
def private_response(response):
    response.headers["Cache-Control"] = "private, no-store"
    return response


def authorized():
    try:
        return db.session.get(User, int(get_jwt_identity())) is not None
    except (ValueError, TypeError):
        return False


def serialize_status(info, state):
    snapshot, latest, scheduled = info["snapshot"], info["latest"], info["scheduled"]
    return dict(stale=info["stale"], source_date=source_stamp(snapshot.source_at, state) if snapshot else None,
                source_at=utc(snapshot.source_at).isoformat() if snapshot else None,
                checked_at=utc(info["checked"]).isoformat() if info["checked"] else None,
                checked=stamp(info["checked"]),
                failure=latest.error if latest and latest.status == "failed" else None,
                interrupted=bool(info["interrupted"]),
                scheduled_status=scheduled.status if scheduled else "Not run yet",
                scheduled_at=stamp(scheduled.finished_at or scheduled.started_at) if scheduled else None)


def serialize_game(game, state):
    return dict(game, qualifying_remaining=game["qualifying_remaining"] if game.get("launch_probability") is not None else None,
                estimated_odds=odds(game.get("probability")), original_odds=odds(game.get("launch_probability")),
                dollar_odds=odds(game.get("per_dollar")), source_date=source_stamp(game["source_at"], state) if game.get("source_at") else None)


def draw_payload(state):
    info = status("draw")
    games = info["snapshot"].data["games"] if info["snapshot"] else []
    return dict(plan=draw_plan(state, games, info["stale"]), status=serialize_status(info, "draw"))


@lottery_api_blueprint.get("/scratch-offs")
@jwt_required()
def scratch_offs():
    if not authorized():
        return jsonify(error="Unauthorized."), 401
    context = comparison(request.args)
    return jsonify({**{key: context[key] for key in ("state", "target", "basis", "prices", "available", "query")},
                    "games": [serialize_game(g, context["state"]) for g in context["games"]],
                    "picks": [g["game_number"] for g in context["picks"]],
                    "pending": [serialize_game(calculate(g, context["target"]), context["state"]) for g in context["pending"]],
                    "status": serialize_status(context["info"], context["state"])})


@lottery_api_blueprint.get("/draws")
@jwt_required()
def draws():
    if not authorized():
        return jsonify(error="Unauthorized."), 401
    return jsonify(draw_payload(request.args.get("state", "ny")))


@lottery_api_blueprint.get("/scratch-offs/<state>/<number>")
@jwt_required()
def scratch_off_detail(state, number):
    if not authorized():
        return jsonify(error="Unauthorized."), 401
    if state not in ("ny", "ct"):
        return jsonify(error="Game not found."), 404
    info = status(state)
    games = info["snapshot"].data["games"] if info["snapshot"] else []
    game = next((g for g in games if g["game_number"] == number), None)
    if game is None:
        return jsonify(error="Game not found."), 404
    from project.lottery.calculations import TARGETS
    target = request.args.get("target", 1000, type=int)
    target = target if target in TARGETS else 1000
    return jsonify(game=serialize_game(calculate(game, target), state), target=target,
                   status=serialize_status(info, state))
