"""Freeze the original local pilot's paid AI before moving its allowance to hosting."""
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

from project.database import db
from project.learning import hosted_pilot as hosted
from project.models import AIRequest, LearningAICharge
from scripts import learning_pilot as pilot, learning_pilot_storage as storage

HANDOFF = "hosted-handoff.json"


def _json_value(value):
    return value.astimezone(timezone.utc).isoformat() if isinstance(value, datetime) else value


def freeze(directory, *, owner_id, owner_email):
    """No remote writes, provider calls, content publication, or progress transfer.

    Requires the server/operator lock. A crash after replacing settings leaves
    local AI disabled; repeating the command completes the same handoff. A
    completed handoff is replayable only for the same target account and costs.
    """
    with storage.operator_lock(directory):
        settings = pilot.load_settings(directory)
        approval = pilot.load_approval(directory, settings)
        if settings["restored"] or not approval:
            raise storage.PilotError("Only the original approved local pilot can hand off its allowance.")
        target = {"owner_id": owner_id, "owner_email": owner_email}
        if settings.get("hosted_handoff_target") not in (None, target):
            raise storage.PilotError("The frozen pilot belongs to a different hosted target. Keep its original cutover choice.")
        app = pilot.app_for(settings, approval=approval)
        with app.app_context():
            try:
                pilot.check_schema()
                if db.session.scalar(select(AIRequest.id).where(AIRequest.status.in_(("pending", "running"))).limit(1)):
                    raise storage.PilotError("Finish or explicitly resolve outstanding AI requests before handing off. No paid request was retried.")
                charges = [dict(row) for row in db.session.execute(
                    select(LearningAICharge.__table__).order_by(LearningAICharge.id)).mappings()]
            finally:
                db.session.remove()
                db.engine.dispose()
        periods = defaultdict(int)
        for charge in charges:
            if charge["state"] != "released":
                amount = charge["cost_microusd"] if charge["state"] == "settled" else charge["reserved_microusd"]
                if type(amount) is not int or amount < 0:
                    raise storage.PilotError("The source ledger needs reconciliation before handoff.")
                periods[charge["period"]] += amount
        digest = hashlib.sha256(hosted.canonical(
            [{key: _json_value(value) for key, value in row.items()} for row in charges]).encode()).hexdigest()
        result = dict(format_version=1, handoff_id=settings.get("hosted_handoff_id") or str(uuid4()),
            source_instance_id=settings["instance_id"], frozen_at=datetime.now(timezone.utc).isoformat(),
            target_app=hosted.APP_NAME, owner_id=owner_id, owner_email=owner_email,
            total_microusd=approval["total_microusd"], verification_microusd=approval["verification_microusd"],
            carryover_microusd=sum(periods.values()), carryover_by_period=dict(periods), source_charge_count=len(charges),
            source_ledger_sha256=digest, draft_revisions=sorted(approval["draft_revisions"]))
        try:
            hosted.validate_approval(result)
        except hosted.PilotPolicyError as exc:
            raise storage.PilotError(str(exc)) from None
        destination = Path(directory) / HANDOFF
        if destination.exists() or destination.is_symlink():
            previous = hosted.validate_approval(storage.read_json(destination))
            if (not settings.get("hosted_handoff_id")
                    or any(previous[key] != result[key] for key in result if key != "frozen_at")):
                raise storage.PilotError("Existing hosted handoff differs. Reconcile it before changing any allowance or target.")
            return destination
        # Disable first, then publish the portable approval. If the second write
        # fails, no usable approval can coexist with a still-live local launcher.
        if not settings.get("hosted_handoff_id"):
            storage.replace_private_json(Path(directory) / pilot.SETTINGS,
                {**settings, "hosted_handoff_id": result["handoff_id"], "hosted_handoff_target": target})
        storage.write_json(destination, result)
        return destination
