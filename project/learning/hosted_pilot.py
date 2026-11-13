"""Operator-only configuration for the one-account hosted pilot.

The approval is a content-free cutover record stored in Heroku configuration.
The local launcher freezes paid work before producing it. Its carried spending
is added to the existing PostgreSQL ledger; it never resets with a new month.
This is not a curriculum publication attestation or a learner-facing API.
"""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
from uuid import UUID

from email_validator import validate_email, EmailNotValidError

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "curriculum/idempotency/catalog-v3.json"
HOSTS = ("www.keithriordan.com", "keithriordan.herokuapp.com")
APP_NAME = "keithriordan"
APPROVAL_VARIABLE = "LEARNING_HOSTED_APPROVAL"


class PilotPolicyError(ValueError):
    """Fixed diagnostic text only; never echo configuration or connection secrets."""


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def uuid(value):
    try:
        return isinstance(value, str) and str(UUID(value)) == value
    except ValueError:
        return False


def exact_drafts():
    from project.learning.content_schema import load_catalog
    from project.services.curriculum_service import content_checksum
    catalog = load_catalog(CATALOG)
    return sorted([[item["id"], item["version"], content_checksum(item, catalog["schema_version"])]
                   for item in catalog["items"]])


def _unique_object(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise PilotPolicyError("Duplicate hosted approval field.")
        result[name] = value
    return result


def validate_approval(value):
    fields = {"format_version", "handoff_id", "source_instance_id", "frozen_at", "target_app",
              "owner_id", "owner_email", "total_microusd", "verification_microusd", "carryover_microusd",
              "carryover_by_period", "source_charge_count", "source_ledger_sha256", "draft_revisions"}
    if not isinstance(value, dict) or set(value) != fields or type(value["format_version"]) is not int or value["format_version"] != 1:
        raise PilotPolicyError("Unrecognized hosted approval format.")
    if (not uuid(value["handoff_id"]) or not uuid(value["source_instance_id"])
            or value["target_app"] != APP_NAME or type(value["owner_id"]) is not int or value["owner_id"] < 1):
        raise PilotPolicyError("Invalid hosted pilot identity.")
    try:
        email = validate_email(value["owner_email"], check_deliverability=False).normalized
        frozen = datetime.fromisoformat(value["frozen_at"])
        if email != value["owner_email"] or frozen.tzinfo is None or frozen > datetime.now(timezone.utc):
            raise ValueError
    except (EmailNotValidError, TypeError, ValueError, AttributeError):
        raise PilotPolicyError("Invalid hosted owner or cutover time.") from None
    amounts = ("total_microusd", "verification_microusd", "carryover_microusd", "source_charge_count")
    if (any(type(value[key]) is not int or value[key] < 0 for key in amounts)
            or value["total_microusd"] > 5_000_000
            or value["verification_microusd"] > min(value["total_microusd"], 1_000_000)):
        raise PilotPolicyError("Hosted allowances may not exceed the approved $5 total and $1 verification limits.")
    periods = value["carryover_by_period"]
    if (not isinstance(periods, dict) or len(periods) > 120
            or any(not isinstance(key, str) or not re.fullmatch(r"[0-9]{4}-(0[1-9]|1[0-2])", key)
                   or type(amount) is not int or amount < 0 for key, amount in periods.items())
            or sum(periods.values()) != value["carryover_microusd"]):
        raise PilotPolicyError("The carried monthly spending must match the carried total.")
    if (not isinstance(value["source_ledger_sha256"], str)
            or not re.fullmatch(r"[a-f0-9]{64}", value["source_ledger_sha256"])):
        raise PilotPolicyError("Invalid source ledger fingerprint.")
    if value["draft_revisions"] != exact_drafts():
        raise PilotPolicyError("This hosted approval does not match the exact reviewed draft packet.")
    return value


def load_approval(raw):
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > 16_384:
        raise PilotPolicyError("Supply the private cutover approval file as LEARNING_HOSTED_APPROVAL.")
    try:
        return validate_approval(json.loads(raw, object_pairs_hook=_unique_object))
    except (json.JSONDecodeError, RecursionError):
        raise PilotPolicyError("Invalid hosted approval JSON.") from None


def _bounded_dollars(environ, name, maximum):
    try:
        value = Decimal(environ.get(name, str(maximum)))
        if not value.is_finite() or value < 0 or value * 1_000_000 != (value * 1_000_000).to_integral_value():
            raise ValueError
        return float(min(value, Decimal(str(maximum))))
    except (InvalidOperation, TypeError, ValueError):
        raise PilotPolicyError("Use a nonnegative finite Learning spending limit with at most six decimal places.") from None


def settings(environ):
    enabled = environ.get("LEARNING_HOSTED_PILOT", "0")
    if enabled not in {"0", "1"}:
        raise PilotPolicyError("LEARNING_HOSTED_PILOT must be 0 or 1.")
    if enabled == "0":
        return {"LEARNING_HOSTED_PILOT": False}
    approval = load_approval(environ.get(APPROVAL_VARIABLE))
    mode = environ.get("LEARNING_HOSTED_AI_MODE", "off")
    if mode not in {"off", "verification", "pilot"}:
        raise PilotPolicyError("Choose hosted AI mode off, verification, or pilot.")
    cap = approval["verification_microusd"] if mode == "verification" else approval["total_microusd"]
    monthly = _bounded_dollars(environ, "LEARNING_AI_MONTHLY_CAP_USD", 50)
    warning = _bounded_dollars(environ, "LEARNING_AI_WARN_USD", min(40, int(monthly * 800_000) / 1_000_000))
    return dict(LEARNING_HOSTED_PILOT=True, LEARNING_HOSTED_OWNER_ID=approval["owner_id"],
        LEARNING_HOSTED_APPROVAL=approval, LEARNING_HOSTED_AI_MODE=mode,
        LEARNING_HOSTED_DRAFT_REVISIONS=approval["draft_revisions"],
        LEARNING_AI_OWNER_EMAIL=approval["owner_email"], LEARNING_PRACTICE_ENABLED=True,
        LEARNING_AI_ENABLED=mode != "off" and cap > 0,
        LEARNING_AI_PROVIDER="openai", LEARNING_AI_MODEL="gpt-6.1-sol", LEARNING_AI_SELECTOR_MODEL="gpt-6.1-sol",
        LEARNING_AI_REASONING_EFFORT="low", LEARNING_AI_SERVICE_TIER="default",
        LEARNING_AI_FEEDBACK_MODEL="gpt-6.1-sol", LEARNING_AI_FEEDBACK_REASONING_EFFORT="medium",
        LEARNING_AI_FEEDBACK_MAX_OUTPUT_TOKENS=4000, LEARNING_AI_MAX_OUTPUT_TOKENS=1200,
        LEARNING_AI_SELECTOR_MAX_OUTPUT_TOKENS=200, LEARNING_AI_CONTEXT_BYTES=524_288,
        LEARNING_AI_CALL_SECONDS=60, LEARNING_AI_CHECK_IN_TURNS=24,
        LEARNING_AI_MONTHLY_CAP_USD=monthly, LEARNING_AI_WARN_USD=warning,
        LEARNING_AI_TOTAL_CAP_USD=_bounded_dollars(environ, "LEARNING_AI_TOTAL_CAP_USD", cap / 1_000_000),
        TRUSTED_HOSTS=list(HOSTS), SESSION_COOKIE_SECURE=True, SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax", REMEMBER_COOKIE_SECURE=True,
        REMEMBER_COOKIE_HTTPONLY=True, REMEMBER_COOKIE_SAMESITE="Lax")


def carried_spending(config, period=None):
    if not config.get("LEARNING_HOSTED_PILOT"):
        return 0
    approval = config.get("LEARNING_HOSTED_APPROVAL")
    if not isinstance(approval, dict):
        raise PilotPolicyError("Hosted spending requires its recorded cutover approval.")
    return approval["carryover_microusd"] if period is None else approval["carryover_by_period"].get(period, 0)
